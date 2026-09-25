// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const S189_CONSULTATION_PY = "ir.industrial_relations.doctype.s189_consultation.s189_consultation";

frappe.ui.form.on("S189 Consultation", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.linked_intervention) {
			if (frm.doc.is_bulk_consultation) {
				frm.add_custom_button(__("Populate Attendees from Process"), () => populate_attendees(frm));
			}
			frm.add_custom_button(__("Populate Union Attendees"), () => populate_union_attendees(frm));
		}
	},

	is_bulk_consultation(frm) {
		if (frm.doc.is_bulk_consultation && frm.doc.linked_intervention && !(frm.doc.attendees || []).length) {
			populate_attendees(frm);
		}
	},

	linked_intervention(frm) {
		if (!frm.doc.linked_intervention) return;

		frappe.db.get_value("Retrenchment Process", frm.doc.linked_intervention, "company").then((r) => {
			const company = r.message && r.message.company;
			if (!company) return;
			frm.set_value("company", company);
			frappe.call({
				method: "ir.industrial_relations.doctype.retrenchment_process.retrenchment_process.fetch_default_letter_head",
				args: { company },
				callback(res) {
					frm.set_value("letter_head", res.message || "");
				},
			});
		});

		if (frm.doc.is_bulk_consultation && !(frm.doc.attendees || []).length) {
			populate_attendees(frm);
		}
	},
});

function populate_attendees(frm) {
	if (!frm.doc.linked_intervention) return;

	frappe.call({
		method: `${S189_CONSULTATION_PY}.populate_attendees`,
		args: { retrenchment_process: frm.doc.linked_intervention },
		freeze: true,
		freeze_message: __("Populating Attendees ..."),
		callback(r) {
			const rows = r.message || [];
			// Only replace Employee-type rows - Trade Union/Other attendees
			// added separately must survive a re-run of this button.
			(frm.doc.attendees || [])
				.filter((row) => row.attendee_type === "Employee")
				.forEach((row) => {
					const grid_row = frm.fields_dict.attendees.grid.grid_rows_by_docname[row.name];
					if (grid_row) grid_row.remove();
				});
			rows.forEach((row) => {
				const child = frm.add_child("attendees");
				Object.assign(child, row);
			});
			frm.refresh_field("attendees");
		},
	});
}

function populate_union_attendees(frm) {
	if (!frm.doc.linked_intervention) return;

	frappe.call({
		method: `${S189_CONSULTATION_PY}.populate_union_attendees`,
		args: { retrenchment_process: frm.doc.linked_intervention },
		freeze: true,
		freeze_message: __("Populating Union Attendees ..."),
		callback(r) {
			const rows = r.message || [];
			if (!rows.length) return;

			const existing = new Set(
				(frm.doc.attendees || [])
					.filter((row) => row.attendee_type === "Trade Union")
					.map((row) => row.trade_union)
			);
			rows.forEach((row) => {
				if (existing.has(row.trade_union)) return;
				const child = frm.add_child("attendees");
				Object.assign(child, row);
			});
			frm.refresh_field("attendees");
		},
	});
}
