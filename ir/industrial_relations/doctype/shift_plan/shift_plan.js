// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shift Plan", {
	onload(frm) {
		set_default_values(frm);
	},

	refresh(frm) {
		add_shift_plan_buttons(frm);
		set_output_tables_read_only(frm);
		render_rotation_editor(frm);
		render_all_visual_blocks(frm);
	},

	operating_model(frm) {
		apply_operating_model_defaults(frm);
	},

	number_of_shift_teams(frm) {
		generate_team_labels(frm);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	},

	rotation_pattern_days(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	rotation_anchor_date(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	calendar_start_date(frm) {
		if (!frm.doc.rotation_anchor_date && frm.doc.calendar_start_date) {
			frm.set_value("rotation_anchor_date", frm.doc.calendar_start_date);
		}

		update_calendar_days(frm);
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	calendar_end_date(frm) {
		update_calendar_days(frm);
		render_full_calendar(frm);
	},

	default_shift_hours(frm) {
		if (!frm.doc.default_operating_hours) {
			frm.set_value("default_operating_hours", frm.doc.default_shift_hours || 0);
		}

		render_full_calendar(frm);
	},

	default_day_shift_hours(frm) {
		render_full_calendar(frm);
	},

	validate(frm) {
		update_calendar_days(frm);
		calculate_all_staffing_totals(frm);
	}
});

frappe.ui.form.on("Shift Plan Staffing", {
	employees_per_shift(frm, cdt, cdn) {
		calculate_staffing_total(frm, cdt, cdn);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	},

	number_of_shift_teams(frm, cdt, cdn) {
		calculate_staffing_total(frm, cdt, cdn);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	},

	cost_group(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	},

	working_hours(frm, cdt, cdn) {
		set_default_working_days(frm, cdt, cdn);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	},

	working_days(frm) {
		render_all_visual_blocks(frm);
	},

	fixed_cost_basis(frm, cdt, cdn) {
		if (!locals[cdt][cdn].fixed_cost_basis) {
			locals[cdt][cdn].fixed_cost_basis = "Per Selected Period";
			frm.refresh_field("employees");
		}
	}
});

frappe.ui.form.on("Shift Plan Rotation Pattern", {
	cost_group(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	pattern_day(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	team_label(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	shift_assignment(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	working_hours(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	},

	rotation_pattern_remove(frm) {
		render_rotation_editor_preserve_scroll(frm);
		render_full_calendar(frm);
	}
});

frappe.ui.form.on("Shift Plan Calendar", {
	date(frm) {
		render_full_calendar(frm);
	},

	day_type(frm) {
		render_full_calendar(frm);
	},

	planned_operating_hours(frm) {
		render_full_calendar(frm);
	},

	day_shift_required(frm) {
		render_full_calendar(frm);
	},

	night_shift_required(frm) {
		render_full_calendar(frm);
	},

	shift_calendar_remove(frm) {
		render_full_calendar(frm);
	}
});

frappe.ui.form.on("Shift Plan Team Output", {
	team_output_add(frm) {
		render_team_summary(frm);
	},

	team_output_remove(frm) {
		render_team_summary(frm);
	},

	period_label(frm) {
		render_team_summary(frm);
	},

	cost_group(frm) {
		render_team_summary(frm);
	},

	team_label(frm) {
		render_team_summary(frm);
	},

	ordinary_hours(frm) {
		render_team_summary(frm);
	},

	normal_overtime_hours(frm) {
		render_team_summary(frm);
	},

	sunday_hours(frm) {
		render_team_summary(frm);
	},

	public_holiday_hours(frm) {
		render_team_summary(frm);
	},

	total_overtime_hours(frm) {
		render_team_summary(frm);
	},

	total_hours(frm) {
		render_team_summary(frm);
	}
});

frappe.ui.form.on("Shift Plan Output", {
	output_add(frm) {
		render_output_summary(frm);
	},

	output_remove(frm) {
		render_output_summary(frm);
	},

	output_type(frm) {
		render_output_summary(frm);
	},

	cost_group(frm) {
		render_output_summary(frm);
	},

	designation(frm) {
		render_output_summary(frm);
	},

	total_cost(frm) {
		render_output_summary(frm);
	},

	overtime_percent_of_revenue(frm) {
		render_output_summary(frm);
	}
});

function add_shift_plan_buttons(frm) {
	frm.add_custom_button(__("Generate Team Labels"), function () {
		generate_team_labels(frm);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Apply Team Count to Staffing"), function () {
		apply_team_count_to_staffing(frm);
		render_rotation_editor_preserve_scroll(frm);
		render_all_visual_blocks(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Load 3D 3N 4O Pattern"), function () {
		load_rotation_preset(frm, "3D3N4O");
	}, __("Rotation"));

	frm.add_custom_button(__("Load 4D 4N 4O Pattern"), function () {
		load_rotation_preset(frm, "4D4N4O");
	}, __("Rotation"));

	frm.add_custom_button(__("Extrapolate Pattern to Calendar Date Range"), function () {
		extrapolate_visible_rotation_to_full_calendar(frm);
	}, __("Rotation"));

	frm.add_custom_button(__("Clean Duplicate Rotation Rows"), function () {
		clean_duplicate_rotation_rows(frm);
	}, __("Rotation"));

	frm.add_custom_button(__("Render Rotation Editor"), function () {
		render_rotation_editor_preserve_scroll(frm);
	}, __("Rotation"));

	frm.add_custom_button(__("Generate Calendar"), function () {
		generate_calendar(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Generate Team Rotation"), function () {
		generate_team_rotation(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Calculate Output"), function () {
		calculate_output(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Render Visual Summaries"), function () {
		render_all_visual_blocks(frm);
	}, __("Actions"));

	frm.add_custom_button(__("Export Shift Plan XLSX"), function () {
		export_shift_plan_xlsx(frm);
	}, __("Export"));

	frm.add_custom_button(__("Clear Output"), function () {
		clear_output(frm);
	}, __("Actions"));
}

function set_default_values(frm) {
	if (!frm.doc.pay_period_type) {
		frm.set_value("pay_period_type", "Mixed");
	}

	if (!frm.doc.hourly_pay_period_start_day) {
		frm.set_value("hourly_pay_period_start_day", 16);
	}

	if (!frm.doc.hourly_pay_period_end_day) {
		frm.set_value("hourly_pay_period_end_day", 15);
	}

	if (!frm.doc.salaried_pay_period_start_day) {
		frm.set_value("salaried_pay_period_start_day", 1);
	}

	if (!frm.doc.salaried_pay_period_end_day) {
		frm.set_value("salaried_pay_period_end_day", 31);
	}

	if (!frm.doc.normal_hours_limit) {
		frm.set_value("normal_hours_limit", 195);
	}

	if (!frm.doc.normal_hours_limit_basis) {
		frm.set_value("normal_hours_limit_basis", "Monthly");
	}

	if (!frm.doc.normal_ot_multiplier) {
		frm.set_value("normal_ot_multiplier", 1.5);
	}

	if (!frm.doc.sunday_ot_multiplier) {
		frm.set_value("sunday_ot_multiplier", 2);
	}

	if (!frm.doc.public_holiday_ot_multiplier) {
		frm.set_value("public_holiday_ot_multiplier", 2);
	}

	if (!frm.doc.default_shift_hours) {
		frm.set_value("default_shift_hours", 12);
	}

	if (!frm.doc.default_day_shift_hours) {
		frm.set_value("default_day_shift_hours", 8);
	}

	if (!frm.doc.default_operating_hours) {
		frm.set_value("default_operating_hours", 24);
	}

	if (!frm.doc.rotation_pattern_days) {
		frm.set_value("rotation_pattern_days", 10);
	}

	if (!frm.doc.rotation_anchor_date && frm.doc.calendar_start_date) {
		frm.set_value("rotation_anchor_date", frm.doc.calendar_start_date);
	}

	if (!frm.doc.sunday_rotation_rule) {
		frm.set_value("sunday_rotation_rule", "Follow Pattern");
	}

	if (frm.doc.treat_sundays_as_overtime === undefined || frm.doc.treat_sundays_as_overtime === null) {
		frm.set_value("treat_sundays_as_overtime", 1);
	}

	if (frm.doc.treat_public_holidays_as_overtime === undefined || frm.doc.treat_public_holidays_as_overtime === null) {
		frm.set_value("treat_public_holidays_as_overtime", 1);
	}
}

function set_output_tables_read_only(frm) {
	set_grid_read_only(frm, "output");
	set_grid_read_only(frm, "team_output");
}

function set_grid_read_only(frm, table_fieldname) {
	if (!frm.fields_dict[table_fieldname] || !frm.fields_dict[table_fieldname].grid) {
		return;
	}

	const grid = frm.fields_dict[table_fieldname].grid;

	grid.wrapper.find(".grid-add-row").hide();
	grid.wrapper.find(".grid-remove-rows").hide();
	grid.wrapper.find(".grid-delete-row").hide();
	grid.wrapper.find(".grid-duplicate-row").hide();
	grid.wrapper.find(".grid-move-row").hide();
	grid.wrapper.find(".grid-append-row").hide();
}

function apply_operating_model_defaults(frm) {
	const operating_model = frm.doc.operating_model;

	if (!operating_model) {
		return;
	}

	if (operating_model === "24h Mon-Sat") {
		frm.set_value("include_mondays", 1);
		frm.set_value("include_tuesdays", 1);
		frm.set_value("include_wednesdays", 1);
		frm.set_value("include_thursdays", 1);
		frm.set_value("include_fridays", 1);
		frm.set_value("include_saturdays", 1);
		frm.set_value("include_sundays", 0);
		frm.set_value("saturday_work_model", "24h");
		frm.set_value("sunday_work_model", "No Work");
		frm.set_value("default_shift_hours", frm.doc.default_shift_hours || 12);
		frm.set_value("default_operating_hours", 24);
	}

	if (operating_model === "24h Mon-Sun") {
		frm.set_value("include_mondays", 1);
		frm.set_value("include_tuesdays", 1);
		frm.set_value("include_wednesdays", 1);
		frm.set_value("include_thursdays", 1);
		frm.set_value("include_fridays", 1);
		frm.set_value("include_saturdays", 1);
		frm.set_value("include_sundays", 1);
		frm.set_value("saturday_work_model", "24h");
		frm.set_value("sunday_work_model", "24h");
		frm.set_value("default_shift_hours", frm.doc.default_shift_hours || 12);
		frm.set_value("default_operating_hours", 24);
	}

	if (operating_model === "Day Shift Only") {
		frm.set_value("include_mondays", 1);
		frm.set_value("include_tuesdays", 1);
		frm.set_value("include_wednesdays", 1);
		frm.set_value("include_thursdays", 1);
		frm.set_value("include_fridays", 1);
		frm.set_value("include_saturdays", 0);
		frm.set_value("include_sundays", 0);
		frm.set_value("saturday_work_model", "No Work");
		frm.set_value("sunday_work_model", "No Work");
		frm.set_value("default_shift_hours", frm.doc.default_shift_hours || 8);
		frm.set_value("default_day_shift_hours", frm.doc.default_day_shift_hours || 8);
		frm.set_value("default_operating_hours", frm.doc.default_day_shift_hours || 8);
	}

	if (!frm.doc.number_of_shift_teams && operating_model !== "Day Shift Only") {
		frm.set_value("number_of_shift_teams", 3);
	}

	if (!frm.doc.number_of_shift_teams && operating_model === "Day Shift Only") {
		frm.set_value("number_of_shift_teams", 1);
	}
}

function generate_team_labels(frm) {
	const number_of_shift_teams = cint(frm.doc.number_of_shift_teams || 0);

	if (!number_of_shift_teams) {
		frm.clear_table("shift_team_labels");
		frm.refresh_field("shift_team_labels");
		return;
	}

	if (!frm.doc.shift_team_labels) {
		frm.doc.shift_team_labels = [];
	}

	while (frm.doc.shift_team_labels.length > number_of_shift_teams) {
		frm.doc.shift_team_labels.pop();
	}

	for (let i = frm.doc.shift_team_labels.length; i < number_of_shift_teams; i++) {
		const row = frm.add_child("shift_team_labels");
		row.team_label = `Team ${String.fromCharCode(65 + i)}`;
	}

	frm.refresh_field("shift_team_labels");
	frm.dirty();
}

function update_calendar_days(frm) {
	if (!frm.doc.calendar_start_date || !frm.doc.calendar_end_date) {
		return;
	}

	const start_date = frappe.datetime.str_to_obj(frm.doc.calendar_start_date);
	const end_date = frappe.datetime.str_to_obj(frm.doc.calendar_end_date);

	if (end_date < start_date) {
		frm.set_value("calendar_days", 0);
		return;
	}

	const diff = frappe.datetime.get_day_diff(frm.doc.calendar_end_date, frm.doc.calendar_start_date) + 1;
	frm.set_value("calendar_days", diff);
}

function calculate_staffing_total(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	const employees_per_shift = cint(row.employees_per_shift || 0);
	const number_of_shift_teams = cint(row.number_of_shift_teams || 0);

	row.total_employees = employees_per_shift * number_of_shift_teams;

	if (!row.working_days) {
		row.working_days = get_default_working_days_for_row(row);
	}

	if (!row.fixed_cost_basis) {
		row.fixed_cost_basis = "Per Selected Period";
	}

	frm.refresh_field("employees");
}

function calculate_all_staffing_totals(frm) {
	(frm.doc.employees || []).forEach(function (row) {
		row.total_employees = cint(row.employees_per_shift || 0) * cint(row.number_of_shift_teams || 0);

		if (!row.working_days) {
			row.working_days = get_default_working_days_for_row(row);
		}

		if (!row.fixed_cost_basis) {
			row.fixed_cost_basis = "Per Selected Period";
		}
	});

	frm.refresh_field("employees");
}

function set_default_working_days(frm, cdt, cdn) {
	const row = locals[cdt][cdn];

	if (!row.working_days) {
		row.working_days = get_default_working_days_for_row(row);
	}

	if (!row.fixed_cost_basis) {
		row.fixed_cost_basis = "Per Selected Period";
	}

	frm.refresh_field("employees");
}

function get_default_working_days_for_row(row) {
	if (row.working_hours === "Shift Pattern") {
		return "Follow Shift Plan Calendar";
	}

	if (row.working_hours === "Day Shift Only") {
		return "Monday to Friday";
	}

	if (row.working_hours === "Night Shift Only") {
		return "Follow Shift Plan Calendar";
	}

	return "Follow Shift Plan Calendar";
}

function apply_team_count_to_staffing(frm) {
	const number_of_shift_teams = cint(frm.doc.number_of_shift_teams || 0);

	if (!number_of_shift_teams) {
		frappe.msgprint(__("Please set Number of Shift Teams first."));
		return;
	}

	(frm.doc.employees || []).forEach(function (row) {
		row.number_of_shift_teams = number_of_shift_teams;
		row.total_employees = cint(row.employees_per_shift || 0) * number_of_shift_teams;

		if (!row.working_days) {
			row.working_days = get_default_working_days_for_row(row);
		}

		if (!row.fixed_cost_basis) {
			row.fixed_cost_basis = "Per Selected Period";
		}
	});

	frm.refresh_field("employees");
	frm.dirty();

	frappe.show_alert({
		message: __("Team count applied to staffing rows."),
		indicator: "green"
	});
}

function normalize_rotation_value(value) {
	return (value || "").toString().trim();
}

function get_rotation_cost_groups(frm) {
	const groups = [];

	(frm.doc.employees || []).forEach(function (row) {
		if (!row.cost_group) {
			return;
		}

		if (row.working_hours === "Shift Pattern" || row.working_hours === "Night Shift Only") {
			if (!groups.includes(row.cost_group)) {
				groups.push(row.cost_group);
			}
		}
	});

	(frm.doc.rotation_pattern || []).forEach(function (row) {
		if (row.cost_group && !groups.includes(row.cost_group)) {
			groups.push(row.cost_group);
		}
	});

	return groups;
}

function get_team_labels(frm) {
	const labels = [];

	(frm.doc.shift_team_labels || []).forEach(function (row) {
		if (row.team_label && !labels.includes(row.team_label)) {
			labels.push(row.team_label);
		}
	});

	(frm.doc.rotation_pattern || []).forEach(function (row) {
		if (row.team_label && !labels.includes(row.team_label)) {
			labels.push(row.team_label);
		}
	});

	return labels;
}

function get_rotation_assignment(frm, cost_group, pattern_day, team_label) {
	const rows = frm.doc.rotation_pattern || [];

	const target_cost_group = normalize_rotation_value(cost_group);
	const target_team_label = normalize_rotation_value(team_label);
	const target_pattern_day = cint(pattern_day);

	for (let i = rows.length - 1; i >= 0; i--) {
		const row = rows[i];

		if (
			normalize_rotation_value(row.cost_group) === target_cost_group &&
			cint(row.pattern_day) === target_pattern_day &&
			normalize_rotation_value(row.team_label) === target_team_label
		) {
			return row.shift_assignment || "Off";
		}
	}

	return "Off";
}

function set_rotation_assignment(frm, cost_group, pattern_day, team_label, assignment) {
	if (!frm.doc.rotation_pattern) {
		frm.doc.rotation_pattern = [];
	}

	const target_cost_group = normalize_rotation_value(cost_group);
	const target_team_label = normalize_rotation_value(team_label);
	const target_pattern_day = cint(pattern_day);

	let last_match = null;

	(frm.doc.rotation_pattern || []).forEach(function (row) {
		if (
			normalize_rotation_value(row.cost_group) === target_cost_group &&
			cint(row.pattern_day) === target_pattern_day &&
			normalize_rotation_value(row.team_label) === target_team_label
		) {
			last_match = row;
		}
	});

	if (!last_match) {
		last_match = frm.add_child("rotation_pattern");
		last_match.cost_group = target_cost_group;
		last_match.pattern_day = target_pattern_day;
		last_match.team_label = target_team_label;
		last_match.working_hours = "Shift Pattern";
	}

	last_match.shift_assignment = assignment || "Off";
	last_match.working_hours = last_match.working_hours || "Shift Pattern";

	frm.dirty();
}

function clean_duplicate_rotation_rows(frm) {
	const rows = frm.doc.rotation_pattern || [];
	const seen = {};
	const to_remove = [];

	for (let i = rows.length - 1; i >= 0; i--) {
		const row = rows[i];
		const key = [
			normalize_rotation_value(row.cost_group),
			cint(row.pattern_day),
			normalize_rotation_value(row.team_label)
		].join("||");

		if (seen[key]) {
			to_remove.push(row.name);
		} else {
			seen[key] = true;
		}
	}

	to_remove.forEach(function (row_name) {
		const grid_row = frm.get_field("rotation_pattern").grid.grid_rows_by_docname[row_name];

		if (grid_row) {
			grid_row.remove();
		}
	});

	frm.refresh_field("rotation_pattern");
	frm.dirty();
	render_rotation_editor_preserve_scroll(frm);
	render_full_calendar(frm);

	frappe.show_alert({
		message: __("Duplicate rotation rows cleaned."),
		indicator: "green"
	});
}

function cycle_assignment(current_assignment) {
	if (current_assignment === "Off") {
		return "Day";
	}

	if (current_assignment === "Day") {
		return "Night";
	}

	return "Off";
}

function get_assignment_badge(assignment) {
	if (assignment === "Day") {
		return `<span class="sp-badge sp-day">D</span>`;
	}

	if (assignment === "Night") {
		return `<span class="sp-badge sp-night">N</span>`;
	}

	return `<span class="sp-badge sp-off">O</span>`;
}

function update_rotation_cell_display(cell, assignment) {
	cell.attr("data-assignment", assignment);
	cell.html(get_assignment_badge(assignment));
}

function get_pattern_date(frm, pattern_day) {
	const anchor = frm.doc.rotation_anchor_date || frm.doc.calendar_start_date;

	if (!anchor) {
		return null;
	}

	return frappe.datetime.add_days(anchor, cint(pattern_day) - 1);
}

function get_weekday_name(date_string) {
	if (!date_string) {
		return "";
	}

	const date_obj = frappe.datetime.str_to_obj(date_string);
	const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

	return days[date_obj.getDay()];
}

function get_calendar_cycle_days(frm) {
	if (!frm.doc.calendar_start_date || !frm.doc.calendar_end_date) {
		return 0;
	}

	const start_date = frappe.datetime.str_to_obj(frm.doc.calendar_start_date);
	const end_date = frappe.datetime.str_to_obj(frm.doc.calendar_end_date);

	if (!start_date || !end_date || end_date < start_date) {
		return 0;
	}

	return frappe.datetime.get_day_diff(frm.doc.calendar_end_date, frm.doc.calendar_start_date) + 1;
}

function get_rotation_scroll_positions(frm) {
	const wrapper = frm.fields_dict.rotation_editor_html?.$wrapper;

	if (!wrapper || !wrapper.length) {
		return {};
	}

	const positions = {};

	wrapper.find(".sp-rotation-wrap").each(function () {
		const group = $(this).attr("data-cost-group");
		const scroll_left = $(this).find(".sp-grid-scroll").scrollLeft();

		if (group) {
			positions[group] = scroll_left || 0;
		}
	});

	return positions;
}

function restore_rotation_scroll_positions(frm, positions) {
	const wrapper = frm.fields_dict.rotation_editor_html?.$wrapper;

	if (!wrapper || !wrapper.length || !positions) {
		return;
	}

	wrapper.find(".sp-rotation-wrap").each(function () {
		const group = $(this).attr("data-cost-group");

		if (group && positions[group] !== undefined) {
			$(this).find(".sp-grid-scroll").scrollLeft(positions[group]);
		}
	});
}

function render_rotation_editor_preserve_scroll(frm) {
	const positions = get_rotation_scroll_positions(frm);
	render_rotation_editor(frm);
	restore_rotation_scroll_positions(frm, positions);
}

function render_rotation_editor(frm) {
	if (!frm.fields_dict.rotation_editor_html || !frm.fields_dict.rotation_editor_html.$wrapper) {
		return;
	}

	const wrapper = frm.fields_dict.rotation_editor_html.$wrapper;
	const teams = get_team_labels(frm);
	const cost_groups = get_rotation_cost_groups(frm);
	const pattern_days = cint(frm.doc.rotation_pattern_days || 0);

	if (!pattern_days || !teams.length || !cost_groups.length) {
		wrapper.html(`
			<div class="sp-rotation-empty">
				<b>Rotation Editor</b><br>
				Set Rotation Pattern Days, generate Team Labels, and add Staffing rows with Shift Pattern or Night Shift Only.
			</div>
		`);
		return;
	}

	const styles = get_shift_plan_visual_styles();

	let html = styles;

	cost_groups.forEach(function (cost_group) {
		html += `
			<div class="sp-rotation-wrap" data-cost-group="${html_escape(cost_group)}">
				<div class="sp-rotation-header">
					<div>
						<div class="sp-rotation-title">${html_escape(cost_group)} Rotation Pattern</div>
						<div class="sp-rotation-help">
							Click a cell to cycle Off → Day → Night. Drag D, N, or O into a cell.
						</div>
					</div>
					<div>
						<button type="button" class="sp-btn sp-load-3d3n4o" data-cost-group="${html_escape(cost_group)}">3D 3N 4O</button>
						<button type="button" class="sp-btn sp-load-4d4n4o" data-cost-group="${html_escape(cost_group)}">4D 4N 4O</button>
						<button type="button" class="sp-btn sp-clear-pattern" data-cost-group="${html_escape(cost_group)}">Clear</button>
						<button type="button" class="sp-btn sp-btn-primary sp-extrapolate-pattern" data-cost-group="${html_escape(cost_group)}">Extrapolate Date Range</button>
					</div>
				</div>

				<div class="sp-chip-row">
					<span class="sp-chip sp-chip-day" draggable="true" data-assignment="Day">D Day</span>
					<span class="sp-chip sp-chip-night" draggable="true" data-assignment="Night">N Night</span>
					<span class="sp-chip sp-chip-off" draggable="true" data-assignment="Off">O Off</span>
				</div>

				<div class="sp-grid-scroll">
					<table class="sp-grid">
						<thead>
							<tr>
								<th class="sp-team-col">Team</th>
		`;

		for (let day = 1; day <= pattern_days; day++) {
			const pattern_date = get_pattern_date(frm, day);
			const weekday = get_weekday_name(pattern_date);

			html += `
				<th>
					<div class="sp-day-head">
						<div class="sp-day-head-main">Day ${day}</div>
						<div class="sp-day-head-date">${pattern_date || ""}</div>
						<div class="sp-day-head-weekday">${weekday || ""}</div>
					</div>
				</th>
			`;
		}

		html += `
							</tr>
						</thead>
						<tbody>
		`;

		teams.forEach(function (team_label) {
			html += `<tr><td class="sp-team-col">${html_escape(team_label)}</td>`;

			for (let day = 1; day <= pattern_days; day++) {
				const assignment = get_rotation_assignment(frm, cost_group, day, team_label);

				html += `
					<td class="sp-cell"
						data-cost-group="${html_escape(cost_group)}"
						data-pattern-day="${day}"
						data-team-label="${html_escape(team_label)}"
						data-assignment="${assignment}">
						${get_assignment_badge(assignment)}
					</td>
				`;
			}

			html += `</tr>`;
		});

		html += `
						</tbody>
					</table>
				</div>
			</div>
		`;
	});

	wrapper.html(html);
	bind_rotation_editor_events(frm, wrapper);
}

function bind_rotation_editor_events(frm, wrapper) {
	wrapper.find(".sp-cell").off("click").on("click", function () {
		const cell = $(this);
		const current = cell.attr("data-assignment") || "Off";
		const next = cycle_assignment(current);

		set_rotation_assignment(
			frm,
			cell.attr("data-cost-group"),
			cint(cell.attr("data-pattern-day")),
			cell.attr("data-team-label"),
			next
		);

		update_rotation_cell_display(cell, next);
		render_full_calendar(frm);
	});

	wrapper.find(".sp-cell").off("dblclick").on("dblclick", function () {
		const cell = $(this);

		set_rotation_assignment(
			frm,
			cell.attr("data-cost-group"),
			cint(cell.attr("data-pattern-day")),
			cell.attr("data-team-label"),
			"Off"
		);

		update_rotation_cell_display(cell, "Off");
		render_full_calendar(frm);
	});

	wrapper.find(".sp-chip").off("dragstart").on("dragstart", function (event) {
		event.originalEvent.dataTransfer.setData("text/plain", $(this).attr("data-assignment"));
	});

	wrapper.find(".sp-cell").off("dragover").on("dragover", function (event) {
		event.preventDefault();
	});

	wrapper.find(".sp-cell").off("drop").on("drop", function (event) {
		event.preventDefault();

		const assignment = event.originalEvent.dataTransfer.getData("text/plain");
		const cell = $(this);

		set_rotation_assignment(
			frm,
			cell.attr("data-cost-group"),
			cint(cell.attr("data-pattern-day")),
			cell.attr("data-team-label"),
			assignment
		);

		update_rotation_cell_display(cell, assignment);
		render_full_calendar(frm);
	});

	wrapper.find(".sp-load-3d3n4o").off("click").on("click", function () {
		load_rotation_preset(frm, "3D3N4O", $(this).attr("data-cost-group"));
	});

	wrapper.find(".sp-load-4d4n4o").off("click").on("click", function () {
		load_rotation_preset(frm, "4D4N4O", $(this).attr("data-cost-group"));
	});

	wrapper.find(".sp-clear-pattern").off("click").on("click", function () {
		clear_rotation_pattern_for_cost_group(frm, $(this).attr("data-cost-group"));
	});

	wrapper.find(".sp-extrapolate-pattern").off("click").on("click", function () {
		extrapolate_visible_rotation_to_full_calendar(frm, $(this).attr("data-cost-group"));
	});
}

function build_seed_from_visible_editor(frm, cost_group, seed_days, teams) {
	const wrapper = frm.fields_dict.rotation_editor_html.$wrapper;
	const seed = {};

	for (let day = 1; day <= seed_days; day++) {
		seed[day] = {};
		teams.forEach(function (team_label) {
			seed[day][team_label] = get_rotation_assignment(frm, cost_group, day, team_label);
		});
	}

	if (wrapper && wrapper.length) {
		wrapper.find(`.sp-cell[data-cost-group="${css_escape(cost_group)}"]`).each(function () {
			const cell = $(this);
			const pattern_day = cint(cell.attr("data-pattern-day"));

			if (pattern_day <= seed_days) {
				const team_label = cell.attr("data-team-label");
				const assignment = cell.attr("data-assignment") || "Off";

				if (!seed[pattern_day]) {
					seed[pattern_day] = {};
				}

				seed[pattern_day][team_label] = assignment;
			}
		});
	}

	return seed;
}

function extrapolate_visible_rotation_to_full_calendar(frm, only_cost_group) {
	const seed_days = cint(frm.doc.rotation_pattern_days || 0);
	const calendar_days = get_calendar_cycle_days(frm);
	const teams = get_team_labels(frm);
	const cost_groups = only_cost_group ? [only_cost_group] : get_rotation_cost_groups(frm);

	if (!seed_days) {
		frappe.msgprint(__("Please set Rotation Pattern Days first."));
		return;
	}

	if (!calendar_days) {
		frappe.msgprint(__("Please set Calendar Start Date and Calendar End Date first."));
		return;
	}

	if (!teams.length) {
		frappe.msgprint(__("Please generate Team Labels first."));
		return;
	}

	if (!cost_groups.length) {
		frappe.msgprint(__("Please add Staffing rows with Shift Pattern or Night Shift Only first."));
		return;
	}

	frappe.confirm(
		__(
			`This will extrapolate the current ${seed_days}-day visible pattern to the full calendar date range ` +
			`${frm.doc.calendar_start_date} to ${frm.doc.calendar_end_date}, creating ${calendar_days} pattern days. Continue?`
		),
		function () {
			cost_groups.forEach(function (cost_group) {
				const seed = build_seed_from_visible_editor(frm, cost_group, seed_days, teams);

				clear_rotation_pattern_for_cost_group_no_render(frm, cost_group);

				for (let day = 1; day <= calendar_days; day++) {
					const seed_day = ((day - 1) % seed_days) + 1;

					teams.forEach(function (team_label) {
						const assignment = seed[seed_day]?.[team_label] || "Off";

						const row = frm.add_child("rotation_pattern");
						row.cost_group = cost_group;
						row.pattern_day = day;
						row.team_label = team_label;
						row.shift_assignment = assignment;
						row.working_hours = "Shift Pattern";
					});
				}
			});

			frm.doc.rotation_pattern_days = calendar_days;
			frm.refresh_field("rotation_pattern_days");
			frm.refresh_field("rotation_pattern");
			frm.dirty();

			render_rotation_editor_preserve_scroll(frm);
			render_full_calendar(frm);

			frappe.show_alert({
				message: __(`Rotation pattern extrapolated to ${calendar_days} calendar day(s).`),
				indicator: "green"
			});
		}
	);
}

function css_escape(value) {
	if (window.CSS && CSS.escape) {
		return CSS.escape(value);
	}

	return String(value).replace(/"/g, '\\"');
}

function clear_rotation_pattern_for_cost_group(frm, cost_group) {
	clear_rotation_pattern_for_cost_group_no_render(frm, cost_group);

	frm.refresh_field("rotation_pattern");
	frm.dirty();
	render_rotation_editor_preserve_scroll(frm);
	render_full_calendar(frm);
}

function clear_rotation_pattern_for_cost_group_no_render(frm, cost_group) {
	const rows = frm.doc.rotation_pattern || [];

	for (let i = rows.length - 1; i >= 0; i--) {
		if (normalize_rotation_value(rows[i].cost_group) === normalize_rotation_value(cost_group)) {
			const grid_row = frm.get_field("rotation_pattern").grid.grid_rows_by_docname[rows[i].name];

			if (grid_row) {
				grid_row.remove();
			}
		}
	}
}

function load_rotation_preset(frm, preset, only_cost_group) {
	const teams = get_team_labels(frm);
	const cost_groups = only_cost_group ? [only_cost_group] : get_rotation_cost_groups(frm);

	if (!teams.length) {
		frappe.msgprint(__("Please generate Team Labels first."));
		return;
	}

	if (!cost_groups.length) {
		frappe.msgprint(__("Please add Staffing rows with Shift Pattern or Night Shift Only first."));
		return;
	}

	if (preset === "3D3N4O") {
		frm.set_value("rotation_pattern_days", 10);
	}

	if (preset === "4D4N4O") {
		frm.set_value("rotation_pattern_days", 12);
	}

	cost_groups.forEach(function (cost_group) {
		clear_rotation_pattern_for_cost_group_no_render(frm, cost_group);
		apply_preset_to_cost_group(frm, preset, cost_group, teams);
	});

	frm.refresh_field("rotation_pattern");
	frm.dirty();
	render_rotation_editor_preserve_scroll(frm);
	render_full_calendar(frm);

	frappe.show_alert({
		message: __(`${preset} rotation pattern loaded.`),
		indicator: "green"
	});
}

function apply_preset_to_cost_group(frm, preset, cost_group, teams) {
	if (preset === "3D3N4O") {
		apply_3d3n4o(frm, cost_group, teams);
		return;
	}

	if (preset === "4D4N4O") {
		apply_4d4n4o(frm, cost_group, teams);
	}
}

function apply_3d3n4o(frm, cost_group, teams) {
	const pattern = [
		["Day", "Off", "Night"],
		["Day", "Off", "Night"],
		["Day", "Off", "Night"],
		["Night", "Day", "Off"],
		["Night", "Day", "Off"],
		["Night", "Day", "Off"],
		["Off", "Night", "Day"],
		["Off", "Night", "Day"],
		["Off", "Night", "Day"],
		["Off", "Off", "Off"]
	];

	apply_pattern_matrix(frm, cost_group, teams, pattern);
}

function apply_4d4n4o(frm, cost_group, teams) {
	const pattern = [
		["Day", "Off", "Night"],
		["Day", "Off", "Night"],
		["Day", "Off", "Night"],
		["Day", "Off", "Night"],
		["Night", "Day", "Off"],
		["Night", "Day", "Off"],
		["Night", "Day", "Off"],
		["Night", "Day", "Off"],
		["Off", "Night", "Day"],
		["Off", "Night", "Day"],
		["Off", "Night", "Day"],
		["Off", "Night", "Day"]
	];

	apply_pattern_matrix(frm, cost_group, teams, pattern);
}

function apply_pattern_matrix(frm, cost_group, teams, pattern) {
	for (let day_index = 0; day_index < pattern.length; day_index++) {
		for (let team_index = 0; team_index < teams.length; team_index++) {
			const assignment = pattern[day_index][team_index] || "Off";
			set_rotation_assignment(frm, cost_group, day_index + 1, teams[team_index], assignment);
		}
	}
}

function generate_calendar(frm) {
	if (!frm.doc.calendar_start_date || !frm.doc.calendar_end_date) {
		frappe.msgprint(__("Please set Calendar Start Date and Calendar End Date first."));
		return;
	}

	frm.call("generate_calendar").then(function (r) {
		if (r.message) {
			frappe.model.sync(r.message);
			frm.refresh();
			frm.dirty();
		}

		render_all_visual_blocks(frm);

		frappe.show_alert({
			message: __("Shift calendar generated."),
			indicator: "green"
		});
	});
}

function generate_team_rotation(frm) {
	if (!frm.doc.shift_calendar || frm.doc.shift_calendar.length === 0) {
		frappe.msgprint(__("Please generate the Shift Calendar first."));
		return;
	}

	if (!frm.doc.rotation_pattern || frm.doc.rotation_pattern.length === 0) {
		frappe.msgprint(__("Please set or load a Rotation Pattern first."));
		return;
	}

	frm.call("generate_team_rotation").then(function (r) {
		if (r.message) {
			frappe.model.sync(r.message);
			frm.refresh();
			frm.dirty();
		}

		render_full_calendar(frm);

		frappe.show_alert({
			message: __("Team rotation generated from pattern."),
			indicator: "green"
		});
	});
}

function calculate_output(frm) {
	if (!frm.doc.shift_calendar || frm.doc.shift_calendar.length === 0) {
		frappe.msgprint(__("Please generate the Shift Calendar first."));
		return;
	}

	if (!frm.doc.employees || frm.doc.employees.length === 0) {
		frappe.msgprint(__("Please add Staffing rows first."));
		return;
	}

	if (!frm.doc.rotation_pattern || frm.doc.rotation_pattern.length === 0) {
		frappe.msgprint(__("Please set or load a Rotation Pattern first."));
		return;
	}

	frm.call("calculate_output").then(function (r) {
		if (r.message) {
			frappe.model.sync(r.message);
			frm.refresh();
			frm.dirty();
		}

		render_all_visual_blocks(frm);

		frappe.show_alert({
			message: __("Shift Plan output calculated."),
			indicator: "green"
		});
	});
}

function clear_output(frm) {
	frm.clear_table("output");

	if (frm.fields_dict.team_output) {
		frm.clear_table("team_output");
	}

	frm.refresh_field("output");
	frm.refresh_field("team_output");
	frm.dirty();

	render_team_summary(frm);
	render_output_summary(frm);

	frappe.show_alert({
		message: __("Output cleared."),
		indicator: "orange"
	});
}

function export_shift_plan_xlsx(frm) {
	if (!frm.doc.name) {
		frappe.msgprint(__("Please save the Shift Plan before exporting."));
		return;
	}

	frm.call("export_shift_plan_xlsx").then(function (r) {
		const result = r.message || {};

		if (result.file_url) {
			window.open(result.file_url, "_blank");

			frappe.show_alert({
				message: __("Shift Plan XLSX export generated."),
				indicator: "green"
			});
		} else {
			frappe.msgprint(__("Export completed but no file URL was returned."));
		}
	});
}

function render_all_visual_blocks(frm) {
	render_full_calendar(frm);
	render_team_summary(frm);
	render_output_summary(frm);
}

function render_full_calendar(frm) {
	if (!frm.fields_dict.full_calendar || !frm.fields_dict.full_calendar.$wrapper) {
		return;
	}

	const wrapper = frm.fields_dict.full_calendar.$wrapper;

	if (!frm.doc.shift_calendar || !frm.doc.shift_calendar.length) {
		wrapper.html(`
			${get_shift_plan_visual_styles()}
			<div class="sp-visual-empty">
				<b>Full Calendar</b><br>
				Generate the Shift Calendar to display the full roster calendar.
			</div>
		`);
		return;
	}

	if (!frm.doc.rotation_pattern || !frm.doc.rotation_pattern.length) {
		wrapper.html(`
			${get_shift_plan_visual_styles()}
			<div class="sp-visual-empty">
				<b>Full Calendar</b><br>
				Set or extrapolate the rotation pattern to display team assignments.
			</div>
		`);
		return;
	}

	wrapper.html(`
		${get_shift_plan_visual_styles()}
		<div class="sp-loading">Rendering full calendar...</div>
	`);

	frm.call("get_visual_calendar_data").then(function (r) {
		const data = r.message || {};
		wrapper.html(build_full_calendar_html(data));
	});
}

function build_full_calendar_html(data) {
	const months = data.months || [];

	if (!months.length) {
		return `
			${get_shift_plan_visual_styles()}
			<div class="sp-visual-empty">
				<b>Full Calendar</b><br>
				No calendar rows available.
			</div>
		`;
	}

	let html = `${get_shift_plan_visual_styles()}`;
	html += `<div class="sp-section-title">Full Roster Calendar</div>`;
	html += `<div class="sp-section-subtitle">Calendar view by month, date, cost group and team assignment.</div>`;

	months.forEach(function (month) {
		html += `
			<div class="sp-month-card">
				<div class="sp-month-title">${html_escape(month.label)}</div>
				<div class="sp-calendar-grid">
					<div class="sp-calendar-head">Mon</div>
					<div class="sp-calendar-head">Tue</div>
					<div class="sp-calendar-head">Wed</div>
					<div class="sp-calendar-head">Thu</div>
					<div class="sp-calendar-head">Fri</div>
					<div class="sp-calendar-head">Sat</div>
					<div class="sp-calendar-head">Sun</div>
		`;

		(month.weeks || []).forEach(function (week) {
			week.forEach(function (day) {
				if (!day || !day.date) {
					html += `<div class="sp-calendar-cell sp-calendar-blank"></div>`;
					return;
				}

				html += `
					<div class="sp-calendar-cell ${get_day_type_class(day.day_type)}">
						<div class="sp-calendar-date-row">
							<span class="sp-calendar-date">${day.day}</span>
							<span class="sp-day-type">${html_escape(day.day_type || "")}</span>
						</div>
				`;

				Object.keys(day.cost_groups || {}).sort().forEach(function (cost_group) {
					const group = day.cost_groups[cost_group] || {};
					html += `
						<div class="sp-calendar-group">
							<div class="sp-calendar-group-title">${html_escape(cost_group)}</div>
							<div class="sp-mini-line"><span class="sp-mini-label sp-day">D</span> ${html_escape((group.day || []).join(", ") || "-")} <span class="sp-hours">${html_escape(group.day_hours_label || "")}</span></div>
							<div class="sp-mini-line"><span class="sp-mini-label sp-night">N</span> ${html_escape((group.night || []).join(", ") || "-")} <span class="sp-hours">${html_escape(group.night_hours_label || "")}</span></div>
							<div class="sp-mini-line"><span class="sp-mini-label sp-off">O</span> ${html_escape((group.off || []).join(", ") || "-")}</div>
						</div>
					`;
				});

				html += `</div>`;
			});
		});

		html += `
				</div>
			</div>
		`;
	});

	return html;
}

function get_day_type_class(day_type) {
	if (day_type === "Sunday") {
		return "sp-calendar-sunday";
	}

	if (day_type === "Saturday") {
		return "sp-calendar-saturday";
	}

	if (day_type === "Public Holiday") {
		return "sp-calendar-public-holiday";
	}

	return "";
}

function render_team_summary(frm) {
	if (!frm.fields_dict.team_summary || !frm.fields_dict.team_summary.$wrapper) {
		return;
	}

	const wrapper = frm.fields_dict.team_summary.$wrapper;
	const rows = frm.doc.team_output || [];

	if (!rows.length) {
		wrapper.html(`
			${get_shift_plan_visual_styles()}
			<div class="sp-visual-empty">
				<b>Team Summary</b><br>
				Calculate Output to display the team summary.
			</div>
		`);
		return;
	}

	wrapper.html(build_team_summary_html(rows));
}

function build_team_summary_html(rows) {
	const grouped = group_by(rows, "period_label");
	const periods = Object.keys(grouped).sort(sort_period_labels);

	let html = `${get_shift_plan_visual_styles()}`;
	html += `<div class="sp-section-title">Team Summary</div>`;
	html += `<div class="sp-section-subtitle">Roster-driven hours by period, cost group and team.</div>`;

	periods.forEach(function (period_label) {
		const period_rows = grouped[period_label] || [];
		const cost_groups = group_by(period_rows, "cost_group");

		html += `
			<div class="sp-summary-card">
				<div class="sp-summary-card-title">${html_escape(period_label || "Unlabelled Period")}</div>
		`;

		Object.keys(cost_groups).sort().forEach(function (cost_group) {
			const sorted_rows = (cost_groups[cost_group] || []).slice().sort(function (a, b) {
				return sort_team_labels(a.team_label, b.team_label);
			});

			html += `
				<div class="sp-cost-group-title">${html_escape(cost_group || "Unspecified")}</div>
				<div class="sp-table-wrap">
					<table class="sp-summary-table">
						<thead>
							<tr>
								<th>Team</th>
								<th>Working Hours</th>
								<th>NT</th>
								<th>OT 1.5</th>
								<th>Sunday</th>
								<th>PPH</th>
								<th>Total OT</th>
								<th>Total Hours</th>
								<th>OT % of NT</th>
							</tr>
						</thead>
						<tbody>
			`;

			sorted_rows.forEach(function (row) {
				const ordinary_hours = flt(row.ordinary_hours || 0);
				const total_overtime_hours = flt(row.total_overtime_hours || 0);

				let overtime_percent = flt(row.overtime_percent_of_normal_time || 0);

				if (!overtime_percent && ordinary_hours) {
					overtime_percent = (total_overtime_hours / ordinary_hours) * 100;
				}

				html += `
					<tr>
						<td><b>${html_escape(row.team_label || "-")}</b></td>
						<td>${html_escape(row.working_hours || "-")}</td>
						<td>${fmt(row.ordinary_hours)}</td>
						<td>${fmt(row.normal_overtime_hours)}</td>
						<td>${fmt(row.sunday_hours)}</td>
						<td>${fmt(row.public_holiday_hours)}</td>
						<td><b>${fmt(row.total_overtime_hours)}</b></td>
						<td>${fmt(row.total_hours)}</td>
						<td><b>${fmt(overtime_percent)}%</b></td>
					</tr>
				`;
			});

			html += `
						</tbody>
					</table>
				</div>
			`;
		});

		html += `</div>`;
	});

	return html;
}

function sort_team_labels(a, b) {
	const label_a = String(a || "");
	const label_b = String(b || "");

	const match_a = label_a.match(/^Team\s+([A-Z])$/i);
	const match_b = label_b.match(/^Team\s+([A-Z])$/i);

	if (match_a && match_b) {
		return match_a[1].toUpperCase().localeCompare(match_b[1].toUpperCase());
	}

	return label_a.localeCompare(label_b, undefined, {
		numeric: true,
		sensitivity: "base"
	});
}

function render_output_summary(frm) {
	if (!frm.fields_dict.output_summary || !frm.fields_dict.output_summary.$wrapper) {
		return;
	}

	const wrapper = frm.fields_dict.output_summary.$wrapper;
	const rows = frm.doc.output || [];

	if (!rows.length) {
		wrapper.html(`
			${get_shift_plan_visual_styles()}
			<div class="sp-visual-empty">
				<b>Output Summary</b><br>
				Calculate Output to display the management summary.
			</div>
		`);
		return;
	}

	wrapper.html(build_output_summary_html(rows));
}

function build_output_summary_html(rows) {
	const site_total = rows.find(row => row.output_type === "Site Total");
	const cost_group_totals = rows.filter(row => row.output_type === "Cost Group Total");
	const details = rows.filter(row => row.output_type === "Detail");

	let html = `${get_shift_plan_visual_styles()}`;
	html += `<div class="sp-section-title">Output Summary</div>`;
	html += `<div class="sp-section-subtitle">Labour-cost split based on the calculated roster, staffing model and captured revenue.</div>`;

	if (site_total) {
		const normal_time_cost = flt(site_total.normal_cost || 0);
		const fixed_labour_cost = flt(site_total.fixed_costs || 0);
		const normal_overtime_cost = flt(site_total.normal_overtime_cost || 0);
		const sunday_cost = flt(site_total.sunday_overtime_cost || 0);
		const public_holiday_cost = flt(site_total.public_holiday_overtime_cost || 0);
		const total_overtime_cost = normal_overtime_cost + sunday_cost + public_holiday_cost;
		const total_labour_cost = normal_time_cost + fixed_labour_cost + total_overtime_cost;
		const revenue = flt(site_total.period_revenue || 0);

		html += `
			<div class="sp-kpi-grid">
				${build_kpi("Revenue / Turnover", revenue ? money(revenue) : "N/A - Revenue not captured")}
				${build_kpi("Normal Time Cost", money(normal_time_cost))}
				${build_kpi("Fixed Labour Cost", money(fixed_labour_cost))}
				${build_kpi("Overtime Cost", money(normal_overtime_cost))}
				${build_kpi("Sunday Cost", money(sunday_cost))}
				${build_kpi("Public Holiday Cost", money(public_holiday_cost))}
				${build_kpi("Total Overtime Cost", money(total_overtime_cost))}
				${build_kpi("Total Labour Cost", money(total_labour_cost))}
				${build_kpi("Overtime % of Revenue", percent_of_revenue(total_overtime_cost, revenue))}
			</div>
		`;

		if (!revenue) {
			html += `
				<div class="sp-warning">
					Revenue has not been captured. Percentage-of-revenue values are shown as N/A.
				</div>
			`;
		}
	}

	html += `
		<div class="sp-summary-card">
			<div class="sp-summary-card-title">Cost Group Labour Cost Split</div>
			<div class="sp-table-wrap">
				<table class="sp-summary-table">
					<thead>
						<tr>
							<th>Cost Group</th>
							<th>Total Employees</th>
							<th>Normal Time Cost</th>
							<th>Fixed Labour Cost</th>
							<th>Overtime Cost</th>
							<th>Sunday Cost</th>
							<th>Public Holiday Cost</th>
							<th>Total Overtime Cost</th>
							<th>Total Labour Cost</th>
							<th>OT % Revenue</th>
							<th>Baseline OT Cost</th>
							<th>Excluded OT Cost</th>
						</tr>
					</thead>
					<tbody>
	`;

	cost_group_totals.forEach(function (row) {
		html += build_output_row(row);
	});

	html += `
					</tbody>
				</table>
			</div>
		</div>
	`;

	html += `
		<div class="sp-summary-card">
			<div class="sp-summary-card-title">Designation Detail</div>
			<div class="sp-table-wrap">
				<table class="sp-summary-table">
					<thead>
						<tr>
							<th>Cost Group</th>
							<th>Designation</th>
							<th>Pay Basis</th>
							<th>Total Employees</th>
							<th>Normal Hours</th>
							<th>Normal OT Hours</th>
							<th>Sunday Hours</th>
							<th>PPH Hours</th>
							<th>Normal Time Cost</th>
							<th>Fixed Labour Cost</th>
							<th>Overtime Cost</th>
							<th>Sunday Cost</th>
							<th>Public Holiday Cost</th>
							<th>Total Overtime Cost</th>
							<th>Total Labour Cost</th>
							<th>OT % Revenue</th>
						</tr>
					</thead>
					<tbody>
	`;

	details.forEach(function (row) {
		const normal_time_cost = flt(row.normal_cost || 0);
		const fixed_labour_cost = flt(row.fixed_costs || 0);
		const normal_overtime_cost = flt(row.normal_overtime_cost || 0);
		const sunday_cost = flt(row.sunday_overtime_cost || 0);
		const public_holiday_cost = flt(row.public_holiday_overtime_cost || 0);
		const total_overtime_cost = normal_overtime_cost + sunday_cost + public_holiday_cost;
		const total_labour_cost = normal_time_cost + fixed_labour_cost + total_overtime_cost;
		const revenue = flt(row.period_revenue || 0);

		html += `
			<tr>
				<td>${html_escape(row.cost_group || "-")}</td>
				<td><b>${html_escape(row.designation || "-")}</b></td>
				<td>${html_escape(row.pay_basis || "-")}</td>
				<td>${fmt(row.total_employees)}</td>
				<td>${fmt(row.normal_hours)}</td>
				<td>${fmt(row.normal_overtime_hours)}</td>
				<td>${fmt(row.sunday_hours)}</td>
				<td>${fmt(row.public_holiday_hours)}</td>
				<td>${money(normal_time_cost)}</td>
				<td>${money(fixed_labour_cost)}</td>
				<td>${money(normal_overtime_cost)}</td>
				<td>${money(sunday_cost)}</td>
				<td>${money(public_holiday_cost)}</td>
				<td><b>${money(total_overtime_cost)}</b></td>
				<td><b>${money(total_labour_cost)}</b></td>
				<td>${percent_of_revenue(total_overtime_cost, revenue)}</td>
			</tr>
		`;
	});

	html += `
					</tbody>
				</table>
			</div>
		</div>
	`;

	return html;
}

function build_output_row(row) {
	const normal_time_cost = flt(row.normal_cost || 0);
	const fixed_labour_cost = flt(row.fixed_costs || 0);
	const normal_overtime_cost = flt(row.normal_overtime_cost || 0);
	const sunday_cost = flt(row.sunday_overtime_cost || 0);
	const public_holiday_cost = flt(row.public_holiday_overtime_cost || 0);
	const total_overtime_cost = normal_overtime_cost + sunday_cost + public_holiday_cost;
	const total_labour_cost = normal_time_cost + fixed_labour_cost + total_overtime_cost;
	const revenue = flt(row.period_revenue || 0);

	return `
		<tr>
			<td><b>${html_escape(row.cost_group || "-")}</b></td>
			<td>${fmt(row.total_employees)}</td>
			<td>${money(normal_time_cost)}</td>
			<td>${money(fixed_labour_cost)}</td>
			<td>${money(normal_overtime_cost)}</td>
			<td>${money(sunday_cost)}</td>
			<td>${money(public_holiday_cost)}</td>
			<td><b>${money(total_overtime_cost)}</b></td>
			<td><b>${money(total_labour_cost)}</b></td>
			<td>${percent_of_revenue(total_overtime_cost, revenue)}</td>
			<td>${money(row.baseline_overtime_cost || 0)}</td>
			<td>${money(row.excluded_overtime_cost || 0)}</td>
		</tr>
	`;
}

function build_kpi(label, value) {
	return `
		<div class="sp-kpi">
			<div class="sp-kpi-label">${html_escape(label)}</div>
			<div class="sp-kpi-value">${value}</div>
		</div>
	`;
}

function group_by(rows, fieldname) {
	const result = {};

	(rows || []).forEach(function (row) {
		const key = row[fieldname] || "Unspecified";

		if (!result[key]) {
			result[key] = [];
		}

		result[key].push(row);
	});

	return result;
}

function sort_period_labels(a, b) {
	if (a === "Average") {
		return 1;
	}

	if (b === "Average") {
		return -1;
	}

	const date_a = parse_period_label_to_date(a);
	const date_b = parse_period_label_to_date(b);

	if (date_a && date_b) {
		return date_a - date_b;
	}

	if (date_a && !date_b) {
		return -1;
	}

	if (!date_a && date_b) {
		return 1;
	}

	return String(a || "").localeCompare(String(b || ""));
}

function parse_period_label_to_date(label) {
	if (!label) {
		return null;
	}

	const parts = String(label).trim().split(/\s+/);

	if (parts.length !== 2) {
		return null;
	}

	const month_map = {
		"January": 0,
		"February": 1,
		"March": 2,
		"April": 3,
		"May": 4,
		"June": 5,
		"July": 6,
		"August": 7,
		"September": 8,
		"October": 9,
		"November": 10,
		"December": 11,
	};

	const month = month_map[parts[0]];
	const year = cint(parts[1]);

	if (month === undefined || !year) {
		return null;
	}

	return new Date(year, month, 1);
}

function fmt(value) {
	const number_value = flt(value || 0);
	return number_value.toLocaleString(undefined, {
		minimumFractionDigits: 2,
		maximumFractionDigits: 2
	});
}

function money(value) {
	return `R ${fmt(value)}`;
}

function percent_of_revenue(value, revenue) {
	value = flt(value || 0);
	revenue = flt(revenue || 0);

	if (!revenue) {
		return "N/A";
	}

	return `${fmt((value / revenue) * 100)}%`;
}

function html_escape(value) {
	return String(value === undefined || value === null ? "" : value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#039;");
}

function get_shift_plan_visual_styles() {
	return `
		<style>
			.sp-section-title {
				font-size: 18px;
				font-weight: 800;
				margin: 16px 0 4px;
			}
			.sp-section-subtitle {
				color: var(--text-muted);
				font-size: 12px;
				margin-bottom: 12px;
			}
			.sp-visual-empty,
			.sp-loading {
				border: 1px dashed var(--border-color);
				border-radius: 8px;
				padding: 12px;
				color: var(--text-muted);
				background: var(--card-bg);
			}
			.sp-rotation-wrap,
			.sp-summary-card,
			.sp-month-card {
				border: 1px solid var(--border-color);
				border-radius: 8px;
				padding: 12px;
				background: var(--card-bg);
				margin-bottom: 12px;
			}
			.sp-rotation-header {
				display: flex;
				justify-content: space-between;
				align-items: center;
				gap: 12px;
				margin-bottom: 10px;
			}
			.sp-rotation-title,
			.sp-summary-card-title,
			.sp-month-title {
				font-weight: 800;
				font-size: 14px;
				margin-bottom: 8px;
			}
			.sp-rotation-help {
				font-size: 12px;
				color: var(--text-muted);
			}
			.sp-chip-row {
				display: flex;
				gap: 8px;
				align-items: center;
				margin-bottom: 10px;
				flex-wrap: wrap;
			}
			.sp-chip {
				border: 1px solid var(--border-color);
				border-radius: 999px;
				padding: 4px 10px;
				cursor: grab;
				background: var(--bg-color);
				font-weight: 600;
			}
			.sp-chip-day { border-color: #b8e1c1; }
			.sp-chip-night { border-color: #b9cef5; }
			.sp-chip-off { border-color: #ddd; }
			.sp-grid-scroll,
			.sp-table-wrap {
				overflow-x: auto;
				padding-bottom: 6px;
			}
			.sp-grid {
				border-collapse: separate;
				border-spacing: 0;
				width: max-content;
				min-width: 100%;
				font-size: 12px;
			}
			.sp-grid th,
			.sp-grid td {
				border: 1px solid var(--border-color);
				padding: 6px;
				text-align: center;
				min-width: 78px;
			}
			.sp-grid th {
				background: var(--control-bg);
				position: sticky;
				top: 0;
				z-index: 1;
				vertical-align: top;
			}
			.sp-day-head {
				line-height: 1.25;
			}
			.sp-day-head-main {
				font-weight: 800;
			}
			.sp-day-head-date,
			.sp-day-head-weekday {
				font-size: 11px;
				color: var(--text-muted);
				white-space: nowrap;
			}
			.sp-team-col {
				text-align: left !important;
				min-width: 110px !important;
				font-weight: 700;
				background: var(--control-bg);
				position: sticky;
				left: 0;
				z-index: 2;
			}
			.sp-cell {
				cursor: pointer;
				user-select: none;
				background: var(--bg-color);
			}
			.sp-cell:hover {
				outline: 2px solid var(--primary);
				outline-offset: -2px;
			}
			.sp-badge {
				display: inline-flex;
				justify-content: center;
				align-items: center;
				width: 28px;
				height: 24px;
				border-radius: 6px;
				font-weight: 800;
			}
			.sp-day { background: #e6f4ea; color: #137333; }
			.sp-night { background: #e8f0fe; color: #174ea6; }
			.sp-off { background: #f1f3f4; color: #5f6368; }
			.sp-btn {
				border: 1px solid var(--border-color);
				border-radius: 6px;
				background: var(--control-bg);
				padding: 4px 8px;
				cursor: pointer;
				font-size: 12px;
				margin-left: 4px;
				margin-bottom: 4px;
			}
			.sp-btn-primary {
				background: var(--primary);
				color: white;
				border-color: var(--primary);
			}
			.sp-calendar-grid {
				display: grid;
				grid-template-columns: repeat(7, minmax(170px, 1fr));
				gap: 6px;
				overflow-x: auto;
			}
			.sp-calendar-head {
				font-weight: 800;
				text-align: center;
				background: var(--control-bg);
				border: 1px solid var(--border-color);
				border-radius: 6px;
				padding: 6px;
			}
			.sp-calendar-cell {
				min-height: 145px;
				border: 1px solid var(--border-color);
				border-radius: 8px;
				padding: 8px;
				background: var(--bg-color);
			}
			.sp-calendar-blank {
				background: var(--control-bg);
				opacity: 0.45;
			}
			.sp-calendar-saturday {
				background: rgba(255, 193, 7, 0.08);
			}
			.sp-calendar-sunday {
				background: rgba(244, 67, 54, 0.08);
			}
			.sp-calendar-public-holiday {
				background: rgba(156, 39, 176, 0.08);
			}
			.sp-calendar-date-row {
				display: flex;
				justify-content: space-between;
				align-items: center;
				margin-bottom: 6px;
			}
			.sp-calendar-date {
				font-weight: 900;
				font-size: 16px;
			}
			.sp-day-type {
				font-size: 10px;
				color: var(--text-muted);
			}
			.sp-calendar-group {
				border-top: 1px solid var(--border-color);
				padding-top: 4px;
				margin-top: 4px;
			}
			.sp-calendar-group-title {
				font-weight: 800;
				font-size: 11px;
				margin-bottom: 2px;
			}
			.sp-mini-line {
				font-size: 11px;
				line-height: 1.45;
			}
			.sp-mini-label {
				display: inline-block;
				width: 17px;
				text-align: center;
				border-radius: 4px;
				font-weight: 800;
				margin-right: 4px;
			}
			.sp-hours {
				color: var(--text-muted);
				font-size: 10px;
			}
			.sp-cost-group-title {
				font-weight: 800;
				margin: 12px 0 6px;
			}
			.sp-summary-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 12px;
				white-space: nowrap;
			}
			.sp-summary-table th,
			.sp-summary-table td {
				border: 1px solid var(--border-color);
				padding: 6px 8px;
				text-align: right;
			}
			.sp-summary-table th:first-child,
			.sp-summary-table td:first-child,
			.sp-summary-table th:nth-child(2),
			.sp-summary-table td:nth-child(2) {
				text-align: left;
			}
			.sp-summary-table th {
				background: var(--control-bg);
				font-weight: 800;
			}
			.sp-kpi-grid {
				display: grid;
				grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
				gap: 10px;
				margin-bottom: 12px;
			}
			.sp-kpi {
				border: 1px solid var(--border-color);
				border-radius: 8px;
				padding: 10px;
				background: var(--card-bg);
			}
			.sp-kpi-label {
				font-size: 11px;
				color: var(--text-muted);
				margin-bottom: 4px;
			}
			.sp-kpi-value {
				font-size: 18px;
				font-weight: 900;
			}
			.sp-warning {
				border: 1px solid #f0ad4e;
				background: #fff8e1;
				color: #7a4f01;
				border-radius: 8px;
				padding: 10px 12px;
				margin-bottom: 12px;
				font-size: 12px;
			}
		</style>
	`;
}