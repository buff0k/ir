# Copyright (c) 2025
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_months, nowdate

EE_CHILD = "Employment Equity Table"
SECTOR_CHILD = "Employment Equity Sectoral Target Table"

# In your HRMS, Occupational Level on Employee is stored in this custom field:
EMP_OCC_LEVEL_FIELD = "custom_occupational_level"

GROUP_FIELDS = [
    "african_male", "coloured_male", "indian_male", "white_male",
    "african_female", "coloured_female", "indian_female", "white_female",
    "foreign_male", "foreign_female",
]

SECTOR_FIELDS = [
    "top_management_male",
    "top_management_female",
    "top_management_total",
    "senior_management_male",
    "senior_management_female",
    "senior_management_total",
    "mid_management_male",
    "mid_management_female",
    "mid_management_total",
    "skilled_male",
    "skilled_female",
    "skilled_total",
    "disability_only",
]


class EmploymentEquityTarget(Document):
    def before_save(self):
        """Server-side safety:
        - Ensure totals are correct even if client JS didn't run.
        - Ensure a row exists for each Occupational Level.
        - If a sectoral_target is selected but sector/aux tables are empty, initialize them.
        """
        # Ensure a row exists for every Occupational Level
        level_names = [x.name for x in frappe.get_all("Occupational Level")]
        existing_levels = {row.occupational_level for row in (self.employment_equity_table or [])}

        for lvl in level_names:
            if lvl not in existing_levels:
                row = self.append("employment_equity_table", {})
                row.occupational_level = lvl
                for f in GROUP_FIELDS:
                    setattr(row, f, 0)
                row.total = 0

        # Recompute totals
        for row in (self.employment_equity_table or []):
            row.total = sum(int(getattr(row, f) or 0) for f in GROUP_FIELDS)

        # Populate base sectoral metrics from master if selected and empty
        if getattr(self, "sectoral_target", None) and not (self.sectoral_target_table or []):
            master = frappe.get_doc("Employment Equity Sectoral Targets", self.sectoral_target)
            child = self.append("sectoral_target_table", {})
            for f in SECTOR_FIELDS:
                setattr(child, f, float(getattr(master, f) or 0.0))

        # Ensure auxiliary sectoral tables exist (one row each)
        if getattr(self, "sectoral_target", None):
            if not (self.previous_numerical_target or []):
                x = self.append("previous_numerical_target", {})
                for f in SECTOR_FIELDS:
                    setattr(x, f, 0.0)
            if not (self.attrition_per_category or []):
                y = self.append("attrition_per_category", {})
                for f in SECTOR_FIELDS:
                    setattr(y, f, 0.0)


@frappe.whitelist()
def compute_suggested_targets(docname: str):
    """Placeholder for future EAP-based logic."""
    if not docname:
        frappe.throw("Missing docname.")
    doc = frappe.get_doc("Employment Equity Target", docname)
    return f"Placeholder OK for {doc.name}. Implement EAP-based logic server-side next."


# ----------------------------- ATTRITION ----------------------------- #

def _norm_gender(val: str) -> str:
    """Normalize various gender strings into 'male'/'female'/''."""
    if not val:
        return ""
    v = str(val).strip().lower()
    if v in {"male", "m"}:
        return "male"
    if v in {"female", "f"}:
        return "female"
    return ""  # treat anything else as unspecified/other (excluded from splits and totals)


@frappe.whitelist()
def calculate_attrition(docname: str):
    """
    Compute attrition rates for the 12 months prior to `start_date` (or `target_date`),
    per Paterson band, split by Male, Female, and Total.

    Mapping (hard-coded):
      F -> top_management_{male,female,total}
      E -> senior_management_{male,female,total}
      D -> mid_management_{male,female,total}
      C -> skilled_{male,female,total}

    BUSINESS RULES (FIXED):
    - Numerator: # of employees with status='Left' and relieving_date within (start_date-12M, start_date].
    - Denominator: HEADCOUNT AT BEGINNING OF WINDOW (i.e., at start_date-12M), per band & gender.
      This matches expectations like "2 leavers out of 6 = 33.33%".
    - 'Male' includes ALL males; 'Female' includes ALL females; 'Other/unspecified' excluded.
    - 'Total' uses the same numerators and denominators as the male/female splits:
        total_rate = (male_left + female_left) / (male_denom + female_denom)
      ensuring the total can’t contradict the splits.
    """
    if not docname:
        frappe.throw("Missing docname.")

    doc = frappe.get_doc("Employment Equity Target", docname)
    company = doc.company

    # Use start_date if present; fall back to target_date; else today
    end_dt = getdate(doc.get("start_date") or doc.get("target_date") or nowdate())
    start_window = add_months(end_dt, -12)

    # Map Occupational Level -> Paterson band (uppercase)
    levels = frappe.get_all("Occupational Level", fields=["name", "paterson_band"], limit_page_length=0)
    level_to_band = {l.name: (l.paterson_band or "").upper() for l in levels}

    # -------------------- Numerators: leavers in window --------------------
    leavers = frappe.get_all(
        "Employee",
        filters=[
            ["company", "=", company],
            ["status", "=", "Left"],
            ["relieving_date", ">=", start_window],
            ["relieving_date", "<=", end_dt],
        ],
        fields=["name", "gender", "relieving_date", EMP_OCC_LEVEL_FIELD],
        limit_page_length=0,
    )

    left = {
        "F": {"male": 0, "female": 0},
        "E": {"male": 0, "female": 0},
        "D": {"male": 0, "female": 0},
        "C": {"male": 0, "female": 0},
    }

    for emp in leavers:
        band = level_to_band.get(emp.get(EMP_OCC_LEVEL_FIELD))
        if band not in left:
            continue
        g = _norm_gender(emp.get("gender"))
        if g:
            left[band][g] += 1

    # -------------------- Denominators: headcount at window START --------------------
    # Headcount at T = joined on/before T AND (no relieving_date OR relieving_date > T)
    # Fetch superset once (joined on/before end_dt), then test membership at start_window.
    employees = frappe.get_all(
        "Employee",
        filters=[
            ["company", "=", company],
            ["date_of_joining", "<=", end_dt],
        ],
        fields=["name", "gender", "date_of_joining", "relieving_date", EMP_OCC_LEVEL_FIELD],
        limit_page_length=0,
    )

    denom_start = {
        "F": {"male": 0, "female": 0},
        "E": {"male": 0, "female": 0},
        "D": {"male": 0, "female": 0},
        "C": {"male": 0, "female": 0},
    }

    for emp in employees:
        band = level_to_band.get(emp.get(EMP_OCC_LEVEL_FIELD))
        if band not in denom_start:
            continue

        doj = getdate(emp.get("date_of_joining")) if emp.get("date_of_joining") else None
        rel = getdate(emp.get("relieving_date")) if emp.get("relieving_date") else None

        # Present at window start?
        present_at_start = (doj is not None and doj <= start_window) and (rel is None or rel > start_window)
        if not present_at_start:
            continue

        g = _norm_gender(emp.get("gender"))
        if g:
            denom_start[band][g] += 1

    # -------------------- Rates --------------------
    def rate(n: int, d: int) -> float:
        return round((n / d) * 100.0, 2) if d else 0.0

    rates = {}
    debug = {}
    for band in ("F", "E", "D", "C"):
        m_num, f_num = left[band]["male"], left[band]["female"]
        m_den, f_den = denom_start[band]["male"], denom_start[band]["female"]

        m_rate = rate(m_num, m_den)
        f_rate = rate(f_num, f_den)
        t_rate = rate(m_num + f_num, m_den + f_den)

        rates[band] = {"male": m_rate, "female": f_rate, "total": t_rate}
        debug[band] = {
            "left": {"male": m_num, "female": f_num, "total": m_num + f_num},
            "headcount_start": {"male": m_den, "female": f_den, "total": m_den + f_den},
            "rates": {"male": m_rate, "female": f_rate, "total": t_rate},
        }

    # Ensure child row exists
    if not (doc.attrition_per_category or []):
        row = doc.append("attrition_per_category", {})
        for f in SECTOR_FIELDS:
            setattr(row, f, 0.0)

    row = doc.attrition_per_category[0]

    # Write rates into mapped fields (F->top_management, E->senior_management, D->mid_management, C->skilled)
    row.top_management_male = rates["F"]["male"]
    row.top_management_female = rates["F"]["female"]
    row.top_management_total = rates["F"]["total"]

    row.senior_management_male = rates["E"]["male"]
    row.senior_management_female = rates["E"]["female"]
    row.senior_management_total = rates["E"]["total"]

    row.mid_management_male = rates["D"]["male"]
    row.mid_management_female = rates["D"]["female"]
    row.mid_management_total = rates["D"]["total"]

    row.skilled_male = rates["C"]["male"]
    row.skilled_female = rates["C"]["female"]
    row.skilled_total = rates["C"]["total"]

    # Save and return debug so you can validate inputs/denominators from the UI if needed
    doc.save(ignore_permissions=True)

    return {
        "window_start": str(start_window),
        "window_end": str(end_dt),
        "counts": {"left": left, "headcount_start": denom_start},
        "rates": rates,
        "message": "Attrition calculated and saved.",
        "debug": debug,
    }
