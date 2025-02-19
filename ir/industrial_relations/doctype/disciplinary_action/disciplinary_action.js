// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disciplinary Action', {
    refresh: function(frm) {
        if (!frm.is_new()) {
            fetch_linked_documents(frm);
        };
    
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
        
            frm.page.add_inner_button(__('Issue Pay Reduction'), function() {
                make_pay_reduction_form_misc(frm);
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
        
            frm.page.add_inner_button(__('Appeal Against Outcome'), function() {
                appeal_disciplinary(frm);
            }, 'Actions');
        }
    },

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
    // List of all the linked doctypes, their corresponding fields, and the linking field in the child table
    const linked_fields = [
        { fieldname: 'linked_nta', doctype: 'NTA Hearing', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_nta' },
        { fieldname: 'linked_outcome', doctype: 'Written Outcome', linking_field: 'linked_intervention', child_table_field: 'linked_outcome' },
        { fieldname: 'linked_warning', doctype: 'Warning Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_warning' },
        { fieldname: 'linked_dismissal', doctype: 'Dismissal Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_dismissal' },
        { fieldname: 'linked_demotion', doctype: 'Demotion Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_demotion' },
        { fieldname: 'linked_pay_deduction', doctype: 'Pay Deduction Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_pay_deduction' },
        { fieldname: 'linked_pay_reduction', doctype: 'Pay Reduction Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_pay_reduction' },
        { fieldname: 'linked_not_guilty', doctype: 'Not Guilty Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_not_guilty' },
        { fieldname: 'linked_suspension', doctype: 'Suspension Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_suspension' },
        { fieldname: 'linked_vsp', doctype: 'Voluntary Seperation Agreement', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_vsp' },
        { fieldname: 'linked_cancellation', doctype: 'Hearing Cancellation Form', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_cancellation' },
        { fieldname: 'linked_appeal', doctype: 'Appeal Against Outcome', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_appeal' }
    ];

    // Iterate over each linked field and fetch the linked documents
    linked_fields.forEach((linked_field) => {
        frappe.call({
            method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.get_linked_documents',
            args: {
                disciplinary_action_name: frm.doc.name,
                linked_doctype: linked_field.doctype,
                linking_field: linked_field.linking_field
            },
            callback: function(r) {
                if (r.message) {
                    // Debugging: Log the fetched documents
                    console.log(`Fetched documents for ${linked_field.fieldname}:`, r.message);

                    // Prepare the data for the virtual field
                    const virtual_data = r.message.map((docname) => {
                        return { [linked_field.child_table_field]: docname }; // Correct structure for the virtual field
                    });

                    // Directly update the virtual field's data in the form's doc object
                    frm.doc[linked_field.fieldname] = virtual_data;

                    // Refresh the field to reflect the changes
                    frm.refresh_field(linked_field.fieldname);
                } else {
                    console.log(`No documents found for ${linked_field.fieldname}`);
                }
            }
        });
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

//Testing
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

function make_pay_reduction_form_misc(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.make_pay_reduction_form_misc",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Creating Pay Reduction Form ...")
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

function appeal_disciplinary(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.appeal_disciplinary",
        frm: frm,
        args: {
            linked_disciplinary_action: frm.doc.name
        },
        freeze_message: __("Generating Appeal Form ...")
    });
}