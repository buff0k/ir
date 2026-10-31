# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Backend for the "EEA2 Employment Equity Widget" Custom HTML Block.

Builds the EEA2 Workforce Profile matrix (occupational level x race x
gender, with Foreign Nationals as a separate pair of columns and a grand
total row) from Employee.za_race / za_occupational_level / za_nationality -
the same custom fields, and the same occupational-level/race normalisation
already proven in hr_exception_report.py's employment-equity profile, reused
here rather than re-implemented so the two stay consistent.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from ir.industrial_relations.page.hr_exception_report.hr_exception_report import (
    EE_LEVELS,
    _normalise_level,
    _normalise_race,
)
from ir.ir_labour.report_utils import get_permitted_company, validate_employee_fields

RACE_CODES = {
    "African": "a",
    "Coloured": "c",
    "Indian": "i",
    "White": "w",
}


def _empty_row(level: str) -> dict:
    row = {"occupational_level": level, "is_total_row": 0, "total": 0}
    for code in RACE_CODES.values():
        row[f"{code}_male"] = 0
        row[f"{code}_female"] = 0
    row["foreign_male"] = 0
    row["foreign_female"] = 0
    return row


def _gender_key(gender) -> str | None:
    value = (gender or "").strip().lower()
    if value == "male":
        return "male"
    if value == "female":
        return "female"
    return None


def _add_person(row: dict, gender, race, is_foreign: bool) -> None:
    gender_key = _gender_key(gender)
    if gender_key:
        if is_foreign:
            row[f"foreign_{gender_key}"] += 1
        elif race:
            row[f"{RACE_CODES[race]}_{gender_key}"] += 1
    row["total"] += 1


@frappe.whitelist()
def get_eea2_data(filters=None) -> dict:
    """EEA2 Workforce Profile rows for the widget: one per occupational
    level, plus an Unclassified row only if it has anyone in it, plus a
    grand total row."""
    frappe.only_for(["System Manager", "HR Manager", "IR Officer"])

    filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
    company = get_permitted_company(filters)
    validate_employee_fields({"za_race", "za_occupational_level", "za_nationality", "za_is_disabled"})
    country = filters.get("country") or "South Africa"
    branch = filters.get("branch")
    disabled_only = cint(filters.get("disabled"))

    conditions = ["e.company = %(company)s", "e.status = 'Active'"]
    values = {"company": company}
    if branch:
        conditions.append("e.branch = %(branch)s")
        values["branch"] = branch
    if disabled_only:
        conditions.append("e.za_is_disabled = 1")

    rows = frappe.db.sql(
        f"""
        SELECT e.gender, e.za_race AS race, e.za_occupational_level AS occupational_level,
               e.za_nationality AS nationality
        FROM `tabEmployee` e
        WHERE {" AND ".join(conditions)}
        """,
        values,
        as_dict=True,
    )

    levels = {level: _empty_row(level) for level in EE_LEVELS}
    unclassified = _empty_row(_("Unclassified"))
    grand_total = _empty_row(_("Total"))
    grand_total["is_total_row"] = 1

    for row in rows:
        race = _normalise_race(row.race)
        level = _normalise_level(row.occupational_level)
        is_foreign = bool(row.nationality) and row.nationality != country

        target = levels.get(level, unclassified)
        _add_person(target, row.gender, race, is_foreign)
        _add_person(grand_total, row.gender, race, is_foreign)

    result_rows = [levels[level] for level in EE_LEVELS]
    if unclassified["total"]:
        result_rows.append(unclassified)
    result_rows.append(grand_total)

    return {"rows": result_rows}
