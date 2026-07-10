# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

from collections import OrderedDict, defaultdict
from io import BytesIO

import frappe
from frappe.model.document import Document


class SiteOrganogram(Document):
    def validate(self):
        normalize_group_structure(self)
        normalize_mappings(self)
        normalize_reporting_lines(self)

    def before_submit(self):
        normalize_group_structure(self)
        normalize_mappings(self)
        normalize_reporting_lines(self)


# -------------------------------------------------------------------
# Generic helpers
# -------------------------------------------------------------------

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


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _safe_int(value, default=0):
    try:
        return int(value or default)
    except Exception:
        return default


def _parse_row_key(row_key):
    row_key = _clean(row_key)

    if row_key.startswith("ASSET::"):
        return {
            "kind": "Asset",
            "asset": row_key[len("ASSET::"):],
            "designation": "",
        }

    if row_key.startswith("DESIG::"):
        rest = row_key[len("DESIG::"):]
        parts = rest.split("::")
        return {
            "kind": "Designation",
            "asset": "",
            "designation": parts[0] or "",
            "token": parts[1] if len(parts) > 1 else "",
        }

    return {
        "kind": "Unknown",
        "asset": "",
        "designation": "",
    }


def _row_key_for_asset(asset):
    return f"ASSET::{_clean(asset)}"


def _row_key_for_designation(label, token=None):
    label = _clean(label) or "Unlinked Role"
    token = _clean(token) or frappe.generate_hash(length=6)
    return f"DESIG::{label}::{token}"


def _derive_row_key(row):
    existing = _clean(getattr(row, "row_key", None))
    if existing:
        return existing

    row_type = _clean(getattr(row, "row_type", None))
    asset = _clean(getattr(row, "asset", None))
    label = _clean(getattr(row, "row_label", None))

    if row_type == "Asset" or asset:
        if asset:
            return _row_key_for_asset(asset)
        return f"MISSING_ASSET::{frappe.generate_hash(length=6)}"

    return _row_key_for_designation(label or "Unlinked Role")


def _asset_display(asset_id):
    if not asset_id:
        return ""

    values = frappe.db.get_value(
        "Asset",
        asset_id,
        ["name", "item_name", "asset_category"],
        as_dict=True,
    )

    if not values:
        return asset_id

    parts = [values.name]
    if values.item_name:
        parts.append(values.item_name)
    elif values.asset_category:
        parts.append(values.asset_category)

    return " — ".join(parts)


def _employee_exists(employee_id):
    if not employee_id:
        return False
    return bool(frappe.db.exists("Employee", employee_id))


def _asset_exists(asset_id):
    if not asset_id:
        return False
    return bool(frappe.db.exists("Asset", asset_id))


def _new_group_key():
    return f"GRP::{frappe.generate_hash(length=10)}"


def normalize_group_structure(doc):
    """Assign stable keys to headings and mirror them onto mapping rows."""
    headings = getattr(doc, "group_headings", None) or []
    mappings = getattr(doc, "shift_mappings", None) or []

    by_key = {}
    by_label = {}

    for heading in headings:
        label = _clean(getattr(heading, "group", None))
        key = _clean(getattr(heading, "group_key", None))

        if not key:
            key = _new_group_key()
            heading.group_key = key

        if key in by_key and by_key[key] is not heading:
            key = _new_group_key()
            heading.group_key = key

        by_key[key] = heading
        if label and label not in by_label:
            by_label[label] = heading

    for row in mappings:
        key = _clean(getattr(row, "group_key", None))
        label = _clean(getattr(row, "group", None))
        heading = by_key.get(key) if key else None

        if not heading and label:
            heading = by_label.get(label)

        if heading:
            row.group_key = heading.group_key
            row.group = heading.group


def normalize_reporting_lines(doc):
    """Repair reporting-line endpoints without deleting user data."""
    headings = getattr(doc, "group_headings", None) or []
    lines = getattr(doc, "reporting_lines", None) or []

    by_key = {
        _clean(getattr(row, "group_key", None)): row
        for row in headings
        if _clean(getattr(row, "group_key", None))
    }
    by_label = {}
    for row in headings:
        label = _clean(getattr(row, "group", None))
        if label and label not in by_label:
            by_label[label] = row

    for index, line in enumerate(lines, start=1):
        for prefix in ("source", "target"):
            key_field = f"{prefix}_group_key"
            label_field = f"{prefix}_group"
            scope_field = f"{prefix}_scope"
            shift_field = f"{prefix}_shift"

            key = _clean(getattr(line, key_field, None))
            label = _clean(getattr(line, label_field, None))
            heading = by_key.get(key) if key else None

            if not heading and label:
                heading = by_label.get(label)

            if heading:
                setattr(line, key_field, heading.group_key)
                setattr(line, label_field, heading.group)

            scope = _clean(getattr(line, scope_field, None)) or "Heading"
            if scope not in ("Heading", "Shift"):
                scope = "Heading"
            setattr(line, scope_field, scope)

            if scope == "Heading":
                setattr(line, shift_field, "")

        line.line_type = _clean(getattr(line, "line_type", None)) or "Solid"
        line.source_anchor = _clean(getattr(line, "source_anchor", None)) or "Auto"
        line.target_anchor = _clean(getattr(line, "target_anchor", None)) or "Auto"
        if not _safe_int(getattr(line, "line_order", 0), 0):
            line.line_order = index


def normalize_mappings(doc):
    """
    Server-side safety net.

    Important:
    - Never delete mapping rows here.
    - Preserve organogram structure.
    - Ensure row_key, row_type, row_label, missing flags, and row_order are sane.
    """

    rows = getattr(doc, "shift_mappings", None) or []
    if not rows:
        return

    # First pass: repair row identity and labels.
    for row in rows:
        row.row_key = _derive_row_key(row)

        info = _parse_row_key(row.row_key)
        current_type = _clean(getattr(row, "row_type", None))

        if info["kind"] == "Asset":
            row.row_type = "Asset"

            asset_from_key = info.get("asset") or ""
            if not _clean(getattr(row, "asset", None)):
                row.asset = asset_from_key if _asset_exists(asset_from_key) else ""

            if not _clean(getattr(row, "row_label", None)):
                row.row_label = _asset_display(asset_from_key) or asset_from_key or "Missing"

            if _clean(getattr(row, "asset", None)) and _asset_exists(row.asset):
                row.missing_asset = 0
            else:
                row.missing_asset = 1

        elif info["kind"] == "Designation":
            row.row_type = "Designation"
            row.asset = ""
            row.missing_asset = 0

            if not _clean(getattr(row, "row_label", None)):
                row.row_label = info.get("designation") or "Unlinked Role"

        else:
            if current_type == "Asset":
                row.row_type = "Asset"
                row.missing_asset = 1
                if not _clean(getattr(row, "row_label", None)):
                    row.row_label = "Missing"
            else:
                row.row_type = "Designation"
                row.asset = ""
                row.missing_asset = 0
                if not _clean(getattr(row, "row_label", None)):
                    row.row_label = "Unlinked Role"

        if _clean(getattr(row, "employee", None)) and _employee_exists(row.employee):
            row.missing_employee = 0
        elif _clean(getattr(row, "employee", None)):
            row.employee = ""
            row.missing_employee = 1
        else:
            row.missing_employee = _safe_int(getattr(row, "missing_employee", 0), 0)

    # Second pass: stable row order per group.
    groups = defaultdict(list)

    for row in rows:
        group = _clean(getattr(row, "group", None))
        row_key = _clean(getattr(row, "row_key", None))
        if not group or not row_key:
            continue
        groups[group].append(row)

    for group, group_rows in groups.items():
        key_order = OrderedDict()

        for row in sorted(
            group_rows,
            key=lambda r: (
                _safe_int(getattr(r, "row_order", 0), 999999) or 999999,
                _safe_int(getattr(r, "idx", 0), 999999) or 999999,
            ),
        ):
            if row.row_key not in key_order:
                key_order[row.row_key] = len(key_order) + 1

        for row in group_rows:
            row.row_order = key_order.get(row.row_key) or 1


# -------------------------------------------------------------------
# Branch / Location helpers
# -------------------------------------------------------------------

@frappe.whitelist()
def get_matching_location_for_branch(branch):
    if not branch:
        return None
    return branch if frappe.db.exists("Location", branch) else None


# -------------------------------------------------------------------
# Employee / Asset sync
# -------------------------------------------------------------------

@frappe.whitelist()
def sync_employees(branch, current_employees=None, auto_employees=None):
    current_employees = _as_list(current_employees)
    auto_employees = _as_list(auto_employees)

    if not branch:
        return {
            "to_add": [],
            "to_remove": sorted(list(set(auto_employees))),
        }

    rows = frappe.get_all(
        "Employee",
        filters={
            "status": "Active",
            "branch": branch,
        },
        fields=["name", "employee_name", "designation"],
        order_by="employee_name asc",
    )

    should_auto = {r.name: r for r in rows}
    current_set = set([x for x in current_employees if x])
    auto_set = set([x for x in auto_employees if x])

    to_remove = sorted(list(auto_set - set(should_auto.keys())))

    to_add = []
    for emp_id, row in should_auto.items():
        if emp_id not in current_set:
            to_add.append(
                {
                    "employee": emp_id,
                    "employee_name": row.employee_name or "",
                    "designation": row.designation or "",
                }
            )

    return {
        "to_add": to_add,
        "to_remove": to_remove,
    }


@frappe.whitelist()
def get_employee_details(employee):
    if not employee:
        return {}

    doc = frappe.get_doc("Employee", employee)

    return {
        "employee_name": doc.employee_name,
        "designation": doc.designation,
    }


@frappe.whitelist()
def sync_assets(location, asset_categories=None, current_assets=None, auto_assets=None):
    asset_categories = _as_list(asset_categories)
    current_assets = _as_list(current_assets)
    auto_assets = _as_list(auto_assets)

    auto_set = set([x for x in auto_assets if x])

    if not location:
        return {
            "to_add": [],
            "to_remove": sorted(list(auto_set)),
        }

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

    to_remove = sorted(list(auto_set - set(should_auto.keys())))

    to_add = []
    for asset_id, row in should_auto.items():
        if asset_id not in current_set:
            to_add.append(
                {
                    "asset": asset_id,
                    "item_name": row.item_name or "",
                    "asset_category": row.asset_category or "",
                }
            )

    return {
        "to_add": to_add,
        "to_remove": to_remove,
    }


@frappe.whitelist()
def get_asset_details(asset):
    if not asset:
        return {}

    doc = frappe.get_doc("Asset", asset)

    return {
        "item_name": doc.item_name,
        "asset_category": doc.asset_category,
    }


@frappe.whitelist()
def debug_assets_query(location, asset_categories=None):
    cats = _as_list(asset_categories)

    filters = {
        "docstatus": 1,
    }

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
    if not branch:
        return []

    try:
        limit = int(limit or 5)
    except Exception:
        limit = 5

    limit = max(1, min(20, limit))

    filters = {
        "branch": branch,
    }

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
    """
    Return a safe clone payload.

    Important:
    - Copies the structure and mapping table exactly.
    - Does not decide what is valid for the target document.
    - The target JS reconciles against the current branch/location pools without deleting rows.
    """

    if not source_name:
        return {}

    doc = frappe.get_doc("Site Organogram", source_name)
    normalize_group_structure(doc)
    normalize_mappings(doc)
    normalize_reporting_lines(doc)

    return {
        "location": getattr(doc, "location", None),
        "shifts": getattr(doc, "shifts", None),
        "group_headings": [
            {
                "group_key": getattr(r, "group_key", None),
                "group": r.group,
                "shifts": r.shifts,
            }
            for r in (getattr(doc, "group_headings", None) or [])
        ],
        "asset_categories": [
            {
                "asset_cateogories": r.asset_cateogories,
            }
            for r in (getattr(doc, "asset_categories", None) or [])
        ],
        "employees": [
            {
                "employee": r.employee,
                "employee_name": r.employee_name,
                "designation": r.designation,
            }
            for r in (getattr(doc, "employees", None) or [])
        ],
        "assets": [
            {
                "asset": r.asset,
                "item_name": r.item_name,
                "asset_category": r.asset_category,
            }
            for r in (getattr(doc, "assets", None) or [])
        ],
        "shift_mappings": [
            {
                "group_key": getattr(r, "group_key", None),
                "group": r.group,
                "shift": r.shift,
                "employee": r.employee,
                "asset": r.asset,
                "row_key": getattr(r, "row_key", None),
                "row_order": getattr(r, "row_order", None),
                "row_label": getattr(r, "row_label", None),
                "row_type": getattr(r, "row_type", None),
                "missing_asset": getattr(r, "missing_asset", 0),
                "missing_employee": getattr(r, "missing_employee", 0),
            }
            for r in (getattr(doc, "shift_mappings", None) or [])
        ],
        "reporting_lines": [
            {
                "source_group_key": getattr(r, "source_group_key", None),
                "source_group": getattr(r, "source_group", None),
                "source_scope": getattr(r, "source_scope", None),
                "source_shift": getattr(r, "source_shift", None),
                "target_group_key": getattr(r, "target_group_key", None),
                "target_group": getattr(r, "target_group", None),
                "target_scope": getattr(r, "target_scope", None),
                "target_shift": getattr(r, "target_shift", None),
                "line_type": getattr(r, "line_type", None),
                "label": getattr(r, "label", None),
                "source_anchor": getattr(r, "source_anchor", None),
                "target_anchor": getattr(r, "target_anchor", None),
                "line_order": getattr(r, "line_order", None),
            }
            for r in (getattr(doc, "reporting_lines", None) or [])
        ],
    }


# -------------------------------------------------------------------
# Excel export
# -------------------------------------------------------------------

def _active_shift_labels(doc):
    count = _safe_int(getattr(doc, "shifts", None), 0)
    count = max(0, min(5, count))
    return [f"Shift {x}" for x in ["A", "B", "C", "D", "E"][:count]]


def _group_shift_labels(doc, group_row):
    mode = _clean(getattr(group_row, "shifts", None))

    if mode == "Day Shift Only":
        return ["Day Shift"]

    if mode == "Night Shift Only":
        return ["Night Shift"]

    return _active_shift_labels(doc)


def _split_employee_name(full_name):
    full_name = _clean(full_name)

    if not full_name:
        return "", ""

    parts = full_name.split()

    if len(parts) == 1:
        return parts[0], ""

    return " ".join(parts[:-1]), parts[-1]


def _employee_lookup(doc):
    lookup = {}

    for row in getattr(doc, "employees", None) or []:
        if not row.employee:
            continue

        first_names, surname = _split_employee_name(row.employee_name or row.employee)

        lookup[row.employee] = {
            "employee": row.employee,
            "employee_name": row.employee_name or row.employee,
            "first_names": first_names,
            "surname": surname,
            "designation": row.designation or "",
        }

    return lookup


def _asset_lookup(doc):
    lookup = {}

    for row in getattr(doc, "assets", None) or []:
        if not row.asset:
            continue

        lookup[row.asset] = {
            "asset": row.asset,
            "item_name": row.item_name or "",
            "asset_category": row.asset_category or "",
        }

    return lookup


def _mapping_indexes(doc):
    by_slot = {}
    row_keys_by_group = defaultdict(OrderedDict)

    rows = sorted(
        getattr(doc, "shift_mappings", None) or [],
        key=lambda row: (
            _clean(getattr(row, "group", None)),
            _safe_int(getattr(row, "row_order", 0), 999999) or 999999,
            _safe_int(getattr(row, "idx", 0), 999999) or 999999,
        ),
    )

    for row in rows:
        group = _clean(getattr(row, "group", None))
        shift = _clean(getattr(row, "shift", None))
        row_key = _clean(getattr(row, "row_key", None))

        if not group or not shift or not row_key:
            continue

        row_keys_by_group[group].setdefault(row_key, row)
        by_slot[(group, shift, row_key)] = row

    return by_slot, row_keys_by_group


def _employee_display(emp):
    if not emp:
        return "", ""
    return emp.get("employee_name") or emp.get("employee") or "", emp.get("employee") or ""


def _style_range_border(ws, min_row, max_row, min_col, max_col, border):
    for row in ws.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
        for cell in row:
            cell.border = border


def _row_label_for_export(row, assets):
    row_type = _clean(getattr(row, "row_type", None))
    row_label = _clean(getattr(row, "row_label", None))
    missing_asset = _safe_int(getattr(row, "missing_asset", 0), 0)

    if row_type == "Asset":
        if missing_asset:
            return "Missing", row_label or "Missing"

        asset_id = _clean(getattr(row, "asset", None))
        asset = assets.get(asset_id)

        if asset:
            return asset.get("asset") or asset_id, asset.get("item_name") or asset.get("asset_category") or ""

        return asset_id or "Missing", row_label or ""

    return row_label or "Designation", ""


def _write_simple_list(ws, row_no, title, headers, rows, styles):
    total_cols = max(1, len(headers))

    ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
    c = ws.cell(row_no, 1, title)
    c.font = styles["section_font"]
    c.alignment = styles["center"]
    c.fill = styles["section_fill"]
    row_no += 1

    for idx, header in enumerate(headers, start=1):
        cell = ws.cell(row_no, idx, header)
        cell.font = styles["header_font"]
        cell.fill = styles["header_fill"]
        cell.alignment = styles["center"]

    row_no += 1
    data_start = row_no

    if rows:
        for item in rows:
            for idx, value in enumerate(item, start=1):
                ws.cell(row_no, idx, value)
                ws.cell(row_no, idx).alignment = styles["wrap"]
            row_no += 1
    else:
        ws.cell(row_no, 1, "None")
        row_no += 1

    _style_range_border(ws, data_start - 2, row_no - 1, 1, total_cols, styles["thin_border"])

    return row_no + 1


def _write_group(ws, row_no, doc, group_row, shifts, row_keys, by_slot, employees, assets, styles):
    group = group_row.group
    total_cols = max(4, 2 + (len(shifts) * 2))

    ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
    cell = ws.cell(row_no, 1, group.upper())
    cell.font = styles["section_font"]
    cell.alignment = styles["center"]
    cell.fill = styles["section_fill"]
    row_no += 1

    ws.cell(row_no, 1, "")
    ws.cell(row_no, 2, "")

    col = 3
    for shift in shifts:
        ws.merge_cells(start_row=row_no, start_column=col, end_row=row_no, end_column=col + 1)
        c = ws.cell(row_no, col, shift.upper())
        c.font = styles["shift_font"]
        c.alignment = styles["center"]
        c.fill = styles["shift_fill"]
        col += 2

    row_no += 1

    ws.cell(row_no, 1, "ASSET / DESIGNATION")
    ws.cell(row_no, 2, "DESCRIPTION")
    col = 3

    for _shift in shifts:
        ws.cell(row_no, col, "OPERATOR NAME")
        ws.cell(row_no, col + 1, "COY NO")
        col += 2

    for c in range(1, total_cols + 1):
        ws.cell(row_no, c).font = styles["header_font"]
        ws.cell(row_no, c).fill = styles["header_fill"]
        ws.cell(row_no, c).alignment = styles["center"]

    row_no += 1
    data_start = row_no

    for row_key, row_identity in row_keys.items():
        label, desc = _row_label_for_export(row_identity, assets)
        ws.cell(row_no, 1, label)
        ws.cell(row_no, 2, desc)

        col = 3
        for shift in shifts:
            mapping = by_slot.get((group, shift, row_key))
            employee_id = mapping.employee if mapping and mapping.employee else None
            emp = employees.get(employee_id) if employee_id else None

            if mapping and _safe_int(getattr(mapping, "missing_employee", 0), 0):
                ws.cell(row_no, col, "Missing")
                ws.cell(row_no, col + 1, "")
            else:
                name, coy_no = _employee_display(emp)
                ws.cell(row_no, col, name or "Vacant")
                ws.cell(row_no, col + 1, coy_no)

            col += 2

        row_no += 1

    data_end = max(data_start, row_no - 1)
    _style_range_border(ws, data_start - 3, data_end, 1, total_cols, styles["thin_border"])

    for r in range(data_start, row_no):
        for c in range(1, total_cols + 1):
            ws.cell(r, c).alignment = styles["wrap"]

    return row_no + 1


@frappe.whitelist()
def export_site_organogram_excel(name):
    if not name:
        frappe.throw("Site Organogram name is required.")

    doc = frappe.get_doc("Site Organogram", name)
    doc.check_permission("read")
    normalize_group_structure(doc)
    normalize_mappings(doc)
    normalize_reporting_lines(doc)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        frappe.throw("openpyxl is required for this export but is not installed.")

    wb = Workbook()
    ws = wb.active
    ws.title = (doc.branch or "Organogram")[:31]

    thin_side = Side(style="thin", color="000000")

    styles = {
        "title_font": Font(bold=True, size=14),
        "section_font": Font(bold=True, size=12),
        "shift_font": Font(bold=True, size=11),
        "header_font": Font(bold=True, size=10),
        "section_fill": PatternFill("solid", fgColor="D9EAD3"),
        "shift_fill": PatternFill("solid", fgColor="D9EAF7"),
        "header_fill": PatternFill("solid", fgColor="E7E6E6"),
        "center": Alignment(horizontal="center", vertical="center", wrap_text=True),
        "wrap": Alignment(vertical="top", wrap_text=True),
        "thin_border": Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side),
    }

    employees = _employee_lookup(doc)
    assets = _asset_lookup(doc)
    by_slot, row_keys_by_group = _mapping_indexes(doc)

    assigned_employees = {
        row.employee
        for row in getattr(doc, "shift_mappings", None) or []
        if row.employee
    }

    assigned_assets = {
        row.asset
        for row in getattr(doc, "shift_mappings", None) or []
        if _clean(getattr(row, "row_type", None)) == "Asset"
        and row.asset
        and not _safe_int(getattr(row, "missing_asset", 0), 0)
    }

    row_no = 1
    heading_cols = max(8, 2 + len(_active_shift_labels(doc)) * 2)

    ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=heading_cols)
    ws.cell(row_no, 1, (doc.branch or doc.name or "SITE ORGANOGRAM").upper())
    ws.cell(row_no, 1).font = styles["title_font"]
    ws.cell(row_no, 1).alignment = styles["center"]
    row_no += 2

    groups = [row for row in getattr(doc, "group_headings", None) or [] if row.group]

    for group_row in groups:
        group = group_row.group
        row_keys = row_keys_by_group.get(group, OrderedDict())

        if not row_keys:
            continue

        shifts = _group_shift_labels(doc, group_row)

        if not shifts:
            continue

        row_no = _write_group(ws, row_no, doc, group_row, shifts, row_keys, by_slot, employees, assets, styles)

    unallocated_employee_rows = []
    for emp_id in sorted(set(employees.keys()) - assigned_employees, key=lambda x: employees[x].get("employee_name") or x):
        emp = employees[emp_id]
        unallocated_employee_rows.append([emp["employee"], emp["first_names"], emp["surname"], emp["designation"]])

    unallocated_asset_rows = []
    for asset_id in sorted(set(assets.keys()) - assigned_assets, key=lambda x: assets[x].get("item_name") or x):
        asset = assets[asset_id]
        unallocated_asset_rows.append([asset["asset"], asset["item_name"], asset["asset_category"]])

    row_no += 1
    row_no = _write_simple_list(
        ws,
        row_no,
        "UNALLOCATED EMPLOYEES",
        ["COY NO", "NAME", "SURNAME", "DESIGNATION"],
        unallocated_employee_rows,
        styles,
    )

    row_no = _write_simple_list(
        ws,
        row_no,
        "UNALLOCATED ASSETS",
        ["PLANT NO", "MACHINE MAKE", "ASSET CATEGORY"],
        unallocated_asset_rows,
        styles,
    )

    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
        for cell in row:
            if cell.value is not None:
                cell.alignment = styles["wrap"]

    for col_idx in range(1, ws.max_column + 1):
        letter = get_column_letter(col_idx)
        if col_idx == 1:
            ws.column_dimensions[letter].width = 22
        elif col_idx == 2:
            ws.column_dimensions[letter].width = 26
        else:
            ws.column_dimensions[letter].width = 18

    for row_idx in range(1, ws.max_row + 1):
        ws.row_dimensions[row_idx].height = 18

    out = BytesIO()
    wb.save(out)
    out.seek(0)

    filename = f"{frappe.scrub(doc.name or 'site_organogram')}.xlsx"
    frappe.local.response.filename = filename
    frappe.local.response.filecontent = out.getvalue()
    frappe.local.response.type = "binary"
# -------------------------------------------------------------------
# Organogram Designer Page API
# -------------------------------------------------------------------

def _designer_child_rows(rows, fields):
    return [
        {field: getattr(row, field, None) for field in fields}
        for row in (rows or [])
    ]


def _designer_payload(doc):
    normalize_group_structure(doc)
    normalize_mappings(doc)
    normalize_reporting_lines(doc)

    return {
        "name": doc.name,
        "doctype": doc.doctype,
        "docstatus": doc.docstatus,
        "modified": str(doc.modified or ""),
        "branch": getattr(doc, "branch", None),
        "location": getattr(doc, "location", None),
        "shifts": getattr(doc, "shifts", None),
        "asset_categories": _designer_child_rows(
            getattr(doc, "asset_categories", None),
            ["asset_cateogories"],
        ),
        "group_headings": _designer_child_rows(
            getattr(doc, "group_headings", None),
            ["group_key", "group", "shifts"],
        ),
        "employees": _designer_child_rows(
            getattr(doc, "employees", None),
            ["employee", "employee_name", "designation"],
        ),
        "assets": _designer_child_rows(
            getattr(doc, "assets", None),
            ["asset", "item_name", "asset_category"],
        ),
        "shift_mappings": _designer_child_rows(
            getattr(doc, "shift_mappings", None),
            [
                "group_key", "group", "shift", "employee", "asset",
                "row_key", "row_order", "row_label", "row_type",
                "missing_asset", "missing_employee",
            ],
        ),
        "reporting_lines": _designer_child_rows(
            getattr(doc, "reporting_lines", None),
            [
                "source_group_key", "source_group", "source_scope", "source_shift",
                "target_group_key", "target_group", "target_scope", "target_shift",
                "line_type", "label", "source_anchor", "target_anchor", "line_order",
            ],
        ),
    }


@frappe.whitelist()
def list_site_organograms_for_designer(branch=None, limit=100):
    try:
        limit = max(1, min(int(limit or 100), 500))
    except Exception:
        limit = 100

    filters = {}
    if branch:
        filters["branch"] = branch

    return frappe.get_all(
        "Site Organogram",
        filters=filters,
        fields=["name", "branch", "location", "shifts", "docstatus", "modified"],
        order_by="modified desc",
        limit_page_length=limit,
    )


@frappe.whitelist()
def get_site_organogram_designer_state(name):
    if not name:
        frappe.throw("Site Organogram name is required.")

    doc = frappe.get_doc("Site Organogram", name)
    doc.check_permission("read")
    return _designer_payload(doc)


def _replace_child_table(doc, fieldname, rows, allowed_fields):
    doc.set(fieldname, [])
    for item in _as_list(rows):
        if not isinstance(item, dict):
            continue
        child = doc.append(fieldname, {})
        for field in allowed_fields:
            if field in item:
                setattr(child, field, item.get(field))


@frappe.whitelist()
def save_site_organogram_designer_state(payload):
    if isinstance(payload, str):
        payload = frappe.parse_json(payload)
    if not isinstance(payload, dict):
        frappe.throw("A valid designer payload is required.")

    name = _clean(payload.get("name"))
    expected_modified = _clean(payload.get("modified"))

    if name:
        doc = frappe.get_doc("Site Organogram", name)
        doc.check_permission("write")
        if doc.docstatus != 0:
            frappe.throw("Submitted or cancelled Site Organograms cannot be edited in the designer.")

        current_modified = str(doc.modified or "")
        if expected_modified and current_modified and expected_modified != current_modified:
            frappe.throw(
                "This Site Organogram was changed after it was loaded. Reload it before saving.",
                title="Document Changed",
            )
    else:
        doc = frappe.new_doc("Site Organogram")
        doc.check_permission("create")

    branch = _clean(payload.get("branch"))
    location = _clean(payload.get("location"))
    shifts = _clean(payload.get("shifts"))

    if not branch:
        frappe.throw("Site is required.")
    if not location:
        frappe.throw("Location is required.")
    if shifts not in ("1", "2", "3", "4", "5"):
        frappe.throw("Shift Teams must be between 1 and 5.")

    doc.branch = branch
    doc.location = location
    doc.shifts = shifts

    _replace_child_table(doc, "asset_categories", payload.get("asset_categories"), ["asset_cateogories"])
    _replace_child_table(doc, "group_headings", payload.get("group_headings"), ["group_key", "group", "shifts"])
    _replace_child_table(doc, "employees", payload.get("employees"), ["employee", "employee_name", "designation"])
    _replace_child_table(doc, "assets", payload.get("assets"), ["asset", "item_name", "asset_category"])
    _replace_child_table(
        doc,
        "shift_mappings",
        payload.get("shift_mappings"),
        [
            "group_key", "group", "shift", "employee", "asset", "row_key",
            "row_order", "row_label", "row_type", "missing_asset", "missing_employee",
        ],
    )
    _replace_child_table(
        doc,
        "reporting_lines",
        payload.get("reporting_lines"),
        [
            "source_group_key", "source_group", "source_scope", "source_shift",
            "target_group_key", "target_group", "target_scope", "target_shift",
            "line_type", "label", "source_anchor", "target_anchor", "line_order",
        ],
    )

    normalize_group_structure(doc)
    normalize_mappings(doc)
    normalize_reporting_lines(doc)
    doc.save()

    return _designer_payload(doc)
