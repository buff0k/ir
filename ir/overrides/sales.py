# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""
Sales Document Deletion Protection

Implements SARS audit trail requirements by preventing deletion of
non-consecutive sales documents (Quotation, Sales Order, Sales Invoice).

Per SARS regulations, businesses must maintain consecutive numbering of
sales documents for tax audit purposes. This module only allows deletion
of the most recent document in a naming series to preserve the audit trail.

Ported from za_local.custom.sales as part of absorbing za_local into ir -
found disconnected from any doc_events hook (confirmed zero callers) and
reconnected here via ir/ir/hooks.py's doc_events.
"""

import frappe
from frappe import _


def on_trash(doc, method=None):
	if not is_latest_in_series(doc):
		frappe.throw(
			_(
				"For SARS audit trail compliance, only the most recent {0} can be deleted. "
				"<br><br>"
				"This document <b>{1}</b> is not the latest in its naming series. "
				"<br>"
				"Latest document: <b>{2}</b>"
				"<br><br>"
				"To maintain consecutive numbering required by SARS, please delete documents "
				"in reverse chronological order (newest first)."
			).format(
				doc.doctype,
				doc.name,
				get_latest_document_name(doc.doctype, doc.naming_series)
			),
			title=_("Cannot Delete Document - SARS Compliance"),
		)


def is_latest_in_series(doc):
	naming_series_field = get_naming_series_field(doc.doctype)
	if not naming_series_field:
		return True

	naming_series = doc.get(naming_series_field)
	if not naming_series:
		return True

	latest_name = get_latest_document_name(doc.doctype, naming_series)
	return doc.name == latest_name


def get_naming_series_field(doctype):
	naming_series_fields = {
		"Quotation": "naming_series",
		"Sales Order": "naming_series",
		"Sales Invoice": "naming_series",
	}
	return naming_series_fields.get(doctype)


def get_latest_document_name(doctype, naming_series):
	naming_series_field = get_naming_series_field(doctype)

	if not naming_series_field:
		return None

	latest = frappe.get_all(
		doctype,
		filters={naming_series_field: naming_series},
		fields=["name"],
		order_by="creation desc",
		limit=1
	)

	return latest[0].name if latest else None

