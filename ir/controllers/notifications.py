# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.meta import get_meta
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
    recipient_emails, name_by_email = _collect_disciplinary_action_recipients()
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


def _collect_disciplinary_action_recipients():
    recipients = []
    name_by_email = {}

    try:
        rows = frappe.get_all(
            "IR User Restriction Table",
            filters={
                "parent": "IR Role Restrictions",
                "parenttype": "IR Role Restrictions",
                "parentfield": "disciplinary_recipients",
            },
            fields=["user", "email_address"],
            order_by="idx asc",
        )
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "Unable to fetch Disciplinary Action recipients from IR Role Restrictions"
        )
        return [], {}

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

    for row in rows:
        user_doc = user_map.get(row.get("user"))

        # Skip disabled / missing users where a User was selected
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