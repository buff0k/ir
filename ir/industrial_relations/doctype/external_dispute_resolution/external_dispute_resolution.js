// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("External Dispute Resolution", {
  refresh(frm) {
    frappe.require("/assets/ir/css/ir_ui.css");

    frm.trigger("render_linked_outcome");
  },

  render_linked_outcome(frm) {
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
    let employees = (frm.doc.employee || []).map(e => e.employee);
    let existing_applicants = (frm.doc.applicant_history || []).map(a => a.applicant);

    frm.doc.applicant_history = (frm.doc.applicant_history || []).filter(a => employees.includes(a.applicant));

    employees.forEach(emp => {
      if (!existing_applicants.includes(emp)) {
        let row = frm.add_child("applicant_history");
        row.applicant = emp;
        // frm.add_child() + a direct property assignment doesn't fire the
        // child table's own "applicant" trigger below (that only fires on a
        // real frappe.model.set_value, e.g. the user picking a value in the
        // grid) - call the same lookup directly so rows added this way still
        // get auto-populated.
        populate_applicant_links(frm, row.doctype, row.name);
      }
    });

    frm.refresh_field("applicant_history");
  },
});

frappe.ui.form.on("External Dispute Resolution Applicants", {
  applicant(frm, cdt, cdn) {
    populate_applicant_links(frm, cdt, cdn);
  },
});

function populate_applicant_links(frm, cdt, cdn) {
  const row = frappe.get_doc(cdt, cdn);
  if (!row.applicant) return;

  frappe.call({
    method:
      "ir.industrial_relations.doctype.external_dispute_resolution.external_dispute_resolution.get_latest_linked_records",
    args: { applicant: row.applicant, exclude_edr: frm.doc.name },
    callback(r) {
      const data = r.message || {};
      Object.entries(data).forEach(([fieldname, value]) => {
        frappe.model.set_value(cdt, cdn, fieldname, value || "");
      });
    },
  });
}
