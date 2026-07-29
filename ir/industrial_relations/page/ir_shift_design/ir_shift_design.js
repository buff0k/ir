// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SD_API = "ir.industrial_relations.page.ir_shift_design.ir_shift_design";

// Mirrors Frappe HRMS Shift Type's "color" Select options.
const SHIFT_TYPE_COLORS = {
  Blue: "#3b82f6",
  Cyan: "#06b6d4",
  Fuchsia: "#d946ef",
  Green: "#22c55e",
  Lime: "#84cc16",
  Orange: "#f59e0b",
  Pink: "#ec4899",
  Red: "#ef4444",
  Violet: "#8b5cf6",
  Yellow: "#eab308",
};
const SHIFT_TYPE_FALLBACK_COLOR = "#64748b";

// Deterministic per-team colors (there's no "team color" field - Teams are
// just rows in a Design's own table, so color is assigned by table position).
const TEAM_COLORS = [
  "#3b82f6",
  "#22c55e",
  "#f59e0b",
  "#d946ef",
  "#06b6d4",
  "#ef4444",
  "#84cc16",
  "#8b5cf6",
  "#ec4899",
  "#eab308",
];

// Indexed by moment().day() (Sun=0..Sat=6) - which "Shift Design Shift Type"
// weekday-applicability field to check for a given real date.
const WEEKDAY_APPLIES_FIELDS = [
  "applies_sunday",
  "applies_monday",
  "applies_tuesday",
  "applies_wednesday",
  "applies_thursday",
  "applies_friday",
  "applies_saturday",
];

frappe.pages["ir-shift-design"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: __("Shift Pattern Modeller"),
    single_column: true,
  });

  const app = new ShiftPatternModeller(page, wrapper);
  wrapper.shift_pattern_modeller = app;
  app.init();
};

class ShiftPatternModeller {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = wrapper;
    this.$main = $(page.main);
    this.controls = {};
    this.sim_controls = {};
    this.bootstrap = {};
    this.state = this.blank_state();
    this.simulation = this.blank_simulation();
    this.holidays = new Map();
    this.dirty = false;
    this.drag_assignment = "";
  }

  blank_state() {
    return {
      name: "",
      design_name: "",
      branch: "",
      company: "",
      status: "Draft",
      enabled: 1,
      effective_from: "",
      effective_until: "",
      anchor_date: "",
      number_of_teams: 3,
      cycle_length: 10,
      pay_period_start_day: 1,
      pay_period_end_day: 31,
      ordinary_hours_limit: 195,
      shift_types: [],
      teams: [],
      pattern: [],
      calendar_rules: [],
      date_overrides: [],
    };
  }

  blank_simulation() {
    const start = frappe.datetime.get_today();

    return {
      shift_type_runs: {},
      off_runs: 4,
      stagger_method: "Evenly Stagger",
      simulation_start: start,
      simulation_end: frappe.datetime.add_months(start, 3),
    };
  }

  async init() {
    this.build_shell();
    this.page.set_primary_action(__("Save Shift Design"), () => this.save());
    this.page.add_menu_item(__("Delete Shift Design"), () =>
      this.delete_design(),
    );

    this.bind_events();
    await this.load_bootstrap();
    this.make_controls();
    this.new_design(false);
    this.render_all();
  }

  build_shell() {
    this.$main.html(`
      <div class="sdm-page">
        <section class="sdm-card sdm-header">
          <div class="sdm-header-grid">
            <div data-control="design"></div>
            <div data-control="branch"></div>
            <div data-control="company"></div>
            <div data-control="design_name"></div>
            <div data-control="status"></div>
            <div data-control="effective_from"></div>
            <div data-control="effective_until"></div>
            <div data-control="anchor_date"></div>
            <div data-control="pay_period_start_day"></div>
            <div data-control="pay_period_end_day"></div>
            <div data-control="ordinary_hours_limit"></div>
          </div>

          <div class="sdm-actions">
            <button class="btn btn-sm btn-primary" data-action="new">
              ${__("New")}
            </button>
            <span class="sdm-save-state"></span>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("1. Shift Types")}</div>
              <div class="sdm-card__hint">
                ${__("The real Shift Types this Design rotates between - Day/Night, Morning/Afternoon/Night, or any other combination a site needs.")}
              </div>
            </div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-shift-types"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("2. Generate the Pattern")}</div>
              <div class="sdm-card__hint">
                ${__("Describe the repeating sequence. The modeller infers the cycle and staggers the teams.")}
              </div>
            </div>
          </header>

          <div class="sdm-card__body">
            <div class="sdm-generator-grid">
              <div data-control="number_of_teams"></div>
              <div class="sdm-shift-type-runs"></div>
              <div data-sim-control="off_runs"></div>
              <div data-sim-control="stagger_method"></div>
            </div>

            <div class="sdm-actions">
              <button class="btn btn-sm btn-primary" data-action="generate">
                ${__("Generate Pattern")}
              </button>
              <button class="btn btn-sm btn-default" data-action="add-day">
                ${__("Add Cycle Day")}
              </button>
              <button class="btn btn-sm btn-default" data-action="remove-day">
                ${__("Remove Cycle Day")}
              </button>
            </div>

            <div class="sdm-cycle-summary"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("3. Visual Cycle Editor")}</div>
              <div class="sdm-card__hint">
                ${__("Click a cell to cycle through Shift Types then Off. Drag a chip onto any cell.")}
              </div>
            </div>
            <div class="sdm-palette"></div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-pattern-editor"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("4. Calendar Rules")}</div>
              <div class="sdm-card__hint">
                ${__("Special-case a Public Holiday or a specific weekday - e.g. 'on Sunday, only the team that had Day continues, using this Shift Type'. The target Shift Type doesn't need to be one of the rotating Shift Types above.")}
              </div>
            </div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-calendar-rules"></div>
            <div class="sdm-actions">
              <button class="btn btn-sm btn-default" data-action="add-calendar-rule">
                ${__("Add Calendar Rule")}
              </button>
            </div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("5. Calendar Simulation")}</div>
              <div class="sdm-card__hint">
                ${__("Expand the cycle over real dates to test Sundays, public holidays and coverage.")}
              </div>
            </div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-simulation-grid">
              <div data-sim-control="simulation_start"></div>
              <div data-sim-control="simulation_end"></div>
            </div>
            <div class="sdm-actions">
              <button class="btn btn-sm btn-primary" data-action="simulate">
                ${__("Recalculate Simulation")}
              </button>
            </div>
            <div class="sdm-calendar"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("6. Team Hours and Coverage")}</div>
              <div class="sdm-card__hint">
                ${__("Pay-period summaries use the configured start and end day, not necessarily calendar months.")}
              </div>
            </div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-hours-summary"></div>
            <div class="sdm-monthly-hours"></div>
            <div class="sdm-coverage-summary"></div>
          </div>
        </section>
      </div>
    `);
  }

  async load_bootstrap() {
    const response = await frappe.call({
      method: `${SD_API}.get_bootstrap`,
    });

    this.bootstrap = response.message || {};
    this.validate_schema();
  }

  validate_schema() {
    const parentFields = new Set(this.bootstrap.parent_fields || []);
    const shiftTypeFields = new Set(this.bootstrap.shift_type_fields || []);
    const patternFields = new Set(this.bootstrap.pattern_fields || []);
    const ruleFields = new Set(this.bootstrap.calendar_rule_fields || []);

    const requiredParentFields = [
      "pay_period_start_day",
      "pay_period_end_day",
      "ordinary_hours_limit",
    ];

    const missingParentFields = requiredParentFields.filter(
      (fieldname) => !parentFields.has(fieldname),
    );

    const missingShiftTypeFields = ["shift_type"].filter(
      (fieldname) => !shiftTypeFields.has(fieldname),
    );

    const missingPatternFields = ["team_key", "pattern_day", "assignment"].filter(
      (fieldname) => !patternFields.has(fieldname),
    );

    const missingRuleFields = [
      "rule_type",
      "day_of_week",
      "action",
      "target_shift_type",
      "hours_override",
      "enabled",
    ].filter((fieldname) => !ruleFields.has(fieldname));

    if (
      missingParentFields.length ||
      missingShiftTypeFields.length ||
      missingPatternFields.length ||
      missingRuleFields.length
    ) {
      frappe.msgprint({
        title: __("Shift Design schema must be updated"),
        indicator: "orange",
        message: __(
          "Apply the supplied GUI DocType changes before relying on save/reload. Missing parent fields: {0}. Missing shift-type fields: {1}. Missing pattern fields: {2}. Missing calendar-rule fields: {3}.",
          [
            missingParentFields.join(", ") || __("None"),
            missingShiftTypeFields.join(", ") || __("None"),
            missingPatternFields.join(", ") || __("None"),
            missingRuleFields.join(", ") || __("None"),
          ],
        ),
      });
    }
  }

  make_controls() {
    this.controls.design = this.control("design", "Link", __("Shift Design"), {
      options: "Shift Design",
    });
    this.controls.branch = this.control("branch", "Link", __("Branch"), {
      options: "Branch",
    });
    this.controls.company = this.control("company", "Link", __("Company"), {
      options: "Company",
    });
    this.controls.design_name = this.control(
      "design_name",
      "Data",
      __("Design Name"),
      { reqd: 1 },
    );
    this.controls.number_of_teams = this.control(
      "number_of_teams",
      "Int",
      __("Number of Shift Teams"),
      { reqd: 1 },
    );
    this.controls.status = this.control("status", "Select", __("Status"), {
      options: "Draft\nActive\nSuperseded\nArchived",
      reqd: 1,
    });
    this.controls.effective_from = this.control(
      "effective_from",
      "Date",
      __("Effective From"),
      { reqd: 1 },
    );
    this.controls.effective_until = this.control(
      "effective_until",
      "Date",
      __("Effective Until"),
    );
    this.controls.anchor_date = this.control(
      "anchor_date",
      "Date",
      __("Cycle Anchor Date"),
      { reqd: 1 },
    );
    this.controls.pay_period_start_day = this.control(
      "pay_period_start_day",
      "Int",
      __("Pay Period Start Day"),
      { reqd: 1 },
    );
    this.controls.pay_period_end_day = this.control(
      "pay_period_end_day",
      "Int",
      __("Pay Period End Day"),
      { reqd: 1 },
    );
    this.controls.ordinary_hours_limit = this.control(
      "ordinary_hours_limit",
      "Float",
      __("Ordinary Hours Limit"),
      { reqd: 1 },
    );
    this.sim_controls.off_runs = this.sim_control(
      "off_runs",
      "Int",
      __("Consecutive Off Days"),
    );
    this.sim_controls.stagger_method = this.sim_control(
      "stagger_method",
      "Select",
      __("Team Stagger"),
      { options: "Evenly Stagger\nSequential Blocks" },
    );
    this.sim_controls.simulation_start = this.sim_control(
      "simulation_start",
      "Date",
      __("Simulation Start"),
    );
    this.sim_controls.simulation_end = this.sim_control(
      "simulation_end",
      "Date",
      __("Simulation End"),
    );

    this.bind_control(this.controls.design, async (value) => {
      if (value && value !== this.state.name) {
        await this.load_design(value);
      }
    });

    this.bind_control(this.controls.number_of_teams, (value) => {
      this.state.number_of_teams = Math.max(cint(value), 1);
      this.controls.number_of_teams.set_value(this.state.number_of_teams);
      this.ensure_teams();
      this.mark_dirty();
      this.render_pattern();
      this.render_cycle_summary();
      this.simulate();
    });

    for (const [fieldname, control] of Object.entries(this.controls)) {
      if (fieldname === "design" || fieldname === "number_of_teams") {
        continue;
      }

      this.bind_control(control, (value) => {
        if (
          [
            "pay_period_start_day",
            "pay_period_end_day",
            "ordinary_hours_limit",
          ].includes(fieldname)
        ) {
          value = flt(value);
        }

        this.state[fieldname] = value;

        if (
          fieldname === "effective_from" &&
          value &&
          !this.state.anchor_date
        ) {
          this.state.anchor_date = value;
          this.controls.anchor_date.set_value(value);
        }

        this.mark_dirty();
        this.render_pattern();
        this.simulate();
      });
    }

    for (const [fieldname, control] of Object.entries(this.sim_controls)) {
      this.bind_control(control, (value) => {
        if (["off_runs"].includes(fieldname)) {
          value = flt(value);
        }

        this.simulation[fieldname] = value;
      });
    }

    this.sync_controls();
  }

  control(fieldname, fieldtype, label, extra = {}) {
    return frappe.ui.form.make_control({
      parent: this.$main.find(`[data-control="${fieldname}"]`),
      df: {
        fieldname,
        fieldtype,
        label,
        ...extra,
      },
      render_input: true,
    });
  }

  sim_control(fieldname, fieldtype, label, extra = {}) {
    return frappe.ui.form.make_control({
      parent: this.$main.find(`[data-sim-control="${fieldname}"]`),
      df: {
        fieldname,
        fieldtype,
        label,
        ...extra,
      },
      render_input: true,
    });
  }

  bind_control(control, handler) {
    if (!control?.$input) {
      return;
    }

    const namespace = `.sdm-${control.df.fieldname}`;
    control.$input.off(namespace);
    control.$input.on(
      `change${namespace} awesomplete-selectcomplete${namespace}`,
      () => Promise.resolve(handler(control.get_value())).catch((error) => this.error(error)),
    );
  }

  bind_events() {
    this.$main.on("click", "[data-action]", (event) => {
      const action = $(event.currentTarget).data("action");

      if (action === "new") this.new_design();
      if (action === "generate") this.generate_pattern();
      if (action === "simulate") this.simulate();
      if (action === "add-day") this.change_cycle(1);
      if (action === "remove-day") this.change_cycle(-1);
      if (action === "add-shift-type") this.add_shift_type();
      if (action === "remove-shift-type") {
        this.remove_shift_type($(event.currentTarget).data("shift-type"));
      }
      if (action === "add-calendar-rule") this.add_calendar_rule();
      if (action === "remove-calendar-rule") {
        this.remove_calendar_rule(cint($(event.currentTarget).data("rule-index")));
      }
    });

    this.$main.on("change input", "[data-shifttype-runs]", (event) => {
      const shiftType = $(event.currentTarget).data("shifttype-runs");
      this.simulation.shift_type_runs[shiftType] = cint(
        event.currentTarget.value,
      );
    });

    this.$main.on("change", "[data-rule-field]", (event) => {
      const $el = $(event.currentTarget);
      const index = cint($el.closest("[data-rule-index]").data("rule-index"));
      const field = $el.data("rule-field");
      let value = $el.val();

      if (field === "enabled") {
        value = event.currentTarget.checked ? 1 : 0;
      } else if (field === "priority") {
        value = cint(value);
      } else if (field === "hours_override") {
        value = value === "" ? null : flt(value);
      }

      this.update_calendar_rule_field(index, field, value);
    });

    this.$main.on("click", ".sdm-cell", (event) => {
      const cell = $(event.currentTarget);
      const currentAssignment = cell.attr("data-assignment") || "";

      this.set_cell_from_element(
        cell,
        this.next_assignment(currentAssignment),
      );
    });

    this.$main.on("dragstart", ".sdm-chip", (event) => {
      this.drag_assignment = $(event.currentTarget).data("assignment");
      event.originalEvent.dataTransfer.setData(
        "text/plain",
        this.drag_assignment,
      );
    });

    this.$main.on("dragover", ".sdm-cell", (event) => {
      event.preventDefault();
    });

    this.$main.on("drop", ".sdm-cell", (event) => {
      event.preventDefault();
      const assignment =
        event.originalEvent.dataTransfer.getData("text/plain") ||
        this.drag_assignment;

      this.set_cell_from_element($(event.currentTarget), assignment);
    });
  }

  new_design(render = true) {
    this.state = this.blank_state();
    this.simulation = this.blank_simulation();
    this.ensure_teams();
    this.ensure_shift_type_runs();
    this.dirty = false;

    if (render) {
      this.sync_controls();
      this.render_all();
    }
  }

  async load_design(name) {
    const response = await frappe.call({
      method: `${SD_API}.get_design`,
      args: { name },
    });

    this.state = {
      ...this.blank_state(),
      ...(response.message || {}),
    };

    this.ensure_teams();
    this.ensure_shift_type_runs();
    this.dirty = false;
    this.sync_controls();
    this.render_all();
    this.simulate();
  }

  sync_controls() {
    for (const [fieldname, control] of Object.entries(this.controls)) {
      control.set_value(this.state[fieldname] ?? "");
    }

    this.sync_sim_controls();
  }

  sync_sim_controls() {
    for (const [fieldname, control] of Object.entries(this.sim_controls)) {
      control.set_value(this.simulation[fieldname] ?? "");
    }
  }

  render_all() {
    this.render_shift_type_controls();
    this.render_pattern();
    this.render_calendar_rules();
    this.render_cycle_summary();
    this.render_save_state();
  }

  ensure_teams() {
    const count = Math.max(cint(this.state.number_of_teams), 1);

    while (this.state.teams.length < count) {
      const index = this.state.teams.length;
      this.state.teams.push({
        team_key: this.key("TEAM"),
        team_name: `Shift ${this.alpha(index)}`,
        display_order: index + 1,
        pattern_offset: 0,
        enabled: 1,
      });
    }

    if (this.state.teams.length > count) {
      this.state.teams = this.state.teams.slice(0, count);
      const validKeys = new Set(this.state.teams.map((team) => team.team_key));
      this.state.pattern = (this.state.pattern || []).filter((row) =>
        validKeys.has(row.team_key),
      );
      this.state.date_overrides = (this.state.date_overrides || []).filter(
        (row) => !row.team_key || validKeys.has(row.team_key),
      );
    }
  }

  ensure_shift_type_runs() {
    this.simulation.shift_type_runs ||= {};
    for (const row of this.state.shift_types || []) {
      if (!(row.shift_type in this.simulation.shift_type_runs)) {
        this.simulation.shift_type_runs[row.shift_type] = 3;
      }
    }
  }

  add_shift_type() {
    const value = this.shift_type_picker?.get_value();
    if (!value) {
      return;
    }

    if ((this.state.shift_types || []).some((row) => row.shift_type === value)) {
      frappe.show_alert({
        message: __("That Shift Type is already added."),
        indicator: "orange",
      });
      return;
    }

    this.state.shift_types.push({ shift_type: value });
    this.ensure_shift_type_runs();
    this.mark_dirty();
    this.render_shift_type_controls();
    this.render_pattern();
    this.simulate();
  }

  remove_shift_type(shiftType) {
    if (!shiftType) {
      return;
    }

    this.state.shift_types = (this.state.shift_types || []).filter(
      (row) => row.shift_type !== shiftType,
    );
    delete this.simulation.shift_type_runs[shiftType];

    this.state.pattern = (this.state.pattern || []).filter(
      (row) => row.assignment !== shiftType,
    );
    this.state.date_overrides = (this.state.date_overrides || []).filter(
      (row) => row.assignment !== shiftType,
    );
    this.state.calendar_rules = (this.state.calendar_rules || []).filter(
      (row) => row.target_shift_type !== shiftType,
    );

    this.mark_dirty();
    this.render_shift_type_controls();
    this.render_pattern();
    this.simulate();
  }

  shift_type_color(name) {
    const row = (this.bootstrap.shift_types || []).find((r) => r.name === name);
    return SHIFT_TYPE_COLORS[row?.color] || SHIFT_TYPE_FALLBACK_COLOR;
  }

  team_color(teamKey) {
    const teams = this.state.teams || [];
    const index = teams.findIndex((row) => row.team_key === teamKey);
    return TEAM_COLORS[index >= 0 ? index % TEAM_COLORS.length : 0];
  }

  is_allowed_on_weekday(shiftTypeName, date) {
    if (!shiftTypeName) return true;

    const row = (this.state.shift_types || []).find(
      (item) => item.shift_type === shiftTypeName,
    );
    if (!row) return true;

    const fieldname = WEEKDAY_APPLIES_FIELDS[moment(date).day()];
    const value = row[fieldname];
    return value === undefined || value === null || !!cint(value);
  }

  render_shift_type_controls() {
    const shiftTypes = this.state.shift_types || [];

    const listRows = shiftTypes
      .map(
        (row) => `
          <div class="sdm-shifttype-row">
            <span class="sdm-shifttype-row__swatch" style="background:${this.shift_type_color(row.shift_type)}"></span>
            <span class="sdm-shifttype-row__name">${frappe.utils.escape_html(row.shift_type)}</span>
            <button type="button" class="btn btn-xs btn-default" data-action="remove-shift-type" data-shift-type="${this.attr(row.shift_type)}">&times;</button>
          </div>
        `,
      )
      .join("");

    this.$main.find(".sdm-shift-types").html(`
      <div class="sdm-shifttype-list">
        ${listRows || `<div class="sdm-empty">${__("No Shift Types added yet.")}</div>`}
      </div>
      <div class="sdm-shifttype-add">
        <div data-control="shift_type_picker"></div>
        <button type="button" class="btn btn-sm btn-default" data-action="add-shift-type">${__("Add Shift Type")}</button>
      </div>
    `);

    this.shift_type_picker = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="shift_type_picker"]'),
      df: {
        fieldname: "shift_type_picker",
        fieldtype: "Link",
        label: __("Shift Type"),
        options: "Shift Type",
        // Add as soon as a value is picked/confirmed - no separate button
        // click needed. The button stays as a fallback/no-op-safe re-trigger.
        onchange: () => this.add_shift_type(),
      },
      render_input: true,
    });

    const runRows = shiftTypes
      .map(
        (row) => `
          <div class="sdm-run-input">
            <label>${frappe.utils.escape_html(row.shift_type)}</label>
            <input
              type="number"
              min="0"
              class="form-control"
              data-shifttype-runs="${this.attr(row.shift_type)}"
              value="${this.simulation.shift_type_runs?.[row.shift_type] ?? 3}">
          </div>
        `,
      )
      .join("");

    this.$main.find(".sdm-shift-type-runs").html(
      runRows || `<div class="sdm-empty">${__("Add Shift Types above first.")}</div>`,
    );

    const chips = shiftTypes
      .map((row) => {
        const color = this.shift_type_color(row.shift_type);
        return `
          <span
            class="sdm-chip"
            draggable="true"
            data-assignment="${this.attr(row.shift_type)}"
            style="background:color-mix(in srgb, ${color} 20%, transparent);border-color:${color}">
            ${frappe.utils.escape_html(row.shift_type)}
          </span>
        `;
      })
      .join("");

    this.$main.find(".sdm-palette").html(`
      ${chips}
      <span class="sdm-chip sdm-chip--off" draggable="true" data-assignment="">${__("Off")}</span>
    `);
  }

  add_calendar_rule() {
    this.state.calendar_rules.push({
      priority: 10,
      rule_type: "Weekday",
      day_of_week: "Sunday",
      action: "Follow Pattern",
      target_shift_type: "",
      hours_override: null,
      enabled: 1,
      notes: "",
    });
    this.mark_dirty();
    this.render_calendar_rules();
    this.simulate();
  }

  remove_calendar_rule(index) {
    this.state.calendar_rules.splice(index, 1);
    this.mark_dirty();
    this.render_calendar_rules();
    this.simulate();
  }

  update_calendar_rule_field(index, field, value) {
    const rule = this.state.calendar_rules[index];
    if (!rule) {
      return;
    }

    rule[field] = value;
    this.mark_dirty();

    if (field === "rule_type" || field === "action") {
      // Dependent fields (Day of Week / Target Shift Type) show or hide.
      this.render_calendar_rules();
    }

    this.simulate();
  }

  render_calendar_rules() {
    const rules = this.state.calendar_rules || [];
    const weekdays = [
      "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    ];
    const actions = [
      "Follow Pattern", "No Work", "Continue Previous Shift Team",
    ];
    const actionsNeedingTarget = new Set(["Continue Previous Shift Team"]);

    const rows = rules
      .map((rule, index) => {
        const needsWeekday = rule.rule_type === "Weekday";
        const needsTarget = actionsNeedingTarget.has(rule.action);

        const targetOptions = (this.bootstrap.shift_types || [])
          .map(
            (st) => `
              <option value="${this.attr(st.name)}" ${rule.target_shift_type === st.name ? "selected" : ""}>
                ${frappe.utils.escape_html(st.name)}
              </option>
            `,
          )
          .join("");

        return `
          <tr data-rule-index="${index}">
            <td>
              <select class="form-control" data-rule-field="rule_type">
                <option value="Public Holiday" ${rule.rule_type === "Public Holiday" ? "selected" : ""}>${__("Public Holiday")}</option>
                <option value="Weekday" ${rule.rule_type === "Weekday" ? "selected" : ""}>${__("Weekday")}</option>
              </select>
            </td>
            <td>
              ${needsWeekday
                ? `
              <select class="form-control" data-rule-field="day_of_week">
                ${weekdays.map((day) => `<option value="${day}" ${rule.day_of_week === day ? "selected" : ""}>${__(day)}</option>`).join("")}
              </select>`
                : `<span class="text-muted">—</span>`}
            </td>
            <td>
              <select class="form-control" data-rule-field="action">
                ${actions.map((action) => `<option value="${this.attr(action)}" ${rule.action === action ? "selected" : ""}>${__(action)}</option>`).join("")}
              </select>
            </td>
            <td>
              ${needsTarget
                ? `
              <select class="form-control" data-rule-field="target_shift_type">
                <option value="">${__("Select...")}</option>
                ${targetOptions}
              </select>`
                : `<span class="text-muted">—</span>`}
            </td>
            <td>
              <input
                type="number"
                step="0.25"
                class="form-control"
                data-rule-field="hours_override"
                value="${rule.hours_override ?? ""}"
                placeholder="${__("auto")}">
            </td>
            <td>
              <input
                type="number"
                class="form-control"
                data-rule-field="priority"
                value="${rule.priority ?? 10}">
            </td>
            <td class="text-center">
              <input type="checkbox" data-rule-field="enabled" ${cint(rule.enabled ?? 1) ? "checked" : ""}>
            </td>
            <td>
              <button type="button" class="btn btn-xs btn-default" data-action="remove-calendar-rule" data-rule-index="${index}">
                &times;
              </button>
            </td>
          </tr>
        `;
      })
      .join("");

    this.$main.find(".sdm-calendar-rules").html(`
      <div class="sdm-table-scroll">
        <table class="sdm-summary-table sdm-rules-table">
          <thead>
            <tr>
              <th>${__("Rule Type")}</th>
              <th>${__("Day of Week")}</th>
              <th>${__("Action")}</th>
              <th>${__("Target Shift Type")}</th>
              <th>${__("Hours Override")}</th>
              <th>${__("Priority")}</th>
              <th>${__("Enabled")}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            ${rows || `<tr><td colspan="8" class="text-muted">${__("No Calendar Rules yet.")}</td></tr>`}
          </tbody>
        </table>
      </div>
    `);
  }

  generate_pattern() {
    const shiftTypes = this.state.shift_types || [];

    if (!shiftTypes.length) {
      frappe.msgprint(__("Add at least one Shift Type first."));
      return;
    }

    const offRuns = Math.max(cint(this.simulation.off_runs), 0);
    const basePattern = [];

    for (const row of shiftTypes) {
      const runs = Math.max(
        cint(this.simulation.shift_type_runs?.[row.shift_type]),
        0,
      );
      for (let i = 0; i < runs; i++) basePattern.push(row.shift_type);
    }
    for (let i = 0; i < offRuns; i++) basePattern.push("");

    if (!basePattern.length) {
      frappe.msgprint(__("The generated cycle must contain at least one day."));
      return;
    }

    this.state.cycle_length = basePattern.length;
    this.ensure_teams();
    this.state.pattern = [];

    const teams = this.enabled_teams();

    teams.forEach((team, index) => {
      const offset = this.infer_offset(
        index,
        teams.length,
        basePattern.length,
      );

      team.pattern_offset = offset;

      for (let day = 1; day <= basePattern.length; day++) {
        const sourceIndex =
          (day - 1 - offset + basePattern.length * 10) %
          basePattern.length;
        const assignment = basePattern[sourceIndex];

        this.state.pattern.push({
          team_key: team.team_key,
          team_name: team.team_name,
          pattern_day: day,
          assignment,
          notes: "",
        });
      }
    });

    this.mark_dirty();
    this.render_pattern();
    this.render_cycle_summary();
    this.simulate();
  }

  infer_offset(index, teamCount, cycleLength) {
    if (this.simulation.stagger_method === "Sequential Blocks") {
      return Math.floor((index * cycleLength) / teamCount);
    }

    return Math.round((index * cycleLength) / teamCount) % cycleLength;
  }


  render_pattern() {
    const teams = this.enabled_teams();
    const days = Math.max(cint(this.state.cycle_length), 1);

    if (!teams.length) {
      this.$main.find(".sdm-pattern-editor").html(`
        <div class="sdm-empty">${__("Import or define Shift Teams first.")}</div>
      `);
      return;
    }

    let header = "";
    for (let day = 1; day <= days; day++) {
      const date = this.pattern_date(day);
      header += `
        <th>
          <div>${__("Day")} ${day}</div>
          <small>${date || ""}</small>
          <small>${date ? moment(date).format("ddd") : ""}</small>
        </th>
      `;
    }

    const rows = teams
      .map((team) => {
        let cells = "";

        for (let day = 1; day <= days; day++) {
          const assignment = this.assignment(team.team_key, day);
          const isOff = !assignment;
          const color = isOff ? "" : this.shift_type_color(assignment);
          const style = isOff
            ? ""
            : `style="background:color-mix(in srgb, ${color} 18%, var(--card-bg));border-color:${color}"`;

          cells += `
            <td
              class="sdm-cell ${isOff ? "sdm-cell--off" : ""}"
              ${style}
              data-team="${this.attr(team.team_key)}"
              data-day="${day}"
              data-assignment="${this.attr(assignment)}">
              ${this.badge(assignment)}
            </td>
          `;
        }

        const teamColor = this.team_color(team.team_key);

        return `
          <tr>
            <td class="sdm-team-name" style="border-left:3px solid ${teamColor}">
              ${frappe.utils.escape_html(team.team_name)}
            </td>
            ${cells}
          </tr>
        `;
      })
      .join("");

    this.$main.find(".sdm-pattern-editor").html(`
      <div class="sdm-pattern-scroll">
        <table class="sdm-pattern-table">
          <thead>
            <tr>
              <th class="sdm-team-name">${__("Team")}</th>
              ${header}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
  }

  set_cell_from_element(cell, assignment) {
    const teamKey = cell.data("team");
    const patternDay = cint(cell.data("day"));
    let row = this.state.pattern.find(
      (item) =>
        item.team_key === teamKey &&
        cint(item.pattern_day) === patternDay,
    );

    const team = this.state.teams.find(
      (item) => item.team_key === teamKey,
    );

    if (!row) {
      row = {
        team_key: teamKey,
        team_name: team?.team_name || "",
        pattern_day: patternDay,
        assignment,
        notes: "",
      };
      this.state.pattern.push(row);
    } else {
      row.assignment = assignment;
    }

    const isOff = !assignment;
    const color = isOff ? "" : this.shift_type_color(assignment);
    const style = isOff
      ? ""
      : `background:color-mix(in srgb, ${color} 18%, var(--card-bg));border-color:${color}`;

    cell
      .attr("data-assignment", assignment)
      .data("assignment", assignment)
      .toggleClass("sdm-cell--off", isOff)
      .attr("style", style)
      .html(this.badge(assignment));

    this.mark_dirty();
    this.simulate();
  }

  change_cycle(delta) {
    const nextLength = Math.max(cint(this.state.cycle_length) + delta, 1);
    this.state.cycle_length = nextLength;

    if (delta < 0) {
      this.state.pattern = this.state.pattern.filter(
        (row) => cint(row.pattern_day) <= nextLength,
      );
    }

    this.mark_dirty();
    this.render_pattern();
    this.render_cycle_summary();
    this.simulate();
  }

  async simulate() {
    const start = this.simulation.simulation_start;
    const end = this.simulation_end_date();

    if (!start || !end) {
      return;
    }

    const response = await frappe.call({
      method: `${SD_API}.get_sa_public_holidays`,
      args: {
        start_date: start,
        end_date: end,
      },
    });

    this.holidays = new Map(
      (response.message || []).map((row) => [
        row.date,
        row.description,
      ]),
    );

    this.render_calendar();
    this.render_hours();
  }

  render_calendar() {
    const teams = this.enabled_teams();
    const dates = this.date_range();
    const dateSet = new Set(dates);
    const monthStarts = {};

    dates.forEach((date) => {
      const key = moment(date).format("YYYY-MM");
      monthStarts[key] ||= moment(`${key}-01`);
    });

    const weekdayHead = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
      .map((label) => `<div class="sdm-weekday-head">${__(label)}</div>`)
      .join("");

    const html = Object.keys(monthStarts)
      .sort()
      .map((monthKey) => {
        const monthStart = monthStarts[monthKey];
        const title = monthStart.format("MMMM YYYY");
        const daysInMonth = monthStart.daysInMonth();
        // Monday-start column index: moment .day() is Sun=0..Sat=6.
        const leadingBlanks = (monthStart.day() + 6) % 7;

        let cells = "";
        for (let i = 0; i < leadingBlanks; i++) {
          cells += `<div class="sdm-date sdm-date--pad"></div>`;
        }

        for (let day = 1; day <= daysInMonth; day++) {
          const date = monthStart.clone().date(day).format("YYYY-MM-DD");

          if (!dateSet.has(date)) {
            cells += `
              <div class="sdm-date sdm-date--out">
                <div class="sdm-date__head"><b>${day}</b></div>
              </div>
            `;
            continue;
          }

          const isSunday = moment(date).day() === 0;
          const holidayName = this.holidays.get(date) || "";
          const assignments = this.assignments_for_date(date);

          const teamRows = teams
            .map((team) => {
              const assignment = assignments[team.team_key] || "";
              const isOff = !assignment;
              // Color by team here (not shift type) - teams are already
              // listed in the same top-to-bottom order everywhere else
              // (pattern grid, hours tables), so a consistent team color
              // lets the shift name itself convey which team is on it.
              const color = isOff ? "" : this.team_color(team.team_key);
              const style = isOff
                ? ""
                : `style="background:color-mix(in srgb, ${color} 20%, transparent)"`;
              const isConflict =
                !isOff && !this.is_allowed_on_weekday(assignment, date);
              const label = this.assignment_label(assignment, team.team_name);
              // Full label always in a title, since narrow viewports
              // ellipsis-truncate the visible text (see ir_ui.css).
              const titleText = isConflict
                ? __("{0} - not configured to apply on this weekday.", [label])
                : label;

              return `
                <span class="sdm-mini ${isOff ? "sdm-mini--off" : ""} ${isConflict ? "sdm-mini--conflict" : ""}" ${style} title="${this.attr(titleText)}">
                  ${label}
                </span>
              `;
            })
            .join("");

          cells += `
            <div class="sdm-date ${isSunday ? "is-sunday" : ""} ${holidayName ? "is-holiday" : ""}">
              <div class="sdm-date__head">
                <b>${day}</b>
              </div>
              <div class="sdm-holiday">${
                holidayName
                  ? frappe.utils.escape_html(holidayName)
                  : "&nbsp;"
              }</div>
              <div class="sdm-date__teams">${teamRows}</div>
            </div>
          `;
        }

        const trailingBlanks = (7 - ((leadingBlanks + daysInMonth) % 7)) % 7;
        for (let i = 0; i < trailingBlanks; i++) {
          cells += `<div class="sdm-date sdm-date--pad"></div>`;
        }

        return `
          <div class="sdm-month">
            <h4>${title}</h4>
            <div class="sdm-month-grid sdm-month-grid--head">${weekdayHead}</div>
            <div class="sdm-month-grid">${cells}</div>
          </div>
        `;
      })
      .join("");

    this.$main.find(".sdm-calendar").html(
      html || `<div class="sdm-empty">${__("No simulation dates.")}</div>`,
    );
  }

  render_hours() {
    const teams = this.enabled_teams();
    const dates = this.date_range();
    const totals = {};
    const periods = {};
    const ordinaryUsed = {};

    teams.forEach((team) => {
      totals[team.team_key] = this.empty_hours_row(team.team_key, team.team_name);
    });

    for (const date of dates) {
      const assignments = this.assignments_for_date(date);
      const period = this.pay_period_for_date(date);

      periods[period.key] ||= {
        label: period.label,
        rows: {},
      };

      for (const team of teams) {
        const assignment = assignments[team.team_key] || "";
        if (!assignment) {
          continue;
        }

        const hours = this.hours_for(assignment, date);
        const totalRow = totals[team.team_key];
        const periodRows = periods[period.key].rows;
        periodRows[team.team_key] ||= this.empty_hours_row(team.team_key, team.team_name);
        const periodRow = periodRows[team.team_key];

        this.add_assignment_hours(totalRow, assignment, hours);
        this.add_assignment_hours(periodRow, assignment, hours);

        if (this.holidays.has(date)) {
          totalRow.holiday += hours;
          periodRow.holiday += hours;
          continue;
        }

        if (moment(date).day() === 0) {
          totalRow.sunday += hours;
          periodRow.sunday += hours;
          continue;
        }

        const ordinaryKey = `${team.team_key}:${period.key}`;
        ordinaryUsed[ordinaryKey] ||= 0;
        const limit = flt(this.state.ordinary_hours_limit || 0);
        const ordinary = Math.max(
          Math.min(hours, limit - ordinaryUsed[ordinaryKey]),
          0,
        );

        totalRow.ordinary += ordinary;
        totalRow.overtime += hours - ordinary;
        periodRow.ordinary += ordinary;
        periodRow.overtime += hours - ordinary;
        ordinaryUsed[ordinaryKey] += hours;
      }
    }

    this.render_total_hours_table(Object.values(totals));
    this.render_pay_period_hours_table(periods);
    this.render_coverage(teams, dates);
  }

  empty_hours_row(teamKey, teamName) {
    return {
      team_key: teamKey,
      team: teamName,
      ordinary: 0,
      overtime: 0,
      sunday: 0,
      holiday: 0,
      total: 0,
      by_type: {},
    };
  }

  add_assignment_hours(row, assignment, hours) {
    row.total += hours;
    row.by_type[assignment] = (row.by_type[assignment] || 0) + hours;
  }

  shift_type_names() {
    return (this.state.shift_types || []).map((row) => row.shift_type);
  }

  render_total_hours_table(rows) {
    const shiftTypeNames = this.shift_type_names();
    const body = rows
      .map((row) => this.hours_table_row(row, false, shiftTypeNames))
      .join("");

    this.$main.find(".sdm-hours-summary").html(`
      <h4 class="sdm-subheading">${__("Simulation Totals")}</h4>
      ${this.hours_table_html(body, false, shiftTypeNames)}
    `);
  }

  render_pay_period_hours_table(periods) {
    const shiftTypeNames = this.shift_type_names();
    const body = Object.values(periods)
      .sort((left, right) => left.label.localeCompare(right.label))
      .map((period) => {
        const rows = Object.values(period.rows).sort((left, right) =>
          left.team.localeCompare(right.team),
        );

        return rows
          .map((row, index) => {
            const periodCell =
              index === 0
                ? `<td rowspan="${rows.length}">${frappe.utils.escape_html(period.label)}</td>`
                : "";
            return this.hours_table_row(row, true, shiftTypeNames, periodCell);
          })
          .join("");
      })
      .join("");

    this.$main.find(".sdm-monthly-hours").html(`
      <h4 class="sdm-subheading">${__("Pay Period Breakdown")}</h4>
      ${this.hours_table_html(body, true, shiftTypeNames)}
    `);
  }

  hours_table_html(body, includePeriod, shiftTypeNames) {
    const typeHeaders = (shiftTypeNames || [])
      .map((name) => `<th>${frappe.utils.escape_html(name)}</th>`)
      .join("");

    return `
      <div class="sdm-table-scroll">
        <table class="sdm-summary-table">
          <thead>
            <tr>
              ${includePeriod ? `<th>${__("Pay Period")}</th>` : ""}
              <th>${__("Team")}</th>
              <th>${__("Ordinary")}</th>
              <th>${__("Normal OT")}</th>
              <th>${__("Sunday")}</th>
              <th>${__("Public Holiday")}</th>
              <th>${__("Total")}</th>
              ${typeHeaders}
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  hours_table_row(row, includePeriod, shiftTypeNames, periodCell) {
    const typeCells = (shiftTypeNames || [])
      .map((name) => `<td>${this.num(row.by_type[name] || 0)}</td>`)
      .join("");
    const teamColor = this.team_color(row.team_key);

    return `
      <tr>
        ${includePeriod ? (periodCell ?? `<td>${frappe.utils.escape_html(row.period || "")}</td>`) : ""}
        <td class="sdm-team-cell" style="border-left:3px solid ${teamColor}">${frappe.utils.escape_html(row.team)}</td>
        <td>${this.num(row.ordinary)}</td>
        <td>${this.num(row.overtime)}</td>
        <td>${this.num(row.sunday)}</td>
        <td>${this.num(row.holiday)}</td>
        <td>${this.num(row.total)}</td>
        ${typeCells}
      </tr>
    `;
  }

  render_coverage(teams, dates) {
    const shiftTypeNames = this.shift_type_names();
    const missing = {};
    const overlapping = {};

    for (const name of shiftTypeNames) {
      missing[name] = 0;
      overlapping[name] = 0;
    }

    for (const date of dates) {
      const assignments = Object.values(this.assignments_for_date(date));
      for (const name of shiftTypeNames) {
        const count = assignments.filter((value) => value === name).length;
        if (!count) missing[name] += 1;
        if (count > 1) overlapping[name] += 1;
      }
    }

    const kpis = shiftTypeNames
      .flatMap((name) => [
        `<div class="sdm-kpi"><span>${__("Days without {0} coverage", [name])}</span><b>${missing[name]}</b></div>`,
        `<div class="sdm-kpi"><span>${__("Days with overlapping {0} teams", [name])}</span><b>${overlapping[name]}</b></div>`,
      ])
      .join("");

    this.$main.find(".sdm-coverage-summary").html(`
      <div class="sdm-kpis">
        ${kpis || `<div class="sdm-empty">${__("Add Shift Types to see coverage.")}</div>`}
      </div>
    `);
  }

  render_cycle_summary() {
    const cycleDays = Math.max(cint(this.state.cycle_length), 1);
    const weekdayRepeatDays = this.least_common_multiple(cycleDays, 7);
    const fullWeeks = weekdayRepeatDays / 7;
    const hasWeekdayDependency = (this.state.calendar_rules || []).some(
      (row) =>
        cint(row.enabled ?? 1) &&
        row.rule_type === "Weekday" &&
        row.action !== "Follow Pattern",
    );
    const operationalDays = hasWeekdayDependency ? weekdayRepeatDays : cycleDays;
    const operationalLabel = hasWeekdayDependency
      ? `${operationalDays} ${__("days")} (${fullWeeks} ${__("full weeks")})`
      : `${operationalDays} ${__("days")}`;

    this.$main.find(".sdm-cycle-summary").html(`
      <div class="sdm-cycle-kpis">
        <div>
          <span>${__("Team cycle")}</span>
          <b>${cycleDays} ${__("days")}</b>
        </div>
        <div>
          <span>${__("Enabled teams")}</span>
          <b>${this.enabled_teams().length}</b>
        </div>
        <div>
          <span>${__("Operational repeat")}</span>
          <b>${operationalLabel}</b>
        </div>
        <div>
          <span>${__("Same weekday alignment")}</span>
          <b>${fullWeeks} ${__("full weeks")}</b>
        </div>
      </div>
    `);
  }

  least_common_multiple(left, right) {
    return Math.abs(left * right) / this.greatest_common_divisor(left, right);
  }

  greatest_common_divisor(left, right) {
    let a = Math.abs(left);
    let b = Math.abs(right);

    while (b) {
      [a, b] = [b, a % b];
    }

    return a || 1;
  }

  calendar_rule_matches(row, date) {
    if (row.rule_type === "Public Holiday") {
      return this.holidays.has(date);
    }
    if (row.rule_type === "Weekday") {
      return moment(date).format("dddd") === row.day_of_week;
    }
    return false;
  }

  matching_calendar_rule(date) {
    const rules = (this.state.calendar_rules || [])
      .filter((row) => cint(row.enabled ?? 1))
      .filter((row) => this.calendar_rule_matches(row, date));

    if (!rules.length) {
      return null;
    }

    const rank = (row) => (row.rule_type === "Public Holiday" ? 0 : 1);
    rules.sort((a, b) => rank(a) - rank(b) || cint(a.priority) - cint(b.priority));

    return rules[0];
  }

  base_assignment_for_date(date, teamKey) {
    return this.assignment(teamKey, this.pattern_day_for_date(date));
  }

  apply_rule_action(assignments, rule, date, teams) {
    const action = rule.action;
    const result = { ...assignments };

    if (action === "No Work") {
      for (const team of teams) result[team.team_key] = "";
      return result;
    }

    if (action === "Continue Previous Shift Team") {
      return this.apply_continuation_takeover(teams, date, rule.target_shift_type);
    }

    return result;
  }

  apply_continuation_takeover(teams, date, targetAssignment) {
    // Full takeover: only the team(s) that had `targetAssignment` on the
    // previous calendar day work today, on that same assignment - every
    // other team is Off, regardless of what the raw pattern says for them.
    const previousDate = moment(date).subtract(1, "day").format("YYYY-MM-DD");
    const continuingTeams = teams
      .filter(
        (team) =>
          this.base_assignment_for_date(previousDate, team.team_key) ===
          targetAssignment,
      )
      .map((team) => team.team_key);

    const result = {};
    for (const team of teams) {
      result[team.team_key] = continuingTeams.includes(team.team_key)
        ? targetAssignment
        : "";
    }
    return result;
  }

  date_overrides_for(date) {
    const result = {};
    for (const row of this.state.date_overrides || []) {
      if (
        cint(row.enabled ?? 1) &&
        row.date &&
        moment(row.date).format("YYYY-MM-DD") === date &&
        row.team_key
      ) {
        result[row.team_key] = row.assignment || "";
      }
    }
    return result;
  }

  assignments_for_date(date) {
    const patternDay = this.pattern_day_for_date(date);
    const teams = this.enabled_teams();
    let assignments = {};

    for (const team of teams) {
      assignments[team.team_key] = this.assignment(team.team_key, patternDay);
    }

    const rule = this.matching_calendar_rule(date);
    if (rule && rule.action !== "Follow Pattern") {
      assignments = this.apply_rule_action(assignments, rule, date, teams);
    }

    const overrides = this.date_overrides_for(date);
    for (const [teamKey, forced] of Object.entries(overrides)) {
      if (teamKey in assignments) {
        assignments[teamKey] = forced;
      }
    }

    return assignments;
  }

  pay_period_for_date(date) {
    const current = moment(date).startOf("day");
    const startDay = Math.max(cint(this.state.pay_period_start_day), 1);
    const endDay = Math.max(cint(this.state.pay_period_end_day), 1);

    if (startDay === 1 && endDay >= 28) {
      const start = current.clone().startOf("month");
      const end = current.clone().endOf("month");
      return {
        key: start.format("YYYY-MM-DD"),
        label: start.format("MMMM YYYY"),
        start,
        end,
      };
    }

    let start;
    let end;

    if (current.date() >= startDay) {
      start = current.clone().date(Math.min(startDay, current.daysInMonth()));
      const nextMonth = current.clone().add(1, "month");
      end = nextMonth
        .clone()
        .date(Math.min(endDay, nextMonth.daysInMonth()));
    } else {
      const previousMonth = current.clone().subtract(1, "month");
      start = previousMonth
        .clone()
        .date(Math.min(startDay, previousMonth.daysInMonth()));
      end = current.clone().date(Math.min(endDay, current.daysInMonth()));
    }

    return {
      key: start.format("YYYY-MM-DD"),
      label: `${start.format("D MMM YYYY")} – ${end.format("D MMM YYYY")}`,
      start,
      end,
    };
  }

  async save() {
    const validationError = this.validate();
    if (validationError) {
      frappe.msgprint({
        title: __("Cannot Save"),
        indicator: "red",
        message: validationError,
      });
      return;
    }

    const response = await frappe.call({
      method: `${SD_API}.save_design`,
      args: {
        data: JSON.stringify(this.state),
      },
      freeze: true,
      freeze_message: __("Saving Shift Design..."),
    });

    this.state = {
      ...this.blank_state(),
      ...(response.message.design || {}),
    };
    this.ensure_shift_type_runs();
    this.dirty = false;
    this.sync_controls();
    this.render_all();

    frappe.show_alert({
      message: __("Shift Design saved."),
      indicator: "green",
    });
  }

  validate() {
    if (!this.state.design_name) return __("Design Name is required.");
    if (!this.state.effective_from) return __("Effective From is required.");
    if (!this.state.anchor_date) return __("Cycle Anchor Date is required.");
    if (!this.state.shift_types.length) return __("At least one Shift Type is required.");
    if (!this.state.teams.length) return __("At least one Shift Team is required.");

    const startDay = cint(this.state.pay_period_start_day);
    const endDay = cint(this.state.pay_period_end_day);
    if (startDay < 1 || startDay > 31 || endDay < 1 || endDay > 31) {
      return __("Pay Period start and end days must be between 1 and 31.");
    }

    return "";
  }

  async delete_design() {
    if (!this.state.name) {
      return;
    }

    frappe.confirm(__("Delete {0}?", [this.state.name]), async () => {
      await frappe.call({
        method: `${SD_API}.delete_design`,
        args: { name: this.state.name },
      });
      this.new_design();
    });
  }

  enabled_teams() {
    return this.state.teams.filter((row) => cint(row.enabled));
  }

  assignment(teamKey, patternDay) {
    return (
      this.state.pattern.find(
        (row) =>
          row.team_key === teamKey &&
          cint(row.pattern_day) === cint(patternDay),
      )?.assignment || ""
    );
  }

  hours_for(assignment, date) {
    if (!assignment) {
      return 0;
    }

    const rule = this.matching_calendar_rule(date);
    // Frappe Float fields never store true NULL - 0 and "unset" both come
    // back as 0, and a genuine 0-hour override has no meaning distinct from
    // the "No Work" action, so treat any falsy value as "no override".
    const override = flt(rule?.hours_override);
    if (override) {
      return override;
    }

    const shiftType = (this.bootstrap.shift_types || []).find(
      (row) => row.name === assignment,
    );

    // No fallback: Shift Types are the sole provider of shift-length hours,
    // and validate_shift_types() on save rejects any Shift Type that can't
    // compute a duration, so this should always be a real number.
    return flt(shiftType?.hours);
  }

  pattern_date(day) {
    return this.state.anchor_date
      ? frappe.datetime.add_days(this.state.anchor_date, day - 1)
      : "";
  }

  pattern_day_for_date(date) {
    if (!this.state.anchor_date) {
      return 1;
    }

    const difference = moment(date)
      .startOf("day")
      .diff(moment(this.state.anchor_date).startOf("day"), "days");
    const length = Math.max(cint(this.state.cycle_length), 1);

    return ((difference % length) + length) % length + 1;
  }

  simulation_end_date() {
    const requestedEnd = this.simulation.simulation_end;
    const effectiveUntil = this.state.effective_until;

    if (!requestedEnd) {
      return effectiveUntil || "";
    }

    if (!effectiveUntil) {
      return requestedEnd;
    }

    return moment(requestedEnd).isBefore(effectiveUntil, "day")
      ? requestedEnd
      : effectiveUntil;
  }

  date_range() {
    const result = [];
    let current = moment(this.simulation.simulation_start);
    const end = moment(this.simulation_end_date());

    while (
      current.isValid() &&
      end.isValid() &&
      current.isSameOrBefore(end, "day") &&
      result.length < 1096
    ) {
      result.push(current.format("YYYY-MM-DD"));
      current.add(1, "day");
    }

    return result;
  }

  next_assignment(assignment) {
    const shiftTypes = (this.state.shift_types || []).map((row) => row.shift_type);
    if (!assignment) {
      return shiftTypes[0] || "";
    }
    const index = shiftTypes.indexOf(assignment);
    if (index === -1 || index === shiftTypes.length - 1) {
      return "";
    }
    return shiftTypes[index + 1];
  }

  badge(assignment) {
    if (!assignment) {
      return `<span class="sdm-assignment sdm-assignment--off">O</span>`;
    }

    const color = this.shift_type_color(assignment);
    const letter = (assignment.match(/[A-Za-z]/) || ["?"])[0].toUpperCase();
    return `<span class="sdm-assignment" style="background:${color};color:#fff" title="${this.attr(assignment)}">${letter}</span>`;
  }

  assignment_label(assignment, teamName) {
    const teamSuffix = String(teamName || "").replace(/^Shift\s+/i, "");
    const label = assignment
      ? __("{0} {1}", [assignment, teamSuffix])
      : __("Off {0}", [teamSuffix]);

    return frappe.utils.escape_html(label);
  }

  num(value) {
    return flt(value).toFixed(2);
  }

  mark_dirty() {
    this.dirty = true;
    this.render_save_state();
  }

  render_save_state() {
    this.$main.find(".sdm-save-state").html(
      this.dirty
        ? `<span class="sdm-dirty">${__("Unsaved changes")}</span>`
        : `<span class="text-muted">${__("Saved")}</span>`,
    );
  }

  error(error) {
    console.error(error);
    frappe.msgprint({
      title: __("Shift Pattern Modeller"),
      indicator: "red",
      message: error.message || String(error),
    });
  }

  key(prefix) {
    return `${prefix}::${Math.random().toString(36).slice(2, 12).toUpperCase()}`;
  }

  alpha(index) {
    let value = index + 1;
    let label = "";

    while (value > 0) {
      value -= 1;
      label = String.fromCharCode(65 + (value % 26)) + label;
      value = Math.floor(value / 26);
    }

    return label;
  }

  attr(value) {
    return frappe.utils
      .escape_html(String(value ?? ""))
      .replaceAll('"', "&quot;");
  }
}
