# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from ir.industrial_relations.utils import (
    autoname_by_linked_parent,
    clear_parent_outcome,
    fetch_company_letter_head as _fetch_company_letter_head,
    fetch_performance_data,
    get_linked_outcome as _get_linked_outcome,
    hydrate_employee_from_source,
    set_parent_outcome,
)

SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


class DemotionForm(Document):
    def autoname(self):
        autoname_by_linked_parent(self, "DEM")

    def validate(self):
        self._validate_intervention()
        self._validate_demotion()

    def before_save(self):
        # Preserve current behaviour: saving a draft clears an existing source outcome.
        if not self.flags.get("skip_clear_parent_outcome"):
            clear_parent_outcome(self)

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))
        if not self.position:
            frappe.throw(_("Current Position is required before submitting."))
        if not self.new_position:
            frappe.throw(_("New Position after Demotion is required before submitting."))
        if self.position == self.new_position:
            frappe.throw(_("The new position must differ from the employee's current position."))
        if not self.signed_demotion:
            frappe.throw(_("You must attach the signed demotion before submitting."))

        self._apply_demotion()

    def on_submit(self):
        self._set_source_outcome()

    def _validate_intervention(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Unsupported IR Intervention: {0}").format(self.ir_intervention))
        if not self.linked_intervention:
            frappe.throw(_("Linked IR Intervention is required."))
        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention, self.linked_intervention
                )
            )

    def _validate_demotion(self):
        if self.from_date and self.to_date and getdate(self.to_date) < getdate(self.from_date):
            frappe.throw(_("End Date of Demotion cannot be before From Date."))

    def _apply_demotion(self):
        employee = frappe.get_doc("Employee", self.employee)
        old_designation = employee.designation

        employee.designation = self.new_position
        employee.status = "Active"
        _append_employee_audit(
            employee,
            fieldname="designation",
            old_value=old_designation,
            new_value=self.new_position,
            reference_doctype=self.doctype,
            reference_name=self.name,
            remarks=_("Demotion applied from {0}").format(self.from_date),
        )
        employee.save(ignore_permissions=True)

        self.demotion_applied = 1
        self.demotion_reversed = 0
        self.demotion_reversed_on = None

    def _set_source_outcome(self):
        if self.to_date:
            outcome_start = _(
                "The employee is demoted to {0} from {1}."
            ).format(self.new_position, self.from_date)
            outcome_end = _(
                "The temporary demotion ends on {0}, after which the employee is to return to {1}."
            ).format(self.to_date, self.position)
        else:
            outcome_start = _(
                "The employee is demoted to {0} with effect from {1}."
            ).format(self.new_position, self.from_date)
            outcome_end = None

        # set_parent_outcome currently omits None values, so clear a stale end explicitly.
        set_parent_outcome(
            self,
            self.demotion_type,
            self.outcome_date,
            outcome_start,
            outcome_end,
        )
        if not self.to_date:
            linked = frappe.get_doc(self.ir_intervention, self.linked_intervention)
            if linked.docstatus == 0:
                linked.outcome_end = None
                linked.save(ignore_permissions=True)
            else:
                linked.db_set("outcome_end", None, update_modified=False)


def _append_employee_audit(employee, *, fieldname, old_value, new_value, reference_doctype, reference_name, remarks):
    """Append to the custom Employee audit table when that table exists.

    The app's deployed audit child DocType has changed over time, so this helper
    fills recognised field names dynamically instead of hard-coding one schema.
    Standard Employee Version history is also created by employee.save() where
    Employee Track Changes is enabled.
    """
    if not employee.meta.has_field("ir_employee_audit"):
        return

    table_field = employee.meta.get_field("ir_employee_audit")
    if not table_field or not table_field.options:
        return

    child_meta = frappe.get_meta(table_field.options)
    row = employee.append("ir_employee_audit", {})
    values = {
        "change_date": frappe.utils.now_datetime(),
        "date": frappe.utils.today(),
        "modified_on": frappe.utils.now_datetime(),
        "changed_by": frappe.session.user,
        "user": frappe.session.user,
        "fieldname": fieldname,
        "field_name": fieldname,
        "field": fieldname,
        "old_value": old_value,
        "previous_value": old_value,
        "new_value": new_value,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "reference_document": reference_name,
        "remarks": remarks,
        "description": remarks,
    }
    for key, value in values.items():
        if child_meta.has_field(key):
            row.set(key, value)


@frappe.whitelist()
def create_demotion_form(source_name: str, source_doctype: str):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported IR Intervention: {0}").format(source_doctype))
    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("{0} {1} does not exist.").format(source_doctype, source_name))

    source = frappe.get_doc(source_doctype, source_name)
    target = frappe.new_doc("Demotion Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name
    target.linked_intervention_processed = 1
    hydrate_employee_from_source(source, target)

    # position is intentionally editable and represents the reviewed pre-demotion position.
    target.position = (
        source.get("employee_designation")
        or source.get("accused_pos")
        or frappe.db.get_value("Employee", target.employee, "designation")
    )
    target.applied_rights = "Demotion"
    target.company = source.get("company")
    if target.company:
        target.letter_head = frappe.db.get_value("Company", target.company, "default_letter_head")

    _populate_rights(target)
    if source_doctype == "Disciplinary Action":
        _populate_disciplinary(source, target)
    elif source_doctype == "Incapacity Proceedings":
        _populate_incapacity(source, target)
    else:
        _populate_performance(source, target)

    return target


def _populate_rights(target):
    if not frappe.db.exists("Employee Rights", "Demotion"):
        return
    rights = frappe.get_doc("Employee Rights", "Demotion")
    target.set("employee_rights", [])
    for item in rights.get("applicable_rights") or []:
        target.append("employee_rights", {"individual_right": item.get("individual_right")})


def _populate_disciplinary(source, target):
    target.set("disciplinary_history", [])
    for row in source.get("previous_disciplinary_outcomes") or []:
        target.append("disciplinary_history", {
            "disc_action": row.get("disc_action"),
            "date": row.get("date"),
            "sanction": row.get("sanction"),
            "charges": row.get("charges"),
        })
    target.set("dem_charges", [])
    for row in source.get("final_charges") or []:
        code = row.get("code_item") or ""
        charge = row.get("charge") or ""
        text = f"({code}) {charge}" if code else charge
        target.append("dem_charges", {"indiv_charge": text})


def _populate_incapacity(source, target):
    target.type_of_incapacity = source.get("type_of_incapacity")
    target.details_of_incapacity = source.get("details_of_incapacity")
    target.set("previous_incapacity_outcomes", [])
    for row in source.get("previous_incapacity_outcomes") or []:
        target.append("previous_incapacity_outcomes", {
            "incap_proc": row.get("incap_proc"),
            "date": row.get("date"),
            "sanction": row.get("sanction"),
            "incap_details": row.get("incap_details"),
        })


def _populate_performance(source, target):
    data = fetch_performance_data(source.name)
    target.performance_details = data.get("performance_details")
    target.set("previous_performance_outcomes", [])
    for row in data.get("previous_performance_outcomes") or []:
        target.append("previous_performance_outcomes", row)


@frappe.whitelist()
def fetch_company_letter_head(company):
    return _fetch_company_letter_head(company)


@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    return _get_linked_outcome(doc_name, doctype)
