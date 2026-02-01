// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Training Matrix"] = {
  freeze: true,
  freeze_columns: 3, // Tracking, Employee, Employee Name

  filters: [
    {
      fieldname: "area_setup",
      label: __("Area Setup"),
      fieldtype: "Link",
      options: "Area Setup",
    },
    {
      fieldname: "branch",
      label: __("Branch"),
      fieldtype: "Link",
      options: "Branch",
    },
    {
      fieldname: "employee",
      label: __("Employee"),
      fieldtype: "Link",
      options: "Employee",
    },
    {
      fieldname: "designation",
      label: __("Designation"),
      fieldtype: "Link",
      options: "Designation",
    },
    {
      fieldname: "employee_status",
      label: __("Employee Status"),
      fieldtype: "Select",
      options: ["All", "Active", "Inactive", "Suspended", "Left"],
      default: "Active",
    },
  ],

  onload: function () {
    if (document.getElementById("tm-css")) return;

    const style = document.createElement("style");
    style.id = "tm-css";
    style.textContent = `
      .tm-pill{
        display:inline-flex;
        align-items:center;
        gap:6px;
        padding:2px 8px;
        border-radius:999px;
        font-size:12px;
        font-weight:600;
        border:1px solid var(--border-color, rgba(0,0,0,0.12));
        background: var(--control-bg, rgba(0,0,0,0.02));
        white-space:nowrap;
        line-height: 1.4;
      }
      .tm-dot{ width:8px; height:8px; border-radius:50%; display:inline-block; }
      .tm-green  .tm-dot { background: rgba(25,135,84,0.95); }
      .tm-yellow .tm-dot { background: rgba(255,193,7,0.95); }
      .tm-red    .tm-dot { background: rgba(220,53,69,0.95); }

      .tm-sub{
        display:block;
        font-size:11px;
        opacity:.8;
        margin-top:2px;
        white-space:nowrap;
      }
      .tm-mono{ font-variant-numeric: tabular-nums; }
    `;
    document.head.appendChild(style);
  },

  formatter: function (value, row, column, data, default_formatter) {
    // Make Tracking + Employee display just the ID (still clickable)
    if (column.fieldname === "tracking" && value) {
      const name_only = String(value).split(":")[0].trim();
      const url = frappe.utils.get_form_link("Employee Induction Tracking", name_only);
      return `<a href="${url}">${frappe.utils.escape_html(name_only)}</a>`;
    }

    if (column.fieldname === "employee" && value) {
      const emp = String(value).split(":")[0].trim();
      const url = frappe.utils.get_form_link("Employee", emp);
      return `<a href="${url}">${frappe.utils.escape_html(emp)}</a>`;
    }

    // Only format dynamic induction columns
    if (!column.fieldname || !column.fieldname.startsWith("ind_")) {
      return default_formatter(value, row, column, data);
    }

    if (!value) return "";

    let obj;
    try {
      obj = typeof value === "string" ? JSON.parse(value) : value;
    } catch (e) {
      return default_formatter(value, row, column, data);
    }

    const status = obj.status || "red";
    const expiry = obj.expiry || "—";
    const days = (obj.days === 0 || obj.days) ? `${obj.days}d` : "";
    const main = `${expiry}${days ? " • " + days : ""}`;
    const sched = obj.scheduled ? `Sched: ${obj.scheduled}` : "";

    return `
      <span class="tm-pill tm-${frappe.utils.escape_html(status)}">
        <span class="tm-dot"></span>
        <span class="tm-mono">${frappe.utils.escape_html(main)}</span>
      </span>
      ${sched ? `<span class="tm-sub">${frappe.utils.escape_html(sched)}</span>` : ""}
    `;
  },
};
