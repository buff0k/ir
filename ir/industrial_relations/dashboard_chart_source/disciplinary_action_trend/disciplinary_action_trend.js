// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.provide("frappe.dashboards.chart_sources");

frappe.dashboards.chart_sources["Disciplinary Action Trend"] = {
    method: "ir.industrial_relations.dashboard_chart_source.disciplinary_action_trend.disciplinary_action_trend.get",
    filters: []
};