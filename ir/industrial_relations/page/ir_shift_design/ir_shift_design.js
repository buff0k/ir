// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SD_API = "ir.industrial_relations.page.ir_shift_design.ir_shift_design";

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
      day_shift_type: "",
      night_shift_type: "",
      pay_period_start_day: 1,
      pay_period_end_day: 31,
      ordinary_hours_limit: 195,
      sunday_rule: "Extend Saturday Day Team",
      teams: [],
      pattern: [],
      calendar_rules: [],
      date_overrides: [],
    };
  }

  blank_simulation() {
    const start = frappe.datetime.get_today();

    return {
      day_runs: 3,
      night_runs: 3,
      off_runs: 4,
      stagger_method: "Evenly Stagger",
      simulation_start: start,
      simulation_end: frappe.datetime.add_months(start, 3),
      default_day_hours: 12,
      default_night_hours: 12,
      weekday_hours: {
        Monday: { day: "", night: "" },
        Tuesday: { day: "", night: "" },
        Wednesday: { day: "", night: "" },
        Thursday: { day: "", night: "" },
        Friday: { day: "", night: "" },
        Saturday: { day: "", night: "" },
        Sunday: { day: "", night: "" },
      },
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
            <div data-control="day_shift_type"></div>
            <div data-control="night_shift_type"></div>
            <div data-control="pay_period_start_day"></div>
            <div data-control="pay_period_end_day"></div>
            <div data-control="ordinary_hours_limit"></div>
            <div data-control="sunday_rule"></div>
          </div>

          <div class="sdm-actions">
            <button class="btn btn-sm btn-primary" data-action="new">
              ${__("New")}
            </button>
            <button class="btn btn-sm btn-default" data-action="import">
              ${__("Import Organogram Teams")}
            </button>
            <span class="sdm-save-state"></span>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("1. Generate the Pattern")}</div>
              <div class="sdm-card__hint">
                ${__("Describe the repeating sequence. The modeller infers the cycle and staggers the teams.")}
              </div>
            </div>
          </header>

          <div class="sdm-card__body">
            <div class="sdm-generator-grid">
              <div data-sim-control="day_runs"></div>
              <div data-sim-control="night_runs"></div>
              <div data-sim-control="off_runs"></div>
              <div data-sim-control="stagger_method"></div>
              <div data-sim-control="default_day_hours"></div>
              <div data-sim-control="default_night_hours"></div>
            </div>

            <div class="sdm-actions">
              <button class="btn btn-sm btn-primary" data-action="generate">
                ${__("Generate Pattern")}
              </button>
              <button class="btn btn-sm btn-default" data-preset="3,3,4">
                3D 3N 4O
              </button>
              <button class="btn btn-sm btn-default" data-preset="4,4,4">
                4D 4N 4O
              </button>
              <button class="btn btn-sm btn-default" data-preset="2,2,4">
                2D 2N 4O
              </button>
              <button class="btn btn-sm btn-default" data-action="add-day">
                ${__("Add Cycle Day")}
              </button>
              <button class="btn btn-sm btn-default" data-action="remove-day">
                ${__("Remove Cycle Day")}
              </button>
            </div>

            <div class="sdm-cycle-summary"></div>

            <h4 class="sdm-subheading">${__("Weekday Shift Hours")}</h4>
            <div class="text-muted small">
              ${__("Leave an override blank to use the linked Shift Type duration. Set only days that differ, such as Sunday Day = 8.")}
            </div>
            <div class="sdm-weekday-hours"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("2. Visual Cycle Editor")}</div>
              <div class="sdm-card__hint">
                ${__("Click cells to cycle Off → Day → Night. Drag D, N or O onto any cell.")}
              </div>
            </div>
            <div class="sdm-palette">
              <span class="sdm-chip sdm-chip--day" draggable="true" data-assignment="Day">
                D ${__("Day")}
              </span>
              <span class="sdm-chip sdm-chip--night" draggable="true" data-assignment="Night">
                N ${__("Night")}
              </span>
              <span class="sdm-chip sdm-chip--off" draggable="true" data-assignment="Off">
                O ${__("Off")}
              </span>
            </div>
          </header>
          <div class="sdm-card__body">
            <div class="sdm-pattern-editor"></div>
          </div>
        </section>

        <section class="sdm-card">
          <header class="sdm-card__header">
            <div>
              <div class="sdm-card__title">${__("3. Calendar Simulation")}</div>
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
              <div class="sdm-card__title">${__("4. Team Hours and Coverage")}</div>
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
    const patternFields = new Set(this.bootstrap.pattern_fields || []);
    const ruleFields = new Set(this.bootstrap.calendar_rule_fields || []);

    const requiredParentFields = [
      "day_shift_type",
      "night_shift_type",
      "pay_period_start_day",
      "pay_period_end_day",
      "ordinary_hours_limit",
      "sunday_rule",
    ];

    const missingParentFields = requiredParentFields.filter(
      (fieldname) => !parentFields.has(fieldname),
    );

    const missingPatternFields = ["team_key", "pattern_day", "assignment"].filter(
      (fieldname) => !patternFields.has(fieldname),
    );

    const missingRuleFields = [
      "rule_type",
      "day_of_week",
      "action",
      "day_shift_hours",
      "night_shift_hours",
      "enabled",
    ].filter((fieldname) => !ruleFields.has(fieldname));

    if (
      missingParentFields.length ||
      missingPatternFields.length ||
      missingRuleFields.length
    ) {
      frappe.msgprint({
        title: __("Shift Design schema must be updated"),
        indicator: "orange",
        message: __(
          "Apply the supplied GUI DocType changes before relying on save/reload. Missing parent fields: {0}. Missing pattern fields: {1}. Missing calendar-rule fields: {2}.",
          [
            missingParentFields.join(", ") || __("None"),
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
      reqd: 1,
    });
    this.controls.company = this.control("company", "Link", __("Company"), {
      options: "Company",
      reqd: 1,
    });
    this.controls.design_name = this.control(
      "design_name",
      "Data",
      __("Design Name"),
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
    this.controls.day_shift_type = this.control(
      "day_shift_type",
      "Link",
      __("Day Shift Type"),
      { options: "Shift Type", reqd: 1 },
    );
    this.controls.night_shift_type = this.control(
      "night_shift_type",
      "Link",
      __("Night Shift Type"),
      { options: "Shift Type", reqd: 1 },
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
    this.controls.sunday_rule = this.control(
      "sunday_rule",
      "Select",
      __("Sunday Rule"),
      {
        options: "Follow Pattern\nExtend Saturday Day Team",
        reqd: 1,
      },
    );

    this.sim_controls.day_runs = this.sim_control(
      "day_runs",
      "Int",
      __("Consecutive Day Shifts"),
    );
    this.sim_controls.night_runs = this.sim_control(
      "night_runs",
      "Int",
      __("Consecutive Night Shifts"),
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
    this.sim_controls.default_day_hours = this.sim_control(
      "default_day_hours",
      "Float",
      __("Fallback Day Hours"),
    );
    this.sim_controls.default_night_hours = this.sim_control(
      "default_night_hours",
      "Float",
      __("Fallback Night Hours"),
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

    for (const [fieldname, control] of Object.entries(this.controls)) {
      if (fieldname === "design") {
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
        if (
          [
            "day_runs",
            "night_runs",
            "off_runs",
            "default_day_hours",
            "default_night_hours",
          ].includes(fieldname)
        ) {
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
      if (action === "import") this.import_dialog();
      if (action === "generate") this.generate_pattern();
      if (action === "simulate") this.simulate();
      if (action === "add-day") this.change_cycle(1);
      if (action === "remove-day") this.change_cycle(-1);
    });

    this.$main.on("click", "[data-preset]", (event) => {
      const [dayRuns, nightRuns, offRuns] = String(
        $(event.currentTarget).data("preset"),
      )
        .split(",")
        .map(cint);

      this.simulation.day_runs = dayRuns;
      this.simulation.night_runs = nightRuns;
      this.simulation.off_runs = offRuns;
      this.sync_sim_controls();
      this.generate_pattern();
    });

    this.$main.on("change input", "[data-weekday-hour]", (event) =>
      this.weekday_hour_change(event),
    );

    this.$main.on("click", ".sdm-cell", (event) => {
      const cell = $(event.currentTarget);
      const currentAssignment = cell.attr("data-assignment") || "Off";

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
    this.simulation.weekday_hours = this.infer_weekday_hours();
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
    this.render_pattern();
    this.render_cycle_summary();
    this.render_weekday_hours();
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
    }
  }

  generate_pattern() {
    const dayRuns = Math.max(cint(this.simulation.day_runs), 0);
    const nightRuns = Math.max(cint(this.simulation.night_runs), 0);
    const offRuns = Math.max(cint(this.simulation.off_runs), 0);

    const basePattern = [
      ...Array(dayRuns).fill("Day"),
      ...Array(nightRuns).fill("Night"),
      ...Array(offRuns).fill("Off"),
    ];

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
          shift_type: this.shift_type_for(assignment),
          notes: "",
        });
      }
    });

    this.sync_calendar_rules();
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

  render_weekday_hours() {
    const weekdays = [
      "Monday",
      "Tuesday",
      "Wednesday",
      "Thursday",
      "Friday",
      "Saturday",
      "Sunday",
    ];

    const rows = weekdays
      .map((weekday) => {
        const values = this.simulation.weekday_hours[weekday] || {
          day: "",
          night: "",
        };

        return `
          <tr>
            <td>${__(weekday)}</td>
            <td>
              <input
                class="form-control"
                type="number"
                min="0"
                step="0.25"
                data-weekday-hour="${weekday}.day"
                value="${this.attr(values.day)}"
                placeholder="${__("Shift Type")}">
            </td>
            <td>
              <input
                class="form-control"
                type="number"
                min="0"
                step="0.25"
                data-weekday-hour="${weekday}.night"
                value="${this.attr(values.night)}"
                placeholder="${__("Shift Type")}">
            </td>
          </tr>
        `;
      })
      .join("");

    this.$main.find(".sdm-weekday-hours").html(`
      <div class="sdm-table-scroll">
        <table class="sdm-summary-table">
          <thead>
            <tr>
              <th>${__("Weekday")}</th>
              <th>${__("Day Shift Hours")}</th>
              <th>${__("Night Shift Hours")}</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);
  }

  weekday_hour_change(event) {
    const path = String(
      $(event.currentTarget).data("weekday-hour") || "",
    );
    const [weekday, assignmentType] = path.split(".");

    if (!weekday || !assignmentType) {
      return;
    }

    const rawValue = event.currentTarget.value;
    this.simulation.weekday_hours[weekday] ||= {
      day: "",
      night: "",
    };
    this.simulation.weekday_hours[weekday][assignmentType] =
      rawValue === "" ? "" : flt(rawValue);

    this.sync_calendar_rules();
    this.mark_dirty();
    this.simulate();
  }

  infer_weekday_hours() {
    const result = this.blank_simulation().weekday_hours;

    for (const row of this.state.calendar_rules || []) {
      if (
        row.rule_type !== "Weekday" ||
        !row.day_of_week ||
        !cint(row.enabled)
      ) {
        continue;
      }

      if (!result[row.day_of_week]) {
        continue;
      }

      result[row.day_of_week] = {
        day:
          row.day_shift_hours === null ||
          row.day_shift_hours === undefined
            ? ""
            : row.day_shift_hours,
        night:
          row.night_shift_hours === null ||
          row.night_shift_hours === undefined
            ? ""
            : row.night_shift_hours,
      };
    }

    return result;
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
          cells += `
            <td
              class="sdm-cell sdm-cell--${assignment.toLowerCase()}"
              data-team="${this.attr(team.team_key)}"
              data-day="${day}"
              data-assignment="${assignment}">
              ${this.badge(assignment)}
            </td>
          `;
        }

        return `
          <tr>
            <td class="sdm-team-name">
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
        shift_type: this.shift_type_for(assignment),
        notes: "",
      };
      this.state.pattern.push(row);
    } else {
      row.assignment = assignment;
      row.shift_type = this.shift_type_for(assignment);
    }

    cell
      .attr("data-assignment", assignment)
      .data("assignment", assignment)
      .removeClass("sdm-cell--day sdm-cell--night sdm-cell--off")
      .addClass(`sdm-cell--${assignment.toLowerCase()}`)
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
    const months = {};

    dates.forEach((date) => {
      const key = moment(date).format("YYYY-MM");
      months[key] ||= [];
      months[key].push(date);
    });

    const html = Object.entries(months)
      .map(([monthKey, monthDates]) => {
        const title = moment(`${monthKey}-01`).format("MMMM YYYY");

        const cells = monthDates
          .map((date) => {
            const isSunday = moment(date).day() === 0;
            const holidayName = this.holidays.get(date) || "";
            const assignments = this.assignments_for_date(date);

            const teamRows = teams
              .map((team) => {
                const assignment = assignments[team.team_key] || "Off";
                return `
                  <span class="sdm-mini sdm-mini--${assignment.toLowerCase()}">
                    ${this.assignment_label(assignment, team.team_name)}
                  </span>
                `;
              })
              .join("");

            return `
              <div class="sdm-date ${isSunday ? "is-sunday" : ""} ${holidayName ? "is-holiday" : ""}">
                <div class="sdm-date__head">
                  <b>${moment(date).format("D")}</b>
                  <span>${moment(date).format("ddd")}</span>
                </div>
                <div class="sdm-holiday">${
                  holidayName
                    ? frappe.utils.escape_html(holidayName)
                    : "&nbsp;"
                }</div>
                <div class="sdm-date__teams">${teamRows}</div>
              </div>
            `;
          })
          .join("");

        return `
          <div class="sdm-month">
            <h4>${title}</h4>
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
      totals[team.team_key] = this.empty_hours_row(team.team_name);
    });

    for (const date of dates) {
      const assignments = this.assignments_for_date(date);
      const period = this.pay_period_for_date(date);

      periods[period.key] ||= {
        label: period.label,
        rows: {},
      };

      for (const team of teams) {
        const assignment = assignments[team.team_key] || "Off";
        if (assignment === "Off") {
          continue;
        }

        const hours = this.hours_for(assignment, date);
        const totalRow = totals[team.team_key];
        const periodRows = periods[period.key].rows;
        periodRows[team.team_key] ||= this.empty_hours_row(team.team_name);
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

  empty_hours_row(teamName) {
    return {
      team: teamName,
      ordinary: 0,
      overtime: 0,
      sunday: 0,
      holiday: 0,
      total: 0,
      day: 0,
      night: 0,
    };
  }

  add_assignment_hours(row, assignment, hours) {
    row.total += hours;
    row[assignment.toLowerCase()] += hours;
  }

  render_total_hours_table(rows) {
    const body = rows
      .map((row) => this.hours_table_row(row, false))
      .join("");

    this.$main.find(".sdm-hours-summary").html(`
      <h4 class="sdm-subheading">${__("Simulation Totals")}</h4>
      ${this.hours_table_html(body, false)}
    `);
  }

  render_pay_period_hours_table(periods) {
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

            return `
              <tr>
                ${periodCell}
                <td>${frappe.utils.escape_html(row.team)}</td>
                <td>${this.num(row.ordinary)}</td>
                <td>${this.num(row.overtime)}</td>
                <td>${this.num(row.sunday)}</td>
                <td>${this.num(row.holiday)}</td>
                <td>${this.num(row.total)}</td>
                <td>${this.num(row.day)}</td>
                <td>${this.num(row.night)}</td>
              </tr>
            `;
          })
          .join("");
      })
      .join("");

    this.$main.find(".sdm-monthly-hours").html(`
      <h4 class="sdm-subheading">${__("Pay Period Breakdown")}</h4>
      ${this.hours_table_html(body, true)}
    `);
  }

  hours_table_html(body, includePeriod) {
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
              <th>${__("Day")}</th>
              <th>${__("Night")}</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `;
  }

  hours_table_row(row, includePeriod) {
    return `
      <tr>
        ${includePeriod ? `<td>${frappe.utils.escape_html(row.period || "")}</td>` : ""}
        <td>${frappe.utils.escape_html(row.team)}</td>
        <td>${this.num(row.ordinary)}</td>
        <td>${this.num(row.overtime)}</td>
        <td>${this.num(row.sunday)}</td>
        <td>${this.num(row.holiday)}</td>
        <td>${this.num(row.total)}</td>
        <td>${this.num(row.day)}</td>
        <td>${this.num(row.night)}</td>
      </tr>
    `;
  }

  render_coverage(teams, dates) {
    let missingDay = 0;
    let missingNight = 0;
    let overlappingDay = 0;
    let overlappingNight = 0;

    for (const date of dates) {
      const assignments = Object.values(this.assignments_for_date(date));
      const dayCount = assignments.filter((value) => value === "Day").length;
      const nightCount = assignments.filter((value) => value === "Night").length;

      if (!dayCount) missingDay += 1;
      if (!nightCount) missingNight += 1;
      if (dayCount > 1) overlappingDay += 1;
      if (nightCount > 1) overlappingNight += 1;
    }

    this.$main.find(".sdm-coverage-summary").html(`
      <div class="sdm-kpis">
        <div class="sdm-kpi">
          <span>${__("Days without day coverage")}</span>
          <b>${missingDay}</b>
        </div>
        <div class="sdm-kpi">
          <span>${__("Days without night coverage")}</span>
          <b>${missingNight}</b>
        </div>
        <div class="sdm-kpi">
          <span>${__("Days with overlapping day teams")}</span>
          <b>${overlappingDay}</b>
        </div>
        <div class="sdm-kpi">
          <span>${__("Days with overlapping night teams")}</span>
          <b>${overlappingNight}</b>
        </div>
      </div>
    `);
  }

  render_cycle_summary() {
    const cycleDays = Math.max(cint(this.state.cycle_length), 1);
    const weekdayRepeatDays = this.least_common_multiple(cycleDays, 7);
    const fullWeeks = weekdayRepeatDays / 7;

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
          <b>${cycleDays} ${__("days")}</b>
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

  async import_dialog() {
    const dialog = new frappe.ui.Dialog({
      title: __("Import Organogram Teams"),
      fields: [
        {
          fieldname: "site_organogram",
          fieldtype: "Link",
          label: __("Site Organogram"),
          options: "Site Organogram",
          reqd: 1,
          get_query: () => ({
            filters: this.state.branch ? { branch: this.state.branch } : {},
          }),
        },
        {
          fieldname: "mode",
          fieldtype: "Select",
          label: __("Mode"),
          options: "Replace\nMerge",
          default: "Replace",
          reqd: 1,
        },
      ],
      primary_action_label: __("Import"),
      primary_action: async (values) => {
        const response = await frappe.call({
          method: `${SD_API}.import_organogram_teams`,
          args: {
            site_organogram: values.site_organogram,
          },
        });

        const data = response.message || {};

        if (values.mode === "Replace") {
          this.state.teams = [];
          this.state.pattern = [];
        }

        if (!this.state.branch) {
          this.state.branch = data.branch || "";
        }

        this.merge_teams(data.teams || []);
        this.state.number_of_teams =
          this.state.teams.filter((row) => cint(row.enabled)).length ||
          cint(data.number_of_teams) ||
          1;

        this.sync_controls();
        this.render_all();
        this.mark_dirty();
        dialog.hide();
      },
    });

    dialog.show();
  }

  merge_teams(teams) {
    const existingNames = new Set(
      this.state.teams.map((row) =>
        String(row.team_name || "").trim().toLowerCase(),
      ),
    );

    for (const source of teams) {
      const normalizedName = String(source.team_name || "")
        .trim()
        .toLowerCase();

      if (!normalizedName || existingNames.has(normalizedName)) {
        continue;
      }

      this.state.teams.push({
        team_key: source.team_key || this.key("TEAM"),
        team_name: source.team_name || "",
        display_order:
          cint(source.display_order) || this.state.teams.length + 1,
        pattern_offset: cint(source.pattern_offset),
        enabled: source.enabled === 0 ? 0 : 1,
      });

      existingNames.add(normalizedName);
    }
  }

  sync_calendar_rules() {
    const retained = (this.state.calendar_rules || []).filter(
      (row) => row.rule_type !== "Sunday" && row.rule_type !== "Weekday",
    );

    retained.push({
      priority: 10,
      rule_type: "Sunday",
      day_of_week: "Sunday",
      action:
        this.state.sunday_rule === "Extend Saturday Day Team"
          ? "Continue Saturday Day Team"
          : "Follow Pattern",
      day_shift_hours: null,
      night_shift_hours: null,
      enabled: 1,
      notes: "",
    });

    for (const weekday of Object.keys(this.simulation.weekday_hours)) {
      const values = this.simulation.weekday_hours[weekday] || {};
      const hasDay = values.day !== "" && values.day !== null && values.day !== undefined;
      const hasNight = values.night !== "" && values.night !== null && values.night !== undefined;

      if (!hasDay && !hasNight) {
        continue;
      }

      retained.push({
        priority: 20,
        rule_type: "Weekday",
        day_of_week: weekday,
        action: "Follow Pattern",
        day_shift_hours: hasDay ? flt(values.day) : null,
        night_shift_hours: hasNight ? flt(values.night) : null,
        enabled: 1,
        notes: "",
      });
    }

    this.state.calendar_rules = retained;
  }

  assignments_for_date(date) {
    const patternDay = this.pattern_day_for_date(date);
    const assignments = {};

    for (const team of this.enabled_teams()) {
      assignments[team.team_key] = this.assignment(team.team_key, patternDay);
    }

    if (
      this.state.sunday_rule !== "Extend Saturday Day Team" ||
      moment(date).day() !== 0
    ) {
      return assignments;
    }

    const saturday = moment(date).subtract(1, "day").format("YYYY-MM-DD");
    const saturdayPatternDay = this.pattern_day_for_date(saturday);

    const saturdayDayTeams = this.enabled_teams()
      .filter(
        (team) => this.assignment(team.team_key, saturdayPatternDay) === "Day",
      )
      .map((team) => team.team_key);

    if (!saturdayDayTeams.length) {
      return assignments;
    }

    for (const team of this.enabled_teams()) {
      if (saturdayDayTeams.includes(team.team_key)) {
        assignments[team.team_key] = "Day";
      } else if (assignments[team.team_key] === "Day") {
        assignments[team.team_key] = "Off";
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

    this.sync_calendar_rules();

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
    this.simulation.weekday_hours = this.infer_weekday_hours();
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
    if (!this.state.branch) return __("Branch is required.");
    if (!this.state.company) return __("Company is required.");
    if (!this.state.effective_from) return __("Effective From is required.");
    if (!this.state.anchor_date) return __("Cycle Anchor Date is required.");
    if (!this.state.day_shift_type) return __("Day Shift Type is required.");
    if (!this.state.night_shift_type) return __("Night Shift Type is required.");
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
      )?.assignment || "Off"
    );
  }

  shift_type_for(assignment) {
    if (assignment === "Day") return this.state.day_shift_type || "";
    if (assignment === "Night") return this.state.night_shift_type || "";
    return "";
  }

  hours_for(assignment, date) {
    const weekday = moment(date).format("dddd");
    const key = assignment === "Day" ? "day" : "night";
    const override = this.simulation.weekday_hours?.[weekday]?.[key];

    if (override !== "" && override !== null && override !== undefined) {
      return flt(override);
    }

    const shiftTypeName = this.shift_type_for(assignment);
    const shiftType = (this.bootstrap.shift_types || []).find(
      (row) => row.name === shiftTypeName,
    );

    return (
      flt(shiftType?.hours) ||
      flt(
        assignment === "Day"
          ? this.simulation.default_day_hours
          : this.simulation.default_night_hours,
      )
    );
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
    if (assignment === "Off") return "Day";
    if (assignment === "Day") return "Night";
    return "Off";
  }

  badge(assignment) {
    const letter = assignment === "Day" ? "D" : assignment === "Night" ? "N" : "O";
    return `<span class="sdm-assignment sdm-assignment--${assignment.toLowerCase()}">${letter}</span>`;
  }

  assignment_label(assignment, teamName) {
    const teamSuffix = String(teamName || "").replace(/^Shift\s+/i, "");
    const label =
      assignment === "Day"
        ? __("Day Shift {0}", [teamSuffix])
        : assignment === "Night"
          ? __("Night Shift {0}", [teamSuffix])
          : __("Off Shift {0}", [teamSuffix]);

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
