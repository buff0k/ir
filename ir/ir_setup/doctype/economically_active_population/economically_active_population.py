# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class EconomicallyActivePopulation(Document):
    def before_submit(self):
        if not self.attach_signed:
            frappe.throw(_("Please attach a signed copy before submitting."))

def validate(self):
    total = (
        flt(self.african_male) + flt(self.african_female) +
        flt(self.coloured_male) + flt(self.coloured_female) +
        flt(self.indian_male) + flt(self.indian_female) +
        flt(self.white_male) + flt(self.white_female)
    )
    self.total = round(total, 2)
    
    if total > 100:
        frappe.throw(_("Total cannot exceed 100%"))