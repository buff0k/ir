import frappe

def execute():
    frappe.flags.ignore_permissions = True

    # Step 1: Clear old linked fields from the Incapacity Proceedings Doctype
    frappe.db.sql("""
        UPDATE `tabIncapacity Proceedings`
        SET linked_nta = NULL, 
            linked_outcome = NULL,
            linked_dismissal = NULL,
            linked_demotion = NULL,
            linked_pay_reduction = NULL,
            linked_not_guilty = NULL,
            linked_suspension = NULL,
            linked_vsp = NULL,
            linked_cancellation = NULL
    """)

    # Step 2: Map Table Multiselect fields to their respective linked Doctypes and fields in child tables
    linked_tables = {
        "linked_nta": {"doctype": "NTA Hearing", "child_table_field": "linked_nta"},
        "linked_outcome": {"doctype": "Disciplinary Outcome Report", "child_table_field": "linked_outcome"},
        "linked_dismissal": {"doctype": "Dismissal Form", "child_table_field": "linked_dismissal"},
        "linked_demotion": {"doctype": "Demotion Form", "child_table_field": "linked_demotion"},
        "linked_pay_reduction": {"doctype": "Pay Reduction Form", "child_table_field": "linked_pay_reduction"},
        "linked_not_guilty": {"doctype": "Not Guilty Form", "child_table_field": "linked_not_guilty"},
        "linked_suspension": {"doctype": "Suspension Form", "child_table_field": "linked_suspension"},
        "linked_vsp": {"doctype": "Voluntary Seperation Agreement", "child_table_field": "linked_vsp"},
        "linked_cancellation": {"doctype": "Hearing Cancellation Form", "child_table_field": "linked_cancellation"}
    }

    # Step 3: Get all Incapacity Proceedings documents
    incapacity_proceedings_list = frappe.get_all("Incapacity Proceedings", fields=["name"])

    for incapacity_proceedings in incapacity_proceedings_list:
        doc_name = incapacity_proceedings.name
        incapacity_doc = frappe.get_doc("Incapacity Proceedings", doc_name)

        # Allow updates to submitted documents without validation errors
        incapacity_doc.flags.ignore_validate_update_after_submit = True

        # Step 4: Clear existing data in the child tables
        for child_field in linked_tables.keys():
            incapacity_doc.set(child_field, [])

        # Step 5: Populate the Table Multiselect fields
        for child_field, table_info in linked_tables.items():
            doctype_name = table_info["doctype"]
            child_table_field = table_info["child_table_field"]

            # Fetch linked documents for the current Doctype
            linked_docs = frappe.get_all(
                doctype_name, 
                filters={"linked_incapacity_proceeding": doc_name}, 
                fields=["name"]
            )

            # Append entries to the child table
            for linked_doc in linked_docs:
                incapacity_doc.append(child_field, {
                    child_table_field: linked_doc["name"]  # Populate the correct field in the child table
                })

        # Save the updated Incapacity Proceeding document
        incapacity_doc.save()

    # Commit changes to the database
    frappe.db.commit()
