# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from ir.industrial_relations.utils import fetch_company_letter_head


def validate_signed_leave_form_attached(doc, method=None):
    if not doc.get("ir_attach_signed_leave_form"):
        frappe.throw(
            _("Please attach the signed leave form before submitting this Leave Application.")
        )


def set_letter_head_from_company(doc, method=None):
    """Leave Application already ships its own `letter_head` field (Frappe's
    print engine reads doc.get("letter_head") to pick which Letter Head to
    render - see get_letter_head() in frappe/www/printview.py - falling back
    to the System default one when it's blank), but nothing in core HRMS
    ever populates it correctly - confirmed some records already have the
    *System default* Letter Head stamped onto them at creation time (not
    blank - a real, wrong value, not just a missing one), so a
    "only fill it in if blank" guard would leave that wrong default in
    place forever. This always recomputes letter_head from the Employee's
    own Company instead, matching the same unconditional-sync pattern used
    for every other IR doctype's company/letter_head fields this session.
    `company` is already reliably kept in sync by HRMS's own fetch_from
    (employee.company), so this only needs to derive letter_head from that.

    A deliberate one-off override is still possible via the print dialog's
    own Letterhead picker, which always takes priority over this field
    regardless (see get_letter_head()'s own `letterhead or doc.get(...)`
    order) - see ir.patches.backfill_leave_application_letter_head for the
    retroactive fix on already-submitted records.
    """
    if not doc.get("company"):
        return

    letter_head = fetch_company_letter_head(doc.company).get("letter_head")
    if letter_head:
        doc.letter_head = letter_head