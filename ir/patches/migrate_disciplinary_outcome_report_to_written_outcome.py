# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _

OLD_DOCTYPE = "Disciplinary Outcome Report"
NEW_DOCTYPE = "Written Outcome"
SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action": "linked_disciplinary_action",
    "Incapacity Proceedings": "linked_incapacity_proceeding",
}

SYSTEM_REFERENCE_TABLES = (
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
        frappe.throw(_("Written Outcome must exist before the legacy outcome migration runs."))

    old_names = frappe.get_all(OLD_DOCTYPE, pluck="name", order_by="creation asc")
    if not old_names:
        return

    plans = [_build_plan(name) for name in old_names]
    _validate_plans(plans)

    migrated = 0
    reused = 0
    for plan in plans:
        if frappe.db.exists(NEW_DOCTYPE, plan["old_name"]):
            _validate_existing_target(plan)
            reused += 1
        else:
            _migrate_document(plan)
            migrated += 1
        _relink_system_references(plan["old_name"])

    _restore_amendment_links(plans)

    frappe.logger("ir").info(
        "Disciplinary Outcome Report migration complete: %s created, %s existing targets reused, %s legacy records retained",
        migrated,
        reused,
        len(plans),
    )


def _build_plan(old_name: str) -> dict:
    old_doc = frappe.get_doc(OLD_DOCTYPE, old_name)
    linked = [
        (doctype, old_doc.get(fieldname))
        for doctype, fieldname in SUPPORTED_INTERVENTIONS.items()
        if old_doc.get(fieldname)
    ]

    return {
        "old_name": old_name,
        "old_doc": old_doc,
        "linked": linked,
    }


def _validate_plans(plans: list[dict]):
    errors = []
    for plan in plans:
        old_doc = plan["old_doc"]
        linked = plan["linked"]
        if len(linked) != 1:
            errors.append(
                _("{0}: expected exactly one linked intervention, found {1}.").format(
                    old_doc.name, len(linked)
                )
            )
            continue

        intervention_type, intervention_name = linked[0]
        if not frappe.db.exists(intervention_type, intervention_name):
            errors.append(
                _("{0}: linked {1} {2} does not exist.").format(
                    old_doc.name, intervention_type, intervention_name
                )
            )

    if errors:
        frappe.throw("<br>".join(errors), title=_("Legacy outcome migration preflight failed"))


def _validate_existing_target(plan: dict):
    intervention_type, intervention_name = plan["linked"][0]
    existing = frappe.db.get_value(
        NEW_DOCTYPE,
        plan["old_name"],
        ["ir_intervention", "linked_intervention"],
        as_dict=True,
    )
    if not existing:
        return
    if (
        existing.ir_intervention != intervention_type
        or existing.linked_intervention != intervention_name
    ):
        frappe.throw(
            _("Written Outcome {0} already exists but is linked to {1} {2}, not {3} {4}.").format(
                plan["old_name"],
                existing.ir_intervention,
                existing.linked_intervention,
                intervention_type,
                intervention_name,
            )
        )


def _migrate_document(plan: dict):
    old_doc = plan["old_doc"]
    intervention_type, intervention_name = plan["linked"][0]
    source = frappe.get_doc(intervention_type, intervention_name)

    new_doc = frappe.new_doc(NEW_DOCTYPE)
    new_doc.name = old_doc.name
    new_doc.flags.ignore_validate = True
    new_doc.flags.ignore_validate_update_after_submit = True
    new_doc.flags.in_migrate = True

    new_doc.ir_intervention = intervention_type
    new_doc.linked_intervention = intervention_name
    new_doc.linked_intervention_processed = 1

    new_doc.employee = old_doc.get("employee") or source.get("accused")
    new_doc.employee_name = old_doc.get("names") or source.get("accused_name")
    new_doc.employee_designation = old_doc.get("position") or source.get("accused_pos")
    new_doc.employee_branch = source.get("branch") or _employee_branch(new_doc.employee)
    new_doc.company = old_doc.get("company") or source.get("company")
    new_doc.letter_head = old_doc.get("letter_head") or source.get("letter_head")

    new_doc.complainant = old_doc.get("complainant") or source.get("complainant")
    new_doc.complainant_name = old_doc.get("complainant_name") or source.get("compl_name")
    new_doc.chairperson = old_doc.get("chairperson")
    new_doc.chairperson_name = old_doc.get("chairperson_name")
    new_doc.approver = old_doc.get("sanction_approver")
    new_doc.approver_name = old_doc.get("approver_name")

    new_doc.enquiry_date = old_doc.get("date_of_enquiry")
    new_doc.outcome_date = old_doc.get("date") or old_doc.get("outcome_date")
    new_doc.linked_nta = _latest_linked_nta(old_doc)

    new_doc.summary_introduction = old_doc.get("introduction")
    new_doc.summary_complainant = old_doc.get("complainant_case")
    new_doc.summary_accused = old_doc.get("accused_case")
    new_doc.summary_analysis = old_doc.get("analysis_of_evidence")
    new_doc.summary_finding = old_doc.get("finding")
    new_doc.summary_mitigation = old_doc.get("mitigating_considerations")
    new_doc.summary_aggravation = old_doc.get("aggravating_conisderations")
    # Legacy `outcome` is Markdown narrative; the new `outcome` is a Link.
    new_doc.summary_outcome = old_doc.get("outcome")
    new_doc.complete_outcome = old_doc.get("complete_outcome")
    new_doc.attach_record = old_doc.get("evidence")
    new_doc.outcome = _linked_outcome(old_doc, source)

    if intervention_type == "Disciplinary Action":
        _copy_charge_rows(old_doc, new_doc)
        _copy_disciplinary_history(old_doc, new_doc)
    else:
        new_doc.incap_type_nta = old_doc.get("type_of_incapacity")
        new_doc.incapacity_details_nta = old_doc.get("details_of_incapacity")
        new_doc.final_incapacity_details = old_doc.get("details_of_incapacity")
        _copy_incapacity_history(old_doc, new_doc)

    _copy_evidence(old_doc, "compl_evidence", new_doc, "complainant_evidence")
    _copy_evidence(old_doc, "acc_evidence", new_doc, "accused_evidence")

    historical_docstatus = int(old_doc.docstatus or 0)
    new_doc.docstatus = 0
    new_doc.insert(
        ignore_permissions=True,
        ignore_mandatory=True,
        ignore_links=True,
        set_name=old_doc.name,
    )

    _restore_metadata_and_status(new_doc, old_doc, historical_docstatus)


def _employee_branch(employee):
    if not employee:
        return None
    return frappe.db.get_value("Employee", employee, "branch")


def _latest_linked_nta(old_doc):
    names = [
        row.get("linked_nta")
        for row in (old_doc.get("linked_nta") or [])
        if row.get("linked_nta") and frappe.db.exists("NTA Enquiry", row.get("linked_nta"))
    ]
    if not names:
        return None

    rows = frappe.get_all(
        "NTA Enquiry",
        filters={"name": ["in", names]},
        fields=["name"],
        order_by="creation desc, modified desc",
        limit_page_length=1,
    )
    return rows[0].name if rows else names[-1]


def _linked_outcome(old_doc, source):
    candidates = [old_doc.get("linked_sanction"), source.get("outcome")]
    for candidate in candidates:
        if candidate and frappe.db.exists("Offence Outcome", candidate):
            return candidate
    return None


def _copy_charge_rows(old_doc, new_doc):
    for row in old_doc.get("outcome_charges") or []:
        value = row.get("indiv_charge")
        if not value:
            continue
        new_doc.append("nta_charges", {"indiv_charge": value})
        # The legacy report did not distinguish NTA charges from final charges.
        new_doc.append("final_charges", {"indiv_charge": value})


def _copy_disciplinary_history(old_doc, new_doc):
    for row in old_doc.get("disciplinary_history") or []:
        new_doc.append(
            "disciplinary_history",
            {
                "disc_action": row.get("disc_action"),
                "date": row.get("date"),
                "sanction": row.get("sanction"),
                "charges": row.get("charges"),
            },
        )


def _copy_incapacity_history(old_doc, new_doc):
    for row in old_doc.get("previous_incapacity_outcomes") or []:
        new_doc.append(
            "previous_incapacity_outcomes",
            {
                "incap_proc": row.get("incap_proc"),
                "date": row.get("date"),
                "sanction": row.get("sanction"),
                "incap_details": row.get("incap_details"),
            },
        )


def _copy_evidence(old_doc, old_field, new_doc, new_field):
    for row in old_doc.get(old_field) or []:
        attachment = row.get("attachment")
        description = row.get("description")
        if not attachment and not description:
            continue
        new_doc.append(
            new_field,
            {
                "evidence_attach": attachment,
                "evidence_description": description,
            },
        )


def _restore_metadata_and_status(new_doc, old_doc, historical_docstatus):
    values = {
        "owner": old_doc.owner,
        "creation": old_doc.creation,
        "modified": old_doc.modified,
        "modified_by": old_doc.modified_by,
        "docstatus": historical_docstatus,
    }
    frappe.db.set_value(NEW_DOCTYPE, new_doc.name, values, update_modified=False)

    for field in frappe.get_meta(NEW_DOCTYPE).get_table_fields():
        child_doctype = field.options
        if not child_doctype:
            continue
        frappe.db.sql(
            f"""UPDATE `tab{child_doctype}`
                SET docstatus = %s
                WHERE parent = %s AND parenttype = %s AND parentfield = %s""",
            (historical_docstatus, new_doc.name, NEW_DOCTYPE, field.fieldname),
        )


def _restore_amendment_links(plans: list[dict]):
    for plan in plans:
        old_doc = plan["old_doc"]
        amended_from = old_doc.get("amended_from")
        if amended_from and frappe.db.exists(NEW_DOCTYPE, amended_from):
            frappe.db.set_value(
                NEW_DOCTYPE,
                old_doc.name,
                "amended_from",
                amended_from,
                update_modified=False,
            )


def _relink_system_references(name: str):
    for doctype, type_field, name_field in SYSTEM_REFERENCE_TABLES:
        if not frappe.db.exists("DocType", doctype):
            continue
        if not frappe.db.has_column(doctype, type_field) or not frappe.db.has_column(doctype, name_field):
            continue
        table = f"tab{doctype}"
        frappe.db.sql(
            f"""UPDATE `{table}`
                SET `{type_field}` = %s
                WHERE `{type_field}` = %s AND `{name_field}` = %s""",
            (NEW_DOCTYPE, OLD_DOCTYPE, name),
        )

    if frappe.db.exists("DocType", "Dynamic Link"):
        if frappe.db.has_column("Dynamic Link", "link_doctype") and frappe.db.has_column("Dynamic Link", "link_name"):
            table = "tabDynamic Link"
            frappe.db.sql(
                f"""UPDATE `{table}`
                    SET `link_doctype` = %s
                    WHERE `link_doctype` = %s AND `link_name` = %s""",
                (NEW_DOCTYPE, OLD_DOCTYPE, name),
            )
