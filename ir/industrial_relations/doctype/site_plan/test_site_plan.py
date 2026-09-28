# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import unittest

import frappe
from frappe.utils import add_days, nowdate

from ir.industrial_relations.doctype.site_plan.site_plan import export_site_plan_excel
from ir.tests.test_helpers import IRSyntheticDataTestCase, synthetic_name

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# resolve_group_keys_by_label()/ensure_group_keys()/ensure_slot_keys() are
# tested directly against a plain frappe.new_doc("Site Plan") (no insert),
# so they need no DB fixtures at all. The Excel-export totals test does need
# a real saved Site Plan (with a real linked Shift Design for its team
# count) - built here from a minimal synthetic Shift Design rather than
# letting Frappe recursively auto-generate every link-field dependency
# transitively, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code which assumes a pristine site and collides with this
# site's real Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Branch",
	"Location",
	"Shift Design",
	"Designation",
	"Asset Category",
]


def _new_site_plan(**overrides):
	values = {
		"doctype": "Site Plan",
		"plan_name": synthetic_name("SP"),
		"status": "Draft",
		"effective_from": nowdate(),
	}
	values.update(overrides)
	return frappe.new_doc("Site Plan").update(values)


class TestEnsureGroupKeys(unittest.TestCase):
	def test_blank_group_key_is_assigned(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "shift_design": ""})

		doc.ensure_group_keys()

		self.assertTrue(doc.groups[0].group_key.startswith("GRP::"))

	def test_existing_group_key_is_kept(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::fixed"})

		doc.ensure_group_keys()

		self.assertEqual(doc.groups[0].group_key, "GRP::fixed")


class TestResolveGroupKeysByLabel(unittest.TestCase):
	"""A Slot/Reporting Line saved via Data Import only carries the group
	*label* (no group_key column in the exported CSV template) - this must
	backfill the key from the label before remove_blank_child_rows() treats
	a still-blank group_key as orphaned and silently drops the row."""

	def test_slot_group_key_backfilled_from_label(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::ops"})
		doc.append("slots", {"group": "Operations", "group_key": "", "row_type": "Designation", "row_label": "Driver"})

		doc.resolve_group_keys_by_label()

		self.assertEqual(doc.slots[0].group_key, "GRP::ops")

	def test_reporting_line_source_and_target_backfilled_from_label(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::ops"})
		doc.append("groups", {"group": "Maintenance", "group_key": "GRP::maint"})
		doc.append("reporting_lines", {
			"source_group": "Operations", "source_group_key": "",
			"target_group": "Maintenance", "target_group_key": "",
		})

		doc.resolve_group_keys_by_label()

		self.assertEqual(doc.reporting_lines[0].source_group_key, "GRP::ops")
		self.assertEqual(doc.reporting_lines[0].target_group_key, "GRP::maint")

	def test_slot_with_no_matching_label_is_left_blank(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::ops"})
		doc.append("slots", {"group": "No Such Group", "group_key": "", "row_type": "Designation", "row_label": "Driver"})

		doc.resolve_group_keys_by_label()

		self.assertEqual(doc.slots[0].group_key, "")

	def test_slot_already_carrying_a_group_key_is_untouched(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::ops"})
		doc.append("slots", {"group": "Operations", "group_key": "GRP::already-set", "row_type": "Designation", "row_label": "Driver"})

		doc.resolve_group_keys_by_label()

		self.assertEqual(doc.slots[0].group_key, "GRP::already-set")


class TestEnsureSlotKeys(unittest.TestCase):
	def test_blank_row_key_gets_a_fresh_key(self):
		doc = _new_site_plan()
		doc.append("slots", {"group_key": "GRP::ops", "row_type": "Designation", "row_label": "Driver", "row_key": ""})

		doc.ensure_slot_keys()

		self.assertTrue(doc.slots[0].row_key.startswith("SLOT::"))

	def test_duplicate_row_key_is_repaired_on_the_second_occurrence(self):
		doc = _new_site_plan()
		doc.append("slots", {"group_key": "GRP::ops", "row_type": "Asset", "row_label": "Dozer 1", "row_key": "SLOT::dup"})
		doc.append("slots", {"group_key": "GRP::ops", "row_type": "Asset", "row_label": "Dozer 2", "row_key": "SLOT::dup"})

		doc.ensure_slot_keys()

		self.assertEqual(doc.slots[0].row_key, "SLOT::dup")
		self.assertNotEqual(doc.slots[1].row_key, "SLOT::dup")
		self.assertTrue(doc.slots[1].row_key.startswith("SLOT::"))

	def test_unique_row_keys_are_left_untouched(self):
		doc = _new_site_plan()
		doc.append("slots", {"group_key": "GRP::ops", "row_type": "Asset", "row_label": "Dozer 1", "row_key": "SLOT::one"})
		doc.append("slots", {"group_key": "GRP::ops", "row_type": "Asset", "row_label": "Dozer 2", "row_key": "SLOT::two"})

		doc.ensure_slot_keys()

		self.assertEqual(doc.slots[0].row_key, "SLOT::one")
		self.assertEqual(doc.slots[1].row_key, "SLOT::two")


class TestPopulateDisplayValues(unittest.TestCase):
	def test_slot_and_reporting_line_group_labels_synced_from_group_key(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "Operations", "group_key": "GRP::ops"})
		doc.append("slots", {"group_key": "GRP::ops", "group": "Stale Label", "row_type": "Designation", "row_label": "Driver"})
		doc.append("reporting_lines", {
			"source_group_key": "GRP::ops", "source_group": "Stale",
			"target_group_key": "GRP::ops", "target_group": "Stale",
		})

		doc.populate_display_values()

		self.assertEqual(doc.slots[0].group, "Operations")
		self.assertEqual(doc.reporting_lines[0].source_group, "Operations")
		self.assertEqual(doc.reporting_lines[0].target_group, "Operations")


class TestValidateEffectiveDates(unittest.TestCase):
	def test_rejects_effective_until_before_effective_from(self):
		doc = _new_site_plan(effective_from=nowdate(), effective_until=add_days(nowdate(), -1))
		with self.assertRaises(frappe.ValidationError):
			doc.validate_effective_dates()

	def test_allows_effective_until_after_effective_from(self):
		doc = _new_site_plan(effective_from=nowdate(), effective_until=add_days(nowdate(), 10))
		doc.validate_effective_dates()  # must not raise


class TestValidateGroupAndSlotReferences(unittest.TestCase):
	def test_duplicate_group_key_is_rejected(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "A", "group_key": "GRP::dup"})
		doc.append("groups", {"group": "B", "group_key": "GRP::dup"})

		with self.assertRaises(frappe.ValidationError):
			doc.validate_group_keys_unique()

	def test_slot_referencing_unknown_group_is_rejected(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "A", "group_key": "GRP::real"})
		doc.append("slots", {"group_key": "GRP::does-not-exist", "row_type": "Designation", "row_label": "Driver"})

		with self.assertRaises(frappe.ValidationError):
			doc.validate_slots_reference_groups()

	def test_reporting_line_referencing_unknown_group_is_rejected(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "A", "group_key": "GRP::real"})
		doc.append("reporting_lines", {"source_group_key": "GRP::real", "target_group_key": "GRP::missing"})

		with self.assertRaises(frappe.ValidationError):
			doc.validate_reporting_lines_reference_groups()


class TestRemoveBlankChildRows(unittest.TestCase):
	def test_blank_group_row_is_dropped(self):
		doc = _new_site_plan()
		doc.append("groups", {"group": "", "shift_design": ""})
		doc.append("groups", {"group": "Real Group", "shift_design": ""})

		doc.remove_blank_child_rows()

		self.assertEqual(len(doc.groups), 1)
		self.assertEqual(doc.groups[0].group, "Real Group")

	def test_slot_with_a_group_key_but_nothing_else_is_dropped(self):
		doc = _new_site_plan()
		doc.append("slots", {"group_key": "GRP::ops", "designation": "", "asset_category": "", "row_label": ""})
		doc.append("slots", {"group_key": "GRP::ops", "row_label": "Driver"})

		doc.remove_blank_child_rows()

		self.assertEqual(len(doc.slots), 1)
		self.assertEqual(doc.slots[0].row_label, "Driver")


class IntegrationTestSitePlanExcelExport(IRSyntheticDataTestCase):
	"""export_site_plan_excel()'s Designation/Asset-Category totals logic is
	inline in that function rather than a separate pure function, so this
	exercises it end-to-end against a real saved Site Plan and inspects the
	generated workbook - the only way to verify the multiplication rules
	without duplicating that logic in the test itself:
	- a Designation slot's required count is multiplied by its Group's own
	  Shift Design team count (a different person needed per shift).
	- an Asset slot's Asset Category count is NOT multiplied (one physical
	  asset, however many shifts operate it) - but the Designation
	  attached to a non-spare Asset slot IS multiplied, same as a plain
	  Designation slot.
	- a Spare/Swing Asset slot never contributes to the Designation total,
	  even though it carries a Designation value.
	"""

	def _make_shift_design(self, number_of_teams):
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

	def test_designation_and_asset_category_totals(self):
		designations = frappe.get_all("Designation", limit=2, pluck="name")
		asset_category = frappe.db.get_value("Asset Category", {}, "name")
		if len(designations) < 2 or not asset_category:
			self.skipTest("Site requires at least 2 existing Designations and 1 Asset Category.")

		designation_one, designation_two = designations[0], designations[1]

		two_team_design = self._make_shift_design(number_of_teams=2)
		one_team_design = self._make_shift_design(number_of_teams=1)

		doc = frappe.get_doc({
			"doctype": "Site Plan",
			"plan_name": synthetic_name("SP"),
			"status": "Draft",
			"effective_from": nowdate(),
			"groups": [
				{"group": "Two Team Group", "shift_design": two_team_design.name},
				{"group": "One Team Group", "shift_design": one_team_design.name},
			],
		})
		doc.insert(ignore_permissions=True)
		self.track("Site Plan", doc.name)

		two_team_key = doc.groups[0].group_key
		one_team_key = doc.groups[1].group_key

		doc.append("slots", {
			"group_key": two_team_key, "row_type": "Designation", "designation": designation_one, "row_label": designation_one,
		})
		doc.append("slots", {
			"group_key": two_team_key, "row_type": "Asset", "asset_category": asset_category,
			"designation": designation_two, "row_label": "Dozer", "spare_swing": 0,
		})
		doc.append("slots", {
			"group_key": two_team_key, "row_type": "Asset", "asset_category": asset_category,
			"designation": designation_one, "row_label": "Spare Dozer", "spare_swing": 1,
		})
		doc.append("slots", {
			"group_key": one_team_key, "row_type": "Designation", "designation": designation_two, "row_label": designation_two,
		})
		doc.save(ignore_permissions=True)

		export_site_plan_excel(doc.name)

		filecontent = frappe.local.response["filecontent"]
		from io import BytesIO

		from openpyxl import load_workbook

		wb = load_workbook(BytesIO(filecontent))
		ws = wb.active

		designation_totals = {}
		category_totals = {}
		section = None
		for row in ws.iter_rows(values_only=True):
			if row[0] == "TOTAL EMPLOYEES REQUIRED BY DESIGNATION":
				section = "designation"
				continue
			if row[0] == "TOTAL ASSETS REQUIRED BY ASSET CATEGORY":
				section = "category"
				continue
			if row[0] in ("DESIGNATION", "ASSET CATEGORY"):
				continue
			if section == "designation" and row[0] and row[0] != "None":
				designation_totals[row[0]] = row[1]
			elif section == "category" and row[0] and row[0] != "None":
				category_totals[row[0]] = row[1]

		# designation_one: 1 (plain Designation slot, x2 teams) + 2 (spare
		# Asset slot's designation is ignored, contributes 0) = 2.
		self.assertEqual(designation_totals.get(designation_one), 2)
		# designation_two: 2 (non-spare Asset slot's designation, x2 teams)
		# + 1 (plain Designation slot in the one-team group, x1) = 3.
		self.assertEqual(designation_totals.get(designation_two), 3)
		# Asset Category counted once per physical Asset slot (2 Asset
		# slots in the two-team group), never multiplied by team count.
		self.assertEqual(category_totals.get(asset_category), 2)
