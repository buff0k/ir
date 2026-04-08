// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Anonymous Report", {
	investigator: function (frm) {
		if (!frm.doc.investigator) {
			frm.set_value("investigator_name", "");
			frm.set_value("investigator_designation", "");
			return;
		}

		frappe.db.get_value("Employee", frm.doc.investigator, [
			"employee_name",
			"designation"
		]).then((r) => {
			if (r.message) {
				frm.set_value("investigator_name", r.message.employee_name || "");
				frm.set_value("investigator_designation", r.message.designation || "");
			}
		});
	},

	validate: function (frm) {
		// Extra client-side guard
		if (frm.doc.docstatus === 0 && frm.doc.__unsaved && frm.doc._action === "submit" && !frm.doc.outcome) {
			frappe.throw(__("Outcome is required before submitting this document."));
		}
	}
});