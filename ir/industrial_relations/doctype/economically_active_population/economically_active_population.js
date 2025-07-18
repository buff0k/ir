// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Economically Active Population', {
    african_male: function(frm) {
        if (frm.doc.african_male !== undefined) {
            update_total(frm);
        }
    },
    african_female: function(frm) {
        if (frm.doc.african_female !== undefined) {
            update_total(frm);
        }
    },
    coloured_male: function(frm) {
        if (frm.doc.coloured_male !== undefined) {
            update_total(frm);
        }
    },
    coloured_female: function(frm) {
        if (frm.doc.coloured_female !== undefined) {
            update_total(frm);
        }
    },
    indian_male: function(frm) {
        if (frm.doc.indian_male !== undefined) {
            update_total(frm);
        }
    },
    indian_female: function(frm) {
        if (frm.doc.indian_female !== undefined) {
            update_total(frm);
        }
    },
    white_male: function(frm) {
        if (frm.doc.white_male !== undefined) {
            update_total(frm);
        }
    },
    white_female: function(frm) {
        if (frm.doc.white_female !== undefined) {
            update_total(frm);
        }
    },

    onload_post_render: function(frm) {
        update_total(frm);
    },

    validate: function(frm) {
        if (flt(frm.doc.total) > 100) {
            frappe.throw(__('Total cannot exceed 100%'));
        }
    }
});

function update_total(frm) {
    let total = 0;

    total += flt(frm.doc.african_male);
    total += flt(frm.doc.african_female);
    total += flt(frm.doc.coloured_male);
    total += flt(frm.doc.coloured_female);
    total += flt(frm.doc.indian_male);
    total += flt(frm.doc.indian_female);
    total += flt(frm.doc.white_male);
    total += flt(frm.doc.white_female);

    frm.set_value('total', total.toFixed(2));
}
