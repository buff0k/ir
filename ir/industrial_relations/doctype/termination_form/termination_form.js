// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Termination Form", {
    onload: function(frm) {
        // Always run the toggle logic on load
        toggle_notice_ends(frm);

        // Only populate if new and empty
        if (frm.is_new() && !(frm.doc.documents_received || []).length) {
            frappe.db.get_list("Termination Documentation", {
                fields: ["name"]
            }).then(docs => {
                docs.forEach(doc => {
                    frm.add_child("documents_received", {
                        document: doc.name,
                        received: "No"
                    });
                });
                frm.refresh_field("documents_received");
            });
        }
    },

    notice: function(frm) {
        toggle_notice_ends(frm);
    },

    before_submit: function(frm) {
        // Check for signed form
        if (!frm.doc.attach_signed) {
            frappe.throw("Please attach a signed copy of the Termination Form in the 'Signed Form Attachment' field before submitting.");
        }
        // Validate documents_received table
        for (let row of frm.doc.documents_received || []) {
            if (row.received !== "N/A") {
                if (row.received === "No") {
                    frappe.throw(`Document "${row.document}" is marked as 'No'. All documents must be received or marked 'N/A' or "Yes" before submission.`);
                }
                if (!row.attach) {
                    frappe.throw(`Please attach a file for "${row.document}" in Documents Received.`);
                }
            }
        }
    },

    company: function(frm) {
        if (frm.doc.company) {
            frappe.db.get_doc('Company', frm.doc.company).then(company => {
                if (company.default_letter_head) {
                    frm.set_value('letter_head', company.default_letter_head);
                } else {
                    frm.set_value('letter_head', '');
                    frappe.msgprint('This company has no default Letter Head set.');
                }
            });
        }
    },

    requested_by: function (frm) {
        if (frm.doc.requested_by) {
            frappe.db.get_doc('Employee', frm.doc.requested_by)
                .then(employee => {
                    frm.set_value('requested_by_site', employee.branch || '');
                    frm.set_value('requested_by_designation', employee.designation || '');
                    frm.set_value('requested_by_names', employee.employee_name || '');
                })
                .catch(err => {
                    frappe.msgprint(__('Failed to fetch employee details'));
                    console.error(err);
                });
        }
    },
    
    requested_for: function (frm) {
        if (frm.doc.requested_for) {
            frappe.db.get_doc('Employee', frm.doc.requested_for)
                .then(employee => {
                    frm.set_value('requested_for_site', employee.branch || '');
                    frm.set_value('requested_for_designation', employee.designation || '');
                    frm.set_value('requested_for_names', employee.employee_name || '');
                    frm.set_value('id_number', employee.custom_id_number || '');
                    frm.set_value('company', employee.company || '');
                    frm.set_value('doc_name', frm.doc.requested_for);
                })
                .catch(err => {
                    frappe.msgprint(__('Failed to fetch employee details'));
                    console.error(err);
                });
        }
    },

    reason: function (frm) {
        if (frm.doc.reason) {
            frappe.db.get_doc('Reason for Termination', frm.doc.reason)
                .then(reason => {
                    frm.set_value('notice', reason.notice || '');
                })
                .catch(err => {
                    frappe.msgprint(__('Failed to fetch reason details'));
                    console.error(err);
                });
        }
    }
});

function toggle_notice_ends(frm) {
    const show = Boolean(frm.doc.notice);
    // Force refresh the field to re-evaluate display logic
    frm.toggle_display("notice_ends", show);
    frm.set_df_property("notice_ends", "reqd", show);
    if (!show) {
        frm.set_value("notice_ends", null);  // Optional: clear the value if notice is unchecked
    }
}