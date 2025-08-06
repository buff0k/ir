// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Appeal Against Outcome", {
 	refresh: function(frm) {
        if (frappe.user.has_role("IR Manager")) {
            frm.add_custom_button(__('Actions'), function() {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

            frm.page.add_inner_button(__('Issue NTA'), function() {
                make_nta_appeal(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Write Outcome Report'), function() {
                create_written_outcome(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Warning'), function() {
                make_warning_form_appeal(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Not Guilty'), function() {
                make_not_guilty_form_appeal(frm);
            }, 'Actions');
                
            frm.page.add_inner_button(__('Issue Suspension'), function() {
                make_suspension_form_appeal(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Demotion'), function() {
                make_demotion_form_appeal(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Pay Deduction'), function() {
                make_pay_deduction_form_appeal(frm);
            }, 'Actions');
        
            frm.page.add_inner_button(__('Issue Pay Reduction'), function() {
                make_pay_reduction_form_appeal(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Dismissal'), function() {
                make_dismissal_form_appeal(frm);
            }, 'Actions');
        
            frm.page.add_inner_button(__('Issue VSP'), function() {
                make_vsp(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Cancel Appeal Enquiry'), function() {
                cancel_appeal(frm);
            }, 'Actions');
        }
    
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
                method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.fetch_disciplinary_action_data',
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
                        frm.doc.outcome = data.outcome || '';
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
                        frm.set_value('details_of_incapacity', data.details_of_incapacity || '');
                        frm.doc.outcome = data.outcome || '';

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

    before_submit: function(frm) {
        if (!frm.doc.signed_nta) {
            frappe.msgprint(__('You cannot submit this document untill you have attached a signed copy of the NTA'));
            frappe.validated = false;
        }
    }
});

function fetch_default_letter_head(frm, company) {
    if (company) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_default_letter_head',
            args: {
                company: company
            },
            callback: function(res) {
                if (res.message) {
                    frm.set_value('letter_head', res.message);
                } else {
                    frm.set_value('letter_head', '');
                }
            }
        });
    }
}

function fetch_disciplinary_history(frm, accused) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_disciplinary_history',
        args: {
            accused: accused,
            current_doc_name: frm.doc.name
        },
        callback: function(res) {
            if (res.message) {
                frm.clear_table('previous_disciplinary_outcomes');
                res.message.forEach(function(row) {
                    let child = frm.add_child('previous_disciplinary_outcomes');
                    child.disc_action = row.disc_action;
                    child.date = row.date;
                    child.sanction = row.sanction;
                    child.charges = row.charges;
                });
                frm.refresh_field('previous_disciplinary_outcomes');
            }
        }
    });
}

function fetch_linked_documents(frm) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_linked_documents',
        args: {
            doc_name: frm.doc.name
        },
        callback: function(res) {
            if (res.message) {
                for (let field in res.message.linked_documents) {
                    frm.set_value(field, res.message.linked_documents[field].join(', '));
                }
                if (res.message.latest_outcome) {
                    frm.set_value('outcome', res.message.latest_outcome);
                    frm.set_value('outcome_date', res.message.latest_outcome_date);
                }
            }
        }
    });
}

function fetch_outcome_dates(frm) {
    // Call the new server function to update outcome_start and outcome_end
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.update_outcome_dates',
        args: {
            doc_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                frm.set_value('outcome_start', r.message.outcome_start || '');
                frm.set_value('outcome_end', r.message.outcome_end || ''); // Ensure outcome_end is set to an empty string if not present
                frm.refresh_fields(); // Refresh fields to show updated outcome dates
                }
        }
     });
}

function fetch_additional_linked_documents(frm) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_additional_linked_documents',
        args: {
            doc_name: frm.doc.name
        },
        callback: function(r) {
            if (r.message) {
                if (r.message.linked_nta && !frm.doc.linked_nta) {
                    frm.set_value('linked_nta', r.message.linked_nta);
                }
                if (r.message.linked_outcome && !frm.doc.linked_outcome) {
                    frm.set_value('linked_outcome', r.message.linked_outcome);
                }
            }
        }
    });
}

function make_nta_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.nta_hearing.nta_hearing.make_nta_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating NTA Appeal Enquiry ...")
    });
}

function create_written_outcome(frm) {
    frappe.call({
        method: "ir.industrial_relations.doctype.written_outcome.written_outcome.create_written_outcome",
        args: {
            source_name: frm.doc.name,  // ✅ Pass the document ID (e.g. DISC-000376)
            source_doctype: frm.doctype  // ✅ Pass the document type (e.g. "Disciplinary Action")
        },
        freeze: true,
        freeze_message: __("Creating Written Outcome Report ..."),
        callback: function(r) {
            if (!r.exc) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", "Written Outcome", r.message.name);
            }
        }
    });
}

function make_not_guilty_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.not_guilty_form.not_guilty_form.make_not_guilty_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Not Guilty Form ...")
    });
}

function make_warning_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.warning_form.warning_form.make_warning_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Warning Form ...")
    });
}

function make_suspension_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Suspension Form ...")
    });
}

function make_demotion_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Demotion Form ...")
    });
}

function make_pay_deduction_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Pay Deduction Form ...")
    });
}

function make_pay_reduction_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.make_pay_reduction_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Pay Reduction Form ...")
    });
}

function make_dismissal_form_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating Dismissal Form ...")
    });
}

function make_vsp_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Creating VSP ...")
    });
}

function cancel_appeal(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_appeal",
        frm: frm,
        args: {
            linked_appeal: frm.doc.name
        },
        freeze_message: __("Generating Cancellation Form ...")
    });
}
