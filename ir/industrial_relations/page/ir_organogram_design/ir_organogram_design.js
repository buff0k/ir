// Copyright (c) 2026, BuFf0k and contributors
// Organogram Designer Page

const SO_PY = "ir.industrial_relations.doctype.site_organogram.site_organogram";

frappe.pages["ir-organogram-design"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Organogram Designer",
    single_column: true,
  });

  const app = new SiteOrganogramDesigner(page, wrapper);
  wrapper.site_organogram_designer = app;
  app.init();
};

class SiteOrganogramDesigner {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = wrapper;
    this.$main = $(page.main);
    this.state = this.blank_state();
    this.dirty = false;
    this.controls = {};
    this.pool_mode = "employees";
    this.pool_query = "";
    this.pool_designation = "";
    this.designations = [];
    this.line_mode = false;
    this.line_source = null;
    this.drag_payload = null;
    this.suppress_control_events = false;
    this._control_load_timer = null;
    this._recovery_prompt_key = "";
  }

  blank_state() {
    return {
      name: "",
      modified: "",
      docstatus: 0,
      branch: "",
      location: "",
      shifts: "3",
      asset_categories: [],
      group_headings: [],
      employees: [],
      assets: [],
      shift_mappings: [],
      reporting_lines: [],
    };
  }

  async init() {
    this.build_shell();
    this.build_page_actions();
    await this.load_designations();
    this.render_all();
  }

  build_shell() {
    this.$main.html(`
      <div class="so-page">
        <div class="so-section">
          <div class="so-section__hd">
            <div><div class="so-section__title">Organogram Configuration</div><div class="so-doc-status"></div></div>
            <div class="so-section__hint">Select or create a Site Organogram, configure its headings, then plan assignments below.</div>
          </div>
          <div class="so-section__bd">
            <div class="so-config-grid">
              <div data-control="organogram"></div>
              <div data-control="branch"></div>
              <div data-control="location"></div>
              <div data-control="shifts"></div>
              <div class="so-config-asset-categories" data-control="asset_categories"></div>
              <div class="so-selected-categories">
                <div class="so-selected-categories__label">Selected Asset Categories</div>
                <div class="so-selected-categories__list"></div>
              </div>
            </div>
            <div class="so-config-actions">
              <button class="btn btn-sm btn-default" data-action="new">New Organogram</button>
              <button class="btn btn-sm btn-default" data-action="sync">Refresh Employees and Assets</button>
            </div>
          </div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">Group Headings</div><div class="so-section__hint">Headings define the major organogram sections and the shift columns available in each section.</div></div>
          <div class="so-section__bd"><div class="so-groups"></div></div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">Visual Organogram Planner</div><div class="so-section__hint">Drag assets or designations into a group, then assign employees to the resulting shift cells.</div></div>
          <div class="so-section__bd"><div class="so-planner"></div></div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">Reporting Lines</div><div class="so-section__hint">Reporting relationships are kept separate from the staffing matrix so neither view becomes unreadable.</div></div>
          <div class="so-section__bd"><div class="so-reporting"></div></div>
        </div>
      </div>
    `);

    this.make_controls();
    this.bind_shell_events();
  }

  make_controls() {
    this.controls.organogram = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="organogram"]'),
      df: { fieldtype: "Link", label: "Site Organogram", options: "Site Organogram", fieldname: "organogram" },
      render_input: true,
    });
    this.controls.branch = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="branch"]'),
      df: { fieldtype: "Link", label: "Site", options: "Branch", fieldname: "branch", reqd: 1 },
      render_input: true,
    });
    this.controls.location = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="location"]'),
      df: { fieldtype: "Link", label: "Location", options: "Location", fieldname: "location", reqd: 1 },
      render_input: true,
    });
    this.controls.shifts = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="shifts"]'),
      df: { fieldtype: "Select", label: "Shift Teams", options: "\n1\n2\n3\n4\n5", fieldname: "shifts", reqd: 1 },
      render_input: true,
    });
    this.controls.asset_categories = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="asset_categories"]'),
      df: { fieldtype: "MultiSelectList", label: "Applicable Asset Categories", fieldname: "asset_categories", get_data: txt => frappe.db.get_link_options("Asset Category", txt) },
      render_input: true,
    });

    this.bind_control_change(this.controls.organogram, async () => {
      if (this.suppress_control_events) return;
      const name = this.controls.organogram.get_value() || "";
      if (!name || name === this.state.name) return;
      await this.load_document(name);
    });

    this.bind_control_change(this.controls.branch, async () => {
      if (this.suppress_control_events) return;
      const branch = this.controls.branch.get_value() || "";
      if (branch === this.state.branch) return;
      await this.on_branch_change(branch);
    });

    this.bind_control_change(this.controls.location, () => {
      if (this.suppress_control_events) return;
      const location = this.controls.location.get_value() || "";
      if (location === this.state.location) return;
      this.state.location = location;
      this.mark_dirty();
    });

    this.bind_control_change(this.controls.shifts, () => {
      if (this.suppress_control_events) return;
      const shifts = this.controls.shifts.get_value() || "";
      if (shifts === String(this.state.shifts || "")) return;
      this.state.shifts = shifts;
      this.reconcile_shifts();
      this.mark_dirty();
      this.render_planner();
      this.render_reporting();
    });

    this.bind_control_change(this.controls.asset_categories, () => {
      if (this.suppress_control_events) return;
      this.sync_asset_categories_from_control();
      this.render_selected_asset_categories();
      this.mark_dirty();
    });
  }

  bind_control_change(control, handler) {
    if (!control || !control.$input) return;
    const namespace = `.so-designer-${control.df.fieldname}`;
    const run = () => {
      clearTimeout(this._control_load_timer);
      this._control_load_timer = setTimeout(() => Promise.resolve(handler()).catch(err => {
        console.error(err);
        frappe.msgprint({ title: "Organogram Designer", message: err.message || String(err), indicator: "red" });
      }), 0);
    };
    control.$input.off(namespace);
    control.$input.on(`change${namespace} awesomplete-selectcomplete${namespace}`, run);
    if (control.$wrapper) {
      control.$wrapper.off(`awesomplete-selectcomplete${namespace}`);
      control.$wrapper.on(`awesomplete-selectcomplete${namespace}`, run);
    }
  }

  normalize_asset_category_values(value) {
    let values = value;

    if (typeof values === "string") {
      const trimmed = values.trim();
      if (!trimmed) return [];
      try {
        const parsed = JSON.parse(trimmed);
        values = Array.isArray(parsed) ? parsed : [parsed];
      } catch (_) {
        values = trimmed.split(",");
      }
    }

    if (!Array.isArray(values)) values = values ? [values] : [];

    const names = [];
    for (const item of values) {
      let name = "";
      if (typeof item === "string") name = item;
      else if (item && typeof item === "object") {
        name = item.value || item.name || item.label || item.asset_cateogories || "";
      }
      name = String(name || "").trim();
      if (name && !names.includes(name)) names.push(name);
    }
    return names;
  }

  sync_asset_categories_from_control() {
    const control = this.controls.asset_categories;
    const raw = control ? control.get_value() : [];
    const names = this.normalize_asset_category_values(raw);
    this.state.asset_categories = names.map(name => ({ asset_cateogories: name }));
    return names;
  }

  render_selected_asset_categories() {
    const $list = this.$main.find(".so-selected-categories__list");
    if (!$list.length) return;

    const names = (this.state.asset_categories || [])
      .map(row => String(row.asset_cateogories || "").trim())
      .filter(Boolean);

    $list.html(names.length
      ? names.map((name, index) => `
          <span class="so-category-chip">
            ${this.esc(name)}
            <button type="button" data-remove-category="${index}" title="Remove ${this.esc(name)}">×</button>
          </span>
        `).join("")
      : '<span class="so-category-empty">No asset categories selected.</span>');

    $list.find("[data-remove-category]").off("click").on("click", ev => {
      const index = Number(ev.currentTarget.getAttribute("data-remove-category"));
      if (!Number.isInteger(index) || index < 0 || index >= names.length) return;
      names.splice(index, 1);
      this.state.asset_categories = names.map(name => ({ asset_cateogories: name }));
      this.suppress_control_events = true;
      try {
        this.controls.asset_categories.set_value(names);
      } finally {
        setTimeout(() => { this.suppress_control_events = false; }, 0);
      }
      this.render_selected_asset_categories();
      this.mark_dirty();
    });
  }

  build_page_actions() {
    this.page.set_primary_action("Save", () => this.save(), "save");

    this.page.add_inner_button("New Organogram", () => this.start_new_document());
    this.page.add_inner_button("Print", () => this.print_organogram(), "Actions");
    this.page.add_inner_button("Export Excel", () => this.export_excel(), "Actions");

    this.page.add_menu_item("Reload", () => this.reload());
    this.page.add_menu_item("Open DocType Record", () => {
      if (!this.state.name) return frappe.msgprint("Save the organogram first.");
      frappe.set_route("Form", "Site Organogram", this.state.name);
    });
  }

  bind_shell_events() {
    this.$main.on("click", '[data-action="new"]', () => this.start_new_document());
    this.$main.on("click", '[data-action="sync"]', () => this.sync_pools(true));
  }

  async load_designations() {
    try {
      const rows = await frappe.db.get_list("Designation", { fields: ["name"], order_by: "name asc", limit: 0 });
      this.designations = rows.map(r => r.name).filter(Boolean);
    } catch (e) {
      this.designations = [];
    }
  }

  async load_document(name) {
    name = String(name || "").trim();
    if (!name) return;
    if (this.dirty && name !== this.state.name) {
      const ok = await this.confirm("Discard unsaved changes and load another organogram?");
      if (!ok) {
        this.suppress_control_events = true;
        try { this.controls.organogram.set_value(this.state.name || ""); }
        finally { this.suppress_control_events = false; }
        return;
      }
    }

    const r = await frappe.call({
      method: `${SO_PY}.get_site_organogram_designer_state`,
      args: { name },
      freeze: true,
      freeze_message: "Loading organogram...",
    });

    if (!r.message || !r.message.name) {
      frappe.throw(`No Site Organogram data was returned for ${name}.`);
    }

    this.state = Object.assign(this.blank_state(), r.message);
    this.ensure_state_keys();
    this.dirty = false;
    this.line_mode = false;
    this.line_source = null;
    this.push_controls();
    this.render_all();
  }

  async reload() {
    if (this.state.name) return this.load_document(this.state.name);
    this.new_document();
  }

  async start_new_document() {
    if (this.dirty) {
      const ok = await this.confirm("Discard unsaved changes and start a new Site Organogram?");
      if (!ok) return;
    }

    this.new_document();
  }

  new_document() {
    this.state = this.blank_state();
    this.dirty = false;
    this.line_mode = false;
    this.line_source = null;
    this._recovery_prompt_key = "";
    this.push_controls();
    this.render_all();
  }

  push_controls() {
    this.suppress_control_events = true;
    try {
      this.controls.organogram.set_value(this.state.name || "");
      this.controls.branch.set_value(this.state.branch || "");
      this.controls.location.set_value(this.state.location || "");
      this.controls.shifts.set_value(String(this.state.shifts || "3"));
      this.controls.asset_categories.set_value((this.state.asset_categories || []).map(r => r.asset_cateogories).filter(Boolean));
      this.render_selected_asset_categories();
    } finally {
      setTimeout(() => { this.suppress_control_events = false; }, 0);
    }
  }

  async on_branch_change(branch) {
    this.state.branch = branch || "";
    this._recovery_prompt_key = "";

    if (!branch) {
      this.state.location = "";
      this.controls.location.set_value("");
      this.mark_dirty();
      return;
    }

    const r = await frappe.call({
      method: `${SO_PY}.get_matching_location_for_branch`,
      args: { branch },
    });

    const location = r.message || "";
    this.state.location = location;

    this.suppress_control_events = true;
    try {
      this.controls.location.set_value(location);
    } finally {
      setTimeout(() => { this.suppress_control_events = false; }, 0);
    }

    this.mark_dirty();

    const recovered = await this.offer_previous_organogram(branch, location);
    if (!recovered) {
      await this.sync_pools(false);
    }
  }

  async offer_previous_organogram(branch, location) {
    if (this.state.name || !branch || !location) return false;

    const promptKey = `${branch}::${location}`;
    if (this._recovery_prompt_key === promptKey) return false;
    this._recovery_prompt_key = promptKey;

    const result = await frappe.call({
      method: `${SO_PY}.list_site_organograms_for_designer`,
      args: { branch, limit: 50 },
      freeze: true,
      freeze_message: "Checking for previous organograms...",
    });

    const matches = (result.message || [])
      .filter(row => row.name && row.branch === branch && row.location === location)
      .sort((a, b) => String(b.modified || "").localeCompare(String(a.modified || "")))
      .slice(0, 10);

    if (!matches.length) return false;

    const usePrevious = await this.confirm(
      `Previous Site Organograms exist for Site <b>${this.esc(branch)}</b> and Location <b>${this.esc(location)}</b>.<br><br>Use one as the basis for this new organogram?`
    );

    if (!usePrevious) return false;

    const labels = matches.map(row => {
      const modified = row.modified ? frappe.datetime.str_to_user(row.modified) : "";
      return modified ? `${row.name} — ${modified}` : row.name;
    });

    const selected = await new Promise(resolve => {
      let completed = false;
      const dialog = new frappe.ui.Dialog({
        title: "Select Previous Site Organogram",
        fields: [
          {
            fieldtype: "Select",
            fieldname: "source",
            label: "Previous Site Organogram",
            options: labels.join("\n"),
            default: labels[0],
            reqd: 1,
          },
        ],
        primary_action_label: "Use as Basis",
        primary_action(values) {
          completed = true;
          dialog.hide();
          resolve(values.source || "");
        },
      });
      dialog.onhide = () => {
        if (!completed) resolve("");
      };
      dialog.show();
    });

    if (!selected) return false;

    const index = labels.indexOf(selected);
    if (index < 0) return false;

    await this.apply_previous_organogram(matches[index].name, branch, location);
    return true;
  }

  async apply_previous_organogram(sourceName, branch, location) {
    const result = await frappe.call({
      method: `${SO_PY}.get_site_organogram_template`,
      args: { source_name: sourceName },
      freeze: true,
      freeze_message: "Recovering previous organogram...",
    });

    const template = result.message || {};

    this.state.name = "";
    this.state.modified = "";
    this.state.docstatus = 0;
    this.state.branch = branch;
    this.state.location = location;
    this.state.shifts = String(template.shifts || this.state.shifts || "3");
    this.state.asset_categories = (template.asset_categories || []).map(row => ({
      asset_cateogories: row.asset_cateogories || "",
    })).filter(row => row.asset_cateogories);
    this.state.group_headings = (template.group_headings || []).map(row => ({
      group_key: row.group_key || this.new_group_key(),
      group: row.group || "",
      shifts: row.shifts || "Shift Pattern",
    }));
    this.state.employees = (template.employees || []).map(row => ({ ...row }));
    this.state.assets = (template.assets || []).map(row => ({ ...row }));
    this.state.shift_mappings = (template.shift_mappings || []).map(row => ({ ...row }));
    this.state.reporting_lines = (template.reporting_lines || []).map(row => ({ ...row }));

    this.ensure_state_keys();
    this.reconcile_shifts();
    await this.sync_pools(false);
    this.push_controls();
    this.mark_dirty();
    this.render_all();

    frappe.show_alert({
      message: `Recovered ${sourceName} as the basis for a new organogram.`,
      indicator: "green",
    });
  }

  async sync_pools(show_message) {
    if (!this.state.branch) return frappe.msgprint("Select a Site first.");
    const emp = await frappe.call({
      method: `${SO_PY}.sync_employees`,
      args: { branch: this.state.branch, current_employees: JSON.stringify([]), auto_employees: JSON.stringify([]) },
    });
    this.state.employees = (emp.message?.to_add || []).filter(r => r.employee);

    if (this.state.location) {
      const cats = (this.state.asset_categories || []).map(r => r.asset_cateogories).filter(Boolean);
      const assets = await frappe.call({
        method: `${SO_PY}.sync_assets`,
        args: { location: this.state.location, asset_categories: JSON.stringify(cats), current_assets: JSON.stringify([]), auto_assets: JSON.stringify([]) },
      });
      this.state.assets = (assets.message?.to_add || []).filter(r => r.asset);
    }

    this.reconcile_missing_assignments();
    this.mark_dirty();
    this.render_planner();
    if (show_message) frappe.show_alert({ message: "Employees and assets refreshed.", indicator: "green" });
  }

  reconcile_missing_assignments() {
    const emps = new Set(this.state.employees.map(r => r.employee));
    const assets = new Set(this.state.assets.map(r => r.asset));
    for (const row of this.state.shift_mappings) {
      if (row.employee && !emps.has(row.employee)) { row.employee = ""; row.missing_employee = 1; }
      if (row.row_type === "Asset" && row.asset && !assets.has(row.asset)) { row.asset = ""; row.missing_asset = 1; }
    }
  }

  mark_dirty() {
    this.dirty = true;
    this.update_status();
  }

  update_status() {
    const $s = this.$main.find(".so-doc-status");
    const name = this.state.name || "New Site Organogram";
    const status = this.state.docstatus === 1 ? "Submitted" : this.state.docstatus === 2 ? "Cancelled" : "Draft";
    $s.html(`<span>${this.esc(name)} · ${status}</span>${this.dirty ? ' <span class="so-dirty">· Unsaved</span>' : ""}`);
  }

  ensure_state_keys() {
    const seen = new Set();
    for (const g of this.state.group_headings || []) {
      if (!g.group_key || seen.has(g.group_key)) g.group_key = this.new_group_key();
      seen.add(g.group_key);
    }
    this.sync_group_references();
  }

  new_group_key() { return `GRP::${frappe.utils.get_random(10)}`; }
  new_designation_key(label) { return `DESIG::${label || "Unlinked Role"}::${frappe.utils.get_random(6)}`; }
  active_shifts() { return ["A","B","C","D","E"].slice(0, Math.max(0, Math.min(5, Number(this.state.shifts || 0)))).map(x => `Shift ${x}`); }
  shifts_for_group(g) { return g.shifts === "Day Shift Only" ? ["Day Shift"] : g.shifts === "Night Shift Only" ? ["Night Shift"] : this.active_shifts(); }

  sync_group_references() {
    const byKey = new Map(this.state.group_headings.map(g => [g.group_key, g]));
    const byName = new Map(this.state.group_headings.map(g => [g.group, g]));
    for (const row of this.state.shift_mappings) {
      const g = byKey.get(row.group_key) || byName.get(row.group);
      if (g) { row.group_key = g.group_key; row.group = g.group; }
    }
    for (const line of this.state.reporting_lines) {
      for (const p of ["source","target"]) {
        const g = byKey.get(line[`${p}_group_key`]) || byName.get(line[`${p}_group`]);
        if (g) { line[`${p}_group_key`] = g.group_key; line[`${p}_group`] = g.group; }
      }
    }
  }

  reconcile_shifts() {
    const valid = new Map(this.state.group_headings.map(g => [g.group_key, new Set(this.shifts_for_group(g))]));
    this.state.shift_mappings = this.state.shift_mappings.filter(r => !r.group_key || !valid.has(r.group_key) || valid.get(r.group_key).has(r.shift));
    for (const line of this.state.reporting_lines) {
      if (line.source_scope === "Shift" && valid.has(line.source_group_key) && !valid.get(line.source_group_key).has(line.source_shift)) line.source_shift = "";
      if (line.target_scope === "Shift" && valid.has(line.target_group_key) && !valid.get(line.target_group_key).has(line.target_shift)) line.target_shift = "";
    }
  }

  render_all() {
    this.update_status();
    this.render_selected_asset_categories();
    this.render_groups();
    this.render_planner();
    this.render_reporting();
  }

  render_groups() {
    const $w = this.$main.find(".so-groups");
    const rows = this.state.group_headings || [];
    $w.html(`
      ${rows.length ? `<table class="so-table"><tbody>${rows.map((g,i) => `
        <tr data-group-index="${i}">
          <td><input class="form-control" data-group-field="group" value="${this.esc(g.group || "")}" placeholder="Heading name"></td>
          <td><select class="form-control" data-group-field="shifts">
            ${["Shift Pattern","Day Shift Only","Night Shift Only"].map(v => `<option ${g.shifts===v?"selected":""}>${v}</option>`).join("")}
          </select></td>
          <td class="so-group-remove-cell"><button class="so-icon-btn" data-group-action="remove" title="Remove">×</button></td>
        </tr>`).join("")}</tbody></table>` : '<div class="so-empty">No group headings configured.</div>'}
      <button class="btn btn-sm btn-default" data-group-action="add">Add Group Heading</button>
    `);

    $w.find('[data-group-action="add"]').on("click", () => {
      this.state.group_headings.push({ group_key:this.new_group_key(), group:"", shifts:"Shift Pattern" });
      this.mark_dirty(); this.render_groups(); this.render_planner(); this.render_reporting();
    });
    $w.find('[data-group-action="remove"]').on("click", async ev => {
      const i = Number($(ev.currentTarget).closest("tr").data("group-index"));
      const g = this.state.group_headings[i];
      if (!g) return;
      const ok = await this.confirm(`Remove heading “${g.group || "Unnamed"}” and its mappings/reporting lines?`);
      if (!ok) return;
      this.state.group_headings.splice(i,1);
      this.state.shift_mappings = this.state.shift_mappings.filter(r => r.group_key !== g.group_key);
      this.state.reporting_lines = this.state.reporting_lines.filter(r => r.source_group_key !== g.group_key && r.target_group_key !== g.group_key);
      this.mark_dirty(); this.render_all();
    });
    $w.find("[data-group-field]").on("change", ev => {
      const $tr = $(ev.currentTarget).closest("tr");
      const i = Number($tr.data("group-index"));
      const field = ev.currentTarget.getAttribute("data-group-field");
      const g = this.state.group_headings[i];
      if (!g) return;
      const oldName = g.group;
      g[field] = ev.currentTarget.value || "";
      if (field === "group") {
        for (const r of this.state.shift_mappings) if (r.group_key === g.group_key || r.group === oldName) { r.group_key=g.group_key; r.group=g.group; }
        for (const l of this.state.reporting_lines) {
          if (l.source_group_key === g.group_key || l.source_group === oldName) { l.source_group_key=g.group_key; l.source_group=g.group; }
          if (l.target_group_key === g.group_key || l.target_group === oldName) { l.target_group_key=g.group_key; l.target_group=g.group; }
        }
      } else this.reconcile_shifts();
      this.mark_dirty(); this.render_planner(); this.render_reporting();
    });
  }

  mapping_rows_for_group(g) {
    const byKey = new Map();
    this.state.shift_mappings.filter(r => r.group_key === g.group_key || r.group === g.group).sort((a,b)=>(Number(a.row_order)||9999)-(Number(b.row_order)||9999)).forEach(r => { if (r.row_key && !byKey.has(r.row_key)) byKey.set(r.row_key,r); });
    return [...byKey.values()];
  }

  find_mapping(groupKey, shift, rowKey) { return this.state.shift_mappings.find(r => r.group_key===groupKey && r.shift===shift && r.row_key===rowKey); }
  employee_by_id(id) { return this.state.employees.find(e => e.employee===id); }
  asset_by_id(id) { return this.state.assets.find(a => a.asset===id); }

  render_planner() {
    const $w = this.$main.find(".so-planner");
    const assignedEmployees = new Set(this.state.shift_mappings.map(r=>r.employee).filter(Boolean));
    const assignedAssets = new Set(this.state.shift_mappings.filter(r=>r.row_type==="Asset"&&r.asset).map(r=>r.asset));
    const q = this.pool_query.toLowerCase();
    const empDesignations = [...new Set(this.state.employees.map(e=>e.designation).filter(Boolean))].sort();

    const poolItems = this.pool_mode === "employees"
      ? this.state.employees.filter(e=>!assignedEmployees.has(e.employee)).filter(e=>!this.pool_designation||e.designation===this.pool_designation).filter(e=>!q||`${e.employee} ${e.employee_name} ${e.designation}`.toLowerCase().includes(q)).map(e=>this.employee_card(e,"employee")).join("")
      : this.pool_mode === "assets"
      ? this.state.assets.filter(a=>!assignedAssets.has(a.asset)).filter(a=>!q||`${a.asset} ${a.item_name} ${a.asset_category}`.toLowerCase().includes(q)).map(a=>this.asset_card(a)).join("")
      : this.designations.filter(d=>!q||d.toLowerCase().includes(q)).map(d=>this.designation_card(d)).join("");

    const groupsHtml = this.state.group_headings.filter(g=>g.group).map(g => {
      const shifts = this.shifts_for_group(g);
      const rows = this.mapping_rows_for_group(g);
      return `<div class="so-group">
        <div class="so-group__hd"><div class="so-group__name">${this.esc(g.group)}</div><div class="so-group__mode">${this.esc(g.shifts)}</div></div>
        <div class="so-gridwrap"><div class="so-grid" data-drop="grid" data-group-key="${this.esc(g.group_key)}">
          <div class="so-grid__hdr"><div class="so-hcell so-h-left">Asset / Designation</div>${shifts.map(s=>`<div class="so-hcell so-h-slot">${this.esc(s)}</div>`).join("")}</div>
          ${rows.length ? rows.map(identity => `<div class="so-grid__row so-rowdrag" draggable="true" data-drag-type="row" data-group-key="${this.esc(g.group_key)}" data-row-key="${this.esc(identity.row_key)}">
            <div class="so-leftcell">${this.row_label(identity)}</div>
            ${shifts.map(s=>this.slot_html(g,s,identity)).join("")}
          </div>`).join("") : '<div class="so-empty so-grid-empty">Drop an Asset or Designation into this group to create rows.</div>'}
        </div></div>
      </div>`;
    }).join("") || '<div class="so-empty">Add at least one Group Heading before planning the organogram.</div>';

    $w.html(`<div class="so-wrap"><div class="so-left">${groupsHtml}</div><div class="so-right so-panel">
      <div class="so-panel__hd"><strong>${this.pool_mode==="employees"?"Unallocated Employees":this.pool_mode==="assets"?"Assets Pool":"Designations Pool"}</strong><div class="so-tabs">
        ${["employees","assets","designations"].map(m=>`<button class="so-tab ${m===this.pool_mode?"is-active":""}" data-pool-mode="${m}">${m[0].toUpperCase()+m.slice(1)}</button>`).join("")}
      </div></div>
      <div class="so-panel__bd"><div class="so-filters"><input class="form-control" data-pool-search placeholder="Search..." value="${this.esc(this.pool_query)}"></div>
        ${this.pool_mode==="employees"?`<div class="so-filters"><select class="form-control" data-pool-designation><option value="">All designations</option>${empDesignations.map(d=>`<option ${d===this.pool_designation?"selected":""}>${this.esc(d)}</option>`).join("")}</select></div>`:""}
        <div class="so-pool-drop" data-drop="pool">Drop here to unassign or remove row</div><div class="so-pool">${poolItems||'<div class="so-empty">No matching unallocated items.</div>'}</div>
      </div></div></div>`);

    this.bind_planner_events($w);
  }

  employee_card(e,type,payload) { return `<div class="so-card" draggable="true" data-drag-type="${type}" data-employee="${this.esc(e.employee)}" ${payload?`data-payload='${this.esc(JSON.stringify(payload))}'`:""}><div class="so-card__title">${this.esc(e.employee_name||e.employee)} (${this.esc(e.employee)})</div><div class="so-card__meta">${this.esc(e.designation||"")}</div></div>`; }
  asset_card(a) { return `<div class="so-card" draggable="true" data-drag-type="asset" data-asset="${this.esc(a.asset)}"><div class="so-card__title">${this.esc(a.asset)}</div><div class="so-card__meta">${this.esc(a.item_name||a.asset_category||"")}</div></div>`; }
  designation_card(d) { return `<div class="so-card" draggable="true" data-drag-type="designation" data-designation="${this.esc(d)}"><div class="so-card__title">${this.esc(d)}</div></div>`; }
  row_label(r) { if(r.row_type==="Asset"){ const a=this.asset_by_id(r.asset); return `<div class="so-rowlabel"><div class="so-rowlabel__title">${this.esc(a?.asset||r.row_label||"Missing")}</div><div class="so-rowlabel__meta">${this.esc(a?.item_name||a?.asset_category||"")}</div></div>`;} return `<div class="so-rowlabel so-rowlabel--desig"><div class="so-rowlabel__title">${this.esc(r.row_label||"Designation")}</div></div>`; }
  slot_html(g,shift,identity) { const r=this.find_mapping(g.group_key,shift,identity.row_key); const e=r?.employee?this.employee_by_id(r.employee):null; return `<div class="so-slot ${e?"is-filled":"is-empty"}" data-drop="cell" data-group-key="${this.esc(g.group_key)}" data-shift="${this.esc(shift)}" data-row-key="${this.esc(identity.row_key)}">${e?this.employee_card(e,"assigned",{group_key:g.group_key,shift,row_key:identity.row_key}):'<span class="so-vacant">Vacant</span>'}</div>`; }

  bind_planner_events($w) {
    $w.find("[data-pool-mode]").on("click",e=>{this.pool_mode=e.currentTarget.dataset.poolMode;this.render_planner();});
    $w.find("[data-pool-search]").on("input",this.debounce(e=>{this.pool_query=e.target.value||"";this.render_planner();},150));
    $w.find("[data-pool-designation]").on("change",e=>{this.pool_designation=e.target.value||"";this.render_planner();});
    $w.find('[draggable="true"]').on("dragstart",e=>{
      const el=e.currentTarget; const type=el.dataset.dragType; let p={type};
      if(type==="employee"||type==="assigned"){p.employee=el.dataset.employee;if(el.dataset.payload)try{p.from=JSON.parse(el.dataset.payload);}catch(_){}}
      if(type==="asset")p.asset=el.dataset.asset;
      if(type==="designation")p.designation=el.dataset.designation;
      if(type==="row"){p.group_key=el.dataset.groupKey;p.row_key=el.dataset.rowKey;}
      e.originalEvent.dataTransfer.setData("application/json",JSON.stringify(p)); e.originalEvent.dataTransfer.effectAllowed="move";
    });
    $w.find("[data-drop]").on("dragover",e=>{e.preventDefault();$(e.currentTarget).addClass("so-over");}).on("dragleave",e=>$(e.currentTarget).removeClass("so-over")).on("drop",async e=>{
      e.preventDefault();$(e.currentTarget).removeClass("so-over");let p;try{p=JSON.parse(e.originalEvent.dataTransfer.getData("application/json"));}catch(_){return;}
      const type=e.currentTarget.dataset.drop;
      if(type==="grid"){if(p.type==="asset")this.add_row(e.currentTarget.dataset.groupKey,"Asset",p.asset);if(p.type==="designation")this.add_row(e.currentTarget.dataset.groupKey,"Designation",p.designation);}
      if(type==="cell"&&p.type==="employee")this.assign_employee(e.currentTarget.dataset.groupKey,e.currentTarget.dataset.shift,e.currentTarget.dataset.rowKey,p.employee,p.from);
      if(type==="pool"){if(p.type==="assigned"&&p.from)this.unassign(p.from);if(p.type==="row")this.remove_row(p.group_key,p.row_key);}
    });
  }

  add_row(groupKey,type,value) {
    const g=this.state.group_headings.find(x=>x.group_key===groupKey); if(!g||!value)return;
    const rowKey=type==="Asset"?`ASSET::${value}`:this.new_designation_key(value);
    if(this.state.shift_mappings.some(r=>r.group_key===groupKey&&r.row_key===rowKey))return;
    const asset=type==="Asset"?this.asset_by_id(value):null;
    const order=this.mapping_rows_for_group(g).length+1;
    for(const shift of this.shifts_for_group(g))this.state.shift_mappings.push({group_key:g.group_key,group:g.group,shift,employee:"",asset:type==="Asset"?value:"",row_key:rowKey,row_order:order,row_label:type==="Asset"?[value,asset?.item_name||asset?.asset_category].filter(Boolean).join(" — "):value,row_type:type,missing_asset:0,missing_employee:0});
    this.mark_dirty();this.render_planner();
  }

  assign_employee(groupKey,shift,rowKey,employee,from) {
    if(from)this.unassign(from,false);
    const r=this.find_mapping(groupKey,shift,rowKey); if(!r)return;
    r.employee=employee;r.missing_employee=0;this.mark_dirty();this.render_planner();
  }
  unassign(from,render=true){const r=this.find_mapping(from.group_key,from.shift,from.row_key);if(r){r.employee="";r.missing_employee=0;this.mark_dirty();if(render)this.render_planner();}}
  remove_row(groupKey,rowKey){this.state.shift_mappings=this.state.shift_mappings.filter(r=>!(r.group_key===groupKey&&r.row_key===rowKey));this.mark_dirty();this.render_planner();}

  organogram_blocks() {
    const groups = (this.state.group_headings || []).filter(
      group => group.group && group.group_key
    );
    const blocks = [];
    const byKey = new Map();

    groups.forEach((group, groupOrder) => {
      const shifts = this.shifts_for_group(group);
      shifts.forEach((shift, shiftOrder) => {
        const key = `${group.group_key}::${shift}`;
        const block = {
          key,
          group_key: group.group_key,
          group: group.group,
          shift,
          shift_order: shiftOrder,
          group_order: groupOrder,
          group_mode: group.shifts || "",
          rows: this.organogram_block_rows(group, shift),
        };
        blocks.push(block);
        byKey.set(key, block);
      });
    });

    return { blocks, byKey, groups };
  }

  organogram_block_rows(group, shift) {
    const mappings = (this.state.shift_mappings || [])
      .filter(row =>
        (row.group_key === group.group_key || row.group === group.group) &&
        row.shift === shift
      )
      .sort((a, b) => {
        const ao = Number(a.row_order || 999999);
        const bo = Number(b.row_order || 999999);
        if (ao !== bo) return ao - bo;
        return Number(a.idx || 999999) - Number(b.idx || 999999);
      });

    const seen = new Set();
    const rows = [];

    for (const mapping of mappings) {
      const rowKey = mapping.row_key || `${mapping.row_label || ""}:${mapping.asset || ""}`;
      if (seen.has(rowKey)) continue;
      seen.add(rowKey);

      const employee = mapping.employee
        ? this.employee_by_id(mapping.employee)
        : null;
      const asset = mapping.asset
        ? this.asset_by_id(mapping.asset)
        : null;

      const leftTitle =
        mapping.row_type === "Asset"
          ? asset?.asset || mapping.asset || mapping.row_label || "Asset"
          : mapping.row_label || "Designation";

      const leftMeta =
        mapping.row_type === "Asset"
          ? asset?.item_name || asset?.asset_category || ""
          : "";

      rows.push({
        row_key: rowKey,
        left_title: leftTitle,
        left_meta: leftMeta,
        employee_name:
          employee?.employee_name ||
          employee?.employee ||
          (mapping.missing_employee ? "Missing" : "Vacant"),
        employee_id: employee?.employee || "",
        designation:
          employee?.designation ||
          (mapping.missing_employee ? "" : mapping.row_label || ""),
        missing: !!mapping.missing_employee,
        vacant: !employee && !mapping.missing_employee,
      });
    }

    return rows;
  }

  organogram_endpoint_blocks(endpoint, model) {
    if (!endpoint || !endpoint.group_key) return [];

    if (endpoint.scope === "Shift" && endpoint.shift) {
      const block = model.byKey.get(
        `${endpoint.group_key}::${endpoint.shift}`
      );
      return block ? [block] : [];
    }

    return model.blocks.filter(
      block => block.group_key === endpoint.group_key
    );
  }

  expand_reporting_edges(model) {
    const edges = [];
    const seen = new Set();

    const addEdge = (source, target, lineIndex) => {
      if (!source || !target || source.key === target.key) return;
      const key = `${source.key}=>${target.key}`;
      if (seen.has(key)) return;
      seen.add(key);
      edges.push({ source, target, lineIndex });
    };

    (this.state.reporting_lines || []).forEach((line, lineIndex) => {
      const sourceEndpoint = this.line_ep(line, "source");
      const targetEndpoint = this.line_ep(line, "target");
      const sourceBlocks = this.organogram_endpoint_blocks(
        sourceEndpoint,
        model
      );
      const targetBlocks = this.organogram_endpoint_blocks(
        targetEndpoint,
        model
      );

      if (!sourceBlocks.length || !targetBlocks.length) return;

      if (
        sourceEndpoint.scope === "Heading" &&
        targetEndpoint.scope === "Heading" &&
        sourceBlocks.length > 1 &&
        targetBlocks.length > 1
      ) {
        const targetsByShift = new Map(
          targetBlocks.map(block => [block.shift, block])
        );
        let paired = false;

        for (const source of sourceBlocks) {
          const target = targetsByShift.get(source.shift);
          if (target) {
            addEdge(source, target, lineIndex);
            paired = true;
          }
        }

        if (paired) return;
      }

      for (const source of sourceBlocks) {
        for (const target of targetBlocks) {
          addEdge(source, target, lineIndex);
        }
      }
    });

    return edges;
  }

  build_organogram_tree() {
    const model = this.organogram_blocks();
    const edges = this.expand_reporting_edges(model);
    const children = new Map(
      model.blocks.map(block => [block.key, []])
    );
    const parents = new Map(
      model.blocks.map(block => [block.key, []])
    );

    for (const edge of edges) {
      children.get(edge.source.key).push(edge);
      parents.get(edge.target.key).push(edge);
    }

    for (const list of children.values()) {
      list.sort((a, b) => {
        const groupOrderCompare =
          Number(a.target.group_order || 0) - Number(b.target.group_order || 0);
        if (groupOrderCompare !== 0) return groupOrderCompare;

        const shiftOrderCompare =
          Number(a.target.shift_order || 0) - Number(b.target.shift_order || 0);
        if (shiftOrderCompare !== 0) return shiftOrderCompare;

        const groupCompare = a.target.group.localeCompare(
          b.target.group,
          undefined,
          { numeric: true }
        );
        if (groupCompare !== 0) return groupCompare;

        return a.target.shift.localeCompare(
          b.target.shift,
          undefined,
          { numeric: true }
        );
      });
    }

    const roots = model.blocks.filter(
      block => !parents.get(block.key).length
    );
    const visited = new Set();

    const buildNode = (block, ancestry = new Set()) => {
      const cyclic = ancestry.has(block.key);
      const nextAncestry = new Set(ancestry);
      nextAncestry.add(block.key);
      visited.add(block.key);

      const childNodes = cyclic
        ? []
        : children
            .get(block.key)
            .map(edge => ({
              edge,
              node: buildNode(edge.target, nextAncestry),
            }));

      return {
        block,
        cyclic,
        children: childNodes,
        secondary_parents: parents
          .get(block.key)
          .slice(1)
          .map(edge => edge.source),
      };
    };

    const trees = roots.map(root => buildNode(root));

    for (const block of model.blocks) {
      if (!visited.has(block.key)) {
        trees.push(buildNode(block));
      }
    }

    return { trees, model, edges };
  }

  organogram_block_html(node) {
    const block = node.block;

    const rowsHtml = block.rows.length
      ? block.rows
          .map(row => `
            <div class="so-org-person-row ${
              row.missing
                ? "is-missing"
                : row.vacant
                ? "is-vacant"
                : "is-filled"
            }">
              <div class="so-org-person-row__role">
                <div class="so-org-person-row__role-title">
                  ${this.esc(row.left_title)}
                </div>
                ${
                  row.left_meta
                    ? `<div class="so-org-person-row__meta">${this.esc(
                        row.left_meta
                      )}</div>`
                    : ""
                }
              </div>
              <div class="so-org-person-row__employee">
                <div class="so-org-person-row__employee-name">
                  ${this.esc(row.employee_name)}
                  ${
                    row.employee_id
                      ? ` <span>(${this.esc(row.employee_id)})</span>`
                      : ""
                  }
                </div>
                ${
                  row.designation
                    ? `<div class="so-org-person-row__meta">${this.esc(
                        row.designation
                      )}</div>`
                    : ""
                }
              </div>
            </div>
          `)
          .join("")
      : `
        <div class="so-org-block__empty">
          No Asset/Designation rows assigned to this block.
        </div>
      `;

    const secondaryHtml = node.secondary_parents.length
      ? `
        <div class="so-org-block__secondary">
          Additional reporting from:
          ${node.secondary_parents
            .map(parent => this.esc(`${parent.group} — ${parent.shift}`))
            .join(", ")}
        </div>
      `
      : "";

    return `
      <div class="so-org-block ${node.cyclic ? "is-cyclic" : ""}"
           data-org-block-key="${this.esc(block.key)}">
        <div class="so-org-block__header">
          <div class="so-org-block__heading">${this.esc(block.group)}</div>
          <div class="so-org-block__shift">${this.esc(block.shift)}</div>
        </div>
        <div class="so-org-block__body">${rowsHtml}</div>
        ${secondaryHtml}
      </div>
    `;
  }

  reporting_sort_nodes(nodes) {
    return [...nodes].sort((a, b) => {
      const groupOrderCompare =
        Number(a.block.group_order || 0) - Number(b.block.group_order || 0);
      if (groupOrderCompare !== 0) return groupOrderCompare;

      const shiftOrderCompare =
        Number(a.block.shift_order || 0) - Number(b.block.shift_order || 0);
      if (shiftOrderCompare !== 0) return shiftOrderCompare;

      const groupCompare = a.block.group.localeCompare(
        b.block.group,
        undefined,
        { numeric: true }
      );
      if (groupCompare !== 0) return groupCompare;

      return a.block.shift.localeCompare(
        b.block.shift,
        undefined,
        { numeric: true }
      );
    });
  }

  build_reporting_graph() {
    const model = this.organogram_blocks();
    const edges = this.expand_reporting_edges(model);
    const nodesByKey = new Map(
      model.blocks.map(block => [
        block.key,
        {
          key: block.key,
          block,
          children: [],
          parents: [],
        },
      ])
    );

    edges.forEach(edge => {
      const source = nodesByKey.get(edge.source.key);
      const target = nodesByKey.get(edge.target.key);
      if (!source || !target) return;
      source.children.push(target);
      target.parents.push(source);
    });

    nodesByKey.forEach(node => {
      node.children = this.reporting_sort_nodes(node.children);
      node.parents = this.reporting_sort_nodes(node.parents);
    });

    const roots = this.reporting_sort_nodes(
      [...nodesByKey.values()].filter(node => !node.parents.length)
    );

    return { model, edges, nodesByKey, roots };
  }

  collect_branch_descendants(node) {
    const results = [];
    const seen = new Set();

    const visit = current => {
      current.children.forEach(child => {
        if (seen.has(child.key)) return;
        seen.add(child.key);
        results.push(child);
        visit(child);
      });
    };

    visit(node);
    return this.reporting_sort_nodes(results);
  }

  build_reporting_layout() {
    const graph = this.build_reporting_graph();
    const matrices = [];
    const standalone = [];

    graph.roots.forEach(root => {
      if (!root.children.length) {
        standalone.push(root);
        return;
      }

      const branches = this.reporting_sort_nodes(root.children);
      const rowDefs = [];
      const rowSeen = new Set();
      const branchRows = new Map();

      branches.forEach(branch => {
        const descendants = this.collect_branch_descendants(branch).filter(
          node => node.key !== branch.key
        );
        const byGroup = new Map();

        descendants.forEach(node => {
          const rowKey = node.block.group_key;
          if (!rowKey || rowKey === branch.block.group_key) return;
          if (!byGroup.has(rowKey)) {
            byGroup.set(rowKey, node);
          }
          if (!rowSeen.has(rowKey)) {
            rowSeen.add(rowKey);
            rowDefs.push({
              group_key: node.block.group_key,
              group: node.block.group,
              group_order: Number(node.block.group_order || 0),
            });
          }
        });

        branchRows.set(branch.key, byGroup);
      });

      rowDefs.sort((a, b) => {
        const orderCompare = Number(a.group_order || 0) - Number(b.group_order || 0);
        if (orderCompare !== 0) return orderCompare;
        return String(a.group || "").localeCompare(String(b.group || ""), undefined, { numeric: true });
      });

      matrices.push({ root, branches, rowDefs, branchRows });
    });

    return { matrices, standalone };
  }

  reporting_present_node(node) {
    return {
      block: node.block,
      cyclic: false,
      secondary_parents: node.parents.slice(1).map(parent => parent.block),
    };
  }

  reporting_matrix_html(layout, matrixIndex) {
    const cols = Math.max(layout.branches.length, 1);
    const columnWidth = 360;
    const columnGap = 36;
    const connectorWidth =
      cols * columnWidth + Math.max(0, cols - 1) * columnGap;
    const rootInset = columnWidth / 2;
    const branchSpineInset = 18;

    const branchRow = layout.branches
      .map((branch, index) => `
        <div class="so-org-grid__cell so-org-grid__cell--branch"
             style="--branch-spine-x:${branchSpineInset}px;">
          ${this.organogram_block_html(this.reporting_present_node(branch))}
        </div>
      `)
      .join("");

    const levelRows = layout.rowDefs
      .map(row => `
        <div class="so-org-grid__row so-org-grid__row--level"
             style="grid-template-columns: repeat(${cols}, ${columnWidth}px); column-gap:${columnGap}px;">
          ${layout.branches
            .map(branch => {
              const node = layout.branchRows.get(branch.key)?.get(row.group_key);
              return `
                <div class="so-org-grid__cell ${node ? "has-node" : "is-empty"}"
                     style="--branch-spine-x:${branchSpineInset}px;">
                  ${node ? '<div class="so-org-grid__cell-connector"></div>' : ''}
                  ${
                    node
                      ? this.organogram_block_html(this.reporting_present_node(node))
                      : '<div class="so-org-grid__placeholder"></div>'
                  }
                </div>
              `;
            })
            .join("")}
        </div>
      `)
      .join("");

    const branchGuides = layout.branches
      .map((branch, index) => {
        const columnLeft = index * (columnWidth + columnGap);
        const centreX = columnLeft + columnWidth / 2;
        const spineX = columnLeft + branchSpineInset;
        return `
          <span class="so-org-descendants__spine"
                style="left:${spineX}px"></span>
          <span class="so-org-descendants__branch-start"
                style="left:${spineX}px; width:${centreX - spineX}px"></span>
        `;
      })
      .join("");

    return `
      <div class="so-org-matrix" data-matrix-index="${matrixIndex}">
        <div class="so-org-root-row">
          ${this.organogram_block_html(this.reporting_present_node(layout.root))}
        </div>

        <div class="so-org-root-links"
             style="width:${connectorWidth}px; --root-line-inset:${rootInset}px;">
          <div class="so-org-root-links__trunk"></div>
          <div class="so-org-root-links__line"></div>
          ${layout.branches
            .map((branch, index) => {
              const left = index * (columnWidth + columnGap) + columnWidth / 2;
              return `<span class="so-org-root-links__drop" style="left:${left}px"></span>`;
            })
            .join("")}
        </div>

        <div class="so-org-grid">
          <div class="so-org-grid__row so-org-grid__row--branches"
               style="grid-template-columns: repeat(${cols}, ${columnWidth}px); column-gap:${columnGap}px;">
            ${branchRow}
          </div>

          ${layout.rowDefs.length
            ? `
              <div class="so-org-descendants" style="width:${connectorWidth}px;">
                <div class="so-org-descendants__guides">${branchGuides}</div>
                ${levelRows}
              </div>
            `
            : ''}
        </div>
      </div>
    `;
  }

  render_reporting() {
    const $wrapper = this.$main.find(".so-reporting");
    const lineCount = this.state.reporting_lines.length;
    const status = this.line_mode
      ? (
          this.line_source
            ? `Source selected: ${this.esc(
                this.endpoint_label(this.line_source)
              )}. Select the target.`
            : "Select a source heading or shift."
        )
      : `${lineCount} reporting line${lineCount === 1 ? "" : "s"}`;

    const layout = this.build_reporting_layout();

    const matricesHtml = layout.matrices.length
      ? layout.matrices
          .map((matrix, index) => this.reporting_matrix_html(matrix, index))
          .join("")
      : "";

    const standaloneHtml = layout.standalone.length
      ? `
          <div class="so-org-unlinked">
            <div class="so-org-unlinked__title">Unlinked Blocks</div>
            <div class="so-org-unlinked__list">
              ${layout.standalone
                .map(node => this.organogram_block_html(this.reporting_present_node(node)))
                .join("")}
            </div>
          </div>
        `
      : "";

    $wrapper.html(`
      <div>
        <div class="so-report-toolbar">
          <button class="btn btn-sm btn-default"
                  data-report-action="manage"
                  ${lineCount ? "" : "disabled"}>
            Manage Reporting Lines
          </button>
          <span class="so-report-status">${status}</span>
        </div>

        <div class="so-org-forest-scroll">
          <div class="so-org-forest">
            ${matricesHtml || '<div class="so-empty">Add headings, mappings and reporting lines to build the organogram.</div>'}
            ${standaloneHtml}
          </div>
        </div>
      </div>
    `);

    $wrapper
      .find('[data-report-action="manage"]')
      .on("click", () => this.manage_lines());
  }

  endpoint_from_el(el) {
    return {
      group_key: el.dataset.groupKey || "",
      group: el.dataset.group || "",
      scope: el.dataset.scope || "Heading",
      shift: el.dataset.shift || "",
    };
  }

  endpoint_label(endpoint) {
    return endpoint.scope === "Shift" && endpoint.shift
      ? `${endpoint.group} — ${endpoint.shift}`
      : endpoint.group;
  }

  endpoint_selector(endpoint) {
    const escapeSelector = value =>
      String(value || "").replace(/\\/g, "\\\\").replace(/"/g, '\\"');

    return `.so-endpoint[data-group-key="${escapeSelector(endpoint.group_key)}"]` +
      `[data-scope="${escapeSelector(endpoint.scope)}"]` +
      `[data-shift="${escapeSelector(endpoint.shift || "")}"]`;
  }

  line_ep(line, prefix) {
    return {
      group_key: line[`${prefix}_group_key`] || "",
      group: line[`${prefix}_group`] || "",
      scope: line[`${prefix}_scope`] || "Heading",
      shift: line[`${prefix}_shift`] || "",
    };
  }

  async create_line(source, target) {
    if (
      source.group_key === target.group_key &&
      source.scope === target.scope &&
      (source.shift || "") === (target.shift || "")
    ) {
      return frappe.msgprint(
        "A reporting line cannot connect an endpoint to itself."
      );
    }

    const duplicate = this.state.reporting_lines.some(line =>
      JSON.stringify(this.line_ep(line, "source")) === JSON.stringify(source) &&
      JSON.stringify(this.line_ep(line, "target")) === JSON.stringify(target)
    );

    if (duplicate) {
      return frappe.msgprint("That reporting line already exists.");
    }

    const result = await this.line_dialog(source, target);
    if (!result) return;

    this.state.reporting_lines.push({
      source_group_key: source.group_key,
      source_group: source.group,
      source_scope: source.scope,
      source_shift: source.scope === "Shift" ? source.shift : "",
      target_group_key: target.group_key,
      target_group: target.group,
      target_scope: target.scope,
      target_shift: target.scope === "Shift" ? target.shift : "",
      line_type: result.line_type || "Solid",
      label: result.label || "",
      source_anchor: result.source_anchor || "Auto",
      target_anchor: result.target_anchor || "Auto",
      line_order: this.state.reporting_lines.length + 1,
    });

    this.mark_dirty();
  }

  line_dialog(source, target, existing) {
    return new Promise(resolve => {
      let completed = false;

      const dialog = new frappe.ui.Dialog({
        title: existing ? "Edit Reporting Line" : "Create Reporting Line",
        fields: [
          {
            fieldtype: "HTML",
            options: `
              <div>
                <b>${this.esc(this.endpoint_label(source))}</b>
                leads to
                <b>${this.esc(this.endpoint_label(target))}</b>
              </div>
            `,
          },
          {
            fieldtype: "Select",
            fieldname: "line_type",
            label: "Line Type",
            options: "Solid\nDotted\nAdvisory\nFunctional",
            default: existing?.line_type || "Solid",
            reqd: 1,
          },
          {
            fieldtype: "Data",
            fieldname: "label",
            label: "Label",
            default: existing?.label || "",
          },
          {
            fieldtype: "Column Break",
          },
          {
            fieldtype: "Select",
            fieldname: "source_anchor",
            label: "Source Anchor",
            options: "Auto\nTop\nRight\nBottom\nLeft",
            default: existing?.source_anchor || "Auto",
          },
          {
            fieldtype: "Select",
            fieldname: "target_anchor",
            label: "Target Anchor",
            options: "Auto\nTop\nRight\nBottom\nLeft",
            default: existing?.target_anchor || "Auto",
          },
        ],
        primary_action_label: existing ? "Update" : "Create",
        primary_action: values => {
          completed = true;
          dialog.hide();
          resolve(values);
        },
      });

      dialog.onhide = () => {
        if (!completed) resolve(null);
      };

      dialog.show();
    });
  }

  async manage_lines() {
    const lines = this.state.reporting_lines;
    if (!lines.length) return;

    const labels = lines.map(
      (line, index) =>
        `${index + 1}. ${this.endpoint_label(this.line_ep(line, "source"))}` +
        ` → ${this.endpoint_label(this.line_ep(line, "target"))}` +
        `${line.label ? ` — ${line.label}` : ""}`
    );

    const dialog = new frappe.ui.Dialog({
      title: "Manage Reporting Lines",
      fields: [
        {
          fieldtype: "Select",
          fieldname: "line",
          label: "Reporting Line",
          options: labels.join("\n"),
          default: labels[0],
          reqd: 1,
        },
      ],
      primary_action_label: "Edit",
      primary_action: async values => {
        const index = labels.indexOf(values.line);
        dialog.hide();

        if (index < 0) return;

        const line = lines[index];
        const updated = await this.line_dialog(
          this.line_ep(line, "source"),
          this.line_ep(line, "target"),
          line
        );

        if (updated) {
          Object.assign(line, updated);
          this.mark_dirty();
          this.render_reporting();
        }
      },
    });

    dialog.show();

    const $delete = $('<button class="btn btn-danger btn-sm">Delete</button>')
      .on("click", async () => {
        const index = labels.indexOf(dialog.get_value("line"));
        if (index < 0) return;

        const confirmed = await this.confirm("Delete this reporting line?");
        if (!confirmed) return;

        lines.splice(index, 1);
        dialog.hide();
        this.mark_dirty();
        this.render_reporting();
      });

    dialog.$wrapper.find(".modal-footer").prepend($delete);
  }

  payload(){
    this.sync_asset_categories_from_control();
    this.ensure_state_keys();
    return JSON.stringify(this.state);
  }
  async save(){
    if(!this.state.branch)return frappe.msgprint("Site is required.");
    if(!this.state.location)return frappe.msgprint("Location is required.");
    this.sync_asset_categories_from_control();
    this.render_selected_asset_categories();
    if(!this.state.asset_categories.length)return frappe.msgprint("Select at least one Applicable Asset Category.");
    if(!this.state.group_headings.some(g=>g.group))return frappe.msgprint("Add at least one Group Heading.");
    const r=await frappe.call({method:`${SO_PY}.save_site_organogram_designer_state`,args:{payload:this.payload()},freeze:true,freeze_message:"Saving organogram..."});
    this.state=Object.assign(this.blank_state(),r.message||{});this.dirty=false;this.push_controls();this.render_all();frappe.show_alert({message:"Site Organogram saved.",indicator:"green"});
  }
  ensure_saved_for_output(actionLabel) {
    if (!this.state.name) {
      frappe.msgprint(`Save the organogram before ${actionLabel.toLowerCase()}.`);
      return false;
    }

    if (this.dirty) {
      frappe.msgprint(`Save changes before ${actionLabel.toLowerCase()} so the output includes the latest organogram.`);
      return false;
    }

    return true;
  }

  export_excel() {
    if (!this.ensure_saved_for_output("Exporting")) return;

    window.open(
      `/api/method/${SO_PY}.export_site_organogram_excel?name=${encodeURIComponent(this.state.name)}`,
      "_blank"
    );
  }

  print_organogram() {
    if (!this.ensure_saved_for_output("Printing")) return;

    // Open Frappe's Desk Print page, which loads the configured/default Print
    // Format and still allows the user to change format, letterhead and output.
    const printUrl = `/app/print/${encodeURIComponent("Site Organogram")}/${encodeURIComponent(this.state.name)}`;
    window.open(printUrl, "_blank");
  }
  confirm(message){return new Promise(resolve=>frappe.confirm(message,()=>resolve(true),()=>resolve(false)));}
  esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
  debounce(fn,wait=200){let t;return(...args)=>{clearTimeout(t);t=setTimeout(()=>fn(...args),wait);};}
}
