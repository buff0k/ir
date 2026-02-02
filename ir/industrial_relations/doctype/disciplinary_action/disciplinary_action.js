// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Disciplinary Action', {
    refresh: function(frm) {
        render_linked_docs(frm);

        frm.toggle_display(
            ['make_warning_form', 'make_nta_hearing', 'write_disciplinary_outcome_report'],
            frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.workflow_state !== 'Submitted'
        );

        if (frappe.user.has_role("IR Manager") || frappe.user.has_role("IR Officer")) {
            frm.add_custom_button(__('Actions'), function() {}, 'Actions')
                .addClass('btn-primary')
                .attr('id', 'actions_dropdown');

            frm.page.add_inner_button(__('Issue NTA'), function() {
                make_nta_hearing(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Write Outcome'), function() {
                create_written_outcome(frm);
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

    after_save: function(frm) {
        render_linked_docs(frm);
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
            check_if_ss(frm, frm.doc.accused);
        }
    },

    complainant: function(frm) {
        if (frm.doc.complainant) {
            fetch_complainant_data(frm, frm.doc.complainant);
        }
    }
});


// ----------------------
// NEW: Linked docs render
// ----------------------

function render_linked_docs(frm) {
    if (!frm.fields_dict.linked_docs) return;

    // Ensure CSS exists (shared UI)
    frappe.require('/assets/ir/css/ir_ui.css');

    if (frm.is_new() || frm.doc.__islocal) {
        frm.fields_dict.linked_docs.$wrapper.html(`
            <div class="ir-linked-docs">
              <div class="ir-linked-docs__empty">
                Linked documents will appear here once the record is saved.
              </div>
            </div>
        `);
        return;
    }

    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.get_linked_docs_html',
        args: {
            disciplinary_action_name: frm.doc.name
        },
        callback: function(r) {
            frm.fields_dict.linked_docs.$wrapper.html(r.message || '');
        }
    });
}


// ----------------------
// Existing helpers
// ----------------------

function fetch_employee_data(frm, employee, fields, callback) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_employee_data',
        args: {
            employee: employee,
            fields: JSON.stringify(fields)
        },
        callback: function(res) {
            if (res.message) {
                Object.keys(res.message).forEach(function(fieldname) {
                    frm.set_value(fieldname, res.message[fieldname]);
                });
            }
            if (callback) callback();
        }
    });
}

function fetch_default_letter_head(frm, company) {
    if (company) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_default_letter_head',
            args: { company: company },
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
    if (!accused) return;

    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_disciplinary_history',
        args: {
            accused: accused,
            current_doc_name: frm.doc.name || ''
        },
        callback: function(res) {
            if (res.message) {
                frm.clear_table('previous_disciplinary_outcomes');
                res.message.forEach(row => {
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

function fetch_complainant_data(frm, complainant) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.fetch_complainant_data',
        args: { complainant: complainant },
        callback: function(res) {
            if (res.message) {
                frm.set_value('compl_name', res.message.compl_name || '');
                frm.set_value('compl_pos', res.message.compl_pos || '');
            }
        }
    });
}

function check_if_ss(frm, accused) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.disciplinary_action.disciplinary_action.check_if_ss',
        args: { accused: accused },
        callback: function(res) {
            if (res.message) {
                frm.set_value('is_ss', res.message.is_ss);
                frm.set_value('ss_union', res.message.ss_union);
            }
        }
    });
}


// ----------------------
// Your existing actions (left as-is)
// NOTE: These are placeholders if your originals live elsewhere in this file.
// If your existing file already defines them below, keep them exactly.
// ----------------------

function make_nta_hearing(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.nta_hearing.nta_hearing.make_nta_hearing",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function create_written_outcome(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.written_outcome.written_outcome.create_written_outcome",
        frm: frm,
        args: { linked_intervention: frm.doc.name }
    });
}

function make_warning_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.warning_form.warning_form.make_warning_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_not_guilty_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.not_guilty_form.not_guilty_form.make_not_guilty_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_suspension_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_demotion_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_pay_deduction_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_pay_reduction_form_misc(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.make_pay_reduction_form_misc",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_dismissal_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function make_vsp(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function cancel_disciplinary(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_disciplinary",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}

function appeal_disciplinary(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.appeal_disciplinary",
        frm: frm,
        args: { linked_disciplinary_action: frm.doc.name }
    });
}
