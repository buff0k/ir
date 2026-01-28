// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Induction Record", {
  refresh(frm) {},

  employee: async function (frm) {
    await frm.events.populate_employee_details(frm);
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
      frm.set_value("employee_name", null);
      frm.set_value("designation", null);
      frm.set_value("branch", null);
      return;
    }

    const employee_fields = ["employee_name", "designation", "branch"];

    try {
      const r = await frappe.db.get_value("Employee", employee, employee_fields);
      const v = (r && r.message) ? r.message : {};
      frm.set_value("employee_name", v.employee_name || null);
      frm.set_value("designation", v.designation || null);
      frm.set_value("branch", v.branch || null);
    } catch (err) {
      console.error("Failed to fetch Employee details:", err);
      frappe.msgprint({
        title: __("Employee lookup failed"),
        message: __("Could not fetch details for Employee {0}. Please try again.", [employee]),
        indicator: "red",
      });
    }
  },

  populate_facilitator_details: async function (frm) {
    const facilitator = frm.doc.facilitator;

    if (!facilitator) {
      frm.set_value("facilitator_names", null);
      frm.set_value("institution", null);
      return;
    }

    const facilitator_fields = ["full_name", "supplier"];

    try {
      const r = await frappe.db.get_value("Facilitator", facilitator, facilitator_fields);
      const v = (r && r.message) ? r.message : {};
      frm.set_value("facilitator_names", v.full_name || null);
      frm.set_value("institution", v.supplier || null);
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
