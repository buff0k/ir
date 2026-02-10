// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("External Dispute Resolution", {
  refresh(frm) {
    // shared IR UI styles (same approach as your other doctype)
    frappe.require("/assets/ir/css/ir_ui.css");

    frm.trigger("render_linked_outcome");
  },

  render_linked_outcome(frm) {
    // `linked_outcome` is now an HTML field
    const wrapper = frm.fields_dict.linked_outcome && frm.fields_dict.linked_outcome.$wrapper;
    if (!wrapper) return;

    if (frm.is_new() || frm.doc.__islocal) {
      wrapper.html(`
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">
            Linked outcomes will appear here once the record is saved.
          </div>
        </div>
      `);
      return;
    }

    frappe.call({
      method: "ir.industrial_relations.doctype.external_dispute_resolution.external_dispute_resolution.get_linked_outcome_html",
      args: { edr_name: frm.doc.name },
      callback(r) {
        wrapper.html((r && r.message) || "");
      },
    });
  },

  employee(frm) {
    let employees = (frm.doc.employee || []).map(e => e.employee); // Extract employee IDs
    let existing_applicants = (frm.doc.applicant_history || []).map(a => a.applicant);

    // Remove rows for employees no longer selected
    frm.doc.applicant_history = (frm.doc.applicant_history || []).filter(a => employees.includes(a.applicant));

    // Add missing employees
    employees.forEach(emp => {
      if (!existing_applicants.includes(emp)) {
        let row = frm.add_child("applicant_history");
        row.applicant = emp;
      }
    });

    frm.refresh_field("applicant_history");
  },
});
