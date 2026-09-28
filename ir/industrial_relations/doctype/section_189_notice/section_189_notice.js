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
		}
	},

	linked_intervention(frm) {
		if (!frm.doc.linked_intervention) return;
		pull_from_process(frm, { silent: true });
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

frappe.ui.form.on("Section 189 Notice Recipient", {
	recipient_type(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		frappe.model.set_value(cdt, cdn, "union_official_row", "");
		frappe.model.set_value(cdt, cdn, "union_region_row", "");
		if (row.recipient_type !== "Other") {
			frappe.model.set_value(cdt, cdn, "contact_name", "");
			frappe.model.set_value(cdt, cdn, "contact_email", "");
		}
	},

	trade_union(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "union_official_row", "");
		frappe.model.set_value(cdt, cdn, "union_region_row", "");
		frappe.model.set_value(cdt, cdn, "contact_name", "");
		frappe.model.set_value(cdt, cdn, "contact_email", "");
	},

	select_union_contact(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.trade_union) {
			frappe.msgprint(__("Select a Trade Union first."));
			return;
		}

		const is_region = row.recipient_type === "Union Region";
		frappe.call({
			method: `${SECTION_189_NOTICE_PY}.${is_region ? "get_union_regions" : "get_union_officials"}`,
			args: { trade_union: row.trade_union },
			freeze: true,
			callback(r) {
				const options = r.message || [];
				if (!options.length) {
					frappe.msgprint(
						is_region
							? __("{0} has no Regional/Area Offices on file.", [row.trade_union])
							: __("{0} has no Officials on file.", [row.trade_union])
					);
					return;
				}

				const dialog = new frappe.ui.Dialog({
					title: is_region ? __("Select Regional/Area Office") : __("Select Official"),
					fields: [
						{
							fieldname: "contact_row",
							fieldtype: "Autocomplete",
							label: is_region ? __("Regional/Area Office") : __("Official"),
							reqd: 1,
							options: options.map((o) => ({
								value: o.name,
								label: is_region
									? `${o.region_name}${o.region_contact_name ? " - " + o.region_contact_name : ""}`
									: `${o.of_name}${o.of_pos ? " - " + o.of_pos : ""}`,
							})),
						},
					],
					primary_action_label: __("Select"),
					primary_action(values) {
						const picked = options.find((o) => o.name === values.contact_row);
						if (!picked) {
							dialog.hide();
							return;
						}
						if (is_region) {
							frappe.model.set_value(cdt, cdn, "union_region_row", picked.name);
							frappe.model.set_value(cdt, cdn, "contact_name", picked.region_name);
							frappe.model.set_value(cdt, cdn, "contact_email", picked.region_mail || "");
						} else {
							frappe.model.set_value(cdt, cdn, "union_official_row", picked.name);
							frappe.model.set_value(cdt, cdn, "contact_name", picked.of_name);
							frappe.model.set_value(cdt, cdn, "contact_email", picked.of_mail || "");
						}
						dialog.hide();
					},
				});
				dialog.show();
			},
		});
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
