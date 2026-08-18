# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, cint, flt, get_first_day, get_last_day, getdate


class ShiftDesign(Document):
	def before_validate(self):
		self.remove_blank_child_rows()
		self.set_defaults()
		self.ensure_team_keys()
		self.populate_display_values()

	def validate(self):
		self.validate_effective_dates()
		self.validate_pay_period()
		self.validate_cycle_configuration()
		self.validate_shift_types()
		self.validate_teams()
		self.validate_pattern()
		self.validate_calendar_rules()
		self.validate_date_overrides()

	def remove_blank_child_rows(self):
		self.shift_types = [
			row for row in self.shift_types or [] if _clean(row.shift_type)
		]

		self.teams = [
			row
			for row in self.teams or []
			if _clean(row.team_key) or _clean(row.team_name)
		]

		self.pattern = [
			row
			for row in self.pattern or []
			if any(
				[
					_clean(row.team_key),
					cint(row.pattern_day),
					_clean(row.assignment),
				]
			)
		]

		self.calendar_rules = [
			row
			for row in self.calendar_rules or []
			if any(
				[
					_clean(row.rule_type),
					_clean(row.day_of_week),
					_clean(row.action),
					_clean(getattr(row, "target_shift_type", "")),
					flt(getattr(row, "hours_override", 0)),
				]
			)
		]

		self.date_overrides = [
			row
			for row in self.date_overrides or []
			if any(
				[
					row.date,
					_clean(row.team_key),
					_clean(row.assignment),
					_clean(row.reason),
				]
			)
		]

	def set_defaults(self):
		if not self.status:
			self.status = "Draft"

		if self.enabled is None:
			self.enabled = 1

		if not cint(self.number_of_teams):
			self.number_of_teams = 1

		if not cint(self.cycle_length):
			self.cycle_length = 1

		if not self.anchor_date and self.effective_from:
			self.anchor_date = self.effective_from

		if not cint(self.pay_period_start_day):
			self.pay_period_start_day = 1

		if not cint(self.pay_period_end_day):
			self.pay_period_end_day = 31

		if not flt(self.ordinary_hours_limit):
			self.ordinary_hours_limit = 195

	def ensure_team_keys(self):
		for row in self.teams or []:
			if not _clean(row.team_key):
				row.team_key = _new_team_key()

	def populate_display_values(self):
		team_names = {
			_clean(row.team_key): _clean(row.team_name)
			for row in self.teams or []
			if _clean(row.team_key)
		}

		for row in self.pattern or []:
			row.team_name = team_names.get(_clean(row.team_key), "")

		for row in self.date_overrides or []:
			row.team_name = team_names.get(_clean(row.team_key), "")

	def validate_effective_dates(self):
		if (
			self.effective_from
			and self.effective_until
			and getdate(self.effective_until) < getdate(self.effective_from)
		):
			frappe.throw(_("Effective Until cannot be before Effective From."))

		if (
			self.anchor_date
			and self.effective_until
			and getdate(self.anchor_date) > getdate(self.effective_until)
		):
			frappe.throw(_("Cycle Anchor Date cannot be after Effective Until."))

	def validate_pay_period(self):
		start_day = cint(self.pay_period_start_day)
		end_day = cint(self.pay_period_end_day)

		if start_day < 1 or start_day > 31:
			frappe.throw(_("Pay Period Start Day must be between 1 and 31."))

		if end_day < 1 or end_day > 31:
			frappe.throw(_("Pay Period End Day must be between 1 and 31."))

		if flt(self.ordinary_hours_limit) <= 0:
			frappe.throw(_("Ordinary Hours Limit must be greater than zero."))

	def validate_cycle_configuration(self):
		if cint(self.number_of_teams) < 1:
			frappe.throw(_("Number of Shift Teams must be at least 1."))

		if cint(self.number_of_teams) > 20:
			frappe.throw(_("Number of Shift Teams cannot exceed 20."))

		if cint(self.cycle_length) < 1:
			frappe.throw(_("Cycle Length must be at least 1 day."))

		if cint(self.cycle_length) > 366:
			frappe.throw(_("Cycle Length cannot exceed 366 days."))

	def validate_shift_types(self):
		seen = set()

		for row in self.shift_types or []:
			shift_type = _clean(row.shift_type)

			if shift_type in seen:
				frappe.throw(
					_("Shift Type '{0}' is added more than once.").format(shift_type)
				)

			seen.add(shift_type)

			# Shift Types are the sole provider of shift-length hours (there is
			# no fallback-hours mechanism), so a Shift Type that can't compute
			# a duration would silently contribute 0 hours everywhere it's
			# used - reject it here instead of saving that quietly.
			start_time, end_time = frappe.db.get_value(
				"Shift Type", shift_type, ["start_time", "end_time"]
			) or (None, None)

			if not start_time or not end_time:
				frappe.throw(
					_(
						"Shift Type '{0}' has no Start Time/End Time set, so its hours "
						"cannot be computed. Set both on the Shift Type before using it here."
					).format(shift_type)
				)

	def configured_shift_types(self):
		return {
			_clean(row.shift_type)
			for row in self.shift_types or []
			if _clean(row.shift_type)
		}

	def validate_teams(self):
		seen_keys = set()
		seen_names = set()
		enabled_teams = 0

		for row in self.teams or []:
			team_key = _clean(row.team_key)
			team_name = _clean(row.team_name)

			if not team_name:
				frappe.throw(_("Team Name is required in row {0}.").format(row.idx))

			if not team_key:
				frappe.throw(_("Team Key is missing in row {0}.").format(row.idx))

			normalized_name = team_name.casefold()

			if team_key in seen_keys:
				frappe.throw(_("Duplicate Team Key in row {0}.").format(row.idx))

			if normalized_name in seen_names:
				frappe.throw(_("Duplicate Team Name '{0}'.").format(team_name))

			pattern_offset = cint(row.pattern_offset)
			if pattern_offset < 0 or pattern_offset >= cint(self.cycle_length):
				frappe.throw(
					_(
						"Pattern Offset for '{0}' must be between 0 and {1}."
					).format(team_name, cint(self.cycle_length) - 1)
				)

			seen_keys.add(team_key)
			seen_names.add(normalized_name)

			if cint(row.enabled):
				enabled_teams += 1

		if enabled_teams != cint(self.number_of_teams):
			frappe.throw(
				_(
					"Enabled Shift Team rows ({0}) must match Number of Shift Teams ({1})."
				).format(enabled_teams, cint(self.number_of_teams))
			)

	def validate_pattern(self):
		team_keys = {
			_clean(row.team_key)
			for row in self.teams or []
			if _clean(row.team_key)
		}
		shift_types = self.configured_shift_types()
		seen_cells = set()

		for row in self.pattern or []:
			team_key = _clean(row.team_key)
			pattern_day = cint(row.pattern_day)

			if team_key not in team_keys:
				frappe.throw(
					_("Pattern row {0} refers to an unknown Team Key.").format(row.idx)
				)

			if pattern_day < 1 or pattern_day > cint(self.cycle_length):
				frappe.throw(
					_(
						"Pattern Day in row {0} must be between 1 and {1}."
					).format(row.idx, cint(self.cycle_length))
				)

			assignment = _clean(row.assignment)
			if assignment and assignment not in shift_types:
				frappe.throw(
					_(
						"Pattern row {0} refers to a Shift Type not configured on this Design."
					).format(row.idx)
				)

			cell_key = (team_key, pattern_day)
			if cell_key in seen_cells:
				frappe.throw(
					_(
						"Duplicate Pattern cell for Team '{0}', Day {1}."
					).format(row.team_name or team_key, pattern_day)
				)

			seen_cells.add(cell_key)

	def validate_calendar_rules(self):
		# Note: target_shift_type is intentionally NOT required to be one of this
		# Design's rotating `shift_types` - a Calendar Rule may invoke a distinct,
		# special-purpose Shift Type (e.g. a "Sunday Day" shift with its own
		# hours) that never appears in the normal rotation at all. The Link
		# field itself already guarantees it's a real Shift Type record.
		actions_needing_target = {"Continue Previous Shift Team"}

		for row in self.calendar_rules or []:
			if _clean(row.rule_type) == "Weekday" and not _clean(row.day_of_week):
				frappe.throw(
					_("Calendar Rule row {0} requires a Day of Week.").format(row.idx)
				)

			action = _clean(row.action)
			target_shift_type = _clean(getattr(row, "target_shift_type", ""))

			if action in actions_needing_target and not target_shift_type:
				frappe.throw(
					_("Calendar Rule row {0} requires a Target Shift Type.").format(row.idx)
				)

			if flt(getattr(row, "hours_override", 0)) < 0:
				frappe.throw(_("Hours Override cannot be negative."))

	def validate_date_overrides(self):
		team_keys = {
			_clean(row.team_key)
			for row in self.teams or []
			if _clean(row.team_key)
		}
		shift_types = self.configured_shift_types()
		seen = set()

		for row in self.date_overrides or []:
			team_key = _clean(row.team_key)

			if team_key and team_key not in team_keys:
				frappe.throw(
					_("Date Override row {0} refers to an unknown Team Key.").format(row.idx)
				)

			assignment = _clean(row.assignment)
			if assignment and assignment not in shift_types:
				frappe.throw(
					_(
						"Date Override row {0} refers to a Shift Type not configured on this Design."
					).format(row.idx)
				)

			key = (getdate(row.date), team_key)
			if key in seen:
				frappe.throw(
					_("Duplicate Date Override for {0}, Team '{1}'.").format(
						row.date,
						row.team_name or team_key or "All",
					)
				)
			seen.add(key)


def _clean(value):
	return str(value or "").strip()


def _new_team_key():
	return f"TEAM::{frappe.generate_hash(length=10)}"


def _pay_period_bounds(start_day, end_day, current_date):
	"""Mirrors ir_shift_design.js's pay_period_for_date() (~line 1693) -
	keep both in sync if that logic ever changes. Returns the (start, end)
	date bounds of the pay period containing current_date."""
	start_day = max(cint(start_day), 1)
	end_day = max(cint(end_day), 1)

	if start_day == 1 and end_day >= 28:
		return get_first_day(current_date), get_last_day(current_date)

	if current_date.day >= start_day:
		period_start = current_date.replace(day=min(start_day, get_last_day(current_date).day))
		next_month = add_months(current_date, 1)
		period_end = next_month.replace(day=min(end_day, get_last_day(next_month).day))
	else:
		previous_month = add_months(current_date, -1)
		period_start = previous_month.replace(day=min(start_day, get_last_day(previous_month).day))
		period_end = current_date.replace(day=min(end_day, get_last_day(current_date).day))

	return period_start, period_end


def count_pay_periods_in_range(pay_period_start_day, pay_period_end_day, range_start, range_end):
	"""How many distinct pay periods (whole cycles, not day-fractions - a
	labour budget is for whole pay periods worked, not prorated days)
	overlap [range_start, range_end]."""
	range_start = getdate(range_start)
	range_end = getdate(range_end)

	if range_start > range_end:
		return 0

	count = 0
	cursor = range_start

	while cursor <= range_end:
		_period_start, period_end = _pay_period_bounds(pay_period_start_day, pay_period_end_day, cursor)
		count += 1
		cursor = add_days(period_end, 1)

	return count


def count_pay_periods_for_shift_design(shift_design, range_start, range_end):
	if not shift_design or not range_start or not range_end:
		return 0

	start_day, end_day = frappe.db.get_value(
		"Shift Design", shift_design, ["pay_period_start_day", "pay_period_end_day"]
	)
	return count_pay_periods_in_range(start_day, end_day, range_start, range_end)


def expand_range_to_pay_periods(pay_period_start_day, pay_period_end_day, range_start, range_end):
	"""Expands [range_start, range_end] out to the full bounds of whichever
	pay periods contain those two dates - so a caller wanting "every day of
	every pay period touching the requested range" (as opposed to the
	literal typed dates) gets a range aligned to the real, possibly non-
	calendar-aligned payroll cycle (e.g. a 16th-15th cycle asked for
	"1-31 Oct" expands to 16 Sep - 15 Nov). Matches count_pay_periods_in_range()'s
	own definition of which periods "touch" the range, so hours simulated over
	the expanded range and the whole-period count used for fixed-cost
	multiplication agree with each other."""
	range_start = getdate(range_start)
	range_end = getdate(range_end)
	period_start, _period_end = _pay_period_bounds(pay_period_start_day, pay_period_end_day, range_start)
	_period_start, period_end = _pay_period_bounds(pay_period_start_day, pay_period_end_day, range_end)
	return period_start, period_end


def expand_range_to_pay_periods_for_shift_design(shift_design, range_start, range_end):
	if not shift_design or not range_start or not range_end:
		return range_start, range_end

	start_day, end_day = frappe.db.get_value(
		"Shift Design", shift_design, ["pay_period_start_day", "pay_period_end_day"]
	)
	return expand_range_to_pay_periods(start_day, end_day, range_start, range_end)


def get_ordered_team_keys(shift_design):
	"""Enabled teams' team_key, ordered by display_order - the same ordering
	used everywhere else in the app to assign "Shift A"/"Shift B"/... letters
	to teams (SHIFT_LETTERS in site_organogram.py), so index 0 is "Shift A",
	index 1 is "Shift B", etc. Site Budget uses this to match a headcount
	slot's "Shift" label back to the specific team simulate_team_hours()
	computed hours for.
	"""
	if not shift_design:
		return []

	doc = frappe.get_doc("Shift Design", shift_design)
	teams = sorted(
		[row for row in (doc.teams or []) if cint(row.enabled)],
		key=lambda row: cint(row.display_order),
	)
	return [team.team_key for team in teams]


def _pattern_day_for_date(anchor_date, cycle_length, date):
	"""Ports ir_shift_design.js's pattern_day_for_date() (~line 1843)."""
	if not anchor_date:
		return 1
	length = max(cint(cycle_length), 1)
	difference = (getdate(date) - getdate(anchor_date)).days
	return ((difference % length) + length) % length + 1


def _base_assignment(pattern_rows, team_key, pattern_day):
	"""Ports ir_shift_design.js's assignment() (~line 1803): raw pattern-grid
	lookup, ignoring calendar rules/date overrides."""
	for row in pattern_rows:
		if row.team_key == team_key and cint(row.pattern_day) == cint(pattern_day):
			return row.assignment or ""
	return ""


def _calendar_rule_matches(rule, date, holidays):
	"""Ports ir_shift_design.js's calendar_rule_matches() (~line 1587)."""
	if rule.rule_type == "Public Holiday":
		return str(date) in holidays
	if rule.rule_type == "Weekday":
		return getdate(date).strftime("%A") == rule.day_of_week
	return False


def _matching_calendar_rule(calendar_rules, date, holidays):
	"""Ports ir_shift_design.js's matching_calendar_rule() (~line 1597):
	Public Holiday rules beat Weekday rules, then lowest priority wins."""
	matching = [
		rule
		for rule in calendar_rules
		if cint(rule.enabled if rule.enabled is not None else 1) and _calendar_rule_matches(rule, date, holidays)
	]
	if not matching:
		return None
	matching.sort(key=lambda rule: (0 if rule.rule_type == "Public Holiday" else 1, cint(rule.priority)))
	return matching[0]


def _apply_continuation_takeover(pattern_rows, teams, date, anchor_date, cycle_length, target_assignment):
	"""Ports ir_shift_design.js's apply_continuation_takeover() (~line 1632):
	only the team(s) on `target_assignment` the previous calendar day (per
	the raw pattern, not calendar rules) work today, on that same
	assignment - every other team is off."""
	previous_date = add_days(date, -1)
	previous_pattern_day = _pattern_day_for_date(anchor_date, cycle_length, previous_date)
	continuing = {
		team.team_key
		for team in teams
		if _base_assignment(pattern_rows, team.team_key, previous_pattern_day) == target_assignment
	}
	return {team.team_key: (target_assignment if team.team_key in continuing else "") for team in teams}


def _apply_rule_action(assignments, rule, teams, pattern_rows, date, anchor_date, cycle_length):
	"""Ports ir_shift_design.js's apply_rule_action() (~line 1616)."""
	if rule.action == "No Work":
		return {team.team_key: "" for team in teams}
	if rule.action == "Continue Previous Shift Team":
		return _apply_continuation_takeover(
			pattern_rows, teams, date, anchor_date, cycle_length, rule.target_shift_type
		)
	return dict(assignments)


def _date_overrides_for(date_overrides, date):
	"""Ports ir_shift_design.js's date_overrides_for() (~line 1654)."""
	result = {}
	for row in date_overrides:
		if (
			cint(row.enabled if row.enabled is not None else 1)
			and row.date
			and getdate(row.date) == getdate(date)
			and row.team_key
		):
			result[row.team_key] = row.assignment or ""
	return result


def _assignments_for_date(teams, pattern_rows, calendar_rules, date_overrides, anchor_date, cycle_length, date, holidays):
	"""Ports ir_shift_design.js's assignments_for_date() (~line 1669): pattern,
	then a matching calendar rule's action, then date-specific overrides."""
	pattern_day = _pattern_day_for_date(anchor_date, cycle_length, date)
	assignments = {team.team_key: _base_assignment(pattern_rows, team.team_key, pattern_day) for team in teams}

	rule = _matching_calendar_rule(calendar_rules, date, holidays)
	if rule and rule.action != "Follow Pattern":
		assignments = _apply_rule_action(assignments, rule, teams, pattern_rows, date, anchor_date, cycle_length)

	for team_key, forced in _date_overrides_for(date_overrides, date).items():
		if team_key in assignments:
			assignments[team_key] = forced

	return assignments


def _hours_for(assignment, date, calendar_rules, holidays, shift_type_hours):
	"""Ports ir_shift_design.js's hours_for() (~line 1813): a matching
	calendar rule's hours_override wins, else the assignment's own Shift
	Type duration."""
	if not assignment:
		return 0

	rule = _matching_calendar_rule(calendar_rules, date, holidays)
	override = flt(rule.hours_override) if rule else 0
	if override:
		return override

	return flt(shift_type_hours.get(assignment, 0))


def _date_category(date, holidays):
	"""Public Holiday > Sunday > Saturday > Normal - the precedence Site
	Budget's overtime costing uses to pick which Overtime Type applies."""
	if str(date) in holidays:
		return "public_holiday"
	weekday = getdate(date).weekday()  # Monday=0 .. Sunday=6
	if weekday == 6:
		return "sunday"
	if weekday == 5:
		return "saturday"
	return "normal"


TEAM_COLORS = [
	"#3b82f6", "#22c55e", "#f59e0b", "#d946ef", "#06b6d4",
	"#ef4444", "#84cc16", "#8b5cf6", "#ec4899", "#eab308",
]


def team_color(index):
	"""Ports ir_shift_design.js's team_color() - a team's index in the
	enabled/display_order-sorted teams list (the same list get_ordered_team_keys()
	and simulate_team_hours() use) picks its color, so a team is the same
	color in Shift Design's own calendar and Site Budget's roster calendar."""
	return TEAM_COLORS[index % len(TEAM_COLORS)]


_WEEKDAY_APPLIES_FIELDS = {
	0: "applies_monday", 1: "applies_tuesday", 2: "applies_wednesday", 3: "applies_thursday",
	4: "applies_friday", 5: "applies_saturday", 6: "applies_sunday",
}  # date.weekday(): Monday=0 .. Sunday=6


def _is_allowed_on_weekday(shift_type_configs, assignment, date):
	"""Ports ir_shift_design.js's is_allowed_on_weekday() (~line 746): a
	blank/unconfigured applies_<weekday> flag means "allowed" (Frappe Check
	fields can't distinguish "not set" from falsy)."""
	if not assignment:
		return True
	row = shift_type_configs.get(assignment)
	if not row:
		return True
	value = row.get(_WEEKDAY_APPLIES_FIELDS[getdate(date).weekday()])
	return value is None or bool(cint(value))


def _load_roster_context(shift_design, range_start, range_end):
	"""Shared setup for simulate_team_hours() and get_roster_calendar_data():
	loads the Shift Design doc plus everything needed to resolve daily
	assignments/hours/categories over [range_start, range_end]. Returns None
	if the design has no enabled teams or the range is invalid."""
	from ir.industrial_relations.page.ir_shift_design.ir_shift_design import (
		_duration_hours,
		get_sa_public_holidays,
	)

	if not shift_design or not range_start or not range_end:
		return None

	range_start = getdate(range_start)
	range_end = getdate(range_end)
	if range_start > range_end:
		return None

	doc = frappe.get_doc("Shift Design", shift_design)

	teams = sorted(
		[row for row in (doc.teams or []) if cint(row.enabled)],
		key=lambda row: cint(row.display_order),
	)
	if not teams:
		return None

	pattern_rows = doc.pattern or []
	calendar_rules = doc.calendar_rules or []
	date_overrides = doc.date_overrides or []
	shift_type_configs = {row.shift_type: row for row in doc.shift_types or [] if row.shift_type}

	shift_type_names = {row.assignment for row in pattern_rows if row.assignment}
	shift_type_names.update(row.target_shift_type for row in calendar_rules if row.target_shift_type)
	shift_type_names.update(row.assignment for row in date_overrides if row.assignment)

	shift_type_hours = {}
	if shift_type_names:
		for row in frappe.get_all(
			"Shift Type",
			filters={"name": ["in", list(shift_type_names)]},
			fields=["name", "start_time", "end_time"],
		):
			shift_type_hours[row.name] = _duration_hours(row.start_time, row.end_time)

	holiday_rows = get_sa_public_holidays(range_start, range_end)
	holidays = {row["date"] for row in holiday_rows}
	holiday_names = {row["date"]: row["description"] for row in holiday_rows}

	return {
		"doc": doc,
		"teams": teams,
		"pattern_rows": pattern_rows,
		"calendar_rules": calendar_rules,
		"date_overrides": date_overrides,
		"shift_type_configs": shift_type_configs,
		"shift_type_hours": shift_type_hours,
		"holidays": holidays,
		"holiday_names": holiday_names,
		"range_start": range_start,
		"range_end": range_end,
	}


def _iter_daily_assignments(context):
	"""Shared day-walking loop behind simulate_team_hours() (aggregate
	totals) and get_roster_calendar_data() (full per-date detail): yields
	(date, team, assignment, hours, category) for every enabled team on
	every date in the context's range, using the same precedence
	assignments_for_date() uses (pattern -> calendar rule -> date override)."""
	doc = context["doc"]
	cursor = context["range_start"]
	while cursor <= context["range_end"]:
		assignments = _assignments_for_date(
			context["teams"], context["pattern_rows"], context["calendar_rules"], context["date_overrides"],
			doc.anchor_date, doc.cycle_length, cursor, context["holidays"],
		)
		category = _date_category(cursor, context["holidays"])

		for team in context["teams"]:
			assignment = assignments.get(team.team_key, "")
			hours = _hours_for(assignment, cursor, context["calendar_rules"], context["holidays"], context["shift_type_hours"])
			yield cursor, team, assignment, hours, category

		cursor = add_days(cursor, 1)


def simulate_team_hours_by_month(shift_design, range_start, range_end):
	"""Same day-by-day roster simulation and per-team-per-pay-period Ordinary
	Hours Limit bucketing as simulate_team_hours(), but additionally grouped
	by calendar month (the month each day itself falls in, not the pay
	period's start) - Site Budget's Excel export reports hours per
	Designation per month, matching how payroll actually runs (one payslip
	per month), even though the Ordinary Hours Limit bucketing itself still
	operates per pay period (which may not be calendar-aligned).

	Returns {team_key: {month_key: {"ordinary": h, "overtime": {"normal": h,
	"saturday": h, "sunday": h, "public_holiday": h}}}}, month_key "YYYY-MM".
	Every enabled team is present as a key, even with an empty month dict if
	it has zero hours across the whole range.
	"""
	context = _load_roster_context(shift_design, range_start, range_end)
	if not context:
		return {}

	ordinary_limit = flt(context["doc"].ordinary_hours_limit)
	results = {team.team_key: {} for team in context["teams"]}
	ordinary_used = {}  # (team_key, pay-period start date) -> hours already counted as ordinary

	for date, team, assignment, hours, category in _iter_daily_assignments(context):
		if not hours:
			continue

		period_start, _period_end = _pay_period_bounds(
			context["doc"].pay_period_start_day, context["doc"].pay_period_end_day, date
		)
		key = (team.team_key, period_start)
		used = ordinary_used.get(key, 0.0)
		ordinary_hours = max(min(hours, ordinary_limit - used), 0.0)
		overtime_hours = hours - ordinary_hours
		ordinary_used[key] = used + hours

		months = results[team.team_key]
		month_key = f"{date.year:04d}-{date.month:02d}"
		if month_key not in months:
			months[month_key] = {
				"ordinary": 0.0,
				"overtime": {"normal": 0.0, "saturday": 0.0, "sunday": 0.0, "public_holiday": 0.0},
			}
		months[month_key]["ordinary"] += ordinary_hours
		if overtime_hours:
			months[month_key]["overtime"][category] += overtime_hours

	return results


def simulate_team_hours(shift_design, range_start, range_end):
	"""Ports ir_shift_design.js's own day-by-day roster simulation (pattern
	cycle -> calendar rule overrides -> date overrides, same precedence as
	assignments_for_date(), plus the same per-team-per-pay-period Ordinary
	Hours Limit bucketing its hours table uses) to estimate each enabled
	team's real ordinary vs overtime hours over [range_start, range_end],
	with overtime further split by day-category (normal/saturday/sunday/
	public_holiday) so Site Budget can apply a different Overtime Type's
	multiplier per category. This is a costing estimate, not real payroll.

	A thin aggregator over simulate_team_hours_by_month() - kept as its own
	function since most callers only need the range-wide total.

	Returns {team_key: {"ordinary": hours, "overtime": {"normal": h, "saturday": h, "sunday": h, "public_holiday": h}}}
	"""
	by_month = simulate_team_hours_by_month(shift_design, range_start, range_end)

	results = {}
	for team_key, months in by_month.items():
		ordinary = 0.0
		overtime = {"normal": 0.0, "saturday": 0.0, "sunday": 0.0, "public_holiday": 0.0}
		for month_data in months.values():
			ordinary += month_data["ordinary"]
			for category, hours in month_data["overtime"].items():
				overtime[category] += hours
		results[team_key] = {"ordinary": ordinary, "overtime": overtime}

	return results


def get_roster_calendar_data(shift_design, range_start, range_end):
	"""Per-date, per-team roster detail for calendar rendering (Site
	Budget's Shift Roster Calendar) - shares the exact same day-by-day
	resolution simulate_team_hours() uses for its aggregate totals, so the
	calendar and the cost totals can never disagree.

	Returns {"holidays": {date: name}, "teams": [{"team_key", "team_name"}, ...],
	"days": {date: {team_key: {"assignment": x, "hours": h, "category": c, "conflict": bool}}}}
	"""
	context = _load_roster_context(shift_design, range_start, range_end)
	if not context:
		return {"holidays": {}, "teams": [], "days": {}}

	days = {}
	for date, team, assignment, hours, category in _iter_daily_assignments(context):
		days.setdefault(str(date), {})[team.team_key] = {
			"assignment": assignment,
			"hours": hours,
			"category": category,
			"conflict": not _is_allowed_on_weekday(context["shift_type_configs"], assignment, date),
		}

	return {
		"holidays": context["holiday_names"],
		"teams": [{"team_key": team.team_key, "team_name": team.team_name} for team in context["teams"]],
		"days": days,
	}
