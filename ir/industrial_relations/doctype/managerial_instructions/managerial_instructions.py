# Copyright (c) 2024, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ManagerialInstructions(Document):
	pass

@frappe.whitelist()
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return {'letter_head': letter_head} if letter_head else {}

@frappe.whitelist()
def fetch_employee_name(employee):
    employee_doc = frappe.get_doc("Employee", employee)
    return {
        "employee_name": employee_doc.employee_name,
        "designation": employee_doc.designation
    }
