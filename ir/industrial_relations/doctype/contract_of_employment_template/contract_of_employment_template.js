// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const COE_TEMPLATE_METHOD =
	"ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template";

frappe.ui.form.on("Contract of Employment Template", {
	async refresh(frm) {
		await frappe.require("coe_template_editor.bundle.js");
		const editor = await ir.coe_template_editor.attach(frm);
		editor.on_after_change = frappe.utils.debounce(() => sync_markdown_from_editor(frm), 600);

		frm.add_custom_button(__("Preview"), () => show_preview(frm, editor.config));
	},

	// Markdown tab -> editor, unless this change is the editor's own echo.
	contract_markdown: frappe.utils.debounce((frm) => {
		const markdown = frm.doc.contract_markdown || "";
		if (markdown === frm.__coe_markdown_from_editor || frm.doc.docstatus !== 0) return;
		frappe
			.xcall(`${COE_TEMPLATE_METHOD}.markdown_to_wording`, { contract_markdown: markdown })
			.then(({ contract_wording, errors }) => {
				const editor = frm.__coe_editor;
				if (editor) {
					editor.set_value(contract_wording);
					editor.last_synced = contract_wording;
				}
				frm.set_value("contract_wording", contract_wording);
				frm.dashboard.clear_comment();
				if (errors.length) {
					frm.dashboard.add_comment(errors.join("<br>"), "orange", true);
				}
			});
	}, 800),
});

function sync_markdown_from_editor(frm) {
	frappe
		.xcall(`${COE_TEMPLATE_METHOD}.wording_to_markdown`, { contract_wording: frm.doc.contract_wording })
		.then((markdown) => {
			frm.__coe_markdown_from_editor = markdown;
			if (markdown !== frm.doc.contract_markdown) frm.set_value("contract_markdown", markdown);
		});
}

// One sample contract at a time: placeholders for every value, a chosen pay
// basis / retirement / working hours, and the earnings and deductions it has.
function show_preview(frm, config) {
	const earnings = config.earning_components || [];
	const deductions = config.deduction_components || [];
	const pick = (wanted, available) => wanted.filter((c) => available.includes(c));

	const dialog = new frappe.ui.Dialog({
		title: __("Preview: {0}", [frm.doc.contract_name || __("New Template")]),
		size: "extra-large",
		fields: [
			{
				fieldtype: "Link",
				fieldname: "shift_design",
				label: __("Shift Design"),
				options: "Shift Design",
				description: __("Optional: use a real roster's hours."),
			},
			{
				fieldtype: "Select",
				fieldname: "working_hours",
				label: __("Working Hours"),
				options: [
					{ value: "fixed", label: __("Fixed shift") },
					{ value: "rotating", label: __("Rotating shift") },
				],
				default: "fixed",
				depends_on: "eval:!doc.shift_design",
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "Select",
				fieldname: "pay_basis",
				label: __("Pay Basis"),
				options: [
					{ value: "hourly", label: __("Hourly rate") },
					{ value: "monthly", label: __("Monthly salary") },
				],
				default: "hourly",
			},
			{
				fieldtype: "Select",
				fieldname: "retirement",
				label: __("Retirement Age"),
				options: [
					{ value: "yes", label: __("Has a retirement age") },
					{ value: "no", label: __("No retirement age") },
				],
				default: "yes",
			},
			{ fieldtype: "Column Break" },
			{
				fieldtype: "MultiSelectList",
				fieldname: "earnings",
				label: __("Earnings"),
				get_data: (txt) => options_for(earnings, txt),
				default: pick(["Housing Allowance", "Shift Allowance", "Safety Bonus"], earnings),
			},
			{
				fieldtype: "MultiSelectList",
				fieldname: "deductions",
				label: __("Deductions"),
				get_data: (txt) => options_for(deductions, txt),
				default: pick(["UIF Employee Contribution", "PAYE", "Employee Provident Fund"], deductions),
			},
			{ fieldtype: "Section Break" },
			{ fieldtype: "HTML", fieldname: "preview" },
		],
	});

	const render = frappe.utils.debounce(() => {
		const scenario = dialog.get_values(true);
		frappe
			.xcall(`${COE_TEMPLATE_METHOD}.preview_wording`, {
				contract_wording: frm.doc.contract_wording,
				scenario,
			})
			.then((html) => dialog.fields_dict.preview.$wrapper.html(html));
	}, 300);
	Object.values(dialog.fields_dict).forEach((field) => {
		if (field.df.fieldname !== "preview") field.df.onchange = render;
	});
	dialog.show();
	render();
}

function options_for(components, txt) {
	const term = (txt || "").toLowerCase();
	return components
		.filter((c) => !term || c.toLowerCase().includes(term))
		.map((c) => ({ value: c, description: "" }));
}
