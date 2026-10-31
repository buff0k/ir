// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("IR Payroll Cost Settings", {
	refresh(frm) {
		frm.set_query("salary_component", "basic_wage_components", () => ({
			filters: { type: "Earning" },
		}));
	},
});
