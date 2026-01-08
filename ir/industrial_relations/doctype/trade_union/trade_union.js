// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Union Shop Stewards', {
    ss_id: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.ss_id) {
            frappe.call({
                method: "ir.industrial_relations.doctype.trade_union.trade_union.get_employee_details",
                args: {
                    ss_id: row.ss_id
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'ss_name', r.message.employee_name);
                        frappe.model.set_value(cdt, cdn, 'ss_designation', r.message.designation);
                        frappe.model.set_value(cdt, cdn, 'ss_branch', r.message.branch);
                    }
                }
            });
        }
    }
});
