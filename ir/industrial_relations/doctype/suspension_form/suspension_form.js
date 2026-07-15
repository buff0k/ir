// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Suspension Form", {
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

        frm.set_query("suspension_type", () => ({
            filters: {
                issuspension: 1,
            },
        }));
    },

    refresh(frm) {
        toggle_source_sections(frm);

        if (
            frm.doc.ir_intervention &&
            frm.doc.linked_intervention &&
            !frm.doc.linked_intervention_processed
        ) {
            frm.trigger("linked_intervention");
        }
    },

    ir_intervention(frm) {
        toggle_source_sections(frm);
    },

    linked_intervention(frm) {
        if (!frm.doc.ir_intervention || !frm.doc.linked_intervention) {
            return;
        }

        frappe.call({
            method:
                "ir.industrial_relations.doctype.suspension_form.suspension_form.fetch_intervention_data",
            args: {
                ir_intervention: frm.doc.ir_intervention,
                linked_intervention: frm.doc.linked_intervention,
            },
            freeze: true,
            freeze_message: __("Loading intervention data ..."),
            callback(r) {
                if (!r.exc && r.message) {
                    apply_intervention_data(frm, r.message);
                }
            },
        });
    },

    suspension_nature(frm) {
        if (frm.doc.suspension_nature === "Precautionary") {
            frm.set_value("suspension_type", null);
            if (!frm.doc.remuneration_status) {
                frm.set_value("remuneration_status", "Paid");
            }
        }

        frm.refresh_field("suspension_type");
    },

    applied_rights(frm) {
        load_employee_rights(frm);
    },

    before_save(frm) {
        return confirm_punitive_outcome_change(frm, "save");
    },

    before_submit(frm) {
        if (!frm.doc.signed_suspension) {
            frappe.throw(__("Attach the signed suspension before submitting."));
        }

        return confirm_punitive_outcome_change(frm, "submit");
    },
});

function toggle_source_sections(frm) {
    const source = frm.doc.ir_intervention;

    frm.toggle_display(
        [
            "details_of_offence_section",
            "susp_charges",
            "previous_disciplinary_offences_section",
            "disciplinary_history",
        ],
        source === "Disciplinary Action"
    );

    frm.toggle_display(
        [
            "incap_details_section",
            "type_of_incapacity",
            "details_of_incapacity",
            "previous_incapacity_outcomes_section",
            "previous_incapacity_outcomes",
        ],
        source === "Incapacity Proceedings"
    );

    frm.toggle_display(
        [
            "performance_details_section",
            "performance_details",
            "performance_history_section",
            "previous_performance_outcomes",
        ],
        source === "Poor Performance"
    );
}

function apply_intervention_data(frm, data) {
    const scalar_fields = [
        "employee",
        "names",
        "position",
        "company",
        "letter_head",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ];

    scalar_fields.forEach((fieldname) => {
        if (Object.prototype.hasOwnProperty.call(data, fieldname)) {
            frm.set_value(fieldname, data[fieldname] || "");
        }
    });

    replace_child_table(frm, "susp_charges", data.susp_charges || []);
    replace_child_table(frm, "disciplinary_history", data.disciplinary_history || []);
    replace_child_table(
        frm,
        "previous_incapacity_outcomes",
        data.previous_incapacity_outcomes || []
    );
    replace_child_table(
        frm,
        "previous_performance_outcomes",
        data.previous_performance_outcomes || []
    );

    if (!frm.doc.applied_rights) {
        frm.set_value("applied_rights", "Suspension");
    }
    load_employee_rights(frm);

    frm.set_value("linked_intervention_processed", 1);
    toggle_source_sections(frm);
}

function replace_child_table(frm, fieldname, rows) {
    if (!frm.fields_dict[fieldname]) {
        return;
    }

    frm.clear_table(fieldname);
    rows.forEach((row) => {
        const child = frm.add_child(fieldname);
        Object.assign(child, row);
    });
    frm.refresh_field(fieldname);
}

function load_employee_rights(frm) {
    if (!frm.doc.applied_rights) {
        return;
    }

    frappe.model.with_doc("Employee Rights", frm.doc.applied_rights, () => {
        const rights = frappe.get_doc("Employee Rights", frm.doc.applied_rights);
        frm.clear_table("employee_rights");
        (rights.applicable_rights || []).forEach((row) => {
            const child = frm.add_child("employee_rights");
            child.individual_right = row.individual_right;
        });
        frm.refresh_field("employee_rights");
    });
}

function confirm_punitive_outcome_change(frm, action) {
    if (
        frm.doc.suspension_nature !== "Punitive" ||
        !frm.doc.ir_intervention ||
        !frm.doc.linked_intervention
    ) {
        return Promise.resolve();
    }

    if (action === "save" && frm.__punitive_save_confirmed) {
        return Promise.resolve();
    }

    if (action === "submit" && frm.__punitive_submit_confirmed) {
        return Promise.resolve();
    }

    return frappe
        .call({
            method:
                "ir.industrial_relations.doctype.suspension_form.suspension_form.get_linked_outcome",
            args: {
                doc_name: frm.doc.linked_intervention,
                doctype: frm.doc.ir_intervention,
            },
        })
        .then((r) => {
            const current = r.message || {};
            const has_existing_outcome = Boolean(
                current.outcome ||
                current.outcome_date ||
                current.outcome_start ||
                current.outcome_end
            );

            if (!has_existing_outcome) {
                return;
            }

            const outcome = current.outcome || __("None");
            const outcomeDate = current.outcome_date
                ? frappe.datetime.str_to_user(current.outcome_date)
                : __("None");

            const message =
                action === "save"
                    ? __(
                          "The linked {0} currently has outcome {1}, dated {2}. Saving this punitive suspension will clear that outcome pending submission. Continue?",
                          [frm.doc.ir_intervention, outcome, outcomeDate]
                      )
                    : __(
                          "The linked {0} currently has outcome {1}, dated {2}. Submitting this punitive suspension will replace it with {3}, dated {4}. Continue?",
                          [
                              frm.doc.ir_intervention,
                              outcome,
                              outcomeDate,
                              frm.doc.suspension_type || __("the suspension outcome"),
                              frm.doc.outcome_date
                                  ? frappe.datetime.str_to_user(frm.doc.outcome_date)
                                  : __("None"),
                          ]
                      );

            return new Promise((resolve, reject) => {
                frappe.confirm(
                    message,
                    () => {
                        if (action === "save") {
                            frm.__punitive_save_confirmed = true;
                        } else {
                            frm.__punitive_submit_confirmed = true;
                        }
                        resolve();
                    },
                    () => reject(new Error(__("Operation cancelled.")))
                );
            });
        });
}
