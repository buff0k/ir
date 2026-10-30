# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class ContractType(Document):
    def validate(self):
        # Define the required sections
        required_sections = {
            "Working Hours Placeholder": False,
            "Remuneration Placeholder": False
        }
        
        # Check if each required section is present exactly once
        for row in self.contract_terms:
            if row.section in required_sections:
                if required_sections[row.section]:
                    # If already marked as True, it means there are duplicates
                    frappe.throw(f"Duplicate entry found for section '{row.section}'")
                required_sections[row.section] = True
        
        # Check for any missing sections
        missing_sections = [section for section, present in required_sections.items() if not present]
        if missing_sections:
            missing_sections_str = ', '.join(missing_sections)
            frappe.throw(f"Missing required rows in the child table: {missing_sections_str}")
