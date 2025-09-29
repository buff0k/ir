# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ExternalDisputeResolution(Document):
    def before_submit(self):
        if not self.outcome:
            frappe.throw("You cannot submit this record without selecting an Outcome.")