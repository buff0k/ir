// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

// period_start/period_end's own min_value/max_value (set to 1/31 in the
// JSON) are not enforced on the version-16 branch of frappe yet, so this is
// the real, immediate-feedback check - the server-side validate() in
// ir_payroll_period.py is the authoritative backstop.
const DAY_OF_MONTH_FIELDS = ["period_start", "period_end"];

frappe.ui.form.on("IR Payroll Period", {
	period_start(frm) {
		validate_day_of_month(frm, "period_start");
	},
	period_end(frm) {
		validate_day_of_month(frm, "period_end");
	},
	validate(frm) {
		DAY_OF_MONTH_FIELDS.forEach((fieldname) => validate_day_of_month(frm, fieldname));
	},
});

function validate_day_of_month(frm, fieldname) {
	const value = frm.doc[fieldname];
	if (value === null || value === undefined || value === "") return;

	if (value < 1 || value > 31) {
		frappe.msgprint({
			title: __("Invalid Day"),
			indicator: "red",
			message: __("{0} must be between 1 and 31.", [frm.get_field(fieldname).df.label]),
		});
		frm.set_value(fieldname, "");
		frappe.validated = false;
	}
}
