// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hearing Cancellation Form", {
    refresh: function(frm) {
        // Check the flags before triggering the handler
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        } else if (frm.doc.linked_incapacity_proceeding && !frm.doc.linked_incapacity_proceeding_processed) {
            frm.trigger('linked_incapacity_proceeding');
        }
    },
    
    linked_disciplinary_action: function(frm) {
        if (frm.doc.linked_disciplinary_action) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.fetch_disciplinary_action_data',
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

                        frm.clear_table('ng_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('ng_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('ng_charges');
                        // Set the flag to prevent refresh loop
                        frm.set_value('linked_disciplinary_action_processed', true);
                    }
                }
            });
        }
    },

    linked_incapacity_proceeding: function(frm) {
        if (frm.doc.linked_incapacity_proceeding) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.fetch_incapacity_proceeding_data',
                args: {
                    incapacity_proceeding: frm.doc.linked_incapacity_proceeding
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;

                        // Update fields
                        frm.doc.employee = data.accused || '';
                        frm.doc.names = data.accused_name || '';
                        frm.doc.coy = data.accused_coy || '';
                        frm.doc.position = data.accused_pos || '';
                        frm.doc.company = data.company || '';
                        frm.set_value('details_of_incapacity', data.details_of_incapacity || '');

                        frm.refresh_field('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');

                        // Update child tables
                        frm.clear_table('previous_incapacity_outcomes');
                        $.each(data.previous_incapacity_outcomes, function(_, row) {
                            let child = frm.add_child('previous_incapacity_outcomes');
                            child.incap_proc = row.incap_proc;
                            child.date = row.date;
                            child.sanction = row.sanction;
                            child.incap_details = row.incap_details;
                        });
                        frm.refresh_field('previous_incapacity_outcomes');

                        // Set the processed flag
                        frm.set_value('linked_incapacity_proceeding_processed', true);

                    }
                }
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.fetch_company_letter_head',
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

    authorized_by: function(frm) {
        if (frm.doc.authorized_by) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.fetch_authorizor_names',
                args: {
                    authorized_by: frm.doc.authorized_by,
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('auth_names', r.message.auth_names);
                    }
                }
            });
        }
    }
});