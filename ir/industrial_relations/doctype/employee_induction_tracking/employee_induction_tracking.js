// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const INDUCTION_DISPLAY_FIELD = "training_name";

frappe.ui.form.on("Employee Induction Tracking", {
  refresh: async function (frm) {
    if (!frm.is_new() && frm.doc.employee) {
      await frm.events.sync_employee_fields_if_changed(frm);
    }
    await frm.events.render_induction_panels(frm);
  },

  employee: async function (frm) {
    await frm.events.populate_employee_details(frm);
    await frm.events.render_induction_panels(frm);
  },

  inductions_required: async function (frm) {
    await frm.events.render_induction_panels(frm);
  },

  sync_employee_fields_if_changed: async function (frm) {
    const employee = frm.doc.employee;
    if (!employee) return;

    const employee_fields = ["designation", "custom_occupational_level"];

    try {
      const r = await frappe.db.get_value("Employee", employee, employee_fields);
      const v = r?.message || {};

      const desired = {
        designation: v.designation || null,
        occupational_level: v.custom_occupational_level || null,
      };

      const changes = {};
      for (const [fieldname, newVal] of Object.entries(desired)) {
        const oldVal = frm.doc[fieldname];
        const normOld = oldVal === "" || oldVal === undefined ? null : oldVal;
        const normNew = newVal === "" || newVal === undefined ? null : newVal;

        if (normOld !== normNew) changes[fieldname] = normNew;
      }

      if (Object.keys(changes).length) frm.set_value(changes);
    } catch (err) {
      console.error("Failed to fetch Employee details:", err);
    }
  },

  populate_employee_details: async function (frm) {
    const employee = frm.doc.employee;

    if (!employee) {
      frm.set_value("employee_name", null);
      frm.set_value("engagement_date", null);
      frm.set_value("designation", null);
      frm.set_value("branch", null);
      frm.set_value("id_number", null);
      frm.set_value("designated_group", null);
      frm.set_value("occupational_level", null);
      frm.set_value("is_disabled", 0);
      return;
    }

    const employee_fields = [
      "employee_name",
      "date_of_joining",
      "designation",
      "branch",
      "za_id_number",
      "za_race",
      "custom_occupational_level",
      "za_is_disabled",
    ];

    try {
      const r = await frappe.db.get_value("Employee", employee, employee_fields);
      const v = r?.message || {};
      frm.set_value("employee_name", v.employee_name || null);
      frm.set_value("engagement_date", v.date_of_joining || null);
      frm.set_value("designation", v.designation || null);
      frm.set_value("branch", v.branch || null);
      frm.set_value("id_number", v.za_id_number || null);
      frm.set_value("designated_group", v.za_race || null);
      frm.set_value("occupational_level", v.custom_occupational_level || null);
      frm.set_value("is_disabled", v.za_is_disabled ? 1 : 0);
    } catch (err) {
      console.error("Failed to fetch Employee details:", err);
      frappe.msgprint({
        title: __("Employee lookup failed"),
        message: __("Could not fetch details for Employee {0}. Please try again.", [employee]),
        indicator: "red",
      });
    }
  },

  render_induction_panels: async function (frm) {
    const field = frm.get_field("induction_history_html");
    const wrapper = field?.$wrapper;
    if (!wrapper) return;

    frm.events.ensure_induction_css();

    const employee = frm.doc.employee;
    if (!employee) {
      wrapper.html(`
        <div class="eit-panel">
          <div class="text-muted">Select an employee to view the skills matrix and induction history.</div>
        </div>
      `);
      return;
    }

    let records = [];
    try {
      records = await frappe.db.get_list("Employee Induction Record", {
        filters: { employee },
        fields: ["name", "training", "facilitator", "training_date", "valid_to", "certificate", "docstatus"],
        order_by: "training_date desc",
        limit: 500,
      });
    } catch (err) {
      console.error("Failed to fetch induction records:", err);
      wrapper.html(`
        <div class="eit-panel eit-panel-danger">
          Could not load induction records for this employee.
        </div>
      `);
      return;
    }

    const required_inductions = (frm.doc.inductions_required || [])
      .map((r) => r.induction)
      .filter(Boolean);

    const induction_name_map = await frm.events.fetch_induction_display_names(required_inductions);

    const cards_html = frm.events.build_skills_cards_html(frm, records, induction_name_map);
    const history_html = frm.events.build_history_table_html(records);

    wrapper.html(`
      <div class="eit-root">
        <div class="eit-section">
          <div class="eit-section-title">Skills Matrix</div>
          ${cards_html}
        </div>

        <div class="eit-section">
          <div class="eit-section-title">Induction History</div>
          ${history_html}
        </div>
      </div>
    `);
  },

  fetch_induction_display_names: async function (induction_ids) {
    const map = {};
    if (!induction_ids || !induction_ids.length) return map;

    const uniq = [...new Set(induction_ids)];

    try {
      const rows = await frappe.db.get_list("Employee Induction", {
        filters: { name: ["in", uniq] },
        fields: ["name", INDUCTION_DISPLAY_FIELD],
        limit: 1000,
      });

      for (const r of rows) {
        map[r.name] = r[INDUCTION_DISPLAY_FIELD] || r.name;
      }
    } catch (e) {
      uniq.forEach((x) => (map[x] = x));
      console.warn("Could not fetch induction display names; falling back to link values.", e);
    }

    uniq.forEach((x) => {
      if (!map[x]) map[x] = x;
    });

    return map;
  },

  build_skills_cards_html: function (frm, records, induction_name_map) {
    const esc = frappe.utils.escape_html;

    const required = (frm.doc.inductions_required || [])
      .map((r) => r.induction)
      .filter(Boolean);

    if (!required.length) {
      return `
        <div class="eit-panel">
          <div class="text-muted">No required inductions selected.</div>
        </div>
      `;
    }

    const by_training = {};
    for (const r of records || []) {
      if (!r.training) continue;
      (by_training[r.training] ||= []).push(r);
    }

    for (const k of Object.keys(by_training)) {
      by_training[k].sort((a, b) => (b.training_date || "").localeCompare(a.training_date || ""));
    }

    const today = frappe.datetime.get_today();
    const warn_date = frappe.datetime.add_days(today, 90);

    const to_obj = (d) => frappe.datetime.str_to_obj(d);
    const days_between = (a, b) => {
      if (!a || !b) return null;
      const ms = to_obj(b).getTime() - to_obj(a).getTime();
      return Math.floor(ms / (1000 * 60 * 60 * 24));
    };

    const band_for = (expiry) => {
      if (!expiry) return "eit-card-danger"; // no expiry => red
      if (expiry < today) return "eit-card-danger";
      if (expiry <= warn_date) return "eit-card-warning";
      return "eit-card-success";
    };

    const fmt = (d) => (d ? esc(d) : `<span class="text-muted">—</span>`);

    const cards = required
      .map((training_id) => {
        const list = by_training[training_id] || [];
        const latest_completed = list.find((x) => x.docstatus === 1) || null;
        const latest_any = list[0] || null;
        const latest_scheduled_future =
          list.find((x) => x.docstatus !== 1 && x.training_date && x.training_date >= today) || null;
        const display_source = latest_completed || latest_any;
        const display_last_date = display_source?.training_date || null;
        const display_expiry = display_source?.valid_to || null;
        const completed_expiry = latest_completed?.valid_to || null;
        const band = latest_completed ? band_for(completed_expiry) : "eit-card-danger";
        const scheduled_date = latest_scheduled_future?.training_date || null;
        let status = "Not Completed";
        if (latest_completed && !completed_expiry) status = "No Expiry Set";
        else if (latest_completed && completed_expiry) status = completed_expiry < today ? "Expired" : "Compliant";
        else if (!latest_completed && scheduled_date) status = "Scheduled";
        const days_remaining = completed_expiry ? days_between(today, completed_expiry) : null;
        const days_html =
          days_remaining === null
            ? `<span class="text-muted">—</span>`
            : `<span class="eit-kpi">${esc(String(days_remaining))} days</span>`;
        const last_label = latest_completed ? "Last attended" : "Last recorded";
        let note_html = "";
        if (latest_completed && completed_expiry && scheduled_date && scheduled_date > completed_expiry) {
          note_html = `<div class="eit-note">Scheduled after expiry</div>`;
        }
        const display_name = induction_name_map?.[training_id] || training_id;

        return `
          <div class="eit-card ${band}">
            <div class="eit-card-head">
              <div class="eit-card-title">${esc(display_name)}</div>
              <div class="eit-card-status">${esc(status)}</div>
            </div>

            <div class="eit-card-body">
              <div class="eit-card-row">
                <div class="eit-label">${esc(last_label)}</div>
                <div class="eit-value">${fmt(display_last_date)}</div>
              </div>

              <div class="eit-card-row">
                <div class="eit-label">Expiry date</div>
                <div class="eit-value">${display_expiry ? esc(display_expiry) : `<span class="text-muted">—</span>`}</div>
              </div>

              <div class="eit-card-row">
                <div class="eit-label">Days remaining</div>
                <div class="eit-value">${days_html}</div>
              </div>

              <div class="eit-card-row">
                <div class="eit-label">Next scheduled</div>
                <div class="eit-value">${fmt(scheduled_date)}</div>
              </div>

              ${note_html}
            </div>
          </div>
        `;
      })
      .join("");

    const legend = `
      <div class="eit-legend">
        <span class="eit-legend-item"><span class="eit-swatch eit-swatch-success"></span> Valid (90+ days)</span>
        <span class="eit-legend-item"><span class="eit-swatch eit-swatch-warning"></span> Expiring (≤ 90 days)</span>
        <span class="eit-legend-item"><span class="eit-swatch eit-swatch-danger"></span> Missing / Expired / No expiry</span>
      </div>
    `;

    return `
      <div class="eit-panel">
        ${legend}
        <div class="eit-card-grid">
          ${cards}
        </div>
      </div>
    `;
  },

  build_history_table_html: function (records) {
    const esc = frappe.utils.escape_html;

    const row_html =
      records.length > 0
        ? records
            .map((r) => {
              const record_url = `/app/employee-induction-record/${encodeURIComponent(r.name)}`;
              const cert_html = r.certificate
                ? `<a href="${esc(r.certificate)}" target="_blank" rel="noopener">Open</a>`
                : `<span class="text-muted">—</span>`;

              const status = r.docstatus === 1 ? "Submitted" : r.docstatus === 0 ? "Draft" : "Cancelled";
              const status_pill = `
                <span class="eit-pill ${r.docstatus === 1 ? "eit-pill-complete" : "eit-pill-scheduled"}">
                  ${esc(status)}
                </span>
              `;

              return `
                <tr>
                  <td><a href="${record_url}">${esc(r.name)}</a></td>
                  <td>${r.training ? esc(r.training) : `<span class="text-muted">—</span>`}</td>
                  <td>${r.facilitator ? esc(r.facilitator) : `<span class="text-muted">—</span>`}</td>
                  <td>${r.training_date ? esc(r.training_date) : `<span class="text-muted">—</span>`}</td>
                  <td>${r.valid_to ? esc(r.valid_to) : `<span class="text-muted">—</span>`}</td>
                  <td>${cert_html}</td>
                  <td>${status_pill}</td>
                </tr>
              `;
            })
            .join("")
        : `
          <tr>
            <td colspan="7" class="text-muted">
              No induction records found for this employee.
            </td>
          </tr>
        `;

    return `
      <div class="table-responsive">
        <table class="table table-bordered table-hover eit-table" style="margin-bottom: 0;">
          <thead>
            <tr>
              <th>Induction Record</th>
              <th>Induction</th>
              <th>Facilitator</th>
              <th>Completed Date</th>
              <th>Expiry Date</th>
              <th>Certificate</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${row_html}
          </tbody>
        </table>
      </div>
    `;
  },

  ensure_induction_css: function () {
    if (document.getElementById("eit-css")) return;

    const style = document.createElement("style");
    style.id = "eit-css";
    style.textContent = `
      .eit-root { display: grid; gap: 12px; }

      .eit-section-title {
        font-weight: 600;
        margin: 2px 0 6px;
        color: var(--text-color, #1f272e);
      }

      .eit-panel {
        background: var(--card-bg, var(--bg-color, #fff));
        border: 1px solid var(--border-color, #d1d8dd);
        border-radius: 10px;
        padding: 10px;
      }

      .eit-panel-danger { border-color: var(--red-300, #f1aeb5); }

      .eit-legend {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-bottom: 10px;
        color: var(--text-muted, #6c7680);
        font-size: 12px;
      }
      .eit-legend-item { display: inline-flex; align-items: center; gap: 6px; }
      .eit-swatch {
        width: 10px; height: 10px; border-radius: 3px;
        border: 1px solid var(--border-color, #d1d8dd);
      }
      .eit-swatch-success { background: rgba(25, 135, 84, 0.35); }
      .eit-swatch-warning { background: rgba(255, 193, 7, 0.45); }
      .eit-swatch-danger  { background: rgba(220, 53, 69, 0.35); }

      .eit-card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 12px;
        align-items: stretch;
      }

      .eit-card {
        border-radius: 12px;
        border: 1px solid var(--border-color, #d1d8dd);
        padding: 12px;
        background: var(--card-bg, var(--bg-color, #fff));
        box-shadow: 0 1px 0 rgba(0,0,0,0.04);
      }

      .eit-card-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 10px;
      }

      .eit-card-title { font-weight: 700; }
      .eit-card-status { font-size: 12px; opacity: 0.85; white-space: nowrap; }

      .eit-card-body { display: grid; gap: 8px; }
      .eit-card-row {
        display: grid;
        grid-template-columns: 120px 1fr;
        gap: 10px;
        align-items: center;
      }

      .eit-label { font-size: 12px; color: var(--text-muted, #6c7680); }
      .eit-value { font-size: 13px; }
      .eit-kpi { font-weight: 800; }
      .eit-note { font-size: 12px; margin-top: 6px; opacity: 0.85; }

      .eit-card-success {
        border-left: 8px solid rgba(25, 135, 84, 0.85);
        background: rgba(25, 135, 84, 0.06);
      }
      .eit-card-warning {
        border-left: 8px solid rgba(255, 193, 7, 0.90);
        background: rgba(255, 193, 7, 0.08);
      }
      .eit-card-danger  {
        border-left: 8px solid rgba(220, 53, 69, 0.85);
        background: rgba(220, 53, 69, 0.06);
      }

      .eit-pill {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid var(--border-color, #d1d8dd);
        background: var(--control-bg, rgba(0,0,0,0.02));
        color: var(--text-color, #1f272e);
        white-space: nowrap;
      }
      .eit-pill-complete { border-color: rgba(25, 135, 84, 0.35); }
      .eit-pill-scheduled { border-color: rgba(13, 110, 253, 0.35); }

      body[data-theme="dark"] .eit-section-title { color: var(--text-color, #f0f3f6); }
      body[data-theme="dark"] .eit-panel { border-color: rgba(255,255,255,0.12); }
      body[data-theme="dark"] .eit-card {
        border-color: rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.03);
        box-shadow: none;
      }
      body[data-theme="dark"] .eit-card-success { background: rgba(25, 135, 84, 0.14); }
      body[data-theme="dark"] .eit-card-warning { background: rgba(255, 193, 7, 0.14); }
      body[data-theme="dark"] .eit-card-danger  { background: rgba(220, 53, 69, 0.14); }
      body[data-theme="dark"] .eit-pill {
        border-color: rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.05);
        color: var(--text-color, #f0f3f6);
      }
    `;
    document.head.appendChild(style);
  },
});
