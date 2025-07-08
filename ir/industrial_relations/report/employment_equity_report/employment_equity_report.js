// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Employment Equity Report"] = {
  filters: [
    {
      fieldname: "company",
      label: "Company",
      fieldtype: "Link",
      options: "Company",
      reqd: 1,
      default: frappe.defaults.get_default("company") || frappe.sys_defaults.company
    },
    {
      fieldname: "country",
      label: "Country (RSA)",
      fieldtype: "Link",
      options: "Country",
      reqd: 1,
      default: frappe.defaults.get_default("country") || "South Africa"
    }
  ],

  onload: function(report) {
    report.page.add_inner_button("Download XLSX", function() {
      const filters = report.get_values();
      const company = filters.company;
      const country = filters.country;
      const url = `/api/method/ir.industrial_relations.report.employment_equity_report.employment_equity_report.download_eea2_xlsx?company=${company}&country=${country}`;
      window.open(url);
    });
  }
};
