// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dismissal Form', {
    refresh: function(frm) {
        // Check the flag before triggering the handler
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        }
    },
    
    linked_disciplinary_action: function(frm) {
        if (frm.doc.linked_disciplinary_action) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.dismissal_form.dismissal_form.fetch_disciplinary_action_data',
                args: {
                    disciplinary_action: frm.doc.linked_disciplinary_action
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;

                        // Directly update the doc and refresh fields without triggering events
                        frm.doc.employee = data.accused || '';
                        frm.doc.names = data.accused_name || '';
                        frm.doc.coy = data.accused_coy || '';
                        frm.doc.position = data.accused_pos || '';
                        frm.doc.company = data.company || '';

                        frm.refresh_field('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');

                        // Update child tables
                        frm.clear_table('disciplinary_history');
                        $.each(data.previous_disciplinary_outcomes, function(_, row) {
                            let child = frm.add_child('disciplinary_history');
                            child.disc_action = row.disc_action;
                            child.date = row.date;
                            child.sanction = row.sanction;
                            child.charges = row.charges;
                        });
                        frm.refresh_field('disciplinary_history');

                        frm.clear_table('dismissal_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('dismissal_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('dismissal_charges');
                        // Set the flag to prevent refresh loop
                        frm.set_value('linked_disciplinary_action_processed', true);
                    }
                }
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.dismissal_form.dismissal_form.fetch_company_letter_head',
                args: {
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message) {
                        frm.doc.letter_head = r.message.letter_head || '';
                        frm.refresh_field('letter_head');
                    }
                }
            });
        }
    },

    applied_rights: function(frm) {
        if (frm.doc.applied_rights) {
            frappe.model.with_doc('Employee Rights', frm.doc.applied_rights, function() {
                let doc = frappe.get_doc('Employee Rights', frm.doc.applied_rights);
                frm.clear_table('employee_rights');
                $.each(doc.applicable_rights, function(_, row) {
                    let child = frm.add_child('employee_rights');
                    child.individual_right = row.individual_right;
                });
                frm.refresh_field('employee_rights');
            });
        }
    },

    before_submit: function(frm) {
        if (!frm.doc.signed_dismissal) {
            frappe.msgprint(__('You cannot submit this document untill you have attached a signed copy of the Dismissal'));
            frappe.validated = false;
        }
    }
});