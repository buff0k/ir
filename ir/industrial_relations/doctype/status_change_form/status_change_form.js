// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Status Change Form", {
  async requested_by(frm) {
    await frm.events.pull_requested_by_details(frm);
  },

  async employee(frm) {
    await frm.events.pull_employee_details(frm);
  },

  before_submit(frm) {
    if (!frm.doc.attach) {
      frappe.throw(__("You must attach the signed status change form before submitting."));
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
    // current_designation/current_branch are no longer stored fields -
    // validate() reads the Employee record live on save instead, to
    // auto-correct the "old" side of any Designation/Branch row in
    // status_change_details.
    if (!frm.doc.employee) {
      frm.set_value("employee_name", "");
      return;
    }

    const r = await frappe.db.get_value("Employee", frm.doc.employee, ["employee_name"]);

    const v = (r && r.message) || {};
    await frm.set_value("employee_name", v.employee_name || "");
  },
});

frappe.ui.form.on("Status Change Detail", {
  // Status Change Detail rows carry fields for all four change_type shapes
  // at once - mirrors the server-side clearing in status_change_form.py so
  // switching a row's type doesn't leave stale values sitting in the fields
  // that just became hidden, visible as soon as the user picks a new type
  // rather than only after save.
  change_type(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const is_link_row = row.change_type === "Branch" || row.change_type === "Designation";
    const is_condition_row = row.change_type === "Conditions of Employment";
    const is_salary_row = row.change_type === "Salary Component";

    if (!is_link_row) {
      frappe.model.set_value(cdt, cdn, "old_value", "");
      frappe.model.set_value(cdt, cdn, "new_value", "");
    }
    if (!is_condition_row) {
      frappe.model.set_value(cdt, cdn, "old_condition", "");
      frappe.model.set_value(cdt, cdn, "new_condition", "");
    }
    if (!is_salary_row) {
      frappe.model.set_value(cdt, cdn, "salary_component", "");
      frappe.model.set_value(cdt, cdn, "old_amount", 0);
      frappe.model.set_value(cdt, cdn, "new_amount", 0);
    }
  },
});
