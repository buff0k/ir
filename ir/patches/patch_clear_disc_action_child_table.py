# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    if frappe.db.exists("DocType", "Disciplinary Action"):
        # List of child table fields in "Disciplinary Action"
        child_table_fields = [
            "linked_nta", "linked_outcome", "linked_warning", "linked_dismissal", "linked_demotion",
            "linked_pay_deduction", "linked_pay_reduction", "linked_not_guilty", "linked_suspension",
            "linked_vsp", "linked_cancellation", "linked_appeal"
        ]

        # Get all Disciplinary Action records
        disciplinary_actions = frappe.get_all("Disciplinary Action", fields=["name"])
        
        for action in disciplinary_actions:
            doc = frappe.get_doc("Disciplinary Action", action["name"])
            
            # Allow modification of submitted documents
            doc.flags.ignore_validate_update_after_submit = True
            doc.flags.ignore_permissions = True
            
            for field in child_table_fields:
                if hasattr(doc, field):  # Check if field exists before clearing
                    doc.set(field, [])  # Clear child table field
            
            doc.save(ignore_permissions=True)
        
        frappe.db.commit()  # Ensure database changes are saved
