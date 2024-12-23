import frappe

def execute():
    # This function will update the 'sanction' field in the 'Disciplinary History' child table
    # by replacing it with the 'disc_offence_out' value from the 'Offence Outcome' table.

    # SQL query to perform the update directly on the database
    query = """
    UPDATE `tabDisciplinary History` dh
    INNER JOIN `tabOffence Outcome` oo ON dh.sanction = oo.name
    SET dh.sanction = oo.disc_offence_out;
    """

    # Execute the SQL query
    frappe.db.sql(query)

    # Commit the transaction (although Frappe usually commits automatically after patches)
    frappe.db.commit()

    # Optional: Log or print a message for patch execution confirmation
    print("Patch to update Disciplinary History sanction field has been applied.")