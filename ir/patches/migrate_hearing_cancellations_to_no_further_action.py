from __future__ import annotations

import frappe
from frappe.utils import cint

OLD_DOCTYPE = "Hearing Cancellation Form"
NEW_DOCTYPE = "No Further Action Form"

SOURCE_LINKS = (
    ("linked_disciplinary_action", "Disciplinary Action"),
    ("linked_incapacity_proceeding", "Incapacity Proceedings"),
    ("linked_poor_performance", "Poor Performance"),
)

CHILD_FIELDS = (
    "ng_charges",
    "disciplinary_history",
    "previous_incapacity_outcomes",
    "previous_performance_outcomes",
)

SYSTEM_CHILD_FIELDS = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus",
    "idx", "parent", "parentfield", "parenttype", "doctype",
}


def execute():
    if not frappe.db.table_exists(OLD_DOCTYPE):
        return
    if not frappe.db.table_exists(NEW_DOCTYPE):
        return

    for old_name in frappe.get_all(OLD_DOCTYPE, pluck="name", order_by="creation asc"):
        _migrate_one(old_name)


def _get_source(old):
    for fieldname, doctype in SOURCE_LINKS:
        value = old.get(fieldname)
        if value:
            return doctype, value
    return None, None


def _equivalent_exists(intervention, linked_intervention, outcome_type, outcome_date):
    filters = {
        "ir_intervention": intervention,
        "linked_intervention": linked_intervention,
        "outcome_type": outcome_type,
    }
    if outcome_date:
        filters["outcome_date"] = outcome_date
    else:
        filters["outcome_date"] = ["is", "not set"]
    return frappe.db.exists(NEW_DOCTYPE, filters)


def _copy_child_rows(old, target, fieldname):
    old_field = old.meta.get_field(fieldname)
    target_field = target.meta.get_field(fieldname)
    if not old_field or not target_field:
        return

    target_meta = frappe.get_meta(target_field.options)
    allowed = {df.fieldname for df in target_meta.fields if df.fieldname}
    rows = []
    for source_row in old.get(fieldname) or []:
        values = {}
        for fieldname_to_copy in allowed:
            if fieldname_to_copy in SYSTEM_CHILD_FIELDS:
                continue
            value = source_row.get(fieldname_to_copy)
            if value not in (None, ""):
                values[fieldname_to_copy] = value
        rows.append(values)
    target.set(fieldname, rows)


def _attached_files(old_name):
    return frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": OLD_DOCTYPE,
            "attached_to_name": old_name,
        },
        fields=["name", "file_url", "file_name", "attached_to_field"],
        order_by="creation asc",
    )


def _signed_file(files):
    for row in files:
        filename = (row.file_name or "").lower()
        if any(word in filename for word in ("signed", "cancel", "outcome")):
            return row
    return files[0] if files else None


def _valid_link(doctype, value):
    if not value:
        return None
    return value if frappe.db.exists(doctype, value) else None


def _source_identity(intervention, linked_intervention):
    source = frappe.get_doc(intervention, linked_intervention)

    if intervention == "Poor Performance":
        employee = source.get("employee")
        employee_name = source.get("employee_name")
        designation = source.get("employee_designation")
    else:
        employee = source.get("accused") or source.get("employee")
        employee_name = source.get("accused_name") or source.get("employee_name")
        designation = (
            source.get("accused_pos")
            or source.get("employee_designation")
            or source.get("designation")
        )

    return {
        "employee": _valid_link("Employee", employee),
        "names": employee_name,
        "designation": _valid_link("Designation", designation),
        "company": _valid_link("Company", source.get("company")),
        "letter_head": _valid_link("Letter Head", source.get("letter_head")),
        "type_of_incapacity": _valid_link(
            "Type of Incapacity", source.get("type_of_incapacity")
        ),
        "details_of_incapacity": source.get("details_of_incapacity"),
        "performance_details_nta": (
            source.get("details_of_poor_performance")
            or source.get("performance_details")
        ),
    }


def _migrate_one(old_name):
    old = frappe.get_doc(OLD_DOCTYPE, old_name)
    intervention, linked_intervention = _get_source(old)
    if not intervention or not linked_intervention:
        frappe.log_error(
            title="Hearing Cancellation migration skipped",
            message=f"No linked intervention could be determined for {old.name}.",
        )
        return

    outcome_type = old.get("cancellation_type") or "CAN"
    outcome_date = old.get("outcome_date")
    if _equivalent_exists(intervention, linked_intervention, outcome_type, outcome_date):
        return

    target = frappe.new_doc(NEW_DOCTYPE)
    target.ir_intervention = intervention
    target.linked_intervention = linked_intervention
    target.linked_intervention_processed = 1
    target.outcome_type = outcome_type
    target.outcome_date = outcome_date

    source_identity = _source_identity(intervention, linked_intervention)

    # The legacy `coy` field is only a displayed company/clock number. It is
    # never a valid substitute for Employee.name and must not be mapped to the
    # Employee Link field.
    target.employee = (
        _valid_link("Employee", old.get("employee"))
        or source_identity.get("employee")
    )
    target.names = old.get("names") or source_identity.get("names")
    target.designation = (
        _valid_link("Designation", old.get("position"))
        or source_identity.get("designation")
    )
    target.company = (
        _valid_link("Company", old.get("company"))
        or source_identity.get("company")
    )
    target.letter_head = (
        _valid_link("Letter Head", old.get("letter_head"))
        or source_identity.get("letter_head")
    )

    authorized_by = _valid_link("Employee", old.get("authorized_by"))
    if target.meta.get_field("authorized_by"):
        target.authorized_by = authorized_by
    if target.meta.get_field("auth_names"):
        target.auth_names = old.get("auth_names")
    if target.meta.get_field("auth_designation") and authorized_by:
        target.auth_designation = _valid_link(
            "Designation",
            frappe.db.get_value("Employee", authorized_by, "designation"),
        )
    if target.meta.get_field("cancel_reason"):
        target.cancel_reason = old.get("reason_for_cancellation")

    target.type_of_incapacity = (
        _valid_link("Type of Incapacity", old.get("type_of_incapacity"))
        or source_identity.get("type_of_incapacity")
    )
    target.details_of_incapacity = (
        old.get("details_of_incapacity")
        or source_identity.get("details_of_incapacity")
    )
    target.performance_details_nta = (
        old.get("performance_details")
        or source_identity.get("performance_details_nta")
    )

    for child_field in CHILD_FIELDS:
        _copy_child_rows(old, target, child_field)

    files = _attached_files(old.name)
    signed = _signed_file(files)
    if signed and target.meta.get_field("signed_ng"):
        target.signed_ng = signed.file_url

    # Historical records are transposed as stored. Validation is deliberately
    # skipped because older cancellation reasons were optional.
    target.flags.ignore_validate = True
    target.flags.ignore_mandatory = True
    target.insert(ignore_permissions=True, ignore_mandatory=True)

    old_docstatus = cint(old.docstatus)
    if old_docstatus in (1, 2):
        frappe.db.set_value(
            NEW_DOCTYPE, target.name, "docstatus", old_docstatus, update_modified=False
        )
        for child_field in CHILD_FIELDS:
            field = target.meta.get_field(child_field)
            if not field:
                continue
            frappe.db.sql(
                f"""
                UPDATE `tab{field.options}`
                   SET docstatus = %s
                 WHERE parent = %s
                   AND parenttype = %s
                   AND parentfield = %s
                """,
                (old_docstatus, target.name, NEW_DOCTYPE, child_field),
            )

    for file_row in files:
        values = {
            "attached_to_doctype": NEW_DOCTYPE,
            "attached_to_name": target.name,
        }
        if signed and file_row.name == signed.name:
            values["attached_to_field"] = "signed_ng"
        frappe.db.set_value("File", file_row.name, values, update_modified=False)

    frappe.db.set_value(
        NEW_DOCTYPE,
        target.name,
        {
            "owner": old.owner,
            "creation": old.creation,
            "modified": old.modified,
            "modified_by": old.modified_by,
        },
        update_modified=False,
    )
