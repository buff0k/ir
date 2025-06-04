// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Site Organogram', {
    // Auto-set location if it matches branch
    branch: function(frm) {
        if (frm.doc.branch) {
            frappe.call({
                method: 'frappe.client.get_list',
                args: {
                    doctype: 'Location',
                    filters: { name: frm.doc.branch },
                    limit_page_length: 1
                },
                callback: function(r) {
                    frm.set_value('location', r.message.length > 0 ? frm.doc.branch : '');
                }
            });
        }
    },

    setup: function(frm) {
        // Employee field filter based on parent branch
        frm.fields_dict.employee_list.grid.get_field('employee').get_query = function(doc, cdt, cdn) {
            let parent = frm.doc;
            return {
                filters: {
                    branch: parent.branch || ''
                }
            };
        };

        // Asset field filter based on parent location
        frm.fields_dict.employee_list.grid.get_field('asset').get_query = function(doc, cdt, cdn) {
            let parent = frm.doc;
            return {
                filters: {
                    location: parent.location || ''
                }
            };
        };
    },

    onload: function(frm) {
        frm.fields_dict['employee_list'].grid.wrapper.find('.grid-add-row').hide();
    }
});

// Child Table Logic
frappe.ui.form.on('Site Organogram Details', {
    employee: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Rule 1: Prevent duplicate employee
        let dup = frm.doc.employee_list.filter(r => r.employee === row.employee);
        if (row.employee && dup.length > 1) {
            frappe.msgprint(`Employee ${row.employee} is already assigned.`);
            frappe.model.set_value(cdt, cdn, 'employee', null);
            return;
        }

        // Auto-fill employee_name
        if (row.employee) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Employee',
                    name: row.employee
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'employee_name', r.message.employee_name);
                    }
                }
            });
        }
    },

    asset: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Auto-fill asset_name
        if (row.asset) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'Asset',
                    name: row.asset
                },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(cdt, cdn, 'asset_name', r.message.asset_name);
                    }
                }
            });
        }
    },

    shift: function(frm, cdt, cdn) {
        validate_combination(frm, cdt, cdn);
    },

    designation: function(frm, cdt, cdn) {
        validate_combination(frm, cdt, cdn);
    },

    asset_name: function(frm, cdt, cdn) {
        validate_combination(frm, cdt, cdn);
    }
});

function validate_combination(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    if (!row.designation || !row.asset || !row.shift) return;

    let duplicates = frm.doc.employee_list.filter(r =>
        r.name !== row.name &&
        r.designation === row.designation &&
        r.asset === row.asset &&
        r.shift === row.shift
    );

    if (duplicates.length > 0) {
        frappe.msgprint(`The combination of Designation "${row.designation}", Asset "${row.asset}" and Shift "${row.shift}" already exists.`);
        frappe.model.set_value(cdt, cdn, 'shift', null);  // or whichever field the user last updated
    }
}
