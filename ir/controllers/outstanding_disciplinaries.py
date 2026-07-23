# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

from ir.industrial_relations.utils import filter_rows_for_recipient, get_ir_notification_recipients


def outstanding_disciplinaries():
    # Fetch Disciplinary Action documents with no outcome
    outstanding_cases = frappe.get_all(
        "Disciplinary Action",
        filters={"outcome": ""},
        fields=["name", "accused", "accused_name", "accused_pos", "creation", "branch"]
    )

    if not outstanding_cases:
        frappe.logger().info("No outstanding disciplinary actions found.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    email_subject = "Weekly HR Report: Outstanding Disciplinary Actions"
    sent_count = 0

    for email in recipient_emails:
        cases = filter_rows_for_recipient(
            outstanding_cases, email,
            doctype="Disciplinary Action",
            designation_field="accused_pos",
            employee_field="accused",
        )
        if not cases:
            continue

        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = (full_name.split(" ")[0] if full_name else "Valued IR Team")

        email_body = f"""
            <p>Dear {first_name},</p>
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

        for case in cases:
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

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=email_body
        )
        sent_count += 1

    frappe.logger().info(f"Weekly outstanding disciplinary report sent to {sent_count} recipients.")
