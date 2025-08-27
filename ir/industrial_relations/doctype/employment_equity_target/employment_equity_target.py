# Copyright (c) 2025
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

EE_CHILD = "Employment Equity Table"
GROUP_FIELDS = [
    "african_male", "coloured_male", "indian_male", "white_male",
    "african_female", "coloured_female", "indian_female", "white_female",
    "foreign_male", "foreign_female",
]

class EmploymentEquityTarget(Document):
    def before_save(self):
        """Server-side safety:
        - Ensure totals are correct even if client JS didn't run.
        - Ensure a row exists for each Occupational Level (defensive backstop).
        """
        # Ensure a row exists for every Occupational Level
        level_names = [x.name for x in frappe.get_all("Occupational Level")]
        existing = {row.occupational_level for row in (self.employment_equity_table or [])}

        for lvl in level_names:
            if lvl not in existing:
                row = self.append("employment_equity_table", {})
                row.occupational_level = lvl
                for f in GROUP_FIELDS:
                    setattr(row, f, 0)
                row.total = 0

        # Recompute totals
        for row in (self.employment_equity_table or []):
            row.total = sum(int(getattr(row, f) or 0) for f in GROUP_FIELDS)

@frappe.whitelist()
def compute_suggested_targets(docname: str):
    """Placeholder for future EAP-based logic."""
    if not docname:
        frappe.throw("Missing docname.")
    doc = frappe.get_doc("Employment Equity Target", docname)
    return f"Placeholder OK for {doc.name}. Implement EAP-based logic server-side next."
