import frappe

def execute():
    # Define the documents to be created
    documents = [
        {
            "sec_head": "Working Hours Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        },
        {
            "sec_head": "Remuneration Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        }
    ]

    for doc in documents:
        # Create a new document with default naming rule
        new_doc = frappe.get_doc({
            "doctype": "Contract Section",
            "notes": doc["notes"],
            "sec_head": doc["sec_head"],
            "sec_par": doc["sec_par"]
        })

        # Insert the document (this will use the naming rule)
        new_doc.insert()

        # Commit the transaction to ensure the document is saved
        frappe.db.commit()

        # Process the document to set the name as per sec_head
        update_document_name(doc["sec_head"])

def update_document_name(desired_name):
    """Update document name after creation."""
    try:
        # Use pattern matching to find the document with the naming rule format
        pattern = f"{desired_name}%"  # Pattern to match names starting with desired_name
        result = frappe.db.sql("""
            SELECT name FROM `tabContract Section`
            WHERE name LIKE %s
            ORDER BY creation DESC
            LIMIT 1
        """, (pattern,), as_dict=True)

        if result:
            auto_generated_name = result[0]['name']
            # Fetch the document using the auto-generated name
            doc = frappe.get_doc("Contract Section", auto_generated_name)

            # Rename the document to the desired name
            if doc.name != desired_name:

                # Update the document with the new name
                doc._rename(name=desired_name)

                # Submit document
                doc.submit()

                # Commit changes
                frappe.db.commit()

                frappe.logger().info(f"Document renamed from {auto_generated_name} to {desired_name}.")
            else:
                frappe.logger().info(f"Document already has the desired name {desired_name}.")
        else:
            frappe.logger().error(f"Document with sec_head '{desired_name}' not found.")

    except frappe.exceptions.DoesNotExistError as e:
        frappe.logger().error(f"Error updating document {desired_name}: {str(e)}")
        raise

