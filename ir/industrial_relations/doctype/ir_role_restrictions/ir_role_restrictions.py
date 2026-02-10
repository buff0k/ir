# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class IRRoleRestrictions(Document):
    def validate(self):
        self._populate_report_recipient_emails()

    def _populate_report_recipient_emails(self):
        for row in self.get("report_recipients") or []:
            if getattr(row, "user", None) and not getattr(row, "email_address", None):
                email = frappe.db.get_value("User", row.user, "email")
                if email:
                    row.email_address = email
