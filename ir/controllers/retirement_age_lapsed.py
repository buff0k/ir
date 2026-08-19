# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url

from ir.industrial_relations.email_style import EMAIL_STYLE_BLOCK, email_header, greeting, intro, signoff
from ir.industrial_relations.utils import filter_rows_for_recipient, get_ir_notification_recipients


def retirement_age_lapsed():
    # Fetch employees whose retirement date is in the past
    lapsed_retirements = frappe.get_all(
        "Employee",
        filters=[
            # Same trap as demotion_expiry.py: Frappe's query builder treats
            # a blank Date field as '0001-01-01' for "<" comparisons, so an
            # Employee with no date_of_retirement set would otherwise always
            # match "< today()" and be wrongly reported as lapsed.
            ["date_of_retirement", "is", "set"],
            ["date_of_retirement", "<", frappe.utils.today()],
        ],
        fields=["name", "employee_name", "designation", "date_of_retirement", "branch"]
    )

    # Exclude employees where the status is "Left"
    filtered_employees = [
        employee for employee in lapsed_retirements
        if frappe.get_value("Employee", employee["name"], "status") != "Left"
    ]

    if not filtered_employees:
        frappe.logger().info("No lapsed retirements found after applying filters.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    email_subject = "Weekly HR Report: Employees Past Retirement Date (Still Active)"
    sent_count = 0

    for email in recipient_emails:
        employees = filter_rows_for_recipient(
            filtered_employees, email,
            doctype="Employee",
            designation_field="designation",
            employee_field="name",
        )
        if not employees:
            continue

        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = (full_name.split(" ")[0] if full_name else "Valued IR Team")

        email_body = EMAIL_STYLE_BLOCK
        email_body += greeting(first_name)
        email_body += intro(
            "Please find below the list of employees whose retirement date is in the "
            "past but who are still active:"
        )
        email_body += """
            <table class="ir-email-table">
                <thead>
                    <tr>
                        <th>Coy. No.</th>
                        <th>Employee Name</th>
                        <th>Retirement Date</th>
                        <th>Site</th>
                    </tr>
                </thead>
                <tbody>
        """

        for employee in employees:
            employee_url = get_url(f"/app/employee/{employee['name']}")
            email_body += f"""
                <tr>
                    <td><a href="{employee_url}">{employee['name']}</a></td>
                    <td>{employee['employee_name']}</td>
                    <td>{employee['date_of_retirement']}</td>
                    <td>{employee['branch']}</td>
                </tr>
            """

        email_body += "</tbody></table>"
        email_body += signoff()

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=email_body,
            header=email_header(email_subject, "urgent"),
        )
        sent_count += 1

    frappe.logger().info(f"Weekly HR report (lapsed retirements) sent to {sent_count} recipients.")
