// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.dashboards.chart_sources["Termination Forms"] = {
  method:
    "ir.industrial_relations.dashboard_chart_source.termination_forms.termination_forms.get",
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
