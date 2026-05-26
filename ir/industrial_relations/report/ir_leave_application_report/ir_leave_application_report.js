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
            fieldname: "leave_type",
            label: __("Leave Type"),
            fieldtype: "Link",
            options: "Leave Type"
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
        }
    ],

    onload: function(report) {
        report.page.add_inner_button(__("Export VIP Leave File"), function() {
            frappe.call({
                method: "ir.industrial_relations.report.ir_leave_application_report.ir_leave_application_report.export_vip_leave_file",
                args: {
                    filters: report.get_values()
                },
                callback: function(r) {
                    if (!r.message) {
                        frappe.msgprint(__("No export data returned."));
                        return;
                    }

                    const blob = new Blob([r.message.content], { type: "text/csv;charset=utf-8" });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");

                    a.href = url;
                    a.download = r.message.filename || "vip_leave_export.csv";
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                }
            });
        });
    }
};