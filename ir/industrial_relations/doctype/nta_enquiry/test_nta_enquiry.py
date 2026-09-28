# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import add_days, now_datetime

from ir.industrial_relations.doctype.nta_enquiry.nta_enquiry import create_nta_enquiry
from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# NTA Enquiry links (directly, or via one of its child tables) to a wide set
# of doctypes - Company/Letter Head/Employee/Branch/Designation/DocType (the
# `ir_intervention` field is a Link to DocType itself) plus the three
# supported source-case doctypes (Disciplinary Action/Incapacity Proceedings/
# Poor Performance) and Employee Rights/Type of Incapacity. Every one of
# these is ignored here - this test builds its own minimal, synthetic
# fixtures via make_employee(), and points `linked_intervention` at an
# existing, real, untouched Poor Performance case (read-only reference,
# never written to) rather than letting Frappe recursively auto-generate
# test records for all of these, which pulls in erpnext/hrms's own legacy
# test-bootstrap code (BootStrapTestData et al) and collides with this
# site's real Company/Fiscal Year/Employee data. See test_termination_form.py
# for the same pattern.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Company",
	"Letter Head",
	"Employee",
	"Designation",
	"Branch",
	"DocType",
	"Employee Rights",
	"Type of Incapacity",
	"Disciplinary Action",
	"Incapacity Proceedings",
	"Poor Performance",
]

DUMMY_SIGNED_NTA = "/files/ZZTEST-signed-nta.pdf"


def _reference_poor_performance() -> str:
	"""An existing, real Poor Performance case with no pre-existing NTA
	Enquiry against it yet - used only as a read-only linked_intervention
	target (existence-checked by validate()); this test never writes to it.
	Picking one with zero existing NTA Enquiries keeps the autoname
	base-name/revision-suffix assertions deterministic regardless of
	whatever real NTA Enquiries already exist on this site."""
	already_linked = set(
		frappe.get_all(
			"NTA Enquiry",
			filters={"ir_intervention": "Poor Performance"},
			pluck="linked_intervention",
		)
	)
	candidates = frappe.get_all(
		"Poor Performance", fields=["name"], order_by="creation asc", pluck="name"
	)
	for name in candidates:
		if name not in already_linked:
			return name
	frappe.throw(
		"Need a Poor Performance record with no existing NTA Enquiry to test NTA Enquiry."
	)


def _reference_employee_rights() -> str:
	name = frappe.db.get_value("Employee Rights", {}, "name", order_by="creation asc")
	if not name:
		frappe.throw("Need at least one Employee Rights record on this site to test NTA Enquiry.")
	return name


class IntegrationTestNTAEnquiry(IRSyntheticDataTestCase):
	"""Functional tests for NTA Enquiry's validate()-time linkage guard
	(supported ir_intervention + an existing linked_intervention case), the
	autoname revision-suffix logic for repeat enquiries against the same
	case, before_submit's signed_nta requirement, and the read-only
	create_nta_enquiry() payload mapping used to prefill a new enquiry from
	its source case."""

	def _base_values(self, **overrides):
		employee = overrides.pop("employee", None) or self.make_employee()
		chairperson = overrides.pop("chairperson", None) or self.make_employee()
		values = {
			"doctype": "NTA Enquiry",
			"ir_intervention": "Poor Performance",
			"linked_intervention": _reference_poor_performance(),
			"employee": employee.name,
			"names": employee.employee_name,
			"position": employee.designation or "ZZTEST Position",
			"hearing_date_time": add_days(now_datetime(), 5),
			"applied_rights": _reference_employee_rights(),
			"venue": get_reference_branch(),
			"chairperson": chairperson.name,
			"chairperson_name": chairperson.employee_name,
		}
		values.update(overrides)
		return values

	def _make_nta_enquiry(self, **overrides):
		doc = frappe.get_doc(self._base_values(**overrides))
		doc.insert(ignore_permissions=True)
		self.track("NTA Enquiry", doc.name)
		return doc

	def test_unsupported_ir_intervention_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				self._base_values(
					ir_intervention="Appeal Against Outcome",
					linked_intervention=_reference_poor_performance(),
				)
			).insert(ignore_permissions=True)

	def test_missing_linked_intervention_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(self._base_values(linked_intervention="")).insert(ignore_permissions=True)

	def test_nonexistent_linked_intervention_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				self._base_values(linked_intervention="ZZTEST-DOES-NOT-EXIST-999")
			).insert(ignore_permissions=True)

	def test_valid_linked_intervention_inserts_with_base_name(self):
		source = _reference_poor_performance()
		doc = self._make_nta_enquiry(linked_intervention=source)
		self.assertEqual(doc.name, f"NTA-{source}")

	def test_second_enquiry_for_same_case_gets_revision_suffix(self):
		source = _reference_poor_performance()
		first = self._make_nta_enquiry(linked_intervention=source)
		second = self._make_nta_enquiry(linked_intervention=source)

		self.assertEqual(first.name, f"NTA-{source}")
		self.assertEqual(second.name, f"NTA-{source}-1")

	def test_before_submit_requires_signed_nta(self):
		doc = self._make_nta_enquiry()
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_submit_succeeds_with_signed_nta_attached(self):
		doc = self._make_nta_enquiry(signed_nta=DUMMY_SIGNED_NTA)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_create_nta_enquiry_maps_poor_performance_payload(self):
		source_name = _reference_poor_performance()
		source = frappe.get_doc("Poor Performance", source_name)

		payload = create_nta_enquiry(source_name=source_name, source_doctype="Poor Performance")

		self.assertEqual(payload.get("ir_intervention"), "Poor Performance")
		self.assertEqual(payload.get("linked_intervention"), source_name)
		# create_nta_enquiry() only stamps the linkage - it does not itself
		# copy the source case's employee/details fields onto the new,
		# unsaved doc (that mapping lives in fetch_intervention_data(),
		# used by the client script separately).
		self.assertFalse(payload.get("name"))

	def test_create_nta_enquiry_rejects_unsupported_source_doctype(self):
		with self.assertRaises(frappe.ValidationError):
			create_nta_enquiry(source_name="Roodepoort", source_doctype="Branch")
