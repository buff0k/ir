# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

EMPLOYEE_DOCTYPE = "Employee"


def execute():
    if "za_local" not in frappe.get_installed_apps():
        return

    if not frappe.db.exists("DocType", EMPLOYEE_DOCTYPE):
        return

    _copy_text_field("custom_id_number", "za_id_number")
    _copy_text_field("custom_nationality", "za_nationality")
    _copy_disabled_status()
    _copy_designated_group()


def _has_columns(*fieldnames):
    return all(
        frappe.db.has_column(EMPLOYEE_DOCTYPE, fieldname)
        for fieldname in fieldnames
    )


def _copy_text_field(source_field, target_field):
    if not _has_columns(source_field, target_field):
        return

    frappe.db.sql(
        f"""
        UPDATE `tabEmployee`
        SET `{target_field}` = `{source_field}`
        WHERE (`{target_field}` IS NULL OR `{target_field}` = '')
          AND (`{source_field}` IS NOT NULL AND `{source_field}` != '')
        """
    )


def _copy_disabled_status():
    if not _has_columns("custom_disabled_employee", "za_is_disabled"):
        return

    frappe.db.sql(
        """
        UPDATE `tabEmployee`
        SET `za_is_disabled` = 1
        WHERE (`za_is_disabled` IS NULL OR `za_is_disabled` = 0)
          AND `custom_disabled_employee` = 1
        """
    )


def _copy_designated_group():
    if not _has_columns("custom_designated_group", "za_race"):
        return

    frappe.db.sql(
        """
        UPDATE `tabEmployee`
        SET `za_race` =
            CASE
                WHEN `custom_designated_group` = 'African' THEN 'African'
                WHEN `custom_designated_group` = 'Coloured' THEN 'Coloured'
                WHEN `custom_designated_group` = 'Indian' THEN 'Indian'
                WHEN `custom_designated_group` = 'White' THEN 'White'
                ELSE 'Other'
            END
        WHERE (`za_race` IS NULL OR `za_race` = '')
          AND (`custom_designated_group` IS NOT NULL
               AND `custom_designated_group` != '')
        """
    )
