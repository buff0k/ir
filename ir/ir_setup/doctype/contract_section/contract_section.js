// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contract Section', {
    refresh: function(frm) {
        frm.fields_dict['sec_par'].grid.wrapper.on('change', 'input[data-fieldname]', function() {
            update_reference(frm);
        });
    }
});

function update_reference(frm) {
    frm.doc.sec_par.forEach(function(row) {
        let reference = "X.";
        let values = [];

        values.push(row.ss_num > 0 ? row.ss_num : 0);
        values.push(row.par_num > 0 ? row.par_num : 0);
        values.push(row.spar_num > 0 ? row.spar_num : 0);
        values.push(row.item_num > 0 ? row.item_num : 0);
        values.push(row.sitem_num > 0 ? row.sitem_num : 0);

        while (values.length > 0 && values[values.length - 1] === 0) {
            values.pop();
        }

        reference += values.map(v => v.toString()).join('.');

        frappe.model.set_value(row.doctype, row.name, 'reference', reference);
    });

    frm.refresh_field('sec_par');
}
