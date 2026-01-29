# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import markdownify
from markdownify import markdownify as md

def execute():
    """Convert existing HTML Text Editor content to Markdown for Disciplinary Outcome Report"""
    fields_to_convert = [
        "introduction", "complainant_case", "accused_case", "analysis_of_evidence",
        "finding", "mitigating_considerations", "aggravating_conisderations", "outcome"
    ]
    
    # Fetch all the reports
    reports = frappe.get_all("Disciplinary Outcome Report", fields=["name"] + fields_to_convert)
    
    for report in reports:
        for field in fields_to_convert:
            if report.get(field):  # Ensure there's content to convert
                # Convert HTML content to Markdown using markdownify
                markdown_content = md(report.get(field))
                
                # Perform a direct database update for each field
                frappe.db.set_value("Disciplinary Outcome Report", report.name, field, markdown_content)
        
        # Commit the changes immediately after updating the record
        frappe.db.commit()
    
    print("✅ Converted all Rich Text fields to Markdown in Disciplinary Outcome Report")