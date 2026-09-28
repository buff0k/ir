// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Contract Type", {
    onload: function(frm) {
        if (frm.is_new() && frm.doc.contract_terms.length <= 1) {
            mandatory_contract_terms(frm);
        }
    }
});

function mandatory_contract_terms(frm) {
    let row1 = frm.add_child('contract_terms');
    row1.sec_no = 4;
    row1.section = 'Remuneration Placeholder';

    let row2 = frm.add_child('contract_terms');
    row2.sec_no = 6;
    row2.section = 'Working Hours Placeholder';

    frm.refresh_field('contract_terms');
}