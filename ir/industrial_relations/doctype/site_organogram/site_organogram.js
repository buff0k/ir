// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Site Organogram', {
    onload_post_render: function(frm) {
        if (frm.fields_dict.employee_list?.grid) {
            frm.fields_dict.employee_list.grid.wrapper.find('.grid-add-row').hide();
        }
    },

    branch: function(frm) {
        if (!frm.doc.branch) return;
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'Location',
                filters: { name: frm.doc.branch },
                limit_page_length: 1
            },
            callback: function(r) {
                frm.set_value('location', r.message.length ? frm.doc.branch : '');
                render_organogram_ui(frm);
            }
        });
    },

    location: function(frm) {
        render_organogram_ui(frm);
    },

    asset_categories: function(frm) {
        render_organogram_ui(frm);
    },

    refresh: function(frm) {
        if (frm.doc.branch && frm.doc.location) {
            render_organogram_ui(frm);
        }
    },

    setup: function(frm) {
        frm.fields_dict.employee_list.grid.get_field('employee').get_query = () => ({
            filters: { branch: frm.doc.branch || '' }
        });
        frm.fields_dict.employee_list.grid.get_field('asset').get_query = () => ({
            filters: { location: frm.doc.location || '' }
        });
    }
});

frappe.ui.form.on('Site Organogram Details', {
    employee: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.employee) return;

        let dup = frm.doc.employee_list.filter(r => r.employee === row.employee);
        if (dup.length > 1) {
            frappe.msgprint(`Employee ${row.employee} is already assigned.`);
            frappe.model.set_value(cdt, cdn, 'employee', null);
            return;
        }

        frappe.call({
            method: 'frappe.client.get',
            args: { doctype: 'Employee', name: row.employee },
            callback: r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'employee_name', r.message.employee_name);
                    frappe.model.set_value(cdt, cdn, 'designation', r.message.designation);
                }
            }
        });
    },

    asset: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.asset) return;

        frappe.call({
            method: 'frappe.client.get',
            args: { doctype: 'Asset', name: row.asset },
            callback: r => {
                if (r.message) {
                    frappe.model.set_value(cdt, cdn, 'asset_name', r.message.asset_name);
                }
            }
        });
    },

    shift: validate_combination,
    designation: validate_combination,
    asset_name: validate_combination
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
        frappe.msgprint(`Duplicate role: "${row.designation}" for "${row.asset}" in "${row.shift}".`);
        frappe.model.set_value(cdt, cdn, 'shift', null);
    }
}
