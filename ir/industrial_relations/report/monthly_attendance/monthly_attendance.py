# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from datetime import date, datetime, timedelta, time as dt_time
import calendar
from typing import Optional, Set, Dict, List, Tuple


SITE_FIELDNAME = "branch"

# Grey rule + expected(195) rule depends on this Employee field:
ATTENDANCE_DEVICE_ID_FIELDNAME = "attendance_device_id"

# Sites where ONLY Sunday is treated as weekend
SUNDAY_ONLY_WEEKEND_SITES = {"klipfontein", "gwab"}

# IR Leave Application fields (manual hours)
IR_LEAVE_APP_DOCTYPE = "Leave Application"
IR_LEAVE_EMP_FIELD = "employee_coco"
IR_LEAVE_FROM_FIELD = "from_date_coco"
IR_LEAVE_TO_FIELD = "to_date_coco"
IR_LEAVE_HOURS_FIELD = "custom_total_leave_hours"
IR_LEAVE_HALF_DAY_FIELD = "half_day_coco"

# Fixed holiday dates to apply EVERY YEAR (month, day)
FIXED_HOLIDAYS_MD: List[Tuple[int, int]] = [
    (1, 1),    # New Year's Day
    (3, 21),   # Human Rights Day
    (3, 29),   # Good Friday (fixed by request)
    (4, 1),    # Family Day (fixed by request)
    (4, 27),   # Freedom Day
    (5, 1),    # Workers' Day
    (5, 29),   # Election Day (fixed by request)
    (6, 16),   # Youth Day
    (6, 17),   # Youth Day Observed (fixed by request)
    (8, 9),    # National Women's Day
    (9, 24),   # Heritage Day
    (12, 16),  # Day of Reconciliation
    (12, 25),  # Christmas Day
    (12, 26),  # Day of Goodwill
]

# Undertime threshold (less than expected by > 10 minutes)
UNDERTIME_MINUTES = 10
UNDERTIME_HOURS = UNDERTIME_MINUTES / 60.0


def _is_weekend_for_site(site: str, d: date) -> bool:
    site_key = (site or "").strip().lower()
    # Mon=0 ... Sat=5 Sun=6
    if site_key in SUNDAY_ONLY_WEEKEND_SITES:
        return d.weekday() == 6
    return d.weekday() >= 5


def _parse_month_yyyy_mm(label: str) -> date:
    return datetime.strptime(label.strip(), "%Y-%m").date().replace(day=1)


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _get_period_16_to_15(month_first_day: date):
    prev_month_first = _add_months(month_first_day, -1)
    return prev_month_first.replace(day=16), month_first_day.replace(day=15)


def _iter_dates(start: date, end: date):
    while start <= end:
        yield start
        start = start.fromordinal(start.toordinal() + 1)


def _day_fieldname(d: date) -> str:
    return f"d_{d.year}_{d.month:02d}_{d.day:02d}"


def _fmt_num(n):
    if n is None:
        return ""
    return str(int(n)) if n == int(n) else f"{n:.1f}"


def _get_leave_field() -> Optional[str]:
    meta = frappe.get_meta("Attendance")
    for f in meta.fields:
        if f.fieldtype == "Link" and f.options == "Leave Type":
            return f.fieldname
    return None


def _leave_bucket(leave_type):
    lt = (leave_type or "").lower()

    if "annual" in lt:
        return "annual_leave_12"
    if "sick" in lt:
        return "sick_leave_12"
    if "family" in lt:
        return "family_responsibility_12"
    if "maternity" in lt:
        return "maternity_leave_12"
    if "parental" in lt:
        return "parental_leave_12"
    if "injury" in lt:
        return "injury_on_duty_12"
    if "trade union" in lt:
        return "trade_union_activities_12"
    if "unpaid" in lt or "without pay" in lt:
        return "unpaid_leave_12"
    if "study" in lt:
        return "study_leave_12"

    return None


def _get_fixed_holidays(start: date, end: date) -> Set[date]:
    out: Set[date] = set()
    for y in range(start.year, end.year + 1):
        for m, d in FIXED_HOLIDAYS_MD:
            try:
                hd = date(y, m, d)
            except ValueError:
                continue
            if start <= hd <= end:
                out.add(hd)
    return out


def _time_to_minutes(val) -> Optional[int]:
    if val is None:
        return None

    if isinstance(val, timedelta):
        total_minutes = int(val.total_seconds() // 60)
        return total_minutes % (24 * 60)

    if isinstance(val, dt_time):
        return val.hour * 60 + val.minute

    if isinstance(val, str):
        s = val.strip()
        if not s:
            return None
        parts = s.split(":")
        try:
            hh = int(parts[0])
            mm = int(parts[1]) if len(parts) > 1 else 0
            return hh * 60 + mm
        except Exception:
            return None

    return None


def _shift_daily_hours_from_shift_type(shift_type: Optional[str], cache: Dict[str, Optional[float]]) -> Optional[float]:
    if not shift_type:
        return None

    if shift_type in cache:
        return cache[shift_type]

    try:
        start_time_val, end_time_val = frappe.db.get_value("Shift Type", shift_type, ["start_time", "end_time"])
    except Exception:
        cache[shift_type] = None
        return None

    start_minutes = _time_to_minutes(start_time_val)
    end_minutes = _time_to_minutes(end_time_val)

    if start_minutes is None or end_minutes is None:
        cache[shift_type] = None
        return None

    if end_minutes < start_minutes:
        end_minutes += 24 * 60

    hours = (end_minutes - start_minutes) / 60.0
    cache[shift_type] = hours
    return hours


def _load_shift_assignments(employee_ids: List[str], start: date, end: date) -> Dict[str, List[Tuple[date, Optional[date], str]]]:
    if not employee_ids:
        return {}

    rows = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee": ["in", employee_ids],
            "status": "Active",
            "start_date": ["<=", end],
        },
        fields=["employee", "shift_type", "start_date", "end_date"],
        limit_page_length=5000,
        order_by="employee asc, start_date asc",
    )

    out: Dict[str, List[Tuple[date, Optional[date], str]]] = {}
    for r in rows:
        sd = r.start_date
        ed = r.end_date
        if ed and ed < start:
            continue
        out.setdefault(r.employee, []).append((sd, ed, r.shift_type))

    for emp, lst in out.items():
        lst.sort(key=lambda x: x[0])

    return out


def _get_shift_type_for_employee_on_date(
    employee_id: str,
    day: date,
    default_shift: Optional[str],
    assignments_by_emp: Dict[str, List[Tuple[date, Optional[date], str]]],
) -> Optional[str]:
    ass_list = assignments_by_emp.get(employee_id) or []
    for sd, ed, st in ass_list:
        if sd and day < sd:
            continue
        if ed and day > ed:
            continue
        return st
    return default_shift


def _safe_float(v) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if not s:
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def _days_inclusive(d1: date, d2: date) -> int:
    if not d1 or not d2:
        return 0
    if d2 < d1:
        return 0
    return (d2 - d1).days + 1


def _load_leave_hours_by_emp_date_for_no_shift_device_emps(
    employee_ids: List[str],
    start: date,
    end: date,
) -> Dict[Tuple[str, date], float]:
    """
    Cross-month accurate:
    - per-day = total_hours_coco / total_days(from_date..to_date)
    - apply only days inside this report period (16..15)
    Only submitted leaves (docstatus=1) are counted.
    """
    if not employee_ids:
        return {}

    if not frappe.db.exists("DocType", IR_LEAVE_APP_DOCTYPE):
        return {}

    rows = frappe.get_all(
        IR_LEAVE_APP_DOCTYPE,
        filters={
            "docstatus": 1,
            IR_LEAVE_EMP_FIELD: ["in", employee_ids],
            IR_LEAVE_FROM_FIELD: ["<=", end],
            IR_LEAVE_TO_FIELD: [">=", start],
        },
        fields=[
            IR_LEAVE_EMP_FIELD,
            IR_LEAVE_FROM_FIELD,
            IR_LEAVE_TO_FIELD,
            IR_LEAVE_HOURS_FIELD,
            IR_LEAVE_HALF_DAY_FIELD,
        ],
        limit_page_length=5000,
        order_by=f"{IR_LEAVE_EMP_FIELD} asc, {IR_LEAVE_FROM_FIELD} asc",
    )

    out: Dict[Tuple[str, date], float] = {}

    for r in rows:
        emp = getattr(r, IR_LEAVE_EMP_FIELD, None)
        if not emp:
            continue

        from_d = getattr(r, IR_LEAVE_FROM_FIELD, None)
        to_d = getattr(r, IR_LEAVE_TO_FIELD, None)
        if not from_d or not to_d:
            continue

        total_days_full = _days_inclusive(from_d, to_d)
        if total_days_full <= 0:
            continue

        total_hours = _safe_float(getattr(r, IR_LEAVE_HOURS_FIELD, None))
        if total_hours <= 0:
            continue

        per_day = total_hours / float(total_days_full)

        lo = max(from_d, start)
        hi = min(to_d, end)
        if hi < lo:
            continue

        for d in _iter_dates(lo, hi):
            key = (emp, d)
            out[key] = out.get(key, 0.0) + per_day

    return out


def execute(filters=None):
    filters = filters or {}
    month = _parse_month_yyyy_mm(filters["month"])
    site = filters["site"]
    show_totals = int(filters.get("show_totals") or 0)

    start, end = _get_period_16_to_15(month)
    dates = list(_iter_dates(start, end))
    fixed_holidays = _get_fixed_holidays(start, end)

    total_days_in_period = len(dates)

    # Ensure Employee.attendance_device_id is fetched if it exists
    emp_fields = ["name", "first_name", "last_name", "designation", "default_shift"]
    try:
        emp_meta = frappe.get_meta("Employee")
        emp_fieldnames = {f.fieldname for f in emp_meta.fields if f.fieldname}
        if ATTENDANCE_DEVICE_ID_FIELDNAME in emp_fieldnames:
            emp_fields.append(ATTENDANCE_DEVICE_ID_FIELDNAME)
    except Exception:
        pass

    employees = frappe.get_all(
        "Employee",
        filters={SITE_FIELDNAME: site, "status": "Active"},
        fields=emp_fields,
        order_by="name",
    )

    leave_field = _get_leave_field()
    att_fields = ["employee", "attendance_date", "working_hours", "status"]
    if leave_field:
        att_fields.append(leave_field)

    attendance = []
    if employees:
        attendance = frappe.get_all(
            "Attendance",
            filters={
                "employee": ["in", [e.name for e in employees]],
                "attendance_date": ["between", [start, end]],
            },
            fields=att_fields,
        )

    att_map = {(a.employee, a.attendance_date): a for a in attendance}

    employee_ids = [e.name for e in employees]
    assignments_by_emp = _load_shift_assignments(employee_ids, start, end)
    shift_hours_cache: Dict[str, Optional[float]] = {}

    # no-shift device employees get leave hours from IR Leave Application
    no_shift_device_emp_ids: List[str] = []
    for emp in employees:
        device_val = getattr(emp, ATTENDANCE_DEVICE_ID_FIELDNAME, None)
        emp_has_device = bool(device_val) and str(device_val).strip() not in ("0", "0.0")
        emp_has_no_default_shift = not bool(getattr(emp, "default_shift", None))
        emp_has_no_assignments = not bool(assignments_by_emp.get(emp.name))
        if emp_has_device and emp_has_no_default_shift and emp_has_no_assignments:
            no_shift_device_emp_ids.append(emp.name)

    leave_hours_by_emp_date = _load_leave_hours_by_emp_date_for_no_shift_device_emps(
        no_shift_device_emp_ids, start, end
    )

    today = date.today()

    columns = _build_columns(dates)
    data = []

    totals = {d: 0 for d in dates}

    totals_cols = {
        "annual_leave_12": 0,
        "sick_leave_12": 0,
        "family_responsibility_12": 0,
        "maternity_leave_12": 0,
        "parental_leave_12": 0,
        "injury_on_duty_12": 0,
        "trade_union_activities_12": 0,
        "unpaid_leave_12": 0,
        "study_leave_12": 0,
        "absent_days": 0,
    }

    for emp in employees:
        row = {
            "name": emp.first_name,
            "surname": emp.last_name,
            "occupation": emp.designation,

            "total_hours_at_work": 0,  # Total man hours + Overtime(2.0)
            "nt_hours": 0,             # N/T

            "total_payment_hours": "",

            "overtime_1_0": 0,
            "overtime_2_0": 0,

            "total_man_hours": 0,
            "total_leave_hours": 0,
            "expected_hours": "",
            **{k: 0 for k in totals_cols},
        }

        device_val = getattr(emp, ATTENDANCE_DEVICE_ID_FIELDNAME, None)
        emp_has_device = bool(device_val) and str(device_val).strip() not in ("0", "0.0")
        emp_has_no_default_shift = not bool(getattr(emp, "default_shift", None))
        emp_has_no_assignments = not bool(assignments_by_emp.get(emp.name))
        emp_is_no_shift_device = emp_has_device and emp_has_no_default_shift and emp_has_no_assignments

        shift_type_today = _get_shift_type_for_employee_on_date(
            employee_id=emp.name,
            day=today,
            default_shift=getattr(emp, "default_shift", None),
            assignments_by_emp=assignments_by_emp,
        )

        if (not shift_type_today) and emp_has_device:
            row["expected_hours"] = "195"
        else:
            expected_daily_today = _shift_daily_hours_from_shift_type(shift_type_today, shift_hours_cache)
            if shift_type_today and expected_daily_today is not None:
                expected_total = expected_daily_today * float(total_days_in_period)

                for d in dates:
                    is_weekend = _is_weekend_for_site(site, d)
                    is_holiday = d in fixed_holidays
                    if not (is_weekend or is_holiday):
                        continue

                    shift_type_on_day = _get_shift_type_for_employee_on_date(
                        employee_id=emp.name,
                        day=d,
                        default_shift=getattr(emp, "default_shift", None),
                        assignments_by_emp=assignments_by_emp,
                    )
                    expected_daily_on_day = _shift_daily_hours_from_shift_type(shift_type_on_day, shift_hours_cache)

                    if shift_type_on_day and expected_daily_on_day is not None:
                        expected_total -= expected_daily_on_day

                if expected_total < 0:
                    expected_total = 0

                row["expected_hours"] = _fmt_num(expected_total)

        # Display-only: show 0 instead of blank (no calc changes)
        if row.get("expected_hours", "") == "":
            row["expected_hours"] = "0"

        for d in dates:
            field = _day_fieldname(d)

            is_weekend = _is_weekend_for_site(site, d)
            is_holiday = d in fixed_holidays
            is_sunday = (d.weekday() == 6)

            row["is_weekend__" + field] = int(is_weekend)
            row["is_holiday__" + field] = int(is_holiday)
            row["is_overtime__" + field] = 0
            row["is_undertime__" + field] = 0
            row["is_no_shift__" + field] = 0
            row["status__" + field] = None

            att = att_map.get((emp.name, d))

            shift_type = _get_shift_type_for_employee_on_date(
                employee_id=emp.name,
                day=d,
                default_shift=getattr(emp, "default_shift", None),
                assignments_by_emp=assignments_by_emp,
            )
            expected_daily = _shift_daily_hours_from_shift_type(shift_type, shift_hours_cache)

            if emp_has_device and (not shift_type) and (not is_weekend) and (not is_holiday):
                row["is_no_shift__" + field] = 1

            if is_weekend or is_holiday:
                row[field] = "0"
                if att and att.status == "Present":
                    row[field] = _fmt_num(att.working_hours)
                    wh = att.working_hours or 0

                    if is_sunday or is_holiday:
                        row["overtime_2_0"] += wh

                    if not (is_sunday or is_holiday):
                        row["total_man_hours"] += wh

                    if expected_daily is not None and att.working_hours is not None and att.working_hours > expected_daily:
                        row["is_overtime__" + field] = 1
                continue

            if not att:
                row[field] = ""
                continue

            if att.status == "Present":
                row[field] = _fmt_num(att.working_hours)
                wh = att.working_hours or 0

                if is_sunday or is_holiday:
                    row["overtime_2_0"] += wh

                if not (is_sunday or is_holiday):
                    row["total_man_hours"] += wh

                totals[d] += wh

                if expected_daily is not None and att.working_hours is not None:
                    if att.working_hours > expected_daily:
                        row["is_overtime__" + field] = 1
                    elif att.working_hours < (expected_daily - UNDERTIME_HOURS):
                        row["is_undertime__" + field] = 1

            elif att.status == "Absent":
                row[field] = "A"
                row["status__" + field] = "Absent"
                row["absent_days"] += 1
                totals_cols["absent_days"] += 1

            elif att.status == "On Leave":
                row[field] = "L"
                row["status__" + field] = "Leave"

                leave_type_val = None
                if leave_field:
                    leave_type_val = getattr(att, leave_field, None)
                bucket = _leave_bucket(leave_type_val)
                if bucket:
                    row[bucket] += 1
                    totals_cols[bucket] += 1

                if emp_is_no_shift_device:
                    lh = leave_hours_by_emp_date.get((emp.name, d), 0.0)
                    if lh > 0:
                        row["total_leave_hours"] += lh
                else:
                    if expected_daily is not None:
                        row["total_leave_hours"] += expected_daily

        # totals
        row["total_hours_at_work"] = float(row.get("total_man_hours") or 0) + float(row.get("overtime_2_0") or 0)

        try:
            expected_val = float(row.get("expected_hours") or 0)
        except Exception:
            expected_val = 0.0

        try:
            man_val = float(row.get("total_man_hours") or 0)
        except Exception:
            man_val = 0.0

        # N/T
        row["nt_hours"] = man_val if man_val < expected_val else expected_val

        # overtime(1.0)
        diff = man_val - expected_val
        row["overtime_1_0"] = int(diff) if diff > 0 else 0

        has_shift_today = bool(shift_type_today)
        show_payment = has_shift_today or (emp_has_device and (not shift_type_today) and emp_has_no_default_shift)

        total_val = float(row.get("total_man_hours") or 0) + float(row.get("total_leave_hours") or 0)

        if show_payment:
            ot2 = float(row.get("overtime_2_0") or 0)
            ot1 = float(row.get("overtime_1_0") or 0)

            if total_val > expected_val:
                pay = (2.0 * ot2) + (1.5 * ot1) + expected_val
            else:
                pay = (2.0 * ot2) + total_val

            row["total_payment_hours"] = _fmt_num(pay)
        else:
            row["total_payment_hours"] = ""

        # Display-only: show 0 instead of blank (no calc changes)
        if row.get("total_payment_hours", "") == "":
            row["total_payment_hours"] = "0"

        data.append(row)

    if show_totals:
        total_row = {
            "name": "TOTALS",
            "surname": "",
            "occupation": "",
            "total_hours_at_work": "",
            "expected_hours": "",
            "total_payment_hours": "",
            "nt_hours": "",
            "total_man_hours": "",
            "total_leave_hours": "",
            "overtime_1_0": "",
            "overtime_2_0": "",
            **totals_cols,
        }
        for d in dates:
            field = _day_fieldname(d)
            total_row[field] = _fmt_num(totals[d]) if totals[d] else ""
        data.append(total_row)

    return columns, data


def _build_columns(dates):
    cols = [
        {"label": "Name", "fieldname": "name", "width": 120},
        {"label": "Surname", "fieldname": "surname", "width": 120},
        {"label": "Occupation", "fieldname": "occupation", "width": 150},

        # ✅ REQUIRED ORDER
        {"label": "TOTAL HOURS AT WORK", "fieldname": "total_hours_at_work", "width": 170},
        {"label": "EXPECTED HOURS", "fieldname": "expected_hours", "width": 140},
        {"label": "TOTAL PAYMENT HOURS", "fieldname": "total_payment_hours", "width": 170},
        {"label": "N/T", "fieldname": "nt_hours", "width": 90},
        {"label": "TOTAL CALCULATED HOURS", "fieldname": "total_man_hours", "width": 190},
        {"label": "LEAVE", "fieldname": "total_leave_hours", "width": 120},
        {"label": "O/TIME 1.5 AFTER 195", "fieldname": "overtime_1_0", "width": 180},
        {"label": "O/TIME 2.0", "fieldname": "overtime_2_0", "width": 120},
    ]

    for d in dates:
        cols.append({
            "label": f"{d.day}\n{d.strftime('%A')}",
            "fieldname": _day_fieldname(d),
            "width": 55,
        })

    cols.extend([
        {"label": "Annual/leave 12 hours", "fieldname": "annual_leave_12"},
        {"label": "Sick leave 12 hours/leave 12 hours", "fieldname": "sick_leave_12"},
        {"label": "Family responsibility/leave 12 hours", "fieldname": "family_responsibility_12"},
        {"label": "Maternity/leave 12 hours", "fieldname": "maternity_leave_12"},
        {"label": "Parental/leave 12 hours", "fieldname": "parental_leave_12"},
        {"label": "Injury on duty/leave 12 hours", "fieldname": "injury_on_duty_12"},
        {"label": "Trade union activities/leave 12 hours", "fieldname": "trade_union_activities_12"},
        {"label": "Unpaid leave/leave 12 hours", "fieldname": "unpaid_leave_12"},
        {"label": "Study leave/leave 12 hours", "fieldname": "study_leave_12"},
        {"label": "Absent", "fieldname": "absent_days"},
    ])

    return cols