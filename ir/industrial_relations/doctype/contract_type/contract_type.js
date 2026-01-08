// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Type", {
    onload: function(frm) {
        // Call the function to populate the child table on form load
        if (frm.is_new() && frm.doc.contract_terms.length <= 1) {
            mandatory_contract_terms(frm);
        }
    }
});

// Function to populate the child table
function mandatory_contract_terms(frm) {
    // Add the first row: Remuneration Placeholder
    let row1 = frm.add_child('contract_terms');
    row1.sec_no = 4;
    row1.section = 'Remuneration Placeholder';

    // Add the second row: Working Hours Placeholder
    let row2 = frm.add_child('contract_terms');
    row2.sec_no = 6;
    row2.section = 'Working Hours Placeholder';

    // Refresh the child table to display the new rows
    frm.refresh_field('contract_terms');
}