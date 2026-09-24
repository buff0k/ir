// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const RETRENCHMENT_PROCESS_PY = "ir.industrial_relations.doctype.retrenchment_process.retrenchment_process";
const RETRENCHMENT_COSTING_PY = "ir.industrial_relations.doctype.retrenchment_process.retrenchment_costing";
const COSTING_DAYS_PER_MONTH = 21.66667;
const COSTING_WEEKS_PER_MONTH = 4.333;

frappe.ui.form.on("Retrenchment Process", {
	onload(frm) {
		frm.set_query("employee", "affected_employees", () => ({
			filters: { status: "Active", company: frm.doc.company || undefined },
		}));
	},

	refresh(frm) {
		render_linked_docs(frm);
		render_guidance(frm);
		render_affected_status(frm);
		render_designation_breakdown(frm);
		render_union_membership(frm);
		render_costing_editor(frm);

		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Add Employees from Branch(es)/Designation(s)"), () => add_employees_from_branches(frm));
		}

		if (frm.doc.docstatus === 0 && !frm.doc.__islocal) {
			frm.add_custom_button(
				__("Section 189 Notice"),
				() => create_generic_child_doc(frm, "Section 189 Notice"),
				__("Create")
			);
			frm.add_custom_button(
				__("S189 Consultation"),
				() => create_generic_child_doc(frm, "S189 Consultation"),
				__("Create")
			);
		}
	},

	after_save(frm) {
		render_linked_docs(frm);
		render_affected_status(frm);
		render_designation_breakdown(frm);
		render_union_membership(frm);
		render_costing_editor(frm);
	},

	company(frm) {
		if (!frm.doc.company) return;
		frappe.call({
			method: `${RETRENCHMENT_PROCESS_PY}.fetch_default_letter_head`,
			args: { company: frm.doc.company },
			callback(r) {
				frm.set_value("letter_head", r.message || "");
			},
		});
		render_guidance(frm);
	},

	process_type(frm) {
		render_guidance(frm);
	},

	proposed_implementation_date(frm) {
		render_guidance(frm);
	},

	override_prior_dismissals_12m(frm) {
		render_guidance(frm);
	},

	prior_operational_dismissals_12m(frm) {
		if (frm.doc.override_prior_dismissals_12m) render_guidance(frm);
	},

	severance_weeks_per_completed_year(frm) {
		recompute_all_costing_rows(frm);
	},

	severance_hours_per_week(frm) {
		recompute_all_costing_rows(frm);
	},

	minimum_severance_weeks(frm) {
		recompute_all_costing_rows(frm);
	},
});

frappe.ui.form.on("Retrenchment Affected Employee", {
	affected_employees_add(frm) {
		render_guidance(frm);
	},
	affected_employees_remove(frm) {
		render_guidance(frm);
	},
	employee(frm) {
		render_guidance(frm);
	},
	inclusion_status(frm) {
		render_guidance(frm);
	},
	create_dismissal_form(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.employee) {
			frappe.msgprint(__("Select an Employee on this row before creating a Dismissal Form."));
			return;
		}
		if (row.outcome) {
			frappe.msgprint(__("A dismissal outcome has already been recorded for this row."));
			return;
		}
		if (frm.doc.__unsaved) {
			frappe.msgprint(__("Save the Retrenchment Process before creating a Dismissal Form."));
			return;
		}

		frappe.call({
			method:
				"ir.industrial_relations.doctype.dismissal_form.dismissal_form.create_dismissal_form",
			args: {
				source_name: frm.doc.name,
				source_doctype: frm.doctype,
				employee: row.employee,
			},
			freeze: true,
			freeze_message: __("Creating Dismissal Form ..."),
			callback(r) {
				if (!r.exc && r.message) {
					frappe.model.sync(r.message);
					frappe.set_route("Form", "Dismissal Form", r.message.name);
				}
			},
		});
	},
	create_termination_form(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!row.employee) {
			frappe.msgprint(__("Select an Employee on this row before creating a Termination Form."));
			return;
		}
		if (row.termination_form) {
			frappe.msgprint(__("A Termination Form already exists for this row."));
			return;
		}
		if (frm.doc.__unsaved) {
			frappe.msgprint(__("Save the Retrenchment Process before creating a Termination Form."));
			return;
		}

		frappe.call({
			method:
				"ir.industrial_relations.doctype.termination_form.termination_form.create_termination_form",
			args: {
				source_name: frm.doc.name,
				source_doctype: frm.doctype,
				employee: row.employee,
			},
			freeze: true,
			freeze_message: __("Creating Termination Form ..."),
			callback(r) {
				if (!r.exc && r.message) {
					frappe.model.sync(r.message);
					frappe.set_route("Form", "Termination Form", r.message.name);
				}
			},
		});
	},
});

function is_affected_row(row) {
	return !row.inclusion_status || row.inclusion_status === "Affected";
}

function create_generic_child_doc(frm, target_doctype) {
	if (frm.doc.__unsaved) {
		frappe.msgprint(__("Save the Retrenchment Process first."));
		return;
	}

	frappe.model.with_doctype(target_doctype, () => {
		const doc = frappe.model.get_new_doc(target_doctype);
		doc.ir_intervention = "Retrenchment Process";
		doc.linked_intervention = frm.doc.name;
		frappe.set_route("Form", target_doctype, doc.name);
	});
}

function add_employees_from_branches(frm) {
	if (!frm.doc.company) {
		frappe.msgprint(__("Select a Company first."));
		return;
	}

	const dialog = new frappe.ui.Dialog({
		title: __("Add Employees from Branch(es) / Designation(s)"),
		fields: [
			{
				fieldname: "branches",
				label: __("Branches (optional - leave blank for every Branch)"),
				fieldtype: "MultiSelectList",
				get_data: (txt) => frappe.db.get_link_options("Branch", txt),
			},
			{
				fieldname: "designations",
				label: __("Designations (optional - leave blank for every Designation)"),
				fieldtype: "MultiSelectList",
				get_data: (txt) => frappe.db.get_link_options("Designation", txt),
			},
			{
				fieldname: "hint",
				fieldtype: "HTML",
				options: `<div class="text-muted small">${__(
					"At least one of Branches or Designations is required. Only Active Employees in {0} are matched.",
					[frappe.utils.escape_html(frm.doc.company)]
				)}</div>`,
			},
		],
		primary_action_label: __("Add"),
		primary_action(values) {
			frappe.call({
				method: `${RETRENCHMENT_PROCESS_PY}.get_employees_for_branches`,
				args: { company: frm.doc.company, branches: values.branches, designations: values.designations },
				freeze: true,
				freeze_message: __("Loading Employees ..."),
				callback(r) {
					const rows = r.message || [];

					const apply_rows = () => {
						const existing = new Set((frm.doc.affected_employees || []).map((row) => row.employee).filter(Boolean));
						let added = 0;
						let skipped = 0;

						rows.forEach((row) => {
							if (existing.has(row.employee)) {
								skipped += 1;
								return;
							}
							const child = frm.add_child("affected_employees");
							Object.assign(child, row);
							existing.add(row.employee);
							added += 1;
						});

						frm.refresh_field("affected_employees");
						render_guidance(frm);
						dialog.hide();

						frappe.msgprint(
							__("Added {0} employee(s). {1} already on the table were skipped.", [added, skipped])
						);
					};

					if (rows.length > 100) {
						frappe.confirm(
							__("This will add {0} employees to Affected Employees. Continue?", [rows.length]),
							apply_rows
						);
					} else {
						apply_rows();
					}
				},
			});
		},
	});

	dialog.show();
}

function render_linked_docs(frm) {
	if (!frm.fields_dict.linked_docs) return;

	frappe.call({
		method: `${RETRENCHMENT_PROCESS_PY}.get_linked_docs_html`,
		args: { process_name: frm.doc.name || "" },
		callback(r) {
			frm.get_field("linked_docs").$wrapper.html(r.message || "");
		},
	});
}

function render_guidance(frm) {
	if (!frm.fields_dict.s189a_guidance) return;

	const $wrapper = frm.get_field("s189a_guidance").$wrapper;
	if (!frm.doc.company) {
		$wrapper.html(`<div class="text-muted">${__("Select a Company to see Section 189A threshold guidance.")}</div>`);
		return;
	}

	const contemplated_count = (frm.doc.affected_employees || []).filter(
		(row) => row.employee && is_affected_row(row)
	).length;

	frappe.call({
		method: `${RETRENCHMENT_PROCESS_PY}.get_189a_guidance`,
		args: {
			company: frm.doc.company,
			contemplated_count,
			reference_date: frm.doc.proposed_implementation_date || "",
			manual_prior_dismissals: frm.doc.override_prior_dismissals_12m
				? frm.doc.prior_operational_dismissals_12m
				: undefined,
		},
		callback(r) {
			const data = r.message || {};
			const color = data.meets_threshold ? "yellow" : "green";
			$wrapper.html(`
				<div class="form-message ${color}">
					<div>${frappe.utils.escape_html(data.message || "")}</div>
				</div>
			`);
		},
	});
}

function render_designation_breakdown(frm) {
	if (!frm.fields_dict.affected_designations_status) return;

	const $wrapper = frm.get_field("affected_designations_status").$wrapper;

	if (frm.doc.__islocal || !frm.doc.name) {
		$wrapper.html(`<div class="text-muted">${__("Save the Retrenchment Process to see the Designation breakdown here.")}</div>`);
		return;
	}

	frappe.call({
		method: `${RETRENCHMENT_PROCESS_PY}.get_designation_breakdown`,
		args: { process_name: frm.doc.name },
		callback(r) {
			const rows = r.message || [];
			if (!rows.length) {
				$wrapper.html(`<div class="text-muted">${__("No named employees on this process yet.")}</div>`);
				return;
			}

			$wrapper.html(`
				<table class="table table-bordered" style="margin-top: 6px;">
					<thead>
						<tr>
							<th>${__("Designation")}</th>
							<th>${__("Initial")}</th>
							<th>${__("Current")}</th>
							<th>${__("Dismissed")}</th>
							<th>${__("Excluded / Transferred")}</th>
						</tr>
					</thead>
					<tbody>
						${rows
							.map(
								(row) => `
								<tr>
									<td>${frappe.utils.escape_html(row.designation)}</td>
									<td>${row.initial}</td>
									<td>${row.current}</td>
									<td>${row.dismissed}</td>
									<td>${row.excluded}</td>
								</tr>
							`
							)
							.join("")}
					</tbody>
				</table>
			`);
		},
	});
}

function render_union_membership(frm) {
	if (!frm.fields_dict.union_membership_status) return;

	const $wrapper = frm.get_field("union_membership_status").$wrapper;

	if (frm.doc.__islocal || !frm.doc.name) {
		$wrapper.html(`<div class="text-muted">${__("Save the Retrenchment Process to see Trade Union membership here.")}</div>`);
		return;
	}

	frappe.call({
		method: `${RETRENCHMENT_PROCESS_PY}.get_union_membership_summary`,
		args: { process_name: frm.doc.name },
		callback(r) {
			const unions = r.message || [];
			if (!unions.length) {
				$wrapper.html(`<div class="text-muted">${__("No affected employees are recorded as Trade Union members.")}</div>`);
				return;
			}

			$wrapper.html(`
				<div class="form-message yellow">
					<div>${__("The following Trade Union(s) have members among the affected employees. Per s189, each must be notified as a recipient in its own right - use \"Populate Union Recipients\" on the Section 189 Notice.")}</div>
				</div>
				<table class="table table-bordered" style="margin-top: 6px;">
					<thead>
						<tr>
							<th>${__("Trade Union")}</th>
							<th>${__("Members Affected")}</th>
							<th>${__("Registered Officials")}</th>
						</tr>
					</thead>
					<tbody>
						${unions
							.map((u) => {
								const members = u.employees.map((e) => frappe.utils.escape_html(e.employee_name || e.employee)).join(", ");
								const officials = u.officials.length
									? u.officials
											.map((o) => `${frappe.utils.escape_html(o.of_name || "")} (${frappe.utils.escape_html(o.of_mail || __("no email on file"))})`)
											.join("; ")
									: `<span class="text-muted">${__("None registered")}</span>`;
								return `
									<tr>
										<td><a href="/app/trade-union/${encodeURIComponent(u.trade_union)}">${frappe.utils.escape_html(u.trade_union)}</a></td>
										<td>${members}</td>
										<td>${officials}</td>
									</tr>
								`;
							})
							.join("")}
					</tbody>
				</table>
			`);
		},
	});
}

function costing_flt(v) {
	const n = parseFloat(v);
	return isNaN(n) ? 0 : n;
}

function frm_currency() {
	return frappe.defaults.get_default("currency");
}

function costing_datediff_years(from_date, to_date) {
	const f = frappe.datetime.str_to_obj(from_date);
	const t = frappe.datetime.str_to_obj(to_date);
	let years = t.getFullYear() - f.getFullYear();
	if (t.getMonth() < f.getMonth() || (t.getMonth() === f.getMonth() && t.getDate() < f.getDate())) {
		years -= 1;
	}
	return Math.max(years, 0);
}

function costing_datediff_months(from_date, to_date) {
	const f = frappe.datetime.str_to_obj(from_date);
	const t = frappe.datetime.str_to_obj(to_date);
	let months = (t.getFullYear() - f.getFullYear()) * 12 + (t.getMonth() - f.getMonth());
	if (t.getDate() < f.getDate()) months -= 1;
	return Math.max(months, 0);
}

function recompute_row_client(frm, row) {
	const rate = costing_flt(row.rate_per_hour);
	const hours_per_day = costing_flt(row.hours_per_day) || 9;
	const total_allowances = (frm.doc.employee_allowances || [])
		.filter((a) => a.employee === row.employee)
		.reduce((sum, a) => sum + costing_flt(a.amount), 0);

	row.total_allowances = total_allowances;
	row.thirty_days_date = null;
	row.completed_years = 0;
	row.notice_weeks = 0;
	row.notice_ends_date = null;
	row.weekly_rate = 0;
	row.estimated_notice_pay = 0;
	row.estimated_severance_pay = 0;

	if (row.s189_notice_date && row.date_of_joining) {
		const thirty_days_date = frappe.datetime.add_days(row.s189_notice_date, 30);
		row.thirty_days_date = thirty_days_date;

		const completed_years = costing_datediff_years(row.date_of_joining, thirty_days_date);
		row.completed_years = completed_years;

		let notice_weeks = 0;
		if (completed_years >= 1) {
			notice_weeks = 4;
		} else if (costing_datediff_months(row.date_of_joining, thirty_days_date) >= 6) {
			notice_weeks = 2;
		}
		row.notice_weeks = notice_weeks;
		row.notice_ends_date = frappe.datetime.add_days(thirty_days_date, notice_weeks * 7);

		const hours_per_month = hours_per_day * COSTING_DAYS_PER_MONTH;
		const weekly_rate = (rate * hours_per_month + total_allowances) / COSTING_WEEKS_PER_MONTH;
		row.weekly_rate = weekly_rate;
		row.estimated_notice_pay = weekly_rate * notice_weeks;

		const weeks_per_year = costing_flt(row.severance_weeks_per_completed_year) || costing_flt(frm.doc.severance_weeks_per_completed_year) || 1;
		const hours_per_week = costing_flt(row.severance_hours_per_week) || costing_flt(frm.doc.severance_hours_per_week) || 45;
		const min_weeks = costing_flt(row.minimum_severance_weeks) || costing_flt(frm.doc.minimum_severance_weeks) || 0;
		const effective_weeks = Math.max(completed_years * weeks_per_year, min_weeks);
		row.estimated_severance_pay = effective_weeks * hours_per_week * rate;
	}

	row.estimated_leave_pay = rate * hours_per_day * costing_flt(row.leave_days_projected);
	row.estimated_total_cost = row.estimated_notice_pay + row.estimated_severance_pay + row.estimated_leave_pay;
}

function recompute_all_costing_rows(frm) {
	(frm.doc.affected_employees || [])
		.filter((row) => row.employee)
		.forEach((row) => recompute_row_client(frm, row));

	set_total_retrenchment_cost(
		frm,
		(frm.doc.affected_employees || [])
			.filter((row) => row.employee)
			.reduce((sum, row) => sum + costing_flt(row.estimated_total_cost), 0)
	);

	render_costing_editor(frm);
}

function set_total_retrenchment_cost(frm, total) {
	frm.doc.estimated_total_retrenchment_cost = total;
	// frm.doc is mutated directly (not via frm.set_value) everywhere in this
	// live-recompute path to avoid marking the form dirty on every keystroke -
	// but that also means the standalone read-only field widget in the
	// Costing Parameters section never repaints on its own; refresh_field
	// forces it to reflect the value frm.doc already has.
	if (frm.fields_dict.estimated_total_retrenchment_cost) {
		frm.refresh_field("estimated_total_retrenchment_cost");
	}
}

function allowance_summary_html(frm, employee) {
	const rows = (frm.doc.employee_allowances || []).filter((a) => a.employee === employee);
	if (!rows.length) {
		return `<span class="text-muted">${__("None")}</span>`;
	}
	return rows
		.map((a) => `${frappe.utils.escape_html(a.salary_component)}: ${format_currency(costing_flt(a.amount), frm_currency())}`)
		.join(", ");
}

function costing_row_html(frm, row) {
	return `
		<tr data-row="${row.name}" data-employee="${frappe.utils.escape_html(row.employee)}">
			<td>${frappe.utils.escape_html(row.employee_name || row.employee)}</td>
			<td><input type="number" step="0.01" class="form-control input-sm" data-field="rate_per_hour" value="${row.rate_per_hour || ""}"></td>
			<td><input type="number" step="0.5" class="form-control input-sm" data-field="hours_per_day" value="${row.hours_per_day || 9}"></td>
			<td><input type="date" class="form-control input-sm" data-field="s189_notice_date" value="${row.s189_notice_date || ""}"></td>
			<td><input type="number" step="0.5" class="form-control input-sm" data-field="leave_days_balance" value="${row.leave_days_balance || ""}"></td>
			<td><input type="number" step="0.5" class="form-control input-sm" data-field="leave_days_projected" value="${row.leave_days_projected || ""}"></td>
			<td class="costing-allowances">
				${allowance_summary_html(frm, row.employee)}
				<a href="#" data-action="edit-allowances" class="ml-2">${__("Edit")}</a>
			</td>
			<td data-computed="weekly_rate">${format_currency(costing_flt(row.weekly_rate), frm_currency())}</td>
			<td data-computed="notice_weeks">${row.notice_weeks || 0}</td>
			<td data-computed="estimated_notice_pay">${format_currency(costing_flt(row.estimated_notice_pay), frm_currency())}</td>
			<td data-computed="estimated_severance_pay">${format_currency(costing_flt(row.estimated_severance_pay), frm_currency())}</td>
			<td data-computed="estimated_leave_pay">${format_currency(costing_flt(row.estimated_leave_pay), frm_currency())}</td>
			<td data-computed="estimated_total_cost"><strong>${format_currency(costing_flt(row.estimated_total_cost), frm_currency())}</strong></td>
			<td><button class="btn btn-xs btn-default" data-action="fetch-row">${__("Fetch")}</button></td>
		</tr>
	`;
}

function render_costing_editor(frm) {
	if (!frm.fields_dict.costing_editor) return;

	const $wrapper = frm.get_field("costing_editor").$wrapper;

	if (frm.doc.__islocal || !frm.doc.name) {
		$wrapper.html(`<div class="text-muted">${__("Save the Retrenchment Process to edit employee costing here.")}</div>`);
		return;
	}

	const rows = (frm.doc.affected_employees || []).filter((row) => row.employee);
	if (!rows.length) {
		$wrapper.html(`<div class="text-muted">${__("No named employees on this process yet.")}</div>`);
		return;
	}

	rows.forEach((row) => recompute_row_client(frm, row));
	set_total_retrenchment_cost(frm, rows.reduce((sum, row) => sum + costing_flt(row.estimated_total_cost), 0));

	$wrapper.html(`
		<div style="margin-bottom: 8px;">
			<button class="btn btn-sm btn-default" data-action="fetch-all">${__("Fetch All from Payroll/Leave")}</button>
		</div>
		<div style="overflow-x: auto;">
			<table class="table table-bordered table-sm" style="min-width: 1400px;">
				<thead>
					<tr>
						<th>${__("Employee")}</th>
						<th style="width:90px;">${__("Rate/Hr")}</th>
						<th style="width:80px;">${__("Hrs/Day")}</th>
						<th style="width:130px;">${__("S189 Notice Date")}</th>
						<th style="width:90px;">${__("Leave Bal.")}</th>
						<th style="width:90px;">${__("Leave Proj.")}</th>
						<th>${__("Allowances")}</th>
						<th style="width:90px;">${__("Wkly Rate")}</th>
						<th style="width:60px;">${__("Notice Wks")}</th>
						<th style="width:100px;">${__("Notice Pay")}</th>
						<th style="width:100px;">${__("Severance")}</th>
						<th style="width:100px;">${__("Leave Pay")}</th>
						<th style="width:110px;">${__("Total")}</th>
						<th style="width:60px;"></th>
					</tr>
				</thead>
				<tbody>
					${rows.map((row) => costing_row_html(frm, row)).join("")}
				</tbody>
				<tfoot>
					<tr>
						<td colspan="12" class="text-right"><strong>${__("Total Estimated Retrenchment Cost")}</strong></td>
						<td colspan="2"><strong data-total-cost>${format_currency(costing_flt(frm.doc.estimated_total_retrenchment_cost), frm_currency())}</strong></td>
					</tr>
				</tfoot>
			</table>
		</div>
	`);

	bind_costing_editor_events(frm, $wrapper);
}

function update_costing_row_dom($wrapper, row) {
	const $row = $wrapper.find(`tr[data-row="${row.name}"]`);
	if (!$row.length) return;

	$row.find('[data-computed="weekly_rate"]').text(format_currency(costing_flt(row.weekly_rate), frm_currency()));
	$row.find('[data-computed="notice_weeks"]').text(row.notice_weeks || 0);
	$row.find('[data-computed="estimated_notice_pay"]').text(format_currency(costing_flt(row.estimated_notice_pay), frm_currency()));
	$row.find('[data-computed="estimated_severance_pay"]').text(format_currency(costing_flt(row.estimated_severance_pay), frm_currency()));
	$row.find('[data-computed="estimated_leave_pay"]').text(format_currency(costing_flt(row.estimated_leave_pay), frm_currency()));
	$row.find('[data-computed="estimated_total_cost"]').html(`<strong>${format_currency(costing_flt(row.estimated_total_cost), frm_currency())}</strong>`);
}

function update_costing_totals_dom($wrapper, frm) {
	const total = (frm.doc.affected_employees || [])
		.filter((row) => row.employee)
		.reduce((sum, row) => sum + costing_flt(row.estimated_total_cost), 0);
	set_total_retrenchment_cost(frm, total);
	$wrapper.find("[data-total-cost]").text(format_currency(total, frm_currency()));
}

function bind_costing_editor_events(frm, $wrapper) {
	// $wrapper itself persists across re-renders (only its innerHTML is
	// replaced each time render_costing_editor runs), so delegated handlers
	// bound to it would otherwise stack up one more copy per re-render -
	// clear them first.
	$wrapper.off();

	$wrapper.find('[data-action="fetch-all"]').on("click", async () => {
		const rows = (frm.doc.affected_employees || []).filter((row) => row.employee);
		for (const row of rows) {
			await fetch_row_costing(frm, row.name, { silent: true });
		}
		render_costing_editor(frm);
	});

	$wrapper.on("click", '[data-action="fetch-row"]', (e) => {
		const row_name = $(e.currentTarget).closest("tr").data("row");
		fetch_row_costing(frm, row_name).then(() => render_costing_editor(frm));
	});

	$wrapper.on("click", '[data-action="edit-allowances"]', (e) => {
		e.preventDefault();
		const employee = $(e.currentTarget).closest("tr").data("employee");
		open_allowances_dialog(frm, employee);
	});

	$wrapper.on("change", "input[data-field]", (e) => {
		const $input = $(e.currentTarget);
		const row_name = $input.closest("tr").data("row");
		const fieldname = $input.data("field");
		const value = $input.val();

		frappe.model.set_value("Retrenchment Affected Employee", row_name, fieldname, value);
		frm.dirty();

		const row = (frm.doc.affected_employees || []).find((r) => r.name === row_name);
		if (!row) return;
		recompute_row_client(frm, row);
		update_costing_row_dom($wrapper, row);
		update_costing_totals_dom($wrapper, frm);
	});
}

function fetch_row_costing(frm, row_name, { silent = false } = {}) {
	const row = (frm.doc.affected_employees || []).find((r) => r.name === row_name);
	if (!row || !row.employee) return Promise.resolve();

	return frappe
		.call({
			method: `${RETRENCHMENT_COSTING_PY}.get_employee_cost_inputs`,
			args: { employee: row.employee },
			freeze: !silent,
			freeze_message: __("Fetching from Payroll/Leave ..."),
		})
		.then((r) => {
			const data = r.message || {};

			if (data.rate_per_hour !== null && data.rate_per_hour !== undefined) {
				frappe.model.set_value("Retrenchment Affected Employee", row_name, "rate_per_hour", data.rate_per_hour);
			}
			if (data.leave_days_balance !== null && data.leave_days_balance !== undefined) {
				frappe.model.set_value("Retrenchment Affected Employee", row_name, "leave_days_balance", data.leave_days_balance);
			}

			(data.allowances || []).forEach((a) => {
				const existing = (frm.doc.employee_allowances || []).find(
					(erow) => erow.employee === row.employee && erow.salary_component === a.salary_component
				);
				if (existing) {
					frappe.model.set_value("Retrenchment Employee Allowance", existing.name, "amount", a.amount);
				} else {
					const child = frm.add_child("employee_allowances");
					child.employee = row.employee;
					child.salary_component = a.salary_component;
					child.amount = a.amount;
				}
			});

			frm.dirty();
			frm.refresh_field("employee_allowances");
		});
}

function open_allowances_dialog(frm, employee) {
	const get_rows = () => (frm.doc.employee_allowances || []).filter((a) => a.employee === employee);

	const dialog = new frappe.ui.Dialog({
		title: __("Allowances for {0}", [employee]),
		fields: [
			{ fieldname: "rows_html", fieldtype: "HTML" },
			{ fieldname: "col_break_1", fieldtype: "Column Break" },
			{ fieldname: "new_component", fieldtype: "Link", options: "Salary Component", label: __("Component") },
			{ fieldname: "new_amount", fieldtype: "Currency", label: __("Amount") },
		],
		primary_action_label: __("Add"),
		primary_action() {
			const component = dialog.get_value("new_component");
			const amount = dialog.get_value("new_amount");
			if (!component) {
				frappe.msgprint(__("Select a Salary Component."));
				return;
			}
			const child = frm.add_child("employee_allowances");
			child.employee = employee;
			child.salary_component = component;
			child.amount = amount || 0;
			frm.dirty();
			frm.refresh_field("employee_allowances");
			dialog.set_value("new_component", "");
			dialog.set_value("new_amount", "");
			render_rows();
		},
	});

	function render_rows() {
		const rows = get_rows();
		const html = rows.length
			? `<table class="table table-bordered table-sm">
				<thead><tr><th>${__("Component")}</th><th>${__("Amount")}</th><th></th></tr></thead>
				<tbody>
					${rows
						.map(
							(r) => `
						<tr data-row="${r.name}">
							<td>${frappe.utils.escape_html(r.salary_component)}</td>
							<td>${format_currency(costing_flt(r.amount), frm_currency())}</td>
							<td><a href="#" data-action="remove-allowance">${__("Remove")}</a></td>
						</tr>
					`
						)
						.join("")}
				</tbody>
			</table>`
			: `<div class="text-muted">${__("No allowances yet.")}</div>`;

		dialog.fields_dict.rows_html.$wrapper.html(html);
		dialog.fields_dict.rows_html.$wrapper.find('[data-action="remove-allowance"]').on("click", (e) => {
			e.preventDefault();
			const row_name = $(e.currentTarget).closest("tr").data("row");
			const grid_row = frm.fields_dict.employee_allowances.grid.grid_rows_by_docname[row_name];
			if (grid_row) grid_row.remove();
			frm.dirty();
			frm.refresh_field("employee_allowances");
			render_rows();
		});
	}

	dialog.$wrapper.on("hidden.bs.modal", () => render_costing_editor(frm));

	dialog.show();
	render_rows();
}

function render_affected_status(frm) {
	if (!frm.fields_dict.affected_employees_status) return;

	const $wrapper = frm.get_field("affected_employees_status").$wrapper;

	if (frm.doc.__islocal || !frm.doc.name) {
		$wrapper.html(`<div class="text-muted">${__("Save the Retrenchment Process to see per-employee Notice / Dismissal status here.")}</div>`);
		return;
	}

	frappe.call({
		method: `${RETRENCHMENT_PROCESS_PY}.get_affected_employee_status`,
		args: { process_name: frm.doc.name },
		callback(r) {
			const rows = r.message || [];
			if (!rows.length) {
				$wrapper.html(`<div class="text-muted">${__("No named employees on this process yet.")}</div>`);
				return;
			}

			$wrapper.html(`
				<table class="table table-bordered" style="margin-top: 6px;">
					<thead>
						<tr>
							<th>${__("Employee")}</th>
							<th>${__("Branch")}</th>
							<th>${__("Status")}</th>
							<th>${__("Section 189 Notice")}</th>
							<th>${__("Dismissal Form")}</th>
							<th>${__("Termination Form")}</th>
						</tr>
					</thead>
					<tbody>
						${rows
							.map((row) => {
								const notice_cell = row.notice_served
									? __("Served {0}", [frappe.datetime.str_to_user(row.notice_date)])
									: `<span class="text-muted">${__("Not yet served")}</span>`;
								const dismissal_cell = row.dismissal_form
									? `<a href="/app/dismissal-form/${encodeURIComponent(row.dismissal_form)}">${frappe.utils.escape_html(row.dismissal_form)}</a> (${row.dismissal_status})`
									: `<span class="text-muted">${__("None")}</span>`;
								const termination_cell = row.termination_form
									? `<a href="/app/termination-form/${encodeURIComponent(row.termination_form)}">${frappe.utils.escape_html(row.termination_form)}</a>`
									: `<span class="text-muted">${__("None")}</span>`;
								return `
									<tr>
										<td>${frappe.utils.escape_html(row.employee_name || row.employee)}</td>
										<td>${frappe.utils.escape_html(row.branch || "")}</td>
										<td>${frappe.utils.escape_html(row.inclusion_status)}</td>
										<td>${notice_cell}</td>
										<td>${dismissal_cell}</td>
										<td>${termination_cell}</td>
									</tr>
								`;
							})
							.join("")}
					</tbody>
				</table>
			`);
		},
	});
}
