// Copyright (c) 2026, BuFf0k and contributors
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
    },
    {
      fieldname: "disabled",
      label: "Disabled Only",
      fieldtype: "Check",
      reqd: 0
    },
    {
      fieldname: "branch",
      label: "Site",
      fieldtype: "Link",
      options: "Branch",
      reqd: 0,
      default: ""
    }
  ],

  onload: function(report) {
    report.page.add_inner_button("Download XLSX", function() {
      const filters = report.get_values();
      const company  = filters.company;
      const country  = filters.country;
      const disabled = filters.disabled ? 1 : 0;
      const branch = filters.branch || "";
      const url = `/api/method/ir.industrial_relations.report.employment_equity_report.employment_equity_report.download_eea2_xlsx?company=${encodeURIComponent(company)}&country=${encodeURIComponent(country)}&disabled=${disabled}`;
      window.open(url);
    });
  }
};
