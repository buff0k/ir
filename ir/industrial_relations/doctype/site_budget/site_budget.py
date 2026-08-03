# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import calendar as _calendar
import re
from collections import defaultdict
from datetime import date as _date
from io import BytesIO

import frappe
import xlsxwriter
from frappe.model.document import Document
from frappe.utils import escape_html, flt, fmt_money, getdate
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

from ir.industrial_relations.doctype.shift_design.shift_design import (
	count_pay_periods_for_shift_design,
	get_ordered_team_keys,
	get_roster_calendar_data,
	simulate_team_hours_by_month,
	team_color,
)
from ir.industrial_relations.doctype.site_budget_map.site_budget_map import (
	compute_salary_structure_totals,
	compute_site_budget_map_totals,
	resolve_active_site_budget_map,
)
from ir.industrial_relations.doctype.site_organogram.site_organogram import (
	SHIFT_LETTERS,
	get_designation_headcounts,
	get_designation_mismatches,
	get_designation_slots_by_group,
)

class SiteBudget(Document):
	def validate(self):
		self.refresh_designation_costs()

	def refresh_designation_costs(self):
		if not self.site_organogram:
			self.set("designation_costs", [])
			return

		organogram = frappe.get_doc("Site Organogram", self.site_organogram)
		headcounts = get_designation_headcounts(organogram)

		existing_salary_structures = {
			row.designation: row.salary_structure
			for row in (self.designation_costs or [])
			if row.designation
		}

		rows = []
		for designation, counts in sorted(headcounts.items()):
			salary_structure = existing_salary_structures.get(designation) or ""
			if not salary_structure:
				salary_structure = self._resolve_default_salary_structure(organogram.branch, designation)

			rows.append({
				"designation": designation,
				"salary_structure": salary_structure,
				"headcount": counts["total"],
				"filled_count": counts["filled"],
				"vacant_count": counts["vacant"],
			})

		self.set("designation_costs", rows)

	def _resolve_default_salary_structure(self, branch, designation):
		if not self.from_date:
			return ""

		active_map = resolve_active_site_budget_map(branch, designation, self.from_date)
		return active_map.salary_structure if active_map else ""


def _compute_designation_costs(doc):
	"""Shared cost computation behind get_site_budget_summary_html() (the
	on-screen preview) and export_site_budget_summary_xlsx() (the Excel
	export) - one place computes per-Designation cost, so the two can never
	disagree. Returns None if no Site Organogram is linked.

	Hours are tracked per Designation per calendar month, split into "NT"
	(Normal Time - ordinary hours, PLUS any simulated overtime hours in a
	day-category with no Overtime Type configured on this Site Budget, since
	no Overtime Type configured means that time is simply paid at the plain
	hourly rate, not excluded from cost) and one bucket per Overtime Type
	actually configured (keyed by its real name, so two categories mapped to
	the same Overtime Type share one bucket). Hours are captured for every
	Designation regardless of whether it has a Salary Structure linked -
	they're a roster fact, not a Salary Structure fact - so a Designation
	missing a Salary Structure still shows real hours to base a hand-entered
	rate on (see export_site_budget_summary_xlsx()).
	"""
	if not doc.site_organogram:
		return None

	organogram = frappe.get_doc("Site Organogram", doc.site_organogram)

	headcounts = get_designation_headcounts(organogram)
	mismatches = get_designation_mismatches(organogram)
	slots_by_group = get_designation_slots_by_group(organogram)

	salary_structure_by_designation = {
		row.designation: row.salary_structure
		for row in (doc.designation_costs or [])
		if row.designation
	}

	overtime_type_by_category = {
		"normal": doc.overtime_type_normal,
		"saturday": doc.overtime_type_saturday,
		"sunday": doc.overtime_type_sunday,
		"public_holiday": doc.overtime_type_public_holiday,
	}
	overtime_type_multiplier = {}
	for overtime_type in set(overtime_type_by_category.values()):
		if overtime_type:
			overtime_type_multiplier[overtime_type] = flt(
				frappe.db.get_value("Overtime Type", overtime_type, "standard_multiplier")
			)

	totals_cache = {}
	allowances_cache = {}
	team_hours_cache = {}
	team_keys_cache = {}
	fixed_cost_by_designation = defaultdict(float)
	hourly_rate_by_designation = {}
	missing_designations = set()
	hours_by_month_designation = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))

	for group_info in slots_by_group.values():
		shift_design = group_info["shift_design"]
		pay_periods = (
			count_pay_periods_for_shift_design(shift_design, doc.from_date, doc.end_date)
			if shift_design and doc.from_date and doc.end_date
			else 0
		)

		if shift_design and shift_design not in team_hours_cache:
			team_hours_cache[shift_design] = simulate_team_hours_by_month(shift_design, doc.from_date, doc.end_date)
			team_keys_cache[shift_design] = get_ordered_team_keys(shift_design)

		team_hours_by_key = team_hours_cache.get(shift_design, {})
		team_keys = team_keys_cache.get(shift_design, [])

		for shift_label, designation_counts in group_info["by_shift"].items():
			team_key = _team_key_for_shift(shift_label, team_keys)
			months = team_hours_by_key.get(team_key, {})

			for designation, count in designation_counts.items():
				for month_key, month_data in months.items():
					bucket = hours_by_month_designation[month_key][designation]
					bucket["NT"] += month_data["ordinary"] * count
					for category, hours in (month_data.get("overtime") or {}).items():
						if not hours:
							continue
						overtime_type = overtime_type_by_category.get(category)
						if overtime_type:
							bucket[overtime_type] += hours * count
						else:
							# No Overtime Type configured for this category -
							# that time is simply paid at the plain hourly
							# rate, i.e. it's Normal Time, not excluded.
							bucket["NT"] += hours * count

				salary_structure = salary_structure_by_designation.get(designation)
				if not salary_structure:
					missing_designations.add(designation)
					continue

				if salary_structure not in totals_cache:
					totals_cache[salary_structure] = compute_salary_structure_totals(salary_structure)

				if designation not in allowances_cache:
					allowances_cache[designation] = _resolve_allowances_total(
						organogram.branch, designation, doc.from_date, salary_structure
					)

				structure_totals = totals_cache[salary_structure]

				# Fixed earnings + Site Specific Allowances recur every pay
				# period - unrelated to hours, so tracked separately from
				# the hourly-rate-driven NT/Overtime Type cost.
				fixed_net_pay = structure_totals["net_pay"] + allowances_cache[designation]
				fixed_cost_by_designation[designation] += fixed_net_pay * count * pay_periods
				hourly_rate_by_designation[designation] = structure_totals["hour_rate"]

	currency_by_designation = {
		designation: totals_cache[salary_structure]["currency"]
		for designation, salary_structure in salary_structure_by_designation.items()
		if salary_structure in totals_cache
	}

	has_hourly_structure = any(
		totals["salary_slip_based_on_timesheet"] for totals in totals_cache.values()
	)

	return {
		"headcounts": headcounts,
		"mismatches": mismatches,
		"salary_structure_by_designation": salary_structure_by_designation,
		"currency_by_designation": currency_by_designation,
		"has_hourly_structure": has_hourly_structure,
		"missing_designations": missing_designations,
		"fixed_cost_by_designation": dict(fixed_cost_by_designation),
		"hourly_rate_by_designation": hourly_rate_by_designation,
		"hours_by_month_designation": {
			month_key: {designation: dict(buckets) for designation, buckets in by_designation.items()}
			for month_key, by_designation in hours_by_month_designation.items()
		},
		"overtime_type_multiplier": overtime_type_multiplier,
	}


def _total_hours_by_designation(hours_by_month_designation):
	"""Flattens hours_by_month_designation (month -> designation -> bucket ->
	hours) down to designation -> bucket -> hours, summed across every month
	in the reporting period."""
	totals = defaultdict(lambda: defaultdict(float))
	for by_designation in hours_by_month_designation.values():
		for designation, buckets in by_designation.items():
			for bucket, hours in buckets.items():
				totals[designation][bucket] += hours
	return {designation: dict(buckets) for designation, buckets in totals.items()}


@frappe.whitelist()
def get_site_budget_summary_html(site_budget):
	if not site_budget:
		return ""

	doc = frappe.get_doc("Site Budget", site_budget)
	doc.check_permission("read")

	data = _compute_designation_costs(doc)
	if data is None:
		return _notice("Link a Site Organogram to see the budget summary.")

	total_hours = _total_hours_by_designation(data["hours_by_month_designation"])
	ordinary_cost_by_designation = {}
	overtime_cost_by_designation = {}
	for designation, buckets in total_hours.items():
		rate = data["hourly_rate_by_designation"].get(designation, 0.0)
		fixed_cost = data["fixed_cost_by_designation"].get(designation, 0.0)
		ordinary_cost_by_designation[designation] = fixed_cost + buckets.get("NT", 0.0) * rate
		overtime_cost_by_designation[designation] = sum(
			hours * rate * data["overtime_type_multiplier"].get(bucket, 0.0)
			for bucket, hours in buckets.items()
			if bucket != "NT"
		)
	# A Designation can have a fixed cost but zero simulated hours at all
	# (e.g. no Shift Design linked to its group) - still needs to show up.
	for designation, fixed_cost in data["fixed_cost_by_designation"].items():
		ordinary_cost_by_designation.setdefault(designation, fixed_cost)

	cost_by_designation = {
		designation: ordinary_cost_by_designation.get(designation, 0.0)
		+ overtime_cost_by_designation.get(designation, 0.0)
		for designation in set(ordinary_cost_by_designation) | set(overtime_cost_by_designation)
	}

	return (
		_vacancy_table_html(data["headcounts"])
		+ _mismatch_table_html(data["mismatches"])
		+ _cost_table_html(
			data["headcounts"],
			data["salary_structure_by_designation"],
			cost_by_designation,
			overtime_cost_by_designation,
			data["currency_by_designation"],
			data["missing_designations"],
			data["has_hourly_structure"],
		)
	)


@frappe.whitelist()
def export_site_budget_summary_xlsx(site_budget):
	doc = frappe.get_doc("Site Budget", site_budget)
	doc.check_permission("read")

	data = _compute_designation_costs(doc)
	if data is None:
		frappe.throw("Link a Site Organogram before exporting.")

	headcounts = data["headcounts"]
	designations = sorted(headcounts.keys())
	months = sorted(data["hours_by_month_designation"].keys())
	overtime_types = sorted(data["overtime_type_multiplier"].keys())
	total_hours = _total_hours_by_designation(data["hours_by_month_designation"])

	output = BytesIO()
	workbook = xlsxwriter.Workbook(output, {"in_memory": True})

	header_format = workbook.add_format({"bold": True, "bg_color": "#f0f0f0", "border": 1})
	# Hand-editable inputs (a rate/cost/hours the user can type over - either
	# because there's no Salary Structure to prefill it from, or because
	# Monthly Hours is meant to be adjustable) are highlighted so it's
	# obvious which cells drive the formulas and which are computed.
	input_format = workbook.add_format({"bg_color": "#fff8dc", "border": 1, "num_format": "#,##0.00"})
	computed_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
	text_format = workbook.add_format({"border": 1})
	int_format = workbook.add_format({"border": 1, "num_format": "0"})
	total_label_format = workbook.add_format({"bold": True})
	total_format = workbook.add_format({"bold": True, "border": 1, "top": 2, "num_format": "#,##0.00"})
	note_format = workbook.add_format({"italic": True, "font_color": "#a00000"})
	legend_label_format = workbook.add_format({"bold": True})

	# --- "Monthly Hours": one row per (Designation, Month) actually worked -
	# the audit trail the Summary sheet's hour totals are built from.
	monthly_sheet = workbook.add_worksheet("Monthly Hours")
	monthly_headers = ["Designation", "Month", "NT Hours"] + [f"{ot} Hours" for ot in overtime_types]
	for col, label in enumerate(monthly_headers):
		monthly_sheet.write(0, col, label, header_format)
	monthly_sheet.set_column(0, 0, 28)
	monthly_sheet.set_column(1, 1, 12)
	if overtime_types:
		monthly_sheet.set_column(2, 2 + len(overtime_types), 14)
	else:
		monthly_sheet.set_column(2, 2, 14)

	row = 1
	for month_key in months:
		by_designation = data["hours_by_month_designation"].get(month_key, {})
		for designation in designations:
			buckets = by_designation.get(designation)
			if not buckets:
				continue
			monthly_sheet.write_string(row, 0, designation, text_format)
			monthly_sheet.write_string(row, 1, month_key, text_format)
			monthly_sheet.write_number(row, 2, buckets.get("NT", 0.0), input_format)
			for i, overtime_type in enumerate(overtime_types):
				monthly_sheet.write_number(row, 3 + i, buckets.get(overtime_type, 0.0), input_format)
			row += 1
	monthly_sheet.freeze_panes(1, 0)

	# --- "Summary": one row per Designation, cross-linked to Monthly Hours
	# via SUMIF so hand-edits on either sheet flow through to the totals.
	sheet = workbook.add_worksheet("Summary")

	legend_row_by_type = {}
	if overtime_types:
		sheet.write_string(0, 0, "Overtime Rates", legend_label_format)
		sheet.write_string(0, 1, "Multiplier", legend_label_format)
		for i, overtime_type in enumerate(overtime_types):
			legend_row = 1 + i
			sheet.write_string(legend_row, 0, overtime_type, text_format)
			sheet.write_number(legend_row, 1, data["overtime_type_multiplier"][overtime_type], input_format)
			legend_row_by_type[overtime_type] = legend_row  # 0-indexed
		table_start_row = len(overtime_types) + 2  # legend rows + 1 blank row
	else:
		table_start_row = 0

	headers = [
		"Designation", "Total Headcount", "Filled", "Vacant", "Salary Structure", "Currency",
		"Hourly Rate", "Fixed Cost", "NT Hours", "NT Cost",
	]
	for overtime_type in overtime_types:
		headers += [f"{overtime_type} Hours", f"{overtime_type} Cost"]
	headers.append("Total Cost")

	COL_DESIGNATION, COL_HEADCOUNT, COL_FILLED, COL_VACANT = 0, 1, 2, 3
	COL_SALARY_STRUCTURE, COL_CURRENCY, COL_HOURLY_RATE, COL_FIXED_COST = 4, 5, 6, 7
	COL_NT_HOURS, COL_NT_COST = 8, 9
	ot_hours_col, ot_cost_col, col = {}, {}, 10
	for overtime_type in overtime_types:
		ot_hours_col[overtime_type] = col
		ot_cost_col[overtime_type] = col + 1
		col += 2
	COL_TOTAL_COST = col

	header_row = table_start_row
	for col_idx, label in enumerate(headers):
		sheet.write(header_row, col_idx, label, header_format)

	col_widths = [28, 14, 10, 10, 28, 10, 14, 14, 12, 14] + [14, 14] * len(overtime_types) + [16]
	for col_idx, width in enumerate(col_widths):
		sheet.set_column(col_idx, col_idx, width)

	data_first_row = header_row + 1  # 0-indexed
	row = data_first_row
	for designation in designations:
		counts = headcounts[designation]
		salary_structure = data["salary_structure_by_designation"].get(designation)
		currency = data["currency_by_designation"].get(designation, "")
		rate = data["hourly_rate_by_designation"].get(designation)
		fixed_cost = data["fixed_cost_by_designation"].get(designation)
		designation_hours = total_hours.get(designation, {})

		sheet.write_string(row, COL_DESIGNATION, designation, text_format)
		sheet.write_number(row, COL_HEADCOUNT, counts["total"], int_format)
		sheet.write_number(row, COL_FILLED, counts["filled"], int_format)
		sheet.write_number(row, COL_VACANT, counts["vacant"], int_format)
		sheet.write_string(row, COL_SALARY_STRUCTURE, salary_structure or "Missing Salary Structure", text_format)
		sheet.write_string(row, COL_CURRENCY, currency or "", text_format)

		# Rate/Fixed Cost are only hand-editable when there's no Salary
		# Structure to prefill them from - otherwise they're the real
		# computed values (0 Hourly Rate for a genuinely non-hourly
		# structure isn't an omission, it's a fact, so it stays computed).
		if rate is not None:
			sheet.write_number(row, COL_HOURLY_RATE, rate, computed_format)
		else:
			sheet.write_blank(row, COL_HOURLY_RATE, None, input_format)
		if fixed_cost is not None:
			sheet.write_number(row, COL_FIXED_COST, fixed_cost, computed_format)
		else:
			sheet.write_blank(row, COL_FIXED_COST, None, input_format)

		designation_cell = xl_rowcol_to_cell(row, COL_DESIGNATION)
		rate_cell = xl_rowcol_to_cell(row, COL_HOURLY_RATE)
		rate_value = rate or 0

		nt_hours_cell = xl_rowcol_to_cell(row, COL_NT_HOURS)
		sheet.write_formula(
			row, COL_NT_HOURS,
			f"=SUMIF('Monthly Hours'!$A:$A,{designation_cell},'Monthly Hours'!$C:$C)",
			computed_format, designation_hours.get("NT", 0.0),
		)
		sheet.write_formula(
			row, COL_NT_COST, f"={nt_hours_cell}*{rate_cell}",
			computed_format, designation_hours.get("NT", 0.0) * rate_value,
		)

		overtime_cost_cells = []
		for i, overtime_type in enumerate(overtime_types):
			monthly_col = xl_col_to_name(3 + i)
			hours_cell = xl_rowcol_to_cell(row, ot_hours_col[overtime_type])
			sheet.write_formula(
				row, ot_hours_col[overtime_type],
				f"=SUMIF('Monthly Hours'!$A:$A,{designation_cell},'Monthly Hours'!{monthly_col}:{monthly_col})",
				computed_format, designation_hours.get(overtime_type, 0.0),
			)
			multiplier_cell = f"$B${legend_row_by_type[overtime_type] + 1}"
			cost_value = designation_hours.get(overtime_type, 0.0) * rate_value * data["overtime_type_multiplier"][overtime_type]
			sheet.write_formula(
				row, ot_cost_col[overtime_type], f"={hours_cell}*{rate_cell}*{multiplier_cell}",
				computed_format, cost_value,
			)
			overtime_cost_cells.append(xl_rowcol_to_cell(row, ot_cost_col[overtime_type]))

		fixed_cost_cell = xl_rowcol_to_cell(row, COL_FIXED_COST)
		nt_cost_cell = xl_rowcol_to_cell(row, COL_NT_COST)
		total_formula = "=" + "+".join([fixed_cost_cell, nt_cost_cell, *overtime_cost_cells])
		total_cached = (
			(fixed_cost or 0) + designation_hours.get("NT", 0.0) * rate_value
			+ sum(
				designation_hours.get(ot, 0.0) * rate_value * data["overtime_type_multiplier"][ot]
				for ot in overtime_types
			)
		)
		sheet.write_formula(row, COL_TOTAL_COST, total_formula, computed_format, total_cached)

		row += 1

	last_data_row = row - 1  # 0-indexed
	total_row = row + 1  # leave a blank row before the Grand Total

	sheet.write_string(total_row, COL_DESIGNATION, "Grand Total", total_label_format)
	if last_data_row >= data_first_row:
		grand_total_cached = sum(
			(data["fixed_cost_by_designation"].get(d) or 0)
			+ total_hours.get(d, {}).get("NT", 0.0) * (data["hourly_rate_by_designation"].get(d) or 0)
			+ sum(
				total_hours.get(d, {}).get(ot, 0.0)
				* (data["hourly_rate_by_designation"].get(d) or 0)
				* data["overtime_type_multiplier"][ot]
				for ot in overtime_types
			)
			for d in designations
		)
		total_range = f"{xl_rowcol_to_cell(data_first_row, COL_TOTAL_COST)}:{xl_rowcol_to_cell(last_data_row, COL_TOTAL_COST)}"
		sheet.write_formula(total_row, COL_TOTAL_COST, f"=SUM({total_range})", total_format, grand_total_cached)
	else:
		sheet.write_number(total_row, COL_TOTAL_COST, 0, total_format)

	note_row = total_row + 2
	if data["missing_designations"]:
		sheet.write_string(
			note_row, 0,
			"Designations missing a Salary Structure are shown with blank Hourly Rate / Fixed Cost cells - "
			"enter values there to include them in the totals above.",
			note_format,
		)

	sheet.freeze_panes(header_row + 1, 0)
	workbook.close()
	output.seek(0)

	frappe.response["filename"] = f"{site_budget} - Budget Summary.xlsx"
	frappe.response["filecontent"] = output.getvalue()
	frappe.response["type"] = "binary"


@frappe.whitelist()
def get_site_budget_roster_calendar_html(site_budget):
	if not site_budget:
		return ""

	doc = frappe.get_doc("Site Budget", site_budget)
	doc.check_permission("read")

	if not doc.site_organogram or not doc.from_date or not doc.end_date:
		return _notice("Link a Site Organogram and set Start/End Date to see the shift roster calendar.")

	organogram = frappe.get_doc("Site Organogram", doc.site_organogram)

	headings_by_design = defaultdict(list)
	for row in organogram.group_headings or []:
		if row.shift_design:
			headings_by_design[row.shift_design].append(row.group)

	if not headings_by_design:
		return _notice("No Shift Design is linked to any Group Heading on the Site Organogram.")

	blocks = ""
	for shift_design in sorted(headings_by_design.keys()):
		heading_names = ", ".join(headings_by_design[shift_design])
		calendar_data = get_roster_calendar_data(shift_design, doc.from_date, doc.end_date)
		blocks += (
			'<div class="sdm-roster-block">'
			f"<h4>{escape_html(shift_design)} - used by: {escape_html(heading_names)}</h4>"
			f"{_render_roster_calendar(calendar_data)}"
			"</div>"
		)

	return blocks


_WEEKDAY_HEAD = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _render_roster_calendar(calendar_data):
	"""Renders the same `.sdm-calendar`/`.sdm-month`/`.sdm-date`/`.sdm-mini`
	markup as ir_shift_design.js's render_calendar(), reusing its globally
	loaded `.sdm-*` CSS (ir_ui.css) - so this looks identical to Shift
	Design's own calendar."""
	days = calendar_data.get("days") or {}
	if not days:
		return _notice("No simulation dates.")

	teams = calendar_data.get("teams") or []
	holidays = calendar_data.get("holidays") or {}
	dates = sorted(getdate(d) for d in days.keys())

	months = defaultdict(list)
	for date in dates:
		months[(date.year, date.month)].append(date.day)

	weekday_head_html = "".join(
		f'<div class="sdm-weekday-head">{escape_html(label)}</div>' for label in _WEEKDAY_HEAD
	)

	month_blocks = ""
	for year, month in sorted(months.keys()):
		days_present = set(months[(year, month)])
		title = f"{_calendar.month_name[month]} {year}"
		# Python's monthrange() weekday is already Monday=0..Sunday=6.
		leading_blanks, days_in_month = _calendar.monthrange(year, month)

		cells = '<div class="sdm-date sdm-date--pad"></div>' * leading_blanks

		for day in range(1, days_in_month + 1):
			if day not in days_present:
				cells += f'<div class="sdm-date sdm-date--out"><div class="sdm-date__head"><b>{day}</b></div></div>'
				continue

			date = _date(year, month, day)
			date_key = str(date)
			is_sunday = date.weekday() == 6
			holiday_name = holidays.get(date_key, "")
			day_data = days.get(date_key, {})

			team_html = ""
			for index, team in enumerate(teams):
				entry = day_data.get(team["team_key"]) or {}
				assignment = entry.get("assignment") or ""
				is_off = not assignment
				color = "" if is_off else team_color(index)
				style = "" if is_off else f'style="background:color-mix(in srgb, {color} 20%, transparent)"'
				is_conflict = bool(entry.get("conflict")) and not is_off
				label = _assignment_label(assignment, team.get("team_name"))  # already HTML-escaped
				title_text = (
					f"{label} - not configured to apply on this weekday." if is_conflict else label
				)
				classes = "sdm-mini"
				if is_off:
					classes += " sdm-mini--off"
				if is_conflict:
					classes += " sdm-mini--conflict"
				team_html += f'<span class="{classes}" {style} title="{title_text}">{label}</span>'

			cells += (
				f'<div class="sdm-date {"is-sunday" if is_sunday else ""} {"is-holiday" if holiday_name else ""}">'
				f'<div class="sdm-date__head"><b>{day}</b></div>'
				f'<div class="sdm-holiday">{escape_html(holiday_name) if holiday_name else "&nbsp;"}</div>'
				f'<div class="sdm-date__teams">{team_html}</div>'
				"</div>"
			)

		trailing_blanks = (7 - ((leading_blanks + days_in_month) % 7)) % 7
		cells += '<div class="sdm-date sdm-date--pad"></div>' * trailing_blanks

		month_blocks += (
			f'<div class="sdm-month"><h4>{escape_html(title)}</h4>'
			f'<div class="sdm-month-grid sdm-month-grid--head">{weekday_head_html}</div>'
			f'<div class="sdm-month-grid">{cells}</div></div>'
		)

	return f'<div class="sdm-calendar">{month_blocks}</div>'


def _assignment_label(assignment, team_name):
	"""Ports ir_shift_design.js's assignment_label() (~line 1913)."""
	team_suffix = re.sub(r"^Shift\s+", "", team_name or "", flags=re.IGNORECASE)
	label = f"{assignment} {team_suffix}" if assignment else f"Off {team_suffix}"
	return escape_html(label)


def _team_key_for_shift(shift_label, team_keys):
	letter = (shift_label or "").replace("Shift", "").strip()
	if letter not in SHIFT_LETTERS:
		return None
	index = SHIFT_LETTERS.index(letter)
	return team_keys[index] if index < len(team_keys) else None


def _resolve_allowances_total(branch, designation, on_date, current_salary_structure):
	"""Site Specific Allowances only apply when the Designation's currently
	resolved Salary Structure still matches what an active Site Budget Map
	for this Branch+Designation actually specifies - if the user has
	hand-overridden the row to something else, there's no Map backing that
	choice to attribute allowances from.
	"""
	active_map = resolve_active_site_budget_map(branch, designation, on_date)
	if not active_map or active_map.salary_structure != current_salary_structure:
		return 0

	return compute_site_budget_map_totals(active_map.name)["allowances_total"]


def _notice(message):
	return f'<p class="text-muted">{escape_html(message)}</p>'


def _vacancy_table_html(headcounts):
	if not headcounts:
		return "<h4>Vacancy Summary</h4>" + _notice("No Designations found on the linked Site Organogram.")

	rows = ""
	total_filled = total_vacant = total_headcount = 0
	for designation, counts in sorted(headcounts.items()):
		rows += (
			f"<tr><td>{escape_html(designation)}</td>"
			f"<td>{counts['filled']}</td><td>{counts['vacant']}</td><td>{counts['total']}</td></tr>"
		)
		total_filled += counts["filled"]
		total_vacant += counts["vacant"]
		total_headcount += counts["total"]

	return f"""
	<h4>Vacancy Summary</h4>
	<table class="table table-bordered">
		<thead><tr><th>Designation</th><th>Filled</th><th>Vacant</th><th>Total</th></tr></thead>
		<tbody>{rows}</tbody>
		<tfoot><tr><td><strong>Total</strong></td><td><strong>{total_filled}</strong></td>
		<td><strong>{total_vacant}</strong></td><td><strong>{total_headcount}</strong></td></tr></tfoot>
	</table>
	"""


def _mismatch_table_html(mismatches):
	if not mismatches:
		return "<h4>Designations in the Wrong Role</h4>" + _notice("No mismatches found.")

	rows = "".join(
		f"<tr><td>{escape_html(m['group'])}</td><td>{escape_html(m['shift'])}</td>"
		f"<td>{escape_html(m['row_label'])}</td>"
		f"<td>{escape_html(m['employee_name'])} ({escape_html(m['employee'])})</td>"
		f"<td>{escape_html(m['expected_designation'])}</td>"
		f"<td>{escape_html(m['actual_designation'])}</td></tr>"
		for m in mismatches
	)

	return f"""
	<h4>Designations in the Wrong Role</h4>
	<table class="table table-bordered">
		<thead><tr><th>Group</th><th>Shift</th><th>Role</th><th>Employee</th>
		<th>Expected Designation</th><th>Actual Designation</th></tr></thead>
		<tbody>{rows}</tbody>
	</table>
	"""


def _cost_table_html(
	headcounts,
	salary_structure_by_designation,
	cost_by_designation,
	overtime_cost_by_designation,
	currency_by_designation,
	missing_designations,
	has_hourly_structure=False,
):
	rows = ""
	grand_total = 0.0
	currencies_used = set()

	for designation in sorted(headcounts.keys()):
		salary_structure = salary_structure_by_designation.get(designation)
		if not salary_structure:
			rows += (
				f"<tr class=\"text-danger\"><td>{escape_html(designation)}</td>"
				f"<td colspan=\"3\">Missing Salary Structure</td></tr>"
			)
			continue

		cost = cost_by_designation.get(designation, 0.0)
		overtime_cost = overtime_cost_by_designation.get(designation, 0.0)
		currency = currency_by_designation.get(designation)
		currencies_used.add(currency)
		grand_total += cost
		rows += (
			f"<tr><td>{escape_html(designation)}</td>"
			f"<td>{escape_html(salary_structure)}</td>"
			f"<td>{fmt_money(cost - overtime_cost, currency=currency)}</td>"
			f"<td>{fmt_money(overtime_cost, currency=currency)}</td></tr>"
		)

	banner = (
		f'<p class="text-danger">{len(missing_designations)} Designation(s) missing a Salary Structure '
		f"- cost is incomplete: {escape_html(', '.join(sorted(missing_designations)))}</p>"
		if missing_designations
		else ""
	)

	mixed_currency_note = (
		'<p class="text-muted small">Salary Structures use more than one currency - the grand total below sums raw amounts without conversion.</p>'
		if len(currencies_used) > 1
		else ""
	)

	grand_total_currency = next(iter(currencies_used)) if len(currencies_used) == 1 else None

	hourly_note = (
		'<p class="text-muted small">Some Designations use a timesheet-based ("Hourly") Salary Structure - '
		"their Ordinary cost simulates real ordinary hours from each role's Shift Design roster "
		"(pattern, calendar rules, date overrides, real SA public holidays), not actual timesheets.</p>"
		if has_hourly_structure
		else ""
	)

	return f"""
	<h4>Predicted Labour Cost</h4>
	{banner}
	{mixed_currency_note}
	{hourly_note}
	<table class="table table-bordered">
		<thead><tr><th>Designation</th><th>Salary Structure</th><th>Ordinary Cost</th><th>Overtime Cost</th></tr></thead>
		<tbody>{rows}</tbody>
		<tfoot><tr><td colspan="3"><strong>Grand Total</strong></td><td><strong>{fmt_money(grand_total, currency=grand_total_currency)}</strong></td></tr></tfoot>
	</table>
	"""
