# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe
from frappe.model.document import Document
from frappe.utils import formatdate

from ir.industrial_relations.utils import fetch_company_letter_head

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

class StatusChangeForm(Document):
    def autoname(self):
        effective_date = formatdate(self.effective_date, "dd-MM-yyyy") if self.effective_date else ""
        name = f"{self.employee} - {self.current_designation} to {self.new_designation} - {effective_date}"
        self.name = _clean(name)

        if frappe.db.exists(self.doctype, self.name):
            frappe.throw(
                f"Duplicate record: a Status Change Form already exists for "
                f"{self.employee} from {self.current_designation} to {self.new_designation} on {effective_date}."
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

        # Company/Letterhead were missing entirely until now, so a Status
        # Change Form always printed with the site's default Letter Head
        # instead of the Employee's own Company's - see
        # ir.patches.backfill_status_change_form_company_letter_head for the
        # retroactive fix on already-submitted records.
        if self.employee:
            vals = frappe.db.get_value(
                "Employee",
                self.employee,
                ["employee_name", "designation", "company"],
                as_dict=True
            ) or {}
            self.employee_name = vals.get("employee_name")
            self.current_designation = vals.get("designation")
            self.company = vals.get("company")
            self.letter_head = fetch_company_letter_head(self.company).get("letter_head") if self.company else None

    def before_submit(self):
        if not self.attach:
            frappe.throw("You must attach the signed status change form before submitting.")

    def on_submit(self):
        """Only touches Employee internal_work_history if designation actually changes; branch is left as-is."""
        if not self.employee:
            frappe.throw("Employee is required.")
        if not self.effective_date:
            frappe.throw("Effective Date is required.")
        if not self.new_designation:
            frappe.throw("New Designation is required.")

        emp = frappe.get_doc("Employee", self.employee)

        current_desig = getattr(emp, "designation", None)
        new_desig = self.new_designation

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

            latest.to_date = self.effective_date

            prev_branch = getattr(latest, "branch", None) or getattr(emp, "branch", None)
            prev_department = getattr(latest, "department", None) or getattr(emp, "department", None)

        emp.append("internal_work_history", {
            "branch": prev_branch,
            "department": prev_department,
            "designation": new_desig,
            "from_date": self.effective_date,
            "to_date": None,
        })

        emp.save(ignore_permissions=True)

        # Employee.designation is updated only after the child table save above, in a second save.
        emp.designation = new_desig
        emp.save(ignore_permissions=True)
