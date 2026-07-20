# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today

from ir.industrial_relations.doctype.demotion_form.demotion_form import _append_employee_audit

SETTINGS_DOCTYPE = "Notification Permissions"
DEFAULT_ROLES = ("IR Manager", "IR Officer", "HR Manager")


def run_daily():
    rows = frappe.get_all(
        "Demotion Form",
        filters={
            "docstatus": 1,
            "demotion_applied": 1,
            "demotion_reversed": 0,
            "to_date": ["<", today()],
        },
        fields=["name", "employee", "names", "position", "new_position", "to_date", "company"],
    )
    for row in rows:
        try:
            _restore(row)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Demotion reversal failed: {row.name}")


def _restore(demotion):
    if not demotion.employee or not demotion.position:
        _log_review(demotion, "Employee or original position is missing.")
        return

    employee = frappe.get_doc("Employee", demotion.employee)
    if employee.designation != demotion.new_position:
        _log_review(
            demotion,
            f"Employee is currently {employee.designation}, not the demoted position {demotion.new_position}.",
        )
        return

    old_designation = employee.designation
    employee.designation = demotion.position
    employee.status = "Active"
    _append_employee_audit(
        employee,
        fieldname="designation",
        old_value=old_designation,
        new_value=demotion.position,
        reference_doctype="Demotion Form",
        reference_name=demotion.name,
        remarks=_("Temporary demotion reversed after expiry on {0}").format(demotion.to_date),
    )
    employee.save(ignore_permissions=True)

    frappe.db.set_value(
        "Demotion Form",
        demotion.name,
        {"demotion_reversed": 1, "demotion_reversed_on": today()},
        update_modified=False,
    )
    _notify_reversal(demotion)


def _log_review(demotion, reason):
    frappe.log_error(
        title=f"Demotion reversal requires review: {demotion.name}",
        message=reason,
    )


def _notify_reversal(demotion):
    recipients = _get_recipients()
    if not recipients:
        return

    employee_name = demotion.names or frappe.db.get_value("Employee", demotion.employee, "employee_name") or demotion.employee
    subject = _("Demotion reversed: {0}").format(employee_name)
    message = frappe.render_template(
        """
        <p>The temporary demotion for <strong>{{ employee_name }}</strong>
        ({{ employee }}) has been reversed.</p>
        <table>
          <tr><td><strong>Demotion Form</strong></td><td>{{ demotion_name }}</td></tr>
          <tr><td><strong>Demoted Position</strong></td><td>{{ new_position }}</td></tr>
          <tr><td><strong>Restored Position</strong></td><td>{{ position }}</td></tr>
          <tr><td><strong>Demotion End Date</strong></td><td>{{ to_date }}</td></tr>
        </table>
        """,
        {
            "employee_name": employee_name,
            "employee": demotion.employee,
            "demotion_name": demotion.name,
            "new_position": demotion.new_position,
            "position": demotion.position,
            "to_date": demotion.to_date,
        },
    )
    frappe.sendmail(recipients=recipients, subject=subject, message=message, reference_doctype="Demotion Form", reference_name=demotion.name)


def _get_recipients():
    """Resolve enabled users whose roles are allowed by Notification Permissions.

    Expected singleton configuration:
      - optional Check: notify_demotion_reversal
      - optional child table: demotion_reversal_roles, with a Link field named role

    For compatibility with older deployments, any table field containing both
    'demotion' and 'role' is accepted. When the singleton or configured rows do
    not exist, the conservative fallback roles are IR Manager, IR Officer and
    HR Manager.
    """
    roles = set()
    enabled = True
    if frappe.db.exists("DocType", SETTINGS_DOCTYPE):
        settings = frappe.get_single(SETTINGS_DOCTYPE)
        if settings.meta.has_field("notify_demotion_reversal"):
            enabled = bool(settings.get("notify_demotion_reversal"))
        if not enabled:
            return []

        table_fields = [
            df for df in settings.meta.fields
            if df.fieldtype == "Table" and "demotion" in df.fieldname and "role" in df.fieldname
        ]
        if settings.meta.has_field("demotion_reversal_roles"):
            table_fields = [settings.meta.get_field("demotion_reversal_roles")] + table_fields
        seen = set()
        for df in table_fields:
            if not df or df.fieldname in seen:
                continue
            seen.add(df.fieldname)
            for row in settings.get(df.fieldname) or []:
                role = row.get("role") or row.get("allowed_role") or row.get("notification_role")
                if role:
                    roles.add(role)

    if not roles:
        roles.update(DEFAULT_ROLES)

    users = frappe.get_all(
        "Has Role",
        filters={"role": ["in", sorted(roles)], "parenttype": "User"},
        pluck="parent",
    )
    recipients = set()
    for user in users:
        enabled, email = frappe.db.get_value("User", user, ["enabled", "email"]) or (0, None)
        if enabled and email:
            recipients.add(email)
    return sorted(recipients)
