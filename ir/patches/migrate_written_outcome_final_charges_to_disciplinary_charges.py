# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe

SOURCE_DOCTYPE = "Charges"
TARGET_DOCTYPE = "Disciplinary Charges"


def execute():
	"""Written Outcome's final_charges field was switched from the generic
	"Charges" child doctype (indiv_charge only) to "Disciplinary Charges"
	(code_item + charge), to match the source Disciplinary Action's own
	Charges table exactly. Existing rows are stored per-child-doctype, so
	that schema change alone leaves every pre-existing final_charges row
	physically stranded in `tabCharges` - invisible to the ORM, which now
	looks in `tabDisciplinary Charges` instead. This patch moves them.
	"""
	if not frappe.db.exists("DocType", "Written Outcome"):
		return

	if not frappe.db.exists("DocType", TARGET_DOCTYPE):
		return

	if not frappe.db.has_column(SOURCE_DOCTYPE, "indiv_charge"):
		return

	orphaned = frappe.db.sql(
		f"""
		SELECT name, creation, modified, modified_by, owner, docstatus, idx,
			parent, parentfield, parenttype, indiv_charge
		FROM `tab{SOURCE_DOCTYPE}`
		WHERE parenttype = 'Written Outcome' AND parentfield = 'final_charges'
		""",
		as_dict=True,
	)

	if not orphaned:
		return

	moved = 0
	for row in orphaned:
		charge_text = (row.indiv_charge or "").strip()
		if not charge_text:
			continue

		frappe.db.sql(
			f"""
			INSERT INTO `tab{TARGET_DOCTYPE}`
				(name, creation, modified, modified_by, owner, docstatus, idx,
				 code_item, charge, parent, parentfield, parenttype)
			VALUES
				(%(name)s, %(creation)s, %(modified)s, %(modified_by)s, %(owner)s,
				 %(docstatus)s, %(idx)s, '', %(charge)s, %(parent)s, %(parentfield)s, %(parenttype)s)
			""",
			{
				"name": frappe.generate_hash(length=10),
				"creation": row.creation,
				"modified": row.modified,
				"modified_by": row.modified_by,
				"owner": row.owner,
				"docstatus": row.docstatus,
				"idx": row.idx,
				"charge": charge_text,
				"parent": row.parent,
				"parentfield": row.parentfield,
				"parenttype": row.parenttype,
			},
		)
		moved += 1

	frappe.db.sql(
		f"""
		DELETE FROM `tab{SOURCE_DOCTYPE}`
		WHERE parenttype = 'Written Outcome' AND parentfield = 'final_charges'
		"""
	)

	frappe.db.commit()
	frappe.logger().info(
		f"migrate_written_outcome_final_charges_to_disciplinary_charges: moved {moved} rows"
	)
