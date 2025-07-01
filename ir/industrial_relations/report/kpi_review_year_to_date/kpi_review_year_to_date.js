// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["KPI Review Year To Date"] = {
    "filters": [
        {
            fieldname: "year",
            label: "Year",
            fieldtype: "Int",
            default: new Date().getFullYear(),
            reqd: 1
        },
        {
            fieldname: "site",
            label: "Site",
            fieldtype: "Link",
            options: "Branch"
        },
        {
            fieldname: "kpi_template",
            label: "KPI Template",
            fieldtype: "Link",
            options: "KPI Template"
        }
    ],
    "formatter": function(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "avg_percentage" && value) {
            return value + " %";
        }
        return value;
    }
};