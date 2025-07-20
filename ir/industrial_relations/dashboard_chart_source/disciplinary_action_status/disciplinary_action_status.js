// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

(function waitForFrappeDashboardSources() {
	if (frappe.dashboard_chart_sources) {
		frappe.dashboard_chart_sources["Disciplinary Action Status"] = {
			method: "get"
		};
	} else {
		setTimeout(waitForFrappeDashboardSources, 100);
	}
})();
