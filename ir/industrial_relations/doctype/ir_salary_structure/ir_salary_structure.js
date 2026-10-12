// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("IR Salary Structure", {
  onload: function (frm) {
    if (frm.is_new() && !frm.doc.company) {
      frm.set_value("company", frappe.defaults.get_default("company"));
    }
  },

  refresh: async function (frm) {
    await frm.events.render_salary_structure_cards(frm);
  },

  company: function (frm) {
    if (!frm.doc.company) {
      frm.set_value("letter_head", null);
      return;
    }
    frappe.call({
      method:
        "ir.industrial_relations.doctype.ir_salary_structure.ir_salary_structure.get_company_letter_head",
      args: { company: frm.doc.company },
      callback: function (r) {
        frm.set_value("letter_head", r.message || null);
      },
    });
  },

  salary_structure_map_add: function (frm) {
    frm.events.render_salary_structure_cards(frm);
  },

  salary_structure_map_remove: function (frm) {
    frm.events.render_salary_structure_cards(frm);
  },

  render_salary_structure_cards: async function (frm) {
    const field = frm.get_field("html_preview");
    const wrapper = field?.$wrapper;
    if (!wrapper) return;

    frm.events.ensure_irss_css();

    const rows = (frm.doc.salary_structure_map || []).filter((r) => r.salary_structure);
    if (!rows.length) {
      wrapper.html(`
        <div class="irss-panel">
          <div class="text-muted">Add a Designation and Salary Structure to preview them here.</div>
        </div>
      `);
      return;
    }

    const names = [...new Set(rows.map((r) => r.salary_structure))];

    let summaries = {};
    try {
      const r = await frappe.call({
        method:
          "ir.industrial_relations.doctype.ir_salary_structure.ir_salary_structure.get_salary_structure_summaries",
        args: { names },
      });
      summaries = r.message || {};
    } catch (err) {
      console.error("Failed to fetch Salary Structure summaries:", err);
    }

    wrapper.html(frm.events.build_irss_cards_html(rows, summaries));
  },

  build_irss_cards_html: function (rows, summaries) {
    const esc = frappe.utils.escape_html;
    const fmt_currency = (value, currency) => (value ? format_currency(value, currency) : "—");

    const cards = rows
      .map((row) => {
        const summary = summaries[row.salary_structure] || {};
        const active = summary.is_active === "Yes";
        const band = active ? "irss-card-success" : "irss-card-warning";
        const currency = summary.currency;

        return `
          <div class="irss-card ${band}">
            <div class="irss-card-head">
              <div class="irss-card-title">${esc(row.designation || "")}</div>
              <div class="irss-card-status">${active ? "Active" : "Inactive"}</div>
            </div>
            <div class="irss-card-body">
              <div class="irss-card-row">
                <span class="irss-label">Salary Structure</span>
                <span class="irss-value">${esc(row.salary_structure || "")}</span>
              </div>
              <div class="irss-card-row">
                <span class="irss-label">Payroll Period</span>
                <span class="irss-value">${esc(row.payroll_period || "—")}</span>
              </div>
              <div class="irss-card-row">
                <span class="irss-label">Frequency</span>
                <span class="irss-value">${esc(summary.payroll_frequency || "—")}</span>
              </div>
              <div class="irss-card-row">
                <span class="irss-label">Total Earning</span>
                <span class="irss-value irss-kpi">${fmt_currency(summary.total_earning, currency)}</span>
              </div>
              <div class="irss-card-row">
                <span class="irss-label">Total Deduction</span>
                <span class="irss-value">${fmt_currency(summary.total_deduction, currency)}</span>
              </div>
              <div class="irss-card-row">
                <span class="irss-label">Net Pay</span>
                <span class="irss-value irss-kpi">${fmt_currency(summary.net_pay, currency)}</span>
              </div>
            </div>
          </div>
        `;
      })
      .join("");

    return `<div class="irss-card-grid">${cards}</div>`;
  },

  ensure_irss_css: function () {
    if (document.getElementById("irss-css")) return;

    const style = document.createElement("style");
    style.id = "irss-css";
    style.textContent = `
      .irss-panel {
        background: var(--card-bg, var(--bg-color, #fff));
        border: 1px solid var(--border-color, #d1d8dd);
        border-radius: 10px;
        padding: 10px;
      }

      .irss-card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 12px;
        align-items: stretch;
      }

      .irss-card {
        border-radius: 12px;
        border: 1px solid var(--border-color, #d1d8dd);
        padding: 12px;
        background: var(--card-bg, var(--bg-color, #fff));
        box-shadow: 0 1px 0 rgba(0,0,0,0.04);
      }

      .irss-card-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 10px;
      }

      .irss-card-title { font-weight: 700; }
      .irss-card-status { font-size: 12px; opacity: 0.85; white-space: nowrap; }

      .irss-card-body { display: grid; gap: 8px; }
      .irss-card-row {
        display: grid;
        grid-template-columns: 120px 1fr;
        gap: 10px;
        align-items: center;
      }

      .irss-label { font-size: 12px; color: var(--text-muted, #6c7680); }
      .irss-value { font-size: 13px; }
      .irss-kpi { font-weight: 800; }

      .irss-card-success {
        border-left: 8px solid rgba(25, 135, 84, 0.85);
        background: rgba(25, 135, 84, 0.06);
      }
      .irss-card-warning {
        border-left: 8px solid rgba(255, 193, 7, 0.90);
        background: rgba(255, 193, 7, 0.08);
      }
    `;
    document.head.appendChild(style);
  },
});

frappe.ui.form.on("IR Salary Structure Map", {
  designation: function (frm) {
    frm.events.render_salary_structure_cards(frm);
  },
  salary_structure: function (frm) {
    frm.events.render_salary_structure_cards(frm);
  },
  payroll_period: function (frm) {
    frm.events.render_salary_structure_cards(frm);
  },
});
