# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


OLD_TO_NEW_OCCUPATIONAL_LEVEL = {
    "Top management": "Top Management",
    "Senior management": "Senior Management",
    "Professionally qualified": "Professionally Qualified",
    "Skilled technical": "Skilled Technical",
    "Semi-skilled": "Semi-Skilled",
    "Unskilled": "Unskilled",
}


def execute():
    doctype = "Employee"

    required_fields = [
        "custom_occupational_level",
        "custom_disabled_employee",
        "za_occupational_level",
        "za_is_disabled",
    ]

    missing_fields = [
        fieldname
        for fieldname in required_fields
        if not frappe.db.has_column(doctype, fieldname)
    ]

    if missing_fields:
        frappe.throw(
            "Cannot migrate Employee ZA fields. Missing columns on Employee: {0}".format(
                ", ".join(missing_fields)
            )
        )

    migrate_occupational_level()
    migrate_disabled_status()


def migrate_occupational_level():
    for old_value, new_value in OLD_TO_NEW_OCCUPATIONAL_LEVEL.items():
        frappe.db.sql(
            """
            UPDATE `tabEmployee`
            SET za_occupational_level = %(new_value)s
            WHERE custom_occupational_level = %(old_value)s
            """,
            {
                "old_value": old_value,
                "new_value": new_value,
            },
        )

    unmapped_values = frappe.db.sql(
        """
        SELECT DISTINCT custom_occupational_level
        FROM `tabEmployee`
        WHERE custom_occupational_level IS NOT NULL
          AND custom_occupational_level != ''
          AND custom_occupational_level NOT IN %(mapped_values)s
        """,
        {
            "mapped_values": tuple(OLD_TO_NEW_OCCUPATIONAL_LEVEL.keys()),
        },
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
        SET za_is_disabled = COALESCE(custom_disabled_employee, 0)
        """
    )