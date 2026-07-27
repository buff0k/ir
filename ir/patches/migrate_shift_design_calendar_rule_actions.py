# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

DOCTYPE = "Shift Design Calendar Rule"


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	if frappe.db.has_column(DOCTYPE, "rule_type"):
		frappe.db.sql(
			f"""
			UPDATE `tab{DOCTYPE}`
			SET `rule_type` = 'Weekday', `day_of_week` = 'Sunday'
			WHERE `rule_type` = 'Sunday'
			"""
		)

	if frappe.db.has_column(DOCTYPE, "action"):
		frappe.db.sql(
			f"""
			UPDATE `tab{DOCTYPE}`
			SET `action` = 'Day Shift Only'
			WHERE `action` = 'No Night Shift'
			"""
		)
