# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.meta import get_meta
from ir import permissions
from ir.industrial_relations.utils import get_ir_notification_recipients
from collections import defaultdict
from datetime import date
from html import escape as html_escape
from frappe.utils import add_days, formatdate, getdate, today


IGNORE_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "idx",
    "docstatus", "parent", "parenttype", "parentfield", "amended_from", "version"
}

ANON_REPORT_INVESTIGATOR_ROLE = "Anonymous Report Investigator"


def handle_doc_event(doc, method, action, changed_fields=None):
    if doc.doctype == "Termination Form":
        return handle_notification(
            doc, action,
            subject_template="Termination form for {requested_for_names} ({requested_for}) {action}",
            body_template="A Termination Form for {requested_for_names} ({requested_for}) at {requested_for_site} has been {action} by {actor}.",
            changed_fields=changed_fields
        )
    elif doc.doctype == "NTA Enquiry":
        return handle_notification(
            doc, action,
            subject_template="A Notice to Attend for {names} ({employee}) {action}",
            body_template="A Notice to Attend for {names} ({employee}) at {venue} has been {action} by {actor}.",
            changed_fields=changed_fields,
        )
    elif doc.doctype == "Status Change Form":
        return handle_notification(
            doc, action,
            subject_template="A Status Change for {employee_name} ({employee}) {action}",
            body_template="A Status Change for {employee_name} ({employee}) has been {action} by {actor}.",
            changed_fields=changed_fields
        )
    elif doc.doctype == "Site Transfer Form":
        return handle_notification(
            doc, action,
            subject_template="A Site Transfer for {employee_name} ({employee}) {action}",
            body_template="A Site Transfer for {employee_name} ({employee}) has been {action} by {actor}.",
            changed_fields=changed_fields
        )


def handle_doc_event_create(doc, method):
    if doc.doctype == "Anonymous Report":
        return handle_anonymous_report_create(doc, method)

    if doc.doctype == "Disciplinary Action":
        return handle_disciplinary_action_create(doc, method)

    if doc.doctype == "Incapacity Proceedings":
        return handle_incapacity_proceedings_create(doc, method)

    if doc.doctype == "Poor Performance":
        return handle_poor_performance_create(doc, method)

    if doc.doctype == "External Dispute Resolution":
        return handle_external_dispute_resolution_create(doc, method)

    return handle_doc_event(doc, method, "created")


def handle_doc_event_update(doc, method):
    # Stop modification notifications for Termination Form only
    if doc.doctype == "Termination Form":
        return

    # Do not send update notifications for Anonymous Report
    if doc.doctype == "Anonymous Report":
        return

    before = doc.get_doc_before_save()
    if not before:
        return

    changed_fields = _diff_changed_fields(doc, before)
    if changed_fields:
        return handle_doc_event(doc, method, "updated", changed_fields)


def handle_doc_event_submit(doc, method):
    # No submit notification for Anonymous Report unless you explicitly want one
    if doc.doctype == "Anonymous Report":
        return

    return handle_doc_event(doc, method, "submitted")


# ---------- Anonymous Report ----------

def handle_anonymous_report_create(doc, method=None):
    recipient_emails, name_by_email = _collect_anonymous_report_recipients()
    if not recipient_emails:
        return

    subject = "New Anonymous Report Submitted"
    url = frappe.utils.get_url(doc.get_url())

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Colleague"

        lines = [
            f"Dear {full_name}",
            "",
            "A new Anonymous Report has been submitted.",
            f"Reference: {doc.name}",
        ]

        # Optional: include category if the field exists
        if hasattr(doc, "report_category") and doc.report_category:
            lines.append(f"Category: {doc.report_category}")

        # Optional: include submission timestamp
        if getattr(doc, "creation", None):
            lines.append(f"Submitted On: {doc.creation}")

        lines.extend([
            "",
            "Please review it in the system.",
            f'<a href="{url}">Click here to view</a>'
        ])

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


def _collect_anonymous_report_recipients():
    recipients = []
    name_by_email = {}

    try:
        user_names = frappe.get_all(
            "Has Role",
            filters={
                "role": ANON_REPORT_INVESTIGATOR_ROLE,
                "parenttype": "User",
            },
            pluck="parent"
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Unable to fetch users for role {ANON_REPORT_INVESTIGATOR_ROLE}"
        )
        return [], {}

    if not user_names:
        return [], {}

    user_docs = frappe.get_all(
        "User",
        filters={
            "name": ["in", user_names],
            "enabled": 1,
        },
        fields=["name", "email", "full_name"]
    )

    for user_doc in user_docs:
        email = user_doc.get("email")
        if not email:
            continue

        if email not in recipients:
            recipients.append(email)
            name_by_email[email] = user_doc.get("full_name") or user_doc.get("name")

    return recipients, name_by_email


# ---------- Existing helpers ----------

def handle_notification(doc, action, subject_template, body_template, changed_fields=None):
    recipient_emails, name_by_email = _collect_recipients(doc)
    if not recipient_emails:
        return

    subject = subject_template.format(**doc.as_dict(), action=action)
    url = frappe.utils.get_url(doc.get_url())

    # Get current user
    actor = frappe.session.user
    actor_fullname = frappe.db.get_value("User", actor, "full_name") or actor

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "IR Team"
        lines = [
            f"Dear {full_name}",
            "",
            body_template.format(**doc.as_dict(), action=action, actor=actor_fullname),
            ""
        ]

        if action == "updated" and changed_fields:
            meta = frappe.get_meta(doc.doctype)
            lines.append("Fields changed:")
            for fieldname, (old, new) in changed_fields.items():
                label = meta.get_label(fieldname) or fieldname
                if isinstance(new, list):  # this is a child table diff
                    lines.append(f"• {label}:")
                    for line in new:
                        lines.append(f"&nbsp;&nbsp;– {line}")
                else:
                    lines.append(f"• {label}: {old} → {new}")
            lines.append("")

        lines.append(f'<a href="{url}">Click here to view</a>')

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
        )


def _collect_recipients(doc):
    return get_ir_notification_recipients(include_owner=doc.owner if doc.owner else None)


def _diff_changed_fields(curr_doc, prev_doc):
    changed = {}
    curr = curr_doc.as_dict()
    prev = prev_doc.as_dict()
    meta = frappe.get_meta(curr_doc.doctype)

    for field in meta.fields:
        fieldname = field.fieldname
        fieldtype = field.fieldtype

        if fieldname in IGNORE_FIELDS:
            continue

        curr_value = curr.get(fieldname)
        prev_value = prev.get(fieldname)

        if fieldtype == "Table":
            diffs = _diff_child_table_rows(curr_value, prev_value)
            if diffs:
                changed[fieldname] = (None, diffs)
        else:
            if isinstance(curr_value, (int, float)) and isinstance(prev_value, (int, float)):
                if abs(curr_value - prev_value) > 1e-6:
                    changed[fieldname] = (prev_value, curr_value)
            elif str(curr_value) != str(prev_value):
                changed[fieldname] = (prev_value, curr_value)

    return changed


def _diff_child_table_rows(curr_rows, prev_rows):
    changes = []

    if not curr_rows and not prev_rows:
        return []

    curr_map = {row.get("name"): row for row in curr_rows or []}
    prev_map = {row.get("name"): row for row in prev_rows or []}

    for name, curr_row in curr_map.items():
        if name in prev_map:
            prev_row = prev_map[name]
            diffs = []
            for key in curr_row:
                if key in IGNORE_FIELDS or key in ("parent", "parenttype", "parentfield"):
                    continue
                if str(curr_row.get(key)) != str(prev_row.get(key)):
                    diffs.append(f"{key}: {prev_row.get(key)} → {curr_row.get(key)}")
            if diffs:
                changes.append(f"Row {curr_row.get('idx')}: " + ", ".join(diffs))
        else:
            changes.append(f"Row {curr_row.get('idx')}: added")

    for name in prev_map:
        if name not in curr_map:
            prev_idx = prev_map[name].get("idx", "?")
            changes.append(f"Row {prev_idx}: removed")

    return changes


def handle_disciplinary_action_create(doc, method=None):
    recipient_emails, name_by_email = _collect_recipients_from_table("disciplinary_recipients", doc)
    if not recipient_emails:
        return

    accused_name = doc.get("accused_name") or doc.get("employee_name") or doc.get("accused") or "Unknown Employee"
    accused_coy = doc.get("accused_coy") or doc.get("accused") or "Unknown Coy No."
    branch = doc.get("branch") or "Unknown Branch"

    is_shop_steward = bool(doc.get("is_ss"))
    ss_union = doc.get("ss_union") or ""

    if is_shop_steward:
        if ss_union:
            shop_steward_line = f"The employee is a Shop Steward for {ss_union}."
        else:
            shop_steward_line = "The employee is a Shop Steward."
    else:
        shop_steward_line = "The employee is not a Shop Steward."

    subject = f"New Disciplinary Action Created: {accused_name} ({accused_coy})"
    url = frappe.utils.get_url(doc.get_url())

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "IR Team"

        lines = [
            f"Dear {full_name}",
            "",
            f"A new Disciplinary Action has been created for {accused_name} ({accused_coy}) at {branch}.",
            "",
            shop_steward_line,
            "",
            "Please attend to this matter urgently.",
            "",
            f'<a href="{url}">Click here to view</a>',
        ]

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


def _fetch_ir_user_restriction_rows(parentfield):
    """Raw rows from IR User Restriction Table for a given parentfield on the
    IR Role Restrictions singleton."""
    try:
        return frappe.get_all(
            "IR User Restriction Table",
            filters={
                "parent": "IR Role Restrictions",
                "parenttype": "IR Role Restrictions",
                "parentfield": parentfield,
            },
            fields=["user", "email_address"],
            order_by="idx asc",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Unable to fetch recipients from IR Role Restrictions.{parentfield}"
        )
        return []


def _collect_recipients_from_table(parentfield, doc=None):
    """Resolve a recipient table (disciplinary_recipients, incapacity_recipients,
    performance_recipients, external_dispute_recipients, ...) into (emails,
    name_by_email).

    When `doc` is given, each row whose `user` is set is checked against
    permissions.recipient_passes_restrictions(doc, user) - i.e. narrowed to their
    hr_per_branch branch(es) if they have any, and skipped if the record's
    designation is restricted for them. Rows with no linked `user` (just a raw
    email address) are never filtered - there's no identity to check restrictions
    against. Pass doc=None (e.g. for External Dispute Resolution) to send
    branch/designation-agnostically to everyone in the table.
    """
    rows = _fetch_ir_user_restriction_rows(parentfield)
    if not rows:
        return [], {}

    user_names = [row.user for row in rows if row.get("user")]

    user_map = {}
    if user_names:
        users = frappe.get_all(
            "User",
            filters={
                "name": ["in", user_names],
                "enabled": 1,
            },
            fields=["name", "email", "full_name"],
        )
        user_map = {user.name: user for user in users}

    recipients = []
    name_by_email = {}

    for row in rows:
        row_user = row.get("user")
        user_doc = user_map.get(row_user)

        # Skip disabled / missing users where a User was selected
        if row_user and not user_doc:
            continue

        if doc is not None and row_user and not permissions.recipient_passes_restrictions(doc, row_user):
            continue

        email = row.get("email_address") or (user_doc.email if user_doc else None)
        if not email:
            continue

        if email not in recipients:
            recipients.append(email)
            name_by_email[email] = (
                user_doc.full_name
                if user_doc and user_doc.get("full_name")
                else row_user
            )

    return recipients, name_by_email


def handle_incapacity_proceedings_create(doc, method=None):
    recipient_emails, name_by_email = _collect_recipients_from_table("incapacity_recipients", doc)
    if not recipient_emails:
        return

    accused_name = doc.get("accused_name") or doc.get("accused") or "Unknown Employee"
    accused_coy = doc.get("accused_coy") or doc.get("accused") or "Unknown Coy No."
    branch = doc.get("branch") or "Unknown Branch"

    subject = f"New Incapacity Proceedings Created: {accused_name} ({accused_coy})"
    url = frappe.utils.get_url(doc.get_url())

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "IR Team"

        lines = [
            f"Dear {full_name}",
            "",
            f"A new Incapacity Proceedings has been created for {accused_name} ({accused_coy}) at {branch}.",
            "",
            "Please attend to this matter urgently.",
            "",
            f'<a href="{url}">Click here to view</a>',
        ]

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


def handle_poor_performance_create(doc, method=None):
    recipient_emails, name_by_email = _collect_recipients_from_table("performance_recipients", doc)
    if not recipient_emails:
        return

    employee_name = doc.get("employee_name") or doc.get("employee") or "Unknown Employee"
    branch = doc.get("branch") or "Unknown Branch"

    subject = f"New Poor Performance Record Created: {employee_name}"
    url = frappe.utils.get_url(doc.get_url())

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "IR Team"

        lines = [
            f"Dear {full_name}",
            "",
            f"A new Poor Performance record has been created for {employee_name} at {branch}.",
            "",
            "Please attend to this matter urgently.",
            "",
            f'<a href="{url}">Click here to view</a>',
        ]

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


def handle_external_dispute_resolution_create(doc, method=None):
    # No Branch or Designation Limits apply to External Dispute Resolution - the full
    # external_dispute_recipients table is notified unconditionally (doc=None below).
    recipient_emails, name_by_email = _collect_recipients_from_table("external_dispute_recipients")
    if not recipient_emails:
        return

    case_no = doc.get("case_no") or doc.name
    forum = doc.get("forum") or "Unknown Forum"

    subject = f"New External Dispute Resolution Created: {case_no}"
    url = frappe.utils.get_url(doc.get_url())

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "IR Team"

        lines = [
            f"Dear {full_name}",
            "",
            f"A new External Dispute Resolution matter has been created ({forum}), case number {case_no}.",
            "",
            "Please attend to this matter urgently.",
            "",
            f'<a href="{url}">Click here to view</a>',
        ]

        message = "<br>".join(lines)

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
            reference_doctype=doc.doctype,
            reference_name=doc.name,
        )


from collections import defaultdict
from datetime import date
from html import escape as html_escape

from frappe.utils import add_days, formatdate, getdate, today


def send_weekly_induction_expiring_soon_notifications():
    """
    Weekly email:
    Employee Induction Records where the latest submitted record
    for that Employee + Training expires within the next 30 days.

    Branch trainers receive only their branch.
    Global trainers receive all branches.
    """
    start_date = today()
    end_date = add_days(start_date, 30)

    rows = _get_latest_induction_expiry_rows(
        date_from=start_date,
        date_to=end_date,
        expired=False,
    )

    _send_training_expiry_notifications(
        rows=rows,
        notification_type="expiring",
        subject_prefix="Employee Induction Records Expiring in the Next 30 Days",
        intro=(
            "The following active employees have Employee Induction Records "
            "expiring in the next 30 days."
        ),
    )


def send_weekly_induction_expired_notifications():
    """
    Weekly email:
    Employee Induction Records where the latest submitted record
    for that Employee + Training has already expired.

    A training is not treated as expired if a later submitted record exists
    for the same Employee + Training with a later Valid To date.
    """
    rows = _get_latest_induction_expiry_rows(
        date_from=None,
        date_to=today(),
        expired=True,
    )

    _send_training_expiry_notifications(
        rows=rows,
        notification_type="expired",
        subject_prefix="Expired Employee Induction Records",
        intro=(
            "The following active employees have Employee Induction Records "
            "that have already expired."
        ),
    )


def _get_latest_induction_expiry_rows(date_from=None, date_to=None, expired=False):
    """
    Returns only the latest submitted Employee Induction Record per:
        Employee + Training

    This is the key renewal logic.

    If an older record expired, but a newer submitted record exists for the
    same employee and training, only the newer record is considered.
    """
    conditions = []

    if expired:
        conditions.append("latest.latest_valid_to < %(date_to)s")
    else:
        conditions.append("latest.latest_valid_to >= %(date_from)s")
        conditions.append("latest.latest_valid_to <= %(date_to)s")

    date_condition = " AND ".join(conditions)

    query = f"""
        SELECT
            latest.employee,
            COALESCE(MAX(record.employee_name), MAX(employee.employee_name), latest.employee) AS employee_name,
            COALESCE(MAX(record.branch), MAX(employee.branch)) AS branch,
            latest.training,
            latest.latest_valid_to AS valid_to,
            MIN(record.name) AS record_name
        FROM (
            SELECT
                induction.employee,
                induction.training,
                MAX(induction.valid_to) AS latest_valid_to
            FROM `tabEmployee Induction Record` induction
            INNER JOIN `tabEmployee` employee
                ON employee.name = induction.employee
            WHERE
                induction.docstatus = 1
                AND induction.employee IS NOT NULL
                AND induction.training IS NOT NULL
                AND induction.valid_to IS NOT NULL
                AND employee.status = 'Active'
            GROUP BY
                induction.employee,
                induction.training
        ) latest
        INNER JOIN `tabEmployee Induction Record` record
            ON record.employee = latest.employee
            AND record.training = latest.training
            AND record.valid_to = latest.latest_valid_to
            AND record.docstatus = 1
        INNER JOIN `tabEmployee` employee
            ON employee.name = latest.employee
        WHERE
            employee.status = 'Active'
            AND {date_condition}
        GROUP BY
            latest.employee,
            latest.training,
            latest.latest_valid_to
        ORDER BY
            branch ASC,
            employee_name ASC,
            training ASC
    """

    return frappe.db.sql(
        query,
        {
            "date_from": date_from,
            "date_to": date_to,
        },
        as_dict=True,
    )


def _send_training_expiry_notifications(rows, notification_type, subject_prefix, intro):
    if not rows:
        return

    global_recipients, global_names = _collect_global_trainer_recipients()
    branch_recipients, branch_names = _collect_trainer_recipients_by_branch()

    # Global trainers receive the full list.
    if global_recipients:
        _send_training_expiry_email(
            recipients=global_recipients,
            name_by_email=global_names,
            rows=rows,
            subject=f"{subject_prefix} - All Branches",
            intro=intro,
            scope_label="All Branches",
            notification_type=notification_type,
        )

    # Branch trainers receive only their own branch list.
    rows_by_branch = defaultdict(list)
    for row in rows:
        branch = row.get("branch") or "No Branch"
        rows_by_branch[branch].append(row)

    for branch, branch_rows in rows_by_branch.items():
        recipients = branch_recipients.get(branch) or []
        if not recipients:
            continue

        _send_training_expiry_email(
            recipients=recipients,
            name_by_email=branch_names,
            rows=branch_rows,
            subject=f"{subject_prefix} - {branch}",
            intro=intro,
            scope_label=branch,
            notification_type=notification_type,
        )


def _send_training_expiry_email(
    recipients,
    name_by_email,
    rows,
    subject,
    intro,
    scope_label,
    notification_type,
):
    grouped_rows = _group_training_expiry_rows_by_employee(rows)

    table_rows = []

    for item in grouped_rows:
        employee = html_escape(item.get("employee") or "")
        employee_name = html_escape(item.get("employee_name") or "")
        branch = html_escape(item.get("branch") or "")
        trainings = "<br>".join(
            html_escape(training_line)
            for training_line in item.get("trainings", [])
        )

        table_rows.append(f"""
            <tr>
                <td>{employee_name}</td>
                <td>{employee}</td>
                <td>{branch}</td>
                <td>{trainings}</td>
            </tr>
        """)

    table_html = f"""
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
                    <th align="left">Employee Name</th>
                    <th align="left">Employee</th>
                    <th align="left">Branch</th>
                    <th align="left">Training / Induction</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    """

    for email in recipients:
        full_name = name_by_email.get(email) or "Training Team"

        message = "<br>".join([
            f"Dear {html_escape(full_name)}",
            "",
            html_escape(intro),
            "",
            f"Scope: {html_escape(scope_label)}",
            "",
            table_html,
            "",
            "Please attend to the relevant renewals urgently.",
        ])

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
        )


def _group_training_expiry_rows_by_employee(rows):
    grouped = {}

    for row in rows:
        employee = row.get("employee")
        branch = row.get("branch") or "No Branch"

        key = (employee, branch)

        if key not in grouped:
            grouped[key] = {
                "employee": employee,
                "employee_name": row.get("employee_name"),
                "branch": branch,
                "trainings": [],
            }

        valid_to = row.get("valid_to")
        valid_to_display = formatdate(valid_to) if valid_to else "No Valid To Date"

        grouped[key]["trainings"].append(
            f"{row.get('training')} - Valid To: {valid_to_display}"
        )

    return list(grouped.values())


def _collect_global_trainer_recipients():
    """
    Users in IR Role Restrictions > global_trainer.
    Child table: IR User Restriction Table.
    """
    try:
        rows = frappe.get_all(
            "IR User Restriction Table",
            filters={
                "parent": "IR Role Restrictions",
                "parenttype": "IR Role Restrictions",
                "parentfield": "global_trainer",
            },
            fields=["user", "email_address"],
            order_by="idx asc",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Unable to fetch Global Trainer recipients from IR Role Restrictions"
        )
        return [], {}

    return _resolve_user_recipients(rows)


def _collect_trainer_recipients_by_branch():
    """
    Users in IR Role Restrictions > trainer_per_branch.
    Child table: IR Role Restrictions User Branch.
    """
    try:
        rows = frappe.get_all(
            "IR Role Restrictions User Branch",
            filters={
                "parent": "IR Role Restrictions",
                "parenttype": "IR Role Restrictions",
                "parentfield": "trainer_per_branch",
            },
            fields=["branch", "user", "email_address"],
            order_by="idx asc",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Unable to fetch Branch Trainer recipients from IR Role Restrictions"
        )
        return {}, {}

    recipients_by_branch = defaultdict(list)
    name_by_email = {}

    user_rows = _get_enabled_user_map([row.get("user") for row in rows if row.get("user")])

    for row in rows:
        branch = row.get("branch")
        if not branch:
            continue

        user_doc = user_rows.get(row.get("user"))

        # If a User was selected but is disabled / missing, skip the row.
        if row.get("user") and not user_doc:
            continue

        email = row.get("email_address") or (user_doc.email if user_doc else None)
        if not email:
            continue

        if email not in recipients_by_branch[branch]:
            recipients_by_branch[branch].append(email)

        name_by_email[email] = (
            user_doc.full_name
            if user_doc and user_doc.get("full_name")
            else row.get("user")
        )

    return dict(recipients_by_branch), name_by_email


def _resolve_user_recipients(rows):
    recipients = []
    name_by_email = {}

    user_rows = _get_enabled_user_map([row.get("user") for row in rows if row.get("user")])

    for row in rows:
        user_doc = user_rows.get(row.get("user"))

        # If a User was selected but is disabled / missing, skip the row.
        if row.get("user") and not user_doc:
            continue

        email = row.get("email_address") or (user_doc.email if user_doc else None)
        if not email:
            continue

        if email not in recipients:
            recipients.append(email)

        name_by_email[email] = (
            user_doc.full_name
            if user_doc and user_doc.get("full_name")
            else row.get("user")
        )

    return recipients, name_by_email


def _get_enabled_user_map(user_names):
    if not user_names:
        return {}

    users = frappe.get_all(
        "User",
        filters={
            "name": ["in", list(set(user_names))],
            "enabled": 1,
        },
        fields=["name", "email", "full_name"],
    )

    return {user.name: user for user in users}


# ---------- Weekly Outstanding HR Workflow Notifications ----------


def send_weekly_outstanding_leave_application_notifications():
    """
    Weekly report of draft Leave Applications for active employees.

    Each draft Leave Application is reported independently. No supersession
    or latest-record logic is applied because multiple Leave Applications may
    legitimately follow one another in the workflow.
    """
    rows = _get_outstanding_leave_applications()

    _send_outstanding_workflow_email(
        rows=rows,
        subject="Weekly HR Report: Outstanding Leave Applications",
        intro=(
            "The following Leave Applications belong to active employees "
            "and have not yet been submitted."
        ),
        table_headers=[
            "Leave Application",
            "Employee Name",
            "Employee",
            "Branch",
            "Leave Type",
            "From Date",
            "To Date",
            "Leave Days",
            "Created",
        ],
        row_builder=_build_leave_application_row,
        empty_log_message="No outstanding Leave Applications found.",
        sent_log_label="outstanding Leave Application",
    )


def send_weekly_outstanding_employee_change_form_notifications():
    """
    Weekly combined report of draft Status Change Forms and Site Transfer
    Forms for active employees.

    Each draft document is reported independently. No supersession or
    latest-record logic is applied because these documents may legitimately
    be sequenced one after another.
    """
    rows = []

    rows.extend(_get_outstanding_status_change_forms())
    rows.extend(_get_outstanding_site_transfer_forms())

    rows.sort(
        key=lambda row: (
            str(row.get("branch") or ""),
            str(row.get("employee_name") or ""),
            str(row.get("creation") or ""),
            str(row.get("doctype") or ""),
        )
    )

    _send_outstanding_workflow_email(
        rows=rows,
        subject="Weekly HR Report: Outstanding Employee Change Forms",
        intro=(
            "The following Status Change Forms and Site Transfer Forms "
            "belong to active employees and have not yet been submitted."
        ),
        table_headers=[
            "Document Type",
            "Document",
            "Employee Name",
            "Employee",
            "Branch",
            "Effective Date",
            "Change",
            "Created",
        ],
        row_builder=_build_employee_change_form_row,
        empty_log_message="No outstanding employee change forms found.",
        sent_log_label="outstanding employee change form",
    )


def _get_outstanding_leave_applications():
    """
    Return draft Leave Applications linked to active employees.

    Employee is joined directly so that inactive employees are excluded even
    where the Leave Application itself still exists as a draft.
    """
    return frappe.db.sql(
        """
        SELECT
            leave_application.name,
            leave_application.employee,
            COALESCE(
                leave_application.employee_name,
                employee.employee_name,
                leave_application.employee
            ) AS employee_name,
            employee.branch,
            leave_application.leave_type,
            leave_application.from_date,
            leave_application.to_date,
            leave_application.total_leave_days,
            leave_application.posting_date,
            leave_application.creation
        FROM `tabLeave Application` leave_application
        INNER JOIN `tabEmployee` employee
            ON employee.name = leave_application.employee
        WHERE
            leave_application.docstatus = 0
            AND leave_application.employee IS NOT NULL
            AND employee.status = 'Active'
        ORDER BY
            employee.branch ASC,
            employee.employee_name ASC,
            leave_application.from_date ASC,
            leave_application.creation ASC
        """,
        as_dict=True,
    )


def _get_outstanding_status_change_forms():
    """
    Return draft Status Change Forms linked to active employees.
    """
    rows = frappe.db.sql(
        """
        SELECT
            'Status Change Form' AS doctype,
            status_change.name,
            status_change.employee,
            COALESCE(
                status_change.employee_name,
                employee.employee_name,
                status_change.employee
            ) AS employee_name,
            employee.branch,
            status_change.effective_date,
            status_change.current_designation,
            status_change.new_designation,
            NULL AS current_branch,
            NULL AS new_branch,
            status_change.creation
        FROM `tabStatus Change Form` status_change
        INNER JOIN `tabEmployee` employee
            ON employee.name = status_change.employee
        WHERE
            status_change.docstatus = 0
            AND status_change.employee IS NOT NULL
            AND employee.status = 'Active'
        ORDER BY
            employee.branch ASC,
            employee.employee_name ASC,
            status_change.effective_date ASC,
            status_change.creation ASC
        """,
        as_dict=True,
    )

    return rows


def _get_outstanding_site_transfer_forms():
    """
    Return draft Site Transfer Forms linked to active employees.
    """
    rows = frappe.db.sql(
        """
        SELECT
            'Site Transfer Form' AS doctype,
            site_transfer.name,
            site_transfer.employee,
            COALESCE(
                site_transfer.employee_name,
                employee.employee_name,
                site_transfer.employee
            ) AS employee_name,
            COALESCE(
                site_transfer.current_branch,
                employee.branch
            ) AS branch,
            site_transfer.transfer_date AS effective_date,
            NULL AS current_designation,
            NULL AS new_designation,
            site_transfer.current_branch,
            site_transfer.new_branch,
            site_transfer.creation
        FROM `tabSite Transfer Form` site_transfer
        INNER JOIN `tabEmployee` employee
            ON employee.name = site_transfer.employee
        WHERE
            site_transfer.docstatus = 0
            AND site_transfer.employee IS NOT NULL
            AND employee.status = 'Active'
        ORDER BY
            branch ASC,
            employee.employee_name ASC,
            site_transfer.transfer_date ASC,
            site_transfer.creation ASC
        """,
        as_dict=True,
    )

    return rows


def _send_outstanding_workflow_email(
    rows,
    subject,
    intro,
    table_headers,
    row_builder,
    empty_log_message,
    sent_log_label,
):
    """
    Send one personalised weekly report to each configured report recipient.

    Recipient configuration:
        IR Role Restrictions > Report Recipients

    This deliberately uses get_ir_notification_recipients(), matching the
    existing weekly IR and HR reports.
    """
    if not rows:
        frappe.logger().info(empty_log_message)
        return

    recipient_emails, name_by_email = get_ir_notification_recipients()

    if not recipient_emails:
        frappe.logger().info("No valid IR report recipients found.")
        return

    header_html = "".join(
        f'<th align="left">{html_escape(str(header))}</th>'
        for header in table_headers
    )

    row_html = "".join(row_builder(row) for row in rows)

    table_html = f"""
        <table
            border="1"
            cellspacing="0"
            cellpadding="6"
            style="border-collapse: collapse; width: 100%;"
        >
            <thead>
                <tr>
                    {header_html}
                </tr>
            </thead>
            <tbody>
                {row_html}
            </tbody>
        </table>
    """

    for email in recipient_emails:
        full_name = name_by_email.get(email) or "Valued IR Team"
        first_name = full_name.split(" ")[0] if full_name else "Valued IR Team"

        message = f"""
            <p>Dear {html_escape(first_name)},</p>

            <p>{html_escape(intro)}</p>

            {table_html}

            <p>Please review and attend to the outstanding documents.</p>

            <p>
                Kind regards,<br>
                Industrial Relations
            </p>
        """

        frappe.sendmail(
            recipients=[email],
            subject=subject,
            message=message,
        )

    frappe.logger().info(
        f"Weekly {sent_log_label} report sent to "
        f"{len(recipient_emails)} recipients."
    )


def _build_leave_application_row(row):
    document_name = row.get("name") or ""
    document_url = frappe.utils.get_url(
        f"/app/leave-application/{document_name}"
    )

    return f"""
        <tr>
            <td>
                <a href="{html_escape(document_url)}">
                    {html_escape(document_name)}
                </a>
            </td>
            <td>{html_escape(row.get("employee_name") or "")}</td>
            <td>{html_escape(row.get("employee") or "")}</td>
            <td>{html_escape(row.get("branch") or "")}</td>
            <td>{html_escape(row.get("leave_type") or "")}</td>
            <td>{_format_notification_date(row.get("from_date"))}</td>
            <td>{_format_notification_date(row.get("to_date"))}</td>
            <td>{html_escape(_format_leave_days(row.get("total_leave_days")))}</td>
            <td>{_format_notification_date(row.get("creation"))}</td>
        </tr>
    """


def _build_employee_change_form_row(row):
    doctype = row.get("doctype") or ""
    document_name = row.get("name") or ""

    route = frappe.scrub(doctype).replace("_", "-")
    document_url = frappe.utils.get_url(f"/app/{route}/{document_name}")

    if doctype == "Status Change Form":
        current_designation = row.get("current_designation") or "Not specified"
        new_designation = row.get("new_designation") or "Not specified"

        change_description = (
            f"Designation: {current_designation} → {new_designation}"
        )
    elif doctype == "Site Transfer Form":
        current_branch = row.get("current_branch") or "Not specified"
        new_branch = row.get("new_branch") or "Not specified"

        change_description = (
            f"Branch: {current_branch} → {new_branch}"
        )
    else:
        change_description = ""

    return f"""
        <tr>
            <td>{html_escape(doctype)}</td>
            <td>
                <a href="{html_escape(document_url)}">
                    {html_escape(document_name)}
                </a>
            </td>
            <td>{html_escape(row.get("employee_name") or "")}</td>
            <td>{html_escape(row.get("employee") or "")}</td>
            <td>{html_escape(row.get("branch") or "")}</td>
            <td>{_format_notification_date(row.get("effective_date"))}</td>
            <td>{html_escape(change_description)}</td>
            <td>{_format_notification_date(row.get("creation"))}</td>
        </tr>
    """


def _format_notification_date(value):
    if not value:
        return ""

    try:
        return html_escape(formatdate(getdate(value)))
    except Exception:
        return html_escape(str(value))


def _format_leave_days(value):
    if value in (None, ""):
        return ""

    try:
        numeric_value = float(value)

        if numeric_value.is_integer():
            return str(int(numeric_value))

        return str(numeric_value)
    except (TypeError, ValueError):
        return str(value)