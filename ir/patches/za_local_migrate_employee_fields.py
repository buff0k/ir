# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe


def _is_za_local_installed() -> bool:
    try:
        return "za_local" in frappe.get_installed_apps()
    except Exception:
        return False


def execute():
    # Only run when za_local is installed
    if not _is_za_local_installed():
        return

    # ------------------------------------------------------------
    # 1) custom_id_number -> za_id_number (Data)
    # SQL-based so it works even if Custom Field docs are deleted by za_local
    # ------------------------------------------------------------
    frappe.db.sql("""
        UPDATE `tabEmployee`
        SET za_id_number = custom_id_number
        WHERE (za_id_number IS NULL OR za_id_number = '')
          AND (custom_id_number IS NOT NULL AND custom_id_number != '')
    """)

    # ------------------------------------------------------------
    # 2) custom_nationality -> za_nationality (Link: Country)
    # Assumes both store the linked document name
    # ------------------------------------------------------------
    frappe.db.sql("""
        UPDATE `tabEmployee`
        SET za_nationality = custom_nationality
        WHERE (za_nationality IS NULL OR za_nationality = '')
          AND (custom_nationality IS NOT NULL AND custom_nationality != '')
    """)

    # ------------------------------------------------------------
    # 3) custom_disabled_employee -> za_is_disabled (Check)
    # Only set to 1 when source is 1; do not overwrite if already set
    # ------------------------------------------------------------
    frappe.db.sql("""
        UPDATE `tabEmployee`
        SET za_is_disabled = 1
        WHERE (za_is_disabled IS NULL OR za_is_disabled = 0)
          AND (custom_disabled_employee IS NOT NULL AND custom_disabled_employee = 1)
    """)

    # ------------------------------------------------------------
    # 4) custom_designated_group (Link -> Designated Group) -> za_race (Select)
    #
    # za_local: za_race SELECT options:
    #   African, Coloured, Indian, White, Other
    #
    # ir: custom_designated_group LINK values (Designated Group names):
    #   African, Coloured, Indian, White, Unknown
    #
    # Mapping:
    #   African   -> African
    #   Coloured -> Coloured
    #   Indian   -> Indian
    #   White    -> White
    #   Unknown  -> Other
    #   anything else -> Other
    #
    # Only fill za_race when it's empty to avoid overwriting manually-corrected data.
    # ------------------------------------------------------------
    frappe.db.sql("""
        UPDATE `tabEmployee`
        SET za_race =
            CASE
                WHEN custom_designated_group IS NULL OR custom_designated_group = '' THEN za_race

                WHEN custom_designated_group = 'African' THEN 'African'
                WHEN custom_designated_group = 'Coloured' THEN 'Coloured'
                WHEN custom_designated_group = 'Indian' THEN 'Indian'
                WHEN custom_designated_group = 'White' THEN 'White'

                WHEN custom_designated_group = 'Unknown' THEN 'Other'
                ELSE 'Other'
            END
        WHERE (za_race IS NULL OR za_race = '')
          AND (custom_designated_group IS NOT NULL AND custom_designated_group != '')
    """)

    # No explicit commit required; migrate manages transactions.
