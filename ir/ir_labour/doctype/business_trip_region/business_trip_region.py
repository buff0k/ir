# Copyright (c) 2025, Cohenix and contributors
# For license information, please see license.txt

"""
Business Trip Region

Master data for business trip regions and their daily allowance rates.
Includes South African cities and international regions with SARS-compliant rates.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class BusinessTripRegion(Document):
	def validate(self):
		self.validate_rates()

	def validate_rates(self):
		if self.daily_allowance_rate and self.daily_allowance_rate < 0:
			frappe.throw(_("Daily Allowance Rate cannot be negative"))

		if self.incidental_allowance_rate and self.incidental_allowance_rate < 0:
			frappe.throw(_("Incidental Allowance Rate cannot be negative"))


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_active_regions(doctype, txt, searchfield, start, page_len, filters):
	frappe.has_permission("Business Trip Region", "read", throw=True)
	return frappe.db.sql(
		"""
		SELECT name, daily_allowance_rate, incidental_allowance_rate
		FROM `tabBusiness Trip Region`
		WHERE is_active = 1
		AND (name LIKE %(txt)s OR country LIKE %(txt)s)
		ORDER BY
			CASE
				WHEN country = 'South Africa' THEN 1
				ELSE 2
			END,
			name
		LIMIT %(start)s, %(page_len)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)
