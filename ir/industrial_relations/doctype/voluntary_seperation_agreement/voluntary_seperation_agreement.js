// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Voluntary Seperation Agreement", {
    refresh: function(frm) {
        // Check the flags before triggering the handler
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        } else if (frm.doc.linked_incapacity_proceeding && !frm.doc.linked_incapacity_proceeding_processed) {
            frm.trigger('linked_incapacity_proceeding');
        }
    },

    linked_disciplinary_action: function(frm) {
        if (frm.doc.linked_disciplinary_action) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.fetch_disciplinary_action_data',
                args: {
                    disciplinary_action: frm.doc.linked_disciplinary_action
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;

                        // Directly update the doc and refresh fields without triggering events
                        frm.doc.employee = data.accused || '';
                        frm.doc.names = data.accused_name || '';
                        frm.doc.coy = data.accused_coy || '';
                        frm.doc.position = data.accused_pos || '';
                        frm.doc.company = data.company || '';

                        frm.refresh_field('employee');
                        frm.trigger('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');
                        // Set the flag to prevent refresh loop
                        frm.set_value('linked_disciplinary_action_processed', true);
                    }
                }
            });
        }
    },

    linked_incapacity_proceeding: function(frm) {
        if (frm.doc.linked_incapacity_proceeding) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.fetch_incapacity_proceeding_data',
                args: {
                    incapacity_proceeding: frm.doc.linked_incapacity_proceeding
                },
                callback: function(r) {
                    if (r.message) {
                        const data = r.message;

                        // Directly update the doc and refresh fields without triggering events
                        frm.doc.employee = data.accused || '';
                        frm.doc.names = data.accused_name || '';
                        frm.doc.coy = data.accused_coy || '';
                        frm.doc.position = data.accused_pos || '';
                        frm.doc.company = data.company || '';

                        frm.refresh_field('employee');
                        frm.trigger('employee');
                        frm.refresh_field('names');
                        frm.refresh_field('coy');
                        frm.refresh_field('position');
                        frm.refresh_field('company');
                        // Set the flag to prevent refresh loop
                        frm.set_value('linked_incapacity_proceeding_processed', true);
                    }
                }
            });
        }
    },

    employee: function(frm) {
        if (frm.doc.employee) {
            frappe.db.get_doc('Employee', frm.doc.employee).then(doc => {
                frm.set_value('names', doc.employee_name || '');
                frm.set_value('coy', doc.employee || '');
                frm.set_value('position', doc.designation || '');
                frm.set_value('company', doc.company || '');
                frm.set_value('engagement_date', doc.date_of_joining || '');
                frm.set_value('custom_id_number', doc.custom_id_number || '');
            
                // Combine the current address lines into a single line
                const addressLines = (doc.current_address || '').split('\n').map(line => line.trim());
                const combinedAddress = addressLines.join(', '); // Use a comma and space as a separator
                frm.set_value('current_address', combinedAddress);
            });
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.call({
                method: 'ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.fetch_company_letter_head',
                args: {
                    company: frm.doc.company
                },
                callback: function(r) {
                    if (r.message) {
                        frm.doc.letter_head = r.message.letter_head || '';
                        frm.refresh_field('letter_head');
                    }
                }
            });
        }
    },

    before_submit: function(frm) {
        if (!frm.doc.signed_vsp) {
            frappe.msgprint(__('You cannot submit this document until you have attached a signed copy of the VSP'));
            frappe.validated = false;
        }
    }
});

function fetch_company_letter_head(frm, company) {
    if (company) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.fetch_company_letter_head',
            args: {
                company: company
            },
            callback: function(res) {
                if (res.message) {
                    frm.set_value('letter_head', res.message);
                } else {
                    frm.set_value('letter_head', '');
                }
            }
        });
    }
}

frappe.ui.form.on('VSP Items', {
    value: function(frm, cdt, cdn) {
        calculate_total(frm, cdt, cdn);
    }
});

function calculate_total(frm) {
    let total = 0;
    frm.doc.payment_details.forEach(row => {
        total += row.value;
    });
    frm.set_value('total_gross', total);
}