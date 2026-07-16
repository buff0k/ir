# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now


def execute():
    """
    Backfill the new List of Offences.offence_code field for every historic
    Disciplinary Action, including Draft, Submitted and Cancelled records.

    Final Charges are aligned conservatively:
    - missing rows are created;
    - rows at the same idx are updated when their code_item differs;
    - existing customised charge wording is retained when code_item is unchanged;
    - surplus rows are removed only when the table has more rows than offences.

    Direct child-table SQL is intentional so submitted/cancelled parent records do
    not need to be reopened or saved.
    """
    if not frappe.db.has_column("List of Offences", "offence_code"):
        frappe.throw(
            "Run bench migrate after adding List of Offences.offence_code before this patch."
        )

    parents = frappe.get_all(
        "Disciplinary Action", fields=["name", "docstatus"], order_by="creation asc"
    )

    for parent_row in parents:
        parent = parent_row.name
        offences = frappe.get_all(
            "List of Offences",
            filters={
                "parent": parent,
                "parenttype": "Disciplinary Action",
                "parentfield": "offences",
            },
            fields=["name", "idx", "code_item"],
            order_by="idx asc",
        )
        charges = frappe.get_all(
            "Disciplinary Charges",
            filters={
                "parent": parent,
                "parenttype": "Disciplinary Action",
                "parentfield": "final_charges",
            },
            fields=["name", "idx", "code_item", "charge"],
            order_by="idx asc",
        )

        descriptions = {}
        code_items = list({row.code_item for row in offences if row.code_item})
        if code_items:
            descriptions = {
                row.name: row.offence_description or ""
                for row in frappe.get_all(
                    "Disciplinary Offence",
                    filters={"name": ["in", code_items]},
                    fields=["name", "offence_description"],
                )
            }

        for offence in offences:
            frappe.db.set_value(
                "List of Offences",
                offence.name,
                "offence_code",
                offence.code_item or "",
                update_modified=False,
            )

        for index, offence in enumerate(offences):
            description = descriptions.get(offence.code_item, "")

            if index < len(charges):
                charge = charges[index]
                updates = {"idx": index + 1}
                if (charge.code_item or "") != (offence.code_item or ""):
                    updates["code_item"] = offence.code_item or ""
                    updates["charge"] = description
                elif not charge.charge:
                    updates["charge"] = description

                frappe.db.set_value(
                    "Disciplinary Charges",
                    charge.name,
                    updates,
                    update_modified=False,
                )
            else:
                frappe.db.sql(
                    """
                    INSERT INTO `tabDisciplinary Charges`
                        (`name`, `creation`, `modified`, `modified_by`, `owner`,
                         `docstatus`, `idx`, `parent`, `parentfield`, `parenttype`,
                         `code_item`, `charge`)
                    VALUES
                        (%s, %s, %s, %s, %s,
                         %s, %s, %s, 'final_charges', 'Disciplinary Action',
                         %s, %s)
                    """,
                    (
                        frappe.generate_hash(length=10),
                        now(),
                        now(),
                        "Administrator",
                        "Administrator",
                        parent_row.docstatus,
                        index + 1,
                        parent,
                        offence.code_item or "",
                        description,
                    ),
                )

        for surplus in charges[len(offences):]:
            frappe.db.delete("Disciplinary Charges", {"name": surplus.name})

    frappe.db.commit()
