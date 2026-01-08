// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contract Section', {
    refresh: function(frm) {
        // Monitor changes in the child table fields
        frm.fields_dict['sec_par'].grid.wrapper.on('change', 'input[data-fieldname]', function() {
            update_reference(frm);
        });
    }
});

function update_reference(frm) {
    frm.doc.sec_par.forEach(function(row) {
        let reference = "X."; // Start with 'X.'
        let values = [];

        // Collect values based on the hierarchy
        values.push(row.ss_num > 0 ? row.ss_num : 0);
        values.push(row.par_num > 0 ? row.par_num : 0);
        values.push(row.spar_num > 0 ? row.spar_num : 0);
        values.push(row.item_num > 0 ? row.item_num : 0);
        values.push(row.sitem_num > 0 ? row.sitem_num : 0);

        // Remove trailing zeros
        while (values.length > 0 && values[values.length - 1] === 0) {
            values.pop();
        }

        // Build the reference string
        reference += values.map(v => v.toString()).join('.');

        // Update the reference field in the child table
        frappe.model.set_value(row.doctype, row.name, 'reference', reference);
    });

    // Refresh the child table to reflect changes
    frm.refresh_field('sec_par');
}
