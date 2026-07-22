# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from ir.industrial_relations.utils import (
    autoname_by_linked_parent,
    clear_parent_outcome,
    set_parent_outcome,
)


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


CANCELLATION_FLAG = "iscancellation"


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


def _get_outcome_flags(outcome_type: str, *fieldnames: str) -> frappe._dict:
    if not outcome_type or not frappe.db.exists("Offence Outcome", outcome_type):
        frappe.throw(_("Please select a valid Outcome Type."))

    available_fields = [
        fieldname
        for fieldname in fieldnames
        if _has_field("Offence Outcome", fieldname)
    ]

    if not available_fields:
        return frappe._dict()

    return frappe.db.get_value(
        "Offence Outcome",
        outcome_type,
        available_fields,
        as_dict=True,
    ) or frappe._dict()


def _is_cancellation_outcome(outcome_type: str) -> bool:
    if not _has_field("Offence Outcome", CANCELLATION_FLAG):
        return False

    return bool(
        frappe.db.get_value(
            "Offence Outcome",
            outcome_type,
            CANCELLATION_FLAG,
        )
    )


def _validate_outcome_type(intervention_type: str, outcome_type: str) -> None:
    config = SUPPORTED_INTERVENTIONS.get(intervention_type)
    if not config:
        frappe.throw(_("Unsupported IR Intervention: {0}").format(intervention_type))

    process_flag = config["outcome_flag"]
    required_flags = [process_flag, CANCELLATION_FLAG]

    for fieldname in required_flags:
        if not _has_field("Offence Outcome", fieldname):
            frappe.throw(
                _("Offence Outcome is missing the required field {0}.").format(fieldname)
            )

    flags = _get_outcome_flags(outcome_type, process_flag, CANCELLATION_FLAG)
    if not flags.get(process_flag) and not flags.get(CANCELLATION_FLAG):
        frappe.throw(
            _("Outcome {0} is not valid for {1}.").format(
                outcome_type,
                intervention_type,
            )
        )


def _set_if_present(doc, fieldname: str, value) -> None:
    if _has_field(doc.doctype, fieldname):
        doc.set(fieldname, value)


def _populate_authorizer_details(doc) -> None:
    if not _has_field(doc.doctype, "authorized_by"):
        return

    if not doc.get("authorized_by"):
        _set_if_present(doc, "auth_names", None)
        _set_if_present(doc, "auth_designation", None)
        return

    employee = frappe.db.get_value(
        "Employee",
        doc.get("authorized_by"),
        ["employee_name", "designation"],
        as_dict=True,
    )

    if not employee:
        frappe.throw(_("Authorising Employee {0} does not exist.").format(doc.get("authorized_by")))

    _set_if_present(doc, "auth_names", employee.employee_name)
    _set_if_present(doc, "auth_designation", employee.designation)


class NoFurtherActionForm(Document):
    def autoname(self):
        autoname_by_linked_parent(self, "NFA")

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

        is_cancellation = _is_cancellation_outcome(self.outcome_type)

        if is_cancellation:
            _populate_authorizer_details(self)

            if not self.get("authorized_by"):
                frappe.throw(_("Authorised By is required for a cancellation."))

            if not _text(self.get("cancel_reason")):
                frappe.throw(_("Reason for Cancellation is required for a cancellation."))
        else:
            _set_if_present(self, "authorized_by", None)
            _set_if_present(self, "auth_names", None)
            _set_if_present(self, "auth_designation", None)
            _set_if_present(self, "cancel_reason", None)

    def before_submit(self):
        if not self.signed_ng:
            frappe.throw(_("You must attach the signed outcome before submitting."))

    def on_submit(self):
        set_parent_outcome(self, self.outcome_type, self.outcome_date)

    def on_cancel(self):
        clear_parent_outcome(self)


@frappe.whitelist()
def get_intervention_config(intervention_type: str) -> dict:
    config = SUPPORTED_INTERVENTIONS.get(intervention_type)
    if not config:
        return {}
    return dict(config)


@frappe.whitelist()
def get_allowed_outcomes(intervention_type: str) -> list[str]:
    config = SUPPORTED_INTERVENTIONS.get(intervention_type)
    if not config:
        return []

    process_flag = config["outcome_flag"]
    for fieldname in (process_flag, CANCELLATION_FLAG):
        if not _has_field("Offence Outcome", fieldname):
            return []

    rows = frappe.get_all(
        "Offence Outcome",
        filters=[
            ["Offence Outcome", process_flag, "=", 1],
        ],
        pluck="name",
        order_by="disc_offence_out asc",
    )

    cancellations = frappe.get_all(
        "Offence Outcome",
        filters={CANCELLATION_FLAG: 1},
        pluck="name",
        order_by="disc_offence_out asc",
    )

    return list(dict.fromkeys([*rows, *cancellations]))


@frappe.whitelist()
def get_outcome_state(outcome_type: str | None = None) -> dict:
    if not outcome_type or not frappe.db.exists("Offence Outcome", outcome_type):
        return {"is_cancellation": 0}

    return {
        "is_cancellation": 1 if _is_cancellation_outcome(outcome_type) else 0,
    }


@frappe.whitelist()
def get_authorizer_details(employee: str | None = None) -> dict:
    if not employee:
        return {"auth_names": None, "auth_designation": None}

    values = frappe.db.get_value(
        "Employee",
        employee,
        ["employee_name", "designation"],
        as_dict=True,
    )

    if not values:
        return {"auth_names": None, "auth_designation": None}

    return {
        "auth_names": values.employee_name,
        "auth_designation": values.designation,
    }


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
def create_no_further_action_form(
    source_name=None,
    source_doctype=None,
    outcome_type=None,
):
    source_name = source_name or frappe.form_dict.get("source_name")
    source_doctype = source_doctype or frappe.form_dict.get("source_doctype")
    outcome_type = outcome_type or frappe.form_dict.get("outcome_type")

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
    payload["outcome_type"] = (
        outcome_type
        or SUPPORTED_INTERVENTIONS[source_doctype]["default_outcome"]
    )

    _validate_outcome_type(source_doctype, payload["outcome_type"])

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
