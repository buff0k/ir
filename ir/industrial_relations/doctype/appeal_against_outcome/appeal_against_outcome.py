# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc

from ir.industrial_relations import utils
from ir.industrial_relations.utils import (
    appeal_and_amend_source,
    autoname_by_linked_parent,
    fetch_performance_data,
)
from ir.industrial_relations.doctype.disciplinary_action.disciplinary_action import (
    get_linked_docs_html as _get_disciplinary_action_linked_docs_html,
)
from ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings import (
    get_linked_docs_html as _get_incapacity_proceedings_linked_docs_html,
)
from ir.industrial_relations.doctype.poor_performance.poor_performance import (
    get_linked_docs_html as _get_poor_performance_linked_docs_html,
)

SOURCE_LINKED_DOCS_HTML_BY_DOCTYPE = {
    "Disciplinary Action": _get_disciplinary_action_linked_docs_html,
    "Incapacity Proceedings": _get_incapacity_proceedings_linked_docs_html,
    "Poor Performance": _get_poor_performance_linked_docs_html,
}

SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}

SUCCESSFUL_DECISIONS = {"Upheld", "Partially Upheld"}


class AppealAgainstOutcome(Document):
    def autoname(self):
        autoname_by_linked_parent(self, "APP")

    def validate(self):
        self._validate_intervention()

    def before_submit(self):
        if not self.appeal_decision or self.appeal_decision == "Pending":
            frappe.throw(_("Select the Appeal Decision before submitting."))

    def on_submit(self):
        self._validate_intervention()

        source = frappe.get_doc(self.ir_intervention, self.linked_intervention)
        if source.docstatus != 1:
            frappe.throw(
                _("{0} {1} is not a submitted record - it may already have been appealed.").format(
                    self.ir_intervention, self.linked_intervention
                )
            )

        if self.appeal_decision in SUCCESSFUL_DECISIONS:
            amended_name = appeal_and_amend_source(self.ir_intervention, self.linked_intervention)
            self.db_set("linked_amended_intervention", amended_name, update_modified=False)

    def _validate_intervention(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Select a supported IR Intervention."))
        if not self.linked_intervention:
            frappe.throw(_("Linked IR Intervention is required."))
        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(self.ir_intervention, self.linked_intervention)
            )


@frappe.whitelist()
def appeal_disciplinary(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.ir_intervention = "Disciplinary Action"
        target.linked_intervention = source_name

    return get_mapped_doc(
        "Disciplinary Action",
        source_name,
        {
            "Disciplinary Action": {
                "doctype": "Appeal Against Outcome",
                "field_map": {"name": "linked_intervention"},
            }
        },
        target_doc,
        set_missing_values,
    )


@frappe.whitelist()
def appeal_incapacity(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.ir_intervention = "Incapacity Proceedings"
        target.linked_intervention = source_name

    return get_mapped_doc(
        "Incapacity Proceedings",
        source_name,
        {
            "Incapacity Proceedings": {
                "doctype": "Appeal Against Outcome",
                "field_map": {"name": "linked_intervention"},
            }
        },
        target_doc,
        set_missing_values,
    )


@frappe.whitelist()
def appeal_poor_performance(source_name, target_doc=None):
    def set_missing_values(source, target):
        target.ir_intervention = "Poor Performance"
        target.linked_intervention = source_name

    return get_mapped_doc(
        "Poor Performance",
        source_name,
        {
            "Poor Performance": {
                "doctype": "Appeal Against Outcome",
                "field_map": {"name": "linked_intervention"},
            }
        },
        target_doc,
        set_missing_values,
    )


@frappe.whitelist()
def fetch_intervention_data(ir_intervention, linked_intervention):
    return get_intervention_data(ir_intervention, linked_intervention)


def get_intervention_data(ir_intervention, linked_intervention):
    if ir_intervention not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported intervention type."))

    if not frappe.db.exists(ir_intervention, linked_intervention):
        return {}

    if ir_intervention == "Disciplinary Action":
        return _get_disciplinary_action_data(linked_intervention)
    if ir_intervention == "Incapacity Proceedings":
        return _get_incapacity_data(linked_intervention)
    return _get_poor_performance_data(linked_intervention)


def _get_disciplinary_action_data(name):
    source = frappe.get_doc("Disciplinary Action", name)
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "coy": source.accused_coy,
        "position": source.accused_pos,
        "company": source.company,
        "outcome": source.outcome,
        "dismissal_charges": [
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
        "outcome": source.outcome,
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
    data = fetch_performance_data(name) or {}
    return {
        "employee": data.get("employee"),
        "names": data.get("employee_name"),
        "coy": data.get("employee"),
        "position": data.get("employee_designation"),
        "company": data.get("company"),
        "outcome": data.get("outcome"),
        "performance_details": data.get("details_of_poor_performance"),
        "previous_performance_outcomes": data.get("previous_performance_outcomes") or [],
    }


@frappe.whitelist()
def fetch_company_letter_head(company):
    letter_head = frappe.db.get_value("Company", company, "default_letter_head")
    return {"letter_head": letter_head} if letter_head else {}


@frappe.whitelist()
def fetch_chairperson_name(employee):
    employee_name = frappe.db.get_value("Employee", employee, "employee_name")
    return {"employee_name": employee_name} if employee_name else {}


def _linked_doc_mappings():
    """Documents that belong to the appeal proceeding itself (e.g. an NTA Enquiry
    scheduling the appeal hearing, or the Written Outcome recording its decision)
    - as opposed to documents belonging to the original case, see
    get_linked_docs_html below.
    """
    return [
        ("NTA Enquiries", "NTA Enquiry",
            {"ir_intervention": "Appeal Against Outcome", "linked_intervention": None}),
        ("Written Outcomes", "Written Outcome",
            {"ir_intervention": "Appeal Against Outcome", "linked_intervention": None}),
        ("Warnings", "Warning Form",
            {"ir_intervention": "Appeal Against Outcome", "linked_intervention": None}),
        ("No Further Action Forms", "No Further Action Form",
            {"ir_intervention": "Appeal Against Outcome", "linked_intervention": None}),
    ]


@frappe.whitelist()
def get_linked_docs_html(appeal_name: str) -> str:
    """Renders two card grids: documents belonging to this appeal itself, and
    (read-only reference) the documents already on the original case it was
    raised against - so a user reviewing the appeal doesn't have to navigate
    away to see the case history it's superseding.
    """
    appeal = frappe.get_doc("Appeal Against Outcome", appeal_name)
    appeal_html = utils.render_linked_docs_html(appeal_name, _linked_doc_mappings())

    source_html = ""
    get_source_html = SOURCE_LINKED_DOCS_HTML_BY_DOCTYPE.get(appeal.ir_intervention)
    if get_source_html and appeal.linked_intervention:
        source_html = get_source_html(appeal.linked_intervention)

    return f"""
    <div class="ir-appeal-linked-docs">
      <div class="ir-linked-docs-heading">{_("This Appeal")}</div>
      {appeal_html}
      <div class="ir-linked-docs-heading">{_("Original Case")}: {appeal.linked_intervention}</div>
      {source_html}
    </div>
    """
