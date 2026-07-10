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
    this.add_styles();
    this.build_shell();
    this.build_page_actions();
    await this.load_designations();
    this.render_all();
  }

  add_styles() {
    if (document.getElementById("so-page-styles")) return;
    $("head").append(`
      <style id="so-page-styles">
        .so-page { padding: 0 4px 30px; }
        .so-section { border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); margin-bottom:14px; overflow:hidden; }
        .so-section__hd { padding:11px 14px; border-bottom:1px solid var(--border-color); background:var(--control-bg); display:flex; gap:12px; align-items:center; justify-content:space-between; }
        .so-section__title { font-weight:900; }
        .so-section__hint { font-size:11px; opacity:.7; text-align:right; }
        .so-section__bd { padding:14px; }
        .so-config-grid { display:grid; grid-template-columns:minmax(220px,1fr) minmax(220px,1fr) minmax(170px,.6fr); gap:12px; align-items:end; }
        .so-config-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
        .so-table { width:100%; border-collapse:separate; border-spacing:0 7px; }
        .so-table td { vertical-align:middle; }
        .so-table .form-control { min-height:34px; }
        .so-icon-btn { border:1px solid var(--border-color); background:var(--control-bg); border-radius:8px; min-width:34px; height:34px; }
        .so-empty { padding:14px; border:1px dashed var(--border-color); border-radius:10px; opacity:.7; text-align:center; }
        .so-wrap { display:flex; gap:12px; align-items:flex-start; }
        .so-left { flex:1 1 auto; min-width:0; }
        .so-right { flex:0 0 310px; max-width:330px; position:sticky; top:12px; }
        .so-panel { border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); overflow:hidden; }
        .so-panel__hd { padding:10px 12px; border-bottom:1px solid var(--border-color); display:flex; gap:8px; align-items:center; justify-content:space-between; }
        .so-panel__bd { padding:10px 12px; }
        .so-tabs { display:flex; gap:5px; flex-wrap:wrap; }
        .so-tab { border:1px solid var(--border-color); background:var(--control-bg); border-radius:9px; padding:4px 8px; font-size:11px; }
        .so-tab.is-active { font-weight:800; background:var(--btn-default-bg,var(--control-bg)); }
        .so-filters { display:flex; gap:7px; margin-bottom:8px; }
        .so-pool { display:flex; flex-direction:column; gap:7px; max-height:68vh; overflow:auto; }
        .so-pool-drop { border:1px dashed var(--border-color); border-radius:9px; padding:9px; text-align:center; opacity:.8; margin-bottom:9px; }
        .so-card { border:1px solid var(--border-color); border-radius:9px; background:var(--card-bg); padding:8px; cursor:grab; user-select:none; }
        .so-card__title { font-size:12px; font-weight:800; overflow-wrap:anywhere; }
        .so-card__meta { font-size:11px; opacity:.75; overflow-wrap:anywhere; }
        .so-group { margin-bottom:12px; }
        .so-group__hd { padding:10px 12px; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); display:flex; justify-content:space-between; align-items:center; }
        .so-group__name { font-weight:900; }
        .so-gridwrap { margin-top:9px; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); overflow:auto; }
        .so-grid { min-width:900px; }
        .so-grid__hdr,.so-grid__row { display:flex; gap:8px; padding:10px; }
        .so-grid__hdr { border-bottom:1px solid var(--border-color); background:var(--control-bg); position:sticky; top:0; z-index:1; }
        .so-hcell { font-size:12px; font-weight:900; border:1px solid var(--border-color); border-radius:9px; padding:8px; background:var(--card-bg); }
        .so-h-left,.so-leftcell { width:190px; flex:0 0 190px; }
        .so-h-slot,.so-slot { width:240px; flex:0 0 240px; }
        .so-slot { border:1px dashed var(--border-color); border-radius:9px; padding:8px; display:flex; align-items:center; min-height:50px; }
        .so-slot.is-empty { border-color:var(--red-500,#ef4444); background:color-mix(in srgb,var(--red-500,#ef4444) 14%,transparent); }
        .so-slot.is-filled { border-color:var(--green-500,#22c55e); background:color-mix(in srgb,var(--green-500,#22c55e) 14%,transparent); }
        .so-rowlabel { border:1px solid var(--border-color); border-radius:9px; padding:8px; background:var(--card-bg); min-height:50px; }
        .so-rowlabel--desig { background:var(--control-bg); }
        .so-rowlabel__title { font-size:12px; font-weight:900; }
        .so-rowlabel__meta { font-size:11px; opacity:.75; }
        .so-rowdrag { border:1px dashed transparent; border-radius:10px; }
        .so-over { outline:2px dashed var(--blue-400,#4c9aff); outline-offset:2px; }
        .so-report-toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-bottom:10px; }
        .so-report-status { margin-left:auto; font-size:12px; opacity:.75; }
        .so-report-scroll { overflow:auto; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); padding:14px; }
        .so-report-canvas { position:relative; min-width:900px; min-height:260px; padding:62px 28px 78px; }
        .so-report-stage { position:relative; z-index:2; display:flex; flex-wrap:wrap; gap:72px 34px; justify-content:center; align-items:flex-start; }
        .so-report-svg { position:absolute; inset:0; width:100%; height:100%; overflow:visible; pointer-events:none; z-index:1; }
        .so-org-node { width:220px; border:1px solid var(--border-color); border-radius:12px; background:var(--card-bg); overflow:hidden; }
        .so-org-heading { padding:11px; min-height:45px; display:flex; align-items:center; justify-content:center; background:var(--control-bg); font-size:12px; font-weight:900; text-align:center; }
        .so-org-mode { padding:5px 8px; border-top:1px solid var(--border-color); text-align:center; font-size:10px; opacity:.68; }
        .so-org-shifts { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; padding:10px; border-top:1px solid var(--border-color); }
        .so-org-shift { min-width:82px; padding:7px; border:1px solid var(--border-color); border-radius:8px; font-size:11px; font-weight:800; text-align:center; }
        .so-line-mode .so-endpoint { cursor:crosshair; outline:2px dashed var(--blue-400,#4c9aff); outline-offset:2px; }
        .so-endpoint.is-source { outline:3px solid var(--orange-500,#f59e0b); outline-offset:2px; }
        .so-line-path { fill:none; stroke:var(--text-color); stroke-width:2.25; pointer-events:stroke; cursor:pointer; }
        .so-line-hit { fill:none; stroke:transparent; stroke-width:14; pointer-events:stroke; cursor:pointer; }
        .so-line-path.dotted { stroke-dasharray:7 6; }
        .so-line-path.advisory { stroke-dasharray:3 5; stroke-width:2; }
        .so-line-path.functional { stroke-dasharray:12 5 3 5; }
        .so-line-label { font-size:11px; font-weight:700; fill:var(--text-color); paint-order:stroke; stroke:var(--card-bg); stroke-width:4px; pointer-events:none; }
        .so-dirty { color:var(--orange-600,#d97706); font-weight:800; }
        @media(max-width:1050px){ .so-config-grid{grid-template-columns:1fr;} .so-wrap{flex-direction:column;} .so-right{position:static;max-width:none;width:100%;flex-basis:auto;} }
      </style>
    `);
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
              <div data-control="asset_categories" style="grid-column:span 2"></div>
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

    this.controls.organogram.$input.on("change", () => this.load_document(this.controls.organogram.get_value()));
    this.controls.branch.$input.on("change", () => this.on_branch_change(this.controls.branch.get_value()));
    this.controls.location.$input.on("change", () => { this.state.location = this.controls.location.get_value() || ""; this.mark_dirty(); });
    this.controls.shifts.$input.on("change", () => { this.state.shifts = this.controls.shifts.get_value() || ""; this.reconcile_shifts(); this.mark_dirty(); this.render_planner(); this.render_reporting(); });
    this.controls.asset_categories.$input.on("change", () => { this.state.asset_categories = (this.controls.asset_categories.get_value() || []).map(v => ({ asset_cateogories: typeof v === "string" ? v : (v.value || v.name || "") })).filter(r => r.asset_cateogories); this.mark_dirty(); });
  }

  build_page_actions() {
    this.page.set_primary_action("Save", () => this.save(), "save");
    this.page.add_menu_item("Reload", () => this.reload());
    this.page.add_menu_item("Open DocType Record", () => {
      if (!this.state.name) return frappe.msgprint("Save the organogram first.");
      frappe.set_route("Form", "Site Organogram", this.state.name);
    });
    this.page.add_menu_item("Export Excel", () => this.export_excel());
  }

  bind_shell_events() {
    this.$main.on("click", '[data-action="new"]', () => this.new_document());
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
    if (!name) return;
    if (this.dirty) {
      const ok = await this.confirm("Discard unsaved changes and load another organogram?");
      if (!ok) { this.controls.organogram.set_value(this.state.name || ""); return; }
    }
    const r = await frappe.call({ method: `${SO_PY}.get_site_organogram_designer_state`, args: { name }, freeze: true, freeze_message: "Loading organogram..." });
    this.state = Object.assign(this.blank_state(), r.message || {});
    this.ensure_state_keys();
    this.dirty = false;
    this.push_controls();
    this.render_all();
  }

  async reload() {
    if (this.state.name) return this.load_document(this.state.name);
    this.new_document();
  }

  new_document() {
    this.state = this.blank_state();
    this.dirty = false;
    this.line_mode = false;
    this.line_source = null;
    this.push_controls();
    this.render_all();
  }

  push_controls() {
    this.controls.organogram.set_value(this.state.name || "");
    this.controls.branch.set_value(this.state.branch || "");
    this.controls.location.set_value(this.state.location || "");
    this.controls.shifts.set_value(String(this.state.shifts || "3"));
    this.controls.asset_categories.set_value((this.state.asset_categories || []).map(r => r.asset_cateogories).filter(Boolean));
  }

  async on_branch_change(branch) {
    this.state.branch = branch || "";
    if (!branch) { this.state.location = ""; this.controls.location.set_value(""); this.mark_dirty(); return; }
    const r = await frappe.call({ method: `${SO_PY}.get_matching_location_for_branch`, args: { branch } });
    const location = r.message || "";
    this.state.location = location;
    this.controls.location.set_value(location);
    this.mark_dirty();
    await this.sync_pools(false);
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
          <td style="width:42px"><button class="so-icon-btn" data-group-action="remove" title="Remove">×</button></td>
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
        <div class="so-group__hd"><div class="so-group__name">${this.esc(g.group)}</div><div style="font-size:11px;opacity:.7">${this.esc(g.shifts)}</div></div>
        <div class="so-gridwrap"><div class="so-grid" data-drop="grid" data-group-key="${this.esc(g.group_key)}">
          <div class="so-grid__hdr"><div class="so-hcell so-h-left">Asset / Designation</div>${shifts.map(s=>`<div class="so-hcell so-h-slot">${this.esc(s)}</div>`).join("")}</div>
          ${rows.length ? rows.map(identity => `<div class="so-grid__row so-rowdrag" draggable="true" data-drag-type="row" data-group-key="${this.esc(g.group_key)}" data-row-key="${this.esc(identity.row_key)}">
            <div class="so-leftcell">${this.row_label(identity)}</div>
            ${shifts.map(s=>this.slot_html(g,s,identity)).join("")}
          </div>`).join("") : '<div class="so-empty" style="margin:10px">Drop an Asset or Designation into this group to create rows.</div>'}
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
  slot_html(g,shift,identity) { const r=this.find_mapping(g.group_key,shift,identity.row_key); const e=r?.employee?this.employee_by_id(r.employee):null; return `<div class="so-slot ${e?"is-filled":"is-empty"}" data-drop="cell" data-group-key="${this.esc(g.group_key)}" data-shift="${this.esc(shift)}" data-row-key="${this.esc(identity.row_key)}">${e?this.employee_card(e,"assigned",{group_key:g.group_key,shift,row_key:identity.row_key}):'<span style="font-size:12px;opacity:.7">Vacant</span>'}</div>`; }

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

  render_reporting() {
    const $w=this.$main.find(".so-reporting"); const count=this.state.reporting_lines.length;
    const status=this.line_mode?(this.line_source?`Source selected: ${this.esc(this.endpoint_label(this.line_source))}. Select the target.`:"Select a source heading or shift."):`${count} reporting line${count===1?"":"s"}`;
    const nodes=this.state.group_headings.filter(g=>g.group).map(g=>`<div class="so-org-node"><div class="so-org-heading so-endpoint" data-group-key="${this.esc(g.group_key)}" data-group="${this.esc(g.group)}" data-scope="Heading" data-shift="">${this.esc(g.group)}</div><div class="so-org-mode">${this.esc(g.shifts)}</div><div class="so-org-shifts">${this.shifts_for_group(g).map(s=>`<div class="so-org-shift so-endpoint" data-group-key="${this.esc(g.group_key)}" data-group="${this.esc(g.group)}" data-scope="Shift" data-shift="${this.esc(s)}">${this.esc(s)}</div>`).join("")}</div></div>`).join("")||'<div class="so-empty">Add group headings to create reporting endpoints.</div>';
    $w.html(`<div class="${this.line_mode?"so-line-mode":""}"><div class="so-report-toolbar"><button class="btn btn-sm ${this.line_mode?"btn-warning":"btn-default"}" data-report-action="toggle">${this.line_mode?"Cancel Drawing":"Draw Reporting Line"}</button><button class="btn btn-sm btn-default" data-report-action="manage" ${count?"":"disabled"}>Manage Lines</button><span class="so-report-status">${status}</span></div><div class="so-report-scroll"><div class="so-report-canvas"><svg class="so-report-svg"></svg><div class="so-report-stage">${nodes}</div></div></div></div>`);
    if(this.line_source){$w.find(this.endpoint_selector(this.line_source)).first().addClass("is-source");}
    $w.find('[data-report-action="toggle"]').on("click",()=>{this.line_mode=!this.line_mode;this.line_source=null;this.render_reporting();});
    $w.find('[data-report-action="manage"]').on("click",()=>this.manage_lines());
    $w.find(".so-endpoint").on("click",async e=>{if(!this.line_mode)return;const ep=this.endpoint_from_el(e.currentTarget);if(!this.line_source){this.line_source=ep;this.render_reporting();return;}await this.create_line(this.line_source,ep);this.line_mode=false;this.line_source=null;this.render_reporting();});
    requestAnimationFrame(()=>this.draw_lines($w));
  }

  endpoint_from_el(el){return{group_key:el.dataset.groupKey||"",group:el.dataset.group||"",scope:el.dataset.scope||"Heading",shift:el.dataset.shift||""};}
  endpoint_label(ep){return ep.scope==="Shift"&&ep.shift?`${ep.group} — ${ep.shift}`:ep.group;}
  endpoint_selector(ep){const esc=v=>String(v||"").replace(/\\/g,"\\\\").replace(/"/g,'\\"');return `.so-endpoint[data-group-key="${esc(ep.group_key)}"][data-scope="${esc(ep.scope)}"][data-shift="${esc(ep.shift||"")}"]`;}
  line_ep(line,p){return{group_key:line[`${p}_group_key`]||"",group:line[`${p}_group`]||"",scope:line[`${p}_scope`]||"Heading",shift:line[`${p}_shift`]||""};}

  async create_line(source,target){
    if(source.group_key===target.group_key&&source.scope===target.scope&&(source.shift||"")===(target.shift||""))return frappe.msgprint("A reporting line cannot connect an endpoint to itself.");
    if(this.state.reporting_lines.some(l=>JSON.stringify(this.line_ep(l,"source"))===JSON.stringify(source)&&JSON.stringify(this.line_ep(l,"target"))===JSON.stringify(target)))return frappe.msgprint("That reporting line already exists.");
    const result=await this.line_dialog(source,target);if(!result)return;
    this.state.reporting_lines.push({source_group_key:source.group_key,source_group:source.group,source_scope:source.scope,source_shift:source.scope==="Shift"?source.shift:"",target_group_key:target.group_key,target_group:target.group,target_scope:target.scope,target_shift:target.scope==="Shift"?target.shift:"",line_type:result.line_type||"Solid",label:result.label||"",source_anchor:result.source_anchor||"Auto",target_anchor:result.target_anchor||"Auto",line_order:this.state.reporting_lines.length+1});
    this.mark_dirty();
  }

  line_dialog(source,target,existing){return new Promise(resolve=>{let done=false;const d=new frappe.ui.Dialog({title:existing?"Edit Reporting Line":"Create Reporting Line",fields:[{fieldtype:"HTML",options:`<div><b>${this.esc(this.endpoint_label(source))}</b> reports to <b>${this.esc(this.endpoint_label(target))}</b></div>`},{fieldtype:"Select",fieldname:"line_type",label:"Line Type",options:"Solid\nDotted\nAdvisory\nFunctional",default:existing?.line_type||"Solid",reqd:1},{fieldtype:"Data",fieldname:"label",label:"Label",default:existing?.label||""},{fieldtype:"Column Break"},{fieldtype:"Select",fieldname:"source_anchor",label:"Source Anchor",options:"Auto\nTop\nRight\nBottom\nLeft",default:existing?.source_anchor||"Auto"},{fieldtype:"Select",fieldname:"target_anchor",label:"Target Anchor",options:"Auto\nTop\nRight\nBottom\nLeft",default:existing?.target_anchor||"Auto"}],primary_action_label:existing?"Update":"Create",primary_action:v=>{done=true;d.hide();resolve(v);}});d.onhide=()=>{if(!done)resolve(null);};d.show();});}

  async manage_lines(){const lines=this.state.reporting_lines;if(!lines.length)return;const labels=lines.map((l,i)=>`${i+1}. ${this.endpoint_label(this.line_ep(l,"source"))} → ${this.endpoint_label(this.line_ep(l,"target"))}${l.label?` — ${l.label}`:""}`);const d=new frappe.ui.Dialog({title:"Manage Reporting Lines",fields:[{fieldtype:"Select",fieldname:"line",label:"Reporting Line",options:labels.join("\n"),default:labels[0],reqd:1}],primary_action_label:"Edit",primary_action:async v=>{const i=labels.indexOf(v.line);d.hide();if(i<0)return;const l=lines[i];const vals=await this.line_dialog(this.line_ep(l,"source"),this.line_ep(l,"target"),l);if(vals){Object.assign(l,vals);this.mark_dirty();this.render_reporting();}}});d.add_custom_action?.("Delete",()=>{});d.show();const $delete=$(`<button class="btn btn-danger btn-sm">Delete</button>`).on("click",async()=>{const i=labels.indexOf(d.get_value("line"));if(i<0)return;const ok=await this.confirm("Delete this reporting line?");if(ok){lines.splice(i,1);d.hide();this.mark_dirty();this.render_reporting();}});d.$wrapper.find(".modal-footer").prepend($delete);}

  draw_lines($w){const canvas=$w.find(".so-report-canvas").get(0),svg=$w.find(".so-report-svg").get(0);if(!canvas||!svg)return;const rect=canvas.getBoundingClientRect();svg.setAttribute("viewBox",`0 0 ${Math.max(1,rect.width)} ${Math.max(1,rect.height)}`);svg.innerHTML='<defs><marker id="so-page-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L0,6 L9,3 z" fill="currentColor"></path></marker></defs>';this.state.reporting_lines.forEach((l,i)=>{const s=$w.find(this.endpoint_selector(this.line_ep(l,"source"))).first().get(0),t=$w.find(this.endpoint_selector(this.line_ep(l,"target"))).first().get(0);if(!s||!t)return;const a=this.anchor_point(s,rect,l.source_anchor||"Auto",t),b=this.anchor_point(t,rect,l.target_anchor||"Auto",s),lane=(i%6)*10,d=this.orthogonal_path(a,b,lane),ns="http://www.w3.org/2000/svg";const hit=document.createElementNS(ns,"path");hit.setAttribute("d",d);hit.setAttribute("class","so-line-hit");hit.dataset.index=i;const path=document.createElementNS(ns,"path");path.setAttribute("d",d);path.setAttribute("class",`so-line-path ${String(l.line_type||"Solid").toLowerCase()}`);path.setAttribute("marker-end","url(#so-page-arrow)");path.dataset.index=i;svg.append(hit,path);if(l.label){const txt=document.createElementNS(ns,"text");txt.setAttribute("x",String((a.x+b.x)/2));txt.setAttribute("y",String(Math.min(a.y,b.y)-35-lane));txt.setAttribute("text-anchor","middle");txt.setAttribute("class","so-line-label");txt.textContent=l.label;svg.appendChild(txt);}});$w.find(".so-line-hit,.so-line-path").on("click",e=>{e.stopPropagation();const i=Number(e.currentTarget.dataset.index);if(Number.isInteger(i)){const l=this.state.reporting_lines[i];this.line_dialog(this.line_ep(l,"source"),this.line_ep(l,"target"),l).then(v=>{if(v){Object.assign(l,v);this.mark_dirty();this.render_reporting();}});}});}
  anchor_point(el,canvasRect,anchor,other){const r=el.getBoundingClientRect(),o=other.getBoundingClientRect(),c={x:r.left-canvasRect.left+r.width/2,y:r.top-canvasRect.top+r.height/2},oc={x:o.left-canvasRect.left+o.width/2,y:o.top-canvasRect.top+o.height/2};let a=anchor;if(!a||a==="Auto"){const dx=oc.x-c.x,dy=oc.y-c.y;a=Math.abs(dx)>Math.abs(dy)?(dx>=0?"Right":"Left"):(dy>=0?"Bottom":"Top");}if(a==="Top")return{x:c.x,y:r.top-canvasRect.top};if(a==="Right")return{x:r.right-canvasRect.left,y:c.y};if(a==="Left")return{x:r.left-canvasRect.left,y:c.y};return{x:c.x,y:r.bottom-canvasRect.top};}
  orthogonal_path(a,b,lane){if(Math.abs(a.y-b.y)<90){const y=Math.max(18,Math.min(a.y,b.y)-34-lane);return`M ${a.x} ${a.y} L ${a.x} ${y} L ${b.x} ${y} L ${b.x} ${b.y}`;}const dir=b.y>=a.y?1:-1,y=a.y+dir*(34+lane);return`M ${a.x} ${a.y} L ${a.x} ${y} L ${b.x} ${y} L ${b.x} ${b.y}`;}

  payload(){this.ensure_state_keys();return JSON.stringify(this.state);}
  async save(){
    if(!this.state.branch)return frappe.msgprint("Site is required.");
    if(!this.state.location)return frappe.msgprint("Location is required.");
    if(!this.state.group_headings.some(g=>g.group))return frappe.msgprint("Add at least one Group Heading.");
    const r=await frappe.call({method:`${SO_PY}.save_site_organogram_designer_state`,args:{payload:this.payload()},freeze:true,freeze_message:"Saving organogram..."});
    this.state=Object.assign(this.blank_state(),r.message||{});this.dirty=false;this.push_controls();this.render_all();frappe.show_alert({message:"Site Organogram saved.",indicator:"green"});
  }
  export_excel(){if(!this.state.name)return frappe.msgprint("Save the organogram first.");if(this.dirty)return frappe.msgprint("Save changes before exporting.");window.open(`/api/method/${SO_PY}.export_site_organogram_excel?name=${encodeURIComponent(this.state.name)}`,"_blank");}
  confirm(message){return new Promise(resolve=>frappe.confirm(message,()=>resolve(true),()=>resolve(false)));}
  esc(v){return String(v??"").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");}
  debounce(fn,wait=200){let t;return(...args)=>{clearTimeout(t);t=setTimeout(()=>fn(...args),wait);};}
}
