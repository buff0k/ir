# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import unittest

import frappe
from frappe.utils import add_days, nowdate

from ir.industrial_relations.doctype.shift_design.shift_design import (
	pay_period_month_key,
)
from ir.industrial_relations.doctype.site_budget.site_budget import (
	_all_pay_period_months,
	_cost_breakdown_for_month,
	_month_label,
	_team_key_for_shift,
)
from ir.tests.test_helpers import IRSyntheticDataTestCase, synthetic_name

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Most tests below are pure-function tests of the cost-computation math
# (_cost_breakdown_for_month() et al.) driven by a hand-built `data` dict, so
# no DB fixtures are needed at all. The one DB-backed test builds its own
# minimal Site Organogram/Shift Design via IRSyntheticDataTestCase rather
# than letting Frappe recursively auto-generate every link-field dependency
# transitively (Overtime Type, Salary Structure, Company, ...), since that
# walk pulls in erpnext/hrms's own legacy test-bootstrap code which assumes a
# pristine site and collides with this site's real data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Site Organogram",
	"Overtime Type",
	"Salary Structure",
	"Designation",
]


class TestMonthLabel(unittest.TestCase):
	def test_formats_month_key_as_month_name_and_year(self):
		self.assertEqual(_month_label("2026-06"), "June 2026")

	def test_pay_period_month_key_matches_month_label_input(self):
		# pay_period_month_key() (shift_design.py) is what actually produces
		# the keys _month_label() (site_budget.py) formats - confirm the two
		# halves of that contract still agree on the "YYYY-MM" shape.
		key = pay_period_month_key("2026-06-15")
		self.assertEqual(_month_label(key), "June 2026")


class TestTeamKeyForShift(unittest.TestCase):
	def test_maps_shift_letter_to_team_key_by_position(self):
		team_keys = ["team-1", "team-2", "team-3"]
		self.assertEqual(_team_key_for_shift("Shift A", team_keys), "team-1")
		self.assertEqual(_team_key_for_shift("Shift B", team_keys), "team-2")
		self.assertEqual(_team_key_for_shift("Shift C", team_keys), "team-3")

	def test_returns_none_for_letter_beyond_configured_teams(self):
		team_keys = ["team-1"]
		self.assertIsNone(_team_key_for_shift("Shift B", team_keys))

	def test_returns_none_for_unparseable_shift_label(self):
		self.assertIsNone(_team_key_for_shift("Day Shift", ["team-1"]))


class TestAllPayPeriodMonths(unittest.TestCase):
	def test_unions_and_sorts_months_across_every_bucket(self):
		data = {
			"hours_by_month_designation": {"2026-07": {}},
			"basic_cost_by_month_designation": {"2026-05": {}},
			"allowance_cost_by_month_designation": {"2026-06": {}},
			"employer_contribution_cost_by_month_designation": {"2026-05": {}},
		}
		self.assertEqual(_all_pay_period_months(data), ["2026-05", "2026-06", "2026-07"])

	def test_empty_when_nothing_recorded(self):
		data = {
			"hours_by_month_designation": {},
			"basic_cost_by_month_designation": {},
			"allowance_cost_by_month_designation": {},
			"employer_contribution_cost_by_month_designation": {},
		}
		self.assertEqual(_all_pay_period_months(data), [])


class TestCostBreakdownForMonth(unittest.TestCase):
	"""Pure-function tests for _cost_breakdown_for_month() - the hourly-rate
	folding and overtime-multiplier math behind Site Budget's cost summary."""

	def test_folds_hourly_ordinary_time_into_basic_and_applies_overtime_multiplier(self):
		data = {
			"hours_by_month_designation": {
				"2026-06": {"Driver": {"NT": 160.0, "Normal OT": 10.0}},
			},
			"basic_cost_by_month_designation": {"2026-06": {"Driver": 5000.0}},
			"allowance_cost_by_month_designation": {"2026-06": {"Driver": 300.0}},
			"employer_contribution_cost_by_month_designation": {"2026-06": {"Driver": 200.0}},
			"hourly_rate_by_designation": {"Driver": 50.0},
			"overtime_type_multiplier": {"Normal OT": 1.5},
		}

		breakdown = _cost_breakdown_for_month(data, "2026-06")

		# basic = fixed Basic/Wages (5000) + NT hours * rate (160 * 50 = 8000)
		self.assertEqual(breakdown["basic"]["Driver"], 5000.0 + 160.0 * 50.0)
		# overtime = OT hours * rate * multiplier (10 * 50 * 1.5 = 750)
		self.assertEqual(breakdown["overtime"]["Driver"], 10.0 * 50.0 * 1.5)
		self.assertEqual(breakdown["allowance"]["Driver"], 300.0)
		self.assertEqual(breakdown["employer_contribution"]["Driver"], 200.0)
		expected_total = (5000.0 + 160.0 * 50.0) + (10.0 * 50.0 * 1.5) + 300.0 + 200.0
		self.assertEqual(breakdown["cost"]["Driver"], expected_total)

	def test_designation_with_only_fixed_cost_and_no_hours_has_zero_overtime(self):
		data = {
			"hours_by_month_designation": {"2026-06": {}},
			"basic_cost_by_month_designation": {"2026-06": {"Supervisor": 8000.0}},
			"allowance_cost_by_month_designation": {"2026-06": {}},
			"employer_contribution_cost_by_month_designation": {"2026-06": {}},
			"hourly_rate_by_designation": {},
			"overtime_type_multiplier": {},
		}

		breakdown = _cost_breakdown_for_month(data, "2026-06")

		self.assertEqual(breakdown["basic"]["Supervisor"], 8000.0)
		self.assertEqual(breakdown["overtime"].get("Supervisor", 0.0), 0.0)
		self.assertEqual(breakdown["cost"]["Supervisor"], 8000.0)

	def test_missing_hourly_rate_defaults_to_zero_rather_than_raising(self):
		data = {
			"hours_by_month_designation": {"2026-06": {"Driver": {"NT": 100.0}}},
			"basic_cost_by_month_designation": {"2026-06": {}},
			"allowance_cost_by_month_designation": {"2026-06": {}},
			"employer_contribution_cost_by_month_designation": {"2026-06": {}},
			"hourly_rate_by_designation": {},
			"overtime_type_multiplier": {},
		}

		breakdown = _cost_breakdown_for_month(data, "2026-06")

		self.assertEqual(breakdown["basic"]["Driver"], 0.0)
		self.assertEqual(breakdown["cost"]["Driver"], 0.0)

	def test_month_with_no_data_at_all_returns_empty_breakdown(self):
		data = {
			"hours_by_month_designation": {},
			"basic_cost_by_month_designation": {},
			"allowance_cost_by_month_designation": {},
			"employer_contribution_cost_by_month_designation": {},
			"hourly_rate_by_designation": {},
			"overtime_type_multiplier": {},
		}

		breakdown = _cost_breakdown_for_month(data, "2026-06")

		self.assertEqual(breakdown["cost"], {})


class IntegrationTestSiteBudgetDbBacked(IRSyntheticDataTestCase):
	"""refresh_designation_costs() needs a real, saved Site Organogram to read
	headcounts from - built here from a minimal synthetic Site Plan + Shift
	Design rather than the full Organogram Designer flow."""

	def _make_shift_design(self, number_of_teams=1):
		shift_type = frappe.db.get_value(
			"Shift Type", {"start_time": ["is", "set"], "end_time": ["is", "set"]}, "name"
		)
		if not shift_type:
			self.skipTest("Site requires at least one Shift Type with Start/End Time set.")

		teams = [
			{
				"team_key": f"TEAM::{frappe.generate_hash(length=6)}",
				"team_name": f"Team {i + 1}",
				"display_order": i,
				"pattern_offset": 0,
				"enabled": 1,
			}
			for i in range(number_of_teams)
		]
		doc = frappe.get_doc({
			"doctype": "Shift Design",
			"design_name": synthetic_name("SD"),
			"status": "Draft",
			"effective_from": nowdate(),
			"number_of_teams": number_of_teams,
			"cycle_length": max(number_of_teams, 1),
			"teams": teams,
			"shift_types": [{"shift_type": shift_type}],
		})
		doc.insert(ignore_permissions=True)
		self.track("Shift Design", doc.name)
		return doc

	def _make_site_plan(self):
		doc = frappe.get_doc({
			"doctype": "Site Plan",
			"plan_name": synthetic_name("SP"),
			"status": "Draft",
			"effective_from": nowdate(),
		})
		doc.insert(ignore_permissions=True)
		self.track("Site Plan", doc.name)
		return doc

	def _make_site_organogram(self, branch, location, site_plan, shift_design):
		asset_category = frappe.db.get_value("Asset Category", {}, "name")
		doc = frappe.get_doc({
			"doctype": "Site Organogram",
			"branch": branch,
			"location": location,
			"site_plan": site_plan,
			"effective_from": nowdate(),
			"asset_categories": [{"asset_cateogories": asset_category}] if asset_category else [],
			"group_headings": [{"group": "Operations", "shift_design": shift_design}],
			"shift_mappings": [
				{"group": "Operations", "shift": "Shift A", "row_type": "Designation", "row_label": "ZZTEST Driver"},
			],
		})
		doc.insert(ignore_permissions=True)
		self.track("Site Organogram", doc.name)
		return doc

	def test_refresh_designation_costs_populates_from_organogram_headcounts(self):
		branch = frappe.db.get_value("Branch", {}, "name")
		location = frappe.db.get_value("Location", {}, "name")
		if not branch or not location:
			self.skipTest("Site requires at least one existing Branch and Location.")

		shift_design = self._make_shift_design(number_of_teams=1)
		site_plan = self._make_site_plan()
		organogram = self._make_site_organogram(branch, location, site_plan.name, shift_design.name)

		budget = frappe.new_doc("Site Budget")
		budget.site_organogram = organogram.name
		budget.refresh_designation_costs()

		rows = {row.designation: row for row in budget.designation_costs}
		self.assertIn("ZZTEST Driver", rows)
		self.assertEqual(rows["ZZTEST Driver"].headcount, 1)
		self.assertEqual(rows["ZZTEST Driver"].filled_count, 0)
		self.assertEqual(rows["ZZTEST Driver"].vacant_count, 1)

	def test_refresh_designation_costs_clears_table_when_no_organogram_linked(self):
		budget = frappe.new_doc("Site Budget")
		budget.append("designation_costs", {"designation": "Leftover", "headcount": 1})
		budget.site_organogram = None
		budget.refresh_designation_costs()

		self.assertEqual(list(budget.designation_costs), [])
