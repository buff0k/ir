"""
South African Salary Structure Assignment Override

This module fixes the validation logic for opening entries to correctly handle
zero values. The original HRMS code treats 0 as falsy, causing warnings even
when values are explicitly set to zero.

ir requires HRMS (required_apps in hooks.py), so it is always installed here.
"""

import frappe
from frappe import _
from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import (
    SalaryStructureAssignment,
)


class ZASalaryStructureAssignment(SalaryStructureAssignment):
    """
    South African Salary Structure Assignment implementation.

    Fixes the opening entries validation to correctly distinguish between
    unset values (None) and explicitly set zero values.
    """

    def warn_about_missing_opening_entries(self):
        """
        Override to fix validation: check for None instead of falsy values.

        The original implementation treats 0 as falsy, causing warnings
        even when values are explicitly set to zero. This fix checks if
        values are None (not set) rather than checking if they're falsy.
        """
        if (
            self.are_opening_entries_required()
            and self.taxable_earnings_till_date is None
            and self.tax_deducted_till_date is None
        ):
            msg = _(
                "Please specify {0} and {1} (if any), for the correct tax calculation in future salary slips."
            ).format(
                frappe.bold(_("Taxable Earnings Till Date")),
                frappe.bold(_("Tax Deducted Till Date")),
            )
            frappe.msgprint(
                msg,
                indicator="orange",
                title=_("Missing Opening Entries"),
            )

