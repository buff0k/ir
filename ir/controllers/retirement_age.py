# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url

from ir.industrial_relations.utils import filter_rows_for_recipient, get_ir_notification_recipients


def retirement_age():
    # Fetch employees retiring within the next three months with additional filters
    retiring_employees = frappe.get_all(
        "Employee",
        filters={
            "date_of_retirement": ["between", [frappe.utils.today(), frappe.utils.add_days(frappe.utils.today(), 90)]]
        },
        fields=["name", "employee_name", "designation", "date_of_retirement", "branch"]
    )

    # Exclude employees where the status is "Left"
    filtered_employees = [
        employee for employee in retiring_employees
        if frappe.get_value("Employee", employee["name"], "status") != "Left"
    ]

    if not filtered_employees:
        frappe.logger().info("No retiring employees found after applying filters.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    email_subject = "Weekly HR Report: Employee's nearing Retirement Date"
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

        email_body = f"""
            <p>Dear {first_name},</p>
            <p>Please find below the list of employees retiring soon:</p>
            <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
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

    frappe.logger().info(f"Weekly HR report sent to {sent_count} recipients.")
