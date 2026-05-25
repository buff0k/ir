# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def validate_signed_leave_form_attached(doc, method=None):
    if not doc.get("ir_attach_signed_leave_form"):
        frappe.throw(
            _("Please attach the signed leave form before submitting this Leave Application.")
        )