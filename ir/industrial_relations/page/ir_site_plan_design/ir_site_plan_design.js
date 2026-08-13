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
      () => Promise.resolve(handler(control.get_value())).catch((error) => this.error(error)),
    );
  }

  bind_events() {
    this.$main.on("click", '[data-action="new"]', () => this.new_plan());
  }

  new_plan(render = true) {
    this.state = this.blank_state();
    this.dirty = false;
    if (render) {
      this.sync_controls();
      this.render_all();
    }
  }

  async load_plan(name) {
    const response = await frappe.call({ method: `${SP_API}.get_plan`, args: { name } });
    this.state = { ...this.blank_state(), ...(response.message || {}) };
    this.dirty = false;
    this.sync_controls();
    this.render_all();
  }

  sync_controls() {
    for (const [fieldname, control] of Object.entries(this.controls)) {
      if (fieldname === "plan") {
        control.set_value(this.state.name || "");
      } else {
        control.set_value(this.state[fieldname] ?? "");
      }
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
          <div class="so-gridwrap"><table class="so-table" data-slot-group-key="${this.esc(g.group_key)}"><tbody>
            ${rows.length ? rows.map((r) => `
              <tr data-slot-key="${this.esc(r.row_key)}">
                <td><select class="form-control" data-slot-field="row_type">
                  <option value="Designation" ${r.row_type === "Designation" ? "selected" : ""}>${__("Designation")}</option>
                  <option value="Asset" ${r.row_type === "Asset" ? "selected" : ""}>${__("Asset")}</option>
                </select></td>
                <td><select class="form-control" data-slot-field="designation">
                  <option value="">${this.esc(__("(none)"))}</option>
                  ${designationOptions.map((d) => `<option value="${this.esc(d)}" ${r.designation === d ? "selected" : ""}>${this.esc(d)}</option>`).join("")}
                </select></td>
                <td class="so-slot-category-cell" style="${r.row_type === "Asset" ? "" : "display:none"}">
                  <select class="form-control" data-slot-field="asset_category">
                    <option value="">${this.esc(__("(none)"))}</option>
                    ${categoryOptions.map((c) => `<option value="${this.esc(c)}" ${r.asset_category === c ? "selected" : ""}>${this.esc(c)}</option>`).join("")}
                  </select>
                </td>
                <td><input class="form-control" data-slot-field="row_label" value="${this.esc(r.row_label || "")}" placeholder="${__("Label")}"></td>
                <td class="so-slot-spare-cell"><label><input type="checkbox" data-slot-field="spare_swing" ${r.spare_swing ? "checked" : ""}> ${__("Spare / Swing")}</label></td>
                <td class="so-group-remove-cell"><button class="so-icon-btn" data-slot-action="remove" title="${__("Remove")}">×</button></td>
              </tr>
            `).join("") : `<tr><td colspan="6"><div class="so-empty">${__("No slots yet.")}</div></td></tr>`}
          </tbody></table></div>
          <button class="btn btn-sm btn-default" data-slot-action="add" data-group-key="${this.esc(g.group_key)}">${__("Add Slot")}</button>
        </div>`;
      })
      .join("");

    $w.html(groupsHtml);

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

    const branchRow = layout.branches
      .map(
        (branch) => `
        <div class="so-org-grid__cell so-org-grid__cell--branch" style="--branch-spine-x:${branchSpineInset}px;">
          ${this.plan_block_html(this.reporting_present_node(branch))}
        </div>`,
      )
      .join("");

    const levelRows = layout.rowDefs
      .map(
        (row) => `
        <div class="so-org-grid__row so-org-grid__row--level" style="grid-template-columns: repeat(${cols}, ${columnWidth}px); column-gap:${columnGap}px;">
          ${layout.branches
            .map((branch) => {
              const node = layout.branchRows.get(branch.key)?.get(row.group_key);
              return `
                <div class="so-org-grid__cell ${node ? "has-node" : "is-empty"}" style="--branch-spine-x:${branchSpineInset}px;">
                  ${node ? '<div class="so-org-grid__cell-connector"></div>' : ""}
                  ${node ? this.plan_block_html(this.reporting_present_node(node)) : '<div class="so-org-grid__placeholder"></div>'}
                </div>`;
            })
            .join("")}
        </div>`,
      )
      .join("");

    const branchGuides = layout.branches
      .map((branch, index) => {
        const columnLeft = index * (columnWidth + columnGap);
        const centreX = columnLeft + columnWidth / 2;
        const spineX = columnLeft + branchSpineInset;
        return `
          <span class="so-org-descendants__spine" style="left:${spineX}px"></span>
          <span class="so-org-descendants__branch-start" style="left:${spineX}px; width:${centreX - spineX}px"></span>`;
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
    this.sync_controls();
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
      this.new_plan();
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
