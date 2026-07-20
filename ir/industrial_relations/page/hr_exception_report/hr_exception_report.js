// Copyright (c) 2026, BuFf0k and contributors
// HR Excpetion Report Page

frappe.pages["hr-exception-report"].on_page_load = function (wrapper) {
  new HRExceptionReport(wrapper);
};

class HRExceptionReport {
  constructor(wrapper) {
    this.wrapper = wrapper;
    this.page = frappe.ui.make_app_page({
      parent: wrapper,
      title: __("HR Exception Report"),
      single_column: true,
    });
    this.data = null;
    this.build();
  }

  build() {
    this.page.main.addClass("her-page");
    this.$root = $("<div class='her-root'></div>").appendTo(this.page.main);
    this.build_filters();
    this.$content = $("<div class='her-content'></div>").appendTo(this.$root);
    this.render_empty();

    this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
    this.page.add_inner_button(__("Export transparent PNG"), () => this.export_png(), __("Export"));
    this.page.add_inner_button(__("Copy PNG"), () => this.copy_png(), __("Export"));

    this.initialise_defaults();
  }

  async initialise_defaults() {
    this.suppress_filter_refresh = true;
    try {
      const response = await frappe.call({
        method: "ir.industrial_relations.page.hr_exception_report.hr_exception_report.get_page_defaults",
      });
      const defaults = response.message || {};
      await this.filters.company.set_value(defaults.company || frappe.defaults.get_user_default("Company") || "");
      await this.filters.from_date.set_value(defaults.from_date || frappe.datetime.month_start(frappe.datetime.get_today()));
      await this.filters.to_date.set_value(defaults.to_date || frappe.datetime.get_today());
    } finally {
      this.suppress_filter_refresh = false;
    }
    await this.refresh();
  }

  build_filters() {
    const today = frappe.datetime.get_today();
    const month_start = frappe.datetime.month_start(today);

    this.$filters = $(`
      <section class="her-filter-card">
        <div class="her-filter-grid">
          <div data-filter="company"></div>
          <div data-filter="from_date"></div>
          <div data-filter="to_date"></div>
          <div class="her-filter-actions">
            <button class="btn btn-primary btn-sm" data-action="refresh">${__("Refresh")}</button>
          </div>
        </div>
      </section>
    `).appendTo(this.$root);

    this.filters = {
      company: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="company"]'),
        df: {
          fieldtype: "Link",
          fieldname: "company",
          label: __("Company"),
          options: "Company",
          reqd: 1,
          default: frappe.defaults.get_user_default("Company"),
          change: () => !this.suppress_filter_refresh && this.refresh_debounced(),
        },
        render_input: true,
      }),
      from_date: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="from_date"]'),
        df: {
          fieldtype: "Date",
          fieldname: "from_date",
          label: __("From Date"),
          reqd: 1,
          default: month_start,
          change: () => !this.suppress_filter_refresh && this.refresh_debounced(),
        },
        render_input: true,
      }),
      to_date: frappe.ui.form.make_control({
        parent: this.$filters.find('[data-filter="to_date"]'),
        df: {
          fieldtype: "Date",
          fieldname: "to_date",
          label: __("To Date"),
          reqd: 1,
          default: today,
          change: () => !this.suppress_filter_refresh && this.refresh_debounced(),
        },
        render_input: true,
      }),
    };

    this.$filters.on("click", '[data-action="refresh"]', () => this.refresh());
    this.refresh_debounced = frappe.utils.debounce(() => this.refresh(), 350);
  }

  get_filters() {
    return Object.fromEntries(Object.entries(this.filters).map(([key, control]) => [key, control.get_value()]));
  }

  validate_filters(filters) {
    if (!filters.company || !filters.from_date || !filters.to_date) {
      frappe.msgprint(__("Company, From Date and To Date are required."));
      return false;
    }
    if (filters.from_date > filters.to_date) {
      frappe.msgprint(__("From Date cannot be after To Date."));
      return false;
    }
    return true;
  }

  async refresh() {
    const filters = this.get_filters();
    if (!this.validate_filters(filters)) return;

    this.page.set_indicator(__("Loading"), "orange");
    this.$content.html(`<div class="her-loading">${__("Loading exception report…")}</div>`);

    try {
      const response = await frappe.call({
        method: "ir.industrial_relations.page.hr_exception_report.hr_exception_report.get_report_data",
        args: filters,
        freeze: true,
        freeze_message: __("Building HR exception report…"),
      });
      this.data = response.message;
      this.render();
      this.page.set_indicator(__("Current"), "green");
    } catch (error) {
      this.page.set_indicator(__("Error"), "red");
      this.render_error(error);
      throw error;
    }
  }

  render_empty() {
    this.$content.html(`<div class="her-empty">${__("Select filters to generate the report.")}</div>`);
  }

  render_error(error) {
    this.$content.html(`
      <div class="her-empty her-empty--error">
        <strong>${__("The report could not be generated.")}</strong>
        <div>${frappe.utils.escape_html(error?.message || __("Unknown error"))}</div>
      </div>
    `);
  }

  render() {
    const d = this.data;
    this.$content.html(`
      <div class="her-export-shell">
        <article class="her-slide her-slide--screen" data-export-target>
          ${this.render_header(d)}
          ${this.render_top_metrics(d)}
          <div class="her-body-grid">
            <div class="her-left-column">
              ${this.render_ir_panel(d)}
              ${this.render_ageing_panel(d)}
            </div>
            <div class="her-right-column">
              ${this.render_ee_panel(d.employment_equity)}
            </div>
          </div>
          ${this.render_footer(d)}
        </article>
      </div>
    `);

    this.bind_metric_clicks();
  }

  render_header(d) {
    return `
      <header class="her-slide-header">
        <div>
          <div class="her-eyebrow">${__("Human Resources & Industrial Relations")}</div>
          <h1>${__("Exception Report")}</h1>
          <div class="her-period">${frappe.utils.escape_html(d.company)} · ${this.format_date(d.from_date)} – ${this.format_date(d.to_date)}</div>
        </div>
        <div class="her-header-meta">
          <span>${__("Generated")}</span>
          <strong>${this.format_datetime(d.generated_at)}</strong>
        </div>
      </header>
    `;
  }

  render_top_metrics(d) {
    const workforce = d.workforce;
    const reasons = workforce.terminated.reasons
      .slice(0, 5)
      .map((row) => `
        <button class="her-reason" data-detail="terminated">
          <span>${frappe.utils.escape_html(row.reason)}</span><b>${row.count}</b>
        </button>`)
      .join("");

    return `
      <section class="her-top-grid">
        ${this.metric_card("new", __("New employees"), workforce.new.count, __("Joined during period"), "positive")}
        ${this.metric_card("terminated", __("Terminated employees"), workforce.terminated.count, __("Relieving date during period"), "negative")}
        <div class="her-card her-card--headcount">
          <div class="her-card-label">${__("Headcount movement")}</div>
          <div class="her-headcount-flow">
            <div><span>${__("Opening")}</span><b>${workforce.headcount.opening}</b></div>
            <i>+</i>
            <div><span>${__("New")}</span><b>${workforce.new.count}</b></div>
            <i>−</i>
            <div><span>${__("Terminated")}</span><b>${workforce.terminated.count}</b></div>
            <i>=</i>
            <div><span>${__("Closing")}</span><b>${workforce.headcount.closing}</b></div>
          </div>
          <div class="her-net ${workforce.headcount.net_change < 0 ? "is-negative" : "is-positive"}">
            ${__("Net change")}: ${this.signed(workforce.headcount.net_change)}
          </div>
        </div>
        <div class="her-card her-card--reasons">
          <div class="her-card-label">${__("Termination reasons")}</div>
          <div class="her-reason-list">${reasons || `<span class="her-muted">${__("No terminations in period")}</span>`}</div>
        </div>
      </section>
    `;
  }

  metric_card(key, label, value, note, tone = "neutral") {
    return `
      <button class="her-card her-metric-card her-tone--${tone}" data-detail="${key}">
        <span class="her-card-label">${label}</span>
        <strong>${value}</strong>
        <small>${note}</small>
      </button>
    `;
  }

  render_ir_panel(d) {
    return `
      <section class="her-panel her-panel--ir">
        <div class="her-section-heading her-section-heading--compact">
          <div><span>${__("Period activity")}</span><h2>${__("IR proceedings")}</h2></div>
          <p>${__("Opened and closed within the selected dates; outstanding is draft only.")}</p>
        </div>
        <div class="her-process-grid her-process-grid--v4">
          ${this.process_column("disciplinary", __("Disciplinary"), d.disciplinary)}
          ${this.process_column("incapacity", __("Incapacity"), d.incapacity)}
          ${this.process_column("poor_performance", __("Poor performance"), d.poor_performance)}
          ${this.process_column("external_disputes", __("External disputes"), d.external_disputes)}
        </div>
        ${this.render_combined(d)}
      </section>
    `;
  }

  process_column(key, title, data) {
    return `
      <div class="her-process-card her-process-card--v4">
        <div class="her-process-title"><h3>${title}</h3><span>${data.average_days_to_close} ${__("avg days")}</span></div>
        <div class="her-process-metrics">
          ${this.process_metric(`${key}.opened`, __("Opened"), data.opened.count, "opened")}
          ${this.process_metric(`${key}.closed`, __("Closed"), data.closed.count, "closed")}
          ${this.process_metric(`${key}.outstanding`, __("Draft"), data.outstanding.count, "outstanding")}
        </div>
        ${key === "external_disputes" ? this.render_external_inline(data) : ""}
      </div>
    `;
  }

  process_metric(detail, label, value, tone) {
    return `
      <button class="her-process-metric is-${tone}" data-detail="${detail}">
        <span>${label}</span><strong>${value}</strong>
      </button>
    `;
  }

  render_external_inline(data) {
    const rows = (data?.outstanding?.rows || []).slice(0, 4);
    if (!rows.length) {
      return `<div class="her-mini-note">${__("No draft external dispute matters.")}</div>`;
    }
    return `
      <button class="her-mini-list" data-detail="external_disputes.outstanding">
        <div class="her-mini-list-title">${__("Draft matters")}</div>
        ${rows.map((row) => `<div><span>${frappe.utils.escape_html(row.forum || __("Forum not set"))}</span><b>${frappe.utils.escape_html(row.case_no || row.name)}</b></div>`).join("")}
        ${(data.outstanding.count > rows.length) ? `<footer>+${data.outstanding.count - rows.length} ${__("more")}</footer>` : ""}
      </button>
    `;
  }

  render_combined(d) {
    return `
      <section class="her-combined-strip her-combined-strip--v4">
        <div><span>${__("Total opened")}</span><b>${d.combined.opened}</b></div>
        <div><span>${__("Total closed")}</span><b>${d.combined.closed}</b></div>
        <div><span>${__("Current draft")}</span><b>${d.combined.outstanding}</b></div>
        <div class="${d.combined.net_backlog_change > 0 ? "is-negative" : "is-positive"}">
          <span>${__("Backlog movement")}</span><b>${this.signed(d.combined.net_backlog_change)}</b>
        </div>
      </section>
    `;
  }

  render_ageing_panel(d) {
    const keys = [
      ["0_30", __("0–30 days")],
      ["31_60", __("31–60 days")],
      ["61_90", __("61–90 days")],
      ["over_90", __("Over 90 days")],
    ];

    return `
      <section class="her-panel her-panel--ageing">
        <div class="her-section-heading her-section-heading--compact"><div><span>${__("Current draft backlog")}</span><h2>${__("Outstanding ageing")}</h2></div></div>
        <div class="her-ageing-grid her-ageing-grid--v4">
          ${keys.map(([key, label]) => {
            const disciplinary = d.disciplinary.outstanding.ageing[key];
            const incapacity = d.incapacity.outstanding.ageing[key];
            const performance = d.poor_performance.outstanding.ageing[key];
            const disputes = d.external_disputes.outstanding.ageing[key];
            return `
              <div class="her-age-card">
                <strong>${label}</strong>
                <div><span>${__("Disciplinary")}</span><b>${disciplinary}</b></div>
                <div><span>${__("Incapacity")}</span><b>${incapacity}</b></div>
                <div><span>${__("Poor performance")}</span><b>${performance}</b></div>
                <div><span>${__("External disputes")}</span><b>${disputes}</b></div>
                <footer><span>${__("Total")}</span><b>${disciplinary + incapacity + performance + disputes}</b></footer>
              </div>`;
          }).join("")}
        </div>
      </section>
    `;
  }

  render_ee_panel(ee) {
    const summary = this.ee_summary(ee);
    return `
      <section class="her-panel her-panel--ee">
        <div class="her-section-heading her-section-heading--compact">
          <div><span>${__("Employment Equity")}</span><h2>${__("EEA13-style workforce snapshot")}</h2></div>
          <p>${__("Snapshot as at")} ${this.format_date(ee.snapshot_date)}</p>
        </div>
        <div class="her-ee-summary-grid">
          ${this.summary_chip(__("Active headcount"), summary.active_headcount)}
          ${this.summary_chip(__("Permanent"), summary.permanent)}
          ${this.summary_chip(__("Temporary"), summary.temporary)}
          ${this.summary_chip(__("Unmapped EE values"), summary.unmapped, summary.unmapped ? "warn" : "ok")}
        </div>
        ${this.render_ee_table(ee.all_employees, ee.special_rows)}
        ${this.render_ee_warning(ee)}
      </section>
    `;
  }

  ee_summary(ee) {
    const all = ee.all_employees || {};
    const disabled = ee.people_with_disabilities || {};
    const grand = all.grand_total || {};
    const perm = all.total_permanent || {};
    const temp = all.temporary || {};
    const disGrand = disabled.grand_total || {};
    return {
      active_headcount: grand.total || 0,
      permanent: perm.total || 0,
      temporary: temp.total || 0,
      disabled: disGrand.total || 0,
      foreign: (grand.foreign_male || 0) + (grand.foreign_female || 0),
      unmapped: (ee.unclassified_levels?.length || 0) + (ee.unclassified_demographics?.length || 0),
    };
  }

  summary_chip(label, value, tone = "neutral") {
    return `<div class="her-summary-chip her-summary-chip--${tone}"><span>${label}</span><b>${value}</b></div>`;
  }

  render_ee_table(table, specialRows = {}) {
    const rows = [
      ...table.levels.map((row) => ({ ...row, row_class: "" })),
      { level: __("TOTAL PERMANENT"), ...table.total_permanent, row_class: "is-total" },
      { level: __("Temporary employees"), ...table.temporary, row_class: "is-subtotal" },
      { level: __("GRAND TOTAL"), ...table.grand_total, row_class: "is-grand-total" },
      { level: __("People with disabilities"), ...(specialRows.people_with_disabilities || {}), row_class: "is-special" },
      { level: __("Foreign nationals"), ...(specialRows.foreign_nationals || {}), row_class: "is-special" },
    ];

    return `
      <div class="her-ee-block her-ee-block--single">
        <table class="her-ee-table her-ee-table--v4">
          <thead>
            <tr>
              <th rowspan="2">${__("Occupational level")}</th>
              <th colspan="4">${__("Male")}</th>
              <th colspan="4">${__("Female")}</th>
              <th rowspan="2">${__("Total")}</th>
            </tr>
            <tr><th>A</th><th>I</th><th>C</th><th>W</th><th>A</th><th>I</th><th>C</th><th>W</th></tr>
          </thead>
          <tbody>
            ${rows.map((row) => `
              <tr class="${row.row_class}">
                <th>${frappe.utils.escape_html(this.compact_level_label(row.level))}</th>
                <td>${row.african_male || 0}</td><td>${row.indian_male || 0}</td><td>${row.coloured_male || 0}</td><td>${row.white_male || 0}</td>
                <td>${row.african_female || 0}</td><td>${row.indian_female || 0}</td><td>${row.coloured_female || 0}</td><td>${row.white_female || 0}</td>
                <td>${row.total || 0}</td>
              </tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  compact_level_label(level) {
    const map = {
      [__("Top Management")]: __("Top Management"),
      [__("Senior Management")]: __("Senior Management"),
      [__("Professionally Qualified and Experienced Specialists and Mid-Management")]: __("Professional & Mid-Management"),
      [__("Skilled Technical and Academically Qualified Workers, Junior Management, Supervisors, Foremen and Superintendents")]: __("Skilled Technical / Junior Mgmt / Supervisors"),
      [__("Semi-Skilled and Discretionary Decision Making")]: __("Semi-Skilled") ,
      [__("Unskilled and Defined Decision Making")]: __("Unskilled"),
      [__("TOTAL PERMANENT")]: __("TOTAL PERMANENT"),
      [__("Temporary employees")]: __("Temporary employees"),
      [__("GRAND TOTAL")]: __("GRAND TOTAL"),
    };
    return map[level] || level;
  }

  render_ee_warning(ee) {
    const warnings = [];
    if (ee.unclassified_levels?.length) {
      warnings.push(`
        <button class="her-ee-warning" data-detail="ee_unclassified">
          ${ee.unclassified_levels.length} ${__("employee(s) excluded because their occupational level could not be mapped. Click to review.")}
        </button>`);
    }
    if (ee.unclassified_demographics?.length) {
      warnings.push(`
        <button class="her-ee-warning" data-detail="ee_unclassified_demographics">
          ${ee.unclassified_demographics.length} ${__("employee(s) have an unmapped Race / Designated Group value. Click to review.")}
        </button>`);
    }
    if (!warnings.length && !ee.employee_count_at_snapshot) {
      warnings.push(`<div class="her-ee-warning">${__("No employees matched the company and snapshot date. Detected fields:")} ${frappe.utils.escape_html(JSON.stringify(ee.field_map || {}))}</div>`);
    }
    return warnings.join("");
  }

  render_footer(d) {
    return `
      <footer class="her-slide-footer">
        <span>${__("Internal management report")}</span>
        <span>${frappe.utils.escape_html(d.company)}</span>
      </footer>
    `;
  }

  bind_metric_clicks() {
    this.$content.off("click.her").on("click.her", "[data-detail]", (event) => {
      const key = $(event.currentTarget).attr("data-detail");
      this.open_details(key);
    });
  }

  open_details(key) {
    const config = this.detail_config(key);
    if (!config) return;

    const dialog = new frappe.ui.Dialog({
      title: config.title,
      size: "extra-large",
      fields: [{ fieldtype: "HTML", fieldname: "results" }],
    });
    dialog.fields_dict.results.$wrapper.html(this.detail_table(config.rows, config.columns));
    dialog.show();
  }

  detail_config(key) {
    const d = this.data;
    const employee_columns = [
      ["name", __("Employee")],
      ["employee_name", __("Employee name")],
      ["branch", __("Branch")],
      ["designation", __("Designation")],
    ];
    const process_columns = [
      ["name", __("Document")],
      ["employee_name", __("Employee name")],
      ["branch", __("Branch")],
      ["request_date", __("Request date")],
      ["outcome", __("Outcome")],
      ["outcome_date", __("Outcome date")],
      ["age_days", __("Age days")],
    ];
    const external_columns = [
      ["case_no", __("Case number")],
      ["forum", __("Forum")],
      ["applicant_external", __("Applicant")],
      ["respondent_external", __("Respondent")],
      ["outcome", __("Outcome")],
      ["creation", __("Created")],
      ["docstatus", __("Docstatus")],
      ["age_days", __("Age days")],
    ];

    const map = {
      new: {
        title: __("New employees"),
        rows: d.workforce.new.rows,
        columns: [...employee_columns, ["date_of_joining", __("Date of joining")]],
      },
      terminated: {
        title: __("Terminated employees"),
        rows: d.workforce.terminated.rows,
        columns: [...employee_columns, ["relieving_date", __("Relieving date")], ["reason_for_leaving", __("Reason for leaving")]],
      },
      ee_unclassified: {
        title: __("Unclassified Employment Equity levels"),
        rows: d.employment_equity.unclassified_levels,
        columns: [["employee", __("Employee")], ["employee_name", __("Employee name")], ["designation", __("Designation")], ["occupational_level", __("Occupational level value")]],
      },
      ee_unclassified_demographics: {
        title: __("Unclassified Employment Equity demographics"),
        rows: d.employment_equity.unclassified_demographics,
        columns: [["employee", __("Employee")], ["employee_name", __("Employee name")], ["gender", __("Gender")], ["race_value", __("Race / Designated Group value")]],
      },
    };

    if (map[key]) return map[key];

    const [processKey, state] = key.split(".");
    if (d[processKey]?.[state]) {
      return {
        title: `${this.process_title(processKey)} – ${__(state)}`,
        rows: d[processKey][state].rows || [],
        columns: processKey === "external_disputes" ? external_columns : process_columns,
      };
    }
    return null;
  }

  process_title(key) {
    return {
      disciplinary: __("Disciplinary"),
      incapacity: __("Incapacity"),
      poor_performance: __("Poor performance"),
      external_disputes: __("External disputes"),
    }[key];
  }

  detail_table(rows, columns) {
    if (!rows?.length) return `<div class="her-empty">${__("No records")}</div>`;
    return `
      <div class="her-dialog-table-wrap">
        <table class="table table-bordered her-dialog-table">
          <thead><tr>${columns.map(([, label]) => `<th>${label}</th>`).join("")}</tr></thead>
          <tbody>
            ${rows.map((row) => `<tr>${columns.map(([field]) => `<td>${frappe.utils.escape_html(this.display_value(row[field]))}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>`;
  }

  display_value(value) {
    if (value === null || value === undefined) return "";
    return String(value);
  }

  async ensure_html2canvas() {
    if (window.html2canvas) {
      return;
    }

    await frappe.require(
      "/assets/ir/js/vendor/html2canvas.min.js"
    );

    if (!window.html2canvas) {
      throw new Error(
        __("html2canvas could not be loaded.")
      );
    }
  }

  export_race_totals(ee) {
    const grand = ee?.all_employees?.grand_total || {};
    return [
      [__("African"), (grand.african_male || 0) + (grand.african_female || 0)],
      [__("Coloured"), (grand.coloured_male || 0) + (grand.coloured_female || 0)],
      [__("Indian"), (grand.indian_male || 0) + (grand.indian_female || 0)],
      [__("White"), (grand.white_male || 0) + (grand.white_female || 0)],
      [__("Foreign nationals"), (grand.foreign_male || 0) + (grand.foreign_female || 0)],
    ];
  }

  ageing_total(d, bucket) {
    return [
      d.disciplinary,
      d.incapacity,
      d.poor_performance,
      d.external_disputes,
    ].reduce((total, process) => {
      return total + Number(process?.outstanding?.ageing?.[bucket] || 0);
    }, 0);
  }

  render_export_slide(d) {
    const workforce = d.workforce;
    const ee = d.employment_equity;
    const eeSummary = this.ee_summary(ee);
    const processes = [
      [__("Disciplinary"), d.disciplinary],
      [__("Incapacity"), d.incapacity],
      [__("Poor performance"), d.poor_performance],
      [__("External disputes"), d.external_disputes],
    ];
    const ageingTotals = [
      ["0–30", this.ageing_total(d, "0_30")],
      ["31–60", this.ageing_total(d, "31_60")],
      ["61–90", this.ageing_total(d, "61_90")],
      ["90+", this.ageing_total(d, "over_90")],
    ];
    const externalRows = (d.external_disputes?.outstanding?.rows || []).slice(0, 6);
    const allLevels = ee?.all_employees?.levels || [];
    const specialRows = ee?.special_rows || {};

    const eeRows = [
      ...allLevels.map((row) => ({ ...row, row_class: "" })),
      {
        level: __("TOTAL PERMANENT"),
        ...ee.all_employees.total_permanent,
        row_class: "her-x-ee-total",
      },
      {
        level: __("Temporary employees"),
        ...ee.all_employees.temporary,
        row_class: "her-x-ee-subtotal",
      },
      {
        level: __("GRAND TOTAL"),
        ...ee.all_employees.grand_total,
        row_class: "her-x-ee-grand-total",
      },
      {
        level: __("People with disabilities"),
        ...(specialRows.people_with_disabilities || {}),
        row_class: "her-x-ee-summary-row",
      },
      {
        level: __("Foreign nationals"),
        ...(specialRows.foreign_nationals || {}),
        row_class: "her-x-ee-summary-row",
      },
    ];

    return `
      <article class="her-export-slide her-export-slide--v7">
        <section class="her-x-kpis her-x-kpis--v7">
          ${this.export_kpi(__("New employees"), workforce.new.count, "green")}
          ${this.export_kpi(__("Terminations"), workforce.terminated.count, "red")}
          ${this.export_kpi(__("Closing headcount"), workforce.headcount.closing, "blue")}
        </section>

        <main class="her-x-body her-x-body--v7">
          <section class="her-x-panel her-x-panel--ir her-x-panel--v7">
            <table class="her-x-process-table her-x-process-table--v7">
              <thead>
                <tr>
                  <th>${__("Process")}</th>
                  <th>${__("New in period")}</th>
                  <th>${__("Concluded in period")}</th>
                  <th>${__("Current drafts")}</th>
                  <th>${__("Average days to conclude")}</th>
                </tr>
              </thead>
              <tbody>
                ${processes.map(([name, item]) => `
                  <tr>
                    <th>${name}</th>
                    <td>${item.opened.count}</td>
                    <td>${item.closed.count}</td>
                    <td class="her-x-alert">${item.outstanding.count}</td>
                    <td>${item.average_days_to_close}</td>
                  </tr>`).join("")}
              </tbody>
            </table>

            <div class="her-x-subtitle">${__("Current draft ageing")}</div>
            <div class="her-x-ageing">
              ${ageingTotals.map(([label, total]) => `<div><span>${label} ${__("days")}</span><b>${total}</b></div>`).join("")}
            </div>

            <div class="her-x-subtitle">${__("Draft external dispute matters")}</div>
            <div class="her-x-disputes">
              ${externalRows.length ? externalRows.map((row) => `<div><span>${frappe.utils.escape_html(row.forum || __("Forum not set"))}</span><b>${frappe.utils.escape_html(row.case_no || row.name)}</b></div>`).join("") : `<p>${__("None")}</p>`}
              ${(d.external_disputes.outstanding.count > externalRows.length) ? `<footer>+${d.external_disputes.outstanding.count - externalRows.length} ${__("additional matter(s)")}</footer>` : ""}
            </div>
          </section>

          <section class="her-x-panel her-x-panel--ee her-x-panel--v7">
            <div class="her-x-ee-meta">
              <span>${__("Employment Equity workforce matrix")}</span>
              <b>${__("Snapshot as at")} ${this.format_date(ee.snapshot_date)}</b>
            </div>
            <table class="her-x-ee-matrix">
              <thead>
                <tr>
                  <th rowspan="2">${__("Occupational level")}</th>
                  <th colspan="4">${__("Male")}</th>
                  <th colspan="4">${__("Female")}</th>
                  <th rowspan="2">${__("Total")}</th>
                </tr>
                <tr>
                  <th>A</th><th>I</th><th>C</th><th>W</th>
                  <th>A</th><th>I</th><th>C</th><th>W</th>
                </tr>
              </thead>
              <tbody>
                ${eeRows.map((row) => `
                  <tr class="${row.row_class}">
                    <th>${frappe.utils.escape_html(this.compact_level_label(row.level))}</th>
                    <td>${row.african_male || 0}</td>
                    <td>${row.indian_male || 0}</td>
                    <td>${row.coloured_male || 0}</td>
                    <td>${row.white_male || 0}</td>
                    <td>${row.african_female || 0}</td>
                    <td>${row.indian_female || 0}</td>
                    <td>${row.coloured_female || 0}</td>
                    <td>${row.white_female || 0}</td>
                    <td>${row.total || 0}</td>
                  </tr>`).join("")}
              </tbody>
            </table>
            <div class="her-x-note">${eeSummary.unmapped ? `${eeSummary.unmapped} ${__("unmapped EE value(s) require review")}` : __("All EE values mapped")}</div>
          </section>
        </main>

        <footer class="her-x-footer her-x-footer--v7">
          <span>${frappe.utils.escape_html(d.company)}</span>
          <span>${this.format_date(d.from_date)} – ${this.format_date(d.to_date)}</span>
        </footer>
      </article>
    `;
  }

  export_kpi(label, value, tone) {
    return `<div class="her-x-kpi her-x-kpi--${tone}"><span>${label}</span><b>${value}</b></div>`;
  }

  export_mini_kpi(label, value) {
    return `<div class="her-x-mini-kpi"><span>${label}</span><b>${value}</b></div>`;
  }

  export_document_css() {
    return `
      * {
        box-sizing: border-box;
      }

      html,
      body {
        width: 1920px;
        height: 1080px;
        margin: 0;
        padding: 0;
        overflow: hidden;
        background: transparent;
        color: #172033;
        font-family: Arial, sans-serif;
      }

      .her-export-slide {
        width: 1920px;
        height: 1080px;
        padding: 24px 30px 18px;
        overflow: hidden;
        background: transparent;
        font-variant-numeric: tabular-nums;
      }

      .her-x-kpis {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
      }

      .her-x-kpi,
      .her-x-panel,
      .her-x-ageing > div {
        border: 1px solid #d7dee8;
        border-radius: 10px;
        background: rgba(255, 255, 255, 0.98);
      }

      .her-x-kpi {
        min-height: 78px;
        padding: 10px 12px;
        border-top-width: 5px;
      }

      .her-x-kpi--green {
        border-top-color: #22c55e;
      }

      .her-x-kpi--red {
        border-top-color: #ef4444;
      }

      .her-x-kpi--blue {
        border-top-color: #3b82f6;
      }

      .her-x-kpi--amber {
        border-top-color: #f59e0b;
      }

      .her-x-kpi span,
      .her-x-subtitle,
      .her-x-ee-meta span {
        color: #64748b;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
      }

      .her-x-kpi b {
        display: block;
        margin-top: 7px;
        font-size: 29px;
        line-height: 1;
      }

      .her-x-body {
        display: grid;
        grid-template-columns: 0.92fr 1.08fr;
        gap: 14px;
        margin-top: 14px;
        align-items: start;
      }

      .her-x-panel {
        min-height: 0;
        padding: 18px;
      }

      table {
        width: 100%;
        border-collapse: collapse;
      }

      th,
      td {
        border: 1px solid #d7dee8;
      }

      .her-x-process-table {
        font-size: 18px;
      }

      .her-x-process-table th,
      .her-x-process-table td {
        padding: 16px 12px;
        text-align: center;
      }

      .her-x-process-table thead th {
        background: #f1f5f9;
        color: #475569;
        font-size: 11px;
        text-transform: uppercase;
      }

      .her-x-process-table tbody th {
        width: 33%;
        text-align: left;
      }

      .her-x-alert {
        color: #b91c1c;
        font-weight: 900;
      }

      .her-x-subtitle {
        margin: 16px 0 7px;
      }

      .her-x-ageing {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
      }

      .her-x-ageing > div {
        padding: 9px 10px;
      }

      .her-x-ageing span {
        display: block;
        color: #64748b;
        font-size: 11px;
        font-weight: 700;
      }

      .her-x-ageing b {
        display: block;
        margin-top: 3px;
        font-size: 23px;
      }

      .her-x-disputes {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 7px 10px;
        font-size: 13px;
      }

      .her-x-disputes > div {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        padding: 7px 8px;
        border-radius: 6px;
        background: #f8fafc;
      }

      .her-x-disputes footer {
        grid-column: 1 / -1;
        color: #64748b;
        font-weight: 700;
        text-align: right;
      }

      .her-x-ee-meta {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 14px;
        margin-bottom: 8px;
      }

      .her-x-ee-meta b {
        color: #475569;
        font-size: 11px;
      }

      .her-x-ee-matrix {
        font-size: 14px;
        line-height: 1.25;
      }

      .her-x-ee-matrix th,
      .her-x-ee-matrix td {
        padding: 11px 7px;
        text-align: center;
      }

      .her-x-ee-matrix thead th {
        background: #f1f5f9;
        color: #475569;
        font-size: 11px;
        text-transform: uppercase;
      }

      .her-x-ee-matrix tbody th {
        width: 330px;
        text-align: left;
        font-size: 14px;
      }

      .her-x-ee-total th,
      .her-x-ee-total td,
      .her-x-ee-subtotal th,
      .her-x-ee-subtotal td {
        background: #f8fafc;
        font-weight: 900;
      }

      .her-x-ee-grand-total th,
      .her-x-ee-grand-total td {
        background: #eef2ff;
        font-weight: 900;
      }

      .her-x-ee-summary-row th,
      .her-x-ee-summary-row td {
        background: #f8fafc;
        font-weight: 800;
      }

      .her-x-ee-summary-row td {
        color: #334155;
      }

      .her-x-note {
        margin-top: 8px;
        padding: 8px 10px;
        border-radius: 7px;
        background: #fff7ed;
        color: #9a3412;
        font-size: 12px;
        font-weight: 800;
      }

      .her-x-footer {
        display: flex;
        justify-content: space-between;
        gap: 18px;
        margin-top: 10px;
        padding-top: 7px;
        border-top: 1px solid #cbd5e1;
        color: #64748b;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
      }
    `;
  }

  create_export_frame(target) {
    const iframe = document.createElement("iframe");
    iframe.setAttribute("aria-hidden", "true");
    Object.assign(iframe.style, {
      position: "fixed",
      left: "-20000px",
      top: "0",
      width: "1920px",
      height: "1080px",
      border: "0",
      opacity: "0",
      pointerEvents: "none",
    });
    document.body.appendChild(iframe);
    const doc = iframe.contentDocument;
    doc.open();
    doc.write(`<!doctype html><html><head><meta charset="utf-8"><style>${this.export_document_css()}</style></head><body></body></html>`);
    doc.close();
    doc.body.innerHTML = this.render_export_slide(this.data);
    const clone = doc.body.firstElementChild;
    return { iframe, clone };
  }

  async capture_blob() {
    if (!this.data) throw new Error(__("Generate the report before exporting."));
    await this.ensure_html2canvas();
    const target = this.$content.find("[data-export-target]")[0];
    const { iframe, clone } = this.create_export_frame(target);
    try {
      const canvas = await window.html2canvas(clone, {
        backgroundColor: null,
        scale: 2,
        useCORS: true,
        logging: false,
        windowWidth: 1920,
        windowHeight: 1080,
        width: 1920,
        height: 1080,
      });
      return await new Promise((resolve, reject) => {
        canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error(__("PNG creation failed.")))), "image/png");
      });
    } finally {
      iframe.remove();
    }
  }

  async export_png() {
    try {
      const blob = await this.capture_blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `HR-Exception-Report-${this.slug(this.data.company)}-${this.data.from_date}-to-${this.data.to_date}.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      frappe.msgprint({ title: __("Export failed"), message: error.message, indicator: "red" });
    }
  }

  async copy_png() {
    try {
      if (!navigator.clipboard || !window.ClipboardItem) {
        throw new Error(__("This browser does not support copying PNG images to the clipboard."));
      }
      const blob = await this.capture_blob();
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      frappe.show_alert({ message: __("PNG copied to clipboard"), indicator: "green" });
    } catch (error) {
      frappe.msgprint({ title: __("Copy failed"), message: error.message, indicator: "red" });
    }
  }

  format_date(value) {
    return value ? frappe.datetime.str_to_user(value) : "";
  }

  format_datetime(value) {
    return value ? frappe.datetime.str_to_user(value.split(".")[0]) : "";
  }

  signed(value) {
    return value > 0 ? `+${value}` : String(value);
  }

  slug(value) {
    return String(value || "company").trim().replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
}