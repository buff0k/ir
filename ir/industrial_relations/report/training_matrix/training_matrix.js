// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Training Matrix"] = {
  freeze: true,
  freeze_columns: 4, // Tracking, Employee, Employee Name, Employee ID Number

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
      fieldname: "induction_type",
      label: __("Induction Type"),
      fieldtype: "Select",
      options: ["", "Training", "Licence", "Qualification", "Authorisation"],
    },
    {
      fieldname: "employee_status",
      label: __("Employee Status"),
      fieldtype: "Select",
      options: ["All", "Active", "Inactive", "Suspended", "Left"],
      default: "Active",
    },
  ],

  // Deliberately a plain Query Report - no custom formatter/CSS/cell
  // height. The visual (status cards, links, the compliance bar chart)
  // lives on the Training Compliance Dashboard page now, which calls
  // get_training_matrix_payload()/get_compliance_summary() for that; this
  // report stays a simple grid over the same execute() data, mainly for
  // ad-hoc filtering and the .xlsx export below.
  onload: function (report) {
    if (report && report.page) {
      // A dropdown (not a single button) so future export formats can be
      // added as siblings under the same "Download in .xlsx Format" group,
      // without touching this call site again.
      report.page.add_inner_button(
        __("Neutral Format"),
        function () {
          download_training_matrix_excel();
        },
        __("Download in .xlsx Format"),
      );
    }
  },
};


function download_training_matrix_excel() {
  const report = frappe.query_report;
  if (!report) return;

  const filters = report.get_filter_values ? report.get_filter_values() : {};

  frappe.call({
    method: "ir.industrial_relations.report.training_matrix.training_matrix.download_training_matrix_excel",
    args: {
      filters: filters,
    },
    freeze: true,
    freeze_message: __("Building Excel file..."),
    callback: function (r) {
      if (!r || !r.message || !r.message.content) return;

      const filename = r.message.filename || "training_matrix.xlsx";
      const mime =
        r.message.type ||
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";

      download_base64_file(r.message.content, filename, mime);
    },
  });
}


function download_base64_file(base64_content, filename, mime_type) {
  const byte_chars = atob(base64_content);
  const byte_numbers = new Array(byte_chars.length);

  for (let i = 0; i < byte_chars.length; i++) {
    byte_numbers[i] = byte_chars.charCodeAt(i);
  }

  const byte_array = new Uint8Array(byte_numbers);
  const blob = new Blob([byte_array], {
    type: mime_type,
  });

  const url = window.URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  window.URL.revokeObjectURL(url);
}
