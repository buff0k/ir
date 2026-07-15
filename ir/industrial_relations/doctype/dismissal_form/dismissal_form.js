// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Dismissal Form", {
    refresh(frm) {
        if (
            frm.doc.ir_intervention &&
            frm.doc.linked_intervention &&
            !frm.doc.linked_intervention_processed
        ) {
            frm.trigger("linked_intervention");
        }
    },

    linked_intervention(frm) {
        if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) return;

        frappe.call({
            method:
                "ir.industrial_relations.doctype.dismissal_form.dismissal_form.fetch_intervention_data",
            args: {
                source_doctype: frm.doc.ir_intervention,
                source_name: frm.doc.linked_intervention,
            },
            freeze: true,
            freeze_message: __("Loading intervention details ..."),
            callback(r) {
                if (!r.exc && r.message) {
                    apply_intervention_data(frm, r.message);
                }
            },
        });
    },

    company(frm) {
        if (!frm.doc.company) return;

        frappe.call({
            method:
                "ir.industrial_relations.doctype.dismissal_form.dismissal_form.fetch_company_letter_head",
            args: { company: frm.doc.company },
            callback(r) {
                frm.set_value("letter_head", r.message || "");
            },
        });
    },

    applied_rights(frm) {
        if (!frm.doc.applied_rights) {
            frm.clear_table("employee_rights");
            frm.refresh_field("employee_rights");
            return;
        }

        frappe.model.with_doc("Employee Rights", frm.doc.applied_rights, function () {
            const rights = frappe.get_doc("Employee Rights", frm.doc.applied_rights);
            frm.clear_table("employee_rights");
            (rights.applicable_rights || []).forEach((row) => {
                const child = frm.add_child("employee_rights");
                child.individual_right = row.individual_right;
            });
            frm.refresh_field("employee_rights");
        });
    },

    before_save(frm) {
        confirm_source_outcome_change(frm, "save");
    },

    before_submit(frm) {
        if (!frm.doc.signed_dismissal) {
            frappe.msgprint(__("You must attach the signed dismissal before submitting."));
            frappe.validated = false;
            return;
        }

        confirm_source_outcome_change(frm, "submit");
    },
});

function apply_intervention_data(frm, data) {
    const values = {
        employee: data.employee || "",
        names: data.names || "",
        position: data.position || "",
        company: data.company || "",
        type_of_incapacity: data.type_of_incapacity || "",
        details_of_incapacity: data.details_of_incapacity || "",
        performance_details: data.performance_details || "",
        applied_rights: "Dismissal",
    };

    Object.entries(values).forEach(([fieldname, value]) => {
        if (frm.fields_dict[fieldname]) {
            frm.doc[fieldname] = value;
            frm.refresh_field(fieldname);
        }
    });

    replace_child_table(frm, "disciplinary_history", data.disciplinary_history);
    replace_child_table(frm, "dismissal_charges", data.dismissal_charges);
    replace_child_table(
        frm,
        "previous_incapacity_outcomes",
        data.previous_incapacity_outcomes
    );
    replace_child_table(
        frm,
        "previous_performance_outcomes",
        data.previous_performance_outcomes
    );

    frm.trigger("applied_rights");
    frm.set_value("linked_intervention_processed", 1);

    if (frm.doc.company) {
        frm.trigger("company");
    }
}

function replace_child_table(frm, fieldname, rows) {
    if (!frm.fields_dict[fieldname]) return;

    frm.clear_table(fieldname);
    (rows || []).forEach((row) => {
        const child = frm.add_child(fieldname);
        Object.assign(child, row);
    });
    frm.refresh_field(fieldname);
}

function confirm_source_outcome_change(frm, action) {
    const confirmedFlag = action === "submit" ? "__confirmed_submit" : "__confirmed_save";
    if (frm[confirmedFlag]) return;
    if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) return;

    frappe.call({
        method:
            "ir.industrial_relations.doctype.dismissal_form.dismissal_form.get_linked_outcome",
        args: {
            doc_name: frm.doc.linked_intervention,
            doctype: frm.doc.ir_intervention,
        },
        callback(r) {
            const data = r.message || {};
            const outcome = data.outcome || __("None");
            const outcomeDate = data.outcome_date
                ? frappe.datetime.str_to_user(data.outcome_date)
                : __("None");

            if (!data.outcome && !data.outcome_date && !data.outcome_start && !data.outcome_end) {
                continue_action(frm, action, confirmedFlag);
                return;
            }

            const message = action === "submit"
                ? __(
                    "The linked {0} currently has outcome {1} dated {2}. It will be replaced by dismissal outcome {3} dated {4}. Continue?",
                    [
                        frm.doc.ir_intervention,
                        outcome,
                        outcomeDate,
                        frm.doc.dismissal_type || __("Not selected"),
                        frm.doc.outcome_date
                            ? frappe.datetime.str_to_user(frm.doc.outcome_date)
                            : __("Not selected"),
                    ]
                )
                : __(
                    "The linked {0} currently has outcome {1} dated {2}. Its outcome fields will be cleared when this draft is saved. Continue?",
                    [frm.doc.ir_intervention, outcome, outcomeDate]
                );

            frappe.confirm(
                message,
                () => continue_action(frm, action, confirmedFlag),
                () => {
                    frappe.validated = false;
                    frappe.msgprint(__("Operation cancelled."));
                }
            );
        },
    });

    frappe.validated = false;
}

function continue_action(frm, action, confirmedFlag) {
    frm[confirmedFlag] = true;
    frappe.validated = true;

    if (action === "submit") {
        frm.save({ action: "submit" });
    } else {
        frm.save();
    }
}
