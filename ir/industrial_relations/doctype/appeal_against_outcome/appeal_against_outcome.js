// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt


frappe.ui.form.on("Appeal Against Outcome", {
 	refresh: function(frm) {
        if (frappe.user.has_role("IR Manager")) {
            frm.add_custom_button(__('Actions'), function() {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

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
        } else if (frm.doc.linked_poor_performance && !frm.doc.linked_poor_performance_processed) {
            frm.trigger('linked_poor_performance');
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
                method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.fetch_incpacity_proceeding_data',
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


    linked_poor_performance: function(frm) {
        if (frm.doc.linked_poor_performance && !frm.doc.linked_poor_performance_processed) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.fetch_poor_performance_data',
                args: { poor_performance: frm.doc.linked_poor_performance },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;
                        frm.doc.employee = data.employee || '';
                        frm.doc.names = data.employee_name || '';
                        frm.doc.coy = data.employee || '';
                        frm.doc.position = data.employee_designation || '';
                        frm.doc.company = data.company || '';
                        frm.set_value('performance_details', data.details_of_poor_performance || '');
                        ['employee', 'names', 'coy', 'position', 'company', 'performance_details'].forEach(f => frm.refresh_field(f));

                        if (frm.fields_dict.previous_performance_outcomes) {
                            frm.clear_table('previous_performance_outcomes');
                            (data.previous_performance_outcomes || []).forEach(row => {
                                let child = frm.add_child('previous_performance_outcomes');
                                child.performance_action = row.performance_action;
                                child.date = row.date;
                                child.charges = row.charges;
                                child.sanction = row.sanction;
                            });
                            frm.refresh_field('previous_performance_outcomes');
                        }

                        if (frm.fields_dict.applied_rights) {
                            frm.set_value('applied_rights', 'Poor Performance');
                            frm.trigger('applied_rights');
                        }

                        frm.set_value('linked_poor_performance_processed', true);
                    }
                }
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.fetch_company_letter_head',
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

function get_appeal_source(frm) {
    if (frm.doc.linked_disciplinary_action) {
        return { source_name: frm.doc.linked_disciplinary_action, source_doctype: "Disciplinary Action" };
    }
    if (frm.doc.linked_incapacity_proceeding) {
        return { source_name: frm.doc.linked_incapacity_proceeding, source_doctype: "Incapacity Proceedings" };
    }
    if (frm.doc.linked_poor_performance) {
        return { source_name: frm.doc.linked_poor_performance, source_doctype: "Poor Performance" };
    }
    frappe.msgprint(__("This Appeal is not linked to a Disciplinary Action, Incapacity Proceedings, or Poor Performance record."));
    return null;
}

function create_form_from_appeal(frm, method, target_doctype, freeze_message, extra_args = {}) {
    const source = get_appeal_source(frm);
    if (!source) return;

    frappe.call({
        method: method,
        args: {
            source_name: source.source_name,
            source_doctype: source.source_doctype,
            ...extra_args
        },
        freeze: true,
        freeze_message: __(freeze_message),
        callback: function(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", target_doctype, r.message.name);
            }
        }
    });
}

function make_not_guilty_form_appeal(frm) {
    // "Not Guilty Form" was migrated to "No Further Action Form"; omitting outcome_type
    // lets the server pick the source doctype's own not-guilty-equivalent default (NG/FIT/PI).
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.no_further_action_form.no_further_action_form.create_no_further_action_form",
        "No Further Action Form",
        "Creating No Further Action Form ...",
    );
}

function make_warning_form_appeal(frm) {
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.warning_form.warning_form.create_warning_form",
        "Warning Form",
        "Creating Warning Form ...",
    );
}

function make_suspension_form_appeal(frm) {
    const source = get_appeal_source(frm);
    if (!source) return;

    frappe.prompt(
        {
            fieldname: "suspension_nature",
            label: __("Suspension Nature"),
            fieldtype: "Select",
            options: ["Precautionary", "Punitive"],
            reqd: 1,
        },
        function(values) {
            frappe.call({
                method: "ir.industrial_relations.doctype.suspension_form.suspension_form.create_suspension_form",
                args: {
                    source_name: source.source_name,
                    source_doctype: source.source_doctype,
                    suspension_nature: values.suspension_nature,
                },
                freeze: true,
                freeze_message: __("Creating Suspension Form ..."),
                callback: function(r) {
                    if (!r.exc && r.message) {
                        frappe.model.sync(r.message);
                        frappe.set_route("Form", "Suspension Form", r.message.name);
                    }
                }
            });
        },
        __("Suspension Nature"),
        __("Create"),
    );
}

function make_demotion_form_appeal(frm) {
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.demotion_form.demotion_form.create_demotion_form",
        "Demotion Form",
        "Creating Demotion Form ...",
    );
}

function make_pay_deduction_form_appeal(frm) {
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.create_pay_deduction_form",
        "Pay Deduction Form",
        "Creating Pay Deduction Form ...",
    );
}

function make_pay_reduction_form_appeal(frm) {
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.create_pay_reduction_form",
        "Pay Reduction Form",
        "Creating Pay Reduction Form ...",
    );
}

function make_dismissal_form_appeal(frm) {
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.dismissal_form.dismissal_form.create_dismissal_form",
        "Dismissal Form",
        "Creating Dismissal Form ...",
    );
}

function make_vsp_appeal(frm) {
    const source = get_appeal_source(frm);
    if (!source) return;

    const method_by_doctype = {
        "Disciplinary Action": "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp",
        "Incapacity Proceedings": "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_incap",
        "Poor Performance": "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_performance",
    };

    frappe.call({
        method: method_by_doctype[source.source_doctype],
        args: { source_name: source.source_name },
        freeze: true,
        freeze_message: __("Creating VSP ..."),
        callback: function(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", "Voluntary Seperation Agreement", r.message.name);
            }
        }
    });
}

function cancel_appeal(frm) {
    // Hearing Cancellation Form is deprecated in favor of No Further Action Form.
    create_form_from_appeal(
        frm,
        "ir.industrial_relations.doctype.no_further_action_form.no_further_action_form.create_no_further_action_form",
        "No Further Action Form",
        "Generating Cancellation Form ...",
        { outcome_type: "CAN" },
    );
}
