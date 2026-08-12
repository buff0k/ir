# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import json

import frappe
from frappe import _


SITE_PLAN = "Site Plan"
TABLE_FIELDS = (
	"groups",
	"slots",
	"reporting_lines",
)


@frappe.whitelist()
def get_bootstrap():
	_check_permission("read")

	return {
		"plans": list_plans(),
		"branches": _names("Branch"),
		"locations": _names("Location"),
		"shift_designs": _shift_design_options(),
		"designations": _names("Designation"),
		"asset_categories": _names("Asset Category"),
		"can_create": frappe.has_permission(SITE_PLAN, ptype="create"),
		"parent_fields": _fieldnames(SITE_PLAN),
		"group_fields": _child_fieldnames(SITE_PLAN, "groups"),
		"slot_fields": _child_fieldnames(SITE_PLAN, "slots"),
		"reporting_line_fields": _child_fieldnames(SITE_PLAN, "reporting_lines"),
	}


@frappe.whitelist()
def list_plans():
	_check_permission("read")
	meta = frappe.get_meta(SITE_PLAN)

	candidate_fields = (
		"name",
		"plan_name",
		"branch",
		"location",
		"status",
		"enabled",
		"effective_from",
		"effective_until",
		"modified",
	)

	fields = [
		fieldname
		for fieldname in candidate_fields
		if fieldname in {"name", "modified"} or meta.has_field(fieldname)
	]

	return frappe.get_all(
		SITE_PLAN,
		fields=fields,
		order_by="modified desc",
		limit_page_length=500,
	)


@frappe.whitelist()
def get_plan(name):
	if not name:
		frappe.throw(_("Site Plan is required."))

	doc = frappe.get_doc(SITE_PLAN, name)
	doc.check_permission("read")
	return _serialize(doc)


@frappe.whitelist()
def save_plan(data):
	payload = _json_object(data)
	name = _clean(payload.get("name"))

	if name:
		doc = frappe.get_doc(SITE_PLAN, name)
		doc.check_permission("write")
	else:
		if not frappe.has_permission(SITE_PLAN, ptype="create"):
			frappe.throw(
				_("You do not have permission to create Site Plans."),
				frappe.PermissionError,
			)
		doc = frappe.new_doc(SITE_PLAN)

	meta = frappe.get_meta(SITE_PLAN)

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
			doc.append(table_fieldname, _clean_child_payload(row, table_field.options))

	if doc.is_new():
		doc.insert()
	else:
		doc.save()

	return {
		"plan": _serialize(doc),
		"plans": list_plans(),
	}


@frappe.whitelist()
def delete_plan(name):
	if not name:
		frappe.throw(_("Site Plan is required."))

	doc = frappe.get_doc(SITE_PLAN, name)
	doc.check_permission("delete")
	frappe.delete_doc(SITE_PLAN, name)

	return {"plans": list_plans()}


def _serialize(doc):
	meta = frappe.get_meta(SITE_PLAN)
	data = {"name": doc.name}

	for field in meta.fields:
		if field.fieldtype in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}:
			continue

		if field.fieldtype == "Table":
			data[field.fieldname] = [_serialize_child(row) for row in doc.get(field.fieldname) or []]
		else:
			data[field.fieldname] = doc.get(field.fieldname)

	data["modified"] = doc.modified
	return data


def _serialize_child(row):
	meta = frappe.get_meta(row.doctype)
	return {
		field.fieldname: row.get(field.fieldname)
		for field in meta.fields
		if field.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}
	}


def _clean_child_payload(row, child_doctype):
	valid_fields = set(_fieldnames(child_doctype))
	return {key: value for key, value in row.items() if key in valid_fields}


def _shift_design_options():
	if not frappe.db.exists("DocType", "Shift Design"):
		return []

	return frappe.get_all(
		"Shift Design",
		filters={"enabled": 1},
		fields=["name", "number_of_teams"],
		order_by="name asc",
	)


def _names(doctype):
	if not frappe.db.exists("DocType", doctype):
		return []

	meta = frappe.get_meta(doctype)
	filters = {}
	if meta.has_field("disabled"):
		filters["disabled"] = 0

	return frappe.get_all(doctype, filters=filters, pluck="name", order_by="name asc")


def _fieldnames(doctype):
	return [
		field.fieldname
		for field in frappe.get_meta(doctype).fields
		if field.fieldtype not in {"Section Break", "Column Break", "Tab Break", "HTML", "Button"}
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
		frappe.throw(_("Invalid Site Plan payload."))

	if not isinstance(parsed, dict):
		frappe.throw(_("Site Plan payload must be an object."))

	return parsed


def _check_permission(ptype):
	if not frappe.has_permission(SITE_PLAN, ptype=ptype):
		frappe.throw(_("Not permitted."), frappe.PermissionError)


def _clean(value):
	return str(value or "").strip()
