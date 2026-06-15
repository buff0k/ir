# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, getdate, today

from ir.industrial_relations.utils import get_ir_notification_recipients


CONTRACT_DOCTYPE = "Contract of Employment"
EMPLOYEE_DOCTYPE = "Employee"


def _as_bool(value):
    """Return True for Frappe check-field truthy values."""
    return bool(int(value or 0))


def _contract_blocks_lapsed_notice(contract, report_date):
    """
    Return True if this later contract means the employee should NOT be
    reported as having no valid current contract.

    Blocking contracts are:
    - Project-based contracts, because their end_date is only indicative.
    - Indefinite/no-expiry contracts.
    - Fixed-term contracts that have not yet expired as at report_date.
    """
    has_expiry = _as_bool(contract.get("has_expiry"))
    has_project = _as_bool(contract.get("has_project"))
    end_date = contract.get("end_date")

    if has_project:
        return True

    if not has_expiry:
        return True

    if end_date and getdate(end_date) >= report_date:
        return True

    return False


def _has_later_blocking_contract(employee, current_contract_name, current_start_date, report_date):
    """
    Check whether the employee has a later contract that is still valid,
    indefinite, or project-based.

    We compare against current_start_date, not current_end_date, because a
    replacement contract may start before or on the old contract's expiry date.
    """
    if not employee or not current_start_date:
        return False

    contracts = frappe.get_all(
        CONTRACT_DOCTYPE,
        filters={
            "employee": employee,
            "name": ["!=", current_contract_name],
            "docstatus": 1,
            "start_date": [">=", current_start_date],
        },
        fields=[
            "name",
            "employee",
            "start_date",
            "end_date",
            "has_expiry",
            "has_project",
            "creation",
            "modified",
        ],
        order_by="start_date asc, creation asc",
    )

    for contract in contracts:
        if _contract_blocks_lapsed_notice(contract, report_date):
            return True

    return False


def fixed_term_expiry_lapsed():
    """
    Weekly HR report: fixed-term contracts that have already expired and are
    not superseded by a later/current valid contract.

    Include only contracts where:
    - The contract itself is submitted.
    - The contract is fixed-term: has_expiry = 1.
    - The contract is not project-based: has_project = 0.
    - The contract end_date is before today.
    - The linked Employee is not marked as Left. Suspended employees are still
      included because they remain employed.
    - There is no later contract for the same employee that is currently valid,
      indefinite/no-expiry, or project-based.
    """
    report_date = getdate(today())

    lapsed_contracts = frappe.get_all(
        CONTRACT_DOCTYPE,
        filters={
            "docstatus": 1,
            "end_date": ["<", report_date],
            "has_expiry": 1,
            "has_project": 0,
        },
        fields=[
            "name",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "branch",
        ],
        order_by="end_date asc, employee_name asc",
    )

    if not lapsed_contracts:
        frappe.logger().info("No lapsed fixed-term contracts found.")
        return

    employee_ids = list({contract.employee for contract in lapsed_contracts if contract.employee})

    employed_employee_ids = set(
        frappe.get_all(
            EMPLOYEE_DOCTYPE,
            filters={
                "name": ["in", employee_ids],
                "status": ["!=", "Left"],
            },
            pluck="name",
        )
    )

    filtered_contracts = []

    for contract in lapsed_contracts:
        if contract.employee not in employed_employee_ids:
            continue

        if _has_later_blocking_contract(
            employee=contract.employee,
            current_contract_name=contract.name,
            current_start_date=contract.start_date,
            report_date=report_date,
        ):
            continue

        filtered_contracts.append(contract)

    if not filtered_contracts:
        frappe.logger().info("No lapsed contracts found after applying employee and later-contract filters.")
        return

    recipient_emails, name_by_email = get_ir_notification_recipients()
    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    email_subject = "Weekly HR Report: Fixed-Term Contracts Already Expired"

    email_body = """
        <p>Dear {name},</p>
        <p>Please find below the list of fixed-term contracts that have already expired and do not appear to have been superseded by a later valid, indefinite, or project-based contract:</p>
        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Contract Name</th>
                    <th>Employee Name</th>
                    <th>Employee Coy</th>
                    <th>Contract Start Date</th>
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
                <td>{contract.employee_name or ""}</td>
                <td>{contract.employee or ""}</td>
                <td>{contract.start_date or ""}</td>
                <td>{contract.end_date or ""}</td>
                <td>{contract.branch or ""}</td>
            </tr>
        """

    email_body += """
            </tbody>
        </table>
        <p>Kind regards,<br>Industrial Relations</p>
    """

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = full_name.split(" ")[0] if full_name else "Valued IR Team"
        personalized_email_body = email_body.format(name=first_name)

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=personalized_email_body,
        )

    frappe.logger().info(
        f"Weekly HR report (lapsed contracts) sent to {len(recipient_emails)} recipients. "
        f"Contracts included: {len(filtered_contracts)}."
    )