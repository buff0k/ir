// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const NFA_SUPPORTED_INTERVENTIONS = [
    "Disciplinary Action",
    "Poor Performance",
    "Incapacity Proceedings",
];

frappe.ui.form.on("No Further Action Form", {
    setup(frm) {
        frm.set_query("ir_intervention", () => ({
            filters: {
                name: ["in", NFA_SUPPORTED_INTERVENTIONS],
            },
        }));

        frm.set_query("linked_intervention", () => ({
            filters: {},
        }));

        frm.set_query("outcome_type", () => ({
            filters: {
                name: ["in", frm.__nfa_allowed_outcomes || ["__invalid__"]],
            },
        }));
    },

    refresh(frm) {
        apply_intervention_visibility(frm);
        apply_cancellation_visibility(frm);
        load_allowed_outcomes(frm);

        if (
            frm.doc.ir_intervention &&
            frm.doc.linked_intervention &&
            !frm.doc.linked_intervention_processed
        ) {
            frm.trigger("fetch_intervention_data");
        }

        if (frm.doc.outcome_type) {
            frm.trigger("update_outcome_state");
        }
    },

    ir_intervention(frm) {
        frm.set_value("linked_intervention", null);
        frm.set_value("linked_intervention_processed", 0);
        clear_intervention_fields(frm);
        apply_intervention_visibility(frm);
        load_allowed_outcomes(frm, true);
        set_default_outcome(frm);
    },

    linked_intervention(frm) {
        frm.set_value("linked_intervention_processed", 0);
        clear_intervention_fields(frm);

        if (frm.doc.ir_intervention && frm.doc.linked_intervention) {
            frm.trigger("fetch_intervention_data");
        }
    },

    outcome_type(frm) {
        frm.trigger("update_outcome_state");
    },

    authorized_by(frm) {
        if (!frm.fields_dict.authorized_by) return;

        if (!frm.doc.authorized_by) {
            set_if_present(frm, "auth_names", null);
            set_if_present(frm, "auth_designation", null);
            return;
        }

        frappe.call({
            method:
                "ir.industrial_relations.doctype.no_further_action_form." +
                "no_further_action_form.get_authorizer_details",
            args: {
                employee: frm.doc.authorized_by,
            },
            callback(r) {
                const data = r.message || {};
                set_if_present(frm, "auth_names", data.auth_names || null);
                set_if_present(
                    frm,
                    "auth_designation",
                    data.auth_designation || null
                );
            },
        });
    },

    update_outcome_state(frm) {
        if (!frm.doc.outcome_type) {
            frm.__nfa_is_cancellation = false;
            clear_cancellation_fields(frm);
            apply_cancellation_visibility(frm);
            apply_intervention_visibility(frm);
            return;
        }

        frappe.call({
            method:
                "ir.industrial_relations.doctype.no_further_action_form." +
                "no_further_action_form.get_outcome_state",
            args: {
                outcome_type: frm.doc.outcome_type,
            },
            callback(r) {
                const state = r.message || {};
                const isCancellation = state.is_cancellation ? 1 : 0;

                frm.__nfa_is_cancellation = Boolean(isCancellation);

                if (!isCancellation) {
                    clear_cancellation_fields(frm);
                }

                apply_cancellation_visibility(frm);
                apply_intervention_visibility(frm);
            },
        });
    },

    fetch_intervention_data(frm) {
        if (!(frm.doc.ir_intervention && frm.doc.linked_intervention)) return;

        frappe.call({
            method:
                "ir.industrial_relations.doctype.no_further_action_form." +
                "no_further_action_form.fetch_intervention_data",
            args: {
                intervention_type: frm.doc.ir_intervention,
                intervention_name: frm.doc.linked_intervention,
            },
            freeze: true,
            freeze_message: __("Loading linked intervention..."),
            callback(r) {
                const data = r.message || {};

                [
                    "employee",
                    "names",
                    "designation",
                    "company",
                    "letter_head",
                    "type_of_incapacity",
                    "details_of_incapacity",
                    "performance_details_nta",
                    "outcome_type",
                ].forEach((fieldname) => {
                    if (frm.fields_dict[fieldname] && fieldname in data) {
                        frm.set_value(fieldname, data[fieldname] || null);
                    }
                });

                set_child_table(frm, "ng_charges", data.ng_charges, {
                    indiv_charge: "indiv_charge",
                });

                set_child_table(
                    frm,
                    "disciplinary_history",
                    data.disciplinary_history,
                    {
                        disc_action: "disc_action",
                        date: "date",
                        sanction: "sanction",
                        charges: "charges",
                    }
                );

                set_child_table(
                    frm,
                    "previous_incapacity_outcomes",
                    data.previous_incapacity_outcomes,
                    {
                        incap_proc: "incap_proc",
                        date: "date",
                        sanction: "sanction",
                        incap_details: "incap_details",
                    }
                );

                set_child_table(
                    frm,
                    "previous_performance_outcomes",
                    data.previous_performance_outcomes,
                    {
                        performance_action: "performance_action",
                        date: "date",
                        sanction: "sanction",
                        charges: "charges",
                    }
                );

                frm.set_value("linked_intervention_processed", 1);
                apply_intervention_visibility(frm);
                frm.trigger("update_outcome_state");
            },
        });
    },

    before_submit(frm) {
        if (!frm.doc.signed_ng) {
            frappe.msgprint(__("You must attach the signed outcome before submitting."));
            frappe.validated = false;
        }
    },
});

function load_allowed_outcomes(frm, clearCurrent = false) {
    frm.__nfa_allowed_outcomes = [];

    if (clearCurrent && frm.fields_dict.outcome_type) {
        frm.set_value("outcome_type", null);
    }

    if (!frm.doc.ir_intervention) {
        frm.set_query("outcome_type", () => ({
            filters: {
                name: ["=", "__invalid__"],
            },
        }));
        return;
    }

    frappe.call({
        method:
            "ir.industrial_relations.doctype.no_further_action_form." +
            "no_further_action_form.get_allowed_outcomes",
        args: {
            intervention_type: frm.doc.ir_intervention,
        },
        callback(r) {
            frm.__nfa_allowed_outcomes = r.message || [];
            frm.set_query("outcome_type", () => ({
                filters: {
                    name: [
                        "in",
                        frm.__nfa_allowed_outcomes.length
                            ? frm.__nfa_allowed_outcomes
                            : ["__invalid__"],
                    ],
                },
            }));
        },
    });
}

function set_default_outcome(frm) {
    if (!frm.doc.ir_intervention) {
        frm.set_value("outcome_type", null);
        return;
    }

    frappe.call({
        method:
            "ir.industrial_relations.doctype.no_further_action_form." +
            "no_further_action_form.get_intervention_config",
        args: {
            intervention_type: frm.doc.ir_intervention,
        },
        callback(r) {
            const config = r.message || {};
            frm.set_value("outcome_type", config.default_outcome || null);
        },
    });
}

function set_child_table(frm, fieldname, rows, mapping) {
    if (!frm.fields_dict[fieldname]) return;

    frm.clear_table(fieldname);
    (rows || []).forEach((row) => {
        const child = frm.add_child(fieldname);
        Object.entries(mapping).forEach(([target, source]) => {
            child[target] = row[source] || null;
        });
    });
    frm.refresh_field(fieldname);
}

function set_if_present(frm, fieldname, value) {
    if (frm.fields_dict[fieldname]) {
        frm.set_value(fieldname, value);
    }
}

function clear_intervention_fields(frm) {
    [
        "employee",
        "names",
        "designation",
        "company",
        "letter_head",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details_nta",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, null);
        }
    });

    [
        "ng_charges",
        "disciplinary_history",
        "previous_incapacity_outcomes",
        "previous_performance_outcomes",
    ].forEach((fieldname) => {
        if (!frm.fields_dict[fieldname]) return;
        frm.clear_table(fieldname);
        frm.refresh_field(fieldname);
    });
}

function clear_cancellation_fields(frm) {
    [
        "authorized_by",
        "auth_names",
        "auth_designation",
        "cancel_reason",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname] && frm.doc[fieldname]) {
            frm.set_value(fieldname, null);
        }
    });
}

function apply_cancellation_visibility(frm) {
    const isCancellation = Boolean(frm.__nfa_is_cancellation);

    [
        "authorized_by",
        "auth_names",
        "auth_designation",
        "cancel_reason",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.toggle_display(fieldname, isCancellation);
        }
    });

    if (frm.fields_dict.authorized_by) {
        frm.toggle_reqd("authorized_by", isCancellation);
    }

    if (frm.fields_dict.cancel_reason) {
        frm.toggle_reqd("cancel_reason", isCancellation);
    }
}

function apply_intervention_visibility(frm) {
    const type = frm.doc.ir_intervention;
    const isCancellation = Boolean(frm.__nfa_is_cancellation);

    const disciplinaryFields = [
        "details_of_offence_section",
        "ng_charges",
        "previous_disciplinary_offences_section",
        "disciplinary_history",
    ];

    const incapacityFields = [
        "incap_details_section",
        "type_of_incapacity",
        "details_of_incapacity",
        "previous_incapacity_outcomes_section",
        "previous_incapacity_outcomes",
    ];

    const performanceFields = [
        "details_of_poor_performance_section",
        "performance_details_nta",
        "history_of_poor_performance_section",
        "previous_performance_outcomes",
    ];

    frm.toggle_display(
        disciplinaryFields,
        type === "Disciplinary Action"
    );
    frm.toggle_display(
        incapacityFields,
        type === "Incapacity Proceedings"
    );
    frm.toggle_display(
        performanceFields,
        type === "Poor Performance"
    );

    if (frm.fields_dict.improvement_summary) {
        frm.toggle_display(
            "improvement_summary",
            type === "Poor Performance" && !isCancellation
        );
        frm.toggle_reqd(
            "improvement_summary",
            type === "Poor Performance" && !isCancellation
        );
    }
}
