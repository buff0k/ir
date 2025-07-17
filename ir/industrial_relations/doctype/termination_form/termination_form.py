# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe import _, get_doc
from frappe.utils import getdate

class TerminationForm(Document):
    def before_submit(self):
        if not self.requested_for:
            frappe.throw(_("Please link an Employee before submitting."))

        if not self.termination_date:
            frappe.throw(_("Termination Date is required before submitting."))

        # Pick the correct relieving date: notice_ends (if present and later), else termination_date
        relieving_date = getdate(self.termination_date)
        if self.notice_ends:
            notice_ends_date = getdate(self.notice_ends)
            if notice_ends_date > relieving_date:
                relieving_date = notice_ends_date

        # Update employee record
        employee = frappe.get_doc("Employee", self.requested_for)
        employee.status = "Left"
        employee.relieving_date = relieving_date
        employee.save(ignore_permissions=True)

        frappe.msgprint(
            _("Employee {0}'s status has been updated to 'Left' and relieving date set to {1}.").format(
                self.requested_for, relieving_date.strftime('%Y-%m-%d')
            ),
            alert=True
        )