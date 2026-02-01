# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt


from __future__ import annotations

import json
import frappe
from frappe.utils import nowdate, add_days, getdate


def execute(filters=None):
    filters = filters or {}

    today = getdate(nowdate())
    warn_date = getdate(add_days(today, 90))

    # 1) Employees based on employee-level filters
    employees = _get_employees(filters)
    if not employees:
        return _base_columns(), []

    emp_ids = [e["name"] for e in employees]
    emp_map = {e["name"]: e for e in employees}

    # 2) Tracking docs (multiple per employee, optionally filtered by branch/area)
    tracking_docs_all = _get_tracking_docs(filters, emp_ids)

    # 3) Apply designation filter with rule:
    #    effective_designation = tracking.designation if set else employee.designation
    designation_filter = (filters.get("designation") or "").strip() or None
    tracking_docs = _filter_tracking_by_designation(tracking_docs_all, emp_map, designation_filter)

    # 4) Determine final included employees:
    #    - If no designation filter: all employees from step 1
    #    - If designation filter:
    #         include employee if employee.designation matches OR has at least one matching tracking doc
    included_employees = _filter_employees_by_designation_fallback(
        employees,
        tracking_docs,
        designation_filter,
        emp_map,
    )

    if not included_employees:
        return _base_columns(), []

    included_emp_ids = [e["name"] for e in included_employees]
    included_emp_map = {e["name"]: e for e in included_employees}

    # Re-filter tracking docs to included employees only (safety)
    tracking_docs = [t for t in tracking_docs if t["employee"] in included_emp_map]

    # 5) Build competency columns from union of required inductions across TRACKING docs in scope
    tracking_names = [t["name"] for t in tracking_docs]
    required_by_tracking, all_inductions = _get_required_inductions(tracking_names)

    induction_name_map = _get_induction_names(all_inductions) if all_inductions else {}
    comp_columns, comp_field_map, ordered_inductions = _build_competency_columns(all_inductions, induction_name_map) if all_inductions else ([], {}, [])

    # 6) Index records for all included employees (employee + training)
    record_index = _index_records(included_emp_ids, today)

    # 7) Output rows:
    #    - For each employee:
    #         * one row per tracking doc (if any)
    #         * else one blank row
    data = []
    tracking_by_employee = {}
    for t in tracking_docs:
        tracking_by_employee.setdefault(t["employee"], []).append(t)

    for emp in included_employees:
        emp_id = emp["name"]
        t_list = tracking_by_employee.get(emp_id, [])

        if t_list:
            # one row per tracking doc
            for t in sorted(t_list, key=lambda x: (x.get("branch") or "", x.get("name") or "")):
                row = _base_row_tracking(t, included_emp_map)

                required = set(required_by_tracking.get(t["name"], []))

                for induction_id in ordered_inductions:
                    fieldname = comp_field_map[induction_id]
                    if induction_id not in required:
                        row[fieldname] = ""
                        continue

                    payload = _build_cell_payload(
                        emp=emp_id,
                        induction=induction_id,
                        idx=record_index,
                        today=today,
                        warn_date=warn_date,
                    )
                    row[fieldname] = json.dumps(payload)

                data.append(row)
        else:
            # blank row (employee exists but has no tracking docs)
            row = _base_row_employee_only(emp)
            for induction_id in ordered_inductions:
                row[comp_field_map[induction_id]] = ""
            data.append(row)

    columns = _base_columns() + comp_columns
    return columns, data


# -----------------------
# Columns / Rows
# -----------------------

def _base_columns():
    return [
        {"fieldname": "tracking", "label": "Tracking", "fieldtype": "Link", "options": "Employee Induction Tracking", "width": 170},
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch", "width": 140},
        {"fieldname": "designation", "label": "Designation", "fieldtype": "Link", "options": "Designation", "width": 160},
    ]


def _base_row_tracking(tracking_row, emp_map):
    emp = emp_map.get(tracking_row["employee"]) or {}
    # designation display: prefer tracking.designation if set else employee.designation
    effective_designation = tracking_row.get("designation") or emp.get("designation")
    return {
        "tracking": tracking_row["name"],
        "employee": tracking_row["employee"],
        "employee_name": emp.get("employee_name"),
        "branch": tracking_row.get("branch"),
        "designation": effective_designation,
    }


def _base_row_employee_only(emp_row):
    # No tracking doc exists; branch/designation are employee-based (branch can be blank if you prefer)
    return {
        "tracking": None,
        "employee": emp_row["name"],
        "employee_name": emp_row.get("employee_name"),
        "branch": emp_row.get("branch"),
        "designation": emp_row.get("designation"),
    }


# -----------------------
# Employees
# -----------------------

def _get_employees(filters):
    employee = (filters.get("employee") or "").strip() or None

    # Synthetic report filter
    employee_status = (filters.get("employee_status") or "Active").strip() or "Active"

    emp_filters = {}
    if employee:
        emp_filters["name"] = employee

    if employee_status != "All":
        emp_filters["status"] = employee_status

    return frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_name", "designation", "branch", "status"],
        order_by="employee_name asc",
        limit_page_length=2000,
    )


# -----------------------
# Tracking Docs (multiple per employee)
# -----------------------

def _resolve_branch_set(filters):
    branch = (filters.get("branch") or "").strip() or None
    area_setup = (filters.get("area_setup") or "").strip() or None

    branches = set()

    if area_setup:
        rows = frappe.get_all(
            "Branch Selector",
            filters={"parenttype": "Area Setup", "parent": area_setup},
            fields=["branch"],
            limit_page_length=10000,
        )
        for r in rows:
            if r.get("branch"):
                branches.add(r["branch"])

    if branch:
        branches.add(branch)

    return sorted(branches)


def _get_tracking_docs(filters, employee_ids):
    branches = _resolve_branch_set(filters)

    t_filters = {"employee": ["in", employee_ids]}
    if branches:
        t_filters["branch"] = ["in", branches]

    return frappe.get_all(
        "Employee Induction Tracking",
        filters=t_filters,
        fields=["name", "employee", "branch", "designation"],
        order_by="employee asc, branch asc, modified desc",
        limit_page_length=20000,
    )


def _filter_tracking_by_designation(tracking_docs, emp_map, designation_filter):
    if not designation_filter:
        return tracking_docs

    out = []
    for t in tracking_docs:
        emp = emp_map.get(t["employee"]) or {}
        effective_designation = t.get("designation") or emp.get("designation")
        if effective_designation == designation_filter:
            out.append(t)
    return out


def _filter_employees_by_designation_fallback(employees, tracking_docs, designation_filter, emp_map):
    if not designation_filter:
        return employees

    emp_with_matching_tracking = {t["employee"] for t in tracking_docs}

    out = []
    for e in employees:
        if e.get("designation") == designation_filter or e["name"] in emp_with_matching_tracking:
            out.append(e)
    return out


# -----------------------
# Required inductions per tracking doc
# -----------------------

def _get_required_inductions(tracking_names):
    tracking_names = [t for t in tracking_names if t]
    if not tracking_names:
        return {}, []

    children = frappe.get_all(
        "Employee Required Inductions",
        filters={"parent": ["in", tracking_names], "parenttype": "Employee Induction Tracking"},
        fields=["parent", "induction"],
        limit_page_length=200000,
    )

    required_by_tracking = {}
    all_inductions = set()

    for c in children:
        parent = c.get("parent")
        ind = c.get("induction")
        if not parent or not ind:
            continue
        required_by_tracking.setdefault(parent, []).append(ind)
        all_inductions.add(ind)

    return required_by_tracking, list(all_inductions)


def _get_induction_names(induction_ids):
    if not induction_ids:
        return {}
    rows = frappe.get_all(
        "Employee Induction",
        filters={"name": ["in", induction_ids]},
        fields=["name", "training_name"],
        limit_page_length=10000,
    )
    return {r["name"]: (r.get("training_name") or r["name"]) for r in rows}


def _build_competency_columns(induction_ids, induction_name_map):
    if not induction_ids:
        return [], {}, []

    ordered = sorted(induction_ids, key=lambda x: (induction_name_map.get(x) or x).lower())

    columns = []
    field_map = {}

    for ind in ordered:
        fieldname = f"ind_{frappe.scrub(ind)}"
        field_map[ind] = fieldname
        columns.append({
            "fieldname": fieldname,
            "label": induction_name_map.get(ind) or ind,
            "fieldtype": "Data",
            "width": 150,
        })

    return columns, field_map, ordered


# -----------------------
# Records index (employee + training)
# -----------------------

def _index_records(employee_ids, today):
    rows = frappe.get_all(
        "Employee Induction Record",
        filters={"employee": ["in", employee_ids]},
        fields=["name", "employee", "training", "training_date", "valid_to", "docstatus"],
        order_by="training_date desc",
        limit_page_length=200000,
    )

    idx = {}
    for r in rows:
        emp = r.get("employee")
        trn = r.get("training")
        if not emp or not trn:
            continue

        key = (emp, trn)
        if key not in idx:
            idx[key] = {"submitted": None, "scheduled": None}

        td = getdate(r["training_date"]) if r.get("training_date") else None
        vd = getdate(r["valid_to"]) if r.get("valid_to") else None

        record = {
            "name": r["name"],
            "training_date": td,
            "valid_to": vd,
            "docstatus": r.get("docstatus"),
        }

        if r.get("docstatus") == 1 and idx[key]["submitted"] is None:
            idx[key]["submitted"] = record
            continue

        if r.get("docstatus") != 1 and td and td >= today and idx[key]["scheduled"] is None:
            idx[key]["scheduled"] = record

    return idx


def _build_cell_payload(emp, induction, idx, today, warn_date):
    entry = idx.get((emp, induction)) or {"submitted": None, "scheduled": None}
    sub = entry.get("submitted")
    sch = entry.get("scheduled")

    payload = {
        "status": "red",
        "expiry": None,
        "days": None,
        "last": None,
        "scheduled": None,
    }

    if sch and sch.get("training_date"):
        payload["scheduled"] = sch["training_date"].isoformat()

    if not sub:
        return payload

    if sub.get("training_date"):
        payload["last"] = sub["training_date"].isoformat()

    # No expiry => red
    if not sub.get("valid_to"):
        payload["status"] = "red"
        return payload

    expiry = sub["valid_to"]
    payload["expiry"] = expiry.isoformat()
    payload["days"] = (expiry - today).days

    if expiry < today:
        payload["status"] = "red"
    elif expiry <= warn_date:
        payload["status"] = "yellow"
    else:
        payload["status"] = "green"

    return payload
