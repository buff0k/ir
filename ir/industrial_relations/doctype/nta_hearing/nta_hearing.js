// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('NTA Hearing', {
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
                method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_disciplinary_action_data',
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

                        frm.clear_table('nta_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('nta_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('nta_charges');

                        // Update applied_rights field
                        frm.set_value('applied_rights', 'Disciplinary Hearing');
                        frm.trigger('applied_rights'); // Trigger the applied_rights function to populate child table
                        
                        // Set the flag to prevent refresh loop
                        frm.set_value('linked_disciplinary_action_processed', true);
                        
                    }
                }
            });
        }
    },

    linked_incapacity_proceeding: function(frm) {
        if (frm.doc.linked_incapacity_proceeding && !frm.doc.linked_incapacity_proceeding_processed) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_incpacity_proceeding_data',
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
                        frm.doc.type_of_incapacity = data.type_of_incapacity || '';
                        frm.set_value('details_of_incapacity', data.details_of_incapacity || '');

                        frm.refresh_field('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');
                        frm.refresh_field('type_of_incapacity');
                        frm.refresh_field('details_of_incapacity');

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

                        // Update applied_rights field
                        frm.set_value('applied_rights', 'Incapacity');
                        frm.trigger('applied_rights'); // Trigger the applied_rights function to populate child table

                        // Set the processed flag
                        frm.set_value('linked_incapacity_proceeding_processed', true);

                    }
                }
            });
        }
    },

    chairperson: function(frm) {
        if (frm.doc.chairperson) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_chairperson_name',
                args: {
                    employee: frm.doc.chairperson
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('chairperson_name', r.message.employee_name || '');
                    }
                }
            });
        }
    },

    complainant: function(frm) {
        if (frm.doc.complainant) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_chairperson_name',
                args: {
                    employee: frm.doc.complainant
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('compl_name', r.message.employee_name || '');
                    }
                }
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_company_letter_head',
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
        if (!frm.doc.signed_nta) {
            frappe.msgprint(__('You cannot submit this document untill you have attached a signed copy of the NTA'));
            frappe.validated = false;
        }
    }
});
