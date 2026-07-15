# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
from datetime import datetime

import frappe
from frappe import _
from frappe.utils import getdate


SHIFT_DESIGN = "Shift Design"
TABLE_FIELDS = (
	"teams",
	"pattern",
	"calendar_rules",
	"date_overrides",
)


@frappe.whitelist()
def get_bootstrap():
	_check_permission("read")

	return {
		"designs": list_designs(),
		"companies": _names("Company", group_filter=True),
		"shift_types": _shift_type_options(),
		"can_create": frappe.has_permission(
			SHIFT_DESIGN,
			ptype="create",
		),
		"parent_fields": _fieldnames(SHIFT_DESIGN),
		"team_fields": _child_fieldnames(SHIFT_DESIGN, "teams"),
		"pattern_fields": _child_fieldnames(SHIFT_DESIGN, "pattern"),
		"calendar_rule_fields": _child_fieldnames(
			SHIFT_DESIGN,
			"calendar_rules",
		),
		"date_override_fields": _child_fieldnames(
			SHIFT_DESIGN,
			"date_overrides",
		),
	}


@frappe.whitelist()
def list_designs():
	_check_permission("read")
	meta = frappe.get_meta(SHIFT_DESIGN)

	candidate_fields = (
		"name",
		"design_name",
		"branch",
		"company",
		"status",
		"enabled",
		"effective_from",
		"effective_until",
		"number_of_teams",
		"cycle_length",
		"anchor_date",
		"pay_period_start_day",
		"pay_period_end_day",
		"modified",
	)

	fields = [
		fieldname
		for fieldname in candidate_fields
		if fieldname in {"name", "modified"}
		or meta.has_field(fieldname)
	]

	return frappe.get_all(
		SHIFT_DESIGN,
		fields=fields,
		order_by="modified desc",
		limit_page_length=500,
	)


@frappe.whitelist()
def get_design(name):
	if not name:
		frappe.throw(_("Shift Design is required."))

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("read")
	return _serialize(doc)


@frappe.whitelist()
def save_design(data):
	payload = _json_object(data)
	name = _clean(payload.get("name"))

	if name:
		doc = frappe.get_doc(SHIFT_DESIGN, name)
		doc.check_permission("write")
	else:
		if not frappe.has_permission(SHIFT_DESIGN, ptype="create"):
			frappe.throw(
				_("You do not have permission to create Shift Designs."),
				frappe.PermissionError,
			)
		doc = frappe.new_doc(SHIFT_DESIGN)

	meta = frappe.get_meta(SHIFT_DESIGN)

	for fieldname, value in payload.items():
		if fieldname in TABLE_FIELDS or fieldname == "name":
			continue
		if meta.has_field(fieldname):
			doc.set(fieldname, value)

	for table_fieldname in TABLE_FIELDS:
		table_field = meta.get_field(table_fieldname)
		if not table_field or not table_field.options:
			continue

		doc.set(table_fieldname, [])
		for row in payload.get(table_fieldname) or []:
			if not isinstance(row, dict):
				continue
			doc.append(
				table_fieldname,
				_clean_child_payload(row, table_field.options),
			)

	if doc.is_new():
		doc.insert()
	else:
		doc.save()

	return {
		"design": _serialize(doc),
		"designs": list_designs(),
	}


@frappe.whitelist()
def delete_design(name):
	if not name:
		frappe.throw(_("Shift Design is required."))

	doc = frappe.get_doc(SHIFT_DESIGN, name)
	doc.check_permission("delete")
	frappe.delete_doc(SHIFT_DESIGN, name)

	return {"designs": list_designs()}


@frappe.whitelist()
def import_organogram_teams(site_organogram):
	"""Import Branch and actual rotating team names only."""
	if not site_organogram:
		frappe.throw(_("Site Organogram is required."))

	if not frappe.db.exists("Site Organogram", site_organogram):
		frappe.throw(_("Site Organogram does not exist."))

	organogram = frappe.get_doc("Site Organogram", site_organogram)
	organogram.check_permission("read")

	team_names = _organogram_team_names(organogram)

	return {
		"site_organogram": organogram.name,
		"branch": organogram.branch,
		"number_of_teams": len(team_names),
		"teams": [
			{
				"team_key": f"TEAM::{frappe.generate_hash(length=10)}",
				"team_name": team_name,
				"display_order": index,
				"pattern_offset": 0,
				"enabled": 1,
			}
			for index, team_name in enumerate(team_names, start=1)
		],
	}


@frappe.whitelist()
def get_sa_public_holidays(start_date, end_date):
	if not start_date or not end_date:
		return []

	start = getdate(start_date)
	end = getdate(end_date)

	if end < start:
		frappe.throw(_("Simulation End cannot be before Simulation Start."))

	years = list(range(start.year, end.year + 1))

	try:
		from holidays import country_holidays

		za_holidays = country_holidays("ZA", years=years)
		return [
			{
				"date": str(getdate(holiday_date)),
				"description": holiday_name,
			}
			for holiday_date, holiday_name in za_holidays.items()
			if start <= getdate(holiday_date) <= end
		]
	except Exception as exc:
		frappe.log_error(
			title="Shift Designer public holiday generation failed",
			message=frappe.get_traceback(),
		)
		frappe.throw(
			_(
				"Unable to generate South African public holidays. "
				"Please confirm that the Python 'holidays' package is installed. "
				"Original error: {0}"
			).format(exc)
		)


def _organogram_team_names(organogram):
	valid_names = {
		"Shift A",
		"Shift B",
		"Shift C",
		"Shift D",
		"Shift E",
	}
	found = set()

	for row in organogram.shift_mappings or []:
		shift_name = _clean(row.shift)
		if shift_name in valid_names:
			found.add(shift_name)

	if found:
		return sorted(found, key=_shift_sort_key)

	configured_count = int(organogram.shifts or 0)
	if configured_count < 1:
		configured_count = 1

	return [
		f"Shift {_alpha_label(index)}"
		for index in range(configured_count)
	]


def _shift_sort_key(value):
	return _alpha_number(value.replace("Shift ", "", 1))


def _alpha_label(index):
	value = index + 1
	label = ""
	while value > 0:
		value -= 1
		label = chr(65 + value % 26) + label
		value //= 26
	return label


def _alpha_number(value):
	result = 0
	for character in str(value or "").upper():
		if "A" <= character <= "Z":
			result = result * 26 + ord(character) - 64
	return result


def _serialize(doc):
	meta = frappe.get_meta(SHIFT_DESIGN)
	data = {"name": doc.name}

	for field in meta.fields:
		if field.fieldtype in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}:
			continue

		if field.fieldtype == "Table":
			data[field.fieldname] = [
				_serialize_child(row)
				for row in doc.get(field.fieldname) or []
			]
		else:
			data[field.fieldname] = doc.get(field.fieldname)

	data["modified"] = doc.modified
	return data


def _serialize_child(row):
	meta = frappe.get_meta(row.doctype)
	return {
		field.fieldname: row.get(field.fieldname)
		for field in meta.fields
		if field.fieldtype not in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}
	}


def _clean_child_payload(row, child_doctype):
	valid_fields = set(_fieldnames(child_doctype))
	return {
		key: value
		for key, value in row.items()
		if key in valid_fields
	}


def _shift_type_options():
	if not frappe.db.exists("DocType", "Shift Type"):
		return []

	meta = frappe.get_meta("Shift Type")
	fields = ["name"]
	for fieldname in ("start_time", "end_time"):
		if meta.has_field(fieldname):
			fields.append(fieldname)

	rows = frappe.get_all(
		"Shift Type",
		filters=_active_filters(meta),
		fields=fields,
		order_by="name asc",
	)

	return [
		{
			"name": row.name,
			"start_time": str(row.get("start_time") or ""),
			"end_time": str(row.get("end_time") or ""),
			"hours": _duration_hours(
				row.get("start_time"),
				row.get("end_time"),
			),
		}
		for row in rows
	]


def _duration_hours(start, end):
	if start is None or end is None:
		return 0

	def seconds(value):
		if hasattr(value, "total_seconds"):
			return value.total_seconds()

		text = str(value).split(".")[0]
		for date_format in ("%H:%M:%S", "%H:%M"):
			try:
				parsed = datetime.strptime(text, date_format)
				return (
					parsed.hour * 3600
					+ parsed.minute * 60
					+ parsed.second
				)
			except ValueError:
				continue
		return 0

	start_seconds = seconds(start)
	end_seconds = seconds(end)
	if end_seconds <= start_seconds:
		end_seconds += 24 * 3600

	return round((end_seconds - start_seconds) / 3600, 4)


def _names(doctype, group_filter=False):
	if not frappe.db.exists("DocType", doctype):
		return []

	meta = frappe.get_meta(doctype)
	filters = {}

	if group_filter and meta.has_field("is_group"):
		filters["is_group"] = 0
	if meta.has_field("disabled"):
		filters["disabled"] = 0

	return frappe.get_all(
		doctype,
		filters=filters,
		pluck="name",
		order_by="name asc",
	)


def _active_filters(meta):
	if meta.has_field("disabled"):
		return {"disabled": 0}
	if meta.has_field("enabled"):
		return {"enabled": 1}
	return {}


def _fieldnames(doctype):
	return [
		field.fieldname
		for field in frappe.get_meta(doctype).fields
		if field.fieldtype not in {
			"Section Break",
			"Column Break",
			"Tab Break",
			"HTML",
			"Button",
		}
	]


def _child_fieldnames(parent_doctype, table_fieldname):
	parent_meta = frappe.get_meta(parent_doctype)
	table_field = parent_meta.get_field(table_fieldname)
	if not table_field or not table_field.options:
		return []
	return _fieldnames(table_field.options)


def _json_object(value):
	if isinstance(value, dict):
		return value

	try:
		parsed = json.loads(value or "{}")
	except (TypeError, ValueError):
		frappe.throw(_("Invalid Shift Design payload."))

	if not isinstance(parsed, dict):
		frappe.throw(_("Shift Design payload must be an object."))

	return parsed


def _check_permission(ptype):
	if not frappe.has_permission(SHIFT_DESIGN, ptype=ptype):
		frappe.throw(_("Not permitted."), frappe.PermissionError)


def _clean(value):
	return str(value or "").strip()
