# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

SUPPORTED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}

VALID_SUSPENSION_NATURES = {"Precautionary", "Punitive"}
VALID_REMUNERATION_STATUSES = {"Paid", "Unpaid"}


class SuspensionForm(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        base_name = f"SUS-{self.linked_intervention}"
        existing = frappe.get_all(
            self.doctype,
            filters={
                "ir_intervention": self.ir_intervention,
                "linked_intervention": self.linked_intervention,
            },
            pluck="name",
        )

        if not existing:
            self.name = base_name
            return

        latest_revision = 0
        prefix = f"{base_name}-"
        for name in existing:
            if not name.startswith(prefix):
                continue
            try:
                latest_revision = max(latest_revision, int(name.rsplit("-", 1)[1]))
            except (TypeError, ValueError):
                continue

        self.name = f"{base_name}-{latest_revision + 1}"

    def validate(self):
        self._validate_intervention()
        self._validate_suspension_details()

    def before_save(self):
        if self.suspension_nature == "Precautionary":
            self.suspension_type = None
            return

        self._clear_source_outcome()

    def before_submit(self):
        if not self.employee:
            frappe.throw(_("Please link an Employee before submitting."))

        if not self.signed_suspension:
            frappe.throw(_("Attach the signed suspension before submitting."))

        frappe.db.set_value(
            "Employee",
            self.employee,
            "status",
            "Suspended",
            update_modified=False,
        )

    def on_submit(self):
        if self.suspension_nature == "Punitive":
            self._set_source_outcome()

    def _validate_intervention(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(_("Select a supported IR Intervention."))

        if not self.linked_intervention:
            frappe.throw(_("Select the linked IR Intervention."))

        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention,
                    self.linked_intervention,
                )
            )

    def _validate_suspension_details(self):
        if self.suspension_nature not in VALID_SUSPENSION_NATURES:
            frappe.throw(_("Select either Precautionary or Punitive Suspension."))

        if self.remuneration_status not in VALID_REMUNERATION_STATUSES:
            frappe.throw(_("Select either Paid or Unpaid remuneration status."))

        if self.suspension_nature == "Punitive" and not self.suspension_type:
            frappe.throw(_("Select the Suspension Outcome for a punitive suspension."))

        if self.from_date and self.to_date and getdate(self.to_date) < getdate(self.from_date):
            frappe.throw(_("End Date cannot be before Start Date."))

    def _get_source(self):
        return frappe.get_doc(self.ir_intervention, self.linked_intervention)

    def _clear_source_outcome(self):
        source = self._get_source()
        values = {
            "outcome": None,
            "outcome_date": None,
            "outcome_start": None,
            "outcome_end": None,
        }
        _update_source_fields(source, values)

    def _set_source_outcome(self):
        source = self._get_source()
        values = {
            "outcome": self.suspension_type,
            "outcome_date": self.outcome_date,
            "outcome_start": _("The employee is suspended from {0}.").format(self.from_date),
            "outcome_end": (
                _("The employee is suspended until {0}.").format(self.to_date)
                if self.to_date
                else None
            ),
        }
        _update_source_fields(source, values)


def _update_source_fields(source, values):
    applicable = {
        fieldname: value
        for fieldname, value in values.items()
        if source.meta.has_field(fieldname)
    }

    if not applicable:
        return

    if source.docstatus == 0:
        for fieldname, value in applicable.items():
            source.set(fieldname, value)
        source.flags.ignore_version = True
        source.save(ignore_permissions=True)
        return

    for fieldname, value in applicable.items():
        source.db_set(fieldname, value, update_modified=False)


@frappe.whitelist()
def create_suspension_form(source_name, source_doctype, suspension_nature):
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported source DocType."))

    if suspension_nature not in VALID_SUSPENSION_NATURES:
        frappe.throw(_("Unsupported suspension nature."))

    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(_("{0} {1} does not exist.").format(source_doctype, source_name))

    target = frappe.new_doc("Suspension Form")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name
    target.suspension_nature = suspension_nature
    target.remuneration_status = "Paid" if suspension_nature == "Precautionary" else "Unpaid"
    target.applied_rights = "Suspension"

    data = fetch_intervention_data(source_doctype, source_name)
    _apply_source_data(target, source_doctype, data)
    _populate_employee_rights(target)

    return target


@frappe.whitelist()
def fetch_intervention_data(ir_intervention, linked_intervention):
    if ir_intervention not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported IR Intervention."))

    if not frappe.db.exists(ir_intervention, linked_intervention):
        return {}

    if ir_intervention == "Disciplinary Action":
        return _get_disciplinary_data(linked_intervention)

    if ir_intervention == "Incapacity Proceedings":
        return _get_incapacity_data(linked_intervention)

    return _get_performance_data(linked_intervention)


def _get_disciplinary_data(name):
    source = frappe.get_doc("Disciplinary Action", name)
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "position": source.accused_pos,
        "company": source.company,
        "letter_head": _get_company_letter_head(source.company),
        "susp_charges": [
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
        "letter_head": _get_company_letter_head(source.company),
        "type_of_incapacity": source.type_of_incapacity,
        "details_of_incapacity": source.details_of_incapacity,
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


def _get_performance_data(name):
    source = frappe.get_doc("Poor Performance", name)
    return {
        "employee": source.employee,
        "names": source.employee_name,
        "position": source.employee_designation,
        "company": source.company,
        "letter_head": _get_company_letter_head(source.company),
        "performance_details": source.details_of_poor_performance,
        "previous_performance_outcomes": [
            {
                "performance_action": row.performance_action,
                "date": row.date,
                "charges": row.charges,
                "sanction": row.sanction,
            }
            for row in (source.previous_disciplinary_outcomes or [])
        ],
    }


def _apply_source_data(target, source_doctype, data):
    for fieldname in (
        "employee",
        "names",
        "position",
        "company",
        "letter_head",
        "type_of_incapacity",
        "details_of_incapacity",
        "performance_details",
    ):
        if fieldname in data:
            target.set(fieldname, data.get(fieldname))

    table_fields = {
        "Disciplinary Action": ("susp_charges", "disciplinary_history"),
        "Incapacity Proceedings": ("previous_incapacity_outcomes",),
        "Poor Performance": ("previous_performance_outcomes",),
    }

    for table_field in table_fields[source_doctype]:
        target.set(table_field, [])
        for row in data.get(table_field, []):
            target.append(table_field, row)

    target.linked_intervention_processed = 1


def _populate_employee_rights(target):
    if not frappe.db.exists("Employee Rights", "Suspension"):
        return

    rights = frappe.get_doc("Employee Rights", "Suspension")
    target.set("employee_rights", [])
    for row in rights.applicable_rights or []:
        target.append("employee_rights", {"individual_right": row.individual_right})


def _get_company_letter_head(company):
    if not company:
        return None
    return frappe.db.get_value("Company", company, "default_letter_head")


@frappe.whitelist()
def get_linked_outcome(doc_name, doctype):
    if doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(_("Unsupported IR Intervention."))

    linked_doc = frappe.get_doc(doctype, doc_name)
    return {
        "linked_doc_name": linked_doc.name,
        "linked_doctype": doctype,
        "outcome": linked_doc.get("outcome"),
        "outcome_date": linked_doc.get("outcome_date"),
        "outcome_start": linked_doc.get("outcome_start"),
        "outcome_end": linked_doc.get("outcome_end"),
    }
