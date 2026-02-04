# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, nowdate


def run_daily():
    """
    Daily job:
      - Find Employees with relieving_date in the past AND status == Active:
          - clear manager chains pointing to them (reports_to), then set to Left
          - disable linked user (user_id) if present
      - Extra precaution:
          - Find Employees already Left but with user_id still enabled -> disable those users too
    """
    today = getdate(nowdate())

    # 1) Active employees whose relieving_date is in the past
    overdue = frappe.get_all(
        "Employee",
        fields=["name", "relieving_date", "status", "user_id"],
        filters={
            "status": "Active",
            "relieving_date": ["<", today],
        },
        limit_page_length=0,
    )

    for emp in overdue:
        emp_name = emp["name"]

        _clear_reports_to_chain_for_terminated_employee(emp_name)

        # set employee to Left
        frappe.db.set_value("Employee", emp_name, "status", "Left", update_modified=False)

        # disable linked user if any
        if emp.get("user_id"):
            _disable_user(emp["user_id"])

    # 2) Extra precaution: Left employees with enabled users
    left_with_users = frappe.get_all(
        "Employee",
        fields=["name", "user_id"],
        filters={
            "status": "Left",
            "user_id": ["!=", ""],
        },
        limit_page_length=0,
    )

    for emp in left_with_users:
        if emp.get("user_id"):
            _disable_user(emp["user_id"])

    frappe.db.commit()


def _disable_user(user_id: str):
    if not user_id:
        return

    # In Frappe/ERPNext, User.enabled is the standard checkbox field
    try:
        enabled = frappe.db.get_value("User", user_id, "enabled")
        if enabled:
            frappe.db.set_value("User", user_id, "enabled", 0, update_modified=False)
    except Exception:
        # If the user record doesn't exist or permissions are odd, skip hard failure
        frappe.log_error(
            title="IR Termination Sync: Failed disabling user",
            message=f"Could not disable user {user_id}",
        )


def _clear_reports_to_chain_for_terminated_employee(terminated_employee: str):
    """
    Same precaution as TerminationForm step (3):
    If any employee's reports_to chain leads to terminated_employee, clear their reports_to.
    """
    if not terminated_employee:
        return

    rows = frappe.get_all(
        "Employee",
        fields=["name", "reports_to"],
        filters={"reports_to": ["!=", ""]},
        limit_page_length=0,
    )
    reports_to_map = {r["name"]: r.get("reports_to") for r in rows}

    to_clear = []

    for emp_name in reports_to_map.keys():
        if emp_name == terminated_employee:
            continue

        visited = set()
        current = emp_name

        while True:
            if current in visited:
                break
            visited.add(current)

            manager = reports_to_map.get(current)
            if not manager:
                break

            if manager == terminated_employee:
                to_clear.append(emp_name)
                break

            current = manager

    for emp_name in set(to_clear):
        frappe.db.set_value("Employee", emp_name, "reports_to", None, update_modified=False)
