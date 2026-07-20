// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Poor Performance", {
    refresh(frm) {
        render_linked_docs(frm);

        if (frappe.user.has_role("IR Manager") || frappe.user.has_role("IR Officer")) {
            frm.add_custom_button(__("Actions"), function () {}, "Actions")
                .addClass("btn-primary")
                .attr("id", "actions_dropdown");

            add_action(frm, "Issue NTA", make_nta_hearing);
            add_action(frm, "Write Outcome", create_written_outcome);
            add_action(frm, "Issue Warning", make_warning_form);
            add_action(frm, "Determine Employee Performance Improved", create_no_further_action_form);
            add_suspension_actions(frm);
            add_action(frm, "Issue Demotion", make_demotion_form);
            add_action(frm, "Issue Pay Deduction", make_pay_deduction_form);
            add_action(frm, "Issue Pay Reduction", make_pay_reduction_form);
            add_action(frm, "Issue Dismissal", make_dismissal_form);
            add_action(frm, "Issue VSP", make_vsp);
            add_action(frm, "Cancel Performance Process", cancel_performance);
            add_action(frm, "Appeal Against Outcome", appeal_performance);
        }
    },

    after_save(frm) {
        render_linked_docs(frm);
    },

    employee(frm) {
        if (!frm.doc.employee) return;

        fetch_employee_data(
            frm,
            frm.doc.employee,
            {
                employee_name: "employee_name",
                designation: "employee_designation",
                company: "company",
                date_of_joining: "engagement_date",
                branch: "branch",
            },
            () => fetch_default_letter_head(frm, frm.doc.company)
        );

        fetch_performance_history(frm, frm.doc.employee);
        check_if_ss(frm, frm.doc.employee);
    },

    complainant(frm) {
        if (frm.doc.complainant) {
            fetch_complainant_data(frm, frm.doc.complainant);
        }
    },
});

function add_action(frm, label, handler) {
    frm.page.add_inner_button(__(label), () => handler(frm), "Actions");
}

function add_suspension_actions(frm) {
    frm.page.add_inner_button(
        __("Issue Precautionary Suspension"),
        () => create_suspension_form(frm, "Precautionary"),
        "Actions"
    );
    frm.page.add_inner_button(
        __("Issue Punitive Suspension"),
        () => create_suspension_form(frm, "Punitive"),
        "Actions"
    );
}

function create_suspension_form(frm, suspension_nature) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.suspension_form.suspension_form.create_suspension_form",
        args: {
            source_name: frm.doc.name,
            source_doctype: frm.doctype,
            suspension_nature,
        },
        freeze: true,
        freeze_message: __("Creating {0} Suspension ...", [suspension_nature]),
        callback(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", "Suspension Form", r.message.name);
            }
        },
    });
}

function render_linked_docs(frm) {
    if (!frm.fields_dict.linked_docs) return;
    frappe.require("/assets/ir/css/ir_ui.css");

    if (frm.is_new() || frm.doc.__islocal) {
        frm.fields_dict.linked_docs.$wrapper.html(
            '<div class="ir-linked-docs"><div class="ir-linked-docs__empty">Linked documents will appear here once the record is saved.</div></div>'
        );
        return;
    }

    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.get_linked_docs_html",
        args: { poor_performance_name: frm.doc.name },
        callback(r) {
            frm.fields_dict.linked_docs.$wrapper.html(r.message || "");
        },
    });
}

function fetch_employee_data(frm, employee, fields, callback) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_employee_data",
        args: { employee, fields: JSON.stringify(fields) },
        callback(res) {
            Object.entries(res.message || {}).forEach(([fieldname, value]) => {
                frm.set_value(fieldname, value);
            });
            if (callback) callback();
        },
    });
}

function fetch_default_letter_head(frm, company) {
    if (!company) return;
    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_default_letter_head",
        args: { company },
        callback(res) {
            frm.set_value("letter_head", res.message || "");
        },
    });
}

function fetch_performance_history(frm, employee) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_performance_history",
        args: { employee, current_doc_name: frm.doc.name || "" },
        callback(res) {
            frm.clear_table("previous_disciplinary_outcomes");
            (res.message || []).forEach((row) => {
                const child = frm.add_child("previous_disciplinary_outcomes");
                Object.assign(child, row);
            });
            frm.refresh_field("previous_disciplinary_outcomes");
        },
    });
}

function fetch_complainant_data(frm, complainant) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.fetch_complainant_data",
        args: { complainant },
        callback(res) {
            const data = res.message || {};
            frm.set_value("complainant_name", data.complainant_name || "");
            frm.set_value("complainant_designation", data.complainant_designation || "");
        },
    });
}

function check_if_ss(frm, employee) {
    frappe.call({
        method:
            "ir.industrial_relations.doctype.poor_performance.poor_performance.check_if_ss",
        args: { employee },
        callback(res) {
            const data = res.message || {};
            frm.set_value("is_ss", data.is_ss || 0);
            frm.set_value("ss_union", data.ss_union || "");
        },
    });
}

function make_nta_hearing(frm) {
    frappe.model.open_mapped_doc({
        method:
            "ir.industrial_relations.doctype.nta_enquiry.nta_enquiry.make_nta_enquiry_poor_performance",
        frm,
        freeze_message: __("Creating NTA Enquiry ..."),
    });
}

function create_written_outcome(frm) {
    create_generic_document(
        frm,
        "ir.industrial_relations.doctype.written_outcome.written_outcome.create_written_outcome",
        "Written Outcome",
        "Creating Written Outcome ..."
    );
}

function make_warning_form(frm) {
    create_generic_document(
        frm,
        "ir.industrial_relations.doctype.warning_form.warning_form.create_warning_form",
        "Warning Form",
        "Creating Warning Form ..."
    );
}

function create_no_further_action_form(frm) {
    create_generic_document(
        frm,
        "ir.industrial_relations.doctype.no_further_action_form.no_further_action_form.create_no_further_action_form",
        "No Further Action Form",
        "Creating No Further Action Form ..."
    );
}

function create_generic_document(frm, method, target_doctype, freeze_message) {
    frappe.call({
        method,
        args: { source_name: frm.doc.name, source_doctype: frm.doctype },
        freeze: true,
        freeze_message: __(freeze_message),
        callback(r) {
            if (!r.exc && r.message) {
                frappe.model.sync(r.message);
                frappe.set_route("Form", target_doctype, r.message.name);
            }
        },
    });
}

function open_legacy_mapped(frm, method, args, message) {
    frappe.model.open_mapped_doc({ method, frm, args, freeze_message: __(message || "Creating document ...") });
}

function make_demotion_form(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form_performance", { linked_poor_performance: frm.doc.name });
}
function make_pay_deduction_form(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.pay_deduction_form.pay_deduction_form.make_pay_deduction_form_performance", { linked_poor_performance: frm.doc.name });
}
function make_pay_reduction_form(frm) {
    create_generic_document(
        frm,
        "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.create_pay_reduction_form",
        "Pay Reduction Form",
        "Creating Pay Reduction Form ..."
    );
}
function make_dismissal_form(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form_performance", { linked_poor_performance: frm.doc.name });
}
function make_vsp(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_performance", { linked_poor_performance: frm.doc.name });
}
function cancel_performance(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_poor_performance", { linked_poor_performance: frm.doc.name });
}
function appeal_performance(frm) {
    open_legacy_mapped(frm, "ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.appeal_poor_performance", { linked_poor_performance: frm.doc.name });
}
