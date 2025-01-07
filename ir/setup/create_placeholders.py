# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe

def execute():
    # Define the documents to be created
    documents = [
        {
            "sec_head": "Working Hours Placeholder",
            "notes": "Placeholder",
            "sec_par": [
                {
                    "ss_num": "1",
                    "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."
                }
            ]
        },
        {
            "sec_head": "Remuneration Placeholder",
            "notes": "Placeholder",
            "sec_par": [
                {
                    "ss_num": "1",
                    "clause_text": "This is a Placeholder Only and Should be Replaced by the Server Script at Runtime."
                }
            ]
        }
    ]

    for doc in documents:
        # Create a new document
        new_doc = frappe.new_doc("Contract Section")
        new_doc.name = doc["sec_head"]  # Explicitly set the name
        new_doc.sec_head = doc["sec_head"]
        new_doc.notes = doc["notes"]

        # Populate the child table with proper child documents
        for child in doc["sec_par"]:
            new_doc.append("sec_par", {
                "ss_num": child["ss_num"],
                "clause_text": child["clause_text"]
            })

        # Insert the document, bypassing naming rules
        new_doc.flags.ignore_naming_rule = True
        new_doc.insert(ignore_permissions=True)

        # Automatically submit the document
        new_doc.submit()

    # Commit the transaction after all documents are created and submitted
    frappe.db.commit()

    # Log successful setup
    frappe.logger().info("Default Contract Section documents created and submitted successfully.")
