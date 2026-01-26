# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time
from typing import Iterable, List, Optional, Tuple

import frappe
from frappe.utils import (
	add_days,
	add_to_date,
	cint,
	flt,
	get_datetime,
	getdate,
	now_datetime,
)
from frappe import _


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DAYS_PAST = 31
DAYS_FUTURE = 31

# Your old script clustered checkins that occur very close together to reduce noise.
CLUSTER_SECONDS = 120


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class WorkResult:
	total_hours: float = 0.0
	first_in: Optional[datetime] = None
	last_out: Optional[datetime] = None
	late_entry: int = 0
	early_exit: int = 0


# ---------------------------------------------------------------------------
# Public entrypoints (hooks)
# ---------------------------------------------------------------------------

def enqueue_daily_sync() -> None:
	"""Scheduler entrypoint: enqueue the heavy sync onto the long queue."""
	# Keep scheduler execution fast; do the actual work in long worker.
	frappe.enqueue(
		"ir.controllers.attendance_sync.daily_sync_attendance",
		queue="long",
		job_name="ir_daily_sync_attendance",
		timeout=60 * 60,  # 60 minutes
	)


def daily_sync_attendance() -> None:
	"""
	Daily recompute Attendance in a window around today.
	- Includes days with checkins
	- Includes days covered by leave applications
	- Includes today for all active employees
	- Upserts Attendance but DOES NOT modify submitted Attendance
	"""
	today = getdate()
	start_date = add_days(today, -DAYS_PAST)
	end_date = add_days(today, DAYS_FUTURE)

	employees = _get_active_employees()
	if not employees:
		return

	# Build worklist: (employee, date)
	worklist = set()

	# 1) Dates where checkins exist
	for emp, att_date in _get_employee_checkin_days(start_date, end_date):
		worklist.add((emp, att_date))

	# 2) Dates covered by approved leave applications (even if no checkins)
	for emp, att_date in _get_employee_leave_days(start_date, end_date):
		worklist.add((emp, att_date))

	# 3) Ensure today is considered for everyone (useful for same-day checkins)
	for emp in employees:
		worklist.add((emp, today))

	# Process
	for emp, att_date in sorted(worklist, key=lambda x: (x[0], x[1])):
		try:
			recompute_attendance_for_employee_day(emp, att_date)
		except Exception:
			# Don't kill the whole job; log and continue.
			frappe.log_error(
				title="IR Attendance Sync Error",
				message=frappe.get_traceback(),
			)


def on_employee_checkin(doc, method=None) -> None:
	"""
	Hook: Employee Checkin after_insert.
	Recompute attendance for the checkin's employee and date.
	"""
	if not getattr(doc, "employee", None) or not getattr(doc, "time", None):
		return

	att_date = getdate(doc.time)
	frappe.enqueue(
		"ir.controllers.attendance_sync.recompute_attendance_for_employee_day",
		queue="long",
		timeout=15 * 60,
		job_name=f"ir_recompute_attendance_{doc.employee}_{att_date}",
		employee=doc.employee,
		attendance_date=att_date,
	)


def on_leave_application_change(doc, method=None) -> None:
	"""
	Hook: Leave Application on_submit / on_cancel / on_update_after_submit.
	Recompute attendance for the employee across the leave's date range.
	"""
	if not getattr(doc, "employee", None):
		return

	from_date = getdate(doc.from_date) if getattr(doc, "from_date", None) else None
	to_date = getdate(doc.to_date) if getattr(doc, "to_date", None) else None
	if not from_date or not to_date:
		return

	# Enqueue range recomputation on long queue
	frappe.enqueue(
		"ir.controllers.attendance_sync.recompute_attendance_for_employee_range",
		queue="long",
		timeout=30 * 60,
		job_name=f"ir_recompute_attendance_leave_{doc.name}",
		employee=doc.employee,
		start_date=from_date,
		end_date=to_date,
	)


# ---------------------------------------------------------------------------
# Core recompute logic
# ---------------------------------------------------------------------------

def recompute_attendance_for_employee_range(employee: str, start_date, end_date) -> None:
	"""Recompute Attendance for employee for each day in [start_date, end_date]."""
	start = getdate(start_date)
	end = getdate(end_date)
	cur = start
	while cur <= end:
		recompute_attendance_for_employee_day(employee, cur)
		cur = add_days(cur, 1)


def recompute_attendance_for_employee_day(employee: str, attendance_date) -> None:
	"""
	Compute derived attendance fields for one employee/day and upsert to HRMS Attendance.

	Important constraints:
	- If Attendance exists and is SUBMITTED (docstatus=1): DO NOT UPDATE
	- If Attendance exists and is DRAFT (docstatus=0): update derived fields
	- If Attendance does not exist: create DRAFT Attendance
	"""
	attendance_date = getdate(attendance_date)

	# If the employee is not active, skip.
	if not _is_employee_active(employee):
		return

	# Determine shift + shift type
	shift_assignment = _get_shift_assignment(employee, attendance_date)
	shift_type = _get_shift_type_for_assignment(shift_assignment)

	# Compute work metrics from checkins (shift-window aware)
	work = _compute_work_from_checkins(
		employee=employee,
		attendance_date=attendance_date,
		shift_assignment=shift_assignment,
		shift_type=shift_type,
	)

	# Determine leave status (read-only from Leave Application)
	leave_info = _get_leave_info(employee, attendance_date)

	status, leave_type, leave_app = _derive_status_from_leave_and_hours(
		leave_info=leave_info,
		total_hours=work.total_hours,
	)

	# Upsert Attendance (draft-only updates)
	_upsert_attendance(
		employee=employee,
		attendance_date=attendance_date,
		shift=shift_assignment.shift if shift_assignment else None,
		status=status,
		working_hours=work.total_hours,
		in_time=work.first_in,
		out_time=work.last_out,
		late_entry=work.late_entry,
		early_exit=work.early_exit,
		leave_type=leave_type,
		leave_application=leave_app,
	)


# ---------------------------------------------------------------------------
# Attendance upsert (NO updates to submitted docs)
# ---------------------------------------------------------------------------

def _upsert_attendance(
	employee: str,
	attendance_date,
	shift: Optional[str],
	status: str,
	working_hours: float,
	in_time: Optional[datetime],
	out_time: Optional[datetime],
	late_entry: int,
	early_exit: int,
	leave_type: Optional[str],
	leave_application: Optional[str],
) -> None:
	attendance_date = getdate(attendance_date)

	existing = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": attendance_date},
		["name", "docstatus"],
		as_dict=True,
	)

	values = {
		"employee": employee,
		"attendance_date": attendance_date,
		"status": status,
		"shift": shift,
		"working_hours": flt(working_hours),
		"in_time": in_time,
		"out_time": out_time,
		"late_entry": cint(late_entry),
		"early_exit": cint(early_exit),
		"leave_type": leave_type,
		"leave_application": leave_application,
	}

	if not existing:
		# Create DRAFT Attendance
		doc = frappe.get_doc({"doctype": "Attendance", **values})
		# Let HRMS validations run
		doc.insert(ignore_permissions=True)
		return

	# If submitted, never touch it
	if cint(existing.docstatus) == 1:
		return

	# If cancelled, do nothing (usually means it was intentionally cancelled)
	if cint(existing.docstatus) == 2:
		return

	# Draft: update
	doc = frappe.get_doc("Attendance", existing.name)
	for k, v in values.items():
		# don't overwrite identity fields
		if k in ("employee", "attendance_date"):
			continue
		doc.set(k, v)
	doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Status logic (Leave Application + hours)
# ---------------------------------------------------------------------------

def _derive_status_from_leave_and_hours(leave_info, total_hours: float) -> Tuple[str, Optional[str], Optional[str]]:
	"""
	Leave-first policy:
	- If approved leave overlaps: On Leave / Half Day
	- Else: Present if hours > 0 else Absent
	"""
	if leave_info:
		if leave_info.get("leave_type") == "Cancellation of Leave":
			# Keep your prior "cancellation leave type cancels leave" behaviour,
			# but without touching Leave Application.
			pass
		else:
			if cint(leave_info.get("half_day")) and leave_info.get("half_day_date") and getdate(leave_info.get("half_day_date")) == leave_info.get("attendance_date"):
				return "Half Day", leave_info.get("leave_type"), leave_info.get("name")
			return "On Leave", leave_info.get("leave_type"), leave_info.get("name")

	# No effective leave
	if flt(total_hours) > 0:
		return "Present", None, None

	return "Absent", None, None


def _get_leave_info(employee: str, attendance_date):
	"""
	Read-only equivalent of HRMS leave overlap logic, using Leave Application.
	Returns a dict or None.
	"""
	attendance_date = getdate(attendance_date)

	rows = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Approved",
			"from_date": ("<=", attendance_date),
			"to_date": (">=", attendance_date),
		},
		fields=[
			"name",
			"leave_type",
			"half_day",
			"half_day_date",
			"from_date",
			"to_date",
		],
		order_by="modified desc",
		limit=1,
	)

	if not rows:
		return None

	row = rows[0]
	row["attendance_date"] = attendance_date
	return row


# ---------------------------------------------------------------------------
# Shift + checkin computation
# ---------------------------------------------------------------------------

def _compute_work_from_checkins(employee: str, attendance_date, shift_assignment, shift_type) -> WorkResult:
	"""
	Computes:
	- working hours (sum of in/out)
	- first_in_time / last_out_time
	- late_entry / early_exit based on grace periods
	"""
	res = WorkResult()

	# If there is no shift, fall back to using the whole day as a window
	start_dt, end_dt, shift_start_dt, shift_end_dt = _get_shift_window(
		attendance_date=attendance_date,
		shift_assignment=shift_assignment,
		shift_type=shift_type,
	)

	checkins = _get_employee_checkins(employee, start_dt, end_dt)
	if not checkins:
		return res

	# Reduce noise
	checkins = _cluster_checkins(checkins, seconds=CLUSTER_SECONDS)

	# Normalize log types to alternate IN/OUT
	checkins = _normalize_log_types(checkins)

	# Sum IN->OUT
	total_seconds, first_in, last_out = _sum_intervals(checkins)

	res.total_hours = flt(total_seconds) / 3600.0
	res.first_in = first_in
	res.last_out = last_out

	# Late / early flags
	if shift_type and first_in and shift_start_dt:
		grace = cint(getattr(shift_type, "late_entry_grace_period", 0) or 0)
		allowed = add_to_date(shift_start_dt, minutes=grace)
		res.late_entry = 1 if first_in > allowed else 0

	if shift_type and last_out and shift_end_dt:
		grace = cint(getattr(shift_type, "early_exit_grace_period", 0) or 0)
		allowed = add_to_date(shift_end_dt, minutes=-grace)
		res.early_exit = 1 if last_out < allowed else 0

	return res


def _get_shift_window(attendance_date, shift_assignment, shift_type):
	"""
	Return:
	- start_dt / end_dt: window to fetch checkins
	- shift_start_dt / shift_end_dt: scheduled shift bounds for late/early checks
	"""
	attendance_date = getdate(attendance_date)

	# Default window: whole day
	start_dt = get_datetime(f"{attendance_date} 00:00:00")
	end_dt = get_datetime(f"{attendance_date} 23:59:59")
	shift_start_dt = None
	shift_end_dt = None

	if not shift_assignment or not shift_type:
		return start_dt, end_dt, shift_start_dt, shift_end_dt

	# shift_type.start_time / end_time are time objects in HRMS Shift Type
	st = getattr(shift_type, "start_time", None)
	et = getattr(shift_type, "end_time", None)

	if st and et:
		shift_start_dt = _combine_date_time(attendance_date, st)
		shift_end_dt = _combine_date_time(attendance_date, et)

		# Handle overnight shifts
		if shift_end_dt <= shift_start_dt:
			shift_end_dt = shift_end_dt + timedelta(days=1)

		# Window expansion: begin_check_in_before_shift_start_time / allow_check_out_after_shift_end_time
		begin_before = cint(getattr(shift_type, "begin_check_in_before_shift_start_time", 0) or 0)
		allow_after = cint(getattr(shift_type, "allow_check_out_after_shift_end_time", 0) or 0)

		start_dt = shift_start_dt - timedelta(minutes=begin_before)
		end_dt = shift_end_dt + timedelta(minutes=allow_after)

	return start_dt, end_dt, shift_start_dt, shift_end_dt


def _combine_date_time(d, t: time) -> datetime:
	return datetime.combine(getdate(d), t)


def _get_employee_checkins(employee: str, start_dt: datetime, end_dt: datetime) -> List[dict]:
	return frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": ("between", [start_dt, end_dt]),
		},
		fields=["name", "time", "log_type"],
		order_by="time asc",
	)


def _cluster_checkins(checkins: List[dict], seconds: int = 120) -> List[dict]:
	"""
	Keep first checkin of a cluster; drop subsequent checkins within `seconds`.
	"""
	if not checkins:
		return []

	out = [checkins[0]]
	last_time = get_datetime(checkins[0]["time"])

	for row in checkins[1:]:
		cur = get_datetime(row["time"])
		if (cur - last_time).total_seconds() > seconds:
			out.append(row)
			last_time = cur

	return out


def _normalize_log_types(checkins: List[dict]) -> List[dict]:
	"""
	Force alternating IN/OUT sequence.
	If log types are missing or repeated, we correct them deterministically.
	"""
	if not checkins:
		return []

	expected = "IN"
	for row in checkins:
		lt = (row.get("log_type") or "").upper()
		if lt not in ("IN", "OUT"):
			lt = expected

		# If repeated, flip to expected
		if lt != expected:
			lt = expected

		row["log_type"] = lt
		expected = "OUT" if expected == "IN" else "IN"

	return checkins


def _sum_intervals(checkins: List[dict]) -> Tuple[int, Optional[datetime], Optional[datetime]]:
	"""
	Sum IN->OUT durations.
	Returns (total_seconds, first_in_time, last_out_time)
	"""
	total = 0
	first_in = None
	last_out = None

	in_time = None

	for row in checkins:
		t = get_datetime(row["time"])
		if row["log_type"] == "IN":
			in_time = t
			if not first_in:
				first_in = t
		else:
			if in_time:
				total += int((t - in_time).total_seconds())
				last_out = t
			in_time = None

	return total, first_in, last_out


# ---------------------------------------------------------------------------
# Shift assignment helpers
# ---------------------------------------------------------------------------

def _get_shift_assignment(employee: str, attendance_date):
	"""
	Return an object-like dict with .shift and .shift_type (via Shift Type link).
	HRMS uses Shift Assignment (employee/date range -> shift).
	"""
	attendance_date = getdate(attendance_date)

	row = frappe.db.get_value(
		"Shift Assignment",
		{
			"employee": employee,
			"docstatus": 1,
			"start_date": ("<=", attendance_date),
			"end_date": (">=", attendance_date),
		},
		["name", "shift"],
		as_dict=True,
	)

	if not row:
		return None

	# Convert to a simple object-like structure
	return frappe._dict(row)


def _get_shift_type_for_assignment(shift_assignment):
	if not shift_assignment or not shift_assignment.shift:
		return None

	# In HRMS, Shift Type doctype is typically "Shift Type" and linked from shift name.
	# Sometimes the shift itself is a Shift Type. We'll assume the link is Shift Type.
	try:
		return frappe.get_cached_doc("Shift Type", shift_assignment.shift)
	except Exception:
		return None


# ---------------------------------------------------------------------------
# Employee helpers
# ---------------------------------------------------------------------------

def _get_active_employees() -> List[str]:
	return frappe.get_all("Employee", filters={"status": "Active"}, pluck="name")


def _is_employee_active(employee: str) -> bool:
	return frappe.db.get_value("Employee", employee, "status") == "Active"


def _get_employee_checkin_days(start_date, end_date) -> Iterable[Tuple[str, object]]:
	"""
	Return unique (employee, date) for checkins between [start_date, end_date].
	"""
	start_dt = get_datetime(f"{getdate(start_date)} 00:00:00")
	end_dt = get_datetime(f"{getdate(end_date)} 23:59:59")

	rows = frappe.db.sql(
		"""
		select employee, date(`time`) as d
		from `tabEmployee Checkin`
		where `time` between %s and %s
		group by employee, date(`time`)
		""",
		(start_dt, end_dt),
		as_dict=True,
	)

	for r in rows:
		yield r["employee"], getdate(r["d"])


def _get_employee_leave_days(start_date, end_date) -> Iterable[Tuple[str, object]]:
	"""
	Return (employee, date) pairs for each day covered by approved leave applications
	overlapping the window.
	"""
	start_date = getdate(start_date)
	end_date = getdate(end_date)

	leaves = frappe.get_all(
		"Leave Application",
		filters={
			"docstatus": 1,
			"status": "Approved",
			"from_date": ("<=", end_date),
			"to_date": (">=", start_date),
		},
		fields=["employee", "from_date", "to_date"],
	)

	for lv in leaves:
		emp = lv["employee"]
		fd = max(getdate(lv["from_date"]), start_date)
		td = min(getdate(lv["to_date"]), end_date)

		cur = fd
		while cur <= td:
			yield emp, cur
			cur = add_days(cur, 1)
