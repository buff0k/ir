// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disciplinary Action', {
    accused: function(frm) {
        if (frm.doc.accused) {
            fetch_employee_data(frm, frm.doc.accused, {
                'employee_name': 'accused_name',
                'employee': 'accused_coy',
                'designation': 'accused_pos',
                'company': 'company',
                'date_of_joining': 'engagement_date',
                'branch': 'branch'
            }, function() {
                fetch_default_letter_head(frm, frm.doc.company);
            });
            fetch_disciplinary_history(frm, frm.doc.accused);

            frappe.call({
                method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.check_if_ss',
                args: {
                    accused: frm.doc.accused
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('is_ss', r.message.is_ss);
                        frm.set_value('ss_union', r.message.ss_union);
                    }
                }
            });
        }
    },

    refresh: function(frm) {
        frm.toggle_display(['make_warning_form', 'make_nta_hearing', 'write_disciplinary_outcome_report'], frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.workflow_state !== 'Submitted');

        if (frappe.user.has_role("IR Manager")) {
            frm.add_custom_button(__('Actions'), function() {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

            frm.page.add_inner_button(__('Issue NTA'), function() {
                make_nta_hearing(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Write Outcome Report'), function() {
                write_disciplinary_outcome_report(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Warning'), function() {
                make_warning_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Not Guilty'), function() {
                make_not_guilty_form(frm);
            }, 'Actions');
                
            frm.page.add_inner_button(__('Issue Suspension'), function() {
                make_suspension_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Demotion'), function() {
                make_demotion_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Pay Deduction'), function() {
                make_pay_deduction_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Dismissal'), function() {
                make_dismissal_form(frm);
            }, 'Actions');
        
            frm.page.add_inner_button(__('Issue VSP'), function() {
                make_vsp(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Cancel Disciplinary Action'), function() {
                cancel_disciplinary(frm);
            }, 'Actions');
        }

        if (!frm.is_new()) {
            fetch_linked_documents(frm);
            fetch_additional_linked_documents(frm);
            fetch_outcome_dates(frm);
        }      
    },

    complainant: function(frm) {
        if (frm.doc.complainant) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_complainant_data',
                args: {
                    complainant: frm.doc.complainant
                },
                callback: function(r) {
                    if (r.message) {
                        frm.set_value('compl_name', r.message.compl_name);
                        frm.set_value('compl_pos', r.message.compl_pos);
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('List of Offences', {
    code_item: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Create a new row in the final_charges child table
        let new_row = frm.add_child('final_charges');

        // Copy the code_item value and set the charge field
        new_row.code_item = row.code_item;
        new_row.charge = 'please update';

        // Refresh the final_charges table to reflect the changes
        frm.refresh_field('final_charges');
    }
});

function fetch_employee_data(frm, employee, fields, callback) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_employee_data',
        args: {
            employee: employee,
            fields: JSON.stringify(fields)
        },
        callback: function(res) {
            if (res.message) {
                for (let field in res.message) {
                    frm.set_value(field, res.message[field]);
                }
                if (callback) callback();
            }
        }
    });
}

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

function make_nta_hearing(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.nta_hearing.nta_hearing.make_nta_hearing",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating NTA Hearing ...")
    });
}

function write_disciplinary_outcome_report(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.write_disciplinary_outcome_report",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Disciplinary Outcome Report ...")
    });
}

function make_not_guilty_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.not_guilty_form.not_guilty_form.make_not_guilty_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Not Guilty Form ...")
    });
}

function make_warning_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.warning_form.warning_form.make_warning_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Warning Form ...")
    });
}

function make_suspension_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Suspension Form ...")
    });
}

function make_demotion_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Demotion Form ...")
    });
}

function make_pay_deduction_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Pay Deduction Form ...")
    });
}

function make_dismissal_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Dismissal Form ...")
    });
}

function make_vsp(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating VSP ...")
    });
}

function cancel_disciplinary(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_disciplinary",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Generating Cancellation Form ...")
    });
}