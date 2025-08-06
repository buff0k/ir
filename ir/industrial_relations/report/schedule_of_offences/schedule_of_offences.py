# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import re
import frappe

def execute(filters=None):
    columns, data = [], []

    # Define the columns, with `name` as `Data` to simplify header styling
    columns = [
        {"fieldname": "name", "label": "Document Name", "fieldtype": "Data", "width": 150},
        {"fieldname": "offence_description", "label": "Offence Description and Notes", "fieldtype": "Data", "width": 300},
        {"fieldname": "sanction_on_first_offence", "label": "First Offence Sanction", "fieldtype": "Data", "width": 150},
        {"fieldname": "sanction_on_second_offence", "label": "Second Offence Sanction", "fieldtype": "Data", "width": 150},
        {"fieldname": "sanction_on_third_offence", "label": "Third Offence Sanction", "fieldtype": "Data", "width": 150},
        {"fieldname": "sanction_on_fourth_offence", "label": "Fourth Offence Sanction", "fieldtype": "Data", "width": 150}
    ]

    offences = frappe.get_all(
        "Disciplinary Offence", 
        fields=["name", "category_of_offence", "offence_description", "notes", 
                "sanction_on_first_offence", "sanction_on_second_offence", 
                "sanction_on_third_offence", "sanction_on_fourth_offence"]
    )

    def natural_sort_key(value):
        return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', value)]

    offences = sorted(offences, key=lambda x: (x["category_of_offence"], natural_sort_key(x["name"])))

    current_category = None
    for offence in offences:
        # Insert category as a header row in `offence_description`
        if offence.category_of_offence != current_category:
            category_desc = frappe.get_value("Offence Category", offence.category_of_offence, "disc_cat_desc")
            data.append({
                "name": "",  # Leave name blank
                "offence_description": "<b>{}</b>".format(category_desc),  # Place header in this field
                "sanction_on_first_offence": "",
                "sanction_on_second_offence": "",
                "sanction_on_third_offence": "",
                "sanction_on_fourth_offence": "",
                "is_header": 1  # Indicate header row
            })
            current_category = offence.category_of_offence

        # Retrieve outcomes and format offence description
        first_offence_outcome = frappe.get_value("Offence Outcome", offence.sanction_on_first_offence, "disc_offence_out") or ""
        second_offence_outcome = frappe.get_value("Offence Outcome", offence.sanction_on_second_offence, "disc_offence_out") or ""
        third_offence_outcome = frappe.get_value("Offence Outcome", offence.sanction_on_third_offence, "disc_offence_out") or ""
        fourth_offence_outcome = frappe.get_value("Offence Outcome", offence.sanction_on_fourth_offence, "disc_offence_out") or ""

        offence_description = offence.offence_description
        if offence.notes:
            offence_description += "<br><i>{}</i>".format(offence.notes)

        # Add regular row
        data.append({
            "name": offence.name,
            "offence_description": offence_description,
            "sanction_on_first_offence": first_offence_outcome,
            "sanction_on_second_offence": second_offence_outcome,
            "sanction_on_third_offence": third_offence_outcome,
            "sanction_on_fourth_offence": fourth_offence_outcome,
            "is_header": 0  # Regular row
        })

    return columns, data
