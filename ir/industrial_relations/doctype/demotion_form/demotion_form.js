// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Demotion Form", {
    refresh(frm) {
        if (frm.doc.linked_intervention && !frm.doc.linked_intervention_processed) {
            frm.set_value("linked_intervention_processed", 1);
        }
    },

    company(frm) {
        if (!frm.doc.company) return;
        frappe.call({
            method: "ir.industrial_relations.doctype.demotion_form.demotion_form.fetch_company_letter_head",
            args: { company: frm.doc.company },
            callback(r) {
                frm.set_value("letter_head", (r.message || {}).letter_head || "");
            },
        });
    },

    from_date(frm) {
        validate_dates(frm);
    },

    to_date(frm) {
        validate_dates(frm);
    },

    before_save(frm) {
        return confirm_source_outcome_change(frm, "clear");
    },

    before_submit(frm) {
        if (!frm.doc.signed_demotion) {
            frappe.throw(__("You must attach the signed demotion before submitting."));
        }
        return confirm_source_outcome_change(frm, "overwrite");
    },
});

function validate_dates(frm) {
    if (frm.doc.from_date && frm.doc.to_date && frm.doc.to_date < frm.doc.from_date) {
        frappe.msgprint(__("End Date of Demotion cannot be before From Date."));
        frm.set_value("to_date", null);
    }
}

function confirm_source_outcome_change(frm, action) {
    if (!frm.doc.linked_intervention || !frm.doc.ir_intervention) return;
    const guard = action === "clear" ? "__demotion_save_confirmed" : "__demotion_submit_confirmed";
    if (frm[guard]) return;

    frappe.validated = false;
    return frappe.call({
        method: "ir.industrial_relations.doctype.demotion_form.demotion_form.get_linked_outcome",
        args: {
            doc_name: frm.doc.linked_intervention,
            doctype: frm.doc.ir_intervention,
        },
    }).then((r) => {
        const data = r.message || {};
        if (!data.outcome && !data.outcome_date && !data.outcome_start && !data.outcome_end) {
            frm[guard] = true;
            frappe.validated = true;
            return action === "clear" ? frm.save() : frm.save({ action: "submit" });
        }

        const message = action === "clear"
            ? __("The linked {0} currently contains outcome information. Saving this draft will clear it. Continue?", [frm.doc.ir_intervention])
            : __("The linked {0} currently contains outcome information. Submitting will replace it with this demotion outcome. Continue?", [frm.doc.ir_intervention]);

        frappe.confirm(message, () => {
            frm[guard] = true;
            frappe.validated = true;
            if (action === "clear") frm.save();
            else frm.save({ action: "submit" });
        });
    });
}
