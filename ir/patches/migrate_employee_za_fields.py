# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

EMPLOYEE_DOCTYPE = "Employee"

OLD_TO_NEW_OCCUPATIONAL_LEVEL = {
    "Top management": "Top Management",
    "Senior management": "Senior Management",
    "Professionally qualified": "Professionally Qualified",
    "Skilled technical": "Skilled Technical",
    "Semi-skilled": "Semi-Skilled",
    "Unskilled": "Unskilled",
}


def execute():
    if not frappe.db.exists("DocType", EMPLOYEE_DOCTYPE):
        return

    if _has_columns("custom_occupational_level", "za_occupational_level"):
        migrate_occupational_level()

    if _has_columns("custom_disabled_employee", "za_is_disabled"):
        migrate_disabled_status()


def _has_columns(*fieldnames):
    return all(
        frappe.db.has_column(EMPLOYEE_DOCTYPE, fieldname)
        for fieldname in fieldnames
    )


def migrate_occupational_level():
    for old_value, new_value in OLD_TO_NEW_OCCUPATIONAL_LEVEL.items():
        frappe.db.sql(
            """
            UPDATE `tabEmployee`
            SET `za_occupational_level` = %(new_value)s
            WHERE `custom_occupational_level` = %(old_value)s
              AND (`za_occupational_level` IS NULL
                   OR `za_occupational_level` = '')
            """,
            {"old_value": old_value, "new_value": new_value},
        )

    unmapped_values = frappe.db.sql(
        """
        SELECT DISTINCT `custom_occupational_level`
        FROM `tabEmployee`
        WHERE `custom_occupational_level` IS NOT NULL
          AND `custom_occupational_level` != ''
          AND `custom_occupational_level` NOT IN %(mapped_values)s
        """,
        {"mapped_values": tuple(OLD_TO_NEW_OCCUPATIONAL_LEVEL.keys())},
        as_dict=True,
    )

    if unmapped_values:
        frappe.log_error(
            title="Unmapped Employee occupational levels",
            message="\n".join(
                row.custom_occupational_level for row in unmapped_values
            ),
        )


def migrate_disabled_status():
    frappe.db.sql(
        """
        UPDATE `tabEmployee`
        SET `za_is_disabled` = COALESCE(`custom_disabled_employee`, 0)
        WHERE `za_is_disabled` IS NULL OR `za_is_disabled` = 0
        """
    )
