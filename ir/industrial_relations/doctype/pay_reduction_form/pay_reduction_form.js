// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Pay Reduction Form", {
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
                method: 'ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.fetch_disciplinary_action_data',
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
                        frm.set_value('applied_rights', 'Pay Reduction');
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
                method: 'ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.fetch_incpacity_proceeding_data',
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
                        frm.set_value('applied_rights', 'Pay Reduction');
                        frm.trigger('applied_rights'); // Trigger the applied_rights function to populate child table

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

    before_save: function(frm) {
        console.log('Running before_save'); // Debug log

        // Skip if already confirmed for this save
        if (frm.__confirmed_save) {
            console.log('Save already confirmed'); // Debug log
            return;
        }

        // Determine linked document
        let linked_doc_name = frm.doc.linked_disciplinary_action || frm.doc.linked_incapacity_proceeding;
        let linked_doctype = frm.doc.linked_disciplinary_action ? 'Disciplinary Action' : 'Incapacity Proceedings';

        if (linked_doc_name) {
            console.log(`Fetching outcome for linked document: ${linked_doc_name}`); // Debug log

            frappe.call({
                method: 'ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.get_linked_outcome',
                args: {
                    doc_name: linked_doc_name,
                    doctype: linked_doctype
                },
                callback: function(r) {
                    if (r.message) {
                        const { outcome, outcome_date } = r.message;

                        const outcome_str = outcome ? outcome.toString() : 'None';
                        const outcome_date_str = outcome_date ? frappe.datetime.str_to_user(outcome_date) : 'None';

                        if (!outcome && !outcome_date) {
                            console.log('No existing outcome, skipping confirmation'); // Debug log
                            frm.__confirmed_save = true;
                            frappe.validated = true;  // Allow save
                            frm.save();
                            return;
                        }

                        // Prompt for confirmation
                        let msg = `The linked document ${linked_doc_name} (${linked_doctype}) currently has an outcome: ${outcome_str} and outcome date: ${outcome_date_str}. These will be cleared upon saving. Do you want to proceed?`;

                        frappe.confirm(
                            msg,
                            function() {
                                console.log('User confirmed save'); // Debug log
                                frm.__confirmed_save = true;  // Set flag after confirmation
                                frappe.validated = true;  // Allow save
                                frm.save();
                            },
                            function() {
                                console.log('User canceled save'); // Debug log
                                frappe.msgprint(__('Save operation canceled.'));
                                frappe.validated = false;  // Block save
                            }
                        );
                    }
                }
            });

            console.log('Blocking save until confirmation'); // Debug log
            frappe.validated = false;  // Block save
        }
    },

    before_submit: function(frm) {
        console.log('Running before_submit'); // Debug log

        if (!frm.doc.signed_pay_reduction) {
            frappe.msgprint(__('You must attach the signed pay reduction before submitting.'));
            frappe.validated = false;
            return;
        }

        if (frm.__confirmed_submit) {
            console.log('Submit already confirmed'); // Debug log
            return;
        }

        let linked_doc_name = frm.doc.linked_disciplinary_action || frm.doc.linked_incapacity_proceeding;
        let linked_doctype = frm.doc.linked_disciplinary_action ? 'Disciplinary Action' : 'Incapacity Proceedings';

        if (linked_doc_name) {
            console.log(`Fetching outcome for linked document: ${linked_doc_name}`); // Debug log

            frappe.call({
                method: 'ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.get_linked_outcome',
                args: {
                    doc_name: linked_doc_name,
                    doctype: linked_doctype
                },
                callback: function(r) {
                    if (r.message) {
                        const { outcome, outcome_date } = r.message;

                        const outcome_str = outcome ? outcome.toString() : 'None';
                        const outcome_date_str = outcome_date ? frappe.datetime.str_to_user(outcome_date) : 'None';

                        if (!outcome && !outcome_date) {
                            console.log('No existing outcome, skipping confirmation for submit'); // Debug log
                            frm.__confirmed_submit = true;
                            frm.save({ action: 'submit' });
                            return;
                        }

                        let msg = `The linked document ${linked_doc_name} (${linked_doctype}) currently has an outcome: ${outcome_str} and outcome date: ${outcome_date_str}. These will be overwritten with demotion type: ${frm.doc.demotion_type} and outcome date: ${frm.doc.outcome_date}. Do you want to proceed?`;

                        frappe.confirm(
                            msg,
                            function() {
                                console.log('User confirmed submit'); // Debug log
                                frm.__confirmed_submit = true;
                                frm.save({ action: 'submit' });
                            },
                            function() {
                                frappe.msgprint(__('Submit operation canceled.'));
                                frappe.validated = false;  // Block submit
                            }
                        );
                    }
                }
            });

            console.log('Blocking submit until confirmation'); // Debug log
            frappe.validated = false;  // Block submit
        }
    }
});
