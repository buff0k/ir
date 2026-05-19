// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Performance Improved', {
    refresh(frm) {
        if (frm.doc.linked_poor_performance && !frm.doc.linked_poor_performance_processed) {
            frm.trigger('linked_poor_performance');
        }
    },

    linked_poor_performance(frm) {
        if (!frm.doc.linked_poor_performance) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.performance_improved.performance_improved.fetch_poor_performance_data',
            args: { poor_performance: frm.doc.linked_poor_performance },
            callback(r) {
                const data = r.message || {};
                frm.doc.employee = data.employee || '';
                frm.doc.names = data.employee_name || '';
                frm.doc.coy = data.employee || '';
                frm.doc.position = data.employee_designation || '';
                frm.doc.company = data.company || '';
                frm.set_value('performance_details', data.details_of_poor_performance || '');
                ['employee', 'names', 'coy', 'position', 'company', 'performance_details'].forEach(f => frm.refresh_field(f));

                frm.clear_table('previous_performance_outcomes');
                (data.previous_performance_outcomes || []).forEach(row => {
                    let child = frm.add_child('previous_performance_outcomes');
                    child.performance_action = row.performance_action;
                    child.date = row.date;
                    child.charges = row.charges;
                    child.sanction = row.sanction;
                });
                frm.refresh_field('previous_performance_outcomes');

                frm.set_value('linked_poor_performance_processed', true);
            }
        });
    },

    company(frm) {
        if (!frm.doc.company) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.performance_improved.performance_improved.fetch_company_letter_head',
            args: { company: frm.doc.company },
            callback(r) {
                if (r.message) {
                    frm.doc.letter_head = r.message.letter_head || '';
                    frm.refresh_field('letter_head');
                }
            }
        });
    },

    before_save(frm) {
        if (frm.__confirmed_save) return;
        confirm_parent_outcome_change(frm, 'save');
    },

    before_submit(frm) {
        if (!frm.doc.signed_confirmation) {
            frappe.msgprint(__('You must attach the signed performance improvement confirmation before submitting.'));
            frappe.validated = false;
            return;
        }
        if (frm.__confirmed_submit) return;
        confirm_parent_outcome_change(frm, 'submit');
    }
});

function confirm_parent_outcome_change(frm, action) {
    const linked_doc_name = frm.doc.linked_poor_performance;
    const linked_doctype = 'Poor Performance';
    if (!linked_doc_name) return;

    frappe.call({
        method: 'ir.industrial_relations.doctype.performance_improved.performance_improved.get_linked_outcome',
        args: { doc_name: linked_doc_name, doctype: linked_doctype },
        callback(r) {
            const data = r.message || {};
            const outcome_str = data.outcome ? data.outcome.toString() : 'None';
            const outcome_date_str = data.outcome_date ? frappe.datetime.str_to_user(data.outcome_date) : 'None';

            if (!data.outcome && !data.outcome_date) {
                if (action === 'submit') {
                    frm.__confirmed_submit = true;
                    frm.save({ action: 'submit' });
                } else {
                    frm.__confirmed_save = true;
                    frappe.validated = true;
                    frm.save();
                }
                return;
            }

            const msg = action === 'submit'
                ? `The linked document ${linked_doc_name} (${linked_doctype}) currently has an outcome: ${outcome_str} and outcome date: ${outcome_date_str}. These will be overwritten with performance improved outcome: ${frm.doc.performance_improved_type} and outcome date: ${frm.doc.outcome_date}. Do you want to proceed?`
                : `The linked document ${linked_doc_name} (${linked_doctype}) currently has an outcome: ${outcome_str} and outcome date: ${outcome_date_str}. These will be cleared upon saving. Do you want to proceed?`;

            frappe.confirm(msg, function() {
                if (action === 'submit') {
                    frm.__confirmed_submit = true;
                    frm.save({ action: 'submit' });
                } else {
                    frm.__confirmed_save = true;
                    frappe.validated = true;
                    frm.save();
                }
            }, function() {
                frappe.msgprint(__(`${action === 'submit' ? 'Submit' : 'Save'} operation canceled.`));
                frappe.validated = false;
            });
        }
    });
    frappe.validated = false;
}
