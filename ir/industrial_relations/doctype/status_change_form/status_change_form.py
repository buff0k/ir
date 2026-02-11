# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import formatdate

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

class StatusChangeForm(Document):
    def autoname(self):
        effective_date = formatdate(self.effective_date, "dd-MM-yyyy") if self.effective_date else ""
        name = f"{self.employee} - {self.current_designation} to {self.new_designation} - {effective_date}"
        self.name = _clean(name)

        # Duplicate check
        if frappe.db.exists(self.doctype, self.name):
            frappe.throw(
                f"Duplicate record: a Status Change Form already exists for "
                f"{self.employee} from {self.current_designation} to {self.new_designation} on {effective_date}."
            )

    def validate(self):
        """Server-side autopopulation (covers UI + API/import)."""

        # requested_by -> requested_by_name, requested_by_designation
        if self.requested_by:
            vals = frappe.db.get_value(
                "Employee",
                self.requested_by,
                ["employee_name", "designation"],
                as_dict=True
            ) or {}
            self.requested_by_name = vals.get("employee_name")
            self.requested_by_designation = vals.get("designation")

        # employee -> employee_name + current_designation
        if self.employee:
            vals = frappe.db.get_value(
                "Employee",
                self.employee,
                ["employee_name", "designation"],
                as_dict=True
            ) or {}
            self.employee_name = vals.get("employee_name")
            self.current_designation = vals.get("designation")

    def before_submit(self):
        if not self.attach:
            frappe.throw("You must attach the signed status change form before submitting.")

    def on_submit(self):
        """
        Update Employee internal_work_history only if designation actually changes.
        Branch remains unchanged; we scope change around designation.
        """
        if not self.employee:
            frappe.throw("Employee is required.")
        if not self.effective_date:
            frappe.throw("Effective Date is required.")
        if not self.new_designation:
            frappe.throw("New Designation is required.")

        emp = frappe.get_doc("Employee", self.employee)

        current_desig = getattr(emp, "designation", None)
        new_desig = self.new_designation

        # If designation does not change: do nothing to Employee/history
        if (current_desig or "") == (new_desig or ""):
            return

        history = emp.get("internal_work_history") or []

        def get_latest_row(rows):
            if not rows:
                return None
            with_from = [r for r in rows if getattr(r, "from_date", None)]
            if with_from:
                return sorted(with_from, key=lambda r: r.from_date)[-1]
            return rows[-1]

        if not history:
            # Create an initial row reflecting current state up to the effective date
            emp.append("internal_work_history", {
                "branch": getattr(emp, "branch", None),
                "department": getattr(emp, "department", None),
                "designation": current_desig,
                "from_date": getattr(emp, "date_of_joining", None),
                "to_date": self.effective_date,
            })
            prev_branch = getattr(emp, "branch", None)
            prev_department = getattr(emp, "department", None)
        else:
            latest = get_latest_row(history)
            if not latest:
                frappe.throw("Could not determine latest internal work history record.")

            # Close off the latest row
            latest.to_date = self.effective_date

            # Carry forward branch/department from latest (fallback to Employee if missing)
            prev_branch = getattr(latest, "branch", None) or getattr(emp, "branch", None)
            prev_department = getattr(latest, "department", None) or getattr(emp, "department", None)

        # Add the new row with updated designation; branch unchanged
        emp.append("internal_work_history", {
            "branch": prev_branch,
            "department": prev_department,
            "designation": new_desig,
            "from_date": self.effective_date,
            "to_date": None,
        })

        # Save child table updates first
        emp.save(ignore_permissions=True)

        # Then update Employee.designation (tracked change) and save again
        emp.designation = new_desig
        emp.save(ignore_permissions=True)
