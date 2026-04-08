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
    frappe.require("/assets/ir/css/ir_ui.css");

    if (
      frm.doc.ir_intervention &&
      frm.doc.linked_intervention &&
      !frm.doc.linked_intervention_processed
    ) {
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
      method:
        "ir.industrial_relations.doctype.written_outcome.written_outcome.fetch_intervention_data",
      args: {
        intervention: frm.doc.linked_intervention,
        intervention_type: frm.doc.ir_intervention,
      },
      callback(r) {
        const data = r.message || null;
        if (!data) return;

        Object.keys(data).forEach((fieldname) => {
          if (fieldname === "nta_charges") return;
          if (frm.fields_dict[fieldname]) {
            frm.set_value(fieldname, data[fieldname]);
          }
        });

        frm.trigger("clear_nta_dependent_fields");

        if (Array.isArray(data.nta_charges)) {
          frm.clear_table("nta_charges");
          data.nta_charges.forEach((row) => {
            const child = frm.add_child("nta_charges");
            child.indiv_charge = row.indiv_charge || "";
          });
          frm.refresh_field("nta_charges");
        }

        if (frm.fields_dict.incap_type_nta) {
          frm.set_value("incap_type_nta", data.incap_type_nta || null);
        }

        if (frm.fields_dict.incapacity_details_nta) {
          frm.set_value(
            "incapacity_details_nta",
            data.incapacity_details_nta || ""
          );
        }

        frm.set_value("linked_intervention_processed", true);
      },
    });
  },

  linked_nta(frm) {
    frm.trigger("clear_nta_dependent_fields");

    if (!frm.doc.linked_nta) return;

    frappe.call({
      method:
        "ir.industrial_relations.doctype.written_outcome.written_outcome.get_nta_details",
      args: {
        nta_name: frm.doc.linked_nta,
        intervention_type: frm.doc.ir_intervention,
        linked_intervention: frm.doc.linked_intervention,
      },
      callback(r) {
        const data = r.message || null;
        if (!data) return;

        if (Array.isArray(data.nta_charges)) {
          frm.clear_table("nta_charges");
          data.nta_charges.forEach((row) => {
            const child = frm.add_child("nta_charges");
            child.indiv_charge = row.indiv_charge || "";
          });
          frm.refresh_field("nta_charges");
        }

        if (frm.fields_dict.incap_type_nta) {
          frm.set_value("incap_type_nta", data.incap_type_nta || null);
        }

        if (frm.fields_dict.incapacity_details_nta) {
          frm.set_value(
            "incapacity_details_nta",
            data.incapacity_details_nta || ""
          );
        }
      },
    });
  },

  clear_nta_dependent_fields(frm) {
    if (frm.fields_dict.nta_charges) {
      frm.clear_table("nta_charges");
      frm.refresh_field("nta_charges");
    }

    if (frm.fields_dict.incap_type_nta) {
      frm.set_value("incap_type_nta", null);
    }

    if (frm.fields_dict.incapacity_details_nta) {
      frm.set_value("incapacity_details_nta", "");
    }
  },

  render_linked_sections(frm) {
    const rulings_wrapper =
      frm.fields_dict.linked_rulings && frm.fields_dict.linked_rulings.$wrapper;

    if (!rulings_wrapper) return;

    if (frm.is_new() || frm.doc.__islocal) {
      rulings_wrapper.html(`
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">
            Linked documents will appear here once the record is saved.
          </div>
        </div>
      `);
      return;
    }

    frappe.call({
      method:
        "ir.industrial_relations.doctype.written_outcome.written_outcome.get_linked_sections_html",
      args: {
        linked_intervention: frm.doc.linked_intervention,
      },
      callback(r) {
        const out = r.message || {};
        rulings_wrapper.html(out.linked_rulings || "");
      },
    });
  },

  compile_outcome(frm) {
    frappe.call({
      method:
        "ir.industrial_relations.doctype.written_outcome.written_outcome.compile_outcome",
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
    if (!frm.doc.complainant && frm.fields_dict.complainant_name) {
      frm.set_value("complainant_name", null);
    }
  },

  chairperson(frm) {
    if (!frm.doc.chairperson && frm.fields_dict.chairperson_name) {
      frm.set_value("chairperson_name", null);
    }
  },

  approver(frm) {
    if (!frm.doc.approver && frm.fields_dict.approver_name) {
      frm.set_value("approver_name", null);
    }
  },
});