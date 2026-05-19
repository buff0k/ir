# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from ir.industrial_relations.utils import autoname_by_linked_parent, clear_parent_outcome, set_parent_outcome, fetch_performance_data, fetch_company_letter_head as _fetch_company_letter_head, get_linked_outcome as _get_linked_outcome


class PerformanceImproved(Document):
    def autoname(self):
        autoname_by_linked_parent(self, "PIMP")

    def before_save(self):
        if not getattr(self, "__confirmed_save", False):
            clear_parent_outcome(self)

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        employee = frappe.get_doc("Employee", self.employee)
        employee.status = "Active"
        employee.relieving_date = ""
        employee.save(ignore_permissions=True)

    def on_submit(self):
        if not getattr(self, "__confirmed_submit", False):
            set_parent_outcome(
                self,
                self.performance_improved_type,
                self.outcome_date,
                self.improvement_summary or None,
                None,
            )


@frappe.whitelist()
def make_performance_improved(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.linked_poor_performance = source_name
    return get_mapped_doc("Poor Performance", source_name, {"Poor Performance": {"doctype": "Performance Improved", "field_map": {"name": "linked_poor_performance"}}}, target_doc, set_missing_values)


@frappe.whitelist()
def fetch_poor_performance_data(poor_performance):
    return fetch_performance_data(poor_performance)


@frappe.whitelist()
def fetch_company_letter_head(company):
    return _fetch_company_letter_head(company)


@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    return _get_linked_outcome(doc_name, doctype)
