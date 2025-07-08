# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class OccupationalLevel(Document):
	pass

@frappe.whitelist()
def get_designations_for_occupational_level(occupational_level):
    return [
        {"designation": d.name}
        for d in frappe.get_all("Designation", filters={"custom_occupational_level": occupational_level})
    ]
