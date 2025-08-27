# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.xlsxutils import make_xlsx

# Mapping for designated groups to column bases
DG_MAP = {"African": "a", "Coloured": "c", "Indian": "i", "White": "w"}
MALE_KEYS   = ["a_male", "c_male", "i_male", "w_male"]
FEMALE_KEYS = ["a_female", "c_female", "i_female", "w_female"]
ALL_KEYS    = MALE_KEYS + FEMALE_KEYS + ["foreign_male", "foreign_female"]


def execute(filters=None):
    filters = filters or {}
    company = filters.get("company")
    country = filters.get("country")
    if not company or not country:
        frappe.throw("Please select both Company and Country")

    branch = (filters.get("branch") or "").strip()
    disabled_only = frappe.utils.cint(filters.get("disabled") or 0)

    # Resolve Employee schema (use sensible fallbacks)
    emp_meta   = frappe.get_meta("Employee")
    occ_field  = "custom_occupational_level" if emp_meta.get_field("custom_occupational_level") else "occupational_level"
    dg_field   = "custom_designated_group" if emp_meta.get_field("custom_designated_group") else "race"
    nat_field  = _first_present(emp_meta, ["custom_nationality", "nationality"])
    foreign_fl = _first_present_check(emp_meta, ["custom_foreign_national", "custom_is_foreign_national", "is_foreign_national", "foreign_national"])
    has_emp_type = frappe.db.has_column("Employee", "employment_type")

    # Occupational Level ordering (Paterson F→A if present)
    if frappe.db.has_column("Occupational Level", "paterson_band"):
        occ_levels = frappe.get_all(
            "Occupational Level",
            fields=["name", "paterson_band"],
            order_by="FIELD(paterson_band,'F','E','D','C','B','A')",
        )
    else:
        occ_levels = frappe.get_all("Occupational Level", fields=["name"], order_by="name")

    # Prepare per-level rows (ALL employees), plus totals rows
    rows_by_level = {ol["name"]: _init_zero_row(ol["name"]) for ol in occ_levels}
    perm_total    = _init_zero_row("TOTAL PERMANENT")
    temp_row      = _init_zero_row("Temporary employees")

    # Pull employees once; do all math in Python
    fields = [
        "name", "status", "gender", "employment_type",
        f"{occ_field} as occ_level",
        f"{dg_field} as dg",
    ]
    if nat_field:
        fields.append(f"{nat_field} as nationality")
    if foreign_fl:
        fields.append(f"{foreign_fl} as is_foreign")

    base_filters = {"company": company, "status": "Active"}
    if branch:
        base_filters["branch"] = branch
    if disabled_only:
        base_filters["custom_disabled_employee"] = 1  # adjust here if your field differs

    employees = frappe.get_all("Employee", fields=fields, filters=base_filters)

    # Aggregate
    for e in employees:
        gender = (e.get("gender") or "").strip()
        if gender not in ("Male", "Female"):
            continue  # EEA2 buckets are Male/Female only

        level = e.get("occ_level")
        if not level or level not in rows_by_level:
            # Skip employees not mapped to an Occupational Level
            # (Optionally, you could accumulate them under an "Unassigned" row.)
            continue

        emp_type = (e.get("employment_type") or "").strip()
        is_perm  = (emp_type.lower() == "full-time") if has_emp_type else False
        is_temp  = not is_perm  # all non-Full-time (including blank) are Temporary

        # Foreign detection (prefer boolean flag, else nationality != selected country)
        if foreign_fl is not None:
            is_foreign = bool(e.get("is_foreign"))
        elif nat_field is not None:
            nat = (e.get("nationality") or "").strip()
            is_foreign = bool(nat) and nat != country
        else:
            is_foreign = False  # if we can't tell, treat as national

        # ----- Per-level rows include ALL employees -----
        r = rows_by_level[level]
        if is_foreign:
            key = "foreign_male" if gender == "Male" else "foreign_female"
            r[key] += 1
        else:
            base = _norm_dg(e.get("dg"))
            if base:
                key = f"{base}_male" if gender == "Male" else f"{base}_female"
                r[key] += 1
            # else: no DG value -> ignore for A/C/I/W counts

        # ----- Totals split by employment_type -----
        target = perm_total if is_perm else temp_row
        if is_foreign:
            key = "foreign_male" if gender == "Male" else "foreign_female"
            target[key] += 1
        else:
            base = _norm_dg(e.get("dg"))
            if base:
                key = f"{base}_male" if gender == "Male" else f"{base}_female"
                target[key] += 1

    # Finalise per-level totals
    data = []
    for name in rows_by_level:
        row = rows_by_level[name]
        row["total"] = _row_sum(row)
        data.append(row)

    # TOTAL PERMANENT row
    perm_total["occupational_level"] = "TOTAL PERMANENT"
    perm_total["is_total_row"] = 1
    perm_total["total"] = _row_sum(perm_total)
    data.append(perm_total)

    # Temporary employees row
    temp_row["occupational_level"] = "Temporary employees"
    temp_row["total"] = _row_sum(temp_row)
    data.append(temp_row)

    # GRAND TOTAL
    grand = _init_zero_row("GRAND TOTAL")
    _add_into(grand, perm_total)
    _add_into(grand, temp_row)
    grand["is_total_row"] = 1
    grand["total"] = _row_sum(grand)
    data.append(grand)

    # Columns
    columns = [
        {"fieldname": "occupational_level", "label": "Occupational Levels", "fieldtype": "Data", "width": 320},
        {"fieldname": "a_male",            "label": "Male A",        "fieldtype": "Int", "width": 60},
        {"fieldname": "c_male",            "label": "Male C",        "fieldtype": "Int", "width": 60},
        {"fieldname": "i_male",            "label": "Male I",        "fieldtype": "Int", "width": 60},
        {"fieldname": "w_male",            "label": "Male W",        "fieldtype": "Int", "width": 60},
        {"fieldname": "a_female",          "label": "Female A",      "fieldtype": "Int", "width": 70},
        {"fieldname": "c_female",          "label": "Female C",      "fieldtype": "Int", "width": 70},
        {"fieldname": "i_female",          "label": "Female I",      "fieldtype": "Int", "width": 70},
        {"fieldname": "w_female",          "label": "Female W",      "fieldtype": "Int", "width": 70},
        {"fieldname": "foreign_male",      "label": "Foreign Male",  "fieldtype": "Int", "width": 90},
        {"fieldname": "foreign_female",    "label": "Foreign Female","fieldtype": "Int", "width": 100},
        {"fieldname": "total",             "label": "Total",         "fieldtype": "Int", "width": 80},
    ]

    return columns, data


# ---------------- helpers ----------------

def _init_zero_row(label: str) -> dict:
    row = {"occupational_level": label}
    for k in MALE_KEYS + FEMALE_KEYS:
        row[k] = 0
    row["foreign_male"] = 0
    row["foreign_female"] = 0
    row["total"] = 0
    return row

def _row_sum(row: dict) -> int:
    return sum((row.get(k, 0) or 0) for k in ALL_KEYS)

def _add_into(acc: dict, row: dict) -> None:
    for k in ALL_KEYS:
        acc[k] = (acc.get(k, 0) or 0) + (row.get(k, 0) or 0)

def _first_present(meta, fieldnames):
    for name in fieldnames:
        if meta.get_field(name):
            return name
    return None

def _first_present_check(meta, fieldnames):
    for name in fieldnames:
        f = meta.get_field(name)
        if f and f.fieldtype == "Check":
            return name
    return None

def _norm_dg(val):
    """Normalise DG/race value to our DG_MAP keys (African/Coloured/Indian/White)."""
    if not val:
        return None
    txt = str(val).strip().lower()
    if txt in ("african", "black", "a"):
        return "a"
    if txt in ("coloured", "colored", "c"):
        return "c"
    if txt in ("indian", "i"):
        return "i"
    if txt in ("white", "w"):
        return "w"
    return None


# ---------------- XLSX download (optional; unchanged) ----------------

@frappe.whitelist()
def download_eea2_xlsx(company, country, disabled=0, branch=None):
    columns, data = execute({
        "company": company,
        "country": country,
        "disabled": frappe.utils.cint(disabled),
        "branch": (branch or "").strip(),
    })

    xlsx_data = []
    headers = [col["label"] for col in columns]
    xlsx_data.append(headers)

    for row in data:
        xlsx_data.append([row.get(col["fieldname"], "") for col in columns])

    xlsx_file = make_xlsx(xlsx_data, "EEA2_Report")
    frappe.response["type"] = "binary"
    frappe.response["filename"] = "EEA2_Employment_Equity_Report.xlsx"
    frappe.response["filecontent"] = xlsx_file.getvalue()
    frappe.response["content_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"