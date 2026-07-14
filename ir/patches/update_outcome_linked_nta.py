# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


LEGACY_OUTCOME_DOCTYPE = "Disciplinary Outcome Report"
LEGACY_SELECTOR_DOCTYPE = "NTA Selector"


def execute():
    frappe.flags.ignore_permissions = True

    if not _legacy_schema_exists():
        return

    _clear_existing_links()

    outcome_reports = frappe.get_all(
        LEGACY_OUTCOME_DOCTYPE,
        fields=[
            "name",
            "linked_disciplinary_action",
            "linked_incapacity_proceeding",
        ],
    )

    for report in outcome_reports:
        linked_nta_rows = _get_linked_nta_rows(report)

        if not linked_nta_rows:
            continue

        _replace_linked_nta_rows(
            report_name=report.name,
            linked_nta_rows=linked_nta_rows,
        )


def _legacy_schema_exists():
    """
    Return False on newer sites where the legacy schema was never installed
    or has already been retired.

    Unexpected runtime or data errors are not swallowed.
    """
    if not frappe.db.exists("DocType", LEGACY_OUTCOME_DOCTYPE):
        return False

    if not frappe.db.exists("DocType", LEGACY_SELECTOR_DOCTYPE):
        return False

    required_columns = {
        LEGACY_OUTCOME_DOCTYPE: [
            "linked_nta",
            "linked_disciplinary_action",
            "linked_incapacity_proceeding",
        ],
        LEGACY_SELECTOR_DOCTYPE: [
            "parent",
            "parentfield",
            "parenttype",
            "linked_nta",
        ],
    }

    for doctype, fieldnames in required_columns.items():
        for fieldname in fieldnames:
            if not frappe.db.has_column(doctype, fieldname):
                return False

    return True


def _clear_existing_links():
    frappe.db.sql(
        """
        UPDATE `tabDisciplinary Outcome Report`
        SET `linked_nta` = NULL
        """
    )

    frappe.db.sql(
        """
        DELETE FROM `tabNTA Selector`
        WHERE `parenttype` = %s
          AND `parentfield` = %s
        """,
        (
            LEGACY_OUTCOME_DOCTYPE,
            "linked_nta",
        ),
    )


def _get_linked_nta_rows(report):
    document_names = []

    if report.linked_disciplinary_action:
        document_names.extend(
            _get_parent_linked_ntas(
                parent_doctype="Disciplinary Action",
                parent_name=report.linked_disciplinary_action,
            )
        )

    if report.linked_incapacity_proceeding:
        document_names.extend(
            _get_parent_linked_ntas(
                parent_doctype="Incapacity Proceedings",
                parent_name=report.linked_incapacity_proceeding,
            )
        )

    seen = set()
    unique_document_names = []

    for document_name in document_names:
        if not document_name or document_name in seen:
            continue

        seen.add(document_name)
        unique_document_names.append(document_name)

    return unique_document_names


def _get_parent_linked_ntas(parent_doctype, parent_name):
    if not frappe.db.exists(parent_doctype, parent_name):
        frappe.log_error(
            title="Legacy linked NTA patch",
            message=(
                f"{parent_doctype} {parent_name} was referenced by a "
                f"{LEGACY_OUTCOME_DOCTYPE} record but no longer exists."
            ),
        )
        return []

    parent_doc = frappe.get_doc(parent_doctype, parent_name)

    if not parent_doc.meta.has_field("linked_nta"):
        return []

    linked_ntas = []

    for row in parent_doc.get("linked_nta") or []:
        linked_nta = row.get("linked_nta")

        if linked_nta:
            linked_ntas.append(linked_nta)

    return linked_ntas


def _replace_linked_nta_rows(report_name, linked_nta_rows):
    for idx, document_name in enumerate(linked_nta_rows, start=1):
        frappe.db.sql(
            """
            INSERT INTO `tabNTA Selector`
            (
                `name`,
                `creation`,
                `modified`,
                `modified_by`,
                `owner`,
                `docstatus`,
                `idx`,
                `parent`,
                `parentfield`,
                `parenttype`,
                `linked_nta`
            )
            VALUES
            (
                %s,
                NOW(),
                NOW(),
                %s,
                %s,
                0,
                %s,
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                frappe.generate_hash(length=10),
                frappe.session.user,
                frappe.session.user,
                idx,
                report_name,
                "linked_nta",
                LEGACY_OUTCOME_DOCTYPE,
                document_name,
            ),
        )