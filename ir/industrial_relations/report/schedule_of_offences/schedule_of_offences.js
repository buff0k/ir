// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.query_reports["Schedule of Offences"] = {
    filters: [],

    onload: function(report) {
        // Ensure report refreshes automatically on load
        report.refresh();

        // Explicitly disable index column with Datatable options
        report.datatable.datamanager.showIndexColumn = false;
        report.datatable.refresh();

        // Add CSS to hide index column elements
        frappe.utils.add_custom_style(`
            .dt-cell--index, .dt-cell--index-header, 
            .dt-row-index, .dt-row-index-header {
                display: none !important;
            }
            @media print {
                .dt-cell--index, .dt-cell--index-header, 
                .dt-row-index, .dt-row-index-header {
                    display: none !important;
                }
            }
        `);
    },

    refresh: function() {
        setTimeout(() => {
            // Style the header rows to be bold and centered across all columns
            $('.header-row').closest('tr').css({
                "font-weight": "bold",
                "text-align": "center",
                "background-color": "#f0f0f0"
            }).children('td').attr('colspan', 6);  // Adjust colspan to match columns
        }, 100);
    }
};
