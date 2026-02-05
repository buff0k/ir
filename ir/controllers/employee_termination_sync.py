# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, nowdate


MIN_VALID_DATE = getdate("2000-01-01")  # adjust if your org legitimately has earlier relieving dates


def run_daily():
    """
    Daily job (SAFE VERSION):
      - Only act on Employees where relieving_date is set AND is a sane date
      - relieving_date strictly < today AND status == Active => set to Left (after clearing reports_to chains)
      - Disable linked users for:
          a) those just set to Left
          b) any Employees already Left who still have enabled user accounts
    """
    today = getdate(nowdate())

    # Pull Active employees with a relieving_date that is set (avoids NULL/empty)
    candidates = frappe.get_all(
        "Employee",
        fields=["name", "relieving_date", "status", "user_id"],
        filters={
            "status": "Active",
            "relieving_date": ["is", "set"],
        },
        limit_page_length=0,
    )

    overdue = []
    for emp in candidates:
        rd = _safe_get_date(emp.get("relieving_date"))
        if not rd:
            continue
        if rd < MIN_VALID_DATE:
            # Guard against placeholder ancient/zero dates
            continue
        if rd < today:
            overdue.append((emp["name"], emp.get("user_id")))

    for emp_name, user_id in overdue:
        _clear_reports_to_chain_for_terminated_employee(emp_name)
        frappe.db.set_value("Employee", emp_name, "status", "Left", update_modified=False)

        if user_id:
            _disable_user(user_id)

    # Extra precaution: Left employees with enabled users
    left_with_users = frappe.get_all(
        "Employee",
        fields=["name", "user_id"],
        filters={"status": "Left", "user_id": ["!=", ""]},
        limit_page_length=0,
    )

    for emp in left_with_users:
        if emp.get("user_id"):
            _disable_user(emp["user_id"])

    frappe.db.commit()


def _safe_get_date(value):
    """Return a real date or None. Filters out MariaDB 'zero date' cases."""
    if not value:
        return None

    # Handle MariaDB zero-date strings if they exist in your DB
    if isinstance(value, str) and value.strip() in ("0000-00-00", "0000-00-00 00:00:00"):
        return None

    try:
        d = getdate(value)
        # Some edge cases still parse to None
        return d
    except Exception:
        return None


def _disable_user(user_id: str):
    if not user_id:
        return

    try:
        enabled = frappe.db.get_value("User", user_id, "enabled")
        if enabled:
            frappe.db.set_value("User", user_id, "enabled", 0, update_modified=False)
    except Exception:
        frappe.log_error(
            title="IR Termination Sync: Failed disabling user",
            message=f"Could not disable user {user_id}",
        )


def _clear_reports_to_chain_for_terminated_employee(terminated_employee: str):
    """
    Clears reports_to for any employees whose manager chain leads back to terminated_employee.
    (Cycle-safe)
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
