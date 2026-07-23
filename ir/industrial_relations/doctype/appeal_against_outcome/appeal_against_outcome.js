// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SUCCESSFUL_DECISIONS = ["Upheld", "Partially Upheld"];

frappe.ui.form.on("Appeal Against Outcome", {
    setup(frm) {
        frm.set_query("ir_intervention", () => ({
            filters: {
                name: [
                    "in",
                    ["Disciplinary Action", "Incapacity Proceedings", "Poor Performance"],
                ],
            },
        }));
    },

    refresh: function(frm) {
        if (frappe.user.has_role("IR Manager")) {
            frm.add_custom_button(__('Actions'), function() {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

            frm.page.add_inner_button(__('Write Outcome Report'), function() {
                create_written_outcome(frm);
            }, 'Actions');

            if (
                frm.doc.docstatus === 1 &&
                SUCCESSFUL_DECISIONS.includes(frm.doc.appeal_decision)
            ) {
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
                    make_vsp_appeal(frm);
                }, 'Actions');
            }
        }

        if (frm.doc.linked_intervention && !frm.doc.linked_intervention_processed) {
            frm.trigger('linked_intervention');
        }

        render_linked_docs(frm);
    },

    after_save: function(frm) {
        render_linked_docs(frm);
    },

    ir_intervention(frm) {
        frm.set_value('linked_intervention', '');
        frm.set_value('linked_intervention_processed', 0);
    },

    linked_intervention: function(frm) {
        if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) {
            return;
        }

        frappe.call({
            method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.fetch_intervention_data',
            args: {
                ir_intervention: frm.doc.ir_intervention,
                linked_intervention: frm.doc.linked_intervention,
            },
            callback: function(r) {
                if (!r.message) {
                    return;
                }
                const data = r.message;

                frm.doc.employee = data.employee || '';
                frm.doc.names = data.names || '';
                frm.doc.coy = data.coy || '';
                frm.doc.position = data.position || '';
                frm.doc.company = data.company || '';
                frm.doc.outcome = data.outcome || '';
                ['employee', 'names', 'coy', 'position', 'company', 'outcome'].forEach(f => frm.refresh_field(f));

                if (frm.fields_dict.details_of_incapacity) {
                    frm.set_value('type_of_incapacity', data.type_of_incapacity || '');
                    frm.set_value('details_of_incapacity', data.details_of_incapacity || '');
                }
                if (frm.fields_dict.performance_details) {
                    frm.set_value('performance_details', data.performance_details || '');
                }

                frm.clear_table('dismissal_charges');
                (data.dismissal_charges || []).forEach(function(row) {
                    let child = frm.add_child('dismissal_charges');
                    child.indiv_charge = row.indiv_charge;
                });
                frm.refresh_field('dismissal_charges');

                frm.clear_table('disciplinary_history');
                (data.disciplinary_history || []).forEach(function(row) {
                    let child = frm.add_child('disciplinary_history');
                    child.disc_action = row.disc_action;
                    child.date = row.date;
                    child.sanction = row.sanction;
                    child.charges = row.charges;
                });
                frm.refresh_field('disciplinary_history');

                frm.clear_table('previous_incapacity_outcomes');
                (data.previous_incapacity_outcomes || []).forEach(function(row) {
                    let child = frm.add_child('previous_incapacity_outcomes');
                    child.incap_proc = row.incap_proc;
                    child.date = row.date;
                    child.sanction = row.sanction;
                    child.incap_details = row.incap_details;
                });
                frm.refresh_field('previous_incapacity_outcomes');

                frm.clear_table('previous_performance_outcomes');
                (data.previous_performance_outcomes || []).forEach(function(row) {
                    frm.add_child('previous_performance_outcomes', row);
                });
                frm.refresh_field('previous_performance_outcomes');

                frm.set_value('linked_intervention_processed', 1);
            }
        });
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
        if (!frm.doc.appeal_decision || frm.doc.appeal_decision === 'Pending') {
            frappe.msgprint(__('Select the Appeal Decision before submitting.'));
            frappe.validated = false;
        }
    }
});

function render_linked_docs(frm) {
    if (!frm.fields_dict.linked_docs) return;
    frappe.require("/assets/ir/css/ir_ui.css");

    if (frm.is_new() || frm.doc.__islocal) {
        frm.fields_dict.linked_docs.$wrapper.html(
            '<div class="ir-linked-docs"><div class="ir-linked-docs__empty">' +
            __('Linked documents will appear here once the record is saved.') +
            '</div></div>',
        );
        return;
    }

    frappe.call({
        method: 'ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.get_linked_docs_html',
        args: { appeal_name: frm.doc.name },
        callback(r) {
            frm.fields_dict.linked_docs.$wrapper.html(r.message || '');
        },
    });
}

function create_written_outcome(frm) {
    frappe.call({
        method: "ir.industrial_relations.doctype.written_outcome.written_outcome.create_written_outcome",
        args: {
            source_name: frm.doc.name,
            source_doctype: frm.doctype
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
    if (
        frm.doc.docstatus === 1 &&
        SUCCESSFUL_DECISIONS.includes(frm.doc.appeal_decision) &&
        frm.doc.linked_amended_intervention
    ) {
        return { source_name: frm.doc.linked_amended_intervention, source_doctype: frm.doc.ir_intervention };
    }
    if (frm.doc.ir_intervention && frm.doc.linked_intervention) {
        return { source_name: frm.doc.linked_intervention, source_doctype: frm.doc.ir_intervention };
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
