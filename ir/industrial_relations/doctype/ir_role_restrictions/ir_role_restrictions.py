# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Every "IR User Restriction Table" field on this singleton (recipient lists) and
# both "IR Role Restrictions User Branch" fields (branch-scoped recipient lists)
# carry the same user/email_address pair.
RECIPIENT_TABLE_FIELDS = (
    "report_recipients",
    "disciplinary_recipients",
    "incapacity_recipients",
    "performance_recipients",
    "external_dispute_recipients",
    "global_trainer",
    "hr_per_branch",
    "trainer_per_branch",
)

class IRRoleRestrictions(Document):
    def validate(self):
        self._sync_recipient_emails()

    def _sync_recipient_emails(self):
        """Keep every row's email_address in sync with its linked User's current
        email, on every save - not just filled in once while blank.

        email_address used to only be populated the first time a row was saved
        (and only on report_recipients), which meant it silently froze at
        whatever the User's email was at that moment. If that User was later
        renamed (e.g. a company domain migration), every table's stored
        email_address kept pointing at the old address forever - notification
        code that trusted it would mail an address nobody reads anymore, while
        the user's new address never received anything. Re-deriving it from the
        User on every save keeps it visibly correct in the UI; the notification
        code itself also independently prefers the live User email over this
        stored value, so delivery isn't dependent on this running.
        """
        for fieldname in RECIPIENT_TABLE_FIELDS:
            for row in self.get(fieldname) or []:
                user = getattr(row, "user", None)
                if not user:
                    continue
                email = frappe.db.get_value("User", user, "email")
                if email and row.email_address != email:
                    row.email_address = email
