# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import formatdate, getdate, nowdate


class TerminationForm(Document):
    """
    Updates the linked Employee record on:
      - create (after_insert)
      - save (validate / on_update while draft)
      - submit (on_submit) - the final update from this specific form;
        termination_date/notice_ends never change after Submit

    Rules:
      1) relieving_date = later of termination_date and notice_ends
      2) if relieving_date is in the past => Employee.status = "Left", else "Active"
      3) before setting to "Left", clear reports_to on any employees whose manager-chain leads to this employee
      4) Employee.reason_for_leaving (Small Text) gets the *text* of Reason for Termination (Link)
         - clear then set

    While a form is a Draft (e.g. waiting on a Payroll-signed copy to come
    back before it can be Submitted), termination_date/notice_ends can be
    corrected any number of times, each save recomputing Status/Relieving
    Date from scratch - see _sync_employee_updates()'s no-op-if-unchanged
    guard, which is what actually matters here: it keeps the Employee record
    accurate through any number of corrections in either direction (a date
    pushed into the future flips Left back to Active, same as a date pulled
    into the past flips Active to Left), without touching the Employee at
    all when nothing actually needs to change.

    Naming: name = the Employee (Coy No), not a bare rigid field:doc_name link -
    an employee terminated and rehired within 4 months keeps their original
    Employee record (per za_local's rehire rules), so a second, genuinely
    different Termination Form for the same Employee is a real, valid case,
    not a data error. append_number_if_name_exists() suffixes -1, -2, ... on
    a name collision, the same style Frappe's own amend workflow uses -
    _guard_against_duplicate() below is what actually stops true duplicates
    (same Employee *and* same Termination Date), not the bare name clashing.
    """

    def autoname(self):
        if not self.requested_for:
            # Let the standard mandatory-field validation (requested_for is
            # reqd=1) catch this with a clear message rather than naming off
            # an empty value here - naming runs before that validation.
            return
        self.name = append_number_if_name_exists(self.doctype, self.requested_for)

    def after_insert(self):
        self._sync_employee_updates(stage="create")

    def validate(self):
        self._guard_against_duplicate()

        # validate runs on save and also during submit, but we only want the "save stage" logic here
        if self.docstatus == 0:
            self._sync_employee_updates(stage="save")

    def on_update(self):
        # extra safety: if any flows bypass validate, keep in sync during draft updates
        if self.docstatus == 0:
            self._sync_employee_updates(stage="save")

    def on_submit(self):
        self._sync_employee_updates(stage="submit", show_message=True)

    def _guard_against_duplicate(self):
        """
        Naming alone (see autoname()) no longer prevents duplicates - it now
        deliberately allows a second Termination Form for the same Employee
        (a genuine rehire-then-terminate-again case). What still shouldn't
        happen is two forms for the same Employee *and* the same Termination
        Date - that's the same event entered twice. Cancelled forms are
        excluded: a cancelled form is void, so re-entering the same
        Employee/date afterwards is not a duplicate.
        """
        if not self.requested_for or not self.termination_date:
            return

        duplicate = frappe.db.exists(
            self.doctype,
            {
                "requested_for": self.requested_for,
                "termination_date": self.termination_date,
                "docstatus": ["!=", 2],
                "name": ["!=", self.name or ""],
            },
        )
        if duplicate:
            frappe.throw(
                frappe._(
                    "A Termination Form already exists for {0} with Termination Date {1}: {2}."
                ).format(self.requested_for, formatdate(self.termination_date), duplicate),
                frappe.DuplicateEntryError,
                title=frappe._("Duplicate Termination Form"),
            )

    # -------------------------
    # Core logic
    # -------------------------

    def _sync_employee_updates(self, stage: str, show_message: bool = False) -> bool:
        """
        Recomputes what the linked Employee's status/relieving_date/
        reason_for_leaving should be *right now*, from this form's current
        field values, and writes them to the Employee record only if
        something actually needs to change. Safe (and cheap) to call on
        every Draft save and again on Submit - a Termination Form can sit in
        Draft for a while with its dates corrected more than once before the
        Payroll-signed copy comes back, and each such save recomputes from
        scratch: if Status and Relieving Date already match what this form
        currently implies, there's nothing to do (no Employee save, no
        reports_to walk, no message). If they don't match - e.g. Status is
        "Left" but notice_ends was just pushed into the future - the Employee
        record is brought back in line, in either direction. Returns True if
        the Employee record was actually updated.
        """
        if not self.requested_for:
            return False

        relieving_date = self._get_effective_relieving_date()
        if not relieving_date:
            # If termination_date is missing, let standard validation handle it (especially on submit).
            return False

        today = getdate(nowdate())
        should_be_left = relieving_date < today  # strictly "in the past"
        new_status = "Left" if should_be_left else "Active"
        reason_text = self._get_reason_text()

        employee = frappe.get_doc("Employee", self.requested_for)

        current_relieving_date = getdate(employee.relieving_date) if employee.relieving_date else None
        if (
            employee.status == new_status
            and current_relieving_date == relieving_date
            and (employee.reason_for_leaving or "") == reason_text
        ):
            return False

        # 4) reason_for_leaving (Small Text) should receive the text value of the Link
        employee.reason_for_leaving = reason_text

        # 1) set relieving_date always to the effective date
        employee.relieving_date = relieving_date

        # 2) status depends on whether relieving_date is in the past
        if should_be_left:
            # 3) before setting to Left, clear reports_to for anyone pointing (directly or indirectly) to this employee
            self._clear_reports_to_chain_for_terminated_employee(self.requested_for)
        employee.status = new_status

        # Save Employee
        employee.save(ignore_permissions=True)

        if show_message:
            frappe.msgprint(
                frappe._(
                    "Employee {0} updated: status set to <b>{1}</b>, relieving date set to <b>{2}</b>."
                ).format(employee.name, employee.status, relieving_date.strftime("%Y-%m-%d")),
                alert=True,
            )

        return True

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

        # Clear reports_to for affected employees - through a real .save(),
        # not a raw frappe.db.set_value(), so the change actually shows up on
        # each employee's own Version/audit trail. Employee isn't a
        # submittable doctype, so there's no docstatus complication that
        # would force a direct DB write the way there sometimes is elsewhere.
        for emp_name in set(to_clear):
            emp_doc = frappe.get_doc("Employee", emp_name)
            emp_doc.reports_to = None
            emp_doc.save(ignore_permissions=True)
