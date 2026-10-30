# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TradeUnion(Document):
	pass

@frappe.whitelist()
def get_employee_details(ss_id):
    employee = frappe.get_doc("Employee", ss_id)
    return {
        'employee_name': employee.employee_name,
        'designation': employee.designation,
        'branch': employee.branch
    }