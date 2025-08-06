// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Pay Deduction Form', {
    refresh: function(frm) {
        // Check the flag before triggering the handler
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        }
    },
    
    linked_disciplinary_action: function(frm) {
        if (frm.doc.linked_disciplinary_action) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.fetch_disciplinary_action_data',
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

                        frm.clear_table('ded_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('ded_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('ded_charges');

                        // Update applied_rights field
                        frm.set_value('applied_rights', 'Pay Deduction');
                        frm.trigger('applied_rights'); // Trigger the applied_rights function to populate child table

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
                method: 'ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.fetch_company_letter_head',
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
        let linked_doc_name = frm.doc.linked_disciplinary_action;
        let linked_doctype = 'Disciplinary Action';

        if (linked_doc_name) {
            console.log(`Fetching outcome for linked document: ${linked_doc_name}`); // Debug log

            frappe.call({
                method: 'ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.get_linked_outcome',
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

        if (!frm.doc.attached_signed_pay_deduction) {
            frappe.msgprint(__('You must attach the signed pay deduction before submitting.'));
            frappe.validated = false;
            return;
        }

        if (frm.__confirmed_submit) {
            console.log('Submit already confirmed'); // Debug log
            return;
        }

        let linked_doc_name = frm.doc.linked_disciplinary_action;
        let linked_doctype = 'Disciplinary Action';

        if (linked_doc_name) {
            console.log(`Fetching outcome for linked document: ${linked_doc_name}`); // Debug log

            frappe.call({
                method: 'ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.get_linked_outcome',
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