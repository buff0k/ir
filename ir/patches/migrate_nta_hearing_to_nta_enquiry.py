# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _

OLD_DOCTYPE = "NTA Hearing"
NEW_DOCTYPE = "NTA Enquiry"

SOURCE_FIELDS = (
    ("linked_disciplinary_action", "Disciplinary Action"),
    ("linked_incapacity_proceeding", "Incapacity Proceedings"),
    ("linked_poor_performance", "Poor Performance"),
)

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
    if not frappe.db.exists("DocType", OLD_DOCTYPE):
        return
    if not frappe.db.exists("DocType", NEW_DOCTYPE):
        frappe.throw(_("Create the NTA Enquiry DocType before running this patch."))

    old_names = frappe.get_all(OLD_DOCTYPE, pluck="name", order_by="creation asc")
    if not old_names:
        return

    plans = [_build_plan(name) for name in old_names]
    for plan in plans:
        _migrate_document(plan)
        _move_system_references(plan["name"])
        _move_dynamic_link_references(plan["name"])


def _build_plan(name: str) -> dict:
    old_doc = frappe.get_doc(OLD_DOCTYPE, name)
    links = [
        (fieldname, source_doctype, old_doc.get(fieldname))
        for fieldname, source_doctype in SOURCE_FIELDS
        if old_doc.get(fieldname)
    ]
    if len(links) != 1:
        frappe.throw(
            _("{0} must have exactly one linked intervention; found {1}.").format(name, len(links))
        )

    _fieldname, source_doctype, source_name = links[0]
    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("Linked {0} {1} does not exist for {2}.").format(source_doctype, source_name, name))

    return {
        "name": name,
        "old_doc": old_doc,
        "source_doctype": source_doctype,
        "source_name": source_name,
    }


def _migrate_document(plan: dict) -> None:
    if frappe.db.exists(NEW_DOCTYPE, plan["name"]):
        return

    old_doc = plan["old_doc"]
    new_doc = frappe.new_doc(NEW_DOCTYPE)
    new_doc.name = old_doc.name
    new_doc.flags.name_set = True
    new_doc.flags.ignore_permissions = True
    new_doc.flags.ignore_mandatory = True
    new_doc.flags.ignore_links = True
    new_doc.flags.ignore_validate = True

    old_meta = frappe.get_meta(OLD_DOCTYPE)
    new_meta = frappe.get_meta(NEW_DOCTYPE)
    old_fields = {field.fieldname: field for field in old_meta.fields}

    for field in new_meta.fields:
        fieldname = field.fieldname
        if fieldname in {
            "amended_from",
            "ir_intervention",
            "linked_intervention",
            "linked_intervention_processed",
            "employee",
        }:
            continue
        old_field = old_fields.get(fieldname)
        if not old_field:
            continue
        if field.fieldtype == "Table" and old_field.fieldtype == "Table":
            for old_row in old_doc.get(fieldname) or []:
                row = new_doc.append(fieldname, {})
                for child_field in frappe.get_meta(field.options).fields:
                    if child_field.fieldname in old_row.as_dict():
                        row.set(child_field.fieldname, old_row.get(child_field.fieldname))
        elif field.fieldtype != "Table":
            new_doc.set(fieldname, old_doc.get(fieldname))

    new_doc.ir_intervention = plan["source_doctype"]
    new_doc.linked_intervention = plan["source_name"]
    new_doc.linked_intervention_processed = 1
    new_doc.employee = old_doc.get("employee") or old_doc.get("coy")

    if old_doc.get("amended_from"):
        new_doc.amended_from = old_doc.amended_from

    # Frappe only permits a new document to be inserted as Draft. Historical
    # Submitted/Cancelled status is restored directly after the insert.
    historical_docstatus = old_doc.docstatus or 0
    historical_metadata = {
        "owner": old_doc.owner,
        "creation": old_doc.creation,
        "modified": old_doc.modified,
        "modified_by": old_doc.modified_by,
    }

    new_doc.docstatus = 0
    for table_field in new_meta.get_table_fields():
        for row in new_doc.get(table_field.fieldname) or []:
            row.docstatus = 0

    new_doc.insert(
        ignore_permissions=True,
        ignore_mandatory=True,
        ignore_links=True,
        set_name=old_doc.name,
    )

    _restore_historical_state(
        new_doc.name,
        new_meta,
        historical_docstatus,
        historical_metadata,
    )


def _restore_historical_state(
    name: str,
    new_meta,
    historical_docstatus: int,
    historical_metadata: dict,
) -> None:
    """Restore audit fields and historical docstatus without workflow transitions."""
    parent_values = {
        **historical_metadata,
        "docstatus": historical_docstatus,
    }
    frappe.db.set_value(
        NEW_DOCTYPE,
        name,
        parent_values,
        update_modified=False,
    )

    for table_field in new_meta.get_table_fields():
        child_doctype = table_field.options
        if not child_doctype or not frappe.db.exists("DocType", child_doctype):
            continue

        frappe.db.sql(
            f"""
            UPDATE `tab{child_doctype}`
               SET `docstatus` = %s
             WHERE `parent` = %s
               AND `parenttype` = %s
               AND `parentfield` = %s
            """,
            (
                historical_docstatus,
                name,
                NEW_DOCTYPE,
                table_field.fieldname,
            ),
        )


def _move_system_references(name: str) -> None:
    for doctype, type_field, name_field in SYSTEM_REFERENCES:
        if not frappe.db.exists("DocType", doctype):
            continue
        meta = frappe.get_meta(doctype)
        if not meta.has_field(type_field) or not meta.has_field(name_field):
            continue
        frappe.db.sql(
            f"""
            UPDATE `tab{doctype}`
               SET `{type_field}` = %s
             WHERE `{type_field}` = %s
               AND `{name_field}` = %s
            """,
            (NEW_DOCTYPE, OLD_DOCTYPE, name),
        )


def _move_dynamic_link_references(name: str) -> None:
    for doctype_name in frappe.get_all("DocType", filters={"issingle": 0}, pluck="name"):
        try:
            meta = frappe.get_meta(doctype_name)
        except Exception:
            continue

        for field in meta.fields:
            if field.fieldtype != "Dynamic Link" or not field.options:
                continue
            selector = meta.get_field(field.options)
            if not selector:
                continue
            table = f"tab{doctype_name}"
            try:
                frappe.db.sql(
                    f"""
                    UPDATE `{table}`
                       SET `{field.options}` = %s
                     WHERE `{field.options}` = %s
                       AND `{field.fieldname}` = %s
                    """,
                    (NEW_DOCTYPE, OLD_DOCTYPE, name),
                )
            except Exception:
                # Some virtual or nonstandard doctypes may not have a physical table.
                continue
