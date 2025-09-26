// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Written Outcome", {
    refresh: function (frm) {
        if (frm.doc.ir_intervention && !frm.doc.linked_intervention_processed) {
            frm.trigger('fetch_intervention_data');
        }
    
        if (!frm.is_new()) {
            fetch_linked_documents(frm);
        };

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
        }

        frm.add_custom_button(__('Compile Outcome'), function () {
            compile_outcome(frm);
        }, __('Actions')).addClass('btn-primary');
    },

    fetch_intervention_data: function(frm) {
        if (frm.doc.ir_intervention && frm.doc.linked_intervention) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.written_outcome.written_outcome.fetch_intervention_data',
                args: {
                    intervention: frm.doc.linked_intervention,
                    intervention_type: frm.doc.ir_intervention
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;
                        frm.set_value('company', data.company);
                        frm.set_value('letter_head', data.letter_head);
                        frm.set_value('employee', data.employee);
                        frm.set_value('employee_name', data.employee_name);
                        frm.set_value('employee_designation', data.employee_designation);
                        frm.set_value('employee_branch', data.employee_branch);
                        frm.set_value('chairperson', data.chairperson);
                        frm.set_value('chairperson_name', data.chairperson_name);
                        frm.set_value('complainant', data.complainant);
                        frm.set_value('complainant_name', data.complainant_name);
                        frm.set_value('incapacity_details_nta', data.incapacity_details_nta);
                        frm.set_value('final_incapacity_details', data.final_incapacity_details);

                        frm.clear_table('nta_charges');
                        $.each(data.nta_charges, function(_, row) {
                            let child = frm.add_child('nta_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('nta_charges');

                        frm.clear_table('final_charges');
                        $.each(data.final_charges, function(_, row) {
                            let child = frm.add_child('final_charges');
                            child.indiv_charge = row.indiv_charge;
                        });
                        frm.refresh_field('final_charges');

                        frm.set_value('linked_intervention_processed', true);
                    }
                }
            });
        }
    },

    compile_outcome: function(frm) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.written_outcome.written_outcome.compile_outcome',
            args: { docname: frm.doc.name },
            callback: function (r) {
                if (r.message) {
                    frappe.msgprint(__('Outcome compiled successfully.'));
                    frm.reload_doc();
                }
            }
        });
    }
});

function fetch_linked_documents(frm) {
    // List of all the linked doctypes, their corresponding fields, and the linking field in the child table
    const linked_fields = [
        { fieldname: 'linked_nta', doctype: 'NTA Hearing', linking_field: 'linked_disciplinary_action', child_table_field: 'linked_nta' },
        { fieldname: 'linked_ruling', doctype: 'Ruling', linking_field: 'linked_intervention', child_table_field: 'ruling' }
    ];

    // Iterate over each linked field and fetch the linked documents
    linked_fields.forEach((linked_field) => {
        frappe.call({
            method: 'ir.industrial_relations.doctype.written_outcome.written_outcome.get_linked_documents',
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

// === Added by ChatGPT: reliable Employee name syncing for complainant/chairperson/approver ===
frappe.ui.form.on('Written Outcome', {
    onload(frm) {
        // auto-fetch from Employee.link to *_name
        try {
            frm.add_fetch('complainant', 'employee_name', 'complainant_name');
            frm.add_fetch('chairperson', 'employee_name', 'chairperson_name');
            frm.add_fetch('approver',   'employee_name', 'approver_name');
        } catch (e) {
            console && console.warn && console.warn('add_fetch not available on this form yet', e);
        }
    },
    complainant(frm) { _wo_clear_if_empty(frm, 'complainant', 'complainant_name'); },
    chairperson(frm) { _wo_clear_if_empty(frm, 'chairperson', 'chairperson_name'); },
    approver(frm)    { _wo_clear_if_empty(frm, 'approver',    'approver_name'); },
    refresh(frm) {
        _wo_initial_sync_if_present(frm, [
            ['complainant','complainant_name'],
            ['chairperson','chairperson_name'],
            ['approver','approver_name'],
        ]);
    },
});

function _wo_clear_if_empty(frm, link_field, name_field) {
    if (!frm.doc[link_field]) {
        frm.set_value(name_field, null);
    }
}

function _wo_initial_sync_if_present(frm, pairs) {
    pairs.forEach(([link_field, name_field]) => {
        const val = frm.doc[link_field];
        if (val && !frm.doc[name_field]) {
            frappe.db.get_value('Employee', val, 'employee_name').then(r => {
                if (r && r.message) {
                    frm.set_value(name_field, r.message.employee_name || null);
                }
            });
        }
    });
}