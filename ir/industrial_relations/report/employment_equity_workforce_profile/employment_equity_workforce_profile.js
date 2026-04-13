// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Employment Equity Workforce Profile"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			reqd: 1,
			default: frappe.defaults.get_user_default("Company")
		},
		{
			fieldname: "as_at_date",
			label: __("As At Date"),
			fieldtype: "Date",
			reqd: 1,
			default: frappe.datetime.get_today()
		},
		{
			fieldname: "employment_category",
			label: __("Employment Category"),
			fieldtype: "Select",
			options: ["All", "Permanent", "Temporary"],
			default: "All"
		},
		{
			fieldname: "occupational_level",
			label: __("Occupational Level"),
			fieldtype: "Link",
			options: "Occupational Level"
		},
		{
			fieldname: "include_suspended",
			label: __("Include Suspended Employees"),
			fieldtype: "Check",
			default: 1
		},
		{
			fieldname: "show_detailed_rows",
			label: __("Show Detailed Rows"),
			fieldtype: "Check",
			default: 0
		}
	]
};