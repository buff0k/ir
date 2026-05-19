// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('NTA Hearing', {
    refresh(frm) {
        if (frm.doc.linked_disciplinary_action && !frm.doc.linked_disciplinary_action_processed) {
            frm.trigger('linked_disciplinary_action');
        } else if (frm.doc.linked_incapacity_proceeding && !frm.doc.linked_incapacity_proceeding_processed) {
            frm.trigger('linked_incapacity_proceeding');
        } else if (frm.doc.linked_poor_performance && !frm.doc.linked_poor_performance_processed) {
            frm.trigger('linked_poor_performance');
        }
    },

    linked_disciplinary_action(frm) {
        if (!frm.doc.linked_disciplinary_action) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_disciplinary_action_data',
            args: { disciplinary_action: frm.doc.linked_disciplinary_action },
            callback(r) {
                const data = r.message || {};
                frm.doc.employee = data.accused || '';
                frm.doc.names = data.accused_name || '';
                frm.doc.coy = data.accused_coy || '';
                frm.doc.position = data.accused_pos || '';
                frm.doc.company = data.company || '';
                ['employee', 'names', 'coy', 'position', 'company'].forEach(f => frm.refresh_field(f));

                frm.clear_table('disciplinary_history');
                (data.previous_disciplinary_outcomes || []).forEach(row => {
                    let child = frm.add_child('disciplinary_history');
                    child.disc_action = row.disc_action;
                    child.date = row.date;
                    child.sanction = row.sanction;
                    child.charges = row.charges;
                });
                frm.refresh_field('disciplinary_history');

                frm.clear_table('nta_charges');
                (data.final_charges || []).forEach(row => {
                    let child = frm.add_child('nta_charges');
                    child.indiv_charge = row.indiv_charge;
                });
                frm.refresh_field('nta_charges');

                frm.set_value('applied_rights', 'Disciplinary Hearing');
                frm.trigger('applied_rights');
                frm.set_value('linked_disciplinary_action_processed', true);
            }
        });
    },

    linked_incapacity_proceeding(frm) {
        if (!frm.doc.linked_incapacity_proceeding) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_incpacity_proceeding_data',
            args: { incapacity_proceeding: frm.doc.linked_incapacity_proceeding },
            callback(r) {
                const data = r.message || {};
                frm.doc.employee = data.accused || '';
                frm.doc.names = data.accused_name || '';
                frm.doc.coy = data.accused_coy || '';
                frm.doc.position = data.accused_pos || '';
                frm.doc.company = data.company || '';
                frm.doc.type_of_incapacity = data.type_of_incapacity || '';
                frm.set_value('details_of_incapacity', data.details_of_incapacity || '');
                ['employee', 'names', 'coy', 'position', 'company', 'type_of_incapacity', 'details_of_incapacity'].forEach(f => frm.refresh_field(f));

                frm.clear_table('previous_incapacity_outcomes');
                (data.previous_incapacity_outcomes || []).forEach(row => {
                    let child = frm.add_child('previous_incapacity_outcomes');
                    child.incap_proc = row.incap_proc;
                    child.date = row.date;
                    child.sanction = row.sanction;
                    child.incap_details = row.incap_details;
                });
                frm.refresh_field('previous_incapacity_outcomes');

                frm.set_value('applied_rights', 'Incapacity');
                frm.trigger('applied_rights');
                frm.set_value('linked_incapacity_proceeding_processed', true);
            }
        });
    },

    linked_poor_performance(frm) {
        if (!frm.doc.linked_poor_performance) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_poor_performance_data',
            args: { poor_performance: frm.doc.linked_poor_performance },
            callback(r) {
                const data = r.message || {};
                frm.doc.employee = data.employee || '';
                frm.doc.names = data.employee_name || '';
                frm.doc.coy = data.employee || '';
                frm.doc.position = data.employee_designation || '';
                frm.doc.company = data.company || '';
                frm.set_value('performance_details_nta', data.details_of_poor_performance || '');
                ['employee', 'names', 'coy', 'position', 'company', 'performance_details_nta'].forEach(f => frm.refresh_field(f));

                frm.clear_table('previous_performance_outcomes');
                (data.previous_performance_outcomes || []).forEach(row => {
                    let child = frm.add_child('previous_performance_outcomes');
                    child.performance_action = row.performance_action;
                    child.date = row.date;
                    child.charges = row.charges;
                    child.sanction = row.sanction;
                });
                frm.refresh_field('previous_performance_outcomes');

                frm.set_value('applied_rights', 'Poor Performance');
                frm.trigger('applied_rights');
                frm.set_value('linked_poor_performance_processed', true);
            }
        });
    },

    chairperson(frm) {
        if (!frm.doc.chairperson) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_chairperson_name',
            args: { employee: frm.doc.chairperson },
            callback(r) { if (r.message) frm.set_value('chairperson_name', r.message.employee_name || ''); }
        });
    },

    complainant(frm) {
        if (!frm.doc.complainant) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_chairperson_name',
            args: { employee: frm.doc.complainant },
            callback(r) { if (r.message) frm.set_value('compl_name', r.message.employee_name || ''); }
        });
    },

    company(frm) {
        if (!frm.doc.company) return;
        frappe.call({
            method: 'ir.industrial_relations.doctype.nta_hearing.nta_hearing.fetch_company_letter_head',
            args: { company: frm.doc.company },
            callback(r) {
                if (r.message) {
                    frm.doc.letter_head = r.message.letter_head || '';
                    frm.refresh_field('letter_head');
                }
            }
        });
    },

    applied_rights(frm) {
        if (!frm.doc.applied_rights) return;
        frappe.model.with_doc('Employee Rights', frm.doc.applied_rights, function() {
            let doc = frappe.get_doc('Employee Rights', frm.doc.applied_rights);
            frm.clear_table('employee_rights');
            $.each(doc.applicable_rights || [], function(_, row) {
                let child = frm.add_child('employee_rights');
                child.individual_right = row.individual_right;
            });
            frm.refresh_field('employee_rights');
        });
    },

    before_submit(frm) {
        if (!frm.doc.signed_nta) {
            frappe.msgprint(__('You cannot submit this document until you have attached a signed copy of the NTA'));
            frappe.validated = false;
        }
    }
});
