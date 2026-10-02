// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bargaining Unit", {
	onload(frm) {
		if (!frm.is_new()) return;

		if (!frm.doc.create_date) {
			frm.set_value("create_date", frappe.datetime.get_today());
		}

		if (!frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_default("company") || "");
		}
	},
});
