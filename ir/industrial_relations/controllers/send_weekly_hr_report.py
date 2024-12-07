# Copyright (c) 2024, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url

def send_weekly_hr_report():
    # Fetch expiring contracts
    expiring_contracts = frappe.get_all(
        "Contract of Employment",
        filters={"end_date": ["between", [frappe.utils.today(), frappe.utils.add_days(frappe.utils.today(), 28)]]},
        fields=["name", "employee", "employee_name", "end_date"]
    )

    if not expiring_contracts:
        frappe.logger().info("No expiring contracts found.")
        return

    # Fetch recipients (IR Managers)
    recipients = frappe.get_all(
        'Has Role',
        filters={'role': 'IR Manager'},
        fields=['parent']
    )

    valid_recipients = [
        recipient['parent']
        for recipient in recipients
        if frappe.db.exists('User', recipient['parent']) and frappe.get_value('User', recipient['parent'], 'enabled')
    ]

    if not valid_recipients:
        frappe.logger().info("No valid IR Managers found.")
        return

    # Prepare the email content
    email_subject = "Weekly HR Report: Contracts Expiring Soon"
    email_body = """
        <p>Dear {name},</p>
        <p>Please find below the list of contracts expiring soon:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Contract Name</th>
                    <th>Employee Name</th>
                    <th>Employee Code</th>
                    <th>Contract End Date</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for contract in expiring_contracts:
        contract_url = get_url(f"/app/contract-of-employment/{contract['name']}")
        email_body += f"""
            <tr>
                <td><a href="{contract_url}">{contract['name']}</a></td>
                <td>{contract['employee_name']}</td>
                <td>{contract['employee']}</td>
                <td>{contract['end_date']}</td>
            </tr>
        """

    email_body += """
            </tbody>
        </table>
        <p>Kind regards,<br>Your HR Team</p>
    """

    # Send email to each recipient
    for recipient in valid_recipients:
        user_name = frappe.get_value('User', recipient, 'first_name') or "Valued IR Manager"
        personalized_email_body = email_body.format(name=user_name)

        frappe.sendmail(
            recipients=[recipient],
            subject=email_subject,
            message=personalized_email_body
        )

    frappe.logger().info(f"Weekly HR report sent to {len(valid_recipients)} recipients.")
