# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class SiteOrganogram(Document):
    pass


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = frappe.parse_json(value)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    return []

def _ensure_row_order(doc):
    """
    Ensure each unique row_key within a (shift, group) gets a stable, sequential row_order.
    - Doesn’t change your actual mapping rows, just normalizes the stored row_order values.
    - Defensive: if shift_mappings is missing/empty, does nothing.
    """

    rows = getattr(doc, "shift_mappings", None) or []
    if not rows:
        return

    # Group by (shift, group)
    buckets = {}
    for r in rows:
        shift = (getattr(r, "shift", None) or "").strip()
        group = (getattr(r, "group", None) or "").strip()

        # row_key should already be present from your UI; if not, fall back gracefully
        row_key = (getattr(r, "row_key", None) or "").strip()
        if not row_key:
            asset = (getattr(r, "asset", None) or "").strip()
            employee = (getattr(r, "employee", None) or "").strip()
            if asset:
                row_key = f"ASSET::{asset}"
            elif employee:
                row_key = f"EMP::{employee}"
            else:
                # last-resort, stable enough for saving
                row_key = f"IDX::{getattr(r, 'idx', 0)}"

        buckets.setdefault((shift, group), []).append((row_key, r))

    # For each bucket, assign row_order based on the first time we see each row_key
    for (_shift, _group), pairs in buckets.items():
        seen = {}
        ordered_keys = []

        # 1) build stable key order from appearance
        for row_key, _r in pairs:
            if row_key not in seen:
                seen[row_key] = True
                ordered_keys.append(row_key)

        # 2) assign sequential row_order (1..n) per unique key
        key_to_order = {k: i + 1 for i, k in enumerate(ordered_keys)}

        # 3) apply to every mapping row
        for row_key, r in pairs:
            r.row_key = row_key
            r.row_order = key_to_order.get(row_key) or 1


@frappe.whitelist()
def get_matching_location_for_branch(branch):
    if not branch:
        return None
    return branch if frappe.db.exists("Location", branch) else None


@frappe.whitelist()
def sync_employees(branch, current_employees=None, auto_employees=None):
    current_employees = _as_list(current_employees)
    auto_employees = _as_list(auto_employees)

    if not branch:
        return {"to_add": [], "to_remove": sorted(list(set(auto_employees)))}

    rows = frappe.get_all(
        "Employee",
        filters={"status": "Active", "branch": branch},
        fields=["name", "employee_name", "designation"],
        order_by="employee_name asc",
    )

    should_auto = {r.name: r for r in rows}
    current_set = set([x for x in current_employees if x])
    auto_set = set([x for x in auto_employees if x])

    to_remove = sorted(list(auto_set - set(should_auto.keys())))

    to_add = []
    for emp_id, r in should_auto.items():
        if emp_id not in current_set:
            to_add.append(
                {"employee": emp_id, "employee_name": r.employee_name or "", "designation": r.designation or ""}
            )

    return {"to_add": to_add, "to_remove": to_remove}


@frappe.whitelist()
def get_employee_details(employee):
    if not employee:
        return {}
    doc = frappe.get_doc("Employee", employee)
    return {"employee_name": doc.employee_name, "designation": doc.designation}


@frappe.whitelist()
def sync_assets(location, asset_categories=None, current_assets=None, auto_assets=None):
    asset_categories = _as_list(asset_categories)
    current_assets = _as_list(current_assets)
    auto_assets = _as_list(auto_assets)

    auto_set = set([x for x in auto_assets if x])

    # If no location, remove only auto-managed assets; keep manual ones
    if not location:
        return {"to_add": [], "to_remove": sorted(list(auto_set))}

    # Build filters: always location + submitted; category filter only if selected
    filters = {
        "docstatus": 1,
        "location": location,
    }
    if asset_categories:
        filters["asset_category"] = ["in", list({c for c in asset_categories if c})]

    rows = frappe.get_all(
        "Asset",
        filters=filters,
        fields=["name", "item_name", "asset_category"],
        order_by="item_name asc",
    )

    should_auto = {r.name: r for r in rows}
    current_set = set([x for x in current_assets if x])

    # Remove only auto-managed assets that no longer match the current filters
    to_remove = sorted(list(auto_set - set(should_auto.keys())))

    # Add assets that match the current filters but aren't in the table yet
    to_add = []
    for asset_id, r in should_auto.items():
        if asset_id not in current_set:
            to_add.append(
                {"asset": asset_id, "item_name": r.item_name or "", "asset_category": r.asset_category or ""}
            )

    return {"to_add": to_add, "to_remove": to_remove}


@frappe.whitelist()
def get_asset_details(asset):
    if not asset:
        return {}
    doc = frappe.get_doc("Asset", asset)
    return {"item_name": doc.item_name, "asset_category": doc.asset_category}


@frappe.whitelist()
def debug_assets_query(location, asset_categories=None):
    """
    Diagnostic endpoint: returns what the server RECEIVES and what it FINDS.
    """
    cats = _as_list(asset_categories)

    filters = {"docstatus": 1}
    if location:
        filters["location"] = location
    if cats:
        filters["asset_category"] = ["in", list({c for c in cats if c})]

    count = frappe.db.count("Asset", filters)

    sample = frappe.get_all(
        "Asset",
        filters=filters,
        fields=["name", "item_name", "asset_category", "location", "docstatus"],
        limit_page_length=10,
        order_by="modified desc",
    )

    return {
        "location_received": location,
        "categories_received": cats,
        "filters_used": filters,
        "count": count,
        "sample": sample,
    }

# -------------------------------------------------------------------
# Template / Clone helpers
# -------------------------------------------------------------------

@frappe.whitelist()
def list_recent_site_organograms_for_branch(branch, exclude_name=None, limit=5):
    """Return last N Site Organograms for a Branch, newest first."""
    if not branch:
        return []

    try:
        limit = int(limit or 5)
    except Exception:
        limit = 5
    limit = max(1, min(20, limit))

    filters = {"branch": branch}
    if exclude_name:
        filters["name"] = ["!=", exclude_name]

    rows = frappe.get_all(
        "Site Organogram",
        filters=filters,
        fields=["name", "modified"],
        order_by="modified desc",
        limit_page_length=limit,
    )
    return rows or []


@frappe.whitelist()
def get_site_organogram_template(source_name):
    """Return a safe subset of fields/tables from a source organogram for cloning."""
    if not source_name:
        return {}

    doc = frappe.get_doc("Site Organogram", source_name)

    return {
        "location": getattr(doc, "location", None),
        "shifts": getattr(doc, "shifts", None),
        "group_headings": [{"group": r.group, "shifts": r.shifts} for r in (getattr(doc, "group_headings", None) or [])],
        "asset_categories": [{"asset_cateogories": r.asset_cateogories} for r in (getattr(doc, "asset_categories", None) or [])],
        "shift_mappings": [
            {
                "group": r.group,
                "shift": r.shift,
                "asset": r.asset,
                "employee": r.employee,
                "row_key": getattr(r, "row_key", None),
            }
            for r in (getattr(doc, "shift_mappings", None) or [])
        ],
    }