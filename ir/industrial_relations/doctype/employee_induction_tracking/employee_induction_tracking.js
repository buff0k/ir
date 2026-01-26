// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Employee Induction Tracking", {
  refresh(frm) {
  },

  employee: async function (frm) {
    await frm.events.populate_employee_details(frm);
  },

  populate_employee_details: async function (frm) {
    const employee = frm.doc.employee;

    if (!employee) {
      frm.set_value("employee_name", null);
      frm.set_value("engagement_date", null);
      frm.set_value("designation", null);
      frm.set_value("branch", null);
      frm.set_value("id_number", null);
      frm.set_value("designated_group", null);
      frm.set_value("occupational_level", null);
      frm.set_value("is_disabled", 0);
      return;
    }

    const employee_fields = [
      "employee_name",
      "date_of_joining",
      "designation",
      "branch",
      "custom_id_number",
      "custom_designated_group",
      "custom_occupational_level",
      "custom_disabled_employee",
    ];

    try {
      const r = await frappe.db.get_value("Employee", employee, employee_fields);
      const v = (r && r.message) ? r.message : {};
      frm.set_value("employee_name", v.employee_name || null);
      frm.set_value("engagement_date", v.date_of_joining || null);
      frm.set_value("designation", v.designation || null);
      frm.set_value("branch", v.branch || null);
      frm.set_value("id_number", v.custom_id_number || null);
      frm.set_value("designated_group", v.custom_designated_group || null);
      frm.set_value("occupational_level", v.custom_occupational_level || null);
      frm.set_value("is_disabled", v.custom_disabled_employee ? 1 : 0);
    } catch (err) {
      console.error("Failed to fetch Employee details:", err);
      frappe.msgprint({
        title: __("Employee lookup failed"),
        message: __("Could not fetch details for Employee {0}. Please try again.", [employee]),
        indicator: "red",
      });
    }
  },
});