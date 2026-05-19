# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_url, formatdate

from ir.industrial_relations.utils import get_ir_notification_recipients


TERMINAL_OUTCOMES = {"Performance Improved", "Dismissal"}


def _outcome_is_terminal(outcome):
    if not outcome:
        return False

    # Primary check: Offence Outcome document name
    if outcome in TERMINAL_OUTCOMES:
        return True

    # Fallback check: display / description field on Offence Outcome
    try:
        display_value = (
            frappe.db.get_value("Offence Outcome", outcome, "disc_offence_out")
            or ""
        )
        return display_value in TERMINAL_OUTCOMES
    except Exception:
        return False


def _get_outcome_label(outcome):
    if not outcome:
        return ""

    try:
        return (
            frappe.db.get_value("Offence Outcome", outcome, "disc_offence_out")
            or outcome
        )
    except Exception:
        return outcome


def _has_later_terminal_poor_performance(employee, current_creation, current_name):
    if not employee or not current_creation:
        return False

    later_records = frappe.get_all(
        "Poor Performance",
        filters={
            "employee": employee,
            "creation": [">", current_creation],
            "name": ["!=", current_name],
        },
        fields=["name", "outcome", "creation"],
        order_by="creation asc",
    )

    for row in later_records:
        if _outcome_is_terminal(row.get("outcome")):
            return True

    return False


def _get_outstanding_poor_performance_cases():
    records = frappe.get_all(
        "Poor Performance",
        fields=[
            "name",
            "docstatus",
            "employee",
            "employee_name",
            "employee_designation",
            "branch",
            "creation",
            "request_date",
            "outcome",
            "outcome_date",
            "details_of_poor_performance",
        ],
        order_by="employee asc, creation asc",
    )

    outstanding = []

    for row in records:
        employee = row.get("employee")
        outcome = row.get("outcome")
        docstatus = row.get("docstatus")
        current_creation = row.get("creation")
        current_name = row.get("name")

        # Requirement 1:
        # All Poor Performance records that are not yet submitted.
        if docstatus != 1:
            row["status_reason"] = "Pending submission"
            row["outcome_label"] = _get_outcome_label(outcome)
            outstanding.append(row)
            continue

        # A terminal Poor Performance record is not outstanding itself.
        if _outcome_is_terminal(outcome):
            continue

        # Requirement 2:
        # Submitted Poor Performance records remain open unless there is a later
        # Poor Performance record for the same employee with terminal outcome:
        # Performance Improved or Dismissal.
        if not _has_later_terminal_poor_performance(employee, current_creation, current_name):
            row["status_reason"] = "Open - no later Performance Improved or Dismissal outcome"
            row["outcome_label"] = _get_outcome_label(outcome)
            outstanding.append(row)

    return outstanding


def outstanding_poor_performance():
    outstanding_cases = _get_outstanding_poor_performance_cases()

    if not outstanding_cases:
        frappe.logger().info("No outstanding poor performance processes found.")
        return

    recipient_emails, name_by_email = get_ir_notification_recipients()

    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    email_subject = "Weekly HR Report: Outstanding Poor Performance Processes"

    table_rows = ""

    for case in outstanding_cases:
        case_url = get_url(f"/app/poor-performance/{case.get('name')}")
        details = case.get("details_of_poor_performance") or ""
        if len(details) > 250:
            details = details[:247] + "..."

        table_rows += f"""
            <tr>
                <td><a href="{case_url}">{case.get("name") or ""}</a></td>
                <td>{case.get("employee_name") or ""}</td>
                <td>{case.get("employee") or ""}</td>
                <td>{case.get("employee_designation") or ""}</td>
                <td>{case.get("branch") or ""}</td>
                <td>{formatdate(case.get("creation")) if case.get("creation") else ""}</td>
                <td>{case.get("outcome_label") or ""}</td>
                <td>{case.get("status_reason") or ""}</td>
                <td>{frappe.utils.escape_html(details)}</td>
            </tr>
        """

    email_body_template = """
        <p>Dear {name},</p>

        <p>The following poor performance processes require attention:</p>

        <table border="1" cellspacing="0" cellpadding="5" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th>Poor Performance</th>
                    <th>Employee Name</th>
                    <th>Employee Coy</th>
                    <th>Position</th>
                    <th>Site</th>
                    <th>Created</th>
                    <th>Current Outcome</th>
                    <th>Status Reason</th>
                    <th>Details</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>

        <p>Kind regards,<br>Industrial Relations</p>
    """

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = full_name.split(" ")[0] if full_name else "Valued IR Team"

        personalized_email_body = email_body_template.format(
            name=first_name,
            table_rows=table_rows,
        )

        frappe.sendmail(
            recipients=[email],
            subject=email_subject,
            message=personalized_email_body,
        )

    frappe.logger().info(
        f"Weekly outstanding poor performance report sent to {len(recipient_emails)} recipients."
    )