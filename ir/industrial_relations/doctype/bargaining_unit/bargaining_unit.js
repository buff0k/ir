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

// "Designation Selector" is a shared child table (also used by Employee
// Induction and Organising Framework for Occupation Code), so this guards
// itself to only act when the parent form is actually Bargaining Unit.
frappe.ui.form.on("Designation Selector", {
	designation(frm, cdt, cdn) {
		if (frm.doctype !== "Bargaining Unit") return;

		const row = frappe.get_doc(cdt, cdn);
		if (!row.designation) return;

		frappe.call({
			method:
				"ir.industrial_relations.doctype.bargaining_unit.bargaining_unit.find_conflicting_bargaining_unit",
			args: { designation: row.designation, exclude: frm.doc.name },
			callback(r) {
				const conflict = r.message;
				if (!conflict) return;

				frappe.msgprint({
					title: __("Designation Conflict"),
					indicator: "red",
					message: __(
						"Designation {0} is already assigned to the submitted Bargaining Unit {1}. A Designation cannot belong to more than one Bargaining Unit.",
						[frappe.utils.escape_html(row.designation), frappe.utils.escape_html(conflict)]
					),
				});

				frappe.model.set_value(cdt, cdn, "designation", "");
			},
		});
	},
});
