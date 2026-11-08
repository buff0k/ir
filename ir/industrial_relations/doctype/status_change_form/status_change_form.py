# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import formatdate

from ir.industrial_relations.utils import fetch_company_letter_head

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _clear_inapplicable_status_change_detail_fields(row):
    is_link_row = row.change_type in ("Branch", "Designation")
    is_condition_row = row.change_type == "Conditions of Employment"
    is_salary_row = row.change_type == "Salary Component"

    if not is_link_row:
        row.old_value = None
        row.new_value = None
    if not is_condition_row:
        row.old_condition = None
        row.new_condition = None
    if not is_salary_row:
        row.salary_component = None
        row.old_amount = 0
        row.new_amount = 0


def _is_no_op_status_change_detail_row(row) -> bool:
    if row.change_type in ("Designation", "Branch"):
        return (row.old_value or None) == (row.new_value or None)
    if row.change_type == "Conditions of Employment":
        return (row.old_condition or None) == (row.new_condition or None)
    if row.change_type == "Salary Component":
        return (row.old_amount or 0) == (row.new_amount or 0)
    return False


class StatusChangeForm(Document):
    def autoname(self):
        effective_date = formatdate(self.effective_date, "dd-MM-yyyy") if self.effective_date else ""
        current_designation = (
            frappe.db.get_value("Employee", self.employee, "designation") if self.employee else None
        )
        designation_row = next(
            (r for r in self.get("status_change_details") or [] if r.change_type == "Designation"), None
        )
        new_designation = designation_row.new_value if designation_row else current_designation

        name = f"{self.employee} - {current_designation} to {new_designation} - {effective_date}"
        self.name = _clean(name)

        if frappe.db.exists(self.doctype, self.name):
            frappe.throw(
                f"Duplicate record: a Status Change Form already exists for "
                f"{self.employee} from {current_designation} to {new_designation} on {effective_date}."
            )

    def validate(self):
        """Server-side autopopulation (covers UI + API/import)."""
        if self.requested_by:
            vals = frappe.db.get_value(
                "Employee",
                self.requested_by,
                ["employee_name", "designation"],
                as_dict=True
            ) or {}
            self.requested_by_name = vals.get("employee_name")
            self.requested_by_designation = vals.get("designation")

        current_designation = None
        current_branch = None

        if self.employee:
            vals = frappe.db.get_value(
                "Employee",
                self.employee,
                ["employee_name", "designation", "branch", "company"],
                as_dict=True
            ) or {}
            self.employee_name = vals.get("employee_name")
            current_designation = vals.get("designation")
            current_branch = vals.get("branch")
            self.company = vals.get("company")
            self.letter_head = fetch_company_letter_head(self.company).get("letter_head") if self.company else None

        details = []
        for row in self.get("status_change_details") or []:
            _clear_inapplicable_status_change_detail_fields(row)
            if row.change_type == "Designation":
                row.old_value = current_designation
            elif row.change_type == "Branch":
                row.old_value = current_branch

            if not _is_no_op_status_change_detail_row(row):
                details.append(row)
        self.set("status_change_details", details)

        self._validate_salary_component_types()

    def _validate_salary_component_types(self):
        component_names = {
            row.salary_component
            for row in self.get("status_change_details") or []
            if row.change_type == "Salary Component" and row.salary_component
        }
        if not component_names:
            return

        non_earning = frappe.get_all(
            "Salary Component",
            filters={"name": ["in", list(component_names)], "type": ["!=", "Earning"]},
            pluck="name",
        )
        if non_earning:
            frappe.throw(
                "Status Change Details can only reference Earning-type Salary Components, "
                f"not: {', '.join(non_earning)}."
            )

    def before_submit(self):
        if not self.attach:
            frappe.throw("You must attach the signed status change form before submitting.")
        if not self.get("status_change_details"):
            frappe.throw("At least one change must be recorded in Status Change Details before submitting.")

    def on_submit(self):
        if not self.employee:
            frappe.throw("Employee is required.")
        if not self.effective_date:
            frappe.throw("Effective Date is required.")

        details = self.get("status_change_details") or []
        designation_row = next((r for r in details if r.change_type == "Designation"), None)
        branch_row = next((r for r in details if r.change_type == "Branch"), None)

        designation_changed = designation_row is not None
        branch_changed = branch_row is not None

        if not designation_changed and not branch_changed:
            return

        emp = frappe.get_doc("Employee", self.employee)

        current_desig = getattr(emp, "designation", None)
        new_desig = designation_row.new_value if designation_row else current_desig
        current_branch = getattr(emp, "branch", None)
        new_branch = branch_row.new_value if branch_row else current_branch

        history = emp.get("internal_work_history") or []

        def get_latest_row(rows):
            if not rows:
                return None
            with_from = [r for r in rows if getattr(r, "from_date", None)]
            if with_from:
                return sorted(with_from, key=lambda r: r.from_date)[-1]
            return rows[-1]

        if not history:
            emp.append("internal_work_history", {
                "branch": current_branch,
                "department": getattr(emp, "department", None),
                "designation": current_desig,
                "from_date": getattr(emp, "date_of_joining", None),
                "to_date": self.effective_date,
            })
            prev_branch = current_branch
            prev_department = getattr(emp, "department", None)
        else:
            latest = get_latest_row(history)
            if not latest:
                frappe.throw("Could not determine latest internal work history record.")

            latest.to_date = self.effective_date

            prev_branch = getattr(latest, "branch", None) or current_branch
            prev_department = getattr(latest, "department", None) or getattr(emp, "department", None)

        emp.append("internal_work_history", {
            "branch": new_branch if branch_changed else prev_branch,
            "department": prev_department,
            "designation": new_desig if designation_changed else current_desig,
            "from_date": self.effective_date,
            "to_date": None,
        })

        emp.save(ignore_permissions=True)

        if designation_changed:
            emp.designation = new_desig
        if branch_changed:
            emp.branch = new_branch
        emp.save(ignore_permissions=True)
