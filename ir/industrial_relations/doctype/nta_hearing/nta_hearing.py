# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from ir.industrial_relations.utils import autoname_by_linked_parent, fetch_company_letter_head as _fetch_company_letter_head, fetch_employee_name, fetch_performance_data


class NTAHearing(Document):
    def autoname(self):
        autoname_by_linked_parent(self, "NTA")


@frappe.whitelist()
def make_nta_hearing(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.linked_disciplinary_action = source_name
    return get_mapped_doc("Disciplinary Action", source_name, {"Disciplinary Action": {"doctype": "NTA Hearing", "field_map": {"name": "linked_disciplinary_action"}}}, target_doc, set_missing_values)


@frappe.whitelist()
def make_nta_incap(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.linked_incapacity_proceeding = source_name
    return get_mapped_doc("Incapacity Proceedings", source_name, {"Incapacity Proceedings": {"doctype": "NTA Hearing", "field_map": {"name": "linked_incapacity_proceeding"}}}, target_doc, set_missing_values)


@frappe.whitelist()
def make_nta_poor_performance(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.linked_poor_performance = source_name
    return get_mapped_doc("Poor Performance", source_name, {"Poor Performance": {"doctype": "NTA Hearing", "field_map": {"name": "linked_poor_performance"}}}, target_doc, set_missing_values)


@frappe.whitelist()
def fetch_disciplinary_action_data(disciplinary_action):
    data = frappe.db.get_value('Disciplinary Action', disciplinary_action, ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company'], as_dict=True)
    if not data:
        return {}
    doc = frappe.get_doc('Disciplinary Action', disciplinary_action)
    data.update({
        'previous_disciplinary_outcomes': [{'disc_action': r.disc_action, 'date': r.date, 'sanction': r.sanction, 'charges': r.charges} for r in (doc.previous_disciplinary_outcomes or [])],
        'final_charges': [{'indiv_charge': f"({r.code_item}) {r.charge}"} for r in (doc.final_charges or [])],
    })
    return data


@frappe.whitelist()
def fetch_incpacity_proceeding_data(incapacity_proceeding):
    if not frappe.db.exists('Incapacity Proceedings', incapacity_proceeding):
        frappe.throw(_("Incapacity Proceedings {0} not found").format(incapacity_proceeding))
    data = frappe.db.get_value('Incapacity Proceedings', incapacity_proceeding, ['accused', 'accused_name', 'accused_coy', 'accused_pos', 'company', 'type_of_incapacity', 'details_of_incapacity'], as_dict=True)
    if not data:
        return {}
    doc = frappe.get_doc('Incapacity Proceedings', incapacity_proceeding)
    data.update({'previous_incapacity_outcomes': [{'incap_proc': r.incap_proc, 'date': r.date, 'sanction': r.sanction, 'incap_details': r.incap_details} for r in (doc.previous_incapacity_outcomes or [])]})
    return data


@frappe.whitelist()
def fetch_poor_performance_data(poor_performance):
    return fetch_performance_data(poor_performance)


@frappe.whitelist()
def fetch_company_letter_head(company):
    return _fetch_company_letter_head(company)


@frappe.whitelist()
def fetch_chairperson_name(employee):
    return fetch_employee_name(employee)
