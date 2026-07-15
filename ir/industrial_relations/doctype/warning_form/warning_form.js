// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Warning Form", {
    setup(frm) {
        frm.set_query("ir_intervention", () => ({
            filters: {
                name: [
                    "in",
                    [
                        "Disciplinary Action",
                        "Incapacity Proceedings",
                        "Poor Performance",
                    ],
                ],
            },
        }));
    },

    refresh(frm) {
        toggle_intervention_sections(frm);

        if (
            frm.doc.applied_rights &&
            !(frm.doc.employee_rights || []).length
        ) {
            frm.trigger("applied_rights");
        }

        if (
            frm.doc.linked_intervention &&
            !frm.doc.linked_intervention_processed
        ) {
            frm.trigger("linked_intervention");
        }
    },

    ir_intervention(frm) {
        frm.set_value("linked_intervention", "");
        frm.set_value("linked_intervention_processed", 0);
        clear_intervention_data(frm);
        toggle_intervention_sections(frm);
    },

    linked_intervention(frm) {
        if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) {
            return;
        }

        frappe.call({
            method:
                "ir.industrial_relations.doctype.warning_form.warning_form.fetch_intervention_data",
            args: {
                ir_intervention: frm.doc.ir_intervention,
                linked_intervention: frm.doc.linked_intervention,
            },
            freeze: true,
            freeze_message: __("Loading intervention details ..."),
            callback(r) {
                if (!r.message) {
                    return;
                }

                apply_intervention_data(frm, r.message);
                frm.set_value("applied_rights", "Warning Form");
                frm.trigger("applied_rights");
                frm.set_value("linked_intervention_processed", 1);
            },
        });
    },

    company(frm) {
        if (!frm.doc.company) {
            frm.set_value("letter_head", "");
            return;
        }

        frappe.call({
            method:
                "ir.industrial_relations.doctype.warning_form.warning_form.fetch_company_letter_head",
            args: { company: frm.doc.company },
            callback(r) {
                frm.set_value(
                    "letter_head",
                    r.message?.letter_head || ""
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
            () => {
                const rights = frappe.get_doc(
                    "Employee Rights",
                    frm.doc.applied_rights
                );

                frm.clear_table("employee_rights");

                (rights.applicable_rights || []).forEach((row) => {
                    const child = frm.add_child("employee_rights");
                    child.individual_right = row.individual_right;
                });

                frm.refresh_field("employee_rights");
            }
        );
    },

    before_save(frm) {
        return confirm_outcome_change(frm, "clear");
    },

    before_submit(frm) {
        if (!frm.doc.signed_warning) {
            frappe.throw(
                __("You must attach the signed warning before submitting.")
            );
        }

        return confirm_outcome_change(frm, "overwrite");
    },

    warning_type(frm) {
        if (!frm.doc.warning_type) {
            frm.set_value("disc_offence_out", "");
            frm.set_value("expiry_days", "");
            return;
        }

        frappe.db
            .get_value(
                "Offence Outcome",
                frm.doc.warning_type,
                ["disc_offence_out", "expiry_days"]
            )
            .then((r) => {
                const values = r.message || {};
                frm.set_value(
                    "disc_offence_out",
                    values.disc_offence_out || ""
                );
                frm.set_value(
                    "expiry_days",
                    values.expiry_days || ""
                );
            });
    },
});


function toggle_intervention_sections(frm) {
    const intervention = frm.doc.ir_intervention;

    frm.toggle_display(
        [
            "details_of_offence_section",
            "warning_charges",
            "previous_disciplinary_offences_section",
            "disciplinary_history",
        ],
        intervention === "Disciplinary Action"
    );

    frm.toggle_display(
        [
            "details_of_incapacity_section",
            "type_of_incapacity",
            "details_of_incapacity",
            "incapacity_history_section",
            "previous_incapacity_outcomes",
        ],
        intervention === "Incapacity Proceedings"
    );

    frm.toggle_display(
        [
            "details_of_poor_performance_section",
            "performance_details",
            "performance_history_section",
            "previous_performance_outcomes",
        ],
        intervention === "Poor Performance"
    );
}


function clear_intervention_data(frm) {
    [
        "employee",
        "names",
        "coy",
        "position",
        "company",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, "");
        }
    });

    [
        "warning_charges",
        "disciplinary_history",
        "previous_incapacity_outcomes",
        "previous_performance_outcomes",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.clear_table(fieldname);
            frm.refresh_field(fieldname);
        }
    });
}


function apply_intervention_data(frm, data) {
    [
        "employee",
        "names",
        "coy",
        "position",
        "company",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, data[fieldname] || "");
        }
    });

    const tables = {
        warning_charges: ["indiv_charge"],
        disciplinary_history: [
            "disc_action",
            "date",
            "sanction",
            "charges",
        ],
        previous_incapacity_outcomes: [
            "incap_proc",
            "date",
            "sanction",
            "incap_details",
        ],
        previous_performance_outcomes: [
            "performance_action",
            "date",
            "charges",
            "sanction",
        ],
    };

    Object.entries(tables).forEach(([fieldname, fields]) => {
        if (!frm.fields_dict[fieldname]) {
            return;
        }

        frm.clear_table(fieldname);

        (data[fieldname] || []).forEach((row) => {
            const child = frm.add_child(fieldname);
            fields.forEach((child_field) => {
                child[child_field] = row[child_field];
            });
        });

        frm.refresh_field(fieldname);
    });

    toggle_intervention_sections(frm);
}


function confirm_outcome_change(frm, mode) {
    if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) {
        return Promise.resolve();
    }

    return new Promise((resolve, reject) => {
        frappe.call({
            method:
                "ir.industrial_relations.doctype.warning_form.warning_form.get_linked_outcome",
            args: {
                doc_name: frm.doc.linked_intervention,
                doctype: frm.doc.ir_intervention,
            },
            callback(r) {
                const data = r.message || {};
                const outcome = data.outcome || "";
                const outcomeDate = data.outcome_date || "";

                if (!outcome && !outcomeDate) {
                    resolve();
                    return;
                }

                const current = __(
                    "The linked {0} currently has outcome {1} dated {2}.",
                    [
                        frm.doc.ir_intervention,
                        outcome || __("None"),
                        outcomeDate
                            ? frappe.datetime.str_to_user(outcomeDate)
                            : __("None"),
                    ]
                );

                const action =
                    mode === "overwrite"
                        ? __(
                              "Submitting will replace it with {0} dated {1}. Continue?",
                              [
                                  frm.doc.warning_type,
                                  frappe.datetime.str_to_user(
                                      frm.doc.outcome_date
                                  ),
                              ]
                          )
                        : __(
                              "Saving this draft will clear the linked outcome. Continue?"
                          );

                frappe.confirm(
                    `${current}<br><br>${action}`,
                    resolve,
                    () => reject(new Error("User cancelled"))
                );
            },
            error: reject,
        });
    });
}
