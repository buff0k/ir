# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""
CSV Data Import Utility

Provides generic functions for importing master data from CSV files
into Frappe DocTypes.

Ported from za_local.utils.csv_importer as part of absorbing za_local into
ir. import_all_master_data() was dropped - Business Trip Region/SETA/
Bargaining Council reference data are now ir's own fixtures instead; only
the generic import_csv_data() (still used by Bargaining Council's
"Import Common Councils" button) is needed here.
"""

import contextlib
from csv import DictReader
from io import StringIO

import frappe
from frappe.exceptions import DuplicateEntryError

from ir.utils.file_utils import read_app_text, resolve_app_path


def _logger():
	return frappe.logger("ir.csv_importer", allow_site=True)


def import_csv_data(doctype, csv_filename, update_existing=False):
	"""csv_filename is read from ir/data/. update_existing=False skips rows
	that already exist (matched by check_existing_record) instead of
	overwriting them."""
	stats = {
		"created": 0,
		"updated": 0,
		"skipped": 0,
		"errors": 0
	}

	if not frappe.db.exists("DocType", doctype):
		_logger().warning(f"DocType '{doctype}' does not exist. Skipping CSV import.")
		return stats

	csv_path = resolve_app_path("data", csv_filename)

	if not csv_path.exists():
		_logger().warning(f"CSV file '{csv_filename}' not found at {csv_path}")
		return stats

	_logger().info(f"Importing {doctype} from {csv_filename}...")

	reader = DictReader(StringIO(read_app_text(csv_path)))

	for row in reader:
		try:
			converted_row = convert_csv_types(row)
			existing = check_existing_record(doctype, converted_row)

			if existing:
				if update_existing:
					doc = frappe.get_doc(doctype, existing)
					doc.update(converted_row)
					doc.save(ignore_permissions=True)
					stats["updated"] += 1
				else:
					stats["skipped"] += 1
					continue
			else:
				doc = frappe.new_doc(doctype)
				doc.update(converted_row)

				with contextlib.suppress(DuplicateEntryError):
					doc.insert(ignore_permissions=True)
					stats["created"] += 1

		except Exception:
			_logger().error(f"Error importing {doctype} row {row}", exc_info=True)
			stats["errors"] += 1

	_logger().info(
		f"{doctype}: Created {stats['created']}, Updated {stats['updated']}, "
		f"Skipped {stats['skipped']}, Errors {stats['errors']}"
	)

	return stats


def convert_csv_types(row_data):
	"""CSV values are all strings; coerce the known currency/numeric fieldnames
	to float/int so they match their DocType field types."""
	converted = {}

	float_fields = [
		'daily_allowance_rate',
		'incidental_allowance_rate',
		'accommodation_limit',
		'mileage_rate',
		'rate',
		'amount',
		'cost'
	]

	int_fields = [
		'duration_hours',
		'days',
		'months',
		'years'
	]

	for key, value in row_data.items():
		if value == '' or value is None:
			converted[key] = None
			continue

		if key in float_fields:
			try:
				converted[key] = float(value)
			except (ValueError, TypeError):
				converted[key] = 0.0
		elif key in int_fields:
			try:
				converted[key] = int(value)
			except (ValueError, TypeError):
				converted[key] = 0
		else:
			converted[key] = value

	return converted


def check_existing_record(doctype, row_data):
	"""Returns the matching record's name, or None."""
	primary_keys = {
		"Business Trip Region": ["region_name"],
		"Bargaining Council": ["council_name"],
	}

	key_fields = primary_keys.get(doctype)

	if not key_fields:
		if row_data.get("name"):
			return row_data["name"] if frappe.db.exists(doctype, row_data["name"]) else None
		return None

	filters = {}
	for field in key_fields:
		if field in row_data:
			filters[field] = row_data[field]

	if not filters:
		return None

	existing = frappe.get_all(doctype, filters=filters, limit=1, pluck="name")
	return existing[0] if existing else None
