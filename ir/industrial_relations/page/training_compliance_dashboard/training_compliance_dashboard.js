// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.pages["training-compliance-dashboard"].on_page_load = function (wrapper) {
  new TrainingComplianceDashboard(wrapper);
};

class TrainingComplianceDashboard {
  constructor(wrapper) {
    this.wrapper = wrapper;
    this.page = frappe.ui.make_app_page({
      parent: wrapper,
      title: __("Training Compliance Dashboard"),
      single_column: true,
    });
    this.build();
  }

  build() {
    this.page.main.addClass("tcd-page");
    this.ensure_css();
    // Reuses the Training Matrix report's own .tm-card/.tm-green/.tm-yellow/
    // .tm-red cell styling for the "Training Matrix" view below, so a
    // record looks identical whether you're looking at the report or here.
    frappe.require("/assets/ir/css/ir_ui.css");

    this.active_view = "compliance";

    this.$root = $("<div class='tcd-root'></div>").appendTo(this.page.main);
    this.build_filters();
    this.build_view_switcher();
    this.$content = $("<div class='tcd-content'></div>").appendTo(this.$root);
    this.render_empty();

    this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");

    // A dropdown, not a single button - matches the same "Neutral Format"
    // group used on the Training Matrix report itself, so future export
    // formats show up here too without any further changes.
    this.page.add_inner_button(
      __("Neutral Format"),
      () => this.download_xlsx(),
      __("Download in .xlsx Format"),
    );

    this.refresh();
  }

  build_filters() {
    this.$filters = $(`
      <section class="tcd-filter-card">
        <div class="tcd-filter-grid">
          <div data-filter="branches"></div>
          <div data-filter="area_setup"></div>
          <div data-filter="designation"></div>
          <div data-filter="induction_type"></div>
          <div data-filter="employee_status"></div>
        </div>
      </section>
    `).appendTo(this.$root);

    this.filters = {
      branches: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="branches"]'),
        df: {
          fieldtype: "MultiSelectList",
          fieldname: "branches",
          label: __("Branch"),
          get_data: (txt) => frappe.db.get_link_options("Branch", txt),
          change: () => this.refresh_debounced(),
        },
        render_input: true,
      }),
      area_setup: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="area_setup"]'),
        df: {
          fieldtype: "Link",
          fieldname: "area_setup",
          label: __("Area Setup"),
          options: "Area Setup",
          change: () => this.refresh_debounced(),
        },
        render_input: true,
      }),
      designation: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="designation"]'),
        df: {
          fieldtype: "Link",
          fieldname: "designation",
          label: __("Designation"),
          options: "Designation",
          change: () => this.refresh_debounced(),
        },
        render_input: true,
      }),
      induction_type: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="induction_type"]'),
        df: {
          fieldtype: "Select",
          fieldname: "induction_type",
          label: __("Induction Type"),
          options: ["", "Training", "Licence", "Qualification", "Authorisation"],
          change: () => this.refresh_debounced(),
        },
        render_input: true,
      }),
      employee_status: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="employee_status"]'),
        df: {
          fieldtype: "Select",
          fieldname: "employee_status",
          label: __("Employee Status"),
          options: ["All", "Active", "Inactive", "Suspended", "Left"],
          default: "Active",
          change: () => this.refresh_debounced(),
        },
        render_input: true,
      }),
    };

    this.refresh_debounced = frappe.utils.debounce(() => this.refresh(), 350);
  }

  build_view_switcher() {
    this.$views = $(`
      <div class="tcd-view-switch">
        <button class="tcd-view-tab is-active" data-view="compliance">
          ${__("Compliance Overview")}
        </button>
        <button class="tcd-view-tab" data-view="matrix">
          ${__("Training Matrix")}
        </button>
      </div>
    `).appendTo(this.$root);

    this.$views.on("click", ".tcd-view-tab", (e) => {
      const view = $(e.currentTarget).data("view");
      if (view === this.active_view) return;

      this.active_view = view;
      this.$views.find(".tcd-view-tab").removeClass("is-active");
      $(e.currentTarget).addClass("is-active");
      this.refresh();
    });
  }

  get_filters() {
    const values = Object.fromEntries(
      Object.entries(this.filters).map(([key, control]) => [key, control.get_value()]),
    );
    // branches is an array; the server-side filter reader accepts either a
    // real list or a JSON-encoded string, so send it the same way
    // hr_exception_report.js already sends its own "branches" filter.
    values.branches = JSON.stringify(values.branches || []);
    return values;
  }

  render_empty() {
    this.$content.html(`<div class="tcd-empty text-muted">${__("Loading...")}</div>`);
  }

  async refresh() {
    if (this.active_view === "matrix") {
      await this.refresh_matrix();
    } else {
      await this.refresh_compliance();
    }
  }

  async refresh_compliance() {
    let response;

    try {
      response = await frappe.call({
        method:
          "ir.industrial_relations.report.training_matrix.training_matrix.get_compliance_summary",
        args: { filters: this.get_filters() },
      });
    } catch (err) {
      console.error("Failed to load Training Compliance summary:", err);
      this.$content.html(
        `<div class="tcd-empty text-muted">${__("Could not load compliance data.")}</div>`,
      );
      return;
    }

    const message = response.message || { categories: [], scope: {} };
    this.last_categories = message.categories || [];
    this.last_scope = message.scope || {};
    this.render_bars();
  }

  async refresh_matrix() {
    this.$content.html(`<div class="tcd-empty text-muted">${__("Loading...")}</div>`);

    let response;

    try {
      response = await frappe.call({
        method:
          "ir.industrial_relations.report.training_matrix.training_matrix.get_training_matrix_payload",
        args: { filters: this.get_filters() },
      });
    } catch (err) {
      console.error("Failed to load Training Matrix:", err);
      this.$content.html(
        `<div class="tcd-empty text-muted">${__("Could not load the Training Matrix.")}</div>`,
      );
      return;
    }

    const message = response.message || { columns: [], data: [] };
    this.render_matrix(message.columns || [], message.data || []);
  }

  render_bars() {
    const categories = this.last_categories || [];
    const scope = this.last_scope || {};

    if (!categories.length || !(scope.employees > 0)) {
      this.$content.html(
        `<div class="tcd-empty text-muted">${__("No employees match the current filters.")}</div>`,
      );
      return;
    }

    if (!this.expanded_categories) this.expanded_categories = new Set();

    const rows = categories
      .map((cat) => {
        const items = cat.items || [];
        const expandable = items.length > 0;
        const expanded = this.expanded_categories.has(cat.label);

        const toggle = expandable
          ? `<span class="tcd-row__toggle">${expanded ? "▾" : "▸"}</span>`
          : `<span class="tcd-row__toggle tcd-row__toggle--spacer"></span>`;

        const sub_rows = expanded
          ? items.map((item) => this.render_bar_row(item, { sub: true })).join("")
          : "";

        const count_badge = expandable
          ? `<span class="tcd-row__count">${items.length}</span>`
          : "";

        return `
          <div class="tcd-group">
            <div class="tcd-row ${expandable ? "tcd-row--expandable" : ""}" data-category="${frappe.utils.escape_html(cat.label)}">
              ${toggle}
              ${this.render_bar_row(cat, { count_badge })}
            </div>
            ${sub_rows ? `<div class="tcd-subrows">${sub_rows}</div>` : ""}
          </div>
        `;
      })
      .join("");

    this.$content.html(`
      <div class="tcd-chart">
        <div class="tcd-chart__scope text-muted">
          ${__("{0} employee(s) in scope", [scope.employees])}
          <span class="tcd-chart__hint">${__("Click a category to see each specific training")}</span>
        </div>
        ${rows}
        <div class="tcd-axis">
          <span>0%</span>
          <span class="tcd-axis__target">${__("100% target")}</span>
        </div>
      </div>
    `);

    this.$content.find(".tcd-row--expandable").on("click", (e) => {
      const label = $(e.currentTarget).data("category");
      if (this.expanded_categories.has(label)) {
        this.expanded_categories.delete(label);
      } else {
        this.expanded_categories.add(label);
      }
      this.render_bars();
    });
  }

  render_bar_row(cat, { sub = false, count_badge = "" } = {}) {
    const esc = frappe.utils.escape_html;
    const band = this.band_for(cat.pct);
    const detail =
      cat.complete > cat.target
        ? __("{0} trained | target {1} | {2} above target", [
            cat.complete,
            cat.target,
            cat.complete - cat.target,
          ])
        : __("{0}/{1} complete | {2} outstanding", [cat.complete, cat.target, cat.outstanding]);

    return `
      <div class="tcd-bar-row ${sub ? "tcd-bar-row--sub" : ""}">
        <div class="tcd-row__label">${esc(__(cat.label))}${count_badge}</div>
        <div class="tcd-row__track">
          <div class="tcd-row__bar ${band}" style="width: ${Math.min(cat.pct, 100)}%;"></div>
          <div class="tcd-row__target-line"></div>
        </div>
        <div class="tcd-row__pct">${cat.pct.toFixed(1)}%</div>
        <div class="tcd-row__detail">${esc(detail)}</div>
      </div>
    `;
  }

  render_matrix(columns, data) {
    if (!data.length) {
      this.$content.html(
        `<div class="tcd-empty text-muted">${__("No employees match the current filters.")}</div>`,
      );
      return;
    }

    const esc = frappe.utils.escape_html;
    const export_columns = columns.filter((c) => c.fieldname);

    const head = export_columns
      .map((col) => `<th>${esc(col.label || col.fieldname)}</th>`)
      .join("");

    const body = data
      .map((row) => {
        const cells = export_columns
          .map((col) => this.render_matrix_cell(col, row))
          .join("");
        return `<tr>${cells}</tr>`;
      })
      .join("");

    this.$content.html(`
      <div class="tcd-matrix-scroll">
        <table class="tcd-matrix-table">
          <thead><tr>${head}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    `);
  }

  render_matrix_cell(col, row) {
    const esc = frappe.utils.escape_html;
    const fieldname = col.fieldname;
    const value = row[fieldname];

    if (fieldname === "tracking" && value) {
      const url = frappe.utils.get_form_link("Employee Induction Tracking", value);
      return `<td><a href="${url}">${esc(value)}</a></td>`;
    }

    if (fieldname === "employee" && value) {
      const url = frappe.utils.get_form_link("Employee", value);
      return `<td><a href="${url}">${esc(value)}</a></td>`;
    }

    if (!fieldname.startsWith("ind_")) {
      return `<td>${value == null ? "" : esc(String(value))}</td>`;
    }

    if (!value) return `<td></td>`;

    let obj;
    try {
      obj = typeof value === "string" ? JSON.parse(value) : value;
    } catch (e) {
      return `<td>${esc(String(value))}</td>`;
    }

    const status = (obj.status || "red").toLowerCase();
    const expiry = obj.expiry || null;
    const days = obj.days === 0 || obj.days ? obj.days : null;

    const status_label = !expiry
      ? __("Not trained")
      : status === "green"
        ? __("Valid")
        : status === "yellow"
          ? __("Expiring")
          : typeof days === "number" && days < 0
            ? __("Expired")
            : __("Attention");

    const main_line = !expiry
      ? __("No expiry on record")
      : typeof days === "number"
        ? `${__("Expires")}: ${expiry} • ${days < 0 ? `${Math.abs(days)}d ${__("overdue")}` : `${days}d ${__("left")}`}`
        : `${__("Expires")}: ${expiry}`;

    return `
      <td>
        <div class="tm-card tm-${esc(status)}">
          <div class="tm-card__top">
            <div class="tm-card__left">
              <span class="tm-dot"></span>
              <span class="tm-status">${esc(status_label)}</span>
            </div>
          </div>
          <div class="tm-main">${esc(main_line)}</div>
        </div>
      </td>
    `;
  }

  band_for(pct) {
    if (pct < 60) return "tcd-bar-red";
    if (pct < 90) return "tcd-bar-amber";
    if (pct < 100) return "tcd-bar-light-green";
    return "tcd-bar-green";
  }

  async download_xlsx() {
    let response;

    try {
      response = await frappe.call({
        method:
          "ir.industrial_relations.report.training_matrix.training_matrix.download_training_matrix_excel",
        args: { filters: this.get_filters() },
        freeze: true,
        freeze_message: __("Building Excel file..."),
      });
    } catch (err) {
      console.error("Failed to build Training Matrix Excel export:", err);
      return;
    }

    const message = response.message;
    if (!message || !message.content) return;

    const filename = message.filename || "training_matrix.xlsx";
    const mime =
      message.type || "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

    this.download_base64_file(message.content, filename, mime);
  }

  download_base64_file(base64_content, filename, mime_type) {
    const byte_chars = atob(base64_content);
    const byte_numbers = new Array(byte_chars.length);

    for (let i = 0; i < byte_chars.length; i++) {
      byte_numbers[i] = byte_chars.charCodeAt(i);
    }

    const byte_array = new Uint8Array(byte_numbers);
    const blob = new Blob([byte_array], { type: mime_type });
    const url = window.URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = url;
    link.download = filename;

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    window.URL.revokeObjectURL(url);
  }

  ensure_css() {
    if (document.getElementById("tcd-css")) return;

    const style = document.createElement("style");
    style.id = "tcd-css";
    style.textContent = `
      .tcd-filter-card {
        background: var(--card-bg, var(--bg-color, #fff));
        border: 1px solid var(--border-color, #d1d8dd);
        border-radius: 10px;
        padding: 12px 16px;
        margin-bottom: 16px;
      }

      .tcd-filter-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 12px;
      }

      .tcd-empty {
        padding: 40px 0;
        text-align: center;
      }

      .tcd-chart {
        background: var(--card-bg, var(--bg-color, #fff));
        border: 1px solid var(--border-color, #d1d8dd);
        border-radius: 10px;
        padding: 20px 24px 12px;
      }

      .tcd-chart__scope {
        font-size: 12px;
        margin-bottom: 14px;
        display: flex;
        align-items: baseline;
        gap: 10px;
      }

      .tcd-chart__hint {
        font-size: 11px;
        opacity: 0.7;
      }

      .tcd-group + .tcd-group {
        border-top: 1px solid var(--border-color, #ebeef1);
      }

      .tcd-row {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 10px 0;
      }

      .tcd-row--expandable {
        cursor: pointer;
      }

      .tcd-row__toggle {
        flex: 0 0 14px;
        font-size: 11px;
        opacity: 0.6;
      }

      .tcd-row__toggle--spacer {
        visibility: hidden;
      }

      .tcd-row__count {
        margin-left: 6px;
        font-size: 11px;
        font-weight: 600;
        opacity: 0.65;
      }

      .tcd-bar-row {
        display: grid;
        grid-template-columns: 220px minmax(200px, 1fr) 64px 220px;
        align-items: center;
        gap: 14px;
        flex: 1 1 auto;
        min-width: 0;
      }

      .tcd-subrows {
        padding-left: 20px;
      }

      .tcd-bar-row--sub {
        padding: 5px 0;
      }

      .tcd-bar-row--sub .tcd-row__label {
        font-weight: 500;
        font-size: 12px;
        opacity: 0.85;
      }

      .tcd-bar-row--sub .tcd-row__track {
        height: 12px;
      }

      .tcd-row__label {
        font-weight: 600;
        font-size: 13px;
      }

      .tcd-row__track {
        position: relative;
        height: 18px;
        background: var(--control-bg, #eceef0);
        border-radius: 4px;
        overflow: visible;
      }

      .tcd-row__bar {
        position: absolute;
        top: 0;
        left: 0;
        height: 100%;
        border-radius: 4px;
        transition: width 0.3s ease;
      }

      .tcd-row__target-line {
        position: absolute;
        top: -3px;
        bottom: -3px;
        right: 0;
        width: 0;
        border-right: 2px dashed var(--text-muted, #8d99a6);
      }

      .tcd-row__pct {
        font-weight: 700;
        font-size: 13px;
        text-align: right;
      }

      .tcd-row__detail {
        font-size: 12px;
        color: var(--text-muted, #6c7680);
        white-space: nowrap;
      }

      .tcd-bar-red { background: #e8463f; }
      .tcd-bar-amber { background: #eba836; }
      .tcd-bar-light-green { background: #8dcba6; }
      .tcd-bar-green { background: #2f9e58; }

      .tcd-axis {
        display: grid;
        grid-template-columns: 220px minmax(200px, 1fr) 64px 220px;
        gap: 14px;
        margin-top: 8px;
        margin-left: 20px;
        padding-top: 6px;
        border-top: 1px solid var(--border-color, #ebeef1);
        font-size: 11px;
        color: var(--text-muted, #8d99a6);
      }

      .tcd-axis span:first-child { grid-column: 2; justify-self: start; }
      .tcd-axis__target { grid-column: 2; justify-self: end; font-weight: 600; }

      .tcd-view-switch {
        display: flex;
        gap: 6px;
        margin-bottom: 16px;
      }

      .tcd-view-tab {
        border: 1px solid var(--border-color, #d1d8dd);
        background: var(--control-bg, #f4f5f6);
        border-radius: 8px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 600;
        cursor: pointer;
      }

      .tcd-view-tab.is-active {
        background: var(--btn-primary, var(--blue-500, #3b82f6));
        color: var(--btn-primary-color, #fff);
        border-color: transparent;
      }

      .tcd-matrix-scroll {
        overflow: auto;
        border: 1px solid var(--border-color, #d1d8dd);
        border-radius: 10px;
        max-height: 75vh;
      }

      .tcd-matrix-table {
        border-collapse: collapse;
        width: max-content;
        min-width: 100%;
      }

      .tcd-matrix-table th,
      .tcd-matrix-table td {
        border-right: 1px solid var(--border-color, #ebeef1);
        border-bottom: 1px solid var(--border-color, #ebeef1);
        padding: 8px;
        vertical-align: top;
        min-width: 160px;
      }

      .tcd-matrix-table th {
        position: sticky;
        top: 0;
        z-index: 2;
        background: var(--control-bg, #f4f5f6);
        font-size: 11px;
        font-weight: 800;
        text-align: left;
        white-space: nowrap;
      }
    `;
    document.head.appendChild(style);
  }
}
