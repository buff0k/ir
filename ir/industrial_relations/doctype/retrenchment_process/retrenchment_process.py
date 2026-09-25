# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, cint, formatdate, getdate, nowdate

from ir.industrial_relations import utils

RETRENCHMENT_OFFENCE_OUTCOME = "RETR"

# LRA s189A(1)(a): applies only to employers with >50 employees, then a sliding
# scale of contemplated/combined dismissals. (cap, threshold) pairs, checked in
# order; anything above the last cap uses S189A_DEFAULT_THRESHOLD.
S189A_TIERS = [
	(200, 10),
	(300, 20),
	(400, 30),
	(500, 40),
]
S189A_DEFAULT_THRESHOLD = 50
S189A_MIN_EMPLOYER_SIZE = 50


class RetrenchmentProcess(Document):
	def autoname(self):
		if not self.process_title:
			frappe.throw(_("Process Title is required before naming the Retrenchment Process."))

		formatted_date = formatdate(nowdate(), "dd-MM-yyyy")
		base_name = f"{self.process_title} - {formatted_date}"
		self.name = _make_unique_process_name(base_name)

	def validate(self):
		self._validate_affected_employees()
		self._validate_employee_company_matches()
		self._validate_status_reason_required()
		self._validate_no_removal_of_protected_employees()

		headcounts = _process_headcounts(self)
		self.total_initially_affected = headcounts["total_initially_affected"]
		self.total_still_affected = headcounts["total_still_affected"]
		self.total_dismissed_12m = headcounts["total_dismissed_12m"]

		# Contemplated headcount for the 189A threshold test = everyone genuinely
		# still in play under THIS process - still pending plus already dismissed
		# through it - net of anyone Excluded/Transferred out (they're no longer
		# being contemplated for dismissal at all, so they shouldn't inflate the
		# threshold test either way).
		contemplated_count = headcounts["total_still_affected"] + headcounts["total_dismissed_12m"]
		guidance = get_189a_guidance(
			self.company,
			contemplated_count,
			self.proposed_implementation_date,
			exclude_process=self.name,
			manual_prior_dismissals=self.prior_operational_dismissals_12m if self.override_prior_dismissals_12m else None,
		)
		self.total_employees = guidance["total_employees"]
		if not self.override_prior_dismissals_12m:
			self.prior_operational_dismissals_12m = guidance["prior_dismissals"]
		self._warn_on_process_type_mismatch(guidance)

		from ir.industrial_relations.doctype.retrenchment_process.retrenchment_costing import (
			_apply_costing,
		)

		_apply_costing(self)

	def _validate_employee_company_matches(self):
		"""LRA s189/189A operates per employer (Company) - a single process can
		never legally span more than one Company, even though a Branch itself
		routinely has Employees from several Companies at once. Anyone from a
		different Company needs their own, separate Retrenchment Process."""
		employees = [row.employee for row in self.affected_employees if row.employee]
		if not self.company or not employees:
			return

		mismatched = frappe.get_all(
			"Employee",
			filters={"name": ["in", employees], "company": ["!=", self.company]},
			fields=["name", "employee_name", "company"],
		)
		if mismatched:
			details = ", ".join(f"{row.employee_name} ({row.name} - {row.company})" for row in mismatched)
			frappe.throw(
				_(
					"A Retrenchment Process covers exactly one Company. These Affected "
					"Employees belong to a different Company than {0}: {1}. Remove them and "
					"raise a separate Retrenchment Process for their own Company."
				).format(self.company, details)
			)

	def _validate_affected_employees(self):
		if not self.affected_employees:
			frappe.throw(_("Add at least one row to Affected Employees."))

		seen = set()
		for row in self.affected_employees:
			if row.employee:
				if row.employee in seen:
					frappe.throw(
						_("Employee {0} appears more than once in Affected Employees.").format(row.employee)
					)
				seen.add(row.employee)

	def _validate_status_reason_required(self):
		for row in self.affected_employees:
			if row.inclusion_status and row.inclusion_status != "Affected" and not row.status_reason:
				frappe.throw(
					_("Row {0} ({1}): a reason is required when marking an employee as {2}.").format(
						row.idx, row.employee or row.designation, row.inclusion_status
					)
				)

	def _validate_no_removal_of_protected_employees(self):
		"""An Affected Employee row that already has a served Section 189 Notice
		or a linked (non-cancelled) Dismissal Form can never simply disappear from
		this table - that would silently break the statutory audit trail (who was
		actually served, who was actually dismissed). The only way to take such an
		employee out of scope is to re-mark their existing row as Excluded or
		Transferred (with a reason) - never delete it."""
		before = self.get_doc_before_save()
		if not before:
			return

		previous_employees = {row.employee for row in (before.affected_employees or []) if row.employee}
		current_employees = {row.employee for row in (self.affected_employees or []) if row.employee}
		removed = previous_employees - current_employees
		if not removed:
			return

		protected = _protected_employees(self.name, list(removed))
		if protected:
			frappe.throw(
				_(
					"Cannot remove {0} from Affected Employees - they have already received a "
					"Section 189 Notice or have a linked Dismissal Form. Mark them as Excluded "
					"or Transferred instead, with a reason."
				).format(", ".join(sorted(protected)))
			)

	def _warn_on_process_type_mismatch(self, guidance):
		if guidance["threshold"] is None:
			return

		if guidance["meets_threshold"] and self.process_type == "Section 189":
			frappe.msgprint(
				_(
					"Based on current numbers, this process meets the Section 189A threshold. "
					"Consider changing Process Type to \"Section 189A\"."
				),
				indicator="orange",
				alert=True,
			)
		elif not guidance["meets_threshold"] and self.process_type == "Section 189A":
			frappe.msgprint(
				_("Based on current numbers, this process does not currently meet the Section 189A threshold."),
				indicator="blue",
				alert=True,
			)


def _make_unique_process_name(base_name):
	if not frappe.db.exists("Retrenchment Process", base_name):
		return base_name

	counter = 1
	while True:
		candidate = f"{base_name} - {counter}"
		if not frappe.db.exists("Retrenchment Process", candidate):
			return candidate
		counter += 1


def get_189a_threshold(total_employees):
	if total_employees <= S189A_MIN_EMPLOYER_SIZE:
		return None

	for cap, threshold in S189A_TIERS:
		if total_employees <= cap:
			return threshold

	return S189A_DEFAULT_THRESHOLD


def _count_prior_operational_dismissals(company, reference_date=None, exclude_process=None):
	"""Company-wide count for LRA s189(3)(j): employees dismissed for
	operational requirements in the preceding 12 months. `exclude_process`
	leaves out dismissals linked to that Retrenchment Process itself - its
	own dismissals are already disclosed separately (total_dismissed_12m /
	total_initially_affected), so including them here too would double-count
	the same people on the same Notice."""
	if not company:
		return 0

	reference_date = getdate(reference_date) if reference_date else getdate(nowdate())
	window_start = add_months(reference_date, -12)

	filters = {
		"company": company,
		"dismissal_type": RETRENCHMENT_OFFENCE_OUTCOME,
		"docstatus": 1,
		"outcome_date": ["between", [window_start, reference_date]],
	}
	if exclude_process:
		filters["linked_intervention"] = ["!=", exclude_process]

	return frappe.db.count("Dismissal Form", filters)


def _process_headcounts(process):
	"""Live, process-scoped headcounts (not company-wide) - the three counts
	the user asked for: how many were ever put forward on this process, how
	many are still pending a decision, and how many of this process's own
	employees have already been dismissed (within the trailing 12 months -
	in practice almost always "all of them", since a single process rarely
	runs longer than that)."""
	reference_date = getdate(nowdate())
	window_start = add_months(reference_date, -12)

	total_initially_affected = 0
	total_still_affected = 0
	total_dismissed_12m = 0

	for row in process.get("affected_employees") or []:
		if not row.employee:
			continue
		total_initially_affected += 1

		if row.outcome:
			outcome_date = getdate(row.outcome_date) if row.outcome_date else None
			if outcome_date and window_start <= outcome_date <= reference_date:
				total_dismissed_12m += 1
		elif _is_affected(row):
			total_still_affected += 1

	return {
		"total_initially_affected": total_initially_affected,
		"total_still_affected": total_still_affected,
		"total_dismissed_12m": total_dismissed_12m,
	}


@frappe.whitelist()
def get_189a_guidance(company, contemplated_count=0, reference_date=None, exclude_process=None, manual_prior_dismissals=None):
	contemplated_count = cint(contemplated_count)
	total_employees = (
		frappe.db.count("Employee", {"status": "Active", "company": company}) if company else 0
	)
	system_prior_dismissals = _count_prior_operational_dismissals(company, reference_date, exclude_process)
	using_override = manual_prior_dismissals not in (None, "")
	prior_dismissals = cint(manual_prior_dismissals) if using_override else system_prior_dismissals
	threshold = get_189a_threshold(total_employees) if company else None

	override_note = ""
	if using_override and prior_dismissals != system_prior_dismissals:
		override_note = _(
			" (manually overridden - the system count from submitted Dismissal Forms is {0})."
		).format(system_prior_dismissals)

	if not company:
		message = _("Select a Company to see Section 189A threshold guidance.")
		meets_threshold = False
	elif threshold is None:
		meets_threshold = False
		message = _("Section 189A does not apply: {0} employs {1} active employees (must exceed 50).").format(
			company, total_employees
		)
	else:
		combined = contemplated_count + prior_dismissals
		meets_threshold = contemplated_count >= threshold or combined >= threshold
		if meets_threshold:
			message = _(
				"This process meets the Section 189A threshold for {0} active employees "
				"(at least {1} affected employees triggers 189A). Contemplated: {2}. "
				"Dismissed for operational requirements in the preceding 12 months: {3}{4}"
			).format(total_employees, threshold, contemplated_count, prior_dismissals, override_note)
		else:
			message = _(
				"This process does not currently meet the Section 189A threshold for {0} "
				"active employees (at least {1} affected employees would trigger 189A). "
				"Contemplated: {2}. Dismissed for operational requirements in the preceding "
				"12 months: {3}{4}"
			).format(total_employees, threshold, contemplated_count, prior_dismissals, override_note)

	return {
		"total_employees": total_employees,
		"threshold": threshold,
		"prior_dismissals": prior_dismissals,
		"system_prior_dismissals": system_prior_dismissals,
		"contemplated_count": contemplated_count,
		"meets_threshold": meets_threshold,
		"message": message,
	}


@frappe.whitelist()
def fetch_default_letter_head(company):
	return utils.get_letter_head_string(company)


@frappe.whitelist()
def get_linked_docs_html(process_name):
	return utils.render_linked_docs_html(
		process_name,
		[
			(_("Section 189 Notices"), "Section 189 Notice", "linked_intervention"),
			(_("S189 Consultations"), "S189 Consultation", "linked_intervention"),
			(_("Dismissal Forms"), "Dismissal Form", "linked_intervention"),
		],
	)


def _is_affected(row):
	return not row.inclusion_status or row.inclusion_status == "Affected"


def _iter_named_affected_employees(process):
	"""Named rows still actually in scope for this process - excludes rows
	explicitly marked Excluded/Transferred. This is what drives contemplated
	headcount, Notice recipient population, and Consultation attendee
	population; it deliberately does NOT drive the status panel or the
	removal guard, both of which need to see every row regardless of status."""
	for row in process.get("affected_employees") or []:
		if row.employee and _is_affected(row):
			yield row


def _served_employees(process_name, employees):
	if not employees:
		return set()

	notice_names = frappe.get_all(
		"Section 189 Notice",
		filters={"linked_intervention": process_name, "docstatus": ["!=", 2]},
		pluck="name",
	)
	if not notice_names:
		return set()

	served = frappe.get_all(
		"Section 189 Notice Recipient",
		filters={
			"parent": ["in", notice_names],
			"parentfield": "recipients",
			"employee": ["in", employees],
		},
		fields=["employee", "date_served"],
	)
	return {row.employee for row in served if row.date_served}


def _dismissed_employees(process_name, employees):
	if not employees:
		return set()

	return set(
		frappe.get_all(
			"Dismissal Form",
			filters={
				"ir_intervention": "Retrenchment Process",
				"linked_intervention": process_name,
				"employee": ["in", employees],
				"docstatus": ["!=", 2],
			},
			pluck="employee",
		)
	)


def _protected_employees(process_name, employees):
	"""Employees among `employees` who already have a served Notice or a
	linked, non-cancelled Dismissal Form on `process_name` - i.e. whose row
	can never simply be deleted from Affected Employees."""
	return _served_employees(process_name, employees) | _dismissed_employees(process_name, employees)


@frappe.whitelist()
def get_outstanding_recipients(process_name):
	"""Currently-affected (not Excluded/Transferred) named employees on
	`process_name` with no served Section 189 Notice Recipient row on any
	(non-cancelled) Notice linked to this process."""
	process = frappe.get_doc("Retrenchment Process", process_name)
	named_employees = [row.employee for row in _iter_named_affected_employees(process)]
	if not named_employees:
		return []

	served_employees = _served_employees(process_name, named_employees)
	return [employee for employee in named_employees if employee not in served_employees]


@frappe.whitelist()
def get_affected_employee_status(process_name):
	"""Per-employee status for every NAMED row on `process_name`, regardless
	of inclusion_status - the "why doesn't each listed employee show its
	linked children" answer: computed live from Section 189 Notice
	Recipients and Dismissal Forms rather than cached, so it can never drift
	out of sync with what was actually issued/decided."""
	process = frappe.get_doc("Retrenchment Process", process_name)
	rows = [row for row in (process.affected_employees or []) if row.employee]
	employees = [row.employee for row in rows]

	served_employees = _served_employees(process_name, employees)
	notice_dates = {}
	if served_employees:
		notice_names = frappe.get_all(
			"Section 189 Notice",
			filters={"linked_intervention": process_name, "docstatus": ["!=", 2]},
			pluck="name",
		)
		notice_rows = frappe.get_all(
			"Section 189 Notice Recipient",
			filters={
				"parent": ["in", notice_names],
				"parentfield": "recipients",
				"employee": ["in", employees],
				"date_served": ["is", "set"],
			},
			fields=["employee", "date_served"],
			order_by="date_served desc",
		)
		for row in notice_rows:
			notice_dates.setdefault(row.employee, row.date_served)

	dismissal_forms = {}
	if employees:
		for row in frappe.get_all(
			"Dismissal Form",
			filters={
				"ir_intervention": "Retrenchment Process",
				"linked_intervention": process_name,
				"employee": ["in", employees],
			},
			fields=["name", "employee", "docstatus"],
		):
			dismissal_forms[row.employee] = {"name": row.name, "docstatus": row.docstatus}

	docstatus_label = {0: "Draft", 1: "Submitted", 2: "Cancelled"}
	results = []
	for row in rows:
		dismissal = dismissal_forms.get(row.employee)
		results.append(
			{
				"employee": row.employee,
				"employee_name": row.employee_name,
				"branch": row.branch,
				"designation": row.designation,
				"inclusion_status": row.inclusion_status or "Affected",
				"notice_served": row.employee in served_employees,
				"notice_date": str(notice_dates.get(row.employee)) if row.employee in notice_dates else None,
				"dismissal_form": dismissal["name"] if dismissal else None,
				"dismissal_status": docstatus_label.get(dismissal["docstatus"]) if dismissal else None,
				"termination_form": row.termination_form,
			}
		)

	return results


@frappe.whitelist()
def get_designation_breakdown(process_name):
	"""Per-Designation breakdown of Affected Employees - answers "how do we
	populate the affected designations" for the statutory (c) disclosure:
	initial (everyone ever named, any status), current (still pending, i.e.
	Affected and not yet dismissed), dismissed, and excluded/transferred,
	per Designation."""
	process = frappe.get_doc("Retrenchment Process", process_name)
	buckets = {}

	for row in process.affected_employees or []:
		if not row.employee or not row.designation:
			continue
		bucket = buckets.setdefault(
			row.designation, {"designation": row.designation, "initial": 0, "current": 0, "dismissed": 0, "excluded": 0}
		)
		bucket["initial"] += 1

		if row.outcome:
			bucket["dismissed"] += 1
		elif not _is_affected(row):
			bucket["excluded"] += 1
		else:
			bucket["current"] += 1

	return sorted(buckets.values(), key=lambda b: b["designation"])


@frappe.whitelist()
def get_union_membership_summary(process_name):
	"""Which Trade Union(s) the currently-affected named employees on this
	process belong to (via Employee.custom_trade_union), and that union's own
	registered officials - LRA s189 requires any Trade Union with members
	among the affected employees to be a recipient of the s189(3) notice in
	its own right, not just their individual members."""
	process = frappe.get_doc("Retrenchment Process", process_name)
	employees = [row.employee for row in _iter_named_affected_employees(process)]
	if not employees:
		return []

	membership = frappe.get_all(
		"Employee",
		filters={"name": ["in", employees], "custom_trade_union": ["is", "set"]},
		fields=["name as employee", "employee_name", "custom_trade_union as trade_union"],
	)
	if not membership:
		return []

	unions = sorted({row.trade_union for row in membership})
	officials_by_union = {}
	for union in unions:
		officials_by_union[union] = frappe.get_all(
			"Union Official",
			filters={"parent": union, "parenttype": "Trade Union", "parentfield": "of_list"},
			fields=["of_name", "of_pos", "of_mail"],
			order_by="idx asc",
		)

	buckets = {}
	for row in membership:
		bucket = buckets.setdefault(
			row.trade_union,
			{"trade_union": row.trade_union, "officials": officials_by_union.get(row.trade_union, []), "employees": []},
		)
		bucket["employees"].append({"employee": row.employee, "employee_name": row.employee_name})

	return sorted(buckets.values(), key=lambda b: b["trade_union"])


@frappe.whitelist()
def get_employees_for_branches(company, branches=None, designations=None):
	"""Active Employees at `company`, optionally narrowed to `branches`
	and/or `designations` (each a list, or JSON-encoded list) - the data
	behind "Add Employees from Branch(es) / Designation(s)" on the
	Retrenchment Process form. Both filters are optional so this also
	covers "every Designation across the whole Company" (no Branch picked)
	and "every employee at a Branch" (no Designation picked) - but at least
	one of the two is required, as a guard against a fat-finger click
	silently importing the entire Company."""
	branches = frappe.parse_json(branches) if isinstance(branches, str) else branches
	designations = frappe.parse_json(designations) if isinstance(designations, str) else designations

	if not company:
		frappe.throw(_("Select a Company on the Retrenchment Process first."))
	if not branches and not designations:
		frappe.throw(_("Select at least one Branch or Designation."))

	filters = {"status": "Active", "company": company}
	if branches:
		filters["branch"] = ["in", branches]
	if designations:
		filters["designation"] = ["in", designations]

	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=["name as employee", "employee_name", "branch", "designation"],
		order_by="branch asc, designation asc, employee_name asc",
	)
