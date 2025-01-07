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
        # Check if the document already exists
        new_doc = frappe.get_doc({
            "doctype": "Contract Section",
            "sec_head": doc["sec_head"],
            "notes": doc["notes"],
            "sec_par": doc["sec_par"]
        })
        
        # Explicitly set the document's name to sec_head
        new_doc.set_name(doc["sec_head"])

        # Insert the document
        new_doc.insert(ignore_permissions=True)

        # Automatically submit the document
        new_doc.submit()

    # Commit the transaction after all documents are created and submitted
    frappe.db.commit()

    # Log successful setup
    frappe.logger().info("Default Contract Section documents created and submitted successfully.")
