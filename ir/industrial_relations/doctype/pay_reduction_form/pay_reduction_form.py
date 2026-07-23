# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from ir.industrial_relations.utils import clear_parent_outcome, fetch_performance_data


SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


class PayReductionForm(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        prefix = f"PRED-{self.linked_intervention}"
        existing = frappe.get_all(
            self.doctype,
            filters={
                "ir_intervention": self.ir_intervention,
                "linked_intervention": self.linked_intervention,
            },
            pluck="name",
        )

        if prefix not in existing:
            self.name = prefix
            return

        latest_revision = 0
        for name in existing:
            if not name.startswith(f"{prefix}-"):
                continue
            try:
                latest_revision = max(latest_revision, int(name.rsplit("-", 1)[1]))
            except (TypeError, ValueError):
                continue

        self.name = f"{prefix}-{latest_revision + 1}"

    def validate(self):
        self._validate_intervention()
        self._validate_dates()

        if self.reduction_amount is None:
            frappe.throw(_("Monetary Value of Reduction is required."))

        if self.reduction_amount < 0:
            frappe.throw(_("Monetary Value of Reduction cannot be negative."))

    def before_save(self):
        self._clear_linked_outcome()

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        if not self.signed_pay_reduction:
            frappe.throw(_("You must attach the signed pay reduction before submitting."))

        employee = frappe.get_doc("Employee", self.employee)
        employee.status = "Active"
        employee.relieving_date = None
        employee.save(ignore_permissions=True)

    def on_submit(self):
        self._set_linked_outcome()

    def on_cancel(self):
        clear_parent_outcome(self)

    def _validate_intervention(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Select a supported IR Intervention."))

        if not self.linked_intervention:
            frappe.throw(_("Select the linked intervention."))

        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention,
                    self.linked_intervention,
                )
            )

    def _validate_dates(self):
        if not self.from_date or not self.to_date:
            return

        if getdate(self.to_date) < getdate(self.from_date):
            frappe.throw(_("To Date cannot be before From Date."))

    def _get_linked_document(self):
        if not self.ir_intervention or not self.linked_intervention:
            return None
        return frappe.get_doc(self.ir_intervention, self.linked_intervention)

    def _clear_linked_outcome(self):
        linked_doc = self._get_linked_document()
        if not linked_doc:
            return

        values = {
            fieldname: None
            for fieldname in (
                "outcome",
                "outcome_date",
                "outcome_start",
                "outcome_end",
            )
            if linked_doc.meta.has_field(fieldname)
        }
        if values:
            linked_doc.db_set(values, update_modified=False)

    def _set_linked_outcome(self):
        linked_doc = self._get_linked_document()
        if not linked_doc:
            return

        values = {}
        if linked_doc.meta.has_field("outcome"):
            values["outcome"] = self.pay_reduction_type
        if linked_doc.meta.has_field("outcome_date"):
            values["outcome_date"] = self.outcome_date
        if linked_doc.meta.has_field("outcome_start"):
            values["outcome_start"] = _build_outcome_start(self)
        if linked_doc.meta.has_field("outcome_end"):
            values["outcome_end"] = _build_outcome_end(self)

        if values:
            linked_doc.db_set(values, update_modified=False)


@frappe.whitelist()
def create_pay_reduction_form(source_name, source_doctype):
    _validate_source(source_name, source_doctype)

    target = frappe.new_doc("Pay Reduction Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name
    target.applied_rights = "Pay Reduction"

    data = get_intervention_data(source_doctype, source_name)
    _apply_intervention_data(target, data)
    _apply_employee_rights(target, target.applied_rights)
    target.linked_intervention_processed = 1
    return target


@frappe.whitelist()
def fetch_intervention_data(ir_intervention, linked_intervention):
    return get_intervention_data(ir_intervention, linked_intervention)


def get_intervention_data(ir_intervention, linked_intervention):
    _validate_source(linked_intervention, ir_intervention)

    if ir_intervention == "Disciplinary Action":
        return _get_disciplinary_action_data(linked_intervention)
    if ir_intervention == "Incapacity Proceedings":
        return _get_incapacity_data(linked_intervention)
    if ir_intervention == "Poor Performance":
        return _get_poor_performance_data(linked_intervention)

    return {}


def _validate_source(source_name, source_doctype):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported intervention type: {0}").format(source_doctype))

    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("{0} {1} does not exist.").format(source_doctype, source_name))


def _get_disciplinary_action_data(name):
    source = frappe.get_doc("Disciplinary Action", name)
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "position": source.accused_pos,
        "company": source.company,
        "nta_charges": [
            {"indiv_charge": f"({row.code_item}) {row.charge}"}
            for row in (source.final_charges or [])
        ],
        "disciplinary_history": [
            {
                "disc_action": row.disc_action,
                "date": row.date,
                "sanction": row.sanction,
                "charges": row.charges,
            }
            for row in (source.previous_disciplinary_outcomes or [])
        ],
    }


def _get_incapacity_data(name):
    source = frappe.get_doc("Incapacity Proceedings", name)
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "position": source.accused_pos,
        "company": source.company,
        "type_of_incapacity": source.get("type_of_incapacity"),
        "details_of_incapacity": source.get("details_of_incapacity"),
        "previous_incapacity_outcomes": [
            {
                "incap_proc": row.incap_proc,
                "date": row.date,
                "sanction": row.sanction,
                "incap_details": row.incap_details,
            }
            for row in (source.get("previous_incapacity_outcomes") or [])
        ],
    }


def _get_poor_performance_data(name):
    source_data = fetch_performance_data(name) or {}
    return {
        "employee": source_data.get("employee"),
        "names": source_data.get("employee_name"),
        "position": source_data.get("employee_designation"),
        "company": source_data.get("company"),
        "performance_details": source_data.get("details_of_poor_performance"),
        "previous_performance_outcomes": source_data.get("previous_performance_outcomes") or [],
    }


def _apply_intervention_data(target, data):
    for fieldname in (
        "employee",
        "names",
        "position",
        "company",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ):
        if target.meta.has_field(fieldname):
            target.set(fieldname, data.get(fieldname))

    for fieldname in (
        "nta_charges",
        "disciplinary_history",
        "previous_incapacity_outcomes",
        "previous_performance_outcomes",
    ):
        if not target.meta.has_field(fieldname):
            continue
        target.set(fieldname, [])
        for row in data.get(fieldname) or []:
            target.append(fieldname, row)


def _apply_employee_rights(target, employee_rights_name):
    target.set("employee_rights", [])

    if not employee_rights_name:
        return

    if not frappe.db.exists("Employee Rights", employee_rights_name):
        frappe.throw(
            _("Employee Rights record {0} does not exist.").format(
                employee_rights_name
            )
        )

    rights_doc = frappe.get_doc("Employee Rights", employee_rights_name)
    for row in rights_doc.get("applicable_rights") or []:
        target.append(
            "employee_rights",
            {"individual_right": row.individual_right},
        )


def _build_outcome_start(doc):
    text = _("The employee's pay is reduced from {0}").format(
        frappe.format_value(doc.from_date, {"fieldtype": "Date"})
    )
    if doc.reduction_amount is not None:
        text += _(" by {0}").format(
            frappe.format_value(doc.reduction_amount, {"fieldtype": "Currency"})
        )
    if doc.details_responsibilities:
        text += _(". Changed responsibilities: {0}").format(
            doc.details_responsibilities
        )
    return f"{text}."


def _build_outcome_end(doc):
    if not doc.to_date:
        return None
    return _("The employee's pay reduction applies until {0}.").format(
        frappe.format_value(doc.to_date, {"fieldtype": "Date"})
    )


@frappe.whitelist()
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value("Company", company, "default_letter_head")
    return {"letter_head": letter_head} if letter_head else {}


@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    if doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported intervention type."))
    if not frappe.db.exists(doctype, doc_name):
        return {}

    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        "outcome": linked_doc.get("outcome"),
        "outcome_date": linked_doc.get("outcome_date"),
        "outcome_start": linked_doc.get("outcome_start"),
        "outcome_end": linked_doc.get("outcome_end"),
    }
