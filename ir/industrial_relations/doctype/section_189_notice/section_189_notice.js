// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SECTION_189_NOTICE_PY = "ir.industrial_relations.doctype.section_189_notice.section_189_notice";

frappe.ui.form.on("Section 189 Notice", {
	refresh(frm) {
		if (frm.doc.linked_intervention && !frm.doc.linked_intervention_processed) {
			frm.trigger("linked_intervention");
		}

		if (frm.doc.docstatus === 0 && !frm.doc.__islocal && frm.doc.linked_intervention) {
			frm.add_custom_button(__("Pull from Process"), () => pull_from_process(frm));
			frm.add_custom_button(__("Populate Recipients"), () => populate_recipients(frm));
			frm.add_custom_button(__("Populate Union Recipients"), () => populate_union_recipients(frm));
		}
	},

	linked_intervention(frm) {
		if (!frm.doc.linked_intervention) return;
		pull_from_process(frm, { silent: true });
		populate_recipients(frm, { silent: true });
		populate_union_recipients(frm, { silent: true });
		frm.set_value("linked_intervention_processed", 1);
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.call({
			method: "ir.industrial_relations.doctype.retrenchment_process.retrenchment_process.fetch_default_letter_head",
			args: { company: frm.doc.company },
			callback(r) {
				frm.set_value("letter_head", r.message || "");
			},
		});
	},

	before_submit(frm) {
		if (!(frm.doc.recipients || []).length) {
			frappe.msgprint(__("Add at least one Recipient before submitting this Notice."));
			frappe.validated = false;
		}
	},
});

function pull_from_process(frm, { silent = false } = {}) {
	if (!frm.doc.linked_intervention) return;

	frappe.call({
		method: `${SECTION_189_NOTICE_PY}.fetch_from_process`,
		args: { retrenchment_process: frm.doc.linked_intervention },
		freeze: !silent,
		freeze_message: __("Pulling from Retrenchment Process ..."),
		callback(r) {
			const data = r.message || {};
			const designation_breakdown = data.designation_breakdown;
			delete data.designation_breakdown;

			Object.entries(data).forEach(([fieldname, value]) => {
				if (frm.fields_dict[fieldname]) {
					frm.set_value(fieldname, value);
				}
			});

			frm.clear_table("designation_breakdown");
			(designation_breakdown || []).forEach((row) => {
				const child = frm.add_child("designation_breakdown");
				Object.assign(child, row);
			});
			frm.refresh_field("designation_breakdown");
		},
	});
}

function populate_recipients(frm, { silent = false } = {}) {
	if (!frm.doc.linked_intervention) return;

	frappe.call({
		method: `${SECTION_189_NOTICE_PY}.populate_recipients`,
		args: { retrenchment_process: frm.doc.linked_intervention },
		freeze: !silent,
		freeze_message: __("Populating Recipients ..."),
		callback(r) {
			const rows = r.message || [];
			// Only replace Employee-type rows - Trade Union/Other recipients
			// added separately (via "Populate Union Recipients" or added by
			// hand) must survive a re-run of this button.
			(frm.doc.recipients || [])
				.filter((row) => row.recipient_type === "Employee")
				.forEach((row) => {
					const grid_row = frm.fields_dict.recipients.grid.grid_rows_by_docname[row.name];
					if (grid_row) grid_row.remove();
				});
			rows.forEach((row) => {
				const child = frm.add_child("recipients");
				Object.assign(child, row);
			});
			frm.refresh_field("recipients");
		},
	});
}

function populate_union_recipients(frm, { silent = false } = {}) {
	if (!frm.doc.linked_intervention) return;

	frappe.call({
		method: `${SECTION_189_NOTICE_PY}.populate_union_recipients`,
		args: { retrenchment_process: frm.doc.linked_intervention },
		freeze: !silent,
		freeze_message: __("Populating Union Recipients ..."),
		callback(r) {
			const rows = r.message || [];
			if (!rows.length) return;

			const existing = new Set(
				(frm.doc.recipients || [])
					.filter((row) => row.recipient_type === "Trade Union")
					.map((row) => row.trade_union)
			);
			rows.forEach((row) => {
				if (existing.has(row.trade_union)) return;
				const child = frm.add_child("recipients");
				Object.assign(child, row);
			});
			frm.refresh_field("recipients");
		},
	});
}
