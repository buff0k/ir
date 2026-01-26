// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Monthly Attendance"] = {
  filters: [
    {
      fieldname: "month",
      label: __("Month (YYYY-MM)"),
      fieldtype: "Data",
      reqd: 1,
      default: frappe.datetime.get_today().slice(0, 7)
    },
    {
      fieldname: "site",
      label: __("Site (Branch)"),
      fieldtype: "Select",
      reqd: 1
    },
    {
      fieldname: "show_totals",
      label: __("Show Totals"),
      fieldtype: "Check",
      default: 0,
      hidden: 1
    }
  ],

  onload: function (report) {
    frappe.call({
      method: "frappe.client.get_list",
      args: {
        doctype: "Employee",
        fields: ["branch"],
        filters: [["branch", "!=", ""]],
        limit_page_length: 1000
      },
      callback: function (r) {
        if (!r.message) return;

        const branches = [...new Set(
          r.message.map(row => row.branch).filter(v => v)
        )].sort();

        const site_filter = report.get_filter("site");
        site_filter.df.options = branches.join("\n");
        site_filter.refresh();
      }
    });

    report.page.add_action_item(__("Show Totals"), function () {
      const f = report.get_filter("show_totals");
      const new_val = f.get_value() ? 0 : 1;
      f.set_value(new_val);
      report.refresh();
    });
  },

  formatter: function (value, row, column, data, default_formatter) {
    value = default_formatter(value, row, column, data);
    if (!data || !column.fieldname) return value;

    const isTotalsRow = ((data.name || "").toUpperCase() === "TOTALS");

    if (isTotalsRow) {
      return `<div style="font-weight:bold;">${value}</div>`;
    }

    if (column.fieldname.startsWith("d_")) {
      const raw = data[column.fieldname];
      const status = data["status__" + column.fieldname];

      const isWeekend = (parseInt(data["is_weekend__" + column.fieldname] || "0", 10) === 1);
      const isHoliday = (parseInt(data["is_holiday__" + column.fieldname] || "0", 10) === 1);
      const isOvertime = (parseInt(data["is_overtime__" + column.fieldname] || "0", 10) === 1);

      const isUndertime = (parseInt(data["is_undertime__" + column.fieldname] || "0", 10) === 1);
      const isNoShift = (parseInt(data["is_no_shift__" + column.fieldname] || "0", 10) === 1);

      if (status === "Absent") {
        return `<div style="background:#ff3b30; font-weight:bold; text-align:center; padding:4px;">A</div>`;
      }

      if (status === "Leave") {
        return `<div style="background:#b3e5fc; font-weight:bold; text-align:center; padding:4px;">L</div>`;
      }

      let style = "text-align:center; padding:4px;";

      if (isHoliday) style += "background:#c8f7c5; font-weight:bold;";
      else if (isWeekend) style += "background:#ffeb3b;";

      if (!isWeekend && !isHoliday && isNoShift) {
        style += "background:#c0c0c0; font-weight:bold;";
      }

      if (!isWeekend && !isHoliday && isUndertime) {
        style += "background:#f8c8dc; font-weight:bold;";
      }

      if (isOvertime) {
        style += "background:brown; color:white; font-weight:bold;";
      }

      return `<div style="${style}">${raw || ""}</div>`;
    }

    return value;
  }
};