# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import html

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_years, format_time, get_time, getdate, now_datetime

from ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template import (
	ContractContext,
	VARIABLES_BY_KEY,
	format_value,
	parse_wording,
	render_contract,
)
from ir.ir_setup.doctype.ir_payroll_cost_settings.ir_payroll_cost_settings import get_basic_wage_components

# (fieldname prefix unused, day label, start field, end field) - Contract of
# Employment's own fixed Monday-Sunday Time fields, fed into the template
# engine's working_days repeat. No rotating-shift support here; every
# contract is shift:fixed (see _build_render_context).
WORKING_DAYS = (
	("Monday", "mon_start", "mon_end"),
	("Tuesday", "tue_start", "tue_end"),
	("Wednesday", "wed_start", "wed_end"),
	("Thursday", "thu_start", "thu_end"),
	("Friday", "fri_start", "fri_end"),
	("Saturday", "sat_start", "sat_end"),
	("Sunday", "sun_start", "sun_end"),
)

# pay_basis -> the real Salary Component that represents Basic/Wages for it
# (both already curated as "Basic/Wages" in IR Payroll Cost Settings).
BASIC_COMPONENT_BY_PAY_BASIS = {"Hourly": "Hourly Earnings", "Monthly": "Basic Salary"}


class ContractofEmployment(Document):
	def autoname(self):
		# Was "format:{contract_type} - {employee_name} - {employee} -
		# {DD}-{MM}-{YYYY}" - contract_type is gone (Contract Type is fully
		# deprecated; contract_template is the only source of wording/
		# classification now), so contract_template takes its place in the
		# name. {DD}/{MM}/{YYYY} resolve to today's date (not self.creation),
		# and a blank field contributes nothing (not the literal text
		# "None") - both exactly as Frappe's own format: autoname did
		# (frappe.model.naming._format_autoname -> parse_naming_series).
		today = now_datetime().strftime("%d-%m-%Y")
		self.name = (
			f"{self.contract_template or ''} - {self.employee_name or ''} - {self.employee or ''} - {today}"
		)

	def validate(self):
		# Backfill from the Employee/Contract Type before ensure_required_fields()
		# checks them - used for Data Import Function too.
		if not self.employee_name:
			self.employee_name = frappe.db.get_value('Employee', self.employee, 'employee_name')
		if not self.company:
			self.company = frappe.db.get_value('Employee', self.employee, 'company')
		if not self.designation:
			self.designation = frappe.db.get_value('Employee', self.employee, 'designation')
		if not self.current_address:
			self.current_address = frappe.db.get_value('Employee', self.employee, 'current_address')
		if not self.date_of_birth:
			self.date_of_birth = frappe.db.get_value('Employee', self.employee, 'date_of_birth')
		if not self.date_of_joining:
			self.date_of_joining = frappe.db.get_value('Employee', self.employee, 'date_of_joining')
		if not self.custom_id_number:
			self.custom_id_number = frappe.db.get_value('Employee', self.employee, 'za_id_number')
		if not self.branch:
			self.branch = frappe.db.get_value('Employee', self.employee, 'branch')

		# Period/Project/Retirement classification comes from the Template,
		# not the deprecated Contract Type - see contract_template: in
		# contract_of_employment.js, which does the same client-side for an
		# interactive save. Only ever synced while still a Draft (same
		# freeze-on-submit rule as generate_contract()/the Earnings table) -
		# these 4 fields aren't allow_on_submit, so re-deriving them
		# unconditionally would make an unrelated resave of an old submitted
		# contract fail outright the day anyone edits that Template's own
		# classification.
		if self.docstatus == 0 and self.contract_template:
			classification = frappe.db.get_value(
				"Contract of Employment Template",
				self.contract_template,
				["has_expiry", "has_project", "has_retirement", "retirement_age"],
				as_dict=True,
			)
			self.has_expiry = classification.has_expiry
			self.has_project = classification.has_project
			self.has_retirement = classification.has_retirement
			self.retirement_age = classification.retirement_age

		self.ensure_required_fields()

		if self.is_new():
			self._prefill_contract_defaults()

		# Only ever re-render while still a Draft: a submitted or cancelled
		# contract's generated_contract is what was actually signed, and must
		# never be silently rewritten by an incidental resave.
		if self.docstatus == 0:
			self.generate_contract()

	def _prefill_contract_defaults(self):
		"""New contracts start with the site's standard Deductions and
		Provident Fund rate (both from Contract Defaults), so HR doesn't
		have to fill either in by hand every time - only ever runs once, on
		insert, and only for whichever of the two wasn't already supplied
		(e.g. via Data Import). The rate becomes this contract's own value
		from here on - a later change to Contract Defaults never silently
		alters an already-created contract, submitted or not."""
		defaults = frappe.get_cached_doc("Contract Defaults")
		if not self.deductions:
			for row in defaults.default_deductions:
				self.append("deductions", {"salary_component": row.salary_component})
		if not self.provident_fund_contribution:
			self.provident_fund_contribution = defaults.provident_fund_contribution

	def _is_real_working_day(self, start_field, end_field) -> bool:
		"""A Monday-Sunday Time pair counts as an actual working day only if
		start and end are both set and genuinely different - not just "both
		truthy". A field just set this same request (e.g. from the client,
		mid-insert) is still the raw value passed in (a non-empty string
		like "00:00:00", which Python considers truthy), while the exact
		same value read back after a DB round-trip comes back as a
		datetime.timedelta(0) (which Python considers falsy) - so a plain
		`start and end` truthiness check only caught an explicitly-"closed"
		day (both fields left/set to the Saturday/Sunday default of 00:00)
		on a reload-then-save, never on a fresh insert from the real UI,
		where every such day was wrongly treated as a real 00:00-to-00:00
		shift and printed in the wording. frappe.utils.get_time() parses
		either representation into a plain datetime.time, so comparing
		those is representation-independent."""
		start_raw, end_raw = self.get(start_field), self.get(end_field)
		if not start_raw or not end_raw:
			return False
		return get_time(start_raw) != get_time(end_raw)

	def _basic_earning_row(self):
		"""The one Earnings row for Basic/Wages matching pay_basis - the rate
		of pay itself. There's no separate rate field any more: HR enters it
		directly as an Earnings row (linked to Basic Salary/Hourly Earnings,
		same as any allowance), via the same Earnings table/editor."""
		target = BASIC_COMPONENT_BY_PAY_BASIS.get(self.pay_basis)
		return next((row for row in self.earnings if row.salary_component == target and row.amount), None)

	def ensure_required_fields(self):
		""" Ensure that all fields marked as required have valid values. """
		required_fields = {
			'employee_name': 'Employee Name',
			'company': 'Company',
			'designation': 'Designation',
			'current_address': 'Current Address',
			'date_of_birth': 'Date of Birth',
			'date_of_joining': 'Date of Joining',
			'custom_id_number': 'RSA ID / Passport No.',
			'branch': 'Site',
		}

		missing_fields = [label for field, label in required_fields.items() if not getattr(self, field)]

		if missing_fields:
			frappe.throw(_("The following fields are required and missing: {0}").format(", ".join(missing_fields)))

		if not self._basic_earning_row():
			target = BASIC_COMPONENT_BY_PAY_BASIS.get(self.pay_basis, "Basic Salary")
			frappe.throw(_("Add a {0} row to the Earnings table with the rate of pay.").format(target))

		# mandatory_depends_on (contract_of_employment.json) only ever
		# drives the client-side red asterisk - Frappe's own server-side
		# mandatory check (Document._get_missing_mandatory_fields()) only
		# ever looks at plain reqd=1, never mandatory_depends_on, so this
		# has to be enforced here explicitly.
		if self.working_hours_type == "Weekly Hours of Work" and not self.weekly_hours_of_work:
			frappe.throw(_("Weekly Hours of Work is required when Working Hours Type is Weekly Hours of Work."))

	def generate_contract(self):
		"""Render this contract's wording through the Contract of Employment
		Template engine (see contract_of_employment_template.py)."""
		if not self.contract_template:
			return

		wording = frappe.db.get_value("Contract of Employment Template", self.contract_template, "contract_wording")
		self.generated_contract = render_contract(parse_wording(wording), self._build_render_context())

	def _compute_retirement_date(self):
		if self.has_retirement and self.retirement_age and self.date_of_birth:
			return add_days(add_years(getdate(self.date_of_birth), int(self.retirement_age)), -1)
		return None

	def _build_render_context(self) -> ContractContext:
		context = ContractContext()
		basic_row = self._basic_earning_row()

		raw_values = {
			"employee_name": self.employee_name,
			"employee_number": self.employee,
			"id_number": self.custom_id_number,
			"current_address": self.current_address,
			"designation": self.designation,
			"branch": self.branch,
			"company": self.company,
			"date_of_joining": self.date_of_joining,
			# contract_type (the field) is gone - the wording engine's own
			# "contract_type" variable key stays (real Templates already
			# have {{contract_type}} baked into their stored wording), just
			# fed from the Template's own name now instead.
			"contract_type": frappe.db.get_value(
				"Contract of Employment Template", self.contract_template, "contract_name"
			)
			if self.contract_template
			else None,
			"start_date": self.start_date,
			"end_date": self.end_date,
			"project": self.project,
			"retirement_age": self.retirement_age,
			"retirement_date": self._compute_retirement_date(),
			"restraint_period": self.restraint_period,
			"restraint_territory": self.restraint_territory,
			"rate": basic_row.amount if basic_row else None,
			"provident_fund_rate": self.provident_fund_contribution,
			"weekly_hours": self.weekly_hours_of_work,
		}
		for key, raw in raw_values.items():
			context.values[key] = format_value(VARIABLES_BY_KEY[key], raw)

		# The Basic/Wages row is real data (entered directly as an Earnings
		# row, same as any allowance) but never shown as an allowance - the
		# "Paid R {rate} ..." sentence above already covers it on the
		# printed contract. Each remaining row becomes its own numbered
		# sub-clause via the earnings repeat.
		basic_components = get_basic_wage_components()
		extra_earnings = [row for row in self.earnings if row.salary_component not in basic_components]
		context.rows["earnings"] = [
			{
				"earning_label": format_value(VARIABLES_BY_KEY["earning_label"], row.salary_component),
				"earning_amount": format_value(VARIABLES_BY_KEY["earning_amount"], row.amount),
			}
			for row in extra_earnings
		]
		context.rows["deductions"] = [
			{"deduction_label": self._deduction_label(row.salary_component)} for row in self.deductions
		]

		# Fixed Hours is the only one of the three with a real weekly
		# schedule (the Monday-Sunday Time fields) - Shift Worker's hours
		# come from a roster, and Weekly Hours of Work has no fixed
		# days/times at all (just a target hours-per-week count), so both
		# render with an empty working_days repeat, same as each other.
		is_fixed_hours = self.working_hours_type == "Fixed Hours"
		context.rows["working_days"] = (
			[
				{
					"day_name": day_label,
					# format_time first - a Time field's raw value isn't
					# guaranteed to already be a clean "HH:MM" string.
					"day_start": format_value(
						VARIABLES_BY_KEY["day_start"], format_time(self.get(start_field), "HH:mm")
					),
					"day_end": format_value(VARIABLES_BY_KEY["day_end"], format_time(self.get(end_field), "HH:mm")),
				}
				for day_label, start_field, end_field in WORKING_DAYS
				if self._is_real_working_day(start_field, end_field)
			]
			if is_fixed_hours
			else []
		)
		context.rows["shifts"] = []

		if is_fixed_hours:
			shift_condition = "shift:fixed"
		elif self.working_hours_type == "Weekly Hours of Work":
			shift_condition = "shift:weekly"
		else:
			shift_condition = "shift:rotating"

		conditions = context.conditions
		conditions.add(shift_condition)
		conditions.add("pay:hourly" if self.pay_basis == "Hourly" else "pay:monthly")
		conditions.add("allowances:any" if extra_earnings else "allowances:none")
		conditions.add("deductions:any" if self.deductions else "deductions:none")
		conditions.add("retirement:yes" if self.has_retirement else "retirement:no")
		conditions.update(f"earning:{row.salary_component}" for row in self.earnings)
		conditions.update(f"deduction:{row.salary_component}" for row in self.deductions)

		return context

	@staticmethod
	def _deduction_label(salary_component) -> str:
		"""One Deduction row's rendered value: its name and live Salary
		Component description, no amount - becomes its own numbered
		sub-paragraph via the deductions repeat (contract_of_employment_
		template.py), same as earning_label does for Allowances."""
		description = frappe.db.get_value("Salary Component", salary_component, "description")
		detail = f"<br><small>{html.escape(description)}</small>" if description else ""
		return f"<b>{html.escape(salary_component)}</b>{detail}"

	def before_submit(self):
		if not self.signed_contract:
			frappe.throw(_("You cannot submit the document without attaching the signed contract."))

		if not self.employee:
			frappe.throw(_("Please link an Employee before submitting."))

		employee = frappe.get_doc("Employee", self.employee)

		if self.has_expiry and self.end_date:
			employee.employment_type = "Contract"
			employee.contract_end_date = self.end_date

		retirement_date = self._compute_retirement_date()
		if retirement_date:
			employee.date_of_retirement = retirement_date

		# Save the Employee document to trigger Track Changes
		employee.save(ignore_permissions=True)


@frappe.whitelist()
def get_pending_status_change(employee):
	"""The employee's most relevant Draft Status Change Form that carries a
	Designation or Branch change (latest effective_date, ties broken by
	creation), if any - used by the client employee: handler to warn when a
	new Contract is being drafted while a Branch/Designation change for this
	employee is still pending submission.

	new_designation/new_branch no longer exist as Status Change Form's own
	fields - Status Change Detail is the only input now, so both are read
	from whichever Designation/Branch row that form carries (a Status
	Change Form with neither - e.g. an allowance-only change - isn't
	relevant here and is skipped)."""
	if not employee:
		return None

	rows = frappe.db.sql(
		"""
		SELECT scf.name, scf.effective_date, scd.change_type, scd.new_value
		FROM `tabStatus Change Form` scf
		INNER JOIN `tabStatus Change Detail` scd ON scd.parent = scf.name
		WHERE scf.employee = %s
			AND scf.docstatus = 0
			AND scd.change_type IN ('Designation', 'Branch')
		ORDER BY scf.effective_date DESC, scf.creation DESC
		""",
		(employee,),
		as_dict=True,
	)
	if not rows:
		return None

	top_name = rows[0].name
	top_rows = [r for r in rows if r.name == top_name]

	return frappe._dict({
		"name": top_name,
		"effective_date": top_rows[0].effective_date,
		"new_designation": next((r.new_value for r in top_rows if r.change_type == "Designation"), None),
		"new_branch": next((r.new_value for r in top_rows if r.change_type == "Branch"), None),
	})
