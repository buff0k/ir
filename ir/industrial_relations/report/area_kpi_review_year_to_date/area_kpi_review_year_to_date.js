// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Area KPI Review Year To Date"] = {
    "filters": [
        {
            "fieldname": "year",
            "label": "Year",
            "fieldtype": "Int",
            "default": new Date().getFullYear(),
            "reqd": 1
        },
        {
            "fieldname": "area",
            "label": "Area",
            "fieldtype": "Link",
            "options": "Area Setup"
        },
        {
            "fieldname": "kpi_template",
            "label": "KPI Template",
            "fieldtype": "Link",
            "options": "KPI Template"
        }
    ],

    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && data.is_group) {
            value = `<b>${value}</b>`;
        }
        return value;
    }
};
