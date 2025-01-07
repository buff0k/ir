# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    # Define the documents to be created
    documents = [
        {
            "sec_head": "Working Hours Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"doctype": "Contract Paragraph", "ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        },
        {
            "sec_head": "Remuneration Placeholder",
            "notes": "Placeholder",
            "sec_par": [{"doctype": "Contract Paragraph", "ss_num": "1", "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."}]
        }
    ]

    for doc in documents:
        # Create a new document with the sec_head as the name
        new_doc = frappe.get_doc({
            "doctype": "Contract Section",
            "name": doc["sec_head"],
            "sec_head": doc["sec_head"],
            "notes": doc["notes"],
            "sec_par": doc["sec_par"]
        })

        # Insert the document
        new_doc.insert(ignore_permissions=True)

        # Automatically submit the document
        new_doc.submit()

    # Commit the transaction after all documents are created and submitted
    frappe.db.commit()

    # Log successful setup
    frappe.logger().info("Default Contract Section documents created and submitted successfully.")
