# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now

JOB_REQUISITION = "Job Requisition"
OLD_FIELD = "ir_qualifications__skills_required"
NEW_TABLE_FIELD = "ir_designation_skills"


def execute():
    """
    One-off backfill: ir_qualifications__skills_required used to be free text.
    It is now ir_designation_skills, a Designation Skill table (the same child
    doctype Designation's own "skills" field already uses). Split each historic
    record's free text into lines, create/reuse a Skill master per line, and add
    a Designation Skill row for it.

    The original ir_qualifications__skills_required column and its data are left
    untouched - it stays as a read-only legacy backup. Direct child-table SQL is
    intentional so historic (possibly submitted) Job Requisitions do not need to
    be reopened or saved.
    """
    if not frappe.db.exists("DocType", JOB_REQUISITION):
        return

    if not frappe.db.has_column(JOB_REQUISITION, OLD_FIELD):
        return

    if not frappe.db.exists("DocType", "Designation Skill"):
        return

    # Note: this patch runs in post_model_sync, before this app's Custom Field
    # fixtures (including ir_designation_skills itself) are synced. It does not
    # need ir_designation_skills to exist yet - child rows are inserted directly
    # against the Designation Skill table, which is independent of whether Job
    # Requisition's meta already lists it as a field.
    migrate_qualifications_to_skills()


def migrate_qualifications_to_skills():
    rows = frappe.get_all(
        JOB_REQUISITION,
        filters={OLD_FIELD: ["is", "set"]},
        fields=["name", "docstatus", OLD_FIELD],
    )

    for row in rows:
        if frappe.db.exists(
            "Designation Skill",
            {
                "parent": row.name,
                "parenttype": JOB_REQUISITION,
                "parentfield": NEW_TABLE_FIELD,
            },
        ):
            continue

        lines = [line.strip() for line in (row.get(OLD_FIELD) or "").splitlines() if line.strip()]

        for index, skill_name in enumerate(lines):
            if not frappe.db.exists("Skill", skill_name):
                frappe.get_doc({"doctype": "Skill", "skill_name": skill_name}).insert(
                    ignore_permissions=True
                )

            frappe.db.sql(
                """
                INSERT INTO `tabDesignation Skill`
                    (`name`, `creation`, `modified`, `modified_by`, `owner`,
                     `docstatus`, `idx`, `parent`, `parentfield`, `parenttype`,
                     `skill`)
                VALUES
                    (%s, %s, %s, %s, %s,
                     %s, %s, %s, %s, %s,
                     %s)
                """,
                (
                    frappe.generate_hash(length=10),
                    now(),
                    now(),
                    "Administrator",
                    "Administrator",
                    row.docstatus,
                    index + 1,
                    row.name,
                    NEW_TABLE_FIELD,
                    JOB_REQUISITION,
                    skill_name,
                ),
            )

    frappe.db.commit()
