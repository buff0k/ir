# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import unittest

import frappe
from frappe.utils import getdate

from ir.industrial_relations.doctype.shift_design.shift_design import (
	ShiftDesign,
	_apply_continuation_takeover,
	_assignments_for_date,
	_base_assignment,
	_calendar_rule_matches,
	_date_category,
	_hours_for,
	_matching_calendar_rule,
	_pattern_day_for_date,
	_pay_period_bounds,
	count_pay_periods_in_range,
	expand_range_to_pay_periods,
	list_pay_periods_in_range,
	pay_period_month_key,
	team_color,
)
from ir.tests.test_helpers import IRSyntheticDataTestCase, synthetic_name

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every test below is a pure-function test of the calendar-rule precedence
# and pay-period math (the day-by-day roster simulation ports of
# ir_shift_design.js's own JS logic) - all driven by plain arguments/
# frappe._dict rows, so no DB fixtures/Shift Design record is needed at all.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Branch",
	"Company",
	"Shift Type",
]


def _row(**kwargs):
	return frappe._dict(**kwargs)


class TestPayPeriodBounds(unittest.TestCase):
	"""_pay_period_bounds() computes the (start, end) of the pay period
	containing a given date - calendar-aligned when start_day=1/end_day>=28,
	otherwise a non-calendar-aligned cycle (e.g. 16th-15th)."""

	def test_calendar_aligned_period_is_whole_month(self):
		start, end = _pay_period_bounds(1, 31, getdate("2026-06-15"))
		self.assertEqual(start, getdate("2026-06-01"))
		self.assertEqual(end, getdate("2026-06-30"))

	def test_mid_month_cycle_after_start_day_spans_into_next_month(self):
		# 16th-15th cycle: 20 June falls in the period 16 June - 15 July.
		start, end = _pay_period_bounds(16, 15, getdate("2026-06-20"))
		self.assertEqual(start, getdate("2026-06-16"))
		self.assertEqual(end, getdate("2026-07-15"))

	def test_mid_month_cycle_before_start_day_spans_from_previous_month(self):
		# 16th-15th cycle: 10 June falls in the period 16 May - 15 June.
		start, end = _pay_period_bounds(16, 15, getdate("2026-06-10"))
		self.assertEqual(start, getdate("2026-05-16"))
		self.assertEqual(end, getdate("2026-06-15"))


class TestListAndCountPayPeriods(unittest.TestCase):
	def test_lists_every_whole_period_touching_the_range(self):
		periods = list_pay_periods_in_range(1, 31, getdate("2026-06-15"), getdate("2026-08-05"))
		self.assertEqual(
			periods,
			[
				(getdate("2026-06-01"), getdate("2026-06-30")),
				(getdate("2026-07-01"), getdate("2026-07-31")),
				(getdate("2026-08-01"), getdate("2026-08-31")),
			],
		)

	def test_count_matches_list_length(self):
		count = count_pay_periods_in_range(1, 31, getdate("2026-06-15"), getdate("2026-08-05"))
		self.assertEqual(count, 3)

	def test_empty_when_range_start_after_range_end(self):
		self.assertEqual(list_pay_periods_in_range(1, 31, getdate("2026-08-01"), getdate("2026-06-01")), [])


class TestPayPeriodMonthKey(unittest.TestCase):
	def test_keyed_by_the_month_the_period_ends_in(self):
		# A 16th-15th period ending 15 June counts as "June" payroll, same
		# as a calendar-aligned 1-31 June period.
		self.assertEqual(pay_period_month_key(getdate("2026-06-15")), "2026-06")

	def test_zero_padded_month(self):
		self.assertEqual(pay_period_month_key(getdate("2026-01-31")), "2026-01")


class TestExpandRangeToPayPeriods(unittest.TestCase):
	def test_expands_typed_dates_to_full_period_bounds(self):
		# 16th-15th cycle asked for "1-31 Oct" expands to 16 Sep - 15 Nov.
		start, end = expand_range_to_pay_periods(16, 15, getdate("2026-10-01"), getdate("2026-10-31"))
		self.assertEqual(start, getdate("2026-09-16"))
		self.assertEqual(end, getdate("2026-11-15"))

	def test_calendar_aligned_range_is_unchanged_when_already_period_aligned(self):
		start, end = expand_range_to_pay_periods(1, 31, getdate("2026-06-01"), getdate("2026-06-30"))
		self.assertEqual(start, getdate("2026-06-01"))
		self.assertEqual(end, getdate("2026-06-30"))


class TestPatternDayForDate(unittest.TestCase):
	def test_anchor_date_itself_is_day_one(self):
		self.assertEqual(_pattern_day_for_date(getdate("2026-01-01"), 4, getdate("2026-01-01")), 1)

	def test_cycles_around_after_cycle_length(self):
		anchor = getdate("2026-01-01")
		self.assertEqual(_pattern_day_for_date(anchor, 4, getdate("2026-01-05")), 1)
		self.assertEqual(_pattern_day_for_date(anchor, 4, getdate("2026-01-04")), 4)

	def test_date_before_anchor_wraps_backward(self):
		anchor = getdate("2026-01-05")
		# One day before a 4-day cycle's anchor is day 4 of the previous cycle.
		self.assertEqual(_pattern_day_for_date(anchor, 4, getdate("2026-01-04")), 4)

	def test_blank_anchor_defaults_to_day_one(self):
		self.assertEqual(_pattern_day_for_date(None, 4, getdate("2026-01-04")), 1)


class TestBaseAssignment(unittest.TestCase):
	def test_returns_assignment_for_matching_team_and_day(self):
		pattern_rows = [_row(team_key="T1", pattern_day=1, assignment="Day Shift")]
		self.assertEqual(_base_assignment(pattern_rows, "T1", 1), "Day Shift")

	def test_returns_blank_when_no_cell_matches(self):
		pattern_rows = [_row(team_key="T1", pattern_day=1, assignment="Day Shift")]
		self.assertEqual(_base_assignment(pattern_rows, "T1", 2), "")


class TestCalendarRuleMatching(unittest.TestCase):
	def test_public_holiday_rule_matches_by_date(self):
		rule = _row(rule_type="Public Holiday")
		self.assertTrue(_calendar_rule_matches(rule, getdate("2026-01-01"), {"2026-01-01"}))
		self.assertFalse(_calendar_rule_matches(rule, getdate("2026-01-02"), {"2026-01-01"}))

	def test_weekday_rule_matches_by_day_name(self):
		rule = _row(rule_type="Weekday", day_of_week="Sunday")
		# 2026-06-21 is a Sunday.
		self.assertTrue(_calendar_rule_matches(rule, getdate("2026-06-21"), {}))
		self.assertFalse(_calendar_rule_matches(rule, getdate("2026-06-22"), {}))

	def test_public_holiday_takes_precedence_over_weekday(self):
		holiday_rule = _row(rule_type="Public Holiday", priority=10, enabled=1)
		weekday_rule = _row(rule_type="Weekday", day_of_week="Sunday", priority=0, enabled=1)
		holidays = {"2026-06-21"}

		winner = _matching_calendar_rule([weekday_rule, holiday_rule], getdate("2026-06-21"), holidays)

		self.assertIs(winner, holiday_rule)

	def test_lowest_priority_wins_among_same_rule_type(self):
		low_priority = _row(rule_type="Weekday", day_of_week="Sunday", priority=1, enabled=1)
		high_priority = _row(rule_type="Weekday", day_of_week="Sunday", priority=5, enabled=1)

		winner = _matching_calendar_rule([high_priority, low_priority], getdate("2026-06-21"), {})

		self.assertIs(winner, low_priority)

	def test_disabled_rule_is_ignored(self):
		rule = _row(rule_type="Public Holiday", priority=0, enabled=0)
		self.assertIsNone(_matching_calendar_rule([rule], getdate("2026-01-01"), {"2026-01-01"}))

	def test_no_matching_rule_returns_none(self):
		self.assertIsNone(_matching_calendar_rule([], getdate("2026-06-21"), {}))


class TestContinuationTakeover(unittest.TestCase):
	def test_only_teams_on_target_assignment_yesterday_continue_today(self):
		teams = [_row(team_key="T1"), _row(team_key="T2")]
		pattern_rows = [
			_row(team_key="T1", pattern_day=1, assignment="Night Shift"),
			_row(team_key="T2", pattern_day=1, assignment="Day Shift"),
		]
		anchor = getdate("2026-06-01")  # so 2026-06-01 is pattern_day 1

		result = _apply_continuation_takeover(
			pattern_rows, teams, getdate("2026-06-02"), anchor, 1, "Night Shift"
		)

		self.assertEqual(result["T1"], "Night Shift")
		self.assertEqual(result["T2"], "")


class TestHoursFor(unittest.TestCase):
	def test_blank_assignment_has_zero_hours(self):
		self.assertEqual(_hours_for("", getdate("2026-06-01"), [], {}, {"Day Shift": 12.0}), 0)

	def test_uses_shift_type_hours_when_no_rule_override(self):
		hours = _hours_for("Day Shift", getdate("2026-06-01"), [], {}, {"Day Shift": 12.0})
		self.assertEqual(hours, 12.0)

	def test_matching_rule_hours_override_wins(self):
		rule = _row(rule_type="Public Holiday", priority=0, enabled=1, hours_override=8.0)
		hours = _hours_for(
			"Day Shift", getdate("2026-01-01"), [rule], {"2026-01-01"}, {"Day Shift": 12.0}
		)
		self.assertEqual(hours, 8.0)

	def test_zero_hours_override_falls_back_to_shift_type_hours(self):
		# hours_override=0 is falsy - "no override", not "override to zero".
		rule = _row(rule_type="Public Holiday", priority=0, enabled=1, hours_override=0)
		hours = _hours_for(
			"Day Shift", getdate("2026-01-01"), [rule], {"2026-01-01"}, {"Day Shift": 12.0}
		)
		self.assertEqual(hours, 12.0)


class TestDateCategory(unittest.TestCase):
	def test_public_holiday_beats_sunday(self):
		# 2026-06-21 is itself a Sunday - marking it a holiday should still
		# report "public_holiday", not "sunday".
		self.assertEqual(_date_category(getdate("2026-06-21"), {"2026-06-21"}), "public_holiday")

	def test_sunday(self):
		self.assertEqual(_date_category(getdate("2026-06-21"), set()), "sunday")

	def test_saturday(self):
		self.assertEqual(_date_category(getdate("2026-06-20"), set()), "saturday")

	def test_normal_weekday(self):
		self.assertEqual(_date_category(getdate("2026-06-22"), set()), "normal")


class TestAssignmentsForDate(unittest.TestCase):
	"""Full precedence chain: pattern -> matching calendar rule's action ->
	date-specific override."""

	def _base_context(self):
		teams = [_row(team_key="T1"), _row(team_key="T2")]
		pattern_rows = [
			_row(team_key="T1", pattern_day=1, assignment="Day Shift"),
			_row(team_key="T2", pattern_day=1, assignment="Night Shift"),
		]
		return teams, pattern_rows

	def test_plain_pattern_lookup_with_no_rule_or_override(self):
		teams, pattern_rows = self._base_context()
		anchor = getdate("2026-06-01")

		assignments = _assignments_for_date(teams, pattern_rows, [], [], anchor, 1, getdate("2026-06-01"), {})

		self.assertEqual(assignments["T1"], "Day Shift")
		self.assertEqual(assignments["T2"], "Night Shift")

	def test_no_work_calendar_rule_clears_every_team(self):
		teams, pattern_rows = self._base_context()
		anchor = getdate("2026-06-01")
		rule = _row(rule_type="Public Holiday", priority=0, enabled=1, action="No Work")

		assignments = _assignments_for_date(
			teams, pattern_rows, [rule], [], anchor, 1, getdate("2026-01-01"), {"2026-01-01"}
		)

		self.assertEqual(assignments["T1"], "")
		self.assertEqual(assignments["T2"], "")

	def test_follow_pattern_rule_action_leaves_pattern_lookup_untouched(self):
		teams, pattern_rows = self._base_context()
		anchor = getdate("2026-06-01")
		rule = _row(rule_type="Public Holiday", priority=0, enabled=1, action="Follow Pattern")

		assignments = _assignments_for_date(
			teams, pattern_rows, [rule], [], anchor, 1, getdate("2026-01-01"), {"2026-01-01"}
		)

		self.assertEqual(assignments["T1"], "Day Shift")

	def test_date_override_wins_over_pattern(self):
		teams, pattern_rows = self._base_context()
		anchor = getdate("2026-06-01")
		override = _row(date=getdate("2026-06-01"), team_key="T1", assignment="Night Shift", enabled=1)

		assignments = _assignments_for_date(
			teams, pattern_rows, [], [override], anchor, 1, getdate("2026-06-01"), {}
		)

		self.assertEqual(assignments["T1"], "Night Shift")
		self.assertEqual(assignments["T2"], "Night Shift")

	def test_disabled_date_override_is_ignored(self):
		teams, pattern_rows = self._base_context()
		anchor = getdate("2026-06-01")
		override = _row(date=getdate("2026-06-01"), team_key="T1", assignment="Night Shift", enabled=0)

		assignments = _assignments_for_date(
			teams, pattern_rows, [], [override], anchor, 1, getdate("2026-06-01"), {}
		)

		self.assertEqual(assignments["T1"], "Day Shift")


class TestValidateShiftTypes(IRSyntheticDataTestCase):
	"""validate_shift_types() rejects a Shift Type it can't compute hours for -
	but start_time/end_time come back from frappe.db.get_value() as
	datetime.timedelta (Time fieldtype), and timedelta(0) - i.e. a shift
	starting or ending exactly at midnight - is falsy in Python. A truthiness
	check would wrongly reject a perfectly valid midnight-anchored Shift Type
	(e.g. a Night Shift running 15:00-00:00) as "not set"."""

	def test_shift_type_ending_at_midnight_is_not_rejected(self):
		shift_type = frappe.get_doc({
			"doctype": "Shift Type",
			"name": synthetic_name("Night"),
			"start_time": "15:00:00",
			"end_time": "00:00:00",
		})
		shift_type.insert(ignore_permissions=True)
		self.track("Shift Type", shift_type.name)

		fake_self = frappe._dict(shift_types=[frappe._dict(shift_type=shift_type.name)])

		# Should not raise.
		ShiftDesign.validate_shift_types(fake_self)

	def test_shift_type_starting_at_midnight_is_not_rejected(self):
		shift_type = frappe.get_doc({
			"doctype": "Shift Type",
			"name": synthetic_name("Night"),
			"start_time": "00:00:00",
			"end_time": "06:00:00",
		})
		shift_type.insert(ignore_permissions=True)
		self.track("Shift Type", shift_type.name)

		fake_self = frappe._dict(shift_types=[frappe._dict(shift_type=shift_type.name)])

		# Should not raise.
		ShiftDesign.validate_shift_types(fake_self)

	def test_shift_type_with_no_times_set_is_still_rejected(self):
		shift_type = frappe.get_doc({
			"doctype": "Shift Type",
			"name": synthetic_name("Blank"),
			"start_time": "08:00:00",
			"end_time": "16:00:00",
		})
		shift_type.insert(ignore_permissions=True)
		self.track("Shift Type", shift_type.name)
		frappe.db.set_value("Shift Type", shift_type.name, {"start_time": None, "end_time": None})

		fake_self = frappe._dict(shift_types=[frappe._dict(shift_type=shift_type.name)])

		with self.assertRaises(frappe.ValidationError):
			ShiftDesign.validate_shift_types(fake_self)


class TestTeamColor(unittest.TestCase):
	def test_same_index_always_gives_same_color(self):
		self.assertEqual(team_color(0), team_color(0))

	def test_different_indexes_can_give_different_colors(self):
		self.assertNotEqual(team_color(0), team_color(1))

	def test_wraps_around_when_index_exceeds_palette_size(self):
		self.assertEqual(team_color(0), team_color(10))
