# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Iterable, List, Optional, Tuple

import frappe
from frappe.utils import (
	add_days,
	add_to_date,
	cint,
	flt,
	get_datetime,
	getdate,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DAYS_PAST = 31
DAYS_FUTURE = 31

# Cluster check-ins occurring very close together to reduce duplicate noise.
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
# Public entrypoints
# ---------------------------------------------------------------------------

def enqueue_daily_sync() -> None:
	"""Enqueue the attendance sync on the long worker queue."""
	frappe.enqueue(
		"ir.controllers.attendance_sync.daily_sync_attendance",
		queue="long",
		job_name="ir_daily_sync_attendance",
		timeout=60 * 60,
	)


def daily_sync_attendance() -> None:
	"""
	Recompute Attendance in a window around today.

	The worklist includes:

	- dates on which Employee Checkins exist;
	- dates covered by approved Leave Applications;
	- today for all employees eligible for attendance today.

	Submitted Attendance records are never modified.
	"""
	today = getdate()
	start_date = add_days(today, -DAYS_PAST)
	end_date = add_days(today, DAYS_FUTURE)

	employees = _get_active_employees(today)

	# Build a unique worklist of (employee, attendance_date).
	worklist = set()

	for employee, attendance_date in _get_employee_checkin_days(
		start_date,
		end_date,
	):
		worklist.add((employee, attendance_date))

	for employee, attendance_date in _get_employee_leave_days(
		start_date,
		end_date,
	):
		worklist.add((employee, attendance_date))

	for employee in employees:
		worklist.add((employee, today))

	if not worklist:
		return

	for employee, attendance_date in sorted(
		worklist,
		key=lambda item: (item[0], item[1]),
	):
		try:
			recompute_attendance_for_employee_day(
				employee,
				attendance_date,
			)
		except Exception:
			# An error for one employee/date must not stop the entire sync.
			frappe.log_error(
				title="IR Attendance Sync Error",
				message=frappe.get_traceback(),
			)


def on_employee_checkin(doc, method=None) -> None:
	"""
	Recompute attendance after an Employee Checkin is inserted.
	"""
	if not getattr(doc, "employee", None):
		return

	if not getattr(doc, "time", None):
		return

	attendance_date = getdate(doc.time)

	frappe.enqueue(
		"ir.controllers.attendance_sync."
		"recompute_attendance_for_employee_day",
		queue="long",
		timeout=15 * 60,
		job_name=(
			f"ir_recompute_attendance_"
			f"{doc.employee}_{attendance_date}"
		),
		employee=doc.employee,
		attendance_date=attendance_date,
	)


def on_leave_application_change(doc, method=None) -> None:
	"""
	Recompute attendance when a Leave Application is submitted, cancelled,
	or updated after submission.
	"""
	if not getattr(doc, "employee", None):
		return

	from_date = (
		getdate(doc.from_date)
		if getattr(doc, "from_date", None)
		else None
	)
	to_date = (
		getdate(doc.to_date)
		if getattr(doc, "to_date", None)
		else None
	)

	if not from_date or not to_date:
		return

	frappe.enqueue(
		"ir.controllers.attendance_sync."
		"recompute_attendance_for_employee_range",
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

def recompute_attendance_for_employee_range(
	employee: str,
	start_date,
	end_date,
) -> None:
	"""
	Recompute Attendance for every date in the inclusive range.
	"""
	current_date = getdate(start_date)
	last_date = getdate(end_date)

	while current_date <= last_date:
		recompute_attendance_for_employee_day(
			employee,
			current_date,
		)
		current_date = add_days(current_date, 1)


def recompute_attendance_for_employee_day(
	employee: str,
	attendance_date,
) -> None:
	"""
	Compute and upsert Attendance for one employee and date.

	Rules:

	- do nothing outside the employee's employment period;
	- do not modify submitted Attendance;
	- do not modify cancelled Attendance;
	- update draft Attendance;
	- create draft Attendance where none exists.
	"""
	attendance_date = getdate(attendance_date)

	if not _is_employee_active_on_date(
		employee,
		attendance_date,
	):
		return

	shift_assignment = _get_shift_assignment(
		employee,
		attendance_date,
	)
	shift_type = _get_shift_type_for_assignment(
		shift_assignment,
	)

	work = _compute_work_from_checkins(
		employee=employee,
		attendance_date=attendance_date,
		shift_assignment=shift_assignment,
		shift_type=shift_type,
	)

	leave_info = _get_leave_info(
		employee,
		attendance_date,
	)

	status, leave_type, leave_application = (
		_derive_status_from_leave_and_hours(
			leave_info=leave_info,
			total_hours=work.total_hours,
		)
	)

	_upsert_attendance(
		employee=employee,
		attendance_date=attendance_date,
		shift=(
			shift_assignment.shift_type
			if shift_assignment
			else None
		),
		status=status,
		working_hours=work.total_hours,
		in_time=work.first_in,
		out_time=work.last_out,
		late_entry=work.late_entry,
		early_exit=work.early_exit,
		leave_type=leave_type,
		leave_application=leave_application,
	)


# ---------------------------------------------------------------------------
# Attendance upsert
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
	"""
	Create or update a draft Attendance record.

	Submitted and cancelled records are left unchanged.
	"""
	attendance_date = getdate(attendance_date)

	existing = frappe.db.get_value(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": attendance_date,
		},
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
		attendance = frappe.get_doc(
			{
				"doctype": "Attendance",
				**values,
			}
		)
		attendance.insert(ignore_permissions=True)
		return

	# Never modify submitted or cancelled Attendance.
	if cint(existing.docstatus) in (1, 2):
		return

	attendance = frappe.get_doc(
		"Attendance",
		existing.name,
	)

	for fieldname, value in values.items():
		if fieldname in (
			"employee",
			"attendance_date",
		):
			continue

		attendance.set(fieldname, value)

	attendance.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Status logic
# ---------------------------------------------------------------------------

def _derive_status_from_leave_and_hours(
	leave_info,
	total_hours: float,
) -> Tuple[str, Optional[str], Optional[str]]:
	"""
	Derive Attendance status from leave and working hours.

	Approved leave takes precedence over check-in hours.
	"""
	if leave_info:
		leave_type = leave_info.get("leave_type")

		# Preserve the existing behaviour whereby this special leave type
		# does not cause the attendance status to become On Leave.
		if leave_type != "Cancellation of Leave":
			is_half_day = cint(leave_info.get("half_day"))
			half_day_date = leave_info.get("half_day_date")
			attendance_date = leave_info.get("attendance_date")

			if (
				is_half_day
				and half_day_date
				and getdate(half_day_date)
				== getdate(attendance_date)
			):
				return (
					"Half Day",
					leave_type,
					leave_info.get("name"),
				)

			return (
				"On Leave",
				leave_type,
				leave_info.get("name"),
			)

	if flt(total_hours) > 0:
		return "Present", None, None

	return "Absent", None, None


def _get_leave_info(
	employee: str,
	attendance_date,
):
	"""
	Return the latest approved Leave Application covering the date.
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

	leave_info = rows[0]
	leave_info["attendance_date"] = attendance_date

	return leave_info


# ---------------------------------------------------------------------------
# Shift and check-in computation
# ---------------------------------------------------------------------------

def _compute_work_from_checkins(
	employee: str,
	attendance_date,
	shift_assignment,
	shift_type,
) -> WorkResult:
	"""
	Compute working hours, first IN, last OUT, late entry, and early exit.
	"""
	result = WorkResult()

	(
		window_start,
		window_end,
		shift_start,
		shift_end,
	) = _get_shift_window(
		attendance_date=attendance_date,
		shift_assignment=shift_assignment,
		shift_type=shift_type,
	)

	checkins = _get_employee_checkins(
		employee,
		window_start,
		window_end,
	)

	if not checkins:
		return result

	checkins = _cluster_checkins(
		checkins,
		seconds=CLUSTER_SECONDS,
	)
	checkins = _normalize_log_types(checkins)

	(
		total_seconds,
		first_in,
		last_out,
	) = _sum_intervals(checkins)

	result.total_hours = flt(total_seconds) / 3600.0
	result.first_in = first_in
	result.last_out = last_out

	if shift_type and first_in and shift_start:
		late_grace_minutes = cint(
			getattr(
				shift_type,
				"late_entry_grace_period",
				0,
			)
			or 0
		)

		latest_allowed_in = add_to_date(
			shift_start,
			minutes=late_grace_minutes,
		)

		result.late_entry = cint(
			first_in > latest_allowed_in
		)

	if shift_type and last_out and shift_end:
		early_exit_grace_minutes = cint(
			getattr(
				shift_type,
				"early_exit_grace_period",
				0,
			)
			or 0
		)

		earliest_allowed_out = add_to_date(
			shift_end,
			minutes=-early_exit_grace_minutes,
		)

		result.early_exit = cint(
			last_out < earliest_allowed_out
		)

	return result


def _get_shift_window(
	attendance_date,
	shift_assignment,
	shift_type,
):
	"""
	Return the check-in window and scheduled shift bounds.

	When no Shift Assignment is available, the entire calendar day is used.
	"""
	attendance_date = getdate(attendance_date)

	window_start = get_datetime(
		f"{attendance_date} 00:00:00"
	)
	window_end = get_datetime(
		f"{attendance_date} 23:59:59"
	)

	shift_start = None
	shift_end = None

	if not shift_assignment or not shift_type:
		return (
			window_start,
			window_end,
			shift_start,
			shift_end,
		)

	start_time = getattr(
		shift_type,
		"start_time",
		None,
	)
	end_time = getattr(
		shift_type,
		"end_time",
		None,
	)

	if not start_time or not end_time:
		return (
			window_start,
			window_end,
			shift_start,
			shift_end,
		)

	shift_start = _combine_date_time(
		attendance_date,
		start_time,
	)
	shift_end = _combine_date_time(
		attendance_date,
		end_time,
	)

	# Overnight shifts finish on the following calendar day.
	if shift_end <= shift_start:
		shift_end += timedelta(days=1)

	begin_before_minutes = cint(
		getattr(
			shift_type,
			"begin_check_in_before_shift_start_time",
			0,
		)
		or 0
	)
	allow_after_minutes = cint(
		getattr(
			shift_type,
			"allow_check_out_after_shift_end_time",
			0,
		)
		or 0
	)

	window_start = shift_start - timedelta(
		minutes=begin_before_minutes
	)
	window_end = shift_end + timedelta(
		minutes=allow_after_minutes
	)

	return (
		window_start,
		window_end,
		shift_start,
		shift_end,
	)


def _combine_date_time(
	date_value,
	time_value: time,
) -> datetime:
	"""Combine a date value and time value into a datetime."""
	return datetime.combine(
		getdate(date_value),
		time_value,
	)


def _get_employee_checkins(
	employee: str,
	start_datetime: datetime,
	end_datetime: datetime,
) -> List[dict]:
	"""Return Employee Checkins in chronological order."""
	return frappe.get_all(
		"Employee Checkin",
		filters={
			"employee": employee,
			"time": (
				"between",
				[
					start_datetime,
					end_datetime,
				],
			),
		},
		fields=[
			"name",
			"time",
			"log_type",
		],
		order_by="time asc",
	)


def _cluster_checkins(
	checkins: List[dict],
	seconds: int = CLUSTER_SECONDS,
) -> List[dict]:
	"""
	Keep the first check-in in each duplicate/noise cluster.
	"""
	if not checkins:
		return []

	clustered = [checkins[0]]
	last_kept_time = get_datetime(
		checkins[0]["time"]
	)

	for checkin in checkins[1:]:
		current_time = get_datetime(
			checkin["time"]
		)

		elapsed_seconds = (
			current_time - last_kept_time
		).total_seconds()

		if elapsed_seconds > seconds:
			clustered.append(checkin)
			last_kept_time = current_time

	return clustered


def _normalize_log_types(
	checkins: List[dict],
) -> List[dict]:
	"""
	Normalize check-ins to a deterministic alternating IN/OUT sequence.

	The first retained check-in is treated as IN, the second as OUT, and so on.
	"""
	if not checkins:
		return []

	expected_log_type = "IN"

	for checkin in checkins:
		checkin["log_type"] = expected_log_type

		expected_log_type = (
			"OUT"
			if expected_log_type == "IN"
			else "IN"
		)

	return checkins


def _sum_intervals(
	checkins: List[dict],
) -> Tuple[
	int,
	Optional[datetime],
	Optional[datetime],
]:
	"""
	Sum valid IN-to-OUT intervals.

	Returns:

	- total seconds;
	- first IN time;
	- last completed OUT time.
	"""
	total_seconds = 0
	first_in = None
	last_out = None
	open_in_time = None

	for checkin in checkins:
		checkin_time = get_datetime(
			checkin["time"]
		)

		if checkin["log_type"] == "IN":
			open_in_time = checkin_time

			if first_in is None:
				first_in = checkin_time

			continue

		if open_in_time is not None:
			total_seconds += int(
				(
					checkin_time - open_in_time
				).total_seconds()
			)
			last_out = checkin_time

		open_in_time = None

	return (
		total_seconds,
		first_in,
		last_out,
	)


# ---------------------------------------------------------------------------
# Shift Assignment helpers
# ---------------------------------------------------------------------------

def _get_shift_assignment(
	employee: str,
	attendance_date,
):
	"""
	Return the latest submitted, active Shift Assignment covering the date.

	Shift Assignment links to Shift Type through the `shift_type` field.
	An empty end date is treated as an open-ended assignment.
	"""
	attendance_date = getdate(attendance_date)

	assignments = frappe.get_all(
		"Shift Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"status": "Active",
			"start_date": (
				"<=",
				attendance_date,
			),
		},
		or_filters=[
			[
				"end_date",
				"is",
				"not set",
			],
			[
				"end_date",
				">=",
				attendance_date,
			],
		],
		fields=[
			"name",
			"shift_type",
			"start_date",
			"end_date",
		],
		order_by=(
			"start_date desc, "
			"creation desc"
		),
		limit=1,
	)

	if not assignments:
		return None

	return frappe._dict(assignments[0])


def _get_shift_type_for_assignment(
	shift_assignment,
):
	"""Return the Shift Type document linked to a Shift Assignment."""
	if not shift_assignment:
		return None

	if not shift_assignment.shift_type:
		return None

	try:
		return frappe.get_cached_doc(
			"Shift Type",
			shift_assignment.shift_type,
		)
	except frappe.DoesNotExistError:
		return None


# ---------------------------------------------------------------------------
# Employee helpers
# ---------------------------------------------------------------------------

def _get_active_employees(
	attendance_date=None,
) -> List[str]:
	"""
	Return employees eligible for Attendance on the requested date.
	"""
	attendance_date = getdate(attendance_date)

	return frappe.get_all(
		"Employee",
		filters={
			"status": "Active",
			"date_of_joining": (
				"<=",
				attendance_date,
			),
		},
		or_filters=[
			[
				"relieving_date",
				"is",
				"not set",
			],
			[
				"relieving_date",
				">=",
				attendance_date,
			],
		],
		pluck="name",
	)


def _is_employee_active_on_date(
	employee: str,
	attendance_date,
) -> bool:
	"""
	Return whether an employee is eligible for Attendance on the date.

	An employee may already have status Active while their joining date is
	still in the future, so status alone is insufficient.
	"""
	attendance_date = getdate(attendance_date)

	employee_details = frappe.db.get_value(
		"Employee",
		employee,
		[
			"status",
			"date_of_joining",
			"relieving_date",
		],
		as_dict=True,
	)

	if not employee_details:
		return False

	if employee_details.status != "Active":
		return False

	if employee_details.date_of_joining:
		joining_date = getdate(
			employee_details.date_of_joining
		)

		if attendance_date < joining_date:
			return False

	if employee_details.relieving_date:
		relieving_date = getdate(
			employee_details.relieving_date
		)

		if attendance_date > relieving_date:
			return False

	return True


def _get_employee_checkin_days(
	start_date,
	end_date,
) -> Iterable[Tuple[str, object]]:
	"""
	Return unique employee/date pairs for check-ins in the date range.
	"""
	start_datetime = get_datetime(
		f"{getdate(start_date)} 00:00:00"
	)
	end_datetime = get_datetime(
		f"{getdate(end_date)} 23:59:59"
	)

	rows = frappe.db.sql(
		"""
		SELECT
			employee,
			DATE(`time`) AS attendance_date
		FROM `tabEmployee Checkin`
		WHERE `time` BETWEEN %s AND %s
			AND employee IS NOT NULL
			AND employee != ''
		GROUP BY
			employee,
			DATE(`time`)
		""",
		(
			start_datetime,
			end_datetime,
		),
		as_dict=True,
	)

	for row in rows:
		yield (
			row["employee"],
			getdate(row["attendance_date"]),
		)


def _get_employee_leave_days(
	start_date,
	end_date,
) -> Iterable[Tuple[str, object]]:
	"""
	Return employee/date pairs covered by approved Leave Applications.
	"""
	start_date = getdate(start_date)
	end_date = getdate(end_date)

	leave_applications = frappe.get_all(
		"Leave Application",
		filters={
			"docstatus": 1,
			"status": "Approved",
			"from_date": (
				"<=",
				end_date,
			),
			"to_date": (
				">=",
				start_date,
			),
		},
		fields=[
			"employee",
			"from_date",
			"to_date",
		],
	)

	for leave_application in leave_applications:
		employee = leave_application.get("employee")

		if not employee:
			continue

		first_date = max(
			getdate(
				leave_application["from_date"]
			),
			start_date,
		)
		last_date = min(
			getdate(
				leave_application["to_date"]
			),
			end_date,
		)

		current_date = first_date

		while current_date <= last_date:
			yield employee, current_date
			current_date = add_days(
				current_date,
				1,
			)