# Copyright (c) 2025, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import random

import frappe
from frappe.utils import add_days, getdate, nowdate

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of KPI Review's own link-field targets (direct, and via its
# three Table fields' own child doctypes: KPI Review Scoring -> Key
# Performance Indicator, KPI Review Employees/Reviewers -> Employee/
# Designation) is ignored here - this test builds its own minimal, synthetic
# fixtures via make_employee()/get_reference_branch() and its own synthetic
# Key Performance Indicator records instead of letting Frappe recursively
# auto-generate them, since that walk pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) which assumes a pristine
# site and collides with this site's real Company/Fiscal Year/Employee
# data. See test_termination_form.py for the same pattern. KPI Template is
# left to point at an existing, real, untouched KPI Template (read-only
# reference - the field is required but never inspected by KPI Review's own
# controller logic).
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"KPI Template",
	"Branch",
	"Key Performance Indicator",
	"Employee",
	"Designation",
]

DUMMY_KPI_ATTACH = "/files/ZZTEST-signed-kpi-review.pdf"


def _reference_kpi_template() -> str:
	"""An existing, real KPI Template - used only as a read-only, required
	Link on the KPI Review header; kpi_review.py's own controller never
	inspects its contents, so this test never writes to it."""
	name = frappe.db.get_value("KPI Template", {}, "name", order_by="creation asc")
	if not name:
		frappe.throw("Need at least one KPI Template on this site to test KPI Review.")
	return name


class IntegrationTestKPIReview(IRSyntheticDataTestCase):
	"""Functional tests for KPI Review's own real controller logic:
	recalculate_weighted_scores() (per-row weighted score + group-KPI score
	aggregation across child KPIs) and ensure_score_limits() (a score may
	not exceed its own KPI row's max_score)."""

	def _make_kpi(self, *, is_group=0, parent_kpi=None):
		kpi = frappe.get_doc(
			{
				"doctype": "Key Performance Indicator",
				"kpi": frappe.generate_hash(length=8),
				"is_group": is_group,
				"parent_kpi": parent_kpi,
			}
		)
		kpi.insert(ignore_permissions=True)
		self.track("Key Performance Indicator", kpi.name)
		return kpi

	def _make_kpi_review(self, review_data, **overrides):
		employee = self.make_employee()
		reviewer = self.make_employee()
		# KPI Review is autonamed as "format:{branch} - {date_of_review}" -
		# a large random historical offset keeps each test's own record from
		# colliding with either another test's record or any real KPI
		# Review already on this site for the same branch.
		review_date = add_days(getdate(nowdate()), -random.randint(1000, 6000))
		values = {
			"doctype": "KPI Review",
			"kpi_template": _reference_kpi_template(),
			"branch": get_reference_branch(),
			"date_of_review": review_date,
			"date_under_review": review_date,
			"employees": [{"employee": employee.name}],
			"reviewers": [{"reviewer": reviewer.name}],
			"review_data": review_data,
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("KPI Review", doc.name)
		return doc

	def test_leaf_kpi_weighted_score_is_computed(self):
		leaf = self._make_kpi()

		doc = self._make_kpi_review(
			[{"kpi": leaf.name, "weight": 50, "max_score": 10, "score": 8}]
		)

		self.assertEqual(doc.review_data[0].weighted_score, 40.0)

	def test_group_kpi_aggregates_children_weighted_scores(self):
		group = self._make_kpi(is_group=1)
		child_1 = self._make_kpi(parent_kpi=group.name)
		child_2 = self._make_kpi(parent_kpi=group.name)

		doc = self._make_kpi_review(
			[
				{"kpi": group.name, "weight": 0, "max_score": 0, "score": 0},
				{"kpi": child_1.name, "weight": 30, "max_score": 10, "score": 10},
				{"kpi": child_2.name, "weight": 20, "max_score": 20, "score": 10},
			]
		)

		rows_by_kpi = {row.kpi: row for row in doc.review_data}
		# child_1: round(10/10*30, 2) = 30.0 ; child_2: round(10/20*20, 2) = 10.0
		self.assertEqual(rows_by_kpi[child_1.name].weighted_score, 30.0)
		self.assertEqual(rows_by_kpi[child_2.name].weighted_score, 10.0)
		# The group row's own weighted_score is overwritten with the sum of
		# its children's weighted scores: 30.0 + 10.0 = 40.0.
		self.assertEqual(rows_by_kpi[group.name].weighted_score, 40.0)

	def test_score_exceeding_max_score_is_rejected(self):
		leaf = self._make_kpi()

		with self.assertRaises(frappe.ValidationError):
			self._make_kpi_review(
				[{"kpi": leaf.name, "weight": 50, "max_score": 10, "score": 15}]
			)

	def test_group_kpi_row_is_exempt_from_score_limit(self):
		# ensure_score_limits() explicitly skips is_group rows, so a group
		# row's own score/max_score values (however nonsensical) never
		# trigger the "score cannot exceed max" guard.
		group = self._make_kpi(is_group=1)

		doc = self._make_kpi_review(
			[{"kpi": group.name, "weight": 100, "max_score": 0, "score": 999}]
		)
		self.assertTrue(doc.name)

	def test_before_submit_requires_kpi_attach(self):
		leaf = self._make_kpi()
		doc = self._make_kpi_review(
			[{"kpi": leaf.name, "weight": 100, "max_score": 10, "score": 5}]
		)

		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_submit_succeeds_with_kpi_attach(self):
		leaf = self._make_kpi()
		doc = self._make_kpi_review(
			[{"kpi": leaf.name, "weight": 100, "max_score": 10, "score": 5}],
			kpi_attach=DUMMY_KPI_ATTACH,
		)

		doc.submit()
		self.assertEqual(doc.docstatus, 1)
