import frappe

def ensure_employee_links():
    """Ensure required Document Links exist in the Employee DocType."""
    required_links = [
        {"link_doctype": "Disciplinary Action", "link_fieldname": "accused"},
        {"link_doctype": "Contract of Employment", "link_fieldname": "employee"},
        {"link_doctype": "Incapacity Proceedings", "link_fieldname": "accused"},
        {"link_doctype": "Appeal Against Outcome", "link_fieldname": "employee"}
    ]

    # Fetch existing links
    existing_links = frappe.get_all(
        "DocType Link",
        filters={"parent": "Employee"},
        fields=["link_doctype", "link_fieldname"]
    )

    existing_links_set = {(link["link_doctype"], link["link_fieldname"]) for link in existing_links}

    for link in required_links:
        if (link["link_doctype"], link["link_fieldname"]) not in existing_links_set:
            doc = frappe.get_doc({
                "doctype": "DocType Link",
                "parent": "Employee",
                "parentfield": "links",
                "parenttype": "DocType",
                "link_doctype": link["link_doctype"],
                "link_fieldname": link["link_fieldname"],
                "group": "Industrial Relations"
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
            frappe.msgprint(f"Added missing Document Link: {link['link_doctype']} to Employee")

    print("✅ Employee Document Links verified/updated.")
