# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Shared backend for the Branch Staffing Dashboard (page: ir-branch-staffing)
and its underlying Branch Staffing Overview report - both call these exact
functions so the two never drift apart on what a "current" Organogram, a
"missing" Organogram, or a headcount actually means.

Built on top of Site Organogram's own get_designation_headcounts() - not a
new data model. HRMS's native Staffing Plan doesn't fit here: it's scoped to
Company with a hard one-active-plan-per-Designation-per-Company constraint,
and Branch has no Company field at all (a single Branch routinely has real
Employees from several different Companies at once - a shared-site group
structure, confirmed against live data) - a per-Branch plan would collide
with itself the moment two Branches under the same Company needed the same
Designation.

Company filtering convention (resolved with the user): a Company filter only
narrows which *filled* slots count as filled - a slot occupied by a
different Company's Employee, or genuinely empty, both fall to "vacant" from
the selected Company's own point of view. `total` is never affected by it.
See get_designation_headcounts()'s own docstring in site_organogram.py for
where that's actually implemented.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_months, getdate, today

from ir.industrial_relations.doctype.site_organogram.site_organogram import get_designation_headcounts


def _clean_branch_list(branches) -> list[str]:
    """Normalise whatever the Branch multi-select filter hands us (a JSON
    string from a Query Report / Page filter, a plain list, or nothing) into
    a clean list of Branch names."""
    if not branches:
        return []

    if isinstance(branches, str):
        import json

        try:
            branches = json.loads(branches)
        except ValueError:
            branches = [b.strip() for b in branches.split(",") if b.strip()]

    if isinstance(branches, (list, tuple, set)):
        return [b for b in branches if b]

    return [branches]


@frappe.whitelist()
def get_scope_branches(branches=None) -> list[str]:
    """The Branch filter's value, or every Branch if it's empty - "no Branch
    selected" means "show everything", not "show nothing"."""
    cleaned = _clean_branch_list(branches)
    if cleaned:
        return cleaned

    return frappe.get_all("Branch", pluck="name", order_by="name asc")


def _valid_organogram_on(branch: str, on_date, candidates: list[dict] | None = None) -> dict | None:
    """The one Site Organogram valid for `branch` on `on_date`: submitted,
    effective_from <= on_date, and effective_until is unset or >= on_date.
    If more than one somehow qualifies (shouldn't happen in practice), the
    latest effective_from wins. `candidates` lets callers that already have
    every submitted Organogram for a set of branches in memory (get_trend_data)
    avoid re-querying per branch per date; omit it to query fresh."""
    on_date = getdate(on_date)

    if candidates is None:
        candidates = frappe.get_all(
            "Site Organogram",
            filters={"branch": branch, "docstatus": 1},
            fields=["name", "branch", "effective_from", "effective_until"],
        )

    best = None
    for row in candidates:
        if row.branch != branch:
            continue
        effective_from = getdate(row.effective_from)
        if effective_from > on_date:
            continue
        effective_until = getdate(row.effective_until) if row.effective_until else None
        if effective_until and effective_until < on_date:
            continue
        if best is None or effective_from > getdate(best.effective_from):
            best = row

    return best


@frappe.whitelist()
def get_current_valid_organogram(branch: str) -> str | None:
    """The name of the one Site Organogram currently valid for `branch`, or
    None if there isn't one."""
    row = _valid_organogram_on(branch, today())
    return row.name if row else None


@frappe.whitelist()
def get_missing_organograms(branches=None) -> list[str]:
    """Scope branches (see get_scope_branches()) with no currently valid Site
    Organogram - deliberately not Company-filtered: a missing Organogram is a
    structural gap in coverage, independent of which Company's Employees
    happen to be at that Branch."""
    scope = get_scope_branches(branches)
    return [branch for branch in scope if not get_current_valid_organogram(branch)]


@frappe.whitelist()
def get_current_snapshot(company=None, branches=None) -> list[dict]:
    """Per-Branch, per-Designation headcount rows for every scope branch's
    currently valid Organogram. Returns a flat list, one row per
    (branch, designation): {branch, designation, total, filled, vacant}."""
    scope = get_scope_branches(branches)
    rows = []

    for branch in scope:
        organogram_name = get_current_valid_organogram(branch)
        if not organogram_name:
            continue

        doc = frappe.get_doc("Site Organogram", organogram_name)
        headcounts = get_designation_headcounts(doc, company=company or None)

        for designation, counts in headcounts.items():
            rows.append({
                "branch": branch,
                "designation": designation,
                "total": counts["total"],
                "filled": counts["filled"],
                "vacant": counts["vacant"],
            })

    return rows


@frappe.whitelist()
def get_trend_data(company=None, branches=None, from_date=None, to_date=None) -> dict:
    """Structure-over-time trend: one data point per distinct effective_from
    date (within [from_date, to_date]) across every submitted Site Organogram
    touching any scope branch - i.e. the trend moves exactly when the org
    structure itself changed, not on some arbitrary fixed interval. At each
    point, every scope branch contributes whichever Organogram was valid for
    it on that date (not necessarily the one whose effective_from triggered
    the point - a change on Branch A doesn't require Branch B to have also
    changed that day). Returns the same {"labels", "datasets"} shape
    disciplinary_action_summary.py's get_chart_data() already produces, so a
    Script Report's own `chart` return and a Page's frappe.Chart call can
    both consume it identically.

    Sparse today by design (only a handful of Organograms exist yet) - this
    naturally densifies as more get created/amended over time, rather than
    inventing a separate snapshot mechanism that could drift from what
    Organograms actually say was true.
    """
    scope = get_scope_branches(branches)
    to_date = getdate(to_date) if to_date else getdate(today())
    from_date = getdate(from_date) if from_date else add_months(to_date, -6)

    if not scope:
        return {"data": {"labels": [], "datasets": [{"name": "Filled", "values": []}, {"name": "Vacant", "values": []}]}, "type": "line", "height": 300}

    candidates = frappe.get_all(
        "Site Organogram",
        filters={"branch": ["in", scope], "docstatus": 1},
        fields=["name", "branch", "effective_from", "effective_until"],
    )

    # Every distinct effective_from within range is a point on the x-axis -
    # this is what makes the trend move exactly when structure changed.
    change_points = sorted({
        getdate(row.effective_from)
        for row in candidates
        if from_date <= getdate(row.effective_from) <= to_date
    })

    headcount_cache: dict[str, dict] = {}

    def headcounts_for(organogram_name: str) -> dict:
        if organogram_name not in headcount_cache:
            doc = frappe.get_doc("Site Organogram", organogram_name)
            headcount_cache[organogram_name] = get_designation_headcounts(doc, company=company or None)
        return headcount_cache[organogram_name]

    labels = []
    filled_values = []
    vacant_values = []

    for point in change_points:
        total_filled = 0
        total_vacant = 0

        for branch in scope:
            row = _valid_organogram_on(branch, point, candidates=candidates)
            if not row:
                continue
            for counts in headcounts_for(row.name).values():
                total_filled += counts["filled"]
                total_vacant += counts["vacant"]

        labels.append(str(point))
        filled_values.append(total_filled)
        vacant_values.append(total_vacant)

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": "Filled", "values": filled_values},
                {"name": "Vacant", "values": vacant_values},
            ],
        },
        "type": "line",
        "height": 300,
        "colors": ["#198754", "#b40000"],
    }
