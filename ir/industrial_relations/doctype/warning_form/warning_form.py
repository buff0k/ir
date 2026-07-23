# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from ir.industrial_relations.utils import clear_parent_outcome, fetch_performance_data


SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


class WarningForm(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        prefix = f"WAR-{self.linked_intervention}"
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

    def before_save(self):
        self._clear_linked_outcome()

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        if not self.signed_warning:
            frappe.throw(_("You must attach the signed warning before submitting."))

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
            for fieldname in ("outcome", "outcome_date", "outcome_start", "outcome_end")
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
            values["outcome"] = self.warning_type
        if linked_doc.meta.has_field("outcome_date"):
            values["outcome_date"] = self.outcome_date

        if values:
            linked_doc.db_set(values, update_modified=False)


@frappe.whitelist()
def create_warning_form(source_name, source_doctype):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(
            _("Unsupported intervention type: {0}").format(source_doctype)
        )

    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(
            _("{0} {1} does not exist.").format(
                source_doctype,
                source_name,
            )
        )

    target = frappe.new_doc("Warning Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name
    target.applied_rights = "Warning Form"

    data = get_intervention_data(
        source_doctype,
        source_name,
    )
    _apply_intervention_data(target, data)
    _apply_employee_rights(
        target,
        target.applied_rights,
    )

    target.linked_intervention_processed = 1
    return target


@frappe.whitelist()
def fetch_intervention_data(ir_intervention, linked_intervention):
    return get_intervention_data(ir_intervention, linked_intervention)


def get_intervention_data(
    ir_intervention,
    linked_intervention,
):
    if ir_intervention not in SUPPORTED_INTERVENTIONS:
        frappe.throw(
            _("Unsupported intervention type.")
        )

    if not frappe.db.exists(
        ir_intervention,
        linked_intervention,
    ):
        return {}

    if ir_intervention == "Disciplinary Action":
        return _get_disciplinary_action_data(
            linked_intervention
        )

    if ir_intervention == "Incapacity Proceedings":
        return _get_incapacity_data(
            linked_intervention
        )

    if ir_intervention == "Poor Performance":
        return _get_poor_performance_data(
            linked_intervention
        )

    return {}


def _get_disciplinary_action_data(name):
    source = frappe.get_doc("Disciplinary Action", name)
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "coy": source.accused_coy,
        "position": source.accused_pos,
        "company": source.company,
        "warning_charges": [
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
        "coy": source.accused_coy,
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
        "coy": source_data.get("employee"),
        "position": source_data.get("employee_designation"),
        "company": source_data.get("company"),
        "performance_details": source_data.get("details_of_poor_performance"),
        "previous_performance_outcomes": source_data.get("previous_performance_outcomes") or [],
    }


def _apply_intervention_data(target, data):
    for fieldname in (
        "employee",
        "names",
        "coy",
        "position",
        "company",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ):
        if target.meta.has_field(fieldname):
            target.set(fieldname, data.get(fieldname))

    for fieldname in (
        "warning_charges",
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

    if not frappe.db.exists(
        "Employee Rights",
        employee_rights_name,
    ):
        frappe.throw(
            _("Employee Rights record {0} does not exist.").format(
                employee_rights_name
            )
        )

    rights_doc = frappe.get_doc(
        "Employee Rights",
        employee_rights_name,
    )

    for row in rights_doc.get("applicable_rights") or []:
        target.append(
            "employee_rights",
            {
                "individual_right": row.individual_right,
            },
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
    }
