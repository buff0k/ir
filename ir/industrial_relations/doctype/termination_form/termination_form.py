# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class TerminationForm(Document):
    """
    Updates the linked Employee record on:
      - create (after_insert)
      - save (validate / on_update while draft)
      - submit (on_submit)

    Rules:
      1) relieving_date = later of termination_date and notice_ends
      2) if relieving_date is in the past => Employee.status = "Left", else "Active"
      3) before setting to "Left", clear reports_to on any employees whose manager-chain leads to this employee
      4) Employee.reason_for_leaving (Small Text) gets the *text* of Reason for Termination (Link)
         - clear then set
    """

    def after_insert(self):
        self._sync_employee_updates(stage="create")

    def validate(self):
        # validate runs on save and also during submit, but we only want the "save stage" logic here
        if self.docstatus == 0:
            self._sync_employee_updates(stage="save")

    def on_update(self):
        # extra safety: if any flows bypass validate, keep in sync during draft updates
        if self.docstatus == 0:
            self._sync_employee_updates(stage="save")

    def on_submit(self):
        self._sync_employee_updates(stage="submit", show_message=True)

    # -------------------------
    # Core logic
    # -------------------------

    def _sync_employee_updates(self, stage: str, show_message: bool = False):
        """
        Applies the rules described above. Safe to call multiple times (idempotent).
        """
        if not self.requested_for:
            return

        relieving_date = self._get_effective_relieving_date()
        if not relieving_date:
            # If termination_date is missing, let standard validation handle it (especially on submit).
            return

        today = getdate(nowdate())
        should_be_left = relieving_date < today  # strictly "in the past"

        employee = frappe.get_doc("Employee", self.requested_for)

        # 4) reason_for_leaving (Small Text) should receive the text value of the Link
        reason_text = self._get_reason_text()
        employee.reason_for_leaving = ""  # clear first as requested
        if reason_text:
            employee.reason_for_leaving = reason_text

        # 1) set relieving_date always to the effective date
        employee.relieving_date = relieving_date

        # 2) status depends on whether relieving_date is in the past
        if should_be_left:
            # 3) before setting to Left, clear reports_to for anyone pointing (directly or indirectly) to this employee
            self._clear_reports_to_chain_for_terminated_employee(self.requested_for)
            employee.status = "Left"
        else:
            employee.status = "Active"

        # Save Employee
        employee.save(ignore_permissions=True)

        if show_message:
            frappe.msgprint(
                frappe._(
                    "Employee {0} updated: status set to <b>{1}</b>, relieving date set to <b>{2}</b>."
                ).format(employee.name, employee.status, relieving_date.strftime("%Y-%m-%d")),
                alert=True,
            )

    def _get_effective_relieving_date(self):
        """
        Returns the later of termination_date and notice_ends (if notice_ends is present).
        """
        if not self.termination_date:
            return None

        t_date = getdate(self.termination_date)
        if self.notice_ends:
            n_date = getdate(self.notice_ends)
            return max(t_date, n_date)

        return t_date

    def _get_reason_text(self) -> str:
        """
        reason is a Link to 'Reason for Termination'. We want a plain text value.
        Safest approach: use the linked doc's title/name; if there's a 'reason' field, prefer it.
        """
        if not self.reason:
            return ""

        # Prefer a common "reason" field if present, otherwise fall back to the document name (which is what the Link stores).
        try:
            val = frappe.db.get_value("Reason for Termination", self.reason, "reason")
            if val:
                return str(val).strip()
        except Exception:
            pass

        return str(self.reason).strip()

    # -------------------------
    # Reports_to chain clearing
    # -------------------------

    @staticmethod
    def _clear_reports_to_chain_for_terminated_employee(terminated_employee: str):
        """
        Recursively scans all Employee.reports_to chains.
        If ANY employee's manager chain leads back to terminated_employee,
        clear that employee's reports_to (set to NULL/empty).
        """
        if not terminated_employee:
            return

        # Build map of employee -> reports_to for all employees that have a manager set
        rows = frappe.get_all(
            "Employee",
            fields=["name", "reports_to"],
            filters={"reports_to": ["!=", ""]},
            limit_page_length=0,
        )
        reports_to_map = {r["name"]: r.get("reports_to") for r in rows}

        to_clear = []

        for emp_name in reports_to_map.keys():
            if emp_name == terminated_employee:
                continue

            visited = set()
            current = emp_name

            # Walk up the chain: emp -> manager -> manager's manager -> ...
            while True:
                if current in visited:
                    # cycle protection
                    break
                visited.add(current)

                manager = reports_to_map.get(current)
                if not manager:
                    break

                if manager == terminated_employee:
                    to_clear.append(emp_name)
                    break

                # continue upwards
                current = manager

        if not to_clear:
            return

        # Clear reports_to for affected employees
        for emp_name in set(to_clear):
            frappe.db.set_value(
                "Employee",
                emp_name,
                "reports_to",
                None,
                update_modified=False,
            )

        frappe.db.commit()
