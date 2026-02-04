// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Training Matrix"] = {
  freeze: true,
  freeze_columns: 3, // Tracking, Employee, Employee Name

  filters: [
    { fieldname: "area_setup", label: __("Area Setup"), fieldtype: "Link", options: "Area Setup" },
    { fieldname: "branch", label: __("Branch"), fieldtype: "Link", options: "Branch" },
    { fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
    { fieldname: "designation", label: __("Designation"), fieldtype: "Link", options: "Designation" },
    {
      fieldname: "employee_status",
      label: __("Employee Status"),
      fieldtype: "Select",
      options: ["All", "Active", "Inactive", "Suspended", "Left"],
      default: "Active",
    },
  ],

  onload: function () {
    frappe.require("/assets/ir/css/ir_ui.css");

    const wrapper = frappe.query_report && frappe.query_report.wrapper;
    if (wrapper) wrapper.addClass("tm-report");

    // Minimal report-scoped CSS; row height is handled by datatable options below.
    if (!document.getElementById("tm-css")) {
      const style = document.createElement("style");
      style.id = "tm-css";
      style.textContent = `
        .tm-report .dt-cell__content{
          overflow: visible !important;
          padding-top: 6px !important;
          padding-bottom: 6px !important;
        }
      `;
      document.head.appendChild(style);
    }
  },

  // ✅ This is the reliable way in Frappe reports (frappe-datatable option)
  get_datatable_options: function (options) {
    return Object.assign(options, {
      // default is ~33; make it taller so card isn't clipped
      cellHeight: 78,

      // keep performance sane; you're already freezing columns
      inlineFilters: true,
    });
  },

  formatter: function (value, row, column, data, default_formatter) {
    // Tracking column: show just ID (clickable)
    if (column.fieldname === "tracking" && value) {
      const name_only = String(value).split(":")[0].trim();
      const url = frappe.utils.get_form_link("Employee Induction Tracking", name_only);
      return `<a href="${url}">${frappe.utils.escape_html(name_only)}</a>`;
    }

    // Employee column: show just ID (clickable)
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

    const status = (obj.status || "red").toLowerCase(); // green|yellow|red
    const expiry = obj.expiry || null;
    const days = (obj.days === 0 || obj.days) ? obj.days : null;
    const last = obj.last || null;
    const scheduled = obj.scheduled || null;

    const status_label = get_status_label(status, expiry, days);
    const main_line = build_main_line(expiry, days);

    const last_line = last ? `Last: ${last}` : "";
    const sched_line = scheduled ? `Scheduled: ${scheduled}` : "";

    // Optional links from payload (safe if missing)
    const sub_rec = obj.submitted_record || null;
    const sch_rec = obj.scheduled_record || null;

    const links = [];
    if (sub_rec) {
      const u = frappe.utils.get_form_link("Employee Induction Record", sub_rec);
      links.push(`<a href="${u}" title="Open latest submitted record">Record</a>`);
    }
    if (sch_rec) {
      const u = frappe.utils.get_form_link("Employee Induction Record", sch_rec);
      links.push(`<a href="${u}" title="Open scheduled draft">Scheduled</a>`);
    }

    return `
      <div class="tm-card tm-${frappe.utils.escape_html(status)}">
        <div class="tm-card__top">
          <div class="tm-card__left">
            <span class="tm-dot"></span>
            <span class="tm-status">${frappe.utils.escape_html(status_label)}</span>
          </div>
        </div>

        <div class="tm-main">${frappe.utils.escape_html(main_line)}</div>

        ${last_line ? `<div class="tm-meta">${frappe.utils.escape_html(last_line)}</div>` : ``}
        ${sched_line ? `<div class="tm-meta">${frappe.utils.escape_html(sched_line)}</div>` : ``}
        ${links.length ? `<div class="tm-meta tm-actions">${links.join(" • ")}</div>` : ``}
      </div>
    `;
  },
};

function get_status_label(status, expiry, days) {
  if (!expiry) return "Not trained";
  if (status === "green") return "Valid";
  if (status === "yellow") return "Expiring";
  if (typeof days === "number" && days < 0) return "Expired";
  return "Attention";
}

function build_main_line(expiry, days) {
  if (!expiry) return "No expiry on record";
  if (typeof days === "number") {
    const d = days < 0 ? `${Math.abs(days)}d overdue` : `${days}d left`;
    return `Expires: ${expiry} • ${d}`;
  }
  return `Expires: ${expiry}`;
}
