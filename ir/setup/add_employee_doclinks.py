# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def ensure_employee_links():
    """Ensure required Document Links exist in the Employee DocType."""
    
    # Check if current schema supports child_table_doctype
    has_child_table_support = frappe.db.has_column("DocType Link", "child_table_doctype")

    # Base fields to fetch from existing DocType Links
    fields = ["link_doctype", "link_fieldname"]
    if has_child_table_support:
        fields += ["child_table_doctype", "is_child_table"]

    existing_links = frappe.get_all(
        "DocType Link",
        filters={"parent": "Employee"},
        fields=fields
    )

    # Set of existing link entries
    existing_set = {
        (
            l["link_doctype"],
            l["link_fieldname"],
            l.get("child_table_doctype", "") if has_child_table_support else "",
            int(l.get("is_child_table", 0)) if has_child_table_support else 0
        )
        for l in existing_links
    }

    # All required DocType Links
    required_links = [
        {"link_doctype": "Disciplinary Action", "link_fieldname": "accused"},
        {"link_doctype": "Contract of Employment", "link_fieldname": "employee"},
        {"link_doctype": "Incapacity Proceedings", "link_fieldname": "accused"},
        {"link_doctype": "Appeal Against Outcome", "link_fieldname": "employee"},
        {"link_doctype": "NTA Hearing", "link_fieldname": "employee"},
        {"link_doctype": "Not Guilty Form", "link_fieldname": "employee"},
        {"link_doctype": "Warning Form", "link_fieldname": "employee"},
        {"link_doctype": "Suspension Form", "link_fieldname": "employee"},
        {"link_doctype": "Demotion Form", "link_fieldname": "employee"},
        {"link_doctype": "Pay Deduction Form", "link_fieldname": "employee"},
        {"link_doctype": "Pay Reduction Form", "link_fieldname": "employee"},
        {"link_doctype": "Dismissal Form", "link_fieldname": "employee"},
        {"link_doctype": "Voluntary Seperation Agreement", "link_fieldname": "employee"},
        {"link_doctype": "Hearing Cancellation Form", "link_fieldname": "employee"},
    ]

    # Include the KPI Review child table link only if schema supports it
    if has_child_table_support:
        required_links.append({
            "link_doctype": "KPI Review",
            "link_fieldname": "employee",
            "child_table_doctype": "KPI Review Employees",
            "is_child_table": 1
        })

    # Insert any missing links
    for link in required_links:
        key = (
            link["link_doctype"],
            link["link_fieldname"],
            link.get("child_table_doctype", "") if has_child_table_support else "",
            int(link.get("is_child_table", 0)) if has_child_table_support else 0
        )

        if key not in existing_set:
            doc = frappe.get_doc({
                "doctype": "DocType Link",
                "parent": "Employee",
                "parentfield": "links",
                "parenttype": "DocType",
                "link_doctype": link["link_doctype"],
                "link_fieldname": link["link_fieldname"],
                "group": "Industrial Relations"
            })

            if has_child_table_support:
                doc.child_table_doctype = link.get("child_table_doctype", "")
                doc.is_child_table = link.get("is_child_table", 0)

            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(f"✅ Linked {link['link_doctype']} to Employee via {'child table' if link.get('is_child_table') else 'field'}.")

    print("✅ All Employee DocType Links are present.")
