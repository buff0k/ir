// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.listview_settings["Employee Induction Record"] = {
	add_fields: ["valid_to"],

	// Draft/Cancelled rows already get Frappe's own standard "Draft"/"Cancelled"
	// indicator automatically (this is only ever called for docstatus=1) - see
	// frappe.get_indicator() in frappe/public/js/frappe/model/indicator.js.
	// Same 90-day "Expiring soon" threshold and colour bands as Employee
	// Induction Tracking's own status cards (see that doctype's list/report
	// JS) - Valid (green) / Expiring within 90 days (orange) / Expired or no
	// expiry set at all (red).
	get_indicator: function (doc) {
		const today = frappe.datetime.get_today();
		const warn_date = frappe.datetime.add_days(today, 90);

		if (!doc.valid_to) {
			return [__("Expired"), "red", "valid_to,is,not set"];
		}
		if (doc.valid_to < today) {
			return [__("Expired"), "red", "valid_to,<," + today];
		}
		if (doc.valid_to <= warn_date) {
			return [__("Expiring"), "orange", "valid_to,<=," + warn_date];
		}
		return [__("Valid"), "green", "valid_to,>," + warn_date];
	},
};
