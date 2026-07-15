# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from ir.industrial_relations.utils import fetch_performance_data

SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


class DismissalForm(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        prefix = f"DISM-{self.linked_intervention}"
        existing = frappe.get_all(
            self.doctype,
            filters={
                "ir_intervention": self.ir_intervention,
                "linked_intervention": self.linked_intervention,
            },
            pluck="name",
        )

        if not existing:
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
        self._validate_required_values()

    def before_save(self):
        if not getattr(self, "__confirmed_save", False):
            self.clear_source_outcome()

    def before_submit(self):
        self._validate_submission()
        self._update_employee_as_left()

    def on_submit(self):
        if not getattr(self, "__confirmed_submit", False):
            self.set_source_outcome()

    def _validate_intervention(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Select a supported IR Intervention."))

        if not self.linked_intervention:
            frappe.throw(_("Linked IR Intervention is required."))

        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention,
                    self.linked_intervention,
                )
            )

    def _validate_required_values(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee."))
        if not self.dismissal_type:
            frappe.throw(_("Dismissal Type is required."))
        if not self.outcome_date:
            frappe.throw(_("Date of Dismissal is required."))

    def _validate_submission(self):
        self._validate_required_values()
        if not self.signed_dismissal:
            frappe.throw(_("Attach the signed dismissal before submitting."))

    def _get_source_document(self):
        self._validate_intervention()
        return frappe.get_doc(self.ir_intervention, self.linked_intervention)

    def clear_source_outcome(self):
        source = self._get_source_document()
        previous = _get_outcome_values(source)

        if not any(previous.values()):
            return

        updates = {
            "outcome": None,
            "outcome_date": None,
            "outcome_start": None,
            "outcome_end": None,
        }
        _apply_source_updates(source, updates, previous)

        frappe.msgprint(
            _("Outcome information for {0} ({1}) has been cleared.").format(
                source.name,
                source.doctype,
            ),
            alert=True,
        )

    def set_source_outcome(self):
        source = self._get_source_document()
        previous = _get_outcome_values(source)
        updates = {
            "outcome": self.dismissal_type,
            "outcome_date": self.outcome_date,
            "outcome_start": None,
            "outcome_end": None,
        }
        _apply_source_updates(source, updates, previous)

        frappe.msgprint(
            _("Outcome for {0} ({1}) has been updated to {2} dated {3}.").format(
                source.name,
                source.doctype,
                self.dismissal_type,
                self.outcome_date,
            ),
            alert=True,
        )

    def _update_employee_as_left(self):
        employee = frappe.get_doc("Employee", self.employee)
        employee.status = "Left"
        employee.relieving_date = self.outcome_date
        employee.save(ignore_permissions=True)

        frappe.msgprint(
            _("Employee {0} has been marked Left with relieving date {1}.").format(
                self.employee,
                self.outcome_date,
            ),
            alert=True,
        )


def _get_outcome_values(doc):
    return {
        "outcome": doc.get("outcome"),
        "outcome_date": doc.get("outcome_date"),
        "outcome_start": doc.get("outcome_start"),
        "outcome_end": doc.get("outcome_end"),
    }


def _apply_source_updates(source, updates, previous):
    source.flags.ignore_version = True

    if source.docstatus == 0:
        for fieldname, value in updates.items():
            source.set(fieldname, value)
        source.save(ignore_permissions=True)
        return

    for fieldname, value in updates.items():
        old_value = previous.get(fieldname)
        if old_value == value:
            continue
        source.db_set(fieldname, value, update_modified=False)
        _create_manual_version(source, fieldname, old_value, value)


def _create_manual_version(doc, fieldname, old_value, new_value):
    frappe.get_doc(
        {
            "doctype": "Version",
            "ref_doctype": doc.doctype,
            "docname": doc.name,
            "data": frappe.as_json(
                {"changed": [[fieldname, old_value, new_value]]}
            ),
        }
    ).insert(ignore_permissions=True)


@frappe.whitelist()
def create_dismissal_form(source_name, source_doctype):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported source DocType: {0}").format(source_doctype))

    source = frappe.get_doc(source_doctype, source_name)
    target = frappe.new_doc("Dismissal Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source.name
    target.linked_intervention_processed = 0
    return target


@frappe.whitelist()
def fetch_intervention_data(source_doctype, source_name):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported source DocType: {0}").format(source_doctype))
    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("{0} {1} was not found.").format(source_doctype, source_name))

    if source_doctype == "Disciplinary Action":
        return _fetch_disciplinary_data(source_name)
    if source_doctype == "Incapacity Proceedings":
        return _fetch_incapacity_data(source_name)
    return _fetch_performance_data(source_name)


def _fetch_disciplinary_data(source_name):
    data = frappe.db.get_value(
        "Disciplinary Action",
        source_name,
        ["accused", "accused_name", "accused_pos", "company"],
        as_dict=True,
    ) or {}
    source = frappe.get_doc("Disciplinary Action", source_name)
    data.update(
        {
            "employee": data.get("accused") or "",
            "names": data.get("accused_name") or "",
            "position": data.get("accused_pos") or "",
            "disciplinary_history": [
                {
                    "disc_action": row.disc_action,
                    "date": row.date,
                    "sanction": row.sanction,
                    "charges": row.charges,
                }
                for row in (source.previous_disciplinary_outcomes or [])
            ],
            "dismissal_charges": [
                {"indiv_charge": f"({row.code_item}) {row.charge}"}
                for row in (source.final_charges or [])
            ],
        }
    )
    return data


def _fetch_incapacity_data(source_name):
    data = frappe.db.get_value(
        "Incapacity Proceedings",
        source_name,
        [
            "accused",
            "accused_name",
            "accused_pos",
            "company",
            "type_of_incapacity",
            "details_of_incapacity",
        ],
        as_dict=True,
    ) or {}
    source = frappe.get_doc("Incapacity Proceedings", source_name)
    data.update(
        {
            "employee": data.get("accused") or "",
            "names": data.get("accused_name") or "",
            "position": data.get("accused_pos") or "",
            "previous_incapacity_outcomes": [
                {
                    "incap_proc": row.incap_proc,
                    "date": row.date,
                    "sanction": row.sanction,
                    "incap_details": row.incap_details,
                }
                for row in (source.previous_incapacity_outcomes or [])
            ],
        }
    )
    return data


def _fetch_performance_data(source_name):
    data = fetch_performance_data(source_name) or {}
    return {
        "employee": data.get("employee") or "",
        "names": data.get("employee_name") or "",
        "position": data.get("employee_designation") or "",
        "company": data.get("company") or "",
        "performance_details": (
            data.get("performance_details")
            or data.get("details_of_poor_performance")
            or ""
        ),
        "previous_performance_outcomes": (
            data.get("previous_performance_outcomes") or []
        ),
    }


@frappe.whitelist()
def fetch_company_letter_head(company):
    return frappe.db.get_value("Company", company, "default_letter_head") or ""


@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    if doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported source DocType: {0}").format(doctype))
    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        **_get_outcome_values(linked_doc),
    }
