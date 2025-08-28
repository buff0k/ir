# Copyright (c) 2025
# For license information, please see license.txt

import math
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, add_months, add_days, nowdate

EE_CHILD = "Employment Equity Table"
SECTOR_CHILD = "Employment Equity Sectoral Target Table"

# In your HRMS, Occupational Level on Employee is stored in this custom field:
EMP_OCC_LEVEL_FIELD = "custom_occupational_level"

GROUP_FIELDS = [
    "african_male", "coloured_male", "indian_male", "white_male",
    "african_female", "coloured_female", "indian_female", "white_female",
    "foreign_male", "foreign_female",
]

MALE_KEYS = ["african_male", "coloured_male", "indian_male", "white_male", "foreign_male"]
FEMALE_KEYS = ["african_female", "coloured_female", "indian_female", "white_female", "foreign_female"]

MALE_DES_KEYS = ["african_male", "coloured_male", "indian_male"]  # white_male is non-designated
FEMALE_ALL_KEYS = ["african_female", "coloured_female", "indian_female", "white_female"]  # all females designated

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

# ----------------------------- Document ----------------------------- #

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

# ----------------------------- Helpers ----------------------------- #

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

def _int(x) -> int:
    try:
        return max(0, int(round(float(x or 0))))
    except Exception:
        return 0

def _sum_fields(row, keys) -> int:
    return sum(_int(getattr(row, k, 0)) for k in keys)

def _largest_remainder_distribution(total_to_allocate: int, weights: list[int]) -> list[int]:
    """Distribute total_to_allocate across len(weights) slots using largest remainder method.
    If all weights are zero, distribute as evenly as possible."""
    n = len(weights)
    if n == 0 or total_to_allocate <= 0:
        return [0] * n
    if all(w <= 0 for w in weights):
        base = total_to_allocate // n
        rem = total_to_allocate - base * n
        out = [base] * n
        for i in range(rem):
            out[i % n] += 1
        return out

    s = float(sum(weights))
    quotas = [total_to_allocate * (w / s) for w in weights]
    floors = [int(math.floor(q)) for q in quotas]
    out = floors[:]
    remainder = total_to_allocate - sum(floors)
    # Indices with largest fractional parts first
    frac = sorted([(i, quotas[i] - floors[i]) for i in range(n)], key=lambda x: (-x[1], x[0]))
    for idx, _f in frac[:remainder]:
        out[idx] += 1
    return out

def _band_map_by_level() -> dict[str, str]:
    """Return dict: Occupational Level name -> Paterson band (upper)."""
    levels = frappe.get_all("Occupational Level", fields=["name", "paterson_band"], limit_page_length=0)
    return {l.name: (l.paterson_band or "").upper() for l in levels}

def _gazette_pct_by_band(doc) -> dict[str, dict[str, float]]:
    """From sectoral_target_table (single row), return per-band % dicts."""
    if not (doc.sectoral_target_table or []):
        frappe.throw("Sectoral target not loaded on this document.")
    row = doc.sectoral_target_table[0]
    return {
        "F": {
            "male": float(getattr(row, "top_management_male") or 0.0),
            "female": float(getattr(row, "top_management_female") or 0.0),
            "total": float(getattr(row, "top_management_total") or 0.0),
        },
        "E": {
            "male": float(getattr(row, "senior_management_male") or 0.0),
            "female": float(getattr(row, "senior_management_female") or 0.0),
            "total": float(getattr(row, "senior_management_total") or 0.0),
        },
        "D": {
            "male": float(getattr(row, "mid_management_male") or 0.0),
            "female": float(getattr(row, "mid_management_female") or 0.0),
            "total": float(getattr(row, "mid_management_total") or 0.0),
        },
        "C": {
            "male": float(getattr(row, "skilled_male") or 0.0),
            "female": float(getattr(row, "skilled_female") or 0.0),
            "total": float(getattr(row, "skilled_total") or 0.0),
        },
    }

def _attrition_rates_from_doc(base_doc) -> dict[str, dict[str, float]]:
    """Read attrition_per_category rates from the FIRST doc in the series.
    Returns per-band {'male': %, 'female': %}. Missing values default to 0."""
    row = (base_doc.attrition_per_category or [None])[0]
    if not row:
        # default zeros
        return {b: {"male": 0.0, "female": 0.0} for b in ("F", "E", "D", "C")}
    return {
        "F": {"male": float(row.top_management_male or 0.0), "female": float(row.top_management_female or 0.0)},
        "E": {"male": float(row.senior_management_male or 0.0), "female": float(row.senior_management_female or 0.0)},
        "D": {"male": float(row.mid_management_male or 0.0), "female": float(row.mid_management_female or 0.0)},
        "C": {"male": float(row.skilled_male or 0.0), "female": float(row.skilled_female or 0.0)},
    }

def _apply_attrition(value: int, pct_rate: float) -> int:
    """Reduce value by pct_rate% and round to nearest int (non-negative)."""
    v = int(round(float(value or 0) * (1.0 - (float(pct_rate or 0.0) / 100.0))))
    return max(0, v)

def _clone_row_skeleton(level_name: str) -> dict:
    d = {"occupational_level": level_name}
    for f in GROUP_FIELDS:
        d[f] = 0
    d["total"] = 0
    return d

def _row_total(row_dict: dict) -> int:
    return sum(int(row_dict[k]) for k in GROUP_FIELDS)

# ----------------------------- API: Calculate Attrition ----------------------------- #

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
    """
    if not docname:
        frappe.throw("Missing docname.")

    doc = frappe.get_doc("Employment Equity Target", docname)
    company = doc.company

    # Use start_date if present; fall back to target_date; else today
    end_dt = getdate(doc.get("start_date") or doc.get("target_date") or nowdate())
    start_window = add_months(end_dt, -12)

    # Map Occupational Level -> Paterson band (uppercase)
    level_to_band = _band_map_by_level()

    # Numerators: leavers in window
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

    left = {b: {"male": 0, "female": 0} for b in ("F", "E", "D", "C")}
    for emp in leavers:
        band = level_to_band.get(emp.get(EMP_OCC_LEVEL_FIELD))
        if band not in left:
            continue
        g = _norm_gender(emp.get("gender"))
        if g:
            left[band][g] += 1

    # Denominators: headcount at window START
    employees = frappe.get_all(
        "Employee",
        filters=[["company", "=", company], ["date_of_joining", "<=", end_dt]],
        fields=["name", "gender", "date_of_joining", "relieving_date", EMP_OCC_LEVEL_FIELD],
        limit_page_length=0,
    )
    denom_start = {b: {"male": 0, "female": 0} for b in ("F", "E", "D", "C")}
    for emp in employees:
        band = level_to_band.get(emp.get(EMP_OCC_LEVEL_FIELD))
        if band not in denom_start:
            continue
        doj = getdate(emp.get("date_of_joining")) if emp.get("date_of_joining") else None
        rel = getdate(emp.get("relieving_date")) if emp.get("relieving_date") else None
        present_at_start = (doj is not None and doj <= start_window) and (rel is None or rel > start_window)
        if not present_at_start:
            continue
        g = _norm_gender(emp.get("gender"))
        if g:
            denom_start[band][g] += 1

    def rate(n: int, d: int) -> float:
        return round((n / d) * 100.0, 2) if d else 0.0

    rates = {}
    for band in ("F", "E", "D", "C"):
        m_num, f_num = left[band]["male"], left[band]["female"]
        m_den, f_den = denom_start[band]["male"], denom_start[band]["female"]
        m_rate = rate(m_num, m_den)
        f_rate = rate(f_num, f_den)
        t_rate = rate(m_num + f_num, m_den + f_den)
        rates[band] = {"male": m_rate, "female": f_rate, "total": t_rate}

    # Ensure child row exists
    if not (doc.attrition_per_category or []):
        row = doc.append("attrition_per_category", {})
        for f in SECTOR_FIELDS:
            setattr(row, f, 0.0)
    row = doc.attrition_per_category[0]

    # Write rates into mapped fields
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

    doc.save(ignore_permissions=True)
    return {
        "window_start": str(start_window),
        "window_end": str(end_dt),
        "rates": rates,
        "message": "Attrition calculated and saved.",
    }

# ----------------------------- API: Compute Suggested Targets ----------------------------- #

@frappe.whitelist()
def compute_suggested_targets(docname: str):
    """
    Generate a yearly series of Employment Equity Target documents until the plan horizon,
    applying attrition (from the FIRST document) and backfilling hires to move toward the
    Gazette-designated percentages per Paterson band.

    Rules:
    1) Validation: target_date == (start_date + plan_duration years - 1 day)  <-- inclusive-year end.
    2) Create (plan_duration - 1) new docs (so total docs == plan_duration).
       - target_date, company, sectoral_target: same as the ORIGINAL
       - previous_target: previous document in the chain
       - plan_duration: decrement by 1 each year
       - start_date: previous start_date + 12 months (the day after last year's inclusive end)
    3) For each new document, compute employment_equity_table by:
       - Reducing each group by the gender-specific attrition % for that band (from FIRST doc).
       - Rehiring to keep the band total constant (same as previous year's total).
         * Female hires first to approach Gazette female designated % (all women count as designated).
           Distribute across female groups proportionally to current post-attrition female composition
           (even split if zero).
         * Then male designated hires (A/C/I) to approach Gazette male designated %.
           Distribute proportionally to current A/C/I male composition (even split if zero).
         * Any remaining openings go to white_male.
       - Foreign nationals are not specifically targeted in rehires (they only change via attrition).
    4) Respect Naming Rule by letting Frappe name the document.

    Returns: list of created document names in order.
    """
    if not docname:
        frappe.throw("Missing docname.")

    base_doc = frappe.get_doc("Employment Equity Target", docname)

    # --- 1) Validate horizon dates (INCLUSIVE YEAR: minus one day) ---
    plan_duration = int(base_doc.get("plan_duration") or 0)
    if plan_duration <= 0:
        frappe.throw("Plan Duration must be 1, 2, 3, 4 or 5.")

    start_dt = getdate(base_doc.get("start_date") or nowdate())
    expected_target_inclusive = add_days(add_months(start_dt, plan_duration * 12), -1)
    actual_target = getdate(base_doc.get("target_date") or nowdate())
    if expected_target_inclusive != actual_target:
        frappe.throw(
            f"Target Date mismatch: expected {expected_target_inclusive} from start_date + {plan_duration} "
            f"year(s) inclusive, but found {actual_target}."
        )

    # Nothing to do if plan_duration == 1 (already year 1)
    if plan_duration == 1:
        return {"created": [], "message": "Plan duration is 1; no additional documents created."}

    # --- 2) Prepare common data ---
    band_of_level = _band_map_by_level()
    gazette = _gazette_pct_by_band(base_doc)  # % per band {'male','female','total'}
    attr_rates = _attrition_rates_from_doc(base_doc)  # % per band {'male','female'}

    # Helper: compute next-year row from previous row counts for a given band
    def next_row_from_previous(prev_row_dict: dict, band: str) -> dict:
        # Start with attrition-applied counts (gender-specific)
        out = {k: 0 for k in GROUP_FIELDS}
        for k in MALE_KEYS:
            out[k] = _apply_attrition(prev_row_dict.get(k, 0), attr_rates.get(band, {}).get("male", 0.0))
        for k in FEMALE_KEYS:
            out[k] = _apply_attrition(prev_row_dict.get(k, 0), attr_rates.get(band, {}).get("female", 0.0))

        # Totals and openings (keep total constant to previous year's total)
        total_prev = sum(int(prev_row_dict.get(k, 0)) for k in GROUP_FIELDS)
        total_after_attr = sum(int(out[k]) for k in GROUP_FIELDS)
        openings = max(0, total_prev - total_after_attr)

        if openings == 0:
            out["total"] = total_after_attr
            return out

        # Gazette targets for this band
        g_male = float(gazette.get(band, {}).get("male", 0.0))
        g_fem = float(gazette.get(band, {}).get("female", 0.0))

        # Desired designated counts (based on constant total = total_prev)
        target_female_total = int(round(g_fem * total_prev / 100.0))
        target_male_designated = int(round(g_male * total_prev / 100.0))

        # Current after-attrition
        cur_female_total = sum(out[k] for k in FEMALE_ALL_KEYS)  # all females designated
        cur_male_designated = sum(out[k] for k in MALE_DES_KEYS)

        # 1) Hire females first (all female keys)
        need_female = max(0, target_female_total - cur_female_total)
        hire_female = min(openings, need_female)

        if hire_female > 0:
            weights = [max(1, out[k]) for k in FEMALE_ALL_KEYS]  # proportional to current; if zeros, even
            add = _largest_remainder_distribution(hire_female, weights)
            for i, k in enumerate(FEMALE_ALL_KEYS):
                out[k] += add[i]
            openings -= hire_female
            cur_female_total += hire_female

        # 2) Hire male designated (A/C/I)
        need_male_des = max(0, target_male_designated - cur_male_designated)
        hire_male_des = min(openings, need_male_des)

        if hire_male_des > 0:
            weights = [max(1, out[k]) for k in MALE_DES_KEYS]  # proportional; if zeros, even
            add = _largest_remainder_distribution(hire_male_des, weights)
            for i, k in enumerate(MALE_DES_KEYS):
                out[k] += add[i]
            openings -= hire_male_des
            cur_male_designated += hire_male_des

        # 3) Any remaining openings -> white_male
        if openings > 0:
            out["white_male"] += openings
            openings = 0

        out["total"] = sum(out[k] for k in GROUP_FIELDS)
        return out

    def prev_rows_by_level(doc_with_rows) -> dict[str, dict]:
        """Return a dict of level -> row-counts for faster access."""
        result = {}
        for r in (doc_with_rows.employment_equity_table or []):
            result[r.occupational_level] = {k: _int(getattr(r, k, 0)) for k in GROUP_FIELDS}
        return result

    # Base rows come from the executing document
    prev_rows_dict = prev_rows_by_level(base_doc)

    created_names = []
    prev_doc = base_doc

    # --- 3) Create yearly documents ---
    for step in range(1, plan_duration):  # create plan_duration-1 new docs
        newdoc = frappe.new_doc("Employment Equity Target")
        newdoc.company = base_doc.company
        newdoc.sectoral_target = base_doc.sectoral_target
        newdoc.target_date = base_doc.target_date  # final horizon stays the same for all years
        newdoc.previous_target = prev_doc.name
        newdoc.plan_duration = max(1, plan_duration - step)
        # Next period starts one year after the base start (inclusive-year means the day after previous end)
        newdoc.start_date = getdate(add_months(start_dt, step * 12))

        # Build employment_equity_table from prev_rows_dict
        newdoc.set("employment_equity_table", [])
        for level_name, prev_counts in prev_rows_dict.items():
            band = band_of_level.get(level_name, "")
            row_dict = _clone_row_skeleton(level_name)

            if band in ("F", "E", "D", "C"):
                nxt = next_row_from_previous(prev_counts, band)
                for k in GROUP_FIELDS:
                    row_dict[k] = _int(nxt.get(k, 0))
                row_dict["total"] = _row_total(row_dict)
            else:
                # Bands without Gazette/attrition mapping: carry over previous counts as-is
                for k in GROUP_FIELDS:
                    row_dict[k] = _int(prev_counts.get(k, 0))
                row_dict["total"] = _row_total(row_dict)

            newdoc.append("employment_equity_table", row_dict)

        # Insert (before_save will ensure sector tables & totals)
        newdoc.insert(ignore_permissions=True)
        created_names.append(newdoc.name)

        # Prepare for next iteration: base the next year on THIS newly created doc's counts
        prev_doc = newdoc
        prev_rows_dict = prev_rows_by_level(newdoc)

    return {"created": created_names, "message": f"Created {len(created_names)} target document(s)."}
