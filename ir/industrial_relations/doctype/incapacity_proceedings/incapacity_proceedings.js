// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Incapacity Proceedings", {
  refresh: function (frm) {
    render_linked_docs(frm);

    frm.toggle_display(
      ["make_nta_hearing", "write_incapacity_outcome_report"],
      frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.workflow_state !== "Submitted"
    );

    if (frappe.user.has_role("IR Manager")) {
      frm.add_custom_button(__("Actions"), function () {}, "Actions")
        .addClass("btn-primary")
        .attr("id", "actions_dropdown");

      frm.page.add_inner_button(
        __("Issue NTA"),
        function () {
          make_nta_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Write Outcome Report"),
        function () {
          write_incapacity_outcome_report(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue Not Incapacitated"),
        function () {
          make_not_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue Suspension"),
        function () {
          make_suspension_form_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue Demotion"),
        function () {
          make_demotion_form_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue Pay Reduction"),
        function () {
          make_pay_reduction_form(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue Dismissal"),
        function () {
          make_dismissal_form_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Issue VSP"),
        function () {
          make_vsp_incap(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Cancel Incapacity Proceeding"),
        function () {
          cancel_incapacity(frm);
        },
        "Actions"
      );

      frm.page.add_inner_button(
        __("Appeal Against Outcome"),
        function () {
          appeal_incapacity(frm);
        },
        "Actions"
      );
    }
  },

  after_save: function (frm) {
    render_linked_docs(frm);
  },

  accused: function (frm) {
    if (frm.doc.accused) {
      fetch_employee_data(
        frm,
        frm.doc.accused,
        {
          employee_name: "accused_name",
          employee: "accused_coy",
          designation: "accused_pos",
          company: "company",
          date_of_joining: "engagement_date",
          branch: "branch",
        },
        function () {
          fetch_default_letter_head(frm, frm.doc.company);
        }
      );

      fetch_incapacity_history(frm, frm.doc.accused);

      frappe.call({
        method:
          "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.check_if_ss",
        args: { accused: frm.doc.accused },
        callback: function (r) {
          if (r.message) {
            frm.set_value("is_ss", r.message.is_ss);
            frm.set_value("ss_union", r.message.ss_union);
          }
        },
      });
    }
  },

  complainant: function (frm) {
    if (frm.doc.complainant) {
      frappe.call({
        method:
          "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.fetch_complainant_data",
        args: { complainant: frm.doc.complainant },
        callback: function (r) {
          if (r.message) {
            frm.set_value("compl_name", r.message.compl_name || "");
            frm.set_value("compl_pos", r.message.compl_pos || "");
          }
        },
      });
    }
  },
});

// ----------------------
// NEW: Linked docs render (HTML field)
// ----------------------

function render_linked_docs(frm) {
  if (!frm.fields_dict.linked_docs) return;

  // Ensure shared CSS exists (same pattern as Disciplinary Action)
  frappe.require("/assets/ir/css/ir_ui.css");

  if (frm.is_new() || frm.doc.__islocal) {
    frm.fields_dict.linked_docs.$wrapper.html(`
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
      "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.get_linked_docs_html",
    args: {
      incapacity_proceedings_name: frm.doc.name,
    },
    callback: function (r) {
      frm.fields_dict.linked_docs.$wrapper.html(r.message || "");
    },
  });
}

// ----------------------
// Existing helpers (kept)
// ----------------------

function fetch_employee_data(frm, employee, fields, callback) {
  frappe.call({
    method:
      "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.fetch_employee_data",
    args: {
      employee: employee,
      fields: JSON.stringify(fields),
    },
    callback: function (res) {
      if (res.message) {
        for (let field in res.message) {
          frm.set_value(field, res.message[field]);
        }
      }
      if (callback) callback();
    },
  });
}

function fetch_default_letter_head(frm, company) {
  if (!company) return;

  frappe.call({
    method:
      "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.fetch_default_letter_head",
    args: { company: company },
    callback: function (res) {
      frm.set_value("letter_head", res.message || "");
    },
  });
}

function fetch_incapacity_history(frm, accused) {
  frappe.call({
    method:
      "ir.industrial_relations.doctype.incapacity_proceedings.incapacity_proceedings.fetch_incapacity_history",
    args: {
      accused: accused,
      current_doc_name: frm.doc.name || "",
    },
    callback: function (res) {
      if (res.message) {
        frm.clear_table("previous_incapacity_outcomes");
        res.message.forEach(function (row) {
          let child = frm.add_child("previous_incapacity_outcomes");
          child.incap_proc = row.incap_proc;
          child.date = row.date;
          child.sanction = row.sanction;
          child.incap_details = row.incap_details;
        });
        frm.refresh_field("previous_incapacity_outcomes");
      }
    },
  });
}

// ----------------------
// Existing actions (kept as-is)
// ----------------------

function make_nta_incap(frm) {
  frappe.model.open_mapped_doc({
    method: "ir.industrial_relations.doctype.nta_hearing.nta_hearing.make_nta_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating NTA Incapcaity ..."),
  });
}

function write_incapacity_outcome_report(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.disciplinary_outcome_report.disciplinary_outcome_report.write_incapacity_outcome_report",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Disciplinary Outcome Report ..."),
  });
}

// (left here intentionally if you still use it elsewhere)
function create_written_outcome(frm) {
  frappe.call({
    method: "ir.industrial_relations.doctype.written_outcome.written_outcome.create_written_outcome",
    args: {
      source_name: frm.doc.name,
      source_doctype: frm.doctype,
    },
    freeze: true,
    freeze_message: __("Creating Written Outcome Report ..."),
    callback: function (r) {
      if (!r.exc) {
        frappe.model.sync(r.message);
        frappe.set_route("Form", "Written Outcome", r.message.name);
      }
    },
  });
}

function make_not_incap(frm) {
  frappe.model.open_mapped_doc({
    method: "ir.industrial_relations.doctype.not_guilty_form.not_guilty_form.make_not_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Not Incapacitated Form ..."),
  });
}

function make_suspension_form_incap(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.suspension_form.suspension_form.make_suspension_form_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Suspension Form ..."),
  });
}

function make_demotion_form_incap(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.demotion_form.demotion_form.make_demotion_form_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Demotion Form ..."),
  });
}

function make_pay_reduction_form(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.pay_reduction_form.pay_reduction_form.make_pay_reduction_form",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Pay Reduction Form ..."),
  });
}

function make_dismissal_form_incap(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.dismissal_form.dismissal_form.make_dismissal_form_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating Dismissal Form ..."),
  });
}

function make_vsp_incap(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.voluntary_seperation_agreement.voluntary_seperation_agreement.make_vsp_incap",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Creating VSP ..."),
  });
}

function cancel_incapacity(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.hearing_cancellation_form.hearing_cancellation_form.cancel_incapacity",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Generating Cancellation Form ..."),
  });
}

function appeal_incapacity(frm) {
  frappe.model.open_mapped_doc({
    method:
      "ir.industrial_relations.doctype.appeal_against_outcome.appeal_against_outcome.appeal_incapacity",
    frm: frm,
    args: { linked_incapacity_proceeding: frm.doc.name },
    freeze_message: __("Generating Cancellation Form ..."),
  });
}
