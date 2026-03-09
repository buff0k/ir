# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, today

from ir.industrial_relations.utils import get_ir_notification_recipients


def fixed_term_expiry_lapsed():
    # Fetch expired fixed-term contracts that are not project-based
    lapsed_contracts = frappe.get_all(
        "Contract of Employment",
        filters={
            "end_date": ["<", today()],
            "has_expiry": 1,
            "has_project": 0,
        },
        fields=["name", "employee", "employee_name", "end_date", "branch"]
    )

    if not lapsed_contracts:
        frappe.logger().info("No lapsed contracts found.")
        return

    # Exclude contracts where the linked Employee status is "Left"
    employee_ids = list({d.employee for d in lapsed_contracts if d.employee})
    active_employees = set(
        frappe.get_all(
            "Employee",
            filters={
                "name": ["in", employee_ids],
                "status": ["!=", "Left"],
            },
            pluck="name"
        )
    )

    filtered_contracts = [
        contract for contract in lapsed_contracts
        if contract.employee in active_employees
    ]

    # Further exclude contracts where the employee has a later contract
    def has_later_contract(employee, current_end_date):
        return bool(
            frappe.get_all(
                "Contract of Employment",
                filters={
                    "employee": employee,
                    "start_date": [">", current_end_date],
                },
                fields=["name"],
                limit=1
            )
        )

    filtered_contracts = [
        contract for contract in filtered_contracts
        if not has_later_contract(contract.employee, contract.end_date)
    ]

    if not filtered_contracts:
        frappe.logger().info("No lapsed contracts found after applying filters.")
        return

    # Fetch recipients
    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    # Prepare email content
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
        contract_url = get_url(f"/app/contract-of-employment/{contract.name}")
        email_body += f"""
            <tr>
                <td><a href="{contract_url}">{contract.name}</a></td>
                <td>{contract.employee_name}</td>
                <td>{contract.employee}</td>
                <td>{contract.end_date}</td>
                <td>{contract.branch}</td>
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
        first_name = full_name.split(" ")[0] if full_name else "Valued IR Team"
        personalized_email_body = email_body.format(name=first_name)

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=personalized_email_body
        )

    frappe.logger().info(
        f"Weekly HR report (lapsed contracts) sent to {len(recipient_emails)} recipients."
    )