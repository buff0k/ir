// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Plan", {
  onload(frm) {
    if (!frm.doc.status) frm.set_value("status", "Draft");
    if (frm.doc.enabled === undefined) frm.set_value("enabled", 1);
  },

  refresh(frm) {
    frm.add_custom_button(
      __("Open Site Plan Designer"),
      () => frappe.set_route("ir-site-plan-design", frm.doc.name),
      __("Site Plan"),
    );
  },

  status(frm) {
    if (["Superseded", "Archived"].includes(frm.doc.status)) {
      frm.set_value("enabled", 0);
    }
  },
});
