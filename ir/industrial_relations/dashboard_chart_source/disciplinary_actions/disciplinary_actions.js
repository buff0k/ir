// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.dashboards.chart_sources["Disciplinary Actions"] = {
  method:
    "ir.industrial_relations.dashboard_chart_source.disciplinary_actions.disciplinary_actions.get",
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
