// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Induction Record", {
  refresh(frm) {},

  employee: async function (frm) {
    await frm.events.populate_employee_details(frm);
  },

  company: function (frm) {
    if (!frm.doc.company) {
      frm.set_value("letter_head", "");
      return;
    }
    frappe.call({
      method: "ir.industrial_relations.doctype.employee_induction_record.employee_induction_record.fetch_company_letter_head",
      args: { company: frm.doc.company },
      callback(r) {
        frm.set_value("letter_head", (r.message || {}).letter_head || "");
      },
    });
  },

  facilitator: async function (frm) {
    await frm.events.populate_facilitator_details(frm);
  },

  training_date: async function (frm) {
    await frm.events.default_valid_from_from_training_date(frm);
    await frm.events.recalc_valid_to_if_needed(frm);
  },

  training: async function (frm) {
    await frm.events.recalc_valid_to_if_needed(frm);
  },

  valid_from: async function (frm) {
    await frm.events.recalc_valid_to_if_needed(frm);
  },

  default_valid_from_from_training_date: async function (frm) {
    const td = frm.doc.training_date;

    if (!td) return;

    const current_vf = frm.doc.valid_from || null;

    if (!current_vf) {
      frm._auto_valid_from = td;
      await frm.set_value("valid_from", td);
      return;
    }

    if (frm._auto_valid_from && current_vf === frm._auto_valid_from) {
      frm._auto_valid_from = td;
      await frm.set_value("valid_from", td);
    }
  },

  recalc_valid_to_if_needed: async function (frm) {
    const training = frm.doc.training;
    const valid_from = frm.doc.valid_from;

    if (!training || !valid_from) return;

    try {
      const r = await frappe.db.get_value("Employee Induction", training, ["valid_for"]);
      const valid_for_raw = r?.message?.valid_for;

      const months = cint(valid_for_raw);
      if (!months) return;

      const computed_valid_to = frm.events.add_months_minus_one_day(valid_from, months);
      const current_vt = frm.doc.valid_to || null;

      if (!current_vt) {
        frm._auto_valid_to = computed_valid_to;
        await frm.set_value("valid_to", computed_valid_to);
        return;
      }

      if (frm._auto_valid_to && current_vt === frm._auto_valid_to) {
        frm._auto_valid_to = computed_valid_to;
        await frm.set_value("valid_to", computed_valid_to);
      }
    } catch (err) {
      console.error("Failed to calculate valid_to:", err);
      frappe.msgprint({
        title: __("Validity calculation failed"),
        message: __("Could not calculate Valid To. Please try again."),
        indicator: "red",
      });
    }
  },

  add_months_minus_one_day: function (date_str, months) {
    const plus_months = frappe.datetime.add_months(date_str, months);
    const minus_one_day = frappe.datetime.add_days(plus_months, -1);
    return minus_one_day;
  },

  populate_employee_details: async function (frm) {
    const employee = frm.doc.employee;

    if (!employee) {
      await frm.set_value({
        employee_name: null,
        designation: null,
        branch: null,
        ofo_code: null,
        company: null,
        letter_head: null,
      });
      return;
    }

    const employee_fields = ["employee_name", "designation", "branch", "company"];

    try {
      const r = await frappe.db.get_value("Employee", employee, employee_fields);
      const v = (r && r.message) ? r.message : {};

      await frm.set_value({
        employee_name: v.employee_name || null,
        designation: v.designation || null,
        branch: v.branch || null,
        company: v.company || null,
      });

      await frm.events.populate_ofo_code_from_designation(frm);
    } catch (err) {
      console.error("Failed to fetch Employee details:", err);
      frappe.msgprint({
        title: __("Employee lookup failed"),
        message: __("Could not fetch details for Employee {0}. Please try again.", [employee]),
        indicator: "red",
      });
    }
  },

  populate_ofo_code_from_designation: async function (frm) {
    const designation = frm.doc.designation;

    if (!designation) {
      await frm.set_value("ofo_code", null);
      return;
    }

    try {
      const r = await frappe.call({
        method: "ir.industrial_relations.doctype.employee_induction_record.employee_induction_record.get_ofo_codes_for_designation",
        args: { designation: designation },
      });

      const unique_ofo_codes = r.message || [];

      if (unique_ofo_codes.length === 1) {
        await frm.set_value("ofo_code", unique_ofo_codes[0]);
        return;
      }

      await frm.set_value("ofo_code", null);

      if (unique_ofo_codes.length > 1) {
        frappe.msgprint({
          title: __("Multiple OFO Codes Found"),
          message: __(
            "The designation {0} is linked to multiple OFO Codes: {1}. Please select the correct OFO Code manually.",
            [designation, unique_ofo_codes.join(", ")]
          ),
          indicator: "orange",
        });
        return;
      }

      // OFO Code is mandatory but couldn't be auto-filled - a fleeting toast
      // here previously left the "why won't this save" question unanswered,
      // since the field just sits there red with no visible explanation.
      frappe.msgprint({
        title: __("No OFO Code Found"),
        message: __(
          "No OFO Code is linked to designation {0} yet. OFO Code is required - please select one manually before saving, or ask a Training Manager to add {0} to the correct OFO Code's Applicable Designation(s).",
          [designation]
        ),
        indicator: "orange",
      });
    } catch (err) {
      console.error("Failed to fetch OFO Code:", err);
      await frm.set_value("ofo_code", null);

      frappe.msgprint({
        title: __("OFO Code lookup failed"),
        message: __("Could not find the OFO Code for designation {0}. Please try again.", [designation]),
        indicator: "red",
      });
    }
  },

  populate_facilitator_details: async function (frm) {
    const facilitator = frm.doc.facilitator;

    if (!facilitator) {
      await frm.set_value("facilitator_names", null);
      await frm.set_value("institution", null);
      return;
    }

    const facilitator_fields = ["full_name", "supplier"];

    try {
      const r = await frappe.db.get_value("Facilitator", facilitator, facilitator_fields);
      const v = (r && r.message) ? r.message : {};

      await frm.set_value("facilitator_names", v.full_name || null);
      await frm.set_value("institution", v.supplier || null);
    } catch (err) {
      console.error("Failed to fetch Facilitator details:", err);
      frappe.msgprint({
        title: __("Facilitator lookup failed"),
        message: __("Could not fetch details for Facilitator {0}. Please try again.", [facilitator]),
        indicator: "red",
      });
    }
  },

  before_submit(frm) {
    if (!frm.doc.certificate) {
      frappe.msgprint({
        title: __("Certificate Required"),
        message: __("Please attach the certificate file before submitting."),
        indicator: "red",
      });
      frappe.validated = false;
    }
  },
});