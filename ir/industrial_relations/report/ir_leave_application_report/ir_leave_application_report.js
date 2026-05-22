// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["IR Leave Application Report"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        },
        {
            fieldname: "application_status",
            label: __("Application Status"),
            fieldtype: "Select",
            options: "\nOpen\nApproved\nRejected\nCancelled",
            default: "Approved"
        },
        {
            fieldname: "branch",
            label: __("Branch"),
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "leave_type",
            label: __("Leave Type"),
            fieldtype: "Link",
            options: "Leave Type"
        }
    ]
};