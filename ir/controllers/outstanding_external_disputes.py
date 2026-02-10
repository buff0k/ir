# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

from ir.industrial_relations.utils import get_ir_notification_recipients


def outstanding_external_disputes():
    # Fetch External Dispute Resolution documents with no outcome
    outstanding_cases = frappe.get_all(
        "External Dispute Resolution",
        filters={"outcome": ""},
        fields=["name", "applicant_external", "respondent_external", "creation"]
    )

    if not outstanding_cases:
        frappe.logger().info("No outstanding external disputes found.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    # Prepare the email content
    email_subject = "Weekly HR Report: Outstanding External Dispute Resolution Matters"
    email_body = """
        <p>Dear {name},</p>
        <p>The following external dispute resolution matters are pending outcomes:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Case No.:</th>
                    <th>Applicant</th>
                    <th>Respondent</th>
                    <th>Outstanding Since</th>
                </tr>
            </thead>
            <tbody>
    """

    for case in outstanding_cases:
        case_url = get_url(f"/app/external-dispute-resolution/{case['name']}")
        email_body += f"""
            <tr>
                <td><a href="{case_url}">{case['name']}</a></td>
                <td>{case['applicant_external']}</td>
                <td>{case['respondent_external']}</td>
                <td>{formatdate(case['creation'])}</td>
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

    frappe.logger().info(f"Weekly outstanding external dispute resolution report sent to {len(recipient_emails)} recipients.")
