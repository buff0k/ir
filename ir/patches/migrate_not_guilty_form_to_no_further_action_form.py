from __future__ import annotations

import frappe

NEW_DOCTYPE = "No Further Action Form"
LEGACY_DOCTYPES = ("Not Guilty Form", "Performance Improved")

SYSTEM_REFERENCES = (
    ("File", "attached_to_doctype", "attached_to_name"),
    ("Communication", "reference_doctype", "reference_name"),
    ("Comment", "reference_doctype", "reference_name"),
    ("Version", "ref_doctype", "docname"),
    ("ToDo", "reference_type", "reference_name"),
    ("DocShare", "share_doctype", "share_name"),
    ("Activity Log", "reference_doctype", "reference_name"),
    ("Email Queue", "reference_doctype", "reference_name"),
)


def execute():
    if not frappe.db.exists("DocType", NEW_DOCTYPE):
        frappe.throw(f"{NEW_DOCTYPE} must exist before this patch runs.")

    previous_mute = getattr(frappe.flags, "mute_emails", False)
    previous_patch = getattr(frappe.flags, "in_patch", False)
    frappe.flags.mute_emails = True
    frappe.flags.in_patch = True

    try:
        for old_doctype in LEGACY_DOCTYPES:
            if not frappe.db.exists("DocType", old_doctype):
                continue
            for old_name in frappe.get_all(old_doctype, pluck="name", order_by="creation asc"):
                if not frappe.db.exists(NEW_DOCTYPE, old_name):
                    _migrate_one(old_doctype, old_name)
                _relink_system_references(old_doctype, old_name)
    finally:
        frappe.flags.mute_emails = previous_mute
        frappe.flags.in_patch = previous_patch


def _migrate_one(old_doctype: str, old_name: str):
    old = frappe.get_doc(old_doctype, old_name)
    intervention_type, intervention_name = _linked_intervention(old_doctype, old)

    if not intervention_type or not intervention_name:
        frappe.throw(f"{old_doctype} {old.name} has no supported linked intervention.")
    if not frappe.db.exists(intervention_type, intervention_name):
        frappe.throw(f"{intervention_type} {intervention_name} linked from {old.name} does not exist.")

    target = frappe.new_doc(NEW_DOCTYPE)
    target.name = old.name
    target.flags.name_set = True
    target.docstatus = 0
    target.ir_intervention = intervention_type
    target.linked_intervention = intervention_name
    target.linked_intervention_processed = 1

    if old_doctype == "Not Guilty Form":
        _map_not_guilty(old, target)
    elif old_doctype == "Performance Improved":
        _map_performance_improved(old, target)

    target.flags.ignore_validate = True
    target.flags.ignore_mandatory = True
    target.flags.ignore_links = True
    target.flags.ignore_permissions = True
    target.flags.ignore_version = True
    target.insert(ignore_permissions=True, ignore_mandatory=True, set_name=old.name)
    _restore_history(target, old)


def _map_not_guilty(old, target):
    scalar_map = {
        "company": "company", "letter_head": "letter_head", "employee": "employee",
        "names": "names", "position": "designation", "signed_ng": "signed_ng",
        "outcome_date": "outcome_date", "type_of_incapacity": "type_of_incapacity",
        "details_of_incapacity": "details_of_incapacity",
    }
    _copy_scalars(old, target, scalar_map)
    target.outcome_type = old.get("type_of_not_guilty") or _default_outcome(target.ir_intervention)
    _copy_table(old, target, "ng_charges", "ng_charges")
    _copy_table(old, target, "disciplinary_history", "disciplinary_history")
    _copy_table(old, target, "previous_incapacity_outcomes", "previous_incapacity_outcomes")


def _map_performance_improved(old, target):
    scalar_map = {
        "company": "company", "letter_head": "letter_head", "employee": "employee",
        "names": "names", "position": "designation", "signed_confirmation": "signed_ng",
        "outcome_date": "outcome_date", "performance_details": "performance_details_nta",
        "improvement_summary": "improvement_summary",
    }
    _copy_scalars(old, target, scalar_map)
    target.outcome_type = old.get("performance_improved_outcome") or "PI"
    _copy_table(old, target, "previous_performance_outcomes", "previous_performance_outcomes")


def _copy_scalars(old, target, mapping):
    for old_field, new_field in mapping.items():
        if target.meta.get_field(new_field):
            target.set(new_field, old.get(old_field))


def _linked_intervention(old_doctype, old):
    if old_doctype == "Performance Improved":
        return "Poor Performance", old.get("linked_poor_performance")
    if old.get("linked_disciplinary_action"):
        return "Disciplinary Action", old.linked_disciplinary_action
    if old.get("linked_incapacity_proceeding"):
        return "Incapacity Proceedings", old.linked_incapacity_proceeding
    return None, None


def _default_outcome(intervention_type):
    return {"Disciplinary Action": "NG", "Poor Performance": "PI", "Incapacity Proceedings": "FIT"}[intervention_type]


def _copy_table(old, target, old_field, new_field):
    if not old.meta.get_field(old_field) or not target.meta.get_field(new_field):
        return
    target.set(new_field, [])
    child_meta = frappe.get_meta(target.meta.get_field(new_field).options)
    for old_row in old.get(old_field) or []:
        values = {}
        for field in child_meta.fields:
            if field.fieldtype in {"Section Break", "Column Break", "Tab Break"}:
                continue
            if old_row.meta.get_field(field.fieldname):
                values[field.fieldname] = old_row.get(field.fieldname)
        target.append(new_field, values)


def _restore_history(target, old):
    frappe.db.sql(
        f"""UPDATE `tab{NEW_DOCTYPE}` SET owner=%s, creation=%s, modified=%s, modified_by=%s, docstatus=%s WHERE name=%s""",
        (old.owner, old.creation, old.modified, old.modified_by, old.docstatus, target.name),
    )
    for field in target.meta.fields:
        if field.fieldtype == "Table" and field.options and frappe.db.table_exists(field.options):
            frappe.db.sql(
                f"""UPDATE `tab{field.options}` SET docstatus=%s WHERE parent=%s AND parenttype=%s AND parentfield=%s""",
                (old.docstatus, target.name, NEW_DOCTYPE, field.fieldname),
            )


def _relink_system_references(old_doctype, name):
    for doctype, type_field, name_field in SYSTEM_REFERENCES:
        if not frappe.db.exists("DocType", doctype):
            continue
        if not frappe.db.has_column(doctype, type_field) or not frappe.db.has_column(doctype, name_field):
            continue
        frappe.db.sql(
            f"""UPDATE `tab{doctype}` SET `{type_field}`=%s WHERE `{type_field}`=%s AND `{name_field}`=%s""",
            (NEW_DOCTYPE, old_doctype, name),
        )
    if frappe.db.exists("DocType", "Dynamic Link") and frappe.db.has_column("Dynamic Link", "link_doctype") and frappe.db.has_column("Dynamic Link", "link_name"):
        frappe.db.sql(
            """UPDATE `tabDynamic Link` SET link_doctype=%s WHERE link_doctype=%s AND link_name=%s""",
            (NEW_DOCTYPE, old_doctype, name),
        )
