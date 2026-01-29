# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    frappe.flags.ignore_permissions = True

    # Step 1: Clear the `linked_nta` field for all Disciplinary Outcome Reports
    frappe.db.sql("""
        UPDATE `tabDisciplinary Outcome Report`
        SET linked_nta = NULL
    """)

    # Step 2: Fetch all Disciplinary Outcome Report documents
    outcome_reports = frappe.get_all(
        "Disciplinary Outcome Report",
        fields=["name", "linked_disciplinary_action", "linked_incapacity_proceeding"]
    )

    for report in outcome_reports:
        linked_nta_rows = []

        # Step 3: Fetch linked NTAs from the Disciplinary Action, if present
        if report.get("linked_disciplinary_action"):
            try:
                disciplinary_action = frappe.get_doc("Disciplinary Action", report.get("linked_disciplinary_action"))
                for row in disciplinary_action.linked_nta or []:
                    linked_nta_rows.append({"document_name": row.linked_nta})
            except frappe.DoesNotExistError:
                frappe.log_error(f"Disciplinary Action {report.get('linked_disciplinary_action')} not found, skipping.", "Patch Error")

        # Step 4: Fetch linked NTAs from the Incapacity Proceedings, if present
        if report.get("linked_incapacity_proceeding"):
            try:
                incapacity_proceeding = frappe.get_doc("Incapacity Proceedings", report.get("linked_incapacity_proceeding"))
                for row in incapacity_proceeding.linked_nta or []:
                    linked_nta_rows.append({"document_name": row.linked_nta})
            except frappe.DoesNotExistError:
                frappe.log_error(f"Incapacity Proceedings {report.get('linked_incapacity_proceeding')} not found, skipping.", "Patch Error")

        # Step 5: Remove duplicates based on the `document_name` field
        seen = set()
        linked_nta_rows = [row for row in linked_nta_rows if row["document_name"] not in seen and not seen.add(row["document_name"])]

        # Step 6: Update the `linked_nta` child table for the Disciplinary Outcome Report
        if linked_nta_rows:
            try:
                # Clear existing child table data
                frappe.db.sql("""
                    DELETE FROM `tabNTA Selector`
                    WHERE parent = %s
                """, (report["name"],))

                # Insert new rows
                for row in linked_nta_rows:
                    frappe.db.sql("""
                        INSERT INTO `tabNTA Selector` (name, parent, parentfield, parenttype, linked_nta)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        frappe.generate_hash(length=10),  # Generate unique row ID
                        report["name"],  # Parent document
                        "linked_nta",  # Parentfield
                        "Disciplinary Outcome Report",  # Parenttype
                        row["document_name"],  # Linked NTA
                    ))

                # Log success for each updated document
                frappe.msgprint(f"Updated linked_nta for Disciplinary Outcome Report {report['name']}.")
            except Exception as e:
                frappe.log_error(message=str(e), title=f"Patch Error: Update linked_nta for {report['name']}")
                frappe.msgprint(f"Failed to update linked_nta for Disciplinary Outcome Report {report['name']}. Check logs for details.")
        else:
            frappe.msgprint(f"No linked NTAs found for Disciplinary Outcome Report {report['name']}.", alert=True)

    # Commit changes to the database
    frappe.db.commit()
