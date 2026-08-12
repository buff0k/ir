# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class SitePlan(Document):
	def before_validate(self):
		self.remove_blank_child_rows()
		self.set_defaults()
		self.ensure_group_keys()
		self.ensure_slot_keys()
		self.populate_display_values()

	def validate(self):
		self.validate_effective_dates()
		self.validate_group_keys_unique()
		self.validate_slots_reference_groups()
		self.validate_reporting_lines_reference_groups()

	def remove_blank_child_rows(self):
		self.groups = [row for row in self.groups or [] if _clean(row.group)]

		self.slots = [
			row
			for row in self.slots or []
			if _clean(row.group_key) and (_clean(row.designation) or _clean(row.asset_category) or _clean(row.row_label))
		]

		self.reporting_lines = [
			row
			for row in self.reporting_lines or []
			if _clean(row.source_group_key) and _clean(row.target_group_key)
		]

	def set_defaults(self):
		if not self.status:
			self.status = "Draft"

		if self.enabled is None:
			self.enabled = 1

	def ensure_group_keys(self):
		for row in self.groups or []:
			if not _clean(row.group_key):
				row.group_key = _new_group_key()

	def ensure_slot_keys(self):
		for row in self.slots or []:
			if not _clean(row.row_key):
				row.row_key = _new_slot_key()

	def populate_display_values(self):
		group_names = {
			_clean(row.group_key): _clean(row.group)
			for row in self.groups or []
			if _clean(row.group_key)
		}

		for row in self.slots or []:
			row.group = group_names.get(_clean(row.group_key), row.group)

		for row in self.reporting_lines or []:
			row.source_group = group_names.get(_clean(row.source_group_key), row.source_group)
			row.target_group = group_names.get(_clean(row.target_group_key), row.target_group)

	def validate_effective_dates(self):
		if (
			self.effective_from
			and self.effective_until
			and getdate(self.effective_until) < getdate(self.effective_from)
		):
			frappe.throw(_("Effective Until cannot be before Effective From."))

	def validate_group_keys_unique(self):
		seen = set()
		for row in self.groups or []:
			key = _clean(row.group_key)
			if key in seen:
				frappe.throw(_("Duplicate group key for heading {0}.").format(row.group))
			seen.add(key)

	def validate_slots_reference_groups(self):
		valid_keys = {_clean(row.group_key) for row in self.groups or []}
		for row in self.slots or []:
			if _clean(row.group_key) not in valid_keys:
				frappe.throw(_("Slot {0} refers to a group heading that no longer exists.").format(row.row_label or row.idx))

	def validate_reporting_lines_reference_groups(self):
		valid_keys = {_clean(row.group_key) for row in self.groups or []}
		for row in self.reporting_lines or []:
			if _clean(row.source_group_key) not in valid_keys or _clean(row.target_group_key) not in valid_keys:
				frappe.throw(_("Reporting line {0} refers to a group heading that no longer exists.").format(row.idx))


def _clean(value):
	return str(value or "").strip()


def _new_group_key():
	return f"GRP::{frappe.generate_hash(length=10)}"


def _new_slot_key():
	return f"SLOT::{frappe.generate_hash(length=10)}"
