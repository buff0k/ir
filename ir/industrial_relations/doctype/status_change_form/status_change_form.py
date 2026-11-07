# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import formatdate

from ir.industrial_relations.doctype.status_change_form.status_change_detail_backfill import (
    build_status_change_detail_rows,
)
from ir.industrial_relations.utils import fetch_company_letter_head

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _clear_inapplicable_status_change_detail_fields(row):
    """Status Change Detail rows carry fields for all four change_type
    shapes (Branch/Designation's old_value+new_value Dynamic Links,
    Conditions of Employment's old_condition+new_condition Selects, and
    Salary Component's salary_component+old_amount+new_amount) at once -
    this blanks out whichever sets don't match the row's current
    change_type, so switching a row's type doesn't leave stale data from
    the type it used to be sitting in the fields that are now hidden."""
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

class StatusChangeForm(Document):
    def autoname(self):
        # current_designation is no longer a stored field (see validate()) -
        # autoname() runs before validate() populates anything anyway, so
        # this was always really just an Employee lookup under the hood.
        effective_date = formatdate(self.effective_date, "dd-MM-yyyy") if self.effective_date else ""
        current_designation = (
            frappe.db.get_value("Employee", self.employee, "designation") if self.employee else None
        )
        name = f"{self.employee} - {current_designation} to {self.new_designation} - {effective_date}"
        self.name = _clean(name)

        if frappe.db.exists(self.doctype, self.name):
            frappe.throw(
                f"Duplicate record: a Status Change Form already exists for "
                f"{self.employee} from {current_designation} to {self.new_designation} on {effective_date}."
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

        # Company/Letterhead were missing entirely until now, so a Status
        # Change Form always printed with the site's default Letter Head
        # instead of the Employee's own Company's - see
        # ir.patches.backfill_status_change_form_company_letter_head for the
        # retroactive fix on already-submitted records.
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

        self._rebuild_status_change_details(current_designation, current_branch)

    def _rebuild_status_change_details(self, current_designation, current_branch):
        """current_designation/current_branch used to be their own stored,
        read-only fields - now that Status Change Detail exists, they (and
        every other current_*/new_* pair) are represented as rows there
        instead, built the exact same way - and from the exact same source
        data - as the one-off historic backfill
        (ir.patches.backfill_status_change_detail_from_legacy_fields), just
        run live on every save rather than once. Fully rebuilt from scratch
        each time rather than merged, matching how current_designation/
        current_branch were themselves unconditionally recomputed on every
        validate() before this - so any manual edit made directly to this
        table will not survive the next save."""
        source = {
            "current_designation": current_designation,
            "new_designation": self.new_designation,
            "current_branch": current_branch,
            "new_branch": self.new_branch,
            "current_conditions": self.current_conditions,
            "new_conditions": self.new_conditions,
            "current_rate": self.current_rate,
            "new_rate": self.new_rate,
            "current_travel": self.current_travel,
            "new_travel": self.new_travel,
            "current_housing": self.current_housing,
            "new_housing": self.new_housing,
            "current_safety": self.current_safety,
            "new_safety": self.new_safety,
            "current_shift": self.current_shift,
            "new_shift": self.new_shift,
            "current_phone": self.current_phone,
            "new_phone": self.new_phone,
            "current_opencast": self.current_opencast,
            "new_opencast": self.new_opencast,
        }
        self.set("status_change_details", [])
        for row in build_status_change_detail_rows(source):
            self.append("status_change_details", row)

    def before_submit(self):
        if not self.attach:
            frappe.throw("You must attach the signed status change form before submitting.")

    def on_submit(self):
        """Touches Employee internal_work_history/designation/branch only for whichever of
        designation or branch actually changed - driven by the Designation/Branch rows in
        status_change_details (built in validate(), the single authoritative record of what
        this form actually changes) rather than re-deriving the same comparison independently
        here a second time."""
        if not self.employee:
            frappe.throw("Employee is required.")
        if not self.effective_date:
            frappe.throw("Effective Date is required.")
        if not self.new_designation:
            frappe.throw("New Designation is required.")

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

        # Employee.designation/branch are updated only after the child table save above, in a second save.
        if designation_changed:
            emp.designation = new_desig
        if branch_changed:
            emp.branch = new_branch
        emp.save(ignore_permissions=True)
