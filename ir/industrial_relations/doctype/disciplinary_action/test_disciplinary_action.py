# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

from __future__ import annotations

import frappe
from frappe.utils import cint, now_datetime

from ir.tests.test_helpers import IRSyntheticDataTestCase, get_reference_branch, get_reference_company

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
#
# Every one of Disciplinary Action's own Link-field targets (plus its Table
# children's own Link targets) is ignored here - this test builds its own
# minimal, synthetic fixtures via make_employee()/get_reference_*() instead
# of letting Frappe recursively auto-generate them, since that walk pulls in
# erpnext/hrms's own legacy test-bootstrap code (BootStrapTestData et al)
# which assumes a pristine site and collides with this site's real
# Company/Fiscal Year/Employee data.
EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = [
	"Employee",
	"Branch",
	"User",
	"Offence Outcome",
	"Company",
	"Disciplinary Offence",
]


def _reference_disciplinary_offence(exclude: str | None = None) -> str | None:
	"""An existing, real Disciplinary Offence - Disciplinary Offence has no
	fixture data of its own, so this looks up whatever real offence codes
	already exist on this site rather than creating a fake one."""
	filters = {}
	if exclude:
		filters["name"] = ["!=", exclude]
	return frappe.db.get_value("Disciplinary Offence", filters, "name", order_by="creation asc")


class IntegrationTestDisciplinaryAction(IRSyntheticDataTestCase):
	"""Functional tests for Disciplinary Action's Offences -> Charges sync
	(_sync_offence_codes_and_final_charges): exactly one Charges row is
	generated the first time each Offence row appears, and that Offence's
	`charge_created` marker then permanently protects it from ever being
	resynced again, no matter what happens to Charges or Offences afterwards.
	"""

	def _make_action(self, accused, complainant, code_item=None, **overrides):
		code_item = code_item or _reference_disciplinary_offence()
		if not code_item:
			self.skipTest("No Disciplinary Offence exists on this site.")

		values = {
			"doctype": "Disciplinary Action",
			"company": get_reference_company(),
			"accused": accused.name,
			"branch": get_reference_branch(),
			"complainant": complainant.name,
			"request_date": now_datetime(),
			"offences": [
				{
					"code_item": code_item,
					"offence_datetime": now_datetime(),
					"incident_details": "ZZTEST synthetic incident details.",
				}
			],
		}
		values.update(overrides)

		doc = frappe.get_doc(values)
		doc.insert(ignore_permissions=True)
		self.track("Disciplinary Action", doc.name)
		return doc

	def test_new_offence_creates_matching_charge_row(self):
		accused = self.make_employee()
		complainant = self.make_employee()
		code_item = _reference_disciplinary_offence()
		if not code_item:
			self.skipTest("No Disciplinary Offence exists on this site.")
		description = frappe.db.get_value("Disciplinary Offence", code_item, "offence_description") or ""

		doc = self._make_action(accused, complainant, code_item=code_item)

		self.assertEqual(len(doc.final_charges), 1)
		self.assertEqual(doc.final_charges[0].code_item, code_item)
		self.assertEqual(doc.final_charges[0].charge, description)
		self.assertEqual(cint(doc.offences[0].charge_created), 1)
		self.assertEqual(doc.offences[0].offence_code, code_item)

	def test_resave_does_not_duplicate_charge_for_already_synced_offence(self):
		accused = self.make_employee()
		complainant = self.make_employee()
		doc = self._make_action(accused, complainant)
		self.assertEqual(len(doc.final_charges), 1)

		doc.save(ignore_permissions=True)

		self.assertEqual(len(doc.final_charges), 1)

	def test_manually_removed_charge_is_not_recreated_on_resave(self):
		"""An IR practitioner is free to remove a Charges row the sync
		created (Charges is their own independent legal opinion, only
		seeded from Offences as a convenience) - once an Offence's
		charge_created marker is set, resaving must never regenerate it."""
		accused = self.make_employee()
		complainant = self.make_employee()
		doc = self._make_action(accused, complainant)
		self.assertEqual(len(doc.final_charges), 1)

		doc.final_charges = []
		doc.save(ignore_permissions=True)

		self.assertEqual(len(doc.final_charges), 0)

	def test_new_offence_added_later_creates_new_charge_without_touching_existing(self):
		accused = self.make_employee()
		complainant = self.make_employee()
		doc = self._make_action(accused, complainant)
		first_code_item = doc.offences[0].code_item
		first_charge_name = doc.final_charges[0].name

		second_code_item = _reference_disciplinary_offence(exclude=first_code_item)
		if not second_code_item:
			self.skipTest("Only one Disciplinary Offence exists on this site.")

		doc.append(
			"offences",
			{
				"code_item": second_code_item,
				"offence_datetime": now_datetime(),
				"incident_details": "ZZTEST second synthetic incident.",
			},
		)
		doc.save(ignore_permissions=True)

		self.assertEqual(len(doc.final_charges), 2)
		# The original Charges row is the very same child row - untouched,
		# not regenerated - and a new one was appended for the new Offence.
		self.assertEqual(doc.final_charges[0].name, first_charge_name)
		self.assertEqual(doc.final_charges[0].code_item, first_code_item)
		self.assertEqual(doc.final_charges[1].code_item, second_code_item)
		self.assertEqual(cint(doc.offences[1].charge_created), 1)
