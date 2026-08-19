# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import today

from ir import permissions
from ir.industrial_relations.doctype.demotion_form.demotion_form import restore_employee_position
from ir.industrial_relations.email_style import EMAIL_STYLE_BLOCK, email_header
from ir.industrial_relations.utils import get_ir_notification_recipients


def run_daily():
    rows = frappe.get_all(
        "Demotion Form",
        filters=[
            ["docstatus", "=", 1],
            ["demotion_applied", "=", 1],
            ["demotion_reversed", "=", 0],
            # Frappe's query builder treats a blank Date field as '0001-01-01'
            # for "<"/">" comparisons (IFNULL(field, '0001-01-01')), so
            # to_date IS NULL (an indefinite demotion, per the field's own
            # "If Temporary" label) would otherwise always match "< today()"
            # and get wrongly reversed. Exclude blank to_date explicitly.
            ["to_date", "is", "set"],
            ["to_date", "<", today()],
        ],
        fields=["name", "employee", "names", "position", "new_position", "to_date", "company"],
    )
    for row in rows:
        try:
            _restore(row)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Demotion reversal failed: {row.name}")


def _restore(demotion):
    # Boundary convention: the closed work-history row's to_date equals the new
    # row's from_date, using the demotion's own defined end date rather than
    # whichever day this background job happens to run.
    reversed_ = restore_employee_position(
        demotion,
        reversed_on=demotion.to_date,
        remarks=_("Temporary demotion reversed after expiry on {0}").format(demotion.to_date),
    )
    if reversed_:
        _notify_reversal(demotion)


def _notify_reversal(demotion):
    recipients = _get_recipients(demotion)
    if not recipients:
        return

    employee_name = demotion.names or frappe.db.get_value("Employee", demotion.employee, "employee_name") or demotion.employee
    subject = _("Demotion reversed: {0}").format(employee_name)
    message = EMAIL_STYLE_BLOCK + frappe.render_template(
        """
        <p class="ir-email-intro">The temporary demotion for <strong>{{ employee_name }}</strong>
        ({{ employee }}) has been reversed.</p>
        <table class="ir-email-table">
          <tbody>
            <tr><td><strong>Demotion Form</strong></td><td><a href="{{ demotion_url }}">{{ demotion_name }}</a></td></tr>
            <tr><td><strong>Demoted Position</strong></td><td>{{ new_position }}</td></tr>
            <tr><td><strong>Restored Position</strong></td><td>{{ position }}</td></tr>
            <tr><td><strong>Demotion End Date</strong></td><td>{{ to_date }}</td></tr>
          </tbody>
        </table>
        """,
        {
            "employee_name": employee_name,
            "employee": demotion.employee,
            "demotion_name": demotion.name,
            "demotion_url": frappe.utils.get_url(f"/app/demotion-form/{demotion.name}"),
            "new_position": demotion.new_position,
            "position": demotion.position,
            "to_date": demotion.to_date,
        },
    )
    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        header=email_header(subject, "info"),
        reference_doctype="Demotion Form",
        reference_name=demotion.name,
    )


def _get_recipients(demotion):
    """Resolve report_recipients (IR Role Restrictions), narrowed to whoever's own
    Designation Limits/Branch Limits actually permit seeing this Demotion Form -
    same recipient pool and same filtering primitive every other IR notification
    uses, replacing the old dead "Notification Permissions" singleton lookup
    (that doctype never existed, so this always silently fell back to mailing
    every enabled IR Manager/IR Officer/HR Manager, unfiltered).

    Demotion Form is already fully wired in DESIGNATION_FIELD_BY_DOCTYPE/
    BRANCH_LIMITED_DOCTYPES (governs opening the document itself) - this just
    brings the reversal email in line with that existing restriction.
    """
    recipient_emails, _name_by_email = get_ir_notification_recipients()
    return [
        email for email in recipient_emails
        if permissions.passes_limits(
            "Demotion Form", email,
            designation=demotion.get("position"),
            employee=demotion.get("employee"),
        )
    ]
