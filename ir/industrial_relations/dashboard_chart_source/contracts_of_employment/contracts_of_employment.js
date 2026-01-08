// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.dashboards.chart_sources["Contracts of Employment"] = {
  method:
    "ir.industrial_relations.dashboard_chart_source.contracts_of_employment.contracts_of_employment.get",
  filters: [
    {
      fieldname: "branch",
      label: __("Site"),
      fieldtype: "Link",
      options: "Branch",
      reqd: 0
    }
  ]
};
