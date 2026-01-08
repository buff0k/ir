// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Site Organogram"] = {
    "filters": [
        {
            "fieldname": "site_organogram",
            "label": "Site Organogram",
            "fieldtype": "Link",
            "options": "Site Organogram",
            "reqd": 1
        }
    ]
};
