# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import calendar as _calendar
import json
from collections import defaultdict
from datetime import date as _date
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import add_months, cint, flt, formatdate, getdate, nowdate


SHIFT_DESIGN = "Shift Design"
TABLE_FIELDS = (
	"shift_types",
	"teams",
	"pattern",
	"calendar_rules",
	"date_overrides",
)


@frappe.whitelist()
def get_bootstrap():
	_check_permission("read")

	return {
		"designs": list_designs(),
		"companies": _names("Company", group_filter=True),
		"shift_types": _shift_type_options(),
		"can_create": frappe.has_permission(
			SHIFT_DESIGN,
			ptype="create",
		),
		"parent_fields": _fieldnames(SHIFT_DESIGN),
		"shift_type_fields": _child_fieldnames(SHIFT_DESIGN, "shift_types"),
		"team_fields": _child_fieldnames(SHIFT_DESIGN, "teams"),
		"pattern_fields": _child_fieldnames(SHIFT_DESIGN, "pattern"),
		"calendar_rule_fields": _child_fieldnames(
			SHIFT_DESIGN,
			"calendar_rules",
		),
		"date_override_fields": _child_fieldnames(
			SHIFT_DESIGN,
			"date_overrides",
		),
	}


@frappe.whitelist()
def list_designs():
	_check_permission("read")
	meta = frappe.get_meta(SHIFT_DESIGN)

	candidate_fields = (
		"name",
		"design_name",
		"branch",
		"company",
		"status",
		"enabled",
		"effective_from",
		"effective_until",
		"number_of_teams",
		"cycle_length",
		"anchor_date",
		"pay_period_start_day",
		"pay_period_end_day",
		"modified",
	)

	fields = [
		fieldname
		for fieldname in candidate_fields
		if fieldname in {"name", "modified"}
		or meta.has_field(fieldname)
	]

	return frappe.get_all(
		SHIFT_DESIGN,
		fields=fields,
		order_by="modified desc",
		limit_page_length=500,
	)


@frappe.whitelist()
def get_design(name):
	if not name:
		frappe.throw(_("Shift Design is required."))

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("read")
	return _serialize(doc)


@frappe.whitelist()
def save_design(data):
	payload = _json_object(data)
	name = _clean(payload.get("name"))

	if name:
		doc = frappe.get_doc(SHIFT_DESIGN, name)
		doc.check_permission("write")
	else:
		if not frappe.has_permission(SHIFT_DESIGN, ptype="create"):
			frappe.throw(
				_("You do not have permission to create Shift Designs."),
				frappe.PermissionError,
			)
		doc = frappe.new_doc(SHIFT_DESIGN)

	meta = frappe.get_meta(SHIFT_DESIGN)

	for fieldname, value in payload.items():
		if fieldname in TABLE_FIELDS or fieldname == "name":
			continue
		if meta.has_field(fieldname):
			doc.set(fieldname, value)

	for table_fieldname in TABLE_FIELDS:
		table_field = meta.get_field(table_fieldname)
		if not table_field or not table_field.options:
			continue

		doc.set(table_fieldname, [])
		for row in payload.get(table_fieldname) or []:
			if not isinstance(row, dict):
				continue
			doc.append(
				table_fieldname,
				_clean_child_payload(row, table_field.options),
			)

	if doc.is_new():
		doc.insert()
	else:
		doc.save()

	return {
		"design": _serialize(doc),
		"designs": list_designs(),
	}


@frappe.whitelist()
def delete_design(name):
	if not name:
		frappe.throw(_("Shift Design is required."))

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("delete")
	frappe.delete_doc(SHIFT_DESIGN, name)

	return {"designs": list_designs()}


@frappe.whitelist()
def get_sa_public_holidays(start_date, end_date):
	if not start_date or not end_date:
		return []

	start = getdate(start_date)
	end = getdate(end_date)

	if end < start:
		frappe.throw(_("Simulation End cannot be before Simulation Start."))

	years = list(range(start.year, end.year + 1))

	try:
		from holidays import country_holidays

		za_holidays = country_holidays("ZA", years=years)
		return [
			{
				"date": str(getdate(holiday_date)),
				"description": holiday_name,
			}
			for holiday_date, holiday_name in za_holidays.items()
			if start <= getdate(holiday_date) <= end
		]
	except Exception as exc:
		frappe.log_error(
			title="Shift Designer public holiday generation failed",
			message=frappe.get_traceback(),
		)
		frappe.throw(
			_(
				"Unable to generate South African public holidays. "
				"Please confirm that the Python 'holidays' package is installed. "
				"Original error: {0}"
			).format(exc)
		)


@frappe.whitelist()
def export_shift_design_excel(name, range_start=None, range_end=None):
	if not name:
		frappe.throw(_("Shift Design is required."))

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("read")

	try:
		from openpyxl import Workbook
		from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
		from openpyxl.utils import get_column_letter
	except ImportError:
		frappe.throw(_("openpyxl is required for this export but is not installed."))

	from io import BytesIO

	from ir.industrial_relations.doctype.shift_design.shift_design import (
		get_roster_calendar_data,
		simulate_team_hours_by_month,
	)

	# Same default window the Designer's own on-screen calendar opens with
	# (today -> +3 months, clamped to Effective Until) - see
	# ir_shift_design.js's blank_simulation()/simulation_end_date(). The JS
	# passes through whatever the user currently has the Simulation
	# start/end controls set to, so the export matches what's on screen;
	# this default only applies to a direct API call with neither supplied.
	calendar_start = getdate(range_start) if range_start else getdate(nowdate())
	calendar_end = getdate(range_end) if range_end else add_months(calendar_start, 3)
	if doc.effective_until and getdate(doc.effective_until) < calendar_end:
		calendar_end = getdate(doc.effective_until)
	if calendar_end < calendar_start:
		calendar_end = calendar_start

	wb = Workbook()
	ws = wb.active
	ws.title = (doc.design_name or "Shift Design")[:31]

	thin_side = Side(style="thin", color="000000")
	styles = {
		"title_font": Font(bold=True, size=14),
		"section_font": Font(bold=True, size=12),
		"header_font": Font(bold=True, size=10),
		"section_fill": PatternFill("solid", fgColor="D9EAD3"),
		"header_fill": PatternFill("solid", fgColor="E7E6E6"),
		"center": Alignment(horizontal="center", vertical="center", wrap_text=True),
		"wrap": Alignment(vertical="top", wrap_text=True),
		"thin_border": Border(left=thin_side, right=thin_side, top=thin_side, bottom=thin_side),
	}

	row_no = 1
	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=4)
	title_cell = ws.cell(row_no, 1, (doc.design_name or doc.name or "SHIFT DESIGN").upper())
	title_cell.font = styles["title_font"]
	title_cell.alignment = styles["center"]
	row_no += 1

	period = f"{doc.effective_from or ''} to {doc.effective_until or 'indefinite'}"
	ws.cell(row_no, 1, f"Effective: {period}  |  Status: {doc.status or ''}  |  Branch: {doc.branch or '-'}")
	row_no += 1
	ws.cell(
		row_no, 1,
		f"Cycle Length: {doc.cycle_length}  |  Anchor Date: {doc.anchor_date or '-'}  |  "
		f"Pay Period: day {doc.pay_period_start_day} to day {doc.pay_period_end_day}  |  "
		f"Ordinary Hours Limit: {doc.ordinary_hours_limit}",
	)
	row_no += 2

	teams = sorted(
		[row for row in doc.teams or [] if cint(row.enabled)],
		key=lambda row: cint(row.display_order),
	)

	# Shift Type is a Link - the actual start/end time and colour live on the
	# real "Shift Type" doctype record, not on this Design's own child row.
	shift_type_names = [row.shift_type for row in doc.shift_types or [] if row.shift_type]
	shift_type_info = {}
	if shift_type_names:
		shift_type_info = {
			row.name: row
			for row in frappe.get_all(
				"Shift Type",
				filters={"name": ["in", shift_type_names]},
				fields=["name", "start_time", "end_time", "color"],
			)
		}

	row_no = _write_table(
		ws, row_no, "SHIFT TYPES",
		["SHIFT TYPE", "START", "END", "HOURS", "COLOUR"],
		[
			[
				row.shift_type,
				str(shift_type_info.get(row.shift_type, {}).get("start_time") or ""),
				str(shift_type_info.get(row.shift_type, {}).get("end_time") or ""),
				_duration_hours(
					shift_type_info.get(row.shift_type, {}).get("start_time"),
					shift_type_info.get(row.shift_type, {}).get("end_time"),
				),
				shift_type_info.get(row.shift_type, {}).get("color") or "",
			]
			for row in doc.shift_types or []
		],
		styles,
	)

	row_no = _write_table(
		ws, row_no, "SHIFT TEAMS",
		["TEAM", "DISPLAY ORDER", "PATTERN OFFSET"],
		[[row.team_name or row.team_key, row.display_order, row.pattern_offset] for row in teams],
		styles,
	)

	pattern_by_team_day = {
		(row.team_key, cint(row.pattern_day)): row.assignment or ""
		for row in doc.pattern or []
	}
	cycle_length = max(cint(doc.cycle_length), 1)
	pattern_rows = [
		[f"Day {day}"] + [pattern_by_team_day.get((team.team_key, day), "") or "Off" for team in teams]
		for day in range(1, cycle_length + 1)
	]
	row_no = _write_table(
		ws, row_no, "ROTATION PATTERN",
		["CYCLE DAY"] + [team.team_name or team.team_key for team in teams],
		pattern_rows,
		styles,
	)

	row_no = _write_table(
		ws, row_no, "CALENDAR RULES",
		["RULE TYPE", "DAY OF WEEK", "ACTION", "TARGET SHIFT TYPE", "HOURS OVERRIDE", "PRIORITY", "ENABLED"],
		[
			[
				row.rule_type, row.day_of_week or "", row.action,
				row.target_shift_type or "", row.hours_override or "",
				row.priority, "Yes" if cint(row.enabled if row.enabled is not None else 1) else "No",
			]
			for row in doc.calendar_rules or []
		],
		styles,
	)

	date_overrides = doc.date_overrides or []
	if date_overrides:
		row_no = _write_table(
			ws, row_no, "DATE OVERRIDES",
			["DATE", "TEAM", "ASSIGNMENT", "REASON"],
			[
				[
					str(row.date) if row.date else "",
					next((t.team_name or t.team_key for t in teams if t.team_key == row.team_key), row.team_key or ""),
					row.assignment or "Off",
					row.reason or "",
				]
				for row in date_overrides
			],
			styles,
		)

	for col_idx in range(1, ws.max_column + 1):
		letter = get_column_letter(col_idx)
		ws.column_dimensions[letter].width = 26 if col_idx == 1 else 16

	calendar_data = get_roster_calendar_data(doc.name, calendar_start, calendar_end)
	_write_roster_calendar_sheet(
		wb, calendar_data, calendar_start, calendar_end, styles,
		Alignment, Border, Font, PatternFill, Side, get_column_letter,
	)

	hours_by_team_month = simulate_team_hours_by_month(doc.name, calendar_start, calendar_end)
	_write_hours_summary_sheet(
		wb, teams, hours_by_team_month, calendar_start, calendar_end, styles,
		Alignment, Font, get_column_letter,
	)

	out = BytesIO()
	wb.save(out)
	out.seek(0)

	filename = f"{frappe.scrub(doc.name or 'shift_design')}.xlsx"
	frappe.local.response.filename = filename
	frappe.local.response.filecontent = out.getvalue()
	frappe.local.response.type = "binary"


def _write_roster_calendar_sheet(
	wb, calendar_data, range_start, range_end, styles,
	Alignment, Border, Font, PatternFill, Side, get_column_letter,
):
	"""A real month-grid calendar (Mon-Sun columns, one cell per day) on its
	own sheet, resolved from the exact same get_roster_calendar_data() the
	Designer's own on-screen calendar and Site Budget's roster calendar use -
	so this can never disagree with what's shown elsewhere in the app. Each
	day cell lists every enabled team's resolved assignment for that date
	("Off" when none), with a "(!)" marker on an assignment that isn't
	configured to apply on that weekday - the same conflict Shift Design's
	own calendar flags in red."""
	ws = wb.create_sheet("Roster Calendar")
	total_cols = 7
	weekday_labels = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

	row_no = 1
	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
	title_cell = ws.cell(row_no, 1, "ROSTER CALENDAR")
	title_cell.font = styles["title_font"]
	title_cell.alignment = styles["center"]
	row_no += 1

	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
	ws.cell(
		row_no, 1,
		f"Period: {formatdate(range_start, 'yyyy-mm-dd')} to {formatdate(range_end, 'yyyy-mm-dd')}",
	)
	row_no += 2

	teams = calendar_data.get("teams") or []
	holidays = calendar_data.get("holidays") or {}
	days = calendar_data.get("days") or {}
	dates_present = sorted(getdate(d) for d in days.keys())

	if not dates_present:
		ws.cell(row_no, 1, "No roster data for this date range.")
		for col_idx in range(1, total_cols + 1):
			ws.column_dimensions[get_column_letter(col_idx)].width = 24
		return

	holiday_fill = PatternFill("solid", fgColor="FCE5CD")
	sunday_fill = PatternFill("solid", fgColor="F4CCCC")
	row_height = max(60, 14 * (len(teams) + 2))

	months = defaultdict(set)
	for date in dates_present:
		months[(date.year, date.month)].add(date.day)

	for year, month in sorted(months.keys()):
		days_present = months[(year, month)]

		ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
		month_cell = ws.cell(row_no, 1, f"{_calendar.month_name[month]} {year}".upper())
		month_cell.font = styles["section_font"]
		month_cell.alignment = styles["center"]
		month_cell.fill = styles["section_fill"]
		row_no += 1

		for col_idx, label in enumerate(weekday_labels, start=1):
			header_cell = ws.cell(row_no, col_idx, label)
			header_cell.font = styles["header_font"]
			header_cell.fill = styles["header_fill"]
			header_cell.alignment = styles["center"]
		row_no += 1

		# Python's monthrange() weekday is already Monday=0..Sunday=6, so it
		# lines up directly with this grid's own Mon-Sun columns.
		leading_blanks, days_in_month = _calendar.monthrange(year, month)
		ws.row_dimensions[row_no].height = row_height
		col_idx = 1 + leading_blanks

		for day in range(1, days_in_month + 1):
			if col_idx > total_cols:
				row_no += 1
				ws.row_dimensions[row_no].height = row_height
				col_idx = 1

			cell = ws.cell(row_no, col_idx)
			cell.alignment = styles["wrap"]
			cell.border = styles["thin_border"]

			if day not in days_present:
				cell.value = str(day)
				col_idx += 1
				continue

			date = _date(year, month, day)
			date_key = str(date)
			holiday_name = holidays.get(date_key, "")
			day_data = days.get(date_key, {})

			lines = [f"Day {day}" + (f" - {holiday_name}" if holiday_name else "")]
			for team in teams:
				team_entry = day_data.get(team["team_key"]) or {}
				assignment = team_entry.get("assignment") or "Off"
				conflict_marker = " (!)" if team_entry.get("conflict") else ""
				lines.append(f"{team['team_name']}: {assignment}{conflict_marker}")
			cell.value = "\n".join(lines)

			if holiday_name:
				cell.fill = holiday_fill
			elif date.weekday() == 6:
				cell.fill = sunday_fill

			col_idx += 1

		row_no += 2

	for col_idx in range(1, total_cols + 1):
		ws.column_dimensions[get_column_letter(col_idx)].width = 24


def _month_label(month_key):
	"""'2026-06' -> 'June 2026' - month_key as produced by
	pay_period_month_key()/simulate_team_hours_by_month() (keyed by whichever
	calendar month a pay period counts as, via its End date - not
	necessarily the month(s) its days fall in)."""
	year, month = month_key.split("-")
	return f"{_calendar.month_name[int(month)]} {year}"


_OVERTIME_CATEGORIES = ("normal", "saturday", "sunday", "public_holiday")


def _empty_overtime():
	return {category: 0.0 for category in _OVERTIME_CATEGORIES}


def _hours_entry(ordinary, overtime):
	ordinary = flt(ordinary)
	overtime = {category: flt(overtime.get(category)) for category in _OVERTIME_CATEGORIES}
	return {
		"ordinary": round(ordinary, 2),
		"overtime": {category: round(hours, 2) for category, hours in overtime.items()},
		"total": round(ordinary + sum(overtime.values()), 2),
	}


def monthly_hours_summary(teams, hours_by_team_month):
	"""Per-month blocks (chronological - month_key is "YYYY-MM" from
	pay_period_month_key(), so a plain string sort is already chronological),
	each with one row per team in *display* order (not alphabetical - that
	doesn't track display_order) plus a TOTAL (sum across teams) and an
	AVERAGE (mean across teams) row. Shared by the Excel "Hours Summary"
	sheet and the on-screen Pay Period Breakdown replacement, so they can't
	disagree with each other - both are read straight from
	simulate_team_hours_by_month(), the same function Site Budget's cost
	engine uses, so none of the three can disagree either.

	Returns [{"month_key", "month_label", "rows": [{"team_key", "team_name",
	"ordinary", "overtime", "total"}, ...], "total": {...}, "average": {...}}]
	- "total"/"average" and each row share the same ordinary/overtime/total
	shape as _hours_entry()."""
	all_month_keys = sorted({
		month_key for months in hours_by_team_month.values() for month_key in months.keys()
	})

	blocks = []
	for month_key in all_month_keys:
		rows = []
		month_ordinary = 0.0
		month_overtime = _empty_overtime()

		for team in teams:
			month_data = hours_by_team_month.get(team.team_key, {}).get(month_key)
			if month_data is None:
				continue

			overtime = month_data.get("overtime") or {}
			ordinary = flt(month_data.get("ordinary"))
			rows.append({
				"team_key": team.team_key,
				"team_name": team.team_name or team.team_key,
				**_hours_entry(ordinary, overtime),
			})

			month_ordinary += ordinary
			for category in _OVERTIME_CATEGORIES:
				month_overtime[category] += flt(overtime.get(category))

		if not rows:
			continue

		team_count = len(rows)
		average_overtime = {category: hours / team_count for category, hours in month_overtime.items()}

		blocks.append({
			"month_key": month_key,
			"month_label": _month_label(month_key),
			"rows": rows,
			"total": _hours_entry(month_ordinary, month_overtime),
			"average": _hours_entry(month_ordinary / team_count, average_overtime),
		})

	return blocks


@frappe.whitelist()
def get_monthly_hours_summary(name, range_start, range_end):
	"""JSON wrapper around monthly_hours_summary() for the on-screen Pay
	Period Breakdown table - see that function's own docstring for why this
	exists instead of the page's own client-side pay-period simulation."""
	from ir.industrial_relations.doctype.shift_design.shift_design import (
		simulate_team_hours_by_month,
	)

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("read")

	teams = sorted(
		[row for row in doc.teams or [] if cint(row.enabled)],
		key=lambda row: cint(row.display_order),
	)
	hours_by_team_month = simulate_team_hours_by_month(name, getdate(range_start), getdate(range_end))
	return monthly_hours_summary(teams, hours_by_team_month)


def _write_hours_summary_sheet(
	wb, teams, hours_by_team_month, range_start, range_end, styles, Alignment, Font, get_column_letter,
):
	"""Per-month, per-team Ordinary/Overtime hours, from the exact same
	simulate_team_hours_by_month() Site Budget's own cost engine uses - so
	this can never disagree with what Site Budget charges for this Shift
	Design's hours. Grouped by calendar month (not pay period - a pay
	period can straddle two calendar months, see pay_period_month_key()),
	months in chronological order, teams in their own display order within
	each month, with a TOTAL and AVERAGE row closing out each month block."""
	ws = wb.create_sheet("Hours Summary")
	headers = [
		"MONTH", "TEAM", "ORDINARY HOURS", "OVERTIME (NORMAL)",
		"OVERTIME (SATURDAY)", "OVERTIME (SUNDAY)", "OVERTIME (PUBLIC HOLIDAY)", "TOTAL HOURS",
	]
	total_cols = len(headers)

	row_no = 1
	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
	title_cell = ws.cell(row_no, 1, "HOURS SUMMARY")
	title_cell.font = styles["title_font"]
	title_cell.alignment = styles["center"]
	row_no += 1

	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
	ws.cell(
		row_no, 1,
		f"Period: {formatdate(range_start, 'yyyy-mm-dd')} to {formatdate(range_end, 'yyyy-mm-dd')}",
	)
	row_no += 2

	def _row_values(entry):
		overtime = entry["overtime"]
		return [
			entry["ordinary"], overtime["normal"], overtime["saturday"],
			overtime["sunday"], overtime["public_holiday"], entry["total"],
		]

	table_rows = []
	emphasis_row_indexes = []

	for block in monthly_hours_summary(teams, hours_by_team_month):
		for row in block["rows"]:
			table_rows.append([block["month_label"], row["team_name"], *_row_values(row)])

		table_rows.append([block["month_label"], "TOTAL", *_row_values(block["total"])])
		emphasis_row_indexes.append(len(table_rows) - 1)

		table_rows.append([block["month_label"], "AVERAGE", *_row_values(block["average"])])
		emphasis_row_indexes.append(len(table_rows) - 1)

	table_start_row = row_no
	row_no = _write_table(ws, table_start_row, "HOURS BY MONTH AND TEAM", headers, table_rows, styles)

	data_start_row = table_start_row + 2  # section title row, then header row
	for offset in emphasis_row_indexes:
		for col_idx in range(1, total_cols + 1):
			ws.cell(data_start_row + offset, col_idx).font = styles["header_font"]

	for col_idx in range(1, total_cols + 1):
		ws.column_dimensions[get_column_letter(col_idx)].width = 14 if col_idx > 1 else 22
	ws.column_dimensions[get_column_letter(1)].width = 22


def _write_table(ws, row_no, title, headers, rows, styles):
	total_cols = max(1, len(headers))

	ws.merge_cells(start_row=row_no, start_column=1, end_row=row_no, end_column=total_cols)
	title_cell = ws.cell(row_no, 1, title)
	title_cell.font = styles["section_font"]
	title_cell.alignment = styles["center"]
	title_cell.fill = styles["section_fill"]
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
				cell = ws.cell(row_no, idx, value)
				cell.alignment = styles["wrap"]
			row_no += 1
	else:
		ws.cell(row_no, 1, "None")
		row_no += 1

	for row in ws.iter_rows(min_row=data_start - 2, max_row=row_no - 1, min_col=1, max_col=total_cols):
		for cell in row:
			cell.border = styles["thin_border"]

	return row_no + 1


def _serialize(doc):
	meta = frappe.get_meta(SHIFT_DESIGN)
	data = {"name": doc.name}

	for field in meta.fields:
		if field.fieldtype in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}:
			continue

		if field.fieldtype == "Table":
			data[field.fieldname] = [
				_serialize_child(row)
				for row in doc.get(field.fieldname) or []
			]
		else:
			data[field.fieldname] = doc.get(field.fieldname)

	data["modified"] = doc.modified
	return data


def _serialize_child(row):
	meta = frappe.get_meta(row.doctype)
	return {
		field.fieldname: row.get(field.fieldname)
		for field in meta.fields
		if field.fieldtype not in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}
	}


def _clean_child_payload(row, child_doctype):
	valid_fields = set(_fieldnames(child_doctype))
	return {
		key: value
		for key, value in row.items()
		if key in valid_fields
	}


def _shift_type_options():
	if not frappe.db.exists("DocType", "Shift Type"):
		return []

	meta = frappe.get_meta("Shift Type")
	fields = ["name"]
	for fieldname in ("start_time", "end_time", "color"):
		if meta.has_field(fieldname):
			fields.append(fieldname)

	rows = frappe.get_all(
		"Shift Type",
		filters=_active_filters(meta),
		fields=fields,
		order_by="name asc",
	)

	return [
		{
			"name": row.name,
			"start_time": str(row.get("start_time")) if row.get("start_time") is not None else "",
			"end_time": str(row.get("end_time")) if row.get("end_time") is not None else "",
			"color": row.get("color") or "",
			"hours": _duration_hours(
				row.get("start_time"),
				row.get("end_time"),
			),
		}
		for row in rows
	]


def _duration_hours(start, end):
	if start is None or end is None:
		return 0

	def seconds(value):
		if hasattr(value, "total_seconds"):
			return value.total_seconds()

		text = str(value).split(".")[0]
		for date_format in ("%H:%M:%S", "%H:%M"):
			try:
				parsed = datetime.strptime(text, date_format)
				return (
					parsed.hour * 3600
					+ parsed.minute * 60
					+ parsed.second
				)
			except ValueError:
				continue
		return 0

	start_seconds = seconds(start)
	end_seconds = seconds(end)
	if end_seconds <= start_seconds:
		end_seconds += 24 * 3600

	return round((end_seconds - start_seconds) / 3600, 4)


def _names(doctype, group_filter=False):
	if not frappe.db.exists("DocType", doctype):
		return []

	meta = frappe.get_meta(doctype)
	filters = {}

	if group_filter and meta.has_field("is_group"):
		filters["is_group"] = 0
	if meta.has_field("disabled"):
		filters["disabled"] = 0

	return frappe.get_all(
		doctype,
		filters=filters,
		pluck="name",
		order_by="name asc",
	)


def _active_filters(meta):
	if meta.has_field("disabled"):
		return {"disabled": 0}
	if meta.has_field("enabled"):
		return {"enabled": 1}
	return {}


def _fieldnames(doctype):
	return [
		field.fieldname
		for field in frappe.get_meta(doctype).fields
		if field.fieldtype not in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}
	]


def _child_fieldnames(parent_doctype, table_fieldname):
	parent_meta = frappe.get_meta(parent_doctype)
	table_field = parent_meta.get_field(table_fieldname)
	if not table_field or not table_field.options:
		return []
	return _fieldnames(table_field.options)


def _json_object(value):
	if isinstance(value, dict):
		return value

	try:
		parsed = json.loads(value or "{}")
	except (TypeError, ValueError):
		frappe.throw(_("Invalid Shift Design payload."))

	if not isinstance(parsed, dict):
		frappe.throw(_("Shift Design payload must be an object."))

	return parsed


def _check_permission(ptype):
	if not frappe.has_permission(SHIFT_DESIGN, ptype=ptype):
		frappe.throw(_("Not permitted."), frappe.PermissionError)


def _clean(value):
	return str(value or "").strip()
