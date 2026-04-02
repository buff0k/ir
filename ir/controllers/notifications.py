# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.meta import get_meta
from ir.industrial_relations.utils import get_ir_notification_recipients

IGNORE_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "idx",
    "docstatus", "parent", "parenttype", "parentfield", "amended_from", "version"
}

ANON_REPORT_SETTINGS_DOCTYPE = "Anonymous Report Recipients"

def handle_doc_event(doc, method, action, changed_fields=None):
    if doc.doctype == "Termination Form":
        return handle_notification(
            doc, action,
            subject_template="Termination form for {requested_for_names} ({requested_for}) {action}",
            body_template="A Termination Form for {requested_for_names} ({requested_for}) at {requested_for_site} has been {action} by {actor}.",
            changed_fields=changed_fields
        )
    elif doc.doctype == "NTA Hearing":
        return handle_notification(
            doc, action,
            subject_template="A Notice to Attend for {names} ({coy}) {action}",
            body_template="A Notice to Attend for {names} ({coy}) at {venue} has been {action} by {actor}.",
            changed_fields=changed_fields
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
    # Special handling for Anonymous Report
    if doc.doctype == "Anonymous Report":
        return handle_anonymous_report_create(doc, method)

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
        settings = frappe.get_single(ANON_REPORT_SETTINGS_DOCTYPE)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            f"Unable to load {ANON_REPORT_SETTINGS_DOCTYPE}"
        )
        return [], {}

    for row in settings.userlist or []:
        if not row.user:
            continue

        user_doc = frappe.db.get_value(
            "User",
            row.user,
            ["email", "full_name", "enabled"],
            as_dict=True
        )

        if not user_doc:
            continue

        if not user_doc.enabled:
            continue

        if not user_doc.email:
            continue

        if user_doc.email not in recipients:
            recipients.append(user_doc.email)
            name_by_email[user_doc.email] = user_doc.full_name or row.user

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