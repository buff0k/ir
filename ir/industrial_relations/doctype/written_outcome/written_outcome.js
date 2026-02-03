// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Written Outcome", {
  onload(frm) {
    try {
      frm.add_fetch("complainant", "employee_name", "complainant_name");
      frm.add_fetch("chairperson", "employee_name", "chairperson_name");
      frm.add_fetch("approver", "employee_name", "approver_name");
    } catch (e) {}
  },

  refresh(frm) {
    // shared CSS styling (same as other doctypes)
    frappe.require("/assets/ir/css/ir_ui.css");

    if (frm.doc.ir_intervention && frm.doc.linked_intervention && !frm.doc.linked_intervention_processed) {
      frm.trigger("fetch_intervention_data");
    }

    frm.trigger("render_linked_sections");

    frm.add_custom_button(
      __("Compile Outcome"),
      () => frm.trigger("compile_outcome"),
      __("Actions")
    ).addClass("btn-primary");
  },

  fetch_intervention_data(frm) {
    if (!(frm.doc.ir_intervention && frm.doc.linked_intervention)) return;

    frappe.call({
      method: "ir.industrial_relations.doctype.written_outcome.written_outcome.fetch_intervention_data",
      args: {
        intervention: frm.doc.linked_intervention,
        intervention_type: frm.doc.ir_intervention,
      },
      callback(r) {
        const data = r.message || null;
        if (!data) return;

        Object.keys(data).forEach((fieldname) => {
          if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, data[fieldname]);
          }
        });

        frm.set_value("linked_intervention_processed", true);
      },
    });
  },

  render_linked_sections(frm) {
    // These are now HTML fields (after your JSON change)
    const nta_wrapper = frm.fields_dict.linked_nta && frm.fields_dict.linked_nta.$wrapper;
    const rulings_wrapper = frm.fields_dict.linked_rulings && frm.fields_dict.linked_rulings.$wrapper;

    if (!nta_wrapper && !rulings_wrapper) return;

    // New / unsaved doc: show placeholder
    if (frm.is_new() || frm.doc.__islocal) {
      const empty = `
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">
            Linked documents will appear here once the record is saved.
          </div>
        </div>
      `;
      if (nta_wrapper) nta_wrapper.html(empty);
      if (rulings_wrapper) rulings_wrapper.html(empty);
      return;
    }

    frappe.call({
      method: "ir.industrial_relations.doctype.written_outcome.written_outcome.get_linked_sections_html",
      args: { linked_intervention: frm.doc.linked_intervention },
      callback(r) {
        const out = r.message || {};
        if (nta_wrapper) nta_wrapper.html(out.linked_nta || "");
        if (rulings_wrapper) rulings_wrapper.html(out.linked_rulings || "");
      },
    });
  },

  compile_outcome(frm) {
    frappe.call({
      method: "ir.industrial_relations.doctype.written_outcome.written_outcome.compile_outcome",
      args: { docname: frm.doc.name },
      callback(r) {
        if (r.message && r.message.ok) {
          frappe.msgprint(__("Outcome compiled successfully."));
          frm.reload_doc();
        }
      },
    });
  },

  complainant(frm) {
    if (!frm.doc.complainant && frm.fields_dict.complainant_name) frm.set_value("complainant_name", null);
  },
  chairperson(frm) {
    if (!frm.doc.chairperson && frm.fields_dict.chairperson_name) frm.set_value("chairperson_name", null);
  },
  approver(frm) {
    if (!frm.doc.approver && frm.fields_dict.approver_name) frm.set_value("approver_name", null);
  },
});
