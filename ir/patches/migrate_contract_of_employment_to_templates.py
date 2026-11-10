# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Contract of Employment moves from its legacy Contract Type/Contract
Section renderer to the Contract of Employment Template engine (see
contract_of_employment.py's generate_contract()/_build_render_context()).
This is the single, complete migration: a never-migrated Contract of
Employment is brought straight to its final correct shape in one pass -
pay_basis, working_hours_type and the Basic/Wages Earnings row are all
derived from the legacy data up front, not defaulted and corrected by a
later patch. (An earlier version of this migration was split across several
patches that each corrected something the previous one got wrong - e.g.
pay_basis defaulting to "Monthly" for everyone, then a second patch
reclassifying it from the real rate data and having to also fix the
Earnings row the first patch had already built against the wrong default.
Functionally that chain was still safe for a fresh site, since every patch
runs in one atomic `bench migrate`, but it only ever existed because this
site's own Contract Types/Salary Components were discovered and corrected
step by step during development. Now that contract_of_employment_template.py
(_legacy_contract_markdown(), import_legacy_contract_types()) and
contract_of_employment.py already produce the fully correct Template
wording/classification and CoE shape on their own, this migration can just
call them once and get the right answer immediately - so it's consolidated
back into this one patch.)

1. Ensures every submitted Contract Type has a submitted Contract of
   Employment Template, via import_legacy_contract_types() (idempotent -
   updates its own draft on a re-run), then submits each one normally.
   Matched to Contract of Employment via contract_name (a Template imported
   from a Contract Type is named after it) rather than a dedicated link
   field, which never had any purpose beyond this one-time import's own
   matching.
2. For every Contract of Employment still missing a contract_template:
   - pay_basis is classified from the legacy rate column: a clean bimodal
     split confirmed against this site's real data (2026-11-09) - under
     R1,000 is clearly an hourly rate (the overwhelming majority are under
     R100/hour), R5,000 or more is clearly a monthly salary, with zero
     records anywhere in between. No rate at all leaves it at the schema's
     own "Monthly" column default - there's no real signal to go on for
     those.
   - working_hours_type is classified from the legacy working_hours column:
     "Working Hours (Shift Roster)" -> "Shift Worker", everything else
     (Monday to Friday/Monday to Sunday/Church/blank) -> the "Fixed Hours"
     default already in place.
   - A Basic/Wages Earnings row is built from the legacy rate column,
     matched to the Salary Component for the now-known pay_basis (see
     BASIC_COMPONENT_BY_PAY_BASIS) - real money the contract pays, added
     for every docstatus. generate_contract()'s own rendering already
     excludes this row from the numbered allowance sub-clauses (the "Paid
     R {rate} ..." sentence already covers it), so adding it never changes
     what any contract - historic or new - actually renders.
   - For Draft records only, real Earnings rows are also built from the
     legacy allowance_1..5_desc/rate fields (via ALLOWANCE_LABEL_TO_COMPONENT,
     a match-list hand-confirmed against this site's real historic label
     text), provident_fund_contribution is defaulted from Contract Defaults
     (seed_contract_defaults_provident_fund_rate.py must run first - see
     patches.txt), and generated_contract is re-rendered through the new
     engine - Drafts aren't finalised yet, so this is safe, and since the
     Template and every field going into the render are already correct by
     the time this single save happens, one save is all it ever needs.
     A Draft with no real rate at all (so no Basic/Wages row can be built)
     is skipped with a logged warning rather than aborting the whole
     migration - ensure_required_fields() (contract_of_employment.py) would
     reject it, and that's a pre-existing data gap (no rate was ever
     captured for it), not something this patch can safely guess at.

Submitted/cancelled records never go through Document.save() at all -
generated_contract is what was actually signed and must never be rewritten
after the fact - only pay_basis/working_hours_type/contract_template
(direct frappe.db.set_value()) and the Basic/Wages Earnings row (a plain
bulk_insert) are added; provident_fund_contribution is deliberately left
alone for them too, since it only ever affects wording that's already
frozen. There is also no itemised-deduction data to backfill for them (or
for Drafts) - Contract of Employment never stored deductions at an itemised
amount level before this change.

Registered in patches.txt under [post_model_sync], so by the time this
runs, Contract of Employment's new fields (contract_template, pay_basis,
working_hours_type, earnings, deductions, provident_fund_contribution)
already exist and the superseded fields (rate, remuneration, working_hours,
allowance_1..5_desc/rate, has_hours, has_allowances, contract_clauses,
contract_type) are already gone from its DocType JSON - but, per Frappe's
schema sync (frappe/database/schema.py, DBTable.sync), never dropped as
actual DB columns, since sync only ever adds/alters columns, never drops one
for a field removed from the JSON. This patch therefore reads those legacy
columns via raw frappe.db.sql (bypassing the ORM/meta layer, which no
longer knows about them) - except on a genuinely fresh install that never
had this doctype's pre-Template schema at all, where those columns never
existed in the first place: checked via frappe.db.has_column() before
referencing any of them, so this patch degrades gracefully rather than
erroring on an unknown column.

Idempotent: a Contract of Employment that already has a contract_template
is skipped entirely on re-run - including every record on a site this
migration already ran on under its older, multi-patch form (contract_
template is already set for all of them, so there's nothing left for this
version to do).
"""

from __future__ import annotations

import frappe

from ir.industrial_relations.doctype.contract_of_employment.contract_of_employment import (
	BASIC_COMPONENT_BY_PAY_BASIS,
)
from ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template import (
	import_legacy_contract_types,
)

RATE_HOURLY_THRESHOLD = 1000
SHIFT_ROSTER_LEGACY_VALUE = "Working Hours (Shift Roster)"

# Historic allowance_N_desc text (everything before the first ":") -> the
# real Salary Component it means. Confirmed against every distinct label
# actually in use on this site (2026-11-09): exact-name matches
# (Housing/Shift/Safety Bonus/Opencast/Special Allowance) and two
# same-concept renames (Cellular Telephone -> Cellphone, Travel ->
# Transport) needed no new component; "Safety Allowance" (1 row) is folded
# into Safety Bonus; "Management Allowance" (1 row) and "Medical Allowance"
# (6 rows) had no existing equivalent, so _ensure_salary_components() below
# creates them.
ALLOWANCE_LABEL_TO_COMPONENT = {
	"Housing Allowance": "Housing Allowance",
	"Shift Allowance": "Shift Allowance",
	"Safety Bonus": "Safety Bonus",
	"Opencast Allowance": "Opencast Allowance",
	"Special Allowance": "Special Allowance",
	"Cellular Telephone Allowance": "Cellphone Allowance",
	"Travel Allowance": "Transport Allowance",
	"Safety Allowance": "Safety Bonus",
	"Management Allowance": "Management Allowance",
	"Medical Allowance": "Medical Allowance",
}
NEW_SALARY_COMPONENTS = ["Management Allowance", "Medical Allowance"]
ALLOWANCE_FIELDS = [(f"allowance_{n}_desc", f"allowance_{n}_rate") for n in range(1, 6)]

EARNING_COLUMNS = [
	"name",
	"parent",
	"parenttype",
	"parentfield",
	"idx",
	"docstatus",
	"owner",
	"modified_by",
	"creation",
	"modified",
	"salary_component",
	"amount",
]


def execute():
	if not frappe.db.table_exists("Contract of Employment"):
		return

	# contract_type (like rate/working_hours/the allowance fields below) is
	# also gone from the schema now - a fresh install never had it as a
	# column either, and it's this patch's only way to match a Contract of
	# Employment to its Template, so there's nothing left for it to do
	# without it (a fresh install has no pre-existing Contract of Employment
	# records needing this backfill anyway).
	if not frappe.db.has_column("Contract of Employment", "contract_type"):
		return

	_ensure_salary_components()
	templates_by_contract_type = _ensure_submitted_templates()

	# A fresh install (never had the pre-Template schema at all) never had
	# these legacy columns - nothing to read for either, on such a site.
	has_allowance_columns = frappe.db.has_column("Contract of Employment", "allowance_1_desc")
	has_rate_column = frappe.db.has_column("Contract of Employment", "rate")
	has_working_hours_column = frappe.db.has_column("Contract of Employment", "working_hours")

	default_pf_rate = frappe.get_cached_doc("Contract Defaults").provident_fund_contribution

	legacy_cols = ["`name`", "`docstatus`", "`contract_type`"]
	if has_rate_column:
		legacy_cols.append("`rate`")
	if has_working_hours_column:
		legacy_cols.append("`working_hours`")
	if has_allowance_columns:
		legacy_cols += [f"`{desc}`" for desc, _rate in ALLOWANCE_FIELDS]
		legacy_cols += [f"`{rate}`" for _desc, rate in ALLOWANCE_FIELDS]

	rows = frappe.db.sql(
		f"""
		SELECT {", ".join(legacy_cols)}
		FROM `tabContract of Employment`
		WHERE `contract_template` IS NULL OR `contract_template` = ''
		""",
		as_dict=True,
	)

	drafts_migrated = 0
	frozen_backfilled = 0
	skipped_no_template = []
	skipped_invalid_draft = []
	unmatched_labels = set()
	basic_earning_rows = []
	now = frappe.utils.now()

	for row in rows:
		template = templates_by_contract_type.get(row.contract_type)
		if not template:
			skipped_no_template.append(row.name)
			continue

		rate = row.get("rate") if has_rate_column else None
		pay_basis = "Hourly" if rate and 0 < rate < RATE_HOURLY_THRESHOLD else "Monthly"
		basic_component = BASIC_COMPONENT_BY_PAY_BASIS[pay_basis]
		is_shift_worker = has_working_hours_column and row.get("working_hours") == SHIFT_ROSTER_LEGACY_VALUE
		working_hours_type = "Shift Worker" if is_shift_worker else "Fixed Hours"

		if row.docstatus != 0:
			# Submitted/cancelled: traceability + real data attributes only -
			# never touch generated_contract, never go through Document.save().
			# The Basic/Wages row is queued for a plain bulk_insert below,
			# bypassing Document entirely, same as everything else here.
			if rate:
				basic_earning_rows.append(
					(
						frappe.generate_hash(length=10),
						row.name,
						"Contract of Employment",
						"earnings",
						1,
						0,
						"Administrator",
						"Administrator",
						now,
						now,
						basic_component,
						rate,
					)
				)
			frappe.db.set_value(
				"Contract of Employment",
				row.name,
				{
					"contract_template": template,
					"pay_basis": pay_basis,
					"working_hours_type": working_hours_type,
				},
				update_modified=False,
			)
			frozen_backfilled += 1
			continue

		doc = frappe.get_doc("Contract of Employment", row.name)
		doc.contract_template = template
		doc.pay_basis = pay_basis
		doc.working_hours_type = working_hours_type
		doc.provident_fund_contribution = default_pf_rate

		# A Draft goes through the normal Document.append()/save() path, not
		# the bulk_insert used for frozen records below - ensure_required_
		# fields() (contract_of_employment.py) requires this row to already
		# be present on self.earnings before save() will even succeed.
		if rate:
			doc.append("earnings", {"salary_component": basic_component, "amount": rate})

		if has_allowance_columns:
			for desc_field, rate_field in ALLOWANCE_FIELDS:
				desc = (row.get(desc_field) or "").strip()
				amount = row.get(rate_field)
				if not desc or not amount:
					continue
				label = desc.split(":", 1)[0].strip()
				component = ALLOWANCE_LABEL_TO_COMPONENT.get(label)
				if not component:
					unmatched_labels.add(label)
					continue
				doc.append("earnings", {"salary_component": component, "amount": amount})

		try:
			doc.save(ignore_permissions=True)
			drafts_migrated += 1
		except frappe.ValidationError as e:
			# No real rate was ever captured for this Draft (so no
			# Basic/Wages row could be built above) - a pre-existing data
			# gap, not something this patch can safely guess at. Log it and
			# move on rather than aborting the whole migration.
			skipped_invalid_draft.append((row.name, str(e)))

	if basic_earning_rows:
		frappe.db.bulk_insert("Contract of Employment Earning", fields=EARNING_COLUMNS, values=basic_earning_rows)

	frappe.db.commit()
	frappe.logger().info(
		"migrate_contract_of_employment_to_templates: "
		f"{drafts_migrated} draft(s) migrated and rendered, {frozen_backfilled} submitted/cancelled record(s) "
		f"backfilled, {len(skipped_no_template)} skipped for lack of a matching template "
		f"({skipped_no_template[:10]}), {len(skipped_invalid_draft)} draft(s) skipped as already invalid "
		f"before this patch ({skipped_invalid_draft}), unmatched allowance labels: {sorted(unmatched_labels)}"
	)


def _ensure_salary_components():
	for name in NEW_SALARY_COMPONENTS:
		if frappe.db.exists("Salary Component", name):
			continue
		frappe.get_doc({"doctype": "Salary Component", "salary_component": name, "type": "Earning"}).insert(
			ignore_permissions=True
		)


def _ensure_submitted_templates() -> dict[str, str]:
	"""contract_type name -> submitted Contract of Employment Template name,
	for every submitted Contract Type. Matched via contract_name (a Template
	imported from a Contract Type is named after it - see
	import_legacy_contract_types()) rather than a dedicated link field: that
	field never had any purpose beyond this one-time import's own matching,
	so it was removed. Only calls import_legacy_contract_types() for a
	Contract Type that doesn't already have a submitted Template - that
	function's own "re-running refreshes the existing draft" idempotency
	only covers a still-Draft Template; once one is submitted, it can no
	longer find/update it (only ever looks for docstatus=0), so re-running
	it unconditionally on an already-fully-migrated site would try to
	create a second, name-colliding Template."""
	contract_types = frappe.get_all("Contract Type", filters={"docstatus": 1}, pluck="name", order_by="name")
	if not contract_types:
		return {}

	mapping = {
		row.contract_name: row.name
		for row in frappe.get_all(
			"Contract of Employment Template",
			filters={"docstatus": 1, "contract_name": ["in", contract_types]},
			fields=["contract_name", "name"],
		)
	}

	needs_import = [ct for ct in contract_types if ct not in mapping]
	if needs_import:
		import_legacy_contract_types(needs_import)
		for contract_type in needs_import:
			draft = frappe.db.get_value(
				"Contract of Employment Template", {"contract_name": contract_type, "docstatus": 0}, "name"
			)
			doc = frappe.get_doc("Contract of Employment Template", draft)
			doc.submit()
			mapping[contract_type] = doc.name
	return mapping
