# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document


SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action": {
        "default_outcome": "NG",
        "outcome_flag": "isnotguilty",
    },
    "Poor Performance": {
        "default_outcome": "PI",
        "outcome_flag": "is_a_performance_improvement",
    },
    "Incapacity Proceedings": {
        "default_outcome": "FIT",
        "outcome_flag": "is_not_incapacitated",
    },
}


def _text(value):
    return (value or "").strip()


def _has_field(doctype: str, fieldname: str) -> bool:
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _first_value(doc, *fieldnames):
    for fieldname in fieldnames:
        if _has_field(doc.doctype, fieldname):
            value = doc.get(fieldname)
            if value not in (None, ""):
                return value
    return None


def _copy_rows(source, fieldname: str, mappings: dict[str, tuple[str, ...]]) -> list[dict]:
    if not _has_field(source.doctype, fieldname):
        return []

    rows = []
    for source_row in source.get(fieldname) or []:
        target_row = {}
        for target_field, source_fields in mappings.items():
            for source_field in source_fields:
                value = source_row.get(source_field)
                if value not in (None, ""):
                    target_row[target_field] = value
                    break
        rows.append(target_row)
    return rows


def _disciplinary_payload(source) -> dict:
    charges = []
    for row in source.get("final_charges") or []:
        code = _text(row.get("code_item"))
        charge = _text(row.get("charge"))
        if not charge:
            continue
        charges.append({"indiv_charge": f"({code}) {charge}" if code else charge})

    return {
        "employee": _first_value(source, "accused", "employee"),
        "names": _first_value(source, "accused_name", "employee_name"),
        "designation": _first_value(source, "accused_pos", "employee_designation", "designation"),
        "company": _first_value(source, "company"),
        "letter_head": _first_value(source, "letter_head"),
        "ng_charges": charges,
        "disciplinary_history": _copy_rows(
            source,
            "previous_disciplinary_outcomes",
            {
                "disc_action": ("disc_action",),
                "date": ("date",),
                "sanction": ("sanction",),
                "charges": ("charges",),
            },
        ),
    }


def _incapacity_payload(source) -> dict:
    return {
        "employee": _first_value(source, "accused", "employee"),
        "names": _first_value(source, "accused_name", "employee_name"),
        "designation": _first_value(source, "accused_pos", "employee_designation", "designation"),
        "company": _first_value(source, "company"),
        "letter_head": _first_value(source, "letter_head"),
        "type_of_incapacity": _first_value(source, "type_of_incapacity"),
        "details_of_incapacity": _first_value(source, "details_of_incapacity") or "",
        "previous_incapacity_outcomes": _copy_rows(
            source,
            "previous_incapacity_outcomes",
            {
                "incap_proc": ("incap_proc",),
                "date": ("date",),
                "sanction": ("sanction",),
                "incap_details": ("incap_details",),
            },
        ),
    }


def _performance_payload(source) -> dict:
    return {
        "employee": _first_value(source, "employee", "accused"),
        "names": _first_value(source, "employee_name", "accused_name"),
        "designation": _first_value(source, "employee_designation", "accused_pos", "designation"),
        "company": _first_value(source, "company"),
        "letter_head": _first_value(source, "letter_head"),
        "performance_details_nta": _first_value(
            source,
            "details_of_poor_performance",
            "performance_details",
        ) or "",
        "previous_performance_outcomes": _copy_rows(
            source,
            "previous_disciplinary_outcomes",
            {
                "performance_action": ("performance_action", "disc_action"),
                "date": ("date",),
                "sanction": ("sanction",),
                "charges": ("charges", "performance_details"),
            },
        ),
    }


def _source_payload(source) -> dict:
    if source.doctype == "Disciplinary Action":
        return _disciplinary_payload(source)
    if source.doctype == "Incapacity Proceedings":
        return _incapacity_payload(source)
    if source.doctype == "Poor Performance":
        return _performance_payload(source)
    frappe.throw(_("Unsupported IR Intervention: {0}").format(source.doctype))


def _validate_outcome_type(intervention_type: str, outcome_type: str) -> None:
    config = SUPPORTED_INTERVENTIONS.get(intervention_type)
    if not config:
        frappe.throw(_("Unsupported IR Intervention: {0}").format(intervention_type))

    if not outcome_type or not frappe.db.exists("Offence Outcome", outcome_type):
        frappe.throw(_("Please select a valid Outcome Type."))

    flag_field = config["outcome_flag"]
    if not _has_field("Offence Outcome", flag_field):
        frappe.throw(
            _("Offence Outcome is missing the required field {0}.").format(flag_field)
        )

    is_allowed = frappe.db.get_value("Offence Outcome", outcome_type, flag_field)
    if not is_allowed:
        frappe.throw(
            _("Outcome {0} is not valid for {1}.").format(
                outcome_type,
                intervention_type,
            )
        )


def _set_source_outcome(source, outcome_type, outcome_date):
    old_outcome = source.get("outcome") if _has_field(source.doctype, "outcome") else None
    old_date = source.get("outcome_date") if _has_field(source.doctype, "outcome_date") else None

    updates = {}
    if _has_field(source.doctype, "outcome"):
        updates["outcome"] = outcome_type
    if _has_field(source.doctype, "outcome_date"):
        updates["outcome_date"] = outcome_date

    if not updates:
        frappe.throw(
            _("{0} does not contain outcome fields that can be updated.").format(
                source.doctype
            )
        )

    for fieldname, value in updates.items():
        source.db_set(fieldname, value, update_modified=False)

    frappe.get_doc(
        {
            "doctype": "Version",
            "ref_doctype": source.doctype,
            "docname": source.name,
            "data": frappe.as_json(
                {
                    "changed": [
                        ["outcome", old_outcome, updates.get("outcome", old_outcome)],
                        ["outcome_date", old_date, updates.get("outcome_date", old_date)],
                    ]
                }
            ),
        }
    ).insert(ignore_permissions=True)


def _clear_source_outcome_if_owned(source, outcome_type, outcome_date):
    current_outcome = source.get("outcome") if _has_field(source.doctype, "outcome") else None
    current_date = source.get("outcome_date") if _has_field(source.doctype, "outcome_date") else None

    if current_outcome != outcome_type or current_date != outcome_date:
        return

    if _has_field(source.doctype, "outcome"):
        source.db_set("outcome", None, update_modified=False)
    if _has_field(source.doctype, "outcome_date"):
        source.db_set("outcome_date", None, update_modified=False)


class NoFurtherActionForm(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        base = f"NFA-{self.linked_intervention}"
        existing = frappe.get_all(
            self.doctype,
            filters={
                "ir_intervention": self.ir_intervention,
                "linked_intervention": self.linked_intervention,
            },
            pluck="name",
        )

        if base not in existing:
            self.name = base
            return

        pattern = re.compile(rf"^{re.escape(base)}-(\d+)$")
        revisions = []
        for name in existing:
            match = pattern.match(name or "")
            if match:
                revisions.append(int(match.group(1)))

        self.name = f"{base}-{(max(revisions) + 1) if revisions else 1}"

    def validate(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Unsupported IR Intervention: {0}").format(self.ir_intervention))

        if not self.linked_intervention:
            frappe.throw(_("Please select a Linked IR Intervention."))

        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention,
                    self.linked_intervention,
                )
            )

        _validate_outcome_type(self.ir_intervention, self.outcome_type)

    def before_submit(self):
        if not self.signed_ng:
            frappe.throw(_("You must attach the signed outcome before submitting."))

    def on_submit(self):
        source = frappe.get_doc(self.ir_intervention, self.linked_intervention)
        _set_source_outcome(source, self.outcome_type, self.outcome_date)

    def on_cancel(self):
        source = frappe.get_doc(self.ir_intervention, self.linked_intervention)
        _clear_source_outcome_if_owned(source, self.outcome_type, self.outcome_date)


@frappe.whitelist()
def get_intervention_config(intervention_type: str) -> dict:
    config = SUPPORTED_INTERVENTIONS.get(intervention_type)
    if not config:
        return {}
    return dict(config)


@frappe.whitelist()
def fetch_intervention_data(intervention_type: str, intervention_name: str) -> dict:
    if intervention_type not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported IR Intervention: {0}").format(intervention_type))

    if not frappe.db.exists(intervention_type, intervention_name):
        frappe.throw(_("{0} {1} does not exist.").format(intervention_type, intervention_name))

    source = frappe.get_doc(intervention_type, intervention_name)
    source.check_permission("read")

    payload = _source_payload(source)
    payload["outcome_type"] = SUPPORTED_INTERVENTIONS[intervention_type]["default_outcome"]
    return payload


@frappe.whitelist()
def create_no_further_action_form(source_name=None, source_doctype=None):
    source_name = source_name or frappe.form_dict.get("source_name")
    source_doctype = source_doctype or frappe.form_dict.get("source_doctype")

    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported source DocType: {0}").format(source_doctype))

    if not source_name or not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("{0} {1} does not exist.").format(source_doctype, source_name))

    source = frappe.get_doc(source_doctype, source_name)
    source.check_permission("read")

    target = frappe.new_doc("No Further Action Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name

    payload = _source_payload(source)
    payload["outcome_type"] = SUPPORTED_INTERVENTIONS[source_doctype]["default_outcome"]

    for fieldname, value in payload.items():
        if fieldname in {
            "ng_charges",
            "disciplinary_history",
            "previous_incapacity_outcomes",
            "previous_performance_outcomes",
        }:
            target.set(fieldname, value or [])
        elif target.meta.get_field(fieldname):
            target.set(fieldname, value)

    target.linked_intervention_processed = 1
    return target.as_dict()
