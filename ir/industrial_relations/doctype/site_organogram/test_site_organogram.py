# Copyright (c) 2025, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import unittest

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.industrial_relations.doctype.site_organogram.branch_staffing import (
	_clean_branch_list,
	_valid_organogram_on,
)
from ir.industrial_relations.doctype.site_organogram.site_organogram import (
	_derive_row_key,
	_get_asset_category_summary,
	_get_vacancy_summary,
	_iter_designation_slots,
	_parse_row_key,
	_row_key_for_asset,
	_row_key_for_designation,
	compute_plan_slot_key_backfill,
	get_designation_headcounts,
	get_designation_mismatches,
	get_designation_slots_by_group,
	normalize_group_structure,
	normalize_mappings,
	normalize_reporting_lines,
)
from ir.tests.test_helpers import IRSyntheticDataTestCase

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Site Organogram's own link-field targets (direct, and via its
# child tables) is ignored here - most tests below are pure-function tests
# against plain frappe._dict stand-ins that need no DB fixtures at all, and
# the few that do touch the DB build their own minimal synthetic Employee via
# make_employee()/get_reference_company(), rather than letting Frappe
# recursively auto-generate every dependency, since that walk pulls in
# erpnext/hrms's own legacy test-bootstrap code (BootStrapTestData et al)
# which assumes a pristine site and collides with this site's real
# Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Branch",
	"Location",
	"Site Plan",
	"Asset Category",
	"Employee",
	"Designation",
	"Asset",
	"Shift Design",
]


def _row(**kwargs):
	return frappe._dict(**kwargs)


class TestRowKeyHelpers(unittest.TestCase):
	"""Pure-function tests for the ASSET::/DESIG:: row-key mini-format that
	identifies a physical row across shift columns."""

	def test_parse_row_key_asset(self):
		info = _parse_row_key("ASSET::PLANT-001")
		self.assertEqual(info["kind"], "Asset")
		self.assertEqual(info["asset"], "PLANT-001")

	def test_parse_row_key_designation(self):
		info = _parse_row_key("DESIG::Dozer Operator::ab12cd")
		self.assertEqual(info["kind"], "Designation")
		self.assertEqual(info["designation"], "Dozer Operator")
		self.assertEqual(info["token"], "ab12cd")

	def test_parse_row_key_unknown_for_blank_or_garbage(self):
		self.assertEqual(_parse_row_key("")["kind"], "Unknown")
		self.assertEqual(_parse_row_key("garbage")["kind"], "Unknown")

	def test_row_key_for_asset_format(self):
		self.assertEqual(_row_key_for_asset("PLANT-001"), "ASSET::PLANT-001")

	def test_row_key_for_designation_falls_back_to_unlinked_role(self):
		key = _row_key_for_designation("", token="tok")
		self.assertEqual(key, "DESIG::Unlinked Role::tok")

	def test_derive_row_key_prefers_existing_value(self):
		row = _row(row_key="ASSET::PLANT-999", row_type="Designation")
		self.assertEqual(_derive_row_key(row), "ASSET::PLANT-999")

	def test_derive_row_key_builds_asset_key_from_asset_field(self):
		row = _row(row_key="", row_type="Asset", asset="PLANT-777")
		self.assertEqual(_derive_row_key(row), "ASSET::PLANT-777")

	def test_derive_row_key_builds_missing_asset_key_when_no_asset(self):
		row = _row(row_key="", row_type="Asset", asset="")
		self.assertTrue(_derive_row_key(row).startswith("MISSING_ASSET::"))

	def test_derive_row_key_builds_designation_key_from_label(self):
		row = _row(row_key="", row_type="Designation", row_label="Driver")
		key = _derive_row_key(row)
		self.assertTrue(key.startswith("DESIG::Driver::"))


class TestNormalizeGroupStructure(unittest.TestCase):
	"""Pure-function tests for normalize_group_structure() - assigning stable
	group_key values to headings and mirroring them onto mapping rows."""

	def test_assigns_key_to_heading_with_blank_key(self):
		heading = _row(group="Operations", group_key="")
		doc = _row(group_headings=[heading], shift_mappings=[])

		normalize_group_structure(doc)

		self.assertTrue(heading.group_key.startswith("GRP::"))

	def test_mirrors_key_onto_mapping_matched_by_existing_key(self):
		heading = _row(group="Operations", group_key="GRP::fixed")
		mapping = _row(group="Old Label", group_key="GRP::fixed")
		doc = _row(group_headings=[heading], shift_mappings=[mapping])

		normalize_group_structure(doc)

		self.assertEqual(mapping.group_key, "GRP::fixed")
		self.assertEqual(mapping.group, "Operations")

	def test_mirrors_key_onto_mapping_matched_by_label_when_key_blank(self):
		heading = _row(group="Operations", group_key="")
		mapping = _row(group="Operations", group_key="")
		doc = _row(group_headings=[heading], shift_mappings=[mapping])

		normalize_group_structure(doc)

		self.assertEqual(mapping.group_key, heading.group_key)

	def test_duplicate_heading_key_is_reassigned(self):
		first = _row(group="A", group_key="GRP::dup")
		second = _row(group="B", group_key="GRP::dup")
		doc = _row(group_headings=[first, second], shift_mappings=[])

		normalize_group_structure(doc)

		self.assertEqual(first.group_key, "GRP::dup")
		self.assertNotEqual(second.group_key, "GRP::dup")


class TestNormalizeReportingLines(unittest.TestCase):
	"""Pure-function tests for normalize_reporting_lines()."""

	def _heading(self, group, key):
		return _row(group=group, group_key=key)

	def test_scope_defaults_to_heading_and_invalid_scope_corrected(self):
		line = _row(
			source_group="A", source_group_key="", source_scope="Bogus", source_shift="Shift A",
			target_group="B", target_group_key="", target_scope="", target_shift="",
		)
		doc = _row(group_headings=[], reporting_lines=[line])

		normalize_reporting_lines(doc)

		self.assertEqual(line.source_scope, "Heading")
		self.assertEqual(line.target_scope, "Heading")

	def test_shift_cleared_when_scope_is_heading(self):
		line = _row(
			source_group="A", source_group_key="", source_scope="Heading", source_shift="Shift A",
			target_group="B", target_group_key="", target_scope="Heading", target_shift="Shift B",
		)
		doc = _row(group_headings=[], reporting_lines=[line])

		normalize_reporting_lines(doc)

		self.assertEqual(line.source_shift, "")
		self.assertEqual(line.target_shift, "")

	def test_shift_kept_when_scope_is_shift(self):
		line = _row(
			source_group="A", source_group_key="", source_scope="Shift", source_shift="Shift A",
			target_group="B", target_group_key="", target_scope="Shift", target_shift="Shift B",
		)
		doc = _row(group_headings=[], reporting_lines=[line])

		normalize_reporting_lines(doc)

		self.assertEqual(line.source_shift, "Shift A")
		self.assertEqual(line.target_shift, "Shift B")

	def test_endpoint_repaired_by_label_when_key_blank(self):
		heading = self._heading("Operations", "GRP::ops")
		line = _row(
			source_group="Operations", source_group_key="", source_scope="Heading", source_shift="",
			target_group="Operations", target_group_key="", target_scope="Heading", target_shift="",
		)
		doc = _row(group_headings=[heading], reporting_lines=[line])

		normalize_reporting_lines(doc)

		self.assertEqual(line.source_group_key, "GRP::ops")
		self.assertEqual(line.target_group_key, "GRP::ops")

	def test_defaults_for_line_type_and_anchors_and_order(self):
		line_one = _row(
			source_group="A", source_group_key="", source_scope="Heading", source_shift="",
			target_group="B", target_group_key="", target_scope="Heading", target_shift="",
		)
		line_two = _row(
			source_group="A", source_group_key="", source_scope="Heading", source_shift="",
			target_group="C", target_group_key="", target_scope="Heading", target_shift="",
		)
		doc = _row(group_headings=[], reporting_lines=[line_one, line_two])

		normalize_reporting_lines(doc)

		for line in (line_one, line_two):
			self.assertEqual(line.line_type, "Solid")
			self.assertEqual(line.source_anchor, "Auto")
			self.assertEqual(line.target_anchor, "Auto")

		self.assertEqual(line_one.line_order, 1)
		self.assertEqual(line_two.line_order, 2)


class TestNormalizeMappings(unittest.TestCase):
	"""Pure-function tests for normalize_mappings() - the server-side safety
	net that repairs row identity/labels/order without ever deleting rows."""

	def test_asset_row_with_nonexistent_asset_is_flagged_missing(self):
		row = _row(row_key="ASSET::FAKE-DOES-NOT-EXIST", row_type="", asset="", row_label="", group="G", idx=1)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.row_type, "Asset")
		self.assertEqual(row.asset, "")
		self.assertEqual(row.missing_asset, 1)
		self.assertEqual(row.row_label, "FAKE-DOES-NOT-EXIST")

	def test_designation_row_clears_asset_fields(self):
		row = _row(
			row_key="DESIG::Driver::tok1", row_type="", asset="SOME-ASSET",
			row_label="", designation="SOME-DESIGNATION", group="G", idx=1,
		)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.row_type, "Designation")
		self.assertEqual(row.asset, "")
		self.assertEqual(row.missing_asset, 0)
		self.assertEqual(row.designation, "")
		self.assertEqual(row.row_label, "Driver")

	def test_designation_row_can_never_be_spare_swing(self):
		row = _row(row_key="DESIG::Driver::tok1", row_type="", asset="", row_label="", spare_swing=1, group="G", idx=1)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.spare_swing, 0)

	def test_spare_swing_clears_employee_and_missing_employee(self):
		row = _row(
			row_key="ASSET::FAKE", row_type="", asset="", row_label="Missing",
			spare_swing=1, employee="ZZ-BOGUS-EMPLOYEE", missing_employee=0, group="G", idx=1,
		)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.employee, "")
		self.assertEqual(row.missing_employee, 0)

	def test_acting_is_cleared_when_no_employee_assigned(self):
		row = _row(row_key="DESIG::Driver::tok1", row_type="", asset="", row_label="", employee="", acting=1, group="G", idx=1)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.acting, 0)

	def test_acting_is_cleared_when_employee_is_missing(self):
		row = _row(
			row_key="DESIG::Driver::tok1", row_type="", asset="", row_label="",
			employee="ZZ-BOGUS-EMPLOYEE-DOES-NOT-EXIST", acting=1, group="G", idx=1,
		)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.employee, "")
		self.assertEqual(row.acting, 0)

	def test_acting_is_cleared_when_row_marked_spare_swing(self):
		row = _row(
			row_key="ASSET::FAKE", row_type="Asset", asset="", row_label="Missing",
			spare_swing=1, employee="ZZ-BOGUS-EMPLOYEE", acting=1, group="G", idx=1,
		)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.employee, "")
		self.assertEqual(row.acting, 0)

	def test_nonexistent_employee_is_cleared_and_flagged_missing(self):
		row = _row(
			row_key="DESIG::Driver::tok1", row_type="", asset="", row_label="",
			employee="ZZ-BOGUS-EMPLOYEE-DOES-NOT-EXIST", group="G", idx=1,
		)
		doc = _row(shift_mappings=[row])

		normalize_mappings(doc)

		self.assertEqual(row.employee, "")
		self.assertEqual(row.missing_employee, 1)

	def test_spare_swing_is_shared_across_sibling_shift_rows_with_same_key(self):
		row_a = _row(row_key="ASSET::FAKE", row_type="Asset", asset="", row_label="Missing", spare_swing=1, employee="", group="G", idx=1)
		row_b = _row(row_key="ASSET::FAKE", row_type="Asset", asset="", row_label="Missing", spare_swing=0, employee="ZZ-BOGUS", group="G", idx=2)
		doc = _row(shift_mappings=[row_a, row_b])

		normalize_mappings(doc)

		self.assertEqual(row_b.spare_swing, 1)
		self.assertEqual(row_b.employee, "")

	def test_default_designation_propagates_to_sibling_asset_rows(self):
		row_a = _row(row_key="ASSET::FAKE", row_type="Asset", asset="", row_label="Missing", designation="", group="G", idx=1)
		row_b = _row(row_key="ASSET::FAKE", row_type="Asset", asset="", row_label="Missing", designation="Dozer Operator", group="G", idx=2)
		doc = _row(shift_mappings=[row_a, row_b])

		normalize_mappings(doc)

		self.assertEqual(row_a.designation, "Dozer Operator")
		self.assertEqual(row_b.designation, "Dozer Operator")

	def test_row_order_is_stable_and_sequential_per_group(self):
		row_a = _row(row_key="ASSET::A", row_type="Asset", asset="", row_label="A", group="G", idx=2, row_order=0)
		row_b = _row(row_key="ASSET::B", row_type="Asset", asset="", row_label="B", group="G", idx=1, row_order=0)
		doc = _row(shift_mappings=[row_a, row_b])

		normalize_mappings(doc)

		# idx=1 (row_b) sorts before idx=2 (row_a) when row_order ties at 0.
		self.assertEqual(row_b.row_order, 1)
		self.assertEqual(row_a.row_order, 2)

	def test_no_rows_is_a_no_op(self):
		doc = _row(shift_mappings=[])
		normalize_mappings(doc)  # must not raise
		self.assertEqual(doc.shift_mappings, [])


class TestVacancyAndDesignationHelpers(unittest.TestCase):
	"""Pure-function tests for the vacancy/headcount/mismatch helpers that
	don't require any real Employee/Asset - only synthetic shift_mappings
	rows already carrying a resolved row_type/row_key/designation, as
	normalize_mappings() would have left them."""

	def test_vacancy_summary_counts_vacant_designation_and_asset_rows(self):
		vacant_designation = _row(row_type="Designation", row_key="DESIG::Driver::t1", row_label="Driver", employee="", shift="Shift A")
		filled_designation = _row(row_type="Designation", row_key="DESIG::Driver::t2", row_label="Driver", employee="EMP-1", shift="Shift B")
		vacant_asset = _row(row_type="Asset", asset="PLANT-1", designation="", spare_swing=0, employee="", shift="Shift A")
		spare_asset = _row(row_type="Asset", asset="PLANT-2", designation="", spare_swing=1, employee="", shift="Shift A")
		doc = _row(shift_mappings=[vacant_designation, filled_designation, vacant_asset, spare_asset], assets=[])

		summary = _get_vacancy_summary(doc)

		self.assertEqual(summary["by_designation"], {"Driver": 1})
		self.assertEqual(len(summary["vacant_assets"]), 1)
		self.assertEqual(summary["vacant_assets"][0][0], "PLANT-1")
		# Spare/Swing assets are never vacancies, even though unfilled.
		self.assertEqual(summary["total"], 2)

	def test_vacant_asset_with_designation_counts_in_both_buckets(self):
		row = _row(row_type="Asset", asset="PLANT-1", designation="Dozer Operator", spare_swing=0, employee="", shift="Shift A")
		doc = _row(shift_mappings=[row], assets=[])

		summary = _get_vacancy_summary(doc)

		self.assertEqual(summary["by_designation"], {"Dozer Operator": 1})
		self.assertEqual(len(summary["vacant_assets"]), 1)
		# Counted once in `total`, even though it appears in both buckets.
		self.assertEqual(summary["total"], 1)

	def test_asset_category_summary_counts_primary_and_spare_swing_per_category(self):
		"""Mirrors a real site's fleet: 4 Dozers, 6 Excavators, 20 primary ADTs
		plus 4 Spare/Swing ADTs - all unlinked ("Missing") placeholder slots,
		so category comes from row_label, matching this app's real current
		data on at least one live site."""
		rows = []
		for i in range(4):
			rows.append(_row(row_type="Asset", group="Dozers", row_key=f"ASSET::D{i}", row_label="Dozer", missing_asset=1, spare_swing=0, shift="Shift A"))
		for i in range(6):
			rows.append(_row(row_type="Asset", group="Excavators", row_key=f"ASSET::E{i}", row_label="Excavator", missing_asset=1, spare_swing=0, shift="Shift A"))
		for i in range(20):
			rows.append(_row(row_type="Asset", group="ADTs", row_key=f"ASSET::A{i}", row_label="ADT", missing_asset=1, spare_swing=0, shift="Shift A"))
		for i in range(4):
			rows.append(_row(row_type="Asset", group="ADTs", row_key=f"ASSET::AS{i}", row_label="ADT", missing_asset=1, spare_swing=1, shift="Shift A"))
		doc = _row(shift_mappings=rows, assets=[])

		summary = _get_asset_category_summary(doc)

		self.assertEqual(summary["Dozer"], {"primary": 4, "spare_swing": 0})
		self.assertEqual(summary["Excavator"], {"primary": 6, "spare_swing": 0})
		self.assertEqual(summary["ADT"], {"primary": 20, "spare_swing": 4})

	def test_asset_category_summary_uses_linked_asset_category_over_row_label(self):
		row = _row(row_type="Asset", group="ADTs", row_key="ASSET::PLANT-1", row_label="ADT", asset="PLANT-1", missing_asset=0, spare_swing=0, shift="Shift A")
		doc = _row(shift_mappings=[row], assets=[_row(asset="PLANT-1", item_name="Bell ADT", asset_category="Articulated Dump Truck")])

		summary = _get_asset_category_summary(doc)

		self.assertEqual(summary, {"Articulated Dump Truck": {"primary": 1, "spare_swing": 0}})

	def test_asset_category_summary_slot_is_spare_if_any_shift_copy_is(self):
		"""Same physical asset slot (group + row_key) referenced once per
		shift column - spare_swing set on only one shift's copy should still
		mark the whole slot as Spare/Swing, not just that one shift."""
		shift_a = _row(row_type="Asset", group="ADTs", row_key="ASSET::A1", row_label="ADT", missing_asset=1, spare_swing=0, shift="Shift A")
		shift_b = _row(row_type="Asset", group="ADTs", row_key="ASSET::A1", row_label="ADT", missing_asset=1, spare_swing=1, shift="Shift B")
		doc = _row(shift_mappings=[shift_a, shift_b], assets=[])

		summary = _get_asset_category_summary(doc)

		self.assertEqual(summary["ADT"], {"primary": 0, "spare_swing": 1})

	def test_iter_designation_slots_skips_spare_swing_and_asset_without_designation(self):
		spare = _row(row_type="Asset", asset="PLANT-1", designation="Dozer Operator", spare_swing=1, employee="", shift="Shift A", group="G", group_key="GK", row_label="")
		no_designation = _row(row_type="Asset", asset="PLANT-2", designation="", spare_swing=0, employee="", shift="Shift A", group="G", group_key="GK", row_label="")
		staffable = _row(row_type="Asset", asset="PLANT-3", designation="Dozer Operator", spare_swing=0, employee="", shift="Shift A", group="G", group_key="GK", row_label="")
		doc = _row(shift_mappings=[spare, no_designation, staffable])

		slots = list(_iter_designation_slots(doc))

		self.assertEqual(len(slots), 1)
		self.assertEqual(slots[0]["designation"], "Dozer Operator")

	def test_designation_headcounts_totals_filled_and_vacant(self):
		filled = _row(row_type="Designation", row_key="DESIG::Driver::t1", row_label="Driver", employee="EMP-1", shift="Shift A", group="G", group_key="GK")
		vacant = _row(row_type="Designation", row_key="DESIG::Driver::t2", row_label="Driver", employee="", shift="Shift B", group="G", group_key="GK")
		doc = _row(shift_mappings=[filled, vacant])

		counts = get_designation_headcounts(doc)

		self.assertEqual(counts["Driver"], {"filled": 1, "vacant": 1, "total": 2})

	def test_designation_slots_by_group_breaks_down_by_shift(self):
		row_a = _row(row_type="Designation", row_key="DESIG::Driver::t1", row_label="Driver", employee="", shift="Shift A", group="G", group_key="GK")
		row_b = _row(row_type="Designation", row_key="DESIG::Driver::t2", row_label="Driver", employee="", shift="Shift B", group="G", group_key="GK")
		doc = _row(shift_mappings=[row_a, row_b], group_headings=[_row(group_key="GK", shift_design="SD-1")])

		by_group = get_designation_slots_by_group(doc)

		self.assertEqual(by_group["GK"]["shift_design"], "SD-1")
		self.assertEqual(by_group["GK"]["designation_counts"], {"Driver": 2})
		self.assertEqual(by_group["GK"]["by_shift"]["Shift A"], {"Driver": 1})
		self.assertEqual(by_group["GK"]["by_shift"]["Shift B"], {"Driver": 1})


class TestValidOrganogramOn(unittest.TestCase):
	"""Pure-function tests for branch_staffing._valid_organogram_on(), passing
	`candidates` explicitly so no DB query is made."""

	def test_picks_organogram_valid_on_date(self):
		today = getdate(nowdate())
		candidates = [
			_row(name="OG-1", branch="Branch A", effective_from=add_days(today, -30), effective_until=add_days(today, -1)),
			_row(name="OG-2", branch="Branch A", effective_from=add_days(today, -10), effective_until=None),
		]

		result = _valid_organogram_on("Branch A", today, candidates=candidates)

		self.assertEqual(result.name, "OG-2")

	def test_returns_none_when_nothing_valid(self):
		today = getdate(nowdate())
		candidates = [
			_row(name="OG-1", branch="Branch A", effective_from=add_days(today, 10), effective_until=None),
		]

		self.assertIsNone(_valid_organogram_on("Branch A", today, candidates=candidates))

	def test_latest_effective_from_wins_when_multiple_qualify(self):
		today = getdate(nowdate())
		candidates = [
			_row(name="OG-OLD", branch="Branch A", effective_from=add_days(today, -60), effective_until=None),
			_row(name="OG-NEW", branch="Branch A", effective_from=add_days(today, -5), effective_until=None),
		]

		result = _valid_organogram_on("Branch A", today, candidates=candidates)

		self.assertEqual(result.name, "OG-NEW")

	def test_ignores_candidates_for_other_branches(self):
		today = getdate(nowdate())
		candidates = [
			_row(name="OG-OTHER", branch="Branch B", effective_from=add_days(today, -5), effective_until=None),
		]

		self.assertIsNone(_valid_organogram_on("Branch A", today, candidates=candidates))


class TestCleanBranchList(unittest.TestCase):
	def test_none_is_empty(self):
		self.assertEqual(_clean_branch_list(None), [])

	def test_json_string_is_parsed(self):
		self.assertEqual(_clean_branch_list('["Branch A", "Branch B"]'), ["Branch A", "Branch B"])

	def test_comma_string_fallback(self):
		self.assertEqual(_clean_branch_list("Branch A, Branch B"), ["Branch A", "Branch B"])

	def test_list_passthrough_drops_blanks(self):
		self.assertEqual(_clean_branch_list(["Branch A", "", None]), ["Branch A"])


class IntegrationTestSiteOrganogramDbBacked(IRSyntheticDataTestCase):
	"""The few behaviours that genuinely need a real Employee row: company
	filtering and Designation-mismatch detection both read the Employee's
	own company/designation from the database."""

	def test_headcounts_company_filter_falls_back_filled_to_vacant(self):
		other_company_employee = self.make_employee()
		filled = _row(
			row_type="Designation", row_key="DESIG::Driver::t1", row_label="Driver",
			employee=other_company_employee.name, shift="Shift A", group="G", group_key="GK",
		)
		doc = _row(shift_mappings=[filled])

		# A different Company than the Employee's own -> falls to vacant.
		fake_other_company = "ZZTEST-NO-SUCH-COMPANY"
		counts = get_designation_headcounts(doc, company=fake_other_company)
		self.assertEqual(counts["Driver"], {"filled": 0, "vacant": 1, "total": 1})

		# The Employee's real own Company -> counts as filled.
		counts_same_company = get_designation_headcounts(doc, company=other_company_employee.company)
		self.assertEqual(counts_same_company["Driver"], {"filled": 1, "vacant": 0, "total": 1})

	def test_designation_mismatch_detected_when_employee_role_differs(self):
		employee = self.make_employee()
		slot = _row(
			row_type="Designation", row_key="DESIG::Dozer Operator::t1", row_label="Dozer Operator",
			employee=employee.name, shift="Shift A", group="G", group_key="GK",
		)
		doc = _row(shift_mappings=[slot], employees=[
			_row(employee=employee.name, employee_name=employee.employee_name, designation="Multi-Skilled Operator"),
		])

		mismatches = get_designation_mismatches(doc)

		self.assertEqual(len(mismatches), 1)
		self.assertEqual(mismatches[0]["expected_designation"], "Dozer Operator")
		self.assertEqual(mismatches[0]["actual_designation"], "Multi-Skilled Operator")

	def test_no_mismatch_when_employee_role_matches(self):
		employee = self.make_employee()
		slot = _row(
			row_type="Designation", row_key="DESIG::Dozer Operator::t1", row_label="Dozer Operator",
			employee=employee.name, shift="Shift A", group="G", group_key="GK",
		)
		doc = _row(shift_mappings=[slot], employees=[
			_row(employee=employee.name, employee_name=employee.employee_name, designation="Dozer Operator"),
		])

		self.assertEqual(get_designation_mismatches(doc), [])


class TestComputePlanSlotKeyBackfill(unittest.TestCase):
	"""compute_plan_slot_key_backfill() is the Python twin of
	populate_from_plan()'s own matching in ir_organogram_design.js - both
	exist because an Asset row's row_key changes (MISSING_ASSET::<token> ->
	ASSET::<id>) the moment a real Asset is committed (assign_asset()), but
	a Site Plan's own Slot has no such identity to give it, so a literal
	row_key match alone can no longer find that row on a later re-populate."""

	def test_already_resolved_asset_row_is_relinked_not_duplicated(self):
		# Simulates real legacy data: an Asset row already committed to a
		# real Asset before plan_slot_key existed - row_key is now
		# ASSET::<id>, and plan_slot_key was never set.
		existing = _row(
			name="mapping-1", group_key="G1", shift="Shift A", row_type="Asset",
			row_key="ASSET::DZ-001", row_order=1, plan_slot_key="", employee="EMP-1",
		)
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotA", "plan_slot_key": "SLOT::slotA", "row_order": 1},
		]

		writes, matched, relinked = compute_plan_slot_key_backfill([existing], template_rows)

		self.assertEqual(writes, [("mapping-1", "SLOT::slotA")])
		self.assertEqual(matched, 1)
		self.assertEqual(relinked, 1)

	def test_row_already_carrying_plan_slot_key_is_left_alone(self):
		existing = _row(
			name="mapping-1", group_key="G1", shift="Shift A", row_type="Asset",
			row_key="ASSET::DZ-001", row_order=1, plan_slot_key="SLOT::slotA", employee="EMP-1",
		)
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotA", "plan_slot_key": "SLOT::slotA", "row_order": 1},
		]

		writes, matched, relinked = compute_plan_slot_key_backfill([existing], template_rows)

		self.assertEqual(writes, [])
		self.assertEqual(matched, 1)
		self.assertEqual(relinked, 0)

	def test_designation_row_matches_directly_by_row_key_no_relink_needed(self):
		# Designation row_keys are never rewritten client-side, so the
		# literal row_key match already finds these - only the missing
		# plan_slot_key itself needs backfilling.
		existing = _row(
			name="mapping-1", group_key="G1", shift="Shift A", row_type="Designation",
			row_key="DESIG::Dozer Operator::tok1", row_order=1, plan_slot_key="", employee="EMP-2",
		)
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Designation",
			 "row_key": "DESIG::Dozer Operator::tok1", "plan_slot_key": "SLOT::slotB", "row_order": 1},
		]

		writes, matched, relinked = compute_plan_slot_key_backfill([existing], template_rows)

		self.assertEqual(writes, [("mapping-1", "SLOT::slotB")])
		self.assertEqual(relinked, 0)

	def test_genuinely_new_slot_with_no_existing_row_is_not_matched(self):
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotA", "plan_slot_key": "SLOT::slotA", "row_order": 1},
		]

		writes, matched, relinked = compute_plan_slot_key_backfill([], template_rows)

		self.assertEqual(writes, [])
		self.assertEqual(matched, 0)
		self.assertEqual(relinked, 0)

	def test_multiple_resolved_asset_rows_relink_positionally_in_row_order(self):
		# Two already-resolved Asset rows in the same group/shift - must
		# pair up oldest-first (by row_order), not by insertion order.
		row_a = _row(name="mapping-A", group_key="G1", shift="Shift A", row_type="Asset",
			row_key="ASSET::DZ-002", row_order=2, plan_slot_key="", employee="EMP-2")
		row_b = _row(name="mapping-B", group_key="G1", shift="Shift A", row_type="Asset",
			row_key="ASSET::DZ-001", row_order=1, plan_slot_key="", employee="EMP-1")
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotA", "plan_slot_key": "SLOT::slotA", "row_order": 1},
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotB", "plan_slot_key": "SLOT::slotB", "row_order": 2},
		]

		# Insertion order deliberately doesn't match row_order.
		writes, matched, relinked = compute_plan_slot_key_backfill([row_a, row_b], template_rows)

		self.assertEqual(dict(writes), {"mapping-B": "SLOT::slotA", "mapping-A": "SLOT::slotB"})
		self.assertEqual(relinked, 2)

	def test_idempotent_second_pass_after_backfill_writes_nothing(self):
		existing = _row(
			name="mapping-1", group_key="G1", shift="Shift A", row_type="Asset",
			row_key="ASSET::DZ-001", row_order=1, plan_slot_key="", employee="EMP-1",
		)
		template_rows = [
			{"group_key": "G1", "shift": "Shift A", "row_type": "Asset",
			 "row_key": "MISSING_ASSET::slotA", "plan_slot_key": "SLOT::slotA", "row_order": 1},
		]

		writes, _, _ = compute_plan_slot_key_backfill([existing], template_rows)
		existing.plan_slot_key = writes[0][1]  # simulate the write actually landing

		writes_again, matched_again, relinked_again = compute_plan_slot_key_backfill([existing], template_rows)

		self.assertEqual(writes_again, [])
		self.assertEqual(matched_again, 1)
		self.assertEqual(relinked_again, 0)
