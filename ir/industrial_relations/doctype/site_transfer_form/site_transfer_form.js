// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Transfer Form", {
  async requested_by(frm) {
    await frm.events.pull_requested_by_details(frm);
  },

  async employee(frm) {
    await frm.events.pull_employee_details(frm);
  },

  // Block submit if no attachment (client-side)
  before_submit(frm) {
    if (!frm.doc.attach) {
      frappe.throw(__("You must attach the signed transfer form before submitting."));
    }
  },

  async pull_requested_by_details(frm) {
    if (!frm.doc.requested_by) {
      frm.set_value("requested_by_name", "");
      frm.set_value("requested_by_designation", "");
      return;
    }

    const r = await frappe.db.get_value("Employee", frm.doc.requested_by, [
      "employee_name",
      "designation",
    ]);

    const v = (r && r.message) || {};
    await frm.set_value("requested_by_name", v.employee_name || "");
    await frm.set_value("requested_by_designation", v.designation || "");
  },

  async pull_employee_details(frm) {
    if (!frm.doc.employee) {
      frm.set_value("employee_name", "");
      frm.set_value("designation", "");
      frm.set_value("current_branch", "");
      return;
    }

    const r = await frappe.db.get_value("Employee", frm.doc.employee, [
      "employee_name",
      "designation",
      "branch",
    ]);

    const v = (r && r.message) || {};
    await frm.set_value("employee_name", v.employee_name || "");
    await frm.set_value("designation", v.designation || "");
    await frm.set_value("current_branch", v.branch || "");
  },
});
