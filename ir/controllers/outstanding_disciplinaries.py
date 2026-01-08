# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

def outstanding_disciplinaries():
    # Fetch Disciplinary Action documents with no outcome
    outstanding_cases = frappe.get_all(
        "Disciplinary Action",
        filters={"outcome": ""},
        fields=["name", "accused", "accused_name", "creation", "branch"]
    )

    if not outstanding_cases:
        frappe.logger().info("No outstanding disciplinary actions found.")
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
    email_subject = "Weekly HR Report: Outstanding Disciplinary Actions"
    email_body = """
        <p>Dear {name},</p>
        <p>The following disciplinary actions are pending outcomes:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Disciplinary Action</th>
                    <th>Employee Name</th>
                    <th>Employee Coy</th>
                    <th>Outstanding Since</th>
                    <th>Site</th>
                </tr>
            </thead>
            <tbody>
    """

    for case in outstanding_cases:
        case_url = get_url(f"/app/disciplinary-action/{case['name']}")
        email_body += f"""
            <tr>
                <td><a href="{case_url}">{case['name']}</a></td>
                <td>{case['accused_name']}</td>
                <td>{case['accused']}</td>
                <td>{formatdate(case['creation'])}</td>
                <td>{case['branch']}</td>
            </tr>
        """

    email_body += """
            </tbody>
        </table>
        <p>Kind regards,<br>Industrial Relations</p>
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

    frappe.logger().info(f"Weekly outstanding disciplinary report sent to {len(valid_recipients)} recipients.")
