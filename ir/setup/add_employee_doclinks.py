# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def ensure_employee_links():
    """Ensure required Document Links exist in the Employee DocType."""

    required_links = [
        # Normal links
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
        {"link_doctype": "KPI Review Employees", "link_fieldname": "employee", "parent_doctype": "KPI Review", "table_fieldname": "employees", "is_child_table": 1},
        {"link_doctype": "Termination Form", "link_fieldname": "requested_for"}
    ]

    existing_links = frappe.get_all(
        "DocType Link",
        filters={"parent": "Employee"},
        fields=["link_doctype", "link_fieldname", "parent_doctype", "table_fieldname", "is_child_table"]
    )

    existing_links_set = {
        (
            link["link_doctype"],
            link["link_fieldname"],
            link.get("parent_doctype") or "",
            link.get("table_fieldname") or "",
            int(link.get("is_child_table", 0))
        )
        for link in existing_links
    }

    for link in required_links:
        key = (
            link["link_doctype"],
            link["link_fieldname"],
            link.get("parent_doctype", ""),
            link.get("table_fieldname", ""),
            int(link.get("is_child_table", 0))
        )

        if key not in existing_links_set:
            doc = frappe.get_doc({
                "doctype": "DocType Link",
                "parent": "Employee",
                "parentfield": "links",
                "parenttype": "DocType",
                "link_doctype": link["link_doctype"],
                "link_fieldname": link["link_fieldname"],
                "parent_doctype": link.get("parent_doctype"),
                "table_fieldname": link.get("table_fieldname"),
                "is_child_table": link.get("is_child_table", 0),
                "group": "Industrial Relations"
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(f"✅ Added: {link['link_doctype']} ({'child' if link.get('is_child_table') else 'direct'})")

