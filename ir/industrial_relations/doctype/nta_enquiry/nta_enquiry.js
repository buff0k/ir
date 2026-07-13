// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("NTA Enquiry", {
    refresh(frm) {
        if (
            frm.doc.ir_intervention &&
            frm.doc.linked_intervention &&
            !frm.doc.linked_intervention_processed
        ) {
            frm.trigger("load_linked_intervention");
        }
    },

    ir_intervention(frm) {
        frm.set_value("linked_intervention", null);
        frm.set_value("linked_intervention_processed", 0);
        clear_intervention_data(frm);
    },

    linked_intervention(frm) {
        frm.set_value("linked_intervention_processed", 0);
        clear_intervention_data(frm);

        if (frm.doc.ir_intervention && frm.doc.linked_intervention) {
            frm.trigger("load_linked_intervention");
        }
    },

    load_linked_intervention(frm) {
        if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) {
            return;
        }

        frappe.call({
            method: "ir.industrial_relations.doctype.nta_enquiry.nta_enquiry.fetch_intervention_data",
            args: {
                intervention: frm.doc.linked_intervention,
                intervention_type: frm.doc.ir_intervention,
            },
            freeze: true,
            freeze_message: __("Loading IR intervention details..."),
            callback(r) {
                if (r.exc) {
                    return;
                }

                const data = r.message || {};

                set_values(frm, {
                    employee: data.employee || null,
                    names: data.names || "",
                    position: data.position || "",
                    company: data.company || null,
                    letter_head: data.letter_head || null,
                    complainant: data.complainant || null,
                    compl_name: data.compl_name || "",
                    applied_rights: data.applied_rights || null,
                    type_of_incapacity: data.type_of_incapacity || null,
                    details_of_incapacity: data.details_of_incapacity || "",
                    performance_details_nta: data.performance_details_nta || "",
                });

                replace_table(frm, "nta_charges", data.nta_charges, [
                    "indiv_charge",
                ]);

                replace_table(
                    frm,
                    "disciplinary_history",
                    data.disciplinary_history,
                    ["disc_action", "date", "sanction", "charges"]
                );

                replace_table(
                    frm,
                    "previous_incapacity_outcomes",
                    data.previous_incapacity_outcomes,
                    ["incap_proc", "date", "sanction", "incap_details"]
                );

                replace_table(
                    frm,
                    "previous_performance_outcomes",
                    data.previous_performance_outcomes,
                    ["performance_action", "date", "charges", "sanction"]
                );

                frm.trigger("applied_rights");
                frm.set_value("linked_intervention_processed", 1);
            },
        });
    },

    chairperson(frm) {
        populate_employee_name(frm, "chairperson", "chairperson_name");
    },

    complainant(frm) {
        populate_employee_name(frm, "complainant", "compl_name");
    },

    company(frm) {
        if (!frm.doc.company) {
            frm.set_value("letter_head", null);
            return;
        }

        frappe.call({
            method: "ir.industrial_relations.doctype.nta_enquiry.nta_enquiry.fetch_company_letter_head",
            args: { company: frm.doc.company },
            callback(r) {
                frm.set_value(
                    "letter_head",
                    r.message ? r.message.letter_head || null : null
                );
            },
        });
    },

    applied_rights(frm) {
        if (!frm.doc.applied_rights) {
            frm.clear_table("employee_rights");
            frm.refresh_field("employee_rights");
            return;
        }

        frappe.model.with_doc(
            "Employee Rights",
            frm.doc.applied_rights,
            function () {
                const rights = frappe.get_doc(
                    "Employee Rights",
                    frm.doc.applied_rights
                );

                frm.clear_table("employee_rights");

                (rights.applicable_rights || []).forEach(function (row) {
                    const child = frm.add_child("employee_rights");
                    child.individual_right = row.individual_right;
                });

                frm.refresh_field("employee_rights");
            }
        );
    },

    before_submit(frm) {
        if (!frm.doc.signed_nta) {
            frappe.msgprint(
                __(
                    "You cannot submit this document until you have attached a signed copy of the NTA."
                )
            );
            frappe.validated = false;
        }
    },
});

function set_values(frm, values) {
    Object.entries(values).forEach(function ([fieldname, value]) {
        if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, value);
        }
    });
}

function replace_table(frm, fieldname, rows, child_fields) {
    if (!frm.fields_dict[fieldname]) {
        return;
    }

    frm.clear_table(fieldname);

    (rows || []).forEach(function (row) {
        const child = frm.add_child(fieldname);

        child_fields.forEach(function (child_field) {
            child[child_field] = row[child_field] ?? null;
        });
    });

    frm.refresh_field(fieldname);
}

function clear_intervention_data(frm) {
    set_values(frm, {
        employee: null,
        names: "",
        position: "",
        company: null,
        letter_head: null,
        complainant: null,
        compl_name: "",
        applied_rights: null,
        type_of_incapacity: null,
        details_of_incapacity: "",
        performance_details_nta: "",
    });

    [
        "nta_charges",
        "disciplinary_history",
        "previous_incapacity_outcomes",
        "previous_performance_outcomes",
        "employee_rights",
    ].forEach(function (fieldname) {
        if (frm.fields_dict[fieldname]) {
            frm.clear_table(fieldname);
            frm.refresh_field(fieldname);
        }
    });
}

function populate_employee_name(frm, source_field, target_field) {
    const employee = frm.doc[source_field];

    if (!employee) {
        frm.set_value(target_field, "");
        return;
    }

    frappe.call({
        method: "ir.industrial_relations.doctype.nta_enquiry.nta_enquiry.fetch_employee_display",
        args: { employee },
        callback(r) {
            frm.set_value(
                target_field,
                r.message ? r.message.employee_name || "" : ""
            );
        },
    });
}
