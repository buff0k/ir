# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import formatdate

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

class SiteTransferForm(Document):
    def autoname(self):
        transfer_date = formatdate(self.transfer_date, "dd-MM-yyyy") if self.transfer_date else ""
        name = f"{self.employee} - {self.current_branch} to {self.new_branch} - {transfer_date}"
        self.name = _clean(name)

        # Duplicate check
        if frappe.db.exists(self.doctype, self.name):
            frappe.throw(
                f"Duplicate record: a Site Transfer Form already exists for "
                f"{self.employee} from {self.current_branch} to {self.new_branch} on {transfer_date}."
            )

    def validate(self):
        """Server-side safety: always keep the derived fields in sync even if record is created via API/import."""
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

        # employee -> employee_name, designation, current_branch
        if self.employee:
            vals = frappe.db.get_value(
                "Employee",
                self.employee,
                ["employee_name", "designation", "branch"],
                as_dict=True
            ) or {}
            self.employee_name = vals.get("employee_name")
            self.designation = vals.get("designation")
            self.current_branch = vals.get("branch")

    def before_submit(self):
        # 1) Block submit if nothing attached
        if not self.attach:
            frappe.throw("You must attach the signed transfer form before submitting.")

    def on_submit(self):
        """
        4) Update Employee internal_work_history child table, then update Employee.branch.
        Uses Document API so changes are tracked (versions/audit trail).
        """
        if not self.employee:
            frappe.throw("Employee is required.")

        if not self.transfer_date:
            frappe.throw("Transfer Date is required.")

        if not self.new_branch:
            frappe.throw("New Branch is required.")

        emp = frappe.get_doc("Employee", self.employee)

        # Ensure child table exists
        history = emp.get("internal_work_history") or []

        # Helper: pick "latest" record (by from_date, else last row)
        def get_latest_row(rows):
            if not rows:
                return None
            with_from = [r for r in rows if getattr(r, "from_date", None)]
            if with_from:
                return sorted(with_from, key=lambda r: r.from_date)[-1]
            return rows[-1]

        if not history:
            # If no entries exist yet, create the initial row
            emp.append("internal_work_history", {
                "branch": emp.branch,
                "department": getattr(emp, "department", None),
                "designation": getattr(emp, "designation", None),
                "from_date": getattr(emp, "date_of_joining", None),
                "to_date": self.transfer_date,
            })
            prev_department = getattr(emp, "department", None)
            prev_designation = getattr(emp, "designation", None)
        else:
            # If a prior entry exists, update to_date on the latest record
            latest = get_latest_row(history)
            if not latest:
                frappe.throw("Could not determine latest internal work history record.")

            latest.to_date = self.transfer_date

            # Carry forward dept/designation from the latest row (as per your mapping)
            prev_department = getattr(latest, "department", None) or getattr(emp, "department", None)
            prev_designation = getattr(latest, "designation", None) or getattr(emp, "designation", None)

        # Create new row for the new branch
        emp.append("internal_work_history", {
            "branch": self.new_branch,
            "department": prev_department,
            "designation": prev_designation,
            "from_date": self.transfer_date,
            "to_date": None,
        })

        # First save: child table changes
        emp.save(ignore_permissions=True)

        # Only after saving child table: update Employee.branch and save again
        emp.branch = self.new_branch
        emp.save(ignore_permissions=True)
