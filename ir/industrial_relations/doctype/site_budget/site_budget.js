// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Site Budget", {
	refresh(frm) {
		render_budget_summary(frm);
		render_roster_calendar(frm);
		add_export_button(frm);
	},
	// Both previews read saved doc state, so they can't actually recompute
	// until the change is saved - but re-running them here means that's
	// communicated immediately (via the "Save to refresh" message) instead
	// of the previews just silently sitting stale until the next refresh.
	site_organogram(frm) {
		render_budget_summary(frm);
		render_roster_calendar(frm);
	},
	from_date(frm) {
		render_budget_summary(frm);
		render_roster_calendar(frm);
	},
	end_date(frm) {
		render_budget_summary(frm);
		render_roster_calendar(frm);
	},
});

function add_export_button(frm) {
	if (frm.doc.__islocal || !frm.doc.site_organogram) {
		return;
	}
	frm.add_custom_button(__("Budget Summary (Excel)"), () => {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the Site Budget before exporting."));
			return;
		}
		open_url_post(
			"/api/method/ir.industrial_relations.doctype.site_budget.site_budget.export_site_budget_summary_xlsx",
			{ site_budget: frm.doc.name }
		);
	}, __("Export"));
}

function render_budget_summary(frm) {
	const $wrapper = frm.fields_dict.budget_summary_preview.$wrapper;
	// The summary reads the doc's *saved* state (designation_costs,
	// site_organogram, from_date/end_date), so it can only be accurate once
	// those are actually saved - showing it against unsaved edits would look
	// live but silently be stale. Prompt a save instead of guessing.
	if (frm.doc.__islocal || !frm.doc.site_organogram) {
		$wrapper.html("");
		return;
	}
	if (frm.is_dirty()) {
		$wrapper.html('<p class="text-muted">Save to refresh the budget summary.</p>');
		return;
	}
	frappe.call({
		method: "ir.industrial_relations.doctype.site_budget.site_budget.get_site_budget_summary_html",
		args: { site_budget: frm.doc.name },
		callback(r) {
			$wrapper.html(r.message || "");
		},
	});
}

function render_roster_calendar(frm) {
	const $wrapper = frm.fields_dict.roster_calendar_preview.$wrapper;
	// Same rationale as render_budget_summary(): this reads the doc's saved
	// site_organogram/from_date/end_date, so it needs a save first.
	if (frm.doc.__islocal || !frm.doc.site_organogram) {
		$wrapper.html("");
		return;
	}
	if (frm.is_dirty()) {
		$wrapper.html('<p class="text-muted">Save to refresh the shift roster calendar.</p>');
		return;
	}
	frappe.call({
		method: "ir.industrial_relations.doctype.site_budget.site_budget.get_site_budget_roster_calendar_html",
		args: { site_budget: frm.doc.name },
		callback(r) {
			$wrapper.html(r.message || "");
		},
	});
}
