# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

DOCTYPE = "List of Offences"


def execute():
	"""The Offences->Charges sync on Disciplinary Action now tracks "have I
	already generated a Charges row for this Offence" per-row via the new
	`charge_created` marker, instead of comparing table lengths. Every
	pre-existing Offence row predates this field (defaults to unset), so
	without this patch the very next save of any existing Disciplinary
	Action would treat all of its Offences as brand new and duplicate
	Charges rows for work that was already done under the old logic. Mark
	every existing Offence row as already-synced so behaviour for existing
	records doesn't change - the new one-row-at-a-time logic only applies
	to Offences added from here on.
	"""
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	if not frappe.db.has_column(DOCTYPE, "charge_created"):
		return

	frappe.db.sql(
		f"""
		UPDATE `tab{DOCTYPE}`
		SET charge_created = 1
		WHERE parenttype = 'Disciplinary Action'
		"""
	)
	frappe.db.commit()
