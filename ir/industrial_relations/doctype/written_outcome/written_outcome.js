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

  after_save(frm) {
    schedule_linked_intervention_update_check(frm);
  },

  on_submit(frm) {
    schedule_linked_intervention_update_check(frm);
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
          if (
            fieldname === "nta_charges" ||
            fieldname === "disciplinary_history" ||
            fieldname === "previous_incapacity_outcomes" ||
            fieldname === "previous_performance_outcomes"
          ) {
            return;
          }

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

        if (frm.fields_dict.performance_details_nta) {
          frm.set_value("performance_details_nta", data.performance_details_nta || "");
        }

        set_initial_final_values(frm, data);
        set_disciplinary_history(
          frm,
          data.disciplinary_history || []
        );
        set_incapacity_history(
          frm,
          data.previous_incapacity_outcomes || []
        );
        set_performance_history(
          frm,
          data.previous_performance_outcomes || []
        );

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

        if (frm.fields_dict.performance_details_nta) {
          frm.set_value("performance_details_nta", data.performance_details_nta || "");
        }

        set_initial_final_values(frm, data);
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

    if (frm.fields_dict.performance_details_nta) {
      frm.set_value("performance_details_nta", "");
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

function set_disciplinary_history(frm, rows) {
  if (!frm.fields_dict.disciplinary_history) return;

  frm.clear_table("disciplinary_history");

  (rows || []).forEach((row) => {
    const child = frm.add_child("disciplinary_history");
    child.disc_action = row.disc_action || "";
    child.date = row.date || null;
    child.sanction = row.sanction || "";
    child.charges = row.charges || "No charges recorded";
  });

  frm.refresh_field("disciplinary_history");
}


function set_incapacity_history(frm, rows) {
  if (!frm.fields_dict.previous_incapacity_outcomes) return;

  frm.clear_table("previous_incapacity_outcomes");

  (rows || []).forEach((row) => {
    const child = frm.add_child("previous_incapacity_outcomes");
    child.incap_proc = row.incap_proc || null;
    child.date = row.date || null;
    child.incap_details = row.incap_details || "";
    child.sanction = row.sanction || "";
  });

  frm.refresh_field("previous_incapacity_outcomes");
}


function set_performance_history(frm, rows) {
  if (!frm.fields_dict.previous_performance_outcomes) return;

  frm.clear_table("previous_performance_outcomes");

  (rows || []).forEach((row) => {
    const child = frm.add_child("previous_performance_outcomes");
    child.performance_action = row.performance_action || null;
    child.date = row.date || null;
    child.charges = row.charges || "";
    child.sanction = row.sanction || "";
  });

  frm.refresh_field("previous_performance_outcomes");
}


function final_charges_are_empty(frm) {
  return !(frm.doc.final_charges || []).some(
    (row) => (row.indiv_charge || "").trim()
  );
}

function set_initial_final_values(frm, data) {
  if (
    frm.doc.ir_intervention === "Disciplinary Action" &&
    frm.fields_dict.final_charges &&
    final_charges_are_empty(frm)
  ) {
    frm.clear_table("final_charges");
    (data.nta_charges || []).forEach((row) => {
      const value = (row.indiv_charge || "").trim();
      if (!value) return;
      const child = frm.add_child("final_charges");
      child.indiv_charge = value;
    });
    frm.refresh_field("final_charges");
  }

  if (
    frm.doc.ir_intervention === "Incapacity Proceedings" &&
    frm.fields_dict.final_incapacity_details &&
    !(frm.doc.final_incapacity_details || "").trim()
  ) {
    frm.set_value(
      "final_incapacity_details",
      data.incapacity_details_nta || ""
    );
  }

  if (
    frm.doc.ir_intervention === "Poor Performance" &&
    frm.fields_dict.final_performance_details &&
    !(frm.doc.final_performance_details || "").trim()
  ) {
    frm.set_value(
      "final_performance_details",
      data.performance_details_nta || ""
    );
  }
}

function schedule_linked_intervention_update_check(frm) {
  if (frm.__linked_update_check_timer) {
    clearTimeout(frm.__linked_update_check_timer);
  }

  frm.__linked_update_check_timer = setTimeout(() => {
    check_and_offer_linked_intervention_update(frm);
  }, 250);
}

function check_and_offer_linked_intervention_update(frm) {
  if (
    frm.is_new() ||
    frm.doc.__islocal ||
    frm.__linked_update_prompt_running
  ) {
    return;
  }

  const supported = [
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
  ];

  if (
    !supported.includes(frm.doc.ir_intervention) ||
    !frm.doc.linked_intervention
  ) {
    return;
  }

  frm.__linked_update_prompt_running = true;

  frappe.call({
    method:
      "ir.industrial_relations.doctype.written_outcome.written_outcome." +
      "get_linked_intervention_update_status",
    args: { docname: frm.doc.name },
    callback(r) {
      const state = r.message || {};

      if (!state.changed) {
        frm.__linked_update_prompt_running = false;
        return;
      }

      frappe.confirm(
        __(
          "The final outcome details differ from the linked {0} " +
            "<b>{1}</b>.<br><br>Do you want to update its " +
            "<b>{2}</b> now?",
          [
            state.intervention_type,
            state.intervention_name,
            state.source_label,
          ]
        ),
        () => update_linked_intervention(frm),
        () => {
          frm.__linked_update_prompt_running = false;
        }
      );
    },
    error() {
      frm.__linked_update_prompt_running = false;
    },
  });
}

function update_linked_intervention(frm) {
  frappe.call({
    method:
      "ir.industrial_relations.doctype.written_outcome.written_outcome." +
      "update_linked_intervention_from_outcome",
    args: { docname: frm.doc.name },
    freeze: true,
    freeze_message: __("Updating linked IR intervention..."),
    callback(r) {
      const result = r.message || {};
      frm.__linked_update_prompt_running = false;

      if (result.updated) {
        frappe.show_alert(
          {
            message: __("{0} {1} updated successfully.", [
              result.intervention_type,
              result.intervention_name,
            ]),
            indicator: "green",
          },
          7
        );
      }
    },
    error() {
      frm.__linked_update_prompt_running = false;
    },
  });
}

