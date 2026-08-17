# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

from ir.industrial_relations.email_style import EMAIL_STYLE_BLOCK, email_header, greeting, intro, signoff
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

    # The table content is identical for every recipient (no Designation/Branch
    # filtering here - see permissions.py's BRANCH_LIMITED_DOCTYPES comment), so
    # it's built once and reused; only the greeting is personalised per recipient.
    email_subject = "Weekly HR Report: Outstanding External Dispute Resolution Matters"
    table_html = """
        <table class="ir-email-table">
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
        table_html += f"""
            <tr>
                <td><a href="{case_url}">{case['name']}</a></td>
                <td>{case['applicant_external']}</td>
                <td>{case['respondent_external']}</td>
                <td>{formatdate(case['creation'])}</td>
            </tr>
        """

    table_html += "</tbody></table>"

    # Send email to each recipient
    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = (full_name.split(" ")[0] if full_name else "Valued IR Team")

        email_body = EMAIL_STYLE_BLOCK
        email_body += greeting(first_name)
        email_body += intro("The following external dispute resolution matters are pending outcomes:")
        email_body += table_html
        email_body += signoff()

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=email_body,
            header=email_header(email_subject, "urgent"),
        )

    frappe.logger().info(f"Weekly outstanding external dispute resolution report sent to {len(recipient_emails)} recipients.")
