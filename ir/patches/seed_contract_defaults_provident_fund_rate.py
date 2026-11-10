# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Seeds Contract Defaults.provident_fund_contribution with 5.00% - the rate
every historic contract hardcoded before it became a real, editable field
(see provident_fund_rate in contract_of_employment_template.py). Only sets
it if still blank, so it never overwrites a value someone has already
configured.
"""

import frappe


def execute():
	if not frappe.db.table_exists("Contract Defaults"):
		return

	if frappe.db.get_single_value("Contract Defaults", "provident_fund_contribution"):
		return

	frappe.db.set_single_value("Contract Defaults", "provident_fund_contribution", 5.00)
	frappe.db.commit()
