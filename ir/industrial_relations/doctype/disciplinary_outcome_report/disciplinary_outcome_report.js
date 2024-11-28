// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Disciplinary Outcome Report", {
    refresh: function (frm) {
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        }

        frm.toggle_display(
            [
                'make_warning_form',
                'make_not_guilty_form',
                'make_suspension_form',
                'make_demotion_form',
                'make_pay_deduction_form',
                'make_dismissal_form'
            ],
            frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.workflow_state !== 'Submitted'
        );

        if (frappe.user.has_role("IR Manager")) {
            frm.add_custom_button(__('Actions'), function () {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

            frm.page.add_inner_button(__('Issue Warning'), function () {
                make_warning_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Not Guilty'), function () {
                make_not_guilty_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Suspension'), function () {
                make_suspension_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Demotion'), function () {
                make_demotion_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Pay Deduction'), function () {
                make_pay_deduction_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Dismissal'), function () {
                make_dismissal_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue VSP'), function () {
                make_vsp(frm);
            }, 'Actions');
        }

        // Add "Compile Outcome" button
        frm.add_custom_button(__('Compile Outcome'), function () {
            compile_outcome(frm);
        }, __('Actions')).addClass('btn-primary');
    },

    linked_disciplinary_action: function(frm) {
        if (frm.doc.linked_disciplinary_action) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.fetch_disciplinary_action_data',
                args: {
                    disciplinary_action: frm.doc.linked_disciplinary_action
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;
                        frm.doc.employee = data.accused || '';
                        frm.doc.names = data.accused_name || '';
                        frm.doc.coy = data.accused_coy || '';
                        frm.doc.position = data.accused_pos || '';
                        frm.doc.company = data.company || '';
                        frm.doc.linked_nta = data.linked_nta || '';
                        frm.refresh_field('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');
                        frm.refresh_field('linked_nta');
                        frm.clear_table('disciplinary_history');
                        $.each(data.previous_disciplinary_outcomes, function(_, row) {
                            let child = frm.add_child('disciplinary_history');
                            child.disc_action = row.disc_action;
                            child.date = row.date;
                            child.sanction = row.sanction;
                            child.charges = row.charges;
                        });
                        frm.refresh_field('disciplinary_history');

                        frm.clear_table('outcome_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('outcome_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('outcome_charges');
                        frm.trigger('fetch_linked_fields');
                        frm.trigger('fetch_employee_names');
                        frm.set_value('linked_disciplinary_action_processed', true);
                        
                    }
                }
            });
        }
    },

    chairperson: function(frm) {
        frm.trigger('fetch_employee_names');
    },

    complainant: function(frm) {
        frm.trigger('fetch_employee_names');
    },

    fetch_employee_names: function(frm) {
        if (frm.doc.chairperson || frm.doc.complainant) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.fetch_employee_names',
                args: {
                    chairperson: frm.doc.chairperson,
                    complainant: frm.doc.complainant
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('chairperson_name', r.message.chairperson_name);
                        frm.set_value('complainant_name', r.message.complainant_name);
                    }
                }
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.fetch_company_letter_head',
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

    fetch_linked_fields: function(frm) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.fetch_linked_fields',
            args: {
                linked_nta: frm.doc.linked_nta,
                linked_disciplinary_action: frm.doc.linked_disciplinary_action
            },
            callback: function(r) {
                if (r.message) {
                    frm.set_value('chairperson', r.message.chairperson);
                    frm.set_value('complainant', r.message.complainant);
                }
            }
        });
    }
});

function make_warning_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.warning_form.warning_form.make_warning_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Warning Form ...")
    });
}

function make_not_guilty_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.not_guilty_form.not_guilty_form.make_not_guilty_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Not Guilty Form ...")
    });
}

function make_suspension_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Suspension Form ...")
    });
}

function make_demotion_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Demotion Form ...")
    });
}

function make_pay_deduction_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Pay Deduction Form ...")
    });
}

function make_dismissal_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating Dismissal Form ...")
    });
}

function make_vsp(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp",
        frm: frm,
        source_name: frm.doc.linked_disciplinary_action,
        freeze_message: __("Creating VSP ...")
    });
}

function compile_outcome(frm) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.compile_outcome',
        args: {
            docname: frm.doc.name
        },
        callback: function (r) {
            if (r.message) {
                frappe.msgprint(__('Outcome compiled successfully.'));
                frm.reload_doc();
            }
        }
    });
}