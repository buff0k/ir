# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    # Fetch all Warning Form documents
    warning_forms = frappe.get_all(
        "Warning Form",
        fields=["name", "warning_type"]
    )

    for form in warning_forms:
        if not form.warning_type:
            continue

        # Fetch Offence Outcome linked to the warning_type
        offence_outcome = frappe.get_value(
            "Offence Outcome",
            form.warning_type,
            ["disc_offence_out", "expiry_days"],
            as_dict=True
        )

        if offence_outcome:
            # Update the fields in the Warning Form
            frappe.db.set_value(
                "Warning Form",
                form.name,
                {
                    "disc_offence_out": offence_outcome.get("disc_offence_out"),
                    "expiry_days": offence_outcome.get("expiry_days"),
                }
            )
            frappe.db.commit()
