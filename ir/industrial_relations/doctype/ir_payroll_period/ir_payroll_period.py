# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class IRPayrollPeriod(Document):
	def validate(self):
		self.validate_period_days()

	def validate_period_days(self):
		# Int fields' own min_value/max_value (set to 1/31 in the JSON) are
		# not enforced on the version-16 branch of frappe yet, so this is
		# the real check - same "between 1 and 31" day-of-month bounds
		# already enforced for Shift Design's pay_period_start_day/
		# pay_period_end_day.
		start_day = cint(self.period_start)
		end_day = cint(self.period_end)

		if start_day < 1 or start_day > 31:
			frappe.throw(_("First Day of Period must be between 1 and 31."))

		if end_day < 1 or end_day > 31:
			frappe.throw(_("Last Day of Period must be between 1 and 31."))
