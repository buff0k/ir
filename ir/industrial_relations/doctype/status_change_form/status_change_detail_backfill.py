# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Pure, DB-free logic for turning a Status Change Form's legacy
current_*/new_* fields into the Status Change Detail rows that represent
its actual changes - shared by the backfill patch
(ir.patches.backfill_status_change_detail_from_legacy_fields) and its tests.
Kept separate from status_change_form.py the same way retrenchment_process's
pure costing math lives in retrenchment_costing.py.
"""

# R1000 is the highest Hourly Rate ever used on this site, so a Status
# Change Form's "Hourly / Basic Rate" value above that can only logically
# be a Basic Salary, never an hourly rate - the user's own cutoff rule.
RATE_CUTOFF = 1000

HOURLY_RATE_COMPONENT = "Hourly Earnings"
BASIC_SALARY_COMPONENT = "Basic Salary"

# Maps each of Status Change Form's simple current_X/new_X allowance field
# pairs to the real Salary Component name confirmed by auditing this site's
# actual tabSalary Component data (there is no "Travelling Allowance"
# component - the real one is "Transport Allowance").
SIMPLE_ALLOWANCE_COMPONENTS = {
    "travel": "Transport Allowance",
    "housing": "Housing Allowance",
    "safety": "Safety Bonus",
    "shift": "Shift Allowance",
    "phone": "Cellphone Allowance",
    "opencast": "Opencast Allowance",
}


def classify_rate_component(amount):
    return BASIC_SALARY_COMPONENT if float(amount or 0) > RATE_CUTOFF else HOURLY_RATE_COMPONENT


def _rate_rows(current_rate, new_rate):
    """The Hourly/Basic Rate field is the hard one: its old and new values
    can land on different sides of the cutoff (e.g. an employee moving from
    an hourly-paid role to a salaried one), which is a genuine component
    changeover, not just an amount change on one component - so that case
    produces two rows: the old component winding down to 0, the new one
    starting from 0."""
    current_rate = float(current_rate or 0)
    new_rate = float(new_rate or 0)
    if current_rate == new_rate:
        return []

    old_component = classify_rate_component(current_rate)
    new_component = classify_rate_component(new_rate)

    if old_component == new_component:
        return [
            {
                "change_type": "Salary Component",
                "salary_component": old_component,
                "old_amount": current_rate,
                "new_amount": new_rate,
            }
        ]

    return [
        {
            "change_type": "Salary Component",
            "salary_component": old_component,
            "old_amount": current_rate,
            "new_amount": 0,
        },
        {
            "change_type": "Salary Component",
            "salary_component": new_component,
            "old_amount": 0,
            "new_amount": new_rate,
        },
    ]


def _is_zero_value_row(row):
    """A Salary Component row where both old and new amounts are 0 carries
    no information - most commonly the rate-cutoff crossover case where one
    side of a 0 -> nonzero (or nonzero -> 0) rate change gets classified
    into a component that never actually held a value (e.g. current_rate=0
    classifies as Hourly Earnings by the cutoff rule, but a literal 0 isn't
    really an hourly rate that existed - there's nothing to record for it).
    Omitted rather than kept as a no-op row."""
    return row["change_type"] == "Salary Component" and not row.get("old_amount") and not row.get("new_amount")


def _allowance_row(component, old_amount, new_amount):
    old_amount = float(old_amount or 0)
    new_amount = float(new_amount or 0)
    if old_amount == new_amount:
        return None
    return {
        "change_type": "Salary Component",
        "salary_component": component,
        "old_amount": old_amount,
        "new_amount": new_amount,
    }


def build_status_change_detail_rows(source):
    """`source` is a dict (or frappe._dict/doc) with Status Change Form's
    legacy current_*/new_* fields. Returns the list of Status Change Detail
    rows (as plain dicts, matching that doctype's own fieldnames) that
    represent what actually changed on this record.

    A field pair is skipped entirely whenever its old and new values are
    identical - including the common null-vs-null / blank-vs-blank case for
    a field that simply didn't exist yet when an older record was created
    (e.g. Branch, pre Site Transfer Form merge) - so historic records only
    ever get rows for the fields that genuinely existed and changed on
    them, never fabricated rows for fields that were blank because they
    predate that field's addition to the form.
    """
    rows = []

    if (source.get("current_designation") or None) != (source.get("new_designation") or None):
        rows.append(
            {
                "change_type": "Designation",
                "old_value": source.get("current_designation"),
                "new_value": source.get("new_designation"),
            }
        )

    if (source.get("current_branch") or None) != (source.get("new_branch") or None):
        rows.append(
            {
                "change_type": "Branch",
                "old_value": source.get("current_branch"),
                "new_value": source.get("new_branch"),
            }
        )

    if (source.get("current_conditions") or None) != (source.get("new_conditions") or None):
        rows.append(
            {
                "change_type": "Conditions of Employment",
                "old_condition": source.get("current_conditions"),
                "new_condition": source.get("new_conditions"),
            }
        )

    rows.extend(_rate_rows(source.get("current_rate"), source.get("new_rate")))

    for key, component in SIMPLE_ALLOWANCE_COMPONENTS.items():
        row = _allowance_row(component, source.get(f"current_{key}"), source.get(f"new_{key}"))
        if row:
            rows.append(row)

    return [row for row in rows if not _is_zero_value_row(row)]
