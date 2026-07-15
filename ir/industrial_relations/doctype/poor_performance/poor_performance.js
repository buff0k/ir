// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Poor Performance', {
    refresh: function(frm) {
        render_linked_docs(frm);

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

            frm.page.add_inner_button(__('Determine Employee Performance Improved'), function() {
                create_no_further_action_form(frm);
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
                make_pay_reduction_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue Dismissal'), function() {
                make_dismissal_form(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Issue VSP'), function() {
                make_vsp(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Cancel Performance Process'), function() {
                cancel_performance(frm);
            }, 'Actions');

            frm.page.add_inner_button(__('Appeal Against Outcome'), function() {
                appeal_performance(frm);
            }, 'Actions');
        }
    },

    after_save: function(frm) {
        render_linked_docs(frm);
    },

    employee: function(frm) {
        if (frm.doc.employee) {
            fetch_employee_data(frm, frm.doc.employee, {
                'employee_name': 'employee_name',
                'designation': 'employee_designation',
                'company': 'company',
                'date_of_joining': 'engagement_date',
                'branch': 'branch'
            }, function() {
                fetch_default_letter_head(frm, frm.doc.company);
            });

            fetch_performance_history(frm, frm.doc.employee);
            check_if_ss(frm, frm.doc.employee);
        }
    },

    complainant: function(frm) {
        if (frm.doc.complainant) {
            fetch_complainant_data(frm, frm.doc.complainant);
        }
    }
});

function render_linked_docs(frm) {
    if (!frm.fields_dict.linked_docs) return;
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
        method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.get_linked_docs_html',
        args: {
            poor_performance_name: frm.doc.name
        },
        callback: function(r) {
            frm.fields_dict.linked_docs.$wrapper.html(r.message || '');
        }
    });
}

function fetch_employee_data(frm, employee, fields, callback) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_employee_data',
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
            method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_default_letter_head',
            args: { company: company },
            callback: function(res) {
                frm.set_value('letter_head', res.message || '');
            }
        });
    }
}

function fetch_performance_history(frm, employee) {
    if (!employee) return;

    frappe.call({
        method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_performance_history',
        args: {
            employee: employee,
            current_doc_name: frm.doc.name || ''
        },
        callback: function(res) {
            if (res.message) {
                frm.clear_table('previous_disciplinary_outcomes');
                res.message.forEach(row => {
                    let child = frm.add_child('previous_disciplinary_outcomes');
                    child.performance_action = row.performance_action;
                    child.date = row.date;
                    child.charges = row.charges;
                    child.sanction = row.sanction;
                });
                frm.refresh_field('previous_disciplinary_outcomes');
            }
        }
    });
}

function fetch_complainant_data(frm, complainant) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_complainant_data',
        args: { complainant: complainant },
        callback: function(res) {
            if (res.message) {
                frm.set_value('complainant_name', res.message.complainant_name || '');
                frm.set_value('complainant_designation', res.message.complainant_designation || '');
            }
        }
    });
}

function check_if_ss(frm, employee) {
    frappe.call({
        method: 'ir.industrial_relations.doctype.poor_performance.poor_performance.check_if_ss',
        args: { employee: employee },
        callback: function(res) {
            if (res.message) {
                frm.set_value('is_ss', res.message.is_ss);
                frm.set_value('ss_union', res.message.ss_union);
            }
        }
    });
}

function make_nta_hearing(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.nta_enquiry.nta_enquiry.make_nta_enquiry_poor_performance",
        frm: frm,
        freeze_message: __("Creating NTA Enquiry ...")
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
        freeze_message: __("Creating Written Outcome ..."),
        callback: function(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", "Written Outcome", r.message.name);
            }
        }
    });
}

function make_warning_form(frm) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.warning_form.warning_form.create_warning_form",
        args: {
            source_name: frm.doc.name,
            source_doctype: frm.doctype,
        },
        freeze: true,
        freeze_message: __("Creating Warning Form ..."),
        callback(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route(
                    "Form",
                    "Warning Form",
                    r.message.name
                );
            }
        },
    });
}

function create_no_further_action_form(frm) {
    frappe.call({
        method: "ir.industrial_relations.doctype.no_further_action_form.no_further_action_form.create_no_further_action_form",
        args: {
            source_name: frm.doc.name,
            source_doctype: frm.doctype
        },
        freeze: true,
        freeze_message: __("Creating No Further Action Form ..."),
        callback: function(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", "No Further Action Form", r.message.name);
            }
        }
    });
}


function make_suspension_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function make_demotion_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function make_pay_deduction_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function make_pay_reduction_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.make_pay_reduction_form_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function make_dismissal_form(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function make_vsp(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function cancel_performance(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_poor_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}

function appeal_performance(frm) {
    frappe.model.open_mapped_doc({
        method: "ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.appeal_poor_performance",
        frm: frm,
        args: { linked_poor_performance: frm.doc.name }
    });
}
