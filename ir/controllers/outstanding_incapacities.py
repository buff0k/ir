# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

from ir.industrial_relations.utils import get_ir_notification_recipients


def outstanding_incapacities():
    # Fetch Incapacity Proceedings documents with no outcome
    outstanding_cases = frappe.get_all(
        "Incapacity Proceedings",
        filters={"outcome": ""},
        fields=["name", "accused", "accused_name", "creation", "branch"]
    )

    if not outstanding_cases:
        frappe.logger().info("No outstanding incapacity processes found.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    # Prepare the email content
    email_subject = "Weekly HR Report: Outstanding Incapacity Processes"
    email_body = """
        <p>Dear {name},</p>
        <p>The following incapacity processes are pending outcomes:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Incapacity Proceeding</th>
                    <th>Employee Name</th>
                    <th>Employee Coy</th>
                    <th>Outstanding Since</th>
                    <th>Site</th>
                </tr>
            </thead>
            <tbody>
    """

    for case in outstanding_cases:
        case_url = get_url(f"/app/incapacity-proceedings/{case['name']}")
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
    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = (full_name.split(" ")[0] if full_name else "Valued IR Team")
        personalized_email_body = email_body.format(name=first_name)

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=personalized_email_body
        )

    frappe.logger().info(f"Weekly outstanding incapacity report sent to {len(recipient_emails)} recipients.")
