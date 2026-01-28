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

    employees = _get_employees(filters)
    if not employees:
        return _base_columns(), []

    emp_ids = [e["name"] for e in employees]

    tracking_by_employee = _get_tracking_docs(emp_ids)

    required_by_tracking, all_inductions = _get_required_inductions(list(tracking_by_employee.values()))

    if not all_inductions:
        return _base_columns(), [_base_row(e) for e in employees]

    induction_name_map = _get_induction_names(all_inductions)

    comp_columns, comp_field_map, ordered_inductions = _build_competency_columns(
        all_inductions,
        induction_name_map,
    )

    record_index = _index_records(emp_ids, today)

    data = []
    for e in employees:
        row = _base_row(e)

        tracking = tracking_by_employee.get(e["name"])
        required = set(required_by_tracking.get(tracking, [])) if tracking else set()

        for induction_id in ordered_inductions:
            fieldname = comp_field_map[induction_id]

            if induction_id not in required:
                row[fieldname] = ""
                continue

            payload = _build_cell_payload(
                emp=e["name"],
                induction=induction_id,
                idx=record_index,
                today=today,
                warn_date=warn_date,
            )
            row[fieldname] = json.dumps(payload)

        data.append(row)

    columns = _base_columns() + comp_columns
    return columns, data


def _base_columns():
    return [
        {"fieldname": "employee", "label": "Employee", "fieldtype": "Link", "options": "Employee", "width": 140},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 220},
        {"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch", "width": 140},
    ]


def _base_row(emp_row):
    return {
        "employee": emp_row["name"],
        "employee_name": emp_row.get("employee_name"),
        "branch": emp_row.get("branch"),
    }


def _get_employees(filters):
    employee = (filters.get("employee") or "").strip() or None
    branch = (filters.get("branch") or "").strip() or None
    area_setup = (filters.get("area_setup") or "").strip() or None
    employee_status = (filters.get("employee_status") or "Active").strip() or "Active"

    branches = []
    if area_setup:
        rows = frappe.get_all(
            "Branch Selector",
            filters={"parenttype": "Area Setup", "parent": area_setup},
            fields=["branch"],
            limit_page_length=10000,
        )
        branches = [r["branch"] for r in rows if r.get("branch")]

    if branch:
        branches = list(set(branches + [branch]))

    emp_filters = {}

    if employee:
        emp_filters["name"] = employee
    elif branches:
        emp_filters["branch"] = ["in", branches]
    if employee_status and employee_status != "All":
        emp_filters["status"] = employee_status
    elif employee_status == "All":
        pass

    return frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_name", "branch", "status"],
        order_by="employee_name asc",
        limit_page_length=2000,
    )


def _get_tracking_docs(employee_ids):
    rows = frappe.get_all(
        "Employee Induction Tracking",
        filters={"employee": ["in", employee_ids]},
        fields=["name", "employee"],
        limit_page_length=10000,
    )
    return {r["employee"]: r["name"] for r in rows}


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
    rows = frappe.get_all(
        "Employee Induction",
        filters={"name": ["in", induction_ids]},
        fields=["name", "training_name"],
        limit_page_length=10000,
    )
    return {r["name"]: (r.get("training_name") or r["name"]) for r in rows}


def _build_competency_columns(induction_ids, induction_name_map):
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
