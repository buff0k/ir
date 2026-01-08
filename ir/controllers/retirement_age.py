# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url

def retirement_age():
    # Fetch employees retiring within the next three months with additional filters
    retiring_employees = frappe.get_all(
        "Employee",
        filters={
            "date_of_retirement": ["between", [frappe.utils.today(), frappe.utils.add_days(frappe.utils.today(), 90)]]
        },
        fields=["name", "employee_name", "date_of_retirement", "branch"]
    )

    # Exclude employees where the status is "Left"
    filtered_employees = [
        employee for employee in retiring_employees
        if frappe.get_value("Employee", employee["name"], "status") != "Left"
    ]

    if not filtered_employees:
        frappe.logger().info("No retiring employees found after applying filters.")
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
    email_subject = "Weekly HR Report: Employee's nearing Retirement Date"
    email_body = """
        <p>Dear {name},</p>
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

    for employee in filtered_employees:
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
