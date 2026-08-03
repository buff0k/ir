// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Budget Map", {
	refresh(frm) {
		render_salary_structure_preview(frm);
	},
	salary_structure(frm) {
		render_salary_structure_preview(frm);
	},
	site_specific_allowances_add(frm) {
		render_salary_structure_preview(frm);
	},
	site_specific_allowances_remove(frm) {
		render_salary_structure_preview(frm);
	},
});

frappe.ui.form.on("Site Budget Map Allowance", {
	salary_component(frm) {
		render_salary_structure_preview(frm);
	},
	amount(frm) {
		render_salary_structure_preview(frm);
	},
});

function render_salary_structure_preview(frm) {
	const $wrapper = frm.fields_dict.salary_structure_preview.$wrapper;
	if (!frm.doc.salary_structure) {
		$wrapper.html("");
		return;
	}
	frappe.call({
		method: "ir.industrial_relations.doctype.site_budget_map.site_budget_map.get_site_budget_map_preview",
		args: {
			salary_structure: frm.doc.salary_structure,
			site_specific_allowances: frm.doc.site_specific_allowances || [],
		},
		callback(r) {
			$wrapper.html(r.message || "");
		},
	});
}
