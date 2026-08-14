// Copyright (c) 2026, BuFf0k and contributors
// Site Plan Designer Page

const SP_API = "ir.industrial_relations.page.ir_site_plan_design.ir_site_plan_design";
const SITE_PLAN_PY = "ir.industrial_relations.doctype.site_plan.site_plan";

frappe.pages["ir-site-plan-design"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "Site Plan Designer",
    single_column: true,
  });

  const app = new SitePlanDesigner(page, wrapper);
  wrapper.site_plan_designer = app;
  app.init();
};

class SitePlanDesigner {
  constructor(page, wrapper) {
    this.page = page;
    this.wrapper = wrapper;
    this.$main = $(page.main);
    this.controls = {};
    this.bootstrap = {};
    this.state = this.blank_state();
    this.dirty = false;
  }

  blank_state() {
    return {
      name: "",
      plan_name: "",
      branch: "",
      location: "",
      status: "Draft",
      enabled: 1,
      effective_from: "",
      effective_until: "",
      groups: [],
      slots: [],
      reporting_lines: [],
    };
  }

  async init() {
    this.build_shell();
    this.page.set_primary_action(__("Save Site Plan"), () => this.save());
    this.page.add_menu_item(__("Export Excel"), () => this.export_excel());
    this.page.add_menu_item(__("Export Diagram PNG"), () => this.export_reporting_png());
    this.page.add_menu_item(__("Delete Site Plan"), () => this.delete_plan());

    this.bind_events();
    await this.load_bootstrap();
    this.make_controls();
    this.new_plan(false);
    this.render_all();
  }

  build_shell() {
    this.$main.html(`
      <div class="so-page">
        <div class="so-section">
          <div class="so-section__hd">
            <div><div class="so-section__title">${__("Site Plan Configuration")}</div><div class="so-doc-status"></div></div>
            <div class="so-section__hint">${__("A Site Plan is a reusable, dated structure - group headings, slots and reporting lines - that Site Organograms are built from. It carries no specific Employees or Assets.")}</div>
          </div>
          <div class="so-section__bd">
            <div class="so-config-grid">
              <div data-control="plan"></div>
              <div data-control="plan_name"></div>
              <div data-control="branch"></div>
              <div data-control="location"></div>
              <div data-control="status"></div>
              <div data-control="enabled"></div>
              <div data-control="effective_from"></div>
              <div data-control="effective_until"></div>
            </div>
            <div class="so-config-actions">
              <button class="btn btn-sm btn-default" data-action="new">${__("New Site Plan")}</button>
              <span class="sdm-save-state"></span>
            </div>
          </div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">${__("Group Headings")}</div><div class="so-section__hint">${__("Headings define the major structural sections and the Shift Design each one draws its shift columns from.")}</div></div>
          <div class="so-section__bd"><div class="so-groups"></div></div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">${__("Slots")}</div><div class="so-section__hint">${__("Slots describe what should exist in each group - a Designation, or an Asset of a given Category - without picking a specific Employee or Asset. A Site Organogram built from this Plan gets one row per Slot, ready to fill in.")}</div></div>
          <div class="so-section__bd"><div class="so-slots"></div></div>
        </div>

        <div class="so-section">
          <div class="so-section__hd"><div class="so-section__title">${__("Reporting Lines")}</div><div class="so-section__hint">${__("Reporting relationships between headings (or specific shift columns within a heading).")}</div></div>
          <div class="so-section__bd"><div class="so-reporting"></div></div>
        </div>
      </div>
    `);
  }

  async load_bootstrap() {
    const response = await frappe.call({ method: `${SP_API}.get_bootstrap` });
    this.bootstrap = response.message || {};
  }

  make_controls() {
    this.controls.plan = frappe.ui.form.make_control({
      parent: this.$main.find('[data-control="plan"]'),
      df: { fieldtype: "Link", label: __("Site Plan"), options: "Site Plan", fieldname: "plan" },
      render_input: true,
    });
    this.controls.plan_name = this.control("plan_name", "Data", __("Plan Name"), { reqd: 1 });
    this.controls.branch = this.control("branch", "Link", __("Default Branch"), { options: "Branch" });
    this.controls.location = this.control("location", "Link", __("Default Location"), { options: "Location" });
    this.controls.status = this.control("status", "Select", __("Status"), {
      options: "Draft\nActive\nSuperseded\nArchived",
      reqd: 1,
    });
    this.controls.enabled = this.control("enabled", "Check", __("Enabled"));
    this.controls.effective_from = this.control("effective_from", "Date", __("Effective From"), { reqd: 1 });
    this.controls.effective_until = this.control("effective_until", "Date", __("Effective Until (blank = indefinite)"));

    this.bind_control(this.controls.plan, async (value) => {
      if (value && value !== this.state.name) {
        await this.load_plan(value);
      }
    });

    for (const fieldname of ["plan_name", "branch", "location", "status", "enabled", "effective_from", "effective_until"]) {
      this.bind_control(this.controls[fieldname], (value) => {
        this.state[fieldname] = value;
        if (fieldname === "status" && ["Superseded", "Archived"].includes(value)) {
          this.state.enabled = 0;
          this.controls.enabled.set_value(0);
        }
        this.mark_dirty();
      });
    }
  }

  control(fieldname, fieldtype, label, extra = {}) {
    return frappe.ui.form.make_control({
      parent: this.$main.find(`[data-control="${fieldname}"]`),
      df: { fieldname, fieldtype, label, ...extra },
      render_input: true,
    });
  }

  bind_control(control, handler) {
    if (!control?.$input) return;
    const namespace = `.spd-${control.df.fieldname}`;
    control.$input.off(namespace);
    control.$input.on(
      `change${namespace} awesomplete-selectcomplete${namespace}`,
      () => {
        if (this.suppress_control_events) return;
        Promise.resolve(handler(control.get_value())).catch((error) => this.error(error));
      },
    );
  }

  bind_events() {
    this.$main.on("click", '[data-action="new"]', () => this.new_plan());
  }

  async new_plan(render = true) {
    this.state = this.blank_state();
    this.dirty = false;
    if (render) {
      await this.sync_controls();
      this.dirty = false;
      this.render_all();
    }
  }

  async load_plan(name) {
    // this.bootstrap.shift_designs is fetched once at page load - refreshed
    // alongside the load so a Shift Design created after this tab was first
    // opened is already known before render_all() below works out each
    // group's shift columns (and reporting-line row counts) from it.
    const [response] = await Promise.all([
      frappe.call({ method: `${SP_API}.get_plan`, args: { name } }),
      this.load_bootstrap(),
    ]);
    this.state = { ...this.blank_state(), ...(response.message || {}) };
    this.dirty = false;
    await this.sync_controls();
    this.dirty = false;
    this.render_all();
  }

  // Link controls' set_value() does a real server round-trip (validating the
  // value) before it resolves and its own 'change' event fires - syncing
  // every control here is what a load/reset needs to do, but without
  // suppression each of those set_value() calls re-fires the normal change
  // handler above and immediately re-marks a freshly-loaded record dirty.
  // Awaiting every set_value() before lifting suppression is what actually
  // closes that race, not just deferring it by a tick.
  async sync_controls() {
    this.suppress_control_events = true;
    try {
      await Promise.all(
        Object.entries(this.controls).map(([fieldname, control]) =>
          control.set_value(fieldname === "plan" ? this.state.name || "" : this.state[fieldname] ?? ""),
        ),
      );
    } finally {
      this.suppress_control_events = false;
    }
  }

  render_all() {
    this.render_groups();
    this.render_slots();
    this.render_reporting();
    this.render_save_state();
  }

  // ---------------------------------------------------------------------
  // Group Headings
  // ---------------------------------------------------------------------

  new_group_key() {
    return `GRP::${frappe.utils.get_random(10)}`;
  }

  render_groups() {
    const $w = this.$main.find(".so-groups");
    const rows = this.state.groups || [];
    $w.html(`
      ${rows.length ? `<table class="so-table"><tbody>${rows.map((g, i) => `
        <tr data-group-index="${i}">
          <td><input class="form-control" data-group-field="group" value="${this.esc(g.group || "")}" placeholder="${__("Heading name")}"></td>
          <td><select class="form-control" data-group-field="shift_design">
            <option value="">${this.esc(__("Select Shift Design"))}</option>
            ${(this.bootstrap.shift_designs || []).map((d) => `<option value="${this.esc(d.name)}" ${g.shift_design === d.name ? "selected" : ""}>${this.esc(d.name)} (${d.number_of_teams})</option>`).join("")}
          </select></td>
          <td class="so-group-remove-cell"><button class="so-icon-btn" data-group-action="remove" title="${__("Remove")}">×</button></td>
        </tr>`).join("")}</tbody></table>` : `<div class="so-empty">${__("No group headings configured.")}</div>`}
      <button class="btn btn-sm btn-default" data-group-action="add">${__("Add Group Heading")}</button>
    `);

    $w.find('[data-group-action="add"]').on("click", () => {
      this.state.groups.push({ group_key: this.new_group_key(), group: "", shift_design: "" });
      this.mark_dirty();
      this.render_groups();
      this.render_slots();
      this.render_reporting();
    });

    $w.find('[data-group-action="remove"]').on("click", async (ev) => {
      const i = Number($(ev.currentTarget).closest("tr").data("group-index"));
      const g = this.state.groups[i];
      if (!g) return;
      const ok = await this.confirm(__("Remove heading “{0}” and its slots/reporting lines?", [g.group || __("Unnamed")]));
      if (!ok) return;
      this.state.groups.splice(i, 1);
      this.state.slots = this.state.slots.filter((r) => r.group_key !== g.group_key);
      this.state.reporting_lines = this.state.reporting_lines.filter(
        (r) => r.source_group_key !== g.group_key && r.target_group_key !== g.group_key,
      );
      this.mark_dirty();
      this.render_all();
    });

    $w.find("[data-group-field]").on("change", (ev) => {
      const $tr = $(ev.currentTarget).closest("tr");
      const i = Number($tr.data("group-index"));
      const field = ev.currentTarget.getAttribute("data-group-field");
      const g = this.state.groups[i];
      if (!g) return;
      const oldName = g.group;
      g[field] = ev.currentTarget.value || "";
      if (field === "group") {
        for (const r of this.state.slots) {
          if (r.group_key === g.group_key || r.group === oldName) {
            r.group_key = g.group_key;
            r.group = g.group;
          }
        }
        for (const l of this.state.reporting_lines) {
          if (l.source_group_key === g.group_key || l.source_group === oldName) {
            l.source_group_key = g.group_key;
            l.source_group = g.group;
          }
          if (l.target_group_key === g.group_key || l.target_group === oldName) {
            l.target_group_key = g.group_key;
            l.target_group = g.group;
          }
        }
        this.mark_dirty();
        this.render_slots();
        this.render_reporting();
      } else {
        this.mark_dirty();
        this.render_reporting();
      }
    });
  }

  // ---------------------------------------------------------------------
  // Slots
  // ---------------------------------------------------------------------

  new_slot_key() {
    return `SLOT::${frappe.utils.get_random(10)}`;
  }

  slots_for_group(g) {
    return (this.state.slots || [])
      .filter((r) => r.group_key === g.group_key)
      .sort((a, b) => (Number(a.row_order) || 9999) - (Number(b.row_order) || 9999));
  }

  render_slots() {
    const $w = this.$main.find(".so-slots");
    const groups = (this.state.groups || []).filter((g) => g.group && g.group_key);

    if (!groups.length) {
      $w.html(`<div class="so-empty">${__("Add at least one Group Heading before defining Slots.")}</div>`);
      return;
    }

    const designationOptions = (this.bootstrap.designations || []);
    const categoryOptions = (this.bootstrap.asset_categories || []);

    const groupsHtml = groups
      .map((g) => {
        const rows = this.slots_for_group(g);
        return `<div class="so-group">
          <div class="so-group__hd"><div class="so-group__name">${this.esc(g.group)}</div></div>
          <div class="so-gridwrap"><table class="so-table" data-slot-group-key="${this.esc(g.group_key)}"><tbody class="so-slots-tbody" data-group-key="${this.esc(g.group_key)}" data-group="${this.esc(g.group)}">
            ${rows.length ? rows.map((r) => `
              <tr data-slot-key="${this.esc(r.row_key)}">
                <td class="so-slot-drag-cell"><span class="so-slot-drag-handle" title="${__("Drag to reorder, or drag into another heading below to move it there")}">⠿</span></td>
                <td><select class="form-control" data-slot-field="row_type">
                  <option value="Designation" ${r.row_type === "Designation" ? "selected" : ""}>${__("Designation")}</option>
                  <option value="Asset" ${r.row_type === "Asset" ? "selected" : ""}>${__("Asset")}</option>
                </select></td>
                <td><select class="form-control" data-slot-field="designation">
                  <option value="">${this.esc(__("(none)"))}</option>
                  ${designationOptions.map((d) => `<option value="${this.esc(d)}" ${r.designation === d ? "selected" : ""}>${this.esc(d)}</option>`).join("")}
                </select></td>
                <td class="so-slot-category-cell${r.row_type === "Asset" ? "" : " is-hidden"}">
                  <select class="form-control" data-slot-field="asset_category">
                    <option value="">${this.esc(__("(none)"))}</option>
                    ${categoryOptions.map((c) => `<option value="${this.esc(c)}" ${r.asset_category === c ? "selected" : ""}>${this.esc(c)}</option>`).join("")}
                  </select>
                </td>
                <td><input class="form-control" data-slot-field="row_label" value="${this.esc(r.row_label || "")}" placeholder="${__("Label")}"></td>
                <td class="so-slot-spare-cell"><label><input type="checkbox" data-slot-field="spare_swing" ${r.spare_swing ? "checked" : ""}> ${__("Spare / Swing")}</label></td>
                <td class="so-group-remove-cell so-slot-actions-cell">
                  <button class="so-icon-btn" data-slot-action="duplicate" title="${__("Duplicate this row")}">⧉</button>
                  <button class="so-icon-btn" data-slot-action="remove" title="${__("Remove")}">×</button>
                </td>
              </tr>
            `).join("") : `<tr class="so-slots-empty-row"><td colspan="7"><div class="so-empty">${__("No slots yet.")}</div></td></tr>`}
          </tbody></table></div>
          <button class="btn btn-sm btn-default" data-slot-action="add" data-group-key="${this.esc(g.group_key)}">${__("Add Slot")}</button>
        </div>`;
      })
      .join("");

    $w.html(groupsHtml);
    this.bind_slots_sortable($w);

    $w.find('[data-slot-action="add"]').on("click", (ev) => {
      const groupKey = $(ev.currentTarget).data("group-key");
      const order = this.slots_for_group({ group_key: groupKey }).length + 1;
      this.state.slots.push({
        group_key: groupKey,
        row_key: this.new_slot_key(),
        row_type: "Designation",
        designation: "",
        asset_category: "",
        row_label: "",
        row_order: order,
        spare_swing: 0,
      });
      this.mark_dirty();
      this.render_slots();
    });

    $w.find('[data-slot-action="remove"]').on("click", (ev) => {
      const rowKey = $(ev.currentTarget).closest("tr").data("slot-key");
      this.state.slots = this.state.slots.filter((r) => r.row_key !== rowKey);
      this.mark_dirty();
      this.render_slots();
    });

    $w.find('[data-slot-action="duplicate"]').on("click", (ev) => {
      const rowKey = $(ev.currentTarget).closest("tr").data("slot-key");
      this.duplicate_slot(rowKey);
    });

    $w.find("[data-slot-field]").on("change", (ev) => {
      const $tr = $(ev.currentTarget).closest("tr");
      const rowKey = $tr.data("slot-key");
      const field = ev.currentTarget.getAttribute("data-slot-field");
      const row = this.state.slots.find((r) => r.row_key === rowKey);
      if (!row) return;
      row[field] = field === "spare_swing" ? (ev.currentTarget.checked ? 1 : 0) : ev.currentTarget.value || "";
      this.mark_dirty();
      if (field === "row_type") {
        this.render_slots();
      }
    });
  }

  // A copy-paste-from-CSV workflow for a large repetitive Slot list (many
  // near-identical Asset rows, say) is exactly what produced the duplicate
  // row_key bug found in production - this is the safe alternative: every
  // duplicate gets its own fresh row_key, so there's never a reason to hand-
  // edit row_key (a field the UI doesn't even expose) to work around it.
  duplicate_slot(rowKey) {
    const idx = this.state.slots.findIndex((r) => r.row_key === rowKey);
    if (idx < 0) return;
    const source = this.state.slots[idx];
    const clone = { ...source, row_key: this.new_slot_key() };
    this.state.slots.splice(idx + 1, 0, clone);
    this.renumber_group(source.group_key);
    this.mark_dirty();
    this.render_slots();
  }

  // row_order only needs to be sequential *within* a group - re-deriving it
  // from this.state.slots' own array order (relative order among rows that
  // share a group_key) after any insert/move keeps it simple and avoids
  // fractional/duplicate order values.
  renumber_group(groupKey) {
    let order = 1;
    for (const row of this.state.slots) {
      if (row.group_key === groupKey) row.row_order = order++;
    }
  }

  // One Sortable instance per heading's <tbody>, all sharing the same
  // `group` name - that's what SortableJS uses to allow dragging a row from
  // one heading's table into another's, not just reordering within one.
  bind_slots_sortable($w) {
    if (!window.Sortable) return;
    if (this._slotsSortables) {
      this._slotsSortables.forEach((s) => s.destroy());
    }
    this._slotsSortables = $w.find(".so-slots-tbody").toArray().map((tbody) =>
      new Sortable(tbody, {
        group: "site-plan-slots",
        handle: ".so-slot-drag-handle",
        animation: 150,
        filter: ".so-slots-empty-row",
        onEnd: () => this.handle_slots_reordered(),
      })
    );
  }

  // Fired after any drag ends, whether it reordered rows within one heading
  // or moved a row into another - re-derives group_key/group/row_order for
  // every Slot from the DOM's current tbody membership and row order, which
  // is simplest single source of truth once the user has finished dragging.
  handle_slots_reordered() {
    const byRowKey = new Map(this.state.slots.map((r) => [r.row_key, r]));
    const seen = new Set();
    const reordered = [];

    this.$main.find(".so-slots-tbody").each((_, tbody) => {
      const $tbody = $(tbody);
      const groupKey = $tbody.attr("data-group-key");
      const group = $tbody.attr("data-group");
      let order = 1;
      $tbody.find("tr[data-slot-key]").each((_, tr) => {
        const row = byRowKey.get($(tr).attr("data-slot-key"));
        if (!row) return;
        row.group_key = groupKey;
        row.group = group;
        row.row_order = order++;
        seen.add(row);
        reordered.push(row);
      });
    });

    // Defensive: a Slot that somehow isn't currently rendered (shouldn't
    // happen) keeps its place at the end rather than silently vanishing.
    for (const row of this.state.slots) {
      if (!seen.has(row)) reordered.push(row);
    }

    this.state.slots = reordered;
    this.mark_dirty();
    this.render_slots();
  }

  // ---------------------------------------------------------------------
  // Reporting Lines - visual layout ported from the Organogram Designer,
  // adapted to render Slot summaries instead of live Employee assignments
  // (a Plan has no Employees/Assets, only the shape of what should exist).
  // ---------------------------------------------------------------------

  shift_design_team_count(designName) {
    const row = (this.bootstrap.shift_designs || []).find((d) => d.name === designName);
    return row ? Math.max(0, Number(row.number_of_teams) || 0) : 0;
  }

  slots_for_count(count) {
    return Array.from({ length: Math.max(0, Math.min(20, count)) }, (_, i) => `Shift ${String.fromCharCode(65 + i)}`);
  }

  shifts_for_group(g) {
    return this.slots_for_count(this.shift_design_team_count(g.shift_design));
  }

  plan_blocks() {
    const groups = (this.state.groups || []).filter((group) => group.group && group.group_key);
    const blocks = [];
    const byKey = new Map();

    groups.forEach((group, groupOrder) => {
      const shifts = this.shifts_for_group(group);
      const rows = this.plan_block_rows(group);
      shifts.forEach((shift, shiftOrder) => {
        const key = `${group.group_key}::${shift}`;
        const block = { key, group_key: group.group_key, group: group.group, shift, shift_order: shiftOrder, group_order: groupOrder, rows };
        blocks.push(block);
        byKey.set(key, block);
      });
    });

    return { blocks, byKey, groups };
  }

  plan_block_rows(group) {
    return this.slots_for_group(group).map((r) => ({
      row_key: r.row_key,
      left_title: r.row_type === "Asset" ? r.asset_category || __("Asset") : r.designation || r.row_label || __("Designation"),
      left_meta: r.row_type === "Asset" ? __("Asset slot") : __("Designation slot"),
      spare: !!r.spare_swing,
      designation: r.designation || "",
    }));
  }

  organogram_endpoint_blocks(endpoint, model) {
    if (!endpoint || !endpoint.group_key) return [];
    if (endpoint.scope === "Shift" && endpoint.shift) {
      const block = model.byKey.get(`${endpoint.group_key}::${endpoint.shift}`);
      return block ? [block] : [];
    }
    return model.blocks.filter((block) => block.group_key === endpoint.group_key);
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
      const sourceBlocks = this.organogram_endpoint_blocks(sourceEndpoint, model);
      const targetBlocks = this.organogram_endpoint_blocks(targetEndpoint, model);
      if (!sourceBlocks.length || !targetBlocks.length) return;

      if (sourceEndpoint.scope === "Heading" && targetEndpoint.scope === "Heading" && sourceBlocks.length > 1 && targetBlocks.length > 1) {
        const targetsByShift = new Map(targetBlocks.map((block) => [block.shift, block]));
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

  reporting_sort_nodes(nodes) {
    return [...nodes].sort((a, b) => {
      const groupOrderCompare = Number(a.block.group_order || 0) - Number(b.block.group_order || 0);
      if (groupOrderCompare !== 0) return groupOrderCompare;
      const shiftOrderCompare = Number(a.block.shift_order || 0) - Number(b.block.shift_order || 0);
      if (shiftOrderCompare !== 0) return shiftOrderCompare;
      const groupCompare = a.block.group.localeCompare(b.block.group, undefined, { numeric: true });
      if (groupCompare !== 0) return groupCompare;
      return a.block.shift.localeCompare(b.block.shift, undefined, { numeric: true });
    });
  }

  build_reporting_graph() {
    const model = this.plan_blocks();
    const edges = this.expand_reporting_edges(model);
    const nodesByKey = new Map(model.blocks.map((block) => [block.key, { key: block.key, block, children: [], parents: [] }]));

    edges.forEach((edge) => {
      const source = nodesByKey.get(edge.source.key);
      const target = nodesByKey.get(edge.target.key);
      if (!source || !target) return;
      source.children.push(target);
      target.parents.push(source);
    });

    nodesByKey.forEach((node) => {
      node.children = this.reporting_sort_nodes(node.children);
      node.parents = this.reporting_sort_nodes(node.parents);
    });

    const roots = this.reporting_sort_nodes([...nodesByKey.values()].filter((node) => !node.parents.length));
    return { model, edges, nodesByKey, roots };
  }

  collect_branch_descendants(node) {
    const results = [];
    const seen = new Set();
    const visit = (current) => {
      current.children.forEach((child) => {
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

    graph.roots.forEach((root) => {
      if (!root.children.length) {
        standalone.push(root);
        return;
      }

      const branches = this.reporting_sort_nodes(root.children);
      const rowDefs = [];
      const rowSeen = new Set();
      const branchRows = new Map();

      branches.forEach((branch) => {
        const descendants = this.collect_branch_descendants(branch).filter((node) => node.key !== branch.key);
        const byGroup = new Map();

        descendants.forEach((node) => {
          const rowKey = node.block.group_key;
          if (!rowKey || rowKey === branch.block.group_key) return;
          if (!byGroup.has(rowKey)) byGroup.set(rowKey, node);
          if (!rowSeen.has(rowKey)) {
            rowSeen.add(rowKey);
            rowDefs.push({ group_key: node.block.group_key, group: node.block.group, group_order: Number(node.block.group_order || 0) });
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
    return { block: node.block, cyclic: false, secondary_parents: node.parents.slice(1).map((parent) => parent.block) };
  }

  plan_block_html(node) {
    const block = node.block;
    const rowsHtml = block.rows.length
      ? block.rows
          .map(
            (row) => `
            <div class="so-org-person-row ${row.spare ? "is-spare" : "is-vacant"}">
              <div class="so-org-person-row__role">
                <div class="so-org-person-row__role-title">${this.esc(row.left_title)}</div>
                ${row.left_meta ? `<div class="so-org-person-row__meta">${this.esc(row.left_meta)}</div>` : ""}
              </div>
              <div class="so-org-person-row__employee">
                <div class="so-org-person-row__employee-name">${row.spare ? __("Spare / Swing slot") : __("Vacant slot")}</div>
                ${row.designation ? `<div class="so-org-person-row__meta">${this.esc(row.designation)}</div>` : ""}
              </div>
            </div>`,
          )
          .join("")
      : `<div class="so-org-block__empty">${__("No Slots defined for this heading.")}</div>`;

    const secondaryHtml = node.secondary_parents.length
      ? `<div class="so-org-block__secondary">${__("Additional reporting from:")} ${node.secondary_parents.map((parent) => this.esc(`${parent.group} — ${parent.shift}`)).join(", ")}</div>`
      : "";

    return `
      <div class="so-org-block ${node.cyclic ? "is-cyclic" : ""}" data-org-block-key="${this.esc(block.key)}">
        <div class="so-org-block__header">
          <div class="so-org-block__heading">${this.esc(block.group)}</div>
          <div class="so-org-block__shift">${this.esc(block.shift)}</div>
        </div>
        <div class="so-org-block__body">${rowsHtml}</div>
        ${secondaryHtml}
      </div>
    `;
  }

  reporting_matrix_html(layout, matrixIndex) {
    const cols = Math.max(layout.branches.length, 1);
    const columnWidth = 360;
    const columnGap = 36;
    const connectorWidth = cols * columnWidth + Math.max(0, cols - 1) * columnGap;
    const rootInset = columnWidth / 2;
    const branchSpineInset = 18;

    // A branch with zero descendant rows (e.g. "Engineering" reporting
    // straight to the root, nothing below it) shouldn't draw *any* "drops
    // down further" connector - the old code drew one unconditionally for
    // every branch, producing a stub hanging off branches that connect to
    // nothing. Same idea per-row below: a branch's spine should only cover
    // rows up to and including its own last row with a node in it, not the
    // full height of every level row that happens to exist for *other*
    // branches.
    const lastRowIndexByBranch = new Map();
    layout.branches.forEach((branch) => {
      let last = -1;
      layout.rowDefs.forEach((row, idx) => {
        if (layout.branchRows.get(branch.key)?.has(row.group_key)) last = idx;
      });
      lastRowIndexByBranch.set(branch.key, last);
    });

    const branchRow = layout.branches
      .map((branch) => {
        const hasDescendants = lastRowIndexByBranch.get(branch.key) >= 0;
        return `
        <div class="so-org-grid__cell so-org-grid__cell--branch${hasDescendants ? " has-descendants" : ""}" style="--branch-spine-x:${branchSpineInset}px;">
          ${this.plan_block_html(this.reporting_present_node(branch))}
        </div>`;
      })
      .join("");

    const levelRows = layout.rowDefs
      .map((row, rowIndex) => {
        const guides = layout.branches
          .map((branch, index) => {
            const lastIdx = lastRowIndexByBranch.get(branch.key);
            if (lastIdx < 0 || rowIndex > lastIdx) return "";
            const spineX = index * (columnWidth + columnGap) + branchSpineInset;
            const isTerminal = rowIndex === lastIdx;
            return `<span class="so-org-descendants__row-spine${isTerminal ? " is-terminal" : ""}" style="left:${spineX}px"></span>`;
          })
          .join("");

        const cells = layout.branches
          .map((branch) => {
            const node = layout.branchRows.get(branch.key)?.get(row.group_key);
            return `
                <div class="so-org-grid__cell ${node ? "has-node" : "is-empty"}" style="--branch-spine-x:${branchSpineInset}px;">
                  ${node ? '<div class="so-org-grid__cell-connector"></div>' : ""}
                  ${node ? this.plan_block_html(this.reporting_present_node(node)) : '<div class="so-org-grid__placeholder"></div>'}
                </div>`;
          })
          .join("");

        return `
        <div class="so-org-grid__row so-org-grid__row--level" style="grid-template-columns: repeat(${cols}, ${columnWidth}px); column-gap:${columnGap}px;">
          <div class="so-org-grid__row-guides">${guides}</div>
          ${cells}
        </div>`;
      })
      .join("");

    const branchGuides = layout.branches
      .map((branch, index) => {
        if (lastRowIndexByBranch.get(branch.key) < 0) return "";
        const columnLeft = index * (columnWidth + columnGap);
        const centreX = columnLeft + columnWidth / 2;
        const spineX = columnLeft + branchSpineInset;
        return `<span class="so-org-descendants__branch-start" style="left:${spineX}px; width:${centreX - spineX}px"></span>`;
      })
      .join("");

    return `
      <div class="so-org-matrix" data-matrix-index="${matrixIndex}">
        <div class="so-org-root-row">${this.plan_block_html(this.reporting_present_node(layout.root))}</div>

        <div class="so-org-root-links" style="width:${connectorWidth}px; --root-line-inset:${rootInset}px;">
          <div class="so-org-root-links__trunk"></div>
          <div class="so-org-root-links__line"></div>
          ${layout.branches.map((branch, index) => `<span class="so-org-root-links__drop" style="left:${index * (columnWidth + columnGap) + columnWidth / 2}px"></span>`).join("")}
        </div>

        <div class="so-org-grid">
          <div class="so-org-grid__row so-org-grid__row--branches" style="grid-template-columns: repeat(${cols}, ${columnWidth}px); column-gap:${columnGap}px;">
            ${branchRow}
          </div>
          ${layout.rowDefs.length ? `<div class="so-org-descendants" style="width:${connectorWidth}px;"><div class="so-org-descendants__guides">${branchGuides}</div>${levelRows}</div>` : ""}
        </div>
      </div>
    `;
  }

  render_reporting() {
    const $wrapper = this.$main.find(".so-reporting");
    const lineCount = this.state.reporting_lines.length;
    const layout = this.build_reporting_layout();

    const matricesHtml = layout.matrices.length
      ? layout.matrices.map((matrix, index) => this.reporting_matrix_html(matrix, index)).join("")
      : "";

    const standaloneHtml = layout.standalone.length
      ? `<div class="so-org-unlinked"><div class="so-org-unlinked__title">${__("Unlinked Headings")}</div><div class="so-org-unlinked__list">${layout.standalone.map((node) => this.plan_block_html(this.reporting_present_node(node))).join("")}</div></div>`
      : "";

    $wrapper.html(`
      <div>
        <div class="so-report-toolbar">
          <button class="btn btn-sm btn-primary" data-report-action="add">${__("Add Reporting Line")}</button>
          <button class="btn btn-sm btn-default" data-report-action="manage" ${lineCount ? "" : "disabled"}>${__("Manage Reporting Lines")}</button>
          <span class="so-report-status">${lineCount} ${__("reporting line(s)")}</span>
        </div>
        <div class="so-org-forest-scroll">
          <div class="so-org-forest">
            ${matricesHtml || `<div class="so-empty">${__("Add group headings and reporting lines to build the diagram.")}</div>`}
            ${standaloneHtml}
          </div>
        </div>
      </div>
    `);

    $wrapper.find('[data-report-action="add"]').on("click", () => this.add_line_dialog());
    $wrapper.find('[data-report-action="manage"]').on("click", () => this.manage_lines());
  }

  endpoint_label(endpoint) {
    return endpoint.scope === "Shift" && endpoint.shift ? `${endpoint.group} — ${endpoint.shift}` : endpoint.group;
  }

  line_ep(line, prefix) {
    return {
      group_key: line[`${prefix}_group_key`] || "",
      group: line[`${prefix}_group`] || "",
      scope: line[`${prefix}_scope`] || "Heading",
      shift: line[`${prefix}_shift`] || "",
    };
  }

  shift_select_options() {
    return ["", "Shift A", "Shift B", "Shift C", "Shift D", "Shift E", "Shift F", "Shift G", "Shift H", "Shift I", "Shift J", "Shift K", "Shift L", "Shift M", "Shift N", "Shift O", "Shift P", "Shift Q", "Shift R", "Shift S", "Shift T", "Day Shift", "Night Shift"];
  }

  endpoint_fields(prefix) {
    const groups = (this.state.groups || []).filter((g) => g.group && g.group_key);
    return [
      { fieldtype: "Select", fieldname: `${prefix}_group`, label: __(prefix === "source" ? "Source Heading" : "Target Heading"), options: [""].concat(groups.map((g) => g.group)).join("\n"), reqd: 1 },
      { fieldtype: "Select", fieldname: `${prefix}_scope`, label: __(prefix === "source" ? "Source Scope" : "Target Scope"), options: "Heading\nShift", default: "Heading", reqd: 1 },
      { fieldtype: "Select", fieldname: `${prefix}_shift`, label: __(prefix === "source" ? "Source Shift" : "Target Shift"), options: this.shift_select_options().join("\n") },
    ];
  }

  add_line_dialog() {
    const groups = (this.state.groups || []).filter((g) => g.group && g.group_key);
    if (groups.length < 1) {
      frappe.msgprint(__("Add at least one Group Heading first."));
      return;
    }

    const groupKeyByName = (name) => groups.find((g) => g.group === name)?.group_key || "";

    const dialog = new frappe.ui.Dialog({
      title: __("Add Reporting Line"),
      fields: [
        ...this.endpoint_fields("source"),
        { fieldtype: "Column Break" },
        ...this.endpoint_fields("target"),
        { fieldtype: "Section Break" },
        { fieldtype: "Select", fieldname: "line_type", label: __("Line Type"), options: "Solid\nDotted\nAdvisory\nFunctional", default: "Solid", reqd: 1 },
        { fieldtype: "Data", fieldname: "label", label: __("Label") },
        { fieldtype: "Column Break" },
        { fieldtype: "Select", fieldname: "source_anchor", label: __("Source Anchor"), options: "Auto\nTop\nRight\nBottom\nLeft", default: "Auto" },
        { fieldtype: "Select", fieldname: "target_anchor", label: __("Target Anchor"), options: "Auto\nTop\nRight\nBottom\nLeft", default: "Auto" },
      ],
      primary_action_label: __("Create"),
      primary_action: (values) => {
        const sourceGroupKey = groupKeyByName(values.source_group);
        const targetGroupKey = groupKeyByName(values.target_group);

        if (!sourceGroupKey || !targetGroupKey) {
          frappe.msgprint(__("Both a source and a target heading are required."));
          return;
        }
        if (
          sourceGroupKey === targetGroupKey &&
          values.source_scope === values.target_scope &&
          (values.source_shift || "") === (values.target_shift || "")
        ) {
          frappe.msgprint(__("A reporting line cannot connect an endpoint to itself."));
          return;
        }

        this.state.reporting_lines.push({
          source_group_key: sourceGroupKey,
          source_group: values.source_group,
          source_scope: values.source_scope,
          source_shift: values.source_scope === "Shift" ? values.source_shift || "" : "",
          target_group_key: targetGroupKey,
          target_group: values.target_group,
          target_scope: values.target_scope,
          target_shift: values.target_scope === "Shift" ? values.target_shift || "" : "",
          line_type: values.line_type || "Solid",
          label: values.label || "",
          source_anchor: values.source_anchor || "Auto",
          target_anchor: values.target_anchor || "Auto",
          line_order: this.state.reporting_lines.length + 1,
        });

        dialog.hide();
        this.mark_dirty();
        this.render_reporting();
      },
    });

    dialog.show();
  }

  async manage_lines() {
    const lines = this.state.reporting_lines;
    if (!lines.length) return;

    const labels = lines.map(
      (line, index) =>
        `${index + 1}. ${this.endpoint_label(this.line_ep(line, "source"))} → ${this.endpoint_label(this.line_ep(line, "target"))}${line.label ? ` — ${line.label}` : ""}`,
    );

    const dialog = new frappe.ui.Dialog({
      title: __("Manage Reporting Lines"),
      fields: [{ fieldtype: "Select", fieldname: "line", label: __("Reporting Line"), options: labels.join("\n"), default: labels[0], reqd: 1 }],
      primary_action_label: __("Close"),
      primary_action: () => dialog.hide(),
    });

    dialog.show();

    const $delete = $(`<button class="btn btn-danger btn-sm">${__("Delete Selected")}</button>`).on("click", async () => {
      const index = labels.indexOf(dialog.get_value("line"));
      if (index < 0) return;
      const confirmed = await this.confirm(__("Delete this reporting line?"));
      if (!confirmed) return;
      lines.splice(index, 1);
      dialog.hide();
      this.mark_dirty();
      this.render_reporting();
    });

    dialog.$wrapper.find(".modal-footer").prepend($delete);
  }

  // ---------------------------------------------------------------------
  // Save / delete / misc
  // ---------------------------------------------------------------------

  async save() {
    const validationError = this.validate();
    if (validationError) {
      frappe.msgprint({ title: __("Cannot Save"), indicator: "red", message: validationError });
      return;
    }

    const response = await frappe.call({
      method: `${SP_API}.save_plan`,
      args: { data: JSON.stringify(this.state) },
      freeze: true,
      freeze_message: __("Saving Site Plan..."),
    });

    this.state = { ...this.blank_state(), ...(response.message.plan || {}) };
    this.dirty = false;
    await this.sync_controls();
    this.dirty = false;
    this.render_all();

    frappe.show_alert({ message: __("Site Plan saved."), indicator: "green" });
  }

  validate() {
    if (!this.state.plan_name) return __("Plan Name is required.");
    if (!this.state.effective_from) return __("Effective From is required.");
    if (this.state.effective_until && moment(this.state.effective_until).isBefore(this.state.effective_from, "day")) {
      return __("Effective Until cannot be before Effective From.");
    }
    return "";
  }

  async delete_plan() {
    if (!this.state.name) return;
    frappe.confirm(__("Delete {0}?", [this.state.name]), async () => {
      await frappe.call({ method: `${SP_API}.delete_plan`, args: { name: this.state.name } });
      await this.new_plan();
    });
  }

  export_excel() {
    if (!this.state.name) {
      frappe.msgprint(__("Save the Site Plan before exporting."));
      return;
    }
    if (this.dirty) {
      frappe.msgprint(__("Save the Site Plan so the export includes the latest changes."));
      return;
    }
    const url = `/api/method/${SITE_PLAN_PY}.export_site_plan_excel?name=${encodeURIComponent(this.state.name)}`;
    window.open(url, "_blank");
  }

  async ensure_html2canvas() {
    if (window.html2canvas) return;
    await frappe.require("/assets/ir/js/vendor/html2canvas.min.js");
    if (!window.html2canvas) {
      throw new Error(__("html2canvas could not be loaded."));
    }
  }

  // A clone rendered off-screen in the *live* document (e.g. left:-20000px)
  // gets laid out by html2canvas relative to that huge negative offset -
  // it tries to rasterise the whole span between there and the origin,
  // which is either extremely slow or effectively hangs. An iframe sidesteps
  // this entirely: its own document has its own 0,0 origin regardless of
  // where the iframe itself sits on the parent page.
  create_capture_frame() {
    const iframe = document.createElement("iframe");
    iframe.setAttribute("aria-hidden", "true");
    Object.assign(iframe.style, {
      position: "fixed",
      left: "-20000px",
      top: "0",
      width: "4000px",
      height: "3000px",
      border: "0",
      opacity: "0",
      pointerEvents: "none",
    });
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument;
    doc.open();
    doc.write("<!doctype html><html><head></head><body></body></html>");
    doc.close();
    doc.body.style.margin = "0";
    doc.body.style.background = "#ffffff";
    return { iframe, doc };
  }

  // Colours computed from ir_ui.css's color-mix() rules don't serialise back
  // from getComputedStyle() as plain rgb()/rgba() the way a normal declared
  // colour would - this Chromium reports them back as CSS Color 4's
  // `color(srgb r g b)` form (components 0-1), which html2canvas 1.4.1's own
  // (much older) CSS parser doesn't understand either, throwing "unsupported
  // color function". A canvas fillStyle round-trip does *not* normalise this
  // form back to rgb() (tried - it just echoes color(srgb ...) unchanged),
  // so it's parsed directly here instead: the three components are already
  // plain 0-1 sRGB, so this is just *255 and round, no colour-engine needed.
  normalize_color(value) {
    if (!value || value === "none" || value === "transparent") return value;
    const m = /^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/.exec(value);
    if (!m) return value;
    const [r, g, b] = [m[1], m[2], m[3]].map((n) => Math.round(parseFloat(n) * 255));
    const a = m[4] !== undefined ? parseFloat(m[4]) : 1;
    return a < 1 ? `rgba(${r}, ${g}, ${b}, ${a})` : `rgb(${r}, ${g}, ${b})`;
  }

  // Frappe's theme CSS variables key off `[data-theme]` on <html> - flipping
  // it to "light" for the duration of `fn` (always restored, even on error)
  // makes every getComputedStyle() call inside `fn` resolve exactly as it
  // would in light mode, with no separate hardcoded export palette to keep
  // in sync with the real one.
  with_forced_light_theme(fn) {
    const root = document.documentElement;
    const had = root.hasAttribute("data-theme");
    const original = root.getAttribute("data-theme");
    root.setAttribute("data-theme", "light");
    try {
      return fn();
    } finally {
      if (had) root.setAttribute("data-theme", original);
      else root.removeAttribute("data-theme");
    }
  }

  // getComputedStyle() on the *live* elements has already resolved every
  // class rule (color-mix() included) - baking those resolved values in as
  // inline styles on the clone reproduces exactly what's on screen without
  // html2canvas ever needing to parse ir_ui.css (or any class rule) at all.
  // box-shadow is deliberately dropped rather than baked - a color-mix()
  // shadow colour hits the exact same unsupported-function wall, and a
  // missing drop-shadow is a trivial cosmetic loss compared to that.
  bake_computed_styles(sourceRoot, cloneRoot) {
    const COLOR_PROPS = ["backgroundColor", "color", "borderTopColor", "borderRightColor", "borderBottomColor", "borderLeftColor"];
    const PLAIN_PROPS = [
      "backgroundImage",
      "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
      "borderTopStyle", "borderRightStyle", "borderBottomStyle", "borderLeftStyle",
      "borderTopLeftRadius", "borderTopRightRadius", "borderBottomLeftRadius", "borderBottomRightRadius",
      "fontWeight", "fontSize", "fontFamily", "lineHeight", "letterSpacing", "textTransform",
      "padding", "margin", "display", "position", "top", "left", "right", "bottom",
      "width", "height", "minWidth", "minHeight", "textAlign", "opacity", "whiteSpace", "overflow",
      "flexDirection", "flexWrap", "flex", "alignItems", "justifyContent", "alignSelf", "justifySelf",
      "gap", "rowGap", "columnGap", "zIndex", "boxSizing",
      // The diagram leans heavily on CSS Grid (group headings, person-row's
      // own two-column layout, the reporting matrix) - without these too,
      // every grid child collapses into a single implicit column/row and
      // rows visibly overlap.
      "gridTemplateColumns", "gridTemplateRows", "gridTemplateAreas",
      "gridColumn", "gridRow", "gridArea", "gridAutoFlow", "gridAutoColumns", "gridAutoRows",
      // The "Unlinked Headings" masonry layout uses CSS multi-column
      // (column-width) - without these too, that declaration is silently
      // dropped in the capture iframe (no stylesheet there to fall back on)
      // and every block collapses back into a single stacked column.
      "columnWidth", "columnCount", "breakInside",
    ];
    const srcEls = [sourceRoot, ...sourceRoot.querySelectorAll("*")];
    const cloneEls = [cloneRoot, ...cloneRoot.querySelectorAll("*")];
    srcEls.forEach((srcEl, i) => {
      const cloneEl = cloneEls[i];
      if (!cloneEl || !cloneEl.style) return;
      const computed = window.getComputedStyle(srcEl);
      let css = "box-shadow:none;";
      for (const prop of COLOR_PROPS) {
        const value = this.normalize_color(computed[prop]);
        if (value) css += `${prop.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase())}:${value};`;
      }
      for (const prop of PLAIN_PROPS) {
        const value = computed[prop];
        if (value) css += `${prop.replace(/[A-Z]/g, (m) => "-" + m.toLowerCase())}:${value};`;
      }
      cloneEl.style.cssText = css;
    });
  }

  async export_reporting_png() {
    const $forest = this.$main.find(".so-org-forest");
    if (!$forest.length || !$forest.find(".so-org-block").length) {
      frappe.msgprint(__("Add Group Headings and Reporting Lines before exporting a diagram."));
      return;
    }

    let iframe;
    try {
      await this.ensure_html2canvas();

      const frame = this.create_capture_frame();
      iframe = frame.iframe;
      const doc = frame.doc;

      const wrapper = doc.createElement("div");
      wrapper.style.cssText = "display:inline-block; padding:24px; background:#fff;";

      const title = doc.createElement("div");
      title.style.cssText = "font:700 20px/1.4 Arial, sans-serif; margin-bottom:14px; color:#1a1a1a;";
      title.textContent = this.png_title();
      wrapper.appendChild(title);

      const forestClone = $forest.get(0).cloneNode(true);
      // The exported file is meant to be shared/printed outside Desk, so it
      // should look the same regardless of whichever theme the exporting
      // user happens to have their own Desk set to - only the live HTML
      // page should ever render dark.
      this.with_forced_light_theme(() => this.bake_computed_styles($forest.get(0), forestClone));
      wrapper.appendChild(forestClone);
      doc.body.appendChild(wrapper);

      const canvas = await window.html2canvas(wrapper, {
        backgroundColor: "#ffffff",
        scale: 2,
        useCORS: true,
        logging: false,
        windowWidth: 4000,
        windowHeight: 3000,
      });
      const blob = await new Promise((resolve, reject) =>
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error(__("PNG creation failed.")))), "image/png")
      );

      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${this.png_filename()}.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      frappe.msgprint({ title: __("Export failed"), message: error.message, indicator: "red" });
    } finally {
      if (iframe) iframe.remove();
    }
  }

  png_title() {
    const name = this.state.plan_name || this.state.name || "Site Plan";
    const eff = this.state.effective_from ? frappe.datetime.str_to_user(this.state.effective_from) : "";
    return eff ? `${name} — Reporting Structure (Effective ${eff})` : `${name} — Reporting Structure`;
  }

  png_filename() {
    return `Site-Plan-${this.slug(this.state.plan_name || this.state.name)}-Reporting-Structure`;
  }

  slug(value) {
    return String(value || "site-plan").trim().replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }

  mark_dirty() {
    this.dirty = true;
    this.render_save_state();
  }

  render_save_state() {
    this.$main.find(".sdm-save-state").html(
      this.dirty ? `<span class="sdm-dirty">${__("Unsaved changes")}</span>` : `<span class="text-muted">${__("Saved")}</span>`,
    );
  }

  confirm(message) {
    return new Promise((resolve) => frappe.confirm(message, () => resolve(true), () => resolve(false)));
  }

  esc(v) {
    return String(v ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  attr(v) {
    return this.esc(v);
  }

  error(error) {
    console.error(error);
    frappe.msgprint({ title: __("Site Plan Designer"), indicator: "red", message: error?.message || String(error) });
  }
}
