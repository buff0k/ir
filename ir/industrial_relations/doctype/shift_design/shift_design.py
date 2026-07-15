# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate


class ShiftDesign(Document):
	def before_validate(self):
		self.remove_blank_child_rows()
		self.set_defaults()
		self.ensure_team_keys()
		self.populate_display_values()

	def validate(self):
		self.validate_effective_dates()
		self.validate_pay_period()
		self.validate_cycle_configuration()
		self.validate_shift_types()
		self.validate_teams()
		self.validate_pattern()
		self.validate_calendar_rules()
		self.validate_date_overrides()

	def remove_blank_child_rows(self):
		self.teams = [
			row
			for row in self.teams or []
			if _clean(row.team_key) or _clean(row.team_name)
		]

		self.pattern = [
			row
			for row in self.pattern or []
			if any(
				[
					_clean(row.team_key),
					cint(row.pattern_day),
					_clean(row.assignment),
					_clean(row.shift_type),
				]
			)
		]

		self.calendar_rules = [
			row
			for row in self.calendar_rules or []
			if any(
				[
					_clean(row.rule_type),
					_clean(row.day_of_week),
					_clean(row.action),
					flt(getattr(row, "day_shift_hours", 0)),
					flt(getattr(row, "night_shift_hours", 0)),
				]
			)
		]

		self.date_overrides = [
			row
			for row in self.date_overrides or []
			if any(
				[
					row.date,
					_clean(row.team_key),
					_clean(row.assignment),
					_clean(row.shift_type),
					_clean(row.reason),
				]
			)
		]

	def set_defaults(self):
		if not self.status:
			self.status = "Draft"

		if self.enabled is None:
			self.enabled = 1

		if not cint(self.number_of_teams):
			self.number_of_teams = 1

		if not cint(self.cycle_length):
			self.cycle_length = 1

		if not self.anchor_date and self.effective_from:
			self.anchor_date = self.effective_from

		if not cint(self.pay_period_start_day):
			self.pay_period_start_day = 1

		if not cint(self.pay_period_end_day):
			self.pay_period_end_day = 31

		if not flt(self.ordinary_hours_limit):
			self.ordinary_hours_limit = 195

		if not self.sunday_rule:
			self.sunday_rule = "Follow Pattern"

	def ensure_team_keys(self):
		for row in self.teams or []:
			if not _clean(row.team_key):
				row.team_key = _new_team_key()

	def populate_display_values(self):
		team_names = {
			_clean(row.team_key): _clean(row.team_name)
			for row in self.teams or []
			if _clean(row.team_key)
		}

		for row in self.pattern or []:
			row.team_name = team_names.get(_clean(row.team_key), "")

		for row in self.date_overrides or []:
			row.team_name = team_names.get(_clean(row.team_key), "")

	def validate_effective_dates(self):
		if (
			self.effective_from
			and self.effective_until
			and getdate(self.effective_until) < getdate(self.effective_from)
		):
			frappe.throw(_("Effective Until cannot be before Effective From."))

		if (
			self.anchor_date
			and self.effective_until
			and getdate(self.anchor_date) > getdate(self.effective_until)
		):
			frappe.throw(_("Cycle Anchor Date cannot be after Effective Until."))

	def validate_pay_period(self):
		start_day = cint(self.pay_period_start_day)
		end_day = cint(self.pay_period_end_day)

		if start_day < 1 or start_day > 31:
			frappe.throw(_("Pay Period Start Day must be between 1 and 31."))

		if end_day < 1 or end_day > 31:
			frappe.throw(_("Pay Period End Day must be between 1 and 31."))

		if flt(self.ordinary_hours_limit) <= 0:
			frappe.throw(_("Ordinary Hours Limit must be greater than zero."))

	def validate_cycle_configuration(self):
		if cint(self.number_of_teams) < 1:
			frappe.throw(_("Number of Shift Teams must be at least 1."))

		if cint(self.number_of_teams) > 20:
			frappe.throw(_("Number of Shift Teams cannot exceed 20."))

		if cint(self.cycle_length) < 1:
			frappe.throw(_("Cycle Length must be at least 1 day."))

		if cint(self.cycle_length) > 366:
			frappe.throw(_("Cycle Length cannot exceed 366 days."))

	def validate_shift_types(self):
		if self.status != "Active":
			return

		if not self.day_shift_type:
			frappe.throw(_("Active Shift Designs require a Day Shift Type."))

		if not self.night_shift_type:
			frappe.throw(_("Active Shift Designs require a Night Shift Type."))

	def validate_teams(self):
		seen_keys = set()
		seen_names = set()
		enabled_teams = 0

		for row in self.teams or []:
			team_key = _clean(row.team_key)
			team_name = _clean(row.team_name)

			if not team_name:
				frappe.throw(_("Team Name is required in row {0}.").format(row.idx))

			if not team_key:
				frappe.throw(_("Team Key is missing in row {0}.").format(row.idx))

			normalized_name = team_name.casefold()

			if team_key in seen_keys:
				frappe.throw(_("Duplicate Team Key in row {0}.").format(row.idx))

			if normalized_name in seen_names:
				frappe.throw(_("Duplicate Team Name '{0}'.").format(team_name))

			pattern_offset = cint(row.pattern_offset)
			if pattern_offset < 0 or pattern_offset >= cint(self.cycle_length):
				frappe.throw(
					_(
						"Pattern Offset for '{0}' must be between 0 and {1}."
					).format(team_name, cint(self.cycle_length) - 1)
				)

			seen_keys.add(team_key)
			seen_names.add(normalized_name)

			if cint(row.enabled):
				enabled_teams += 1

		if enabled_teams != cint(self.number_of_teams):
			frappe.throw(
				_(
					"Enabled Shift Team rows ({0}) must match Number of Shift Teams ({1})."
				).format(enabled_teams, cint(self.number_of_teams))
			)

	def validate_pattern(self):
		team_keys = {
			_clean(row.team_key)
			for row in self.teams or []
			if _clean(row.team_key)
		}
		seen_cells = set()

		for row in self.pattern or []:
			team_key = _clean(row.team_key)
			pattern_day = cint(row.pattern_day)

			if team_key not in team_keys:
				frappe.throw(
					_("Pattern row {0} refers to an unknown Team Key.").format(row.idx)
				)

			if pattern_day < 1 or pattern_day > cint(self.cycle_length):
				frappe.throw(
					_(
						"Pattern Day in row {0} must be between 1 and {1}."
					).format(row.idx, cint(self.cycle_length))
				)

			if _clean(row.assignment) not in {"Day", "Night", "Off"}:
				frappe.throw(_("Pattern row {0} has an invalid Assignment.").format(row.idx))

			cell_key = (team_key, pattern_day)
			if cell_key in seen_cells:
				frappe.throw(
					_(
						"Duplicate Pattern cell for Team '{0}', Day {1}."
					).format(row.team_name or team_key, pattern_day)
				)

			seen_cells.add(cell_key)

	def validate_calendar_rules(self):
		for row in self.calendar_rules or []:
			if _clean(row.rule_type) == "Weekday" and not _clean(row.day_of_week):
				frappe.throw(
					_("Calendar Rule row {0} requires a Day of Week.").format(row.idx)
				)

			if flt(getattr(row, "day_shift_hours", 0)) < 0:
				frappe.throw(_("Day Shift Hours cannot be negative."))

			if flt(getattr(row, "night_shift_hours", 0)) < 0:
				frappe.throw(_("Night Shift Hours cannot be negative."))

	def validate_date_overrides(self):
		team_keys = {
			_clean(row.team_key)
			for row in self.teams or []
			if _clean(row.team_key)
		}
		seen = set()

		for row in self.date_overrides or []:
			team_key = _clean(row.team_key)

			if team_key and team_key not in team_keys:
				frappe.throw(
					_("Date Override row {0} refers to an unknown Team Key.").format(row.idx)
				)

			key = (getdate(row.date), team_key)
			if key in seen:
				frappe.throw(
					_("Duplicate Date Override for {0}, Team '{1}'.").format(
						row.date,
						row.team_name or team_key or "All",
					)
				)
			seen.add(key)


@frappe.whitelist()
def get_site_organogram_import_data(site_organogram):
	"""Compatibility endpoint for the standard form: Branch and teams only."""
	from ir.industrial_relations.page.ir_shift_design.ir_shift_design import (
		import_organogram_teams,
	)

	return import_organogram_teams(site_organogram)


def _clean(value):
	return str(value or "").strip()


def _new_team_key():
	return f"TEAM::{frappe.generate_hash(length=10)}"
