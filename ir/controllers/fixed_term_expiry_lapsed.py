# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url

from ir.industrial_relations.utils import get_ir_notification_recipients


def fixed_term_expiry_lapsed():
    # Fetch contracts already expired (end_date < today) with additional filters
    lapsed_contracts = frappe.get_all(
        "Contract of Employment",
        filters={
            "end_date": ["<", frappe.utils.today()],
            "has_expiry": 1,
        },
        fields=["name", "employee", "employee_name", "end_date", "branch"]
    )

    # Exclude contracts where the linked Employee's status is "Left"
    filtered_contracts = [
        contract for contract in lapsed_contracts
        if frappe.get_value("Employee", contract["employee"], "status") != "Left"
    ]

    # Further filter contracts to exclude those with a later contract for the same employee
    def has_later_contract(employee, current_end_date):
        later_contracts = frappe.get_all(
            "Contract of Employment",
            filters={
                "employee": employee,
                "start_date": [">", current_end_date],
            },
            fields=["name"]
        )
        return bool(later_contracts)

    filtered_contracts = [
        contract for contract in filtered_contracts
        if not has_later_contract(contract["employee"], contract["end_date"])
    ]

    if not filtered_contracts:
        frappe.logger().info("No lapsed contracts found after applying filters.")
        return

    # Fetch recipients (from IR Role Restrictions -> report_recipients)
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    # Prepare the email content
    email_subject = "Weekly HR Report: Fixed-Term Contracts Already Expired"
    email_body = """
        <p>Dear {name},</p>
        <p>Please find below the list of fixed-term contracts that have already expired:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Contract Name</th>
                    <th>Employee Name</th>
                    <th>Employee Coy</th>
                    <th>Contract End Date</th>
                    <th>Site</th>
                </tr>
            </thead>
            <tbody>
    """

    for contract in filtered_contracts:
        contract_url = get_url(f"/app/contract-of-employment/{contract['name']}")
        email_body += f"""
            <tr>
                <td><a href="{contract_url}">{contract['name']}</a></td>
                <td>{contract['employee_name']}</td>
                <td>{contract['employee']}</td>
                <td>{contract['end_date']}</td>
                <td>{contract['branch']}</td>
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

    frappe.logger().info(f"Weekly HR report (lapsed contracts) sent to {len(recipient_emails)} recipients.")
