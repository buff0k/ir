// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Facilitator", {
  first_name(frm) {
    frm.events.set_full_name(frm);
  },

  middle_name(frm) {
    frm.events.set_full_name(frm);
  },

  last_name(frm) {
    frm.events.set_full_name(frm);
  },

  set_full_name(frm) {
    const parts = [
      frm.doc.first_name,
      frm.doc.middle_name,
      frm.doc.last_name,
    ]
      .map(v => (v || "").trim())
      .filter(v => v.length > 0);

    frm.set_value("full_name", parts.join(" "));
  },
});