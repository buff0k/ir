// Copyright (c) 2026, BuFf0k and contributors
// Branch Staffing Dashboard Page

const BSD_PY = "ir.industrial_relations.doctype.site_organogram.branch_staffing";
const BSD_ACCENT = "#b40000";
const BSD_GREEN = "#198754";

frappe.pages["ir-branch-staffing"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Branch Staffing Dashboard",
		single_column: true,
	});

	const app = new BranchStaffingDashboard(page, wrapper);
	wrapper.branch_staffing_dashboard = app;
	app.init();
};

class BranchStaffingDashboard {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.$main = $(page.main);
		this.controls = {};
		this.pie_chart = null;
		this.trend_chart = null;
		this.snapshot = [];
		this.missing = [];
		this.trend = null;
	}

	async init() {
		this.build_shell();
		this.make_controls();
		await this.refresh();
	}

	build_shell() {
		this.$main.html(`
			<div class="bsd-page">
				<div class="bsd-filters">
					<div class="bsd-filters__control" data-control="company"></div>
					<div class="bsd-filters__control" data-control="branches"></div>
					<div class="bsd-filters__control" data-control="from_date"></div>
					<div class="bsd-filters__control" data-control="to_date"></div>
					<div class="bsd-filters__actions">
						<button class="btn btn-sm btn-primary" data-action="refresh">Refresh</button>
					</div>
				</div>
				<div class="bsd-kpis">
					<div class="bsd-kpi" data-kpi="total">
						<div class="bsd-kpi__value">-</div>
						<div class="bsd-kpi__label">Total Roles</div>
					</div>
					<div class="bsd-kpi" data-kpi="filled">
						<div class="bsd-kpi__value">-</div>
						<div class="bsd-kpi__label">Filled</div>
					</div>
					<div class="bsd-kpi" data-kpi="vacant">
						<div class="bsd-kpi__value">-</div>
						<div class="bsd-kpi__label">Vacant</div>
					</div>
					<div class="bsd-kpi" data-kpi="fill_rate">
						<div class="bsd-kpi__value">-</div>
						<div class="bsd-kpi__label">Fill Rate</div>
					</div>
					<div class="bsd-kpi bsd-kpi--warn" data-kpi="missing">
						<div class="bsd-kpi__value">-</div>
						<div class="bsd-kpi__label">Branches Missing Organogram</div>
					</div>
				</div>
				<div class="bsd-charts">
					<div class="bsd-chart-card">
						<div class="bsd-chart-card__title">Current Staffing</div>
						<div class="bsd-chart-card__body" data-chart="pie"></div>
					</div>
					<div class="bsd-chart-card">
						<div class="bsd-chart-card__title">Structure Trend</div>
						<div class="bsd-chart-card__body" data-chart="trend"></div>
					</div>
				</div>
				<div class="bsd-section">
					<div class="bsd-section__title">Branches Missing a Current Organogram</div>
					<div class="bsd-missing" data-missing></div>
				</div>
				<div class="bsd-section">
					<div class="bsd-section__title">Designation Breakdown</div>
					<div class="bsd-section__hint">Click a row to open it in the Branch Staffing Overview report. Click a Filled count to see those Employees.</div>
					<div class="bsd-table" data-table></div>
				</div>
			</div>
		`);
	}

	make_controls() {
		this.controls.company = frappe.ui.form.make_control({
			parent: this.$main.find('[data-control="company"]'),
			df: { fieldtype: "Link", label: "Company", options: "Company", fieldname: "company" },
			render_input: true,
		});
		this.controls.company.set_value(frappe.defaults.get_default("company") || "");

		this.controls.branches = frappe.ui.form.make_control({
			parent: this.$main.find('[data-control="branches"]'),
			df: {
				fieldtype: "MultiSelectList",
				label: "Branches",
				fieldname: "branches",
				get_data: (txt) => frappe.db.get_link_options("Branch", txt),
			},
			render_input: true,
		});

		this.controls.from_date = frappe.ui.form.make_control({
			parent: this.$main.find('[data-control="from_date"]'),
			df: { fieldtype: "Date", label: "From Date", fieldname: "from_date" },
			render_input: true,
		});

		this.controls.to_date = frappe.ui.form.make_control({
			parent: this.$main.find('[data-control="to_date"]'),
			df: { fieldtype: "Date", label: "To Date", fieldname: "to_date" },
			render_input: true,
		});

		this.$main.find('[data-action="refresh"]').on("click", () => this.refresh());
	}

	get_filters() {
		return {
			company: this.controls.company.get_value() || "",
			branches: this.controls.branches.get_value() || [],
			from_date: this.controls.from_date.get_value() || "",
			to_date: this.controls.to_date.get_value() || "",
		};
	}

	async refresh() {
		const filters = this.get_filters();
		this.page.set_indicator("Loading...", "orange");

		const [snapshot_r, missing_r, trend_r] = await Promise.all([
			frappe.call({
				method: `${BSD_PY}.get_current_snapshot`,
				args: { company: filters.company || null, branches: filters.branches },
			}),
			frappe.call({
				method: `${BSD_PY}.get_missing_organograms`,
				args: { branches: filters.branches },
			}),
			frappe.call({
				method: `${BSD_PY}.get_trend_data`,
				args: {
					company: filters.company || null,
					branches: filters.branches,
					from_date: filters.from_date || null,
					to_date: filters.to_date || null,
				},
			}),
		]);

		this.snapshot = snapshot_r.message || [];
		this.missing = missing_r.message || [];
		this.trend = trend_r.message || null;

		this.render_kpis();
		this.render_pie_chart();
		this.render_trend_chart();
		this.render_missing_panel();
		this.render_table();

		this.page.clear_indicator();
	}

	render_kpis() {
		const total = this.snapshot.reduce((sum, r) => sum + r.total, 0);
		const filled = this.snapshot.reduce((sum, r) => sum + r.filled, 0);
		const vacant = this.snapshot.reduce((sum, r) => sum + r.vacant, 0);
		const fill_rate = total ? Math.round((filled / total) * 1000) / 10 : 0;

		this.$main.find('[data-kpi="total"] .bsd-kpi__value').text(total);
		this.$main.find('[data-kpi="filled"] .bsd-kpi__value').text(filled);
		this.$main.find('[data-kpi="vacant"] .bsd-kpi__value').text(vacant);
		this.$main.find('[data-kpi="fill_rate"] .bsd-kpi__value').text(`${fill_rate}%`);
		this.$main.find('[data-kpi="missing"] .bsd-kpi__value').text(this.missing.length);
	}

	render_pie_chart() {
		const filled = this.snapshot.reduce((sum, r) => sum + r.filled, 0);
		const vacant = this.snapshot.reduce((sum, r) => sum + r.vacant, 0);
		const $target = this.$main.find('[data-chart="pie"]');
		$target.empty();

		if (!filled && !vacant) {
			$target.html('<div class="bsd-empty">No current Organogram data for this scope.</div>');
			return;
		}

		this.pie_chart = new frappe.Chart($target[0], {
			data: {
				labels: ["Filled", "Vacant"],
				datasets: [{ values: [filled, vacant] }],
			},
			type: "pie",
			height: 260,
			colors: [BSD_GREEN, BSD_ACCENT],
		});
	}

	render_trend_chart() {
		const $target = this.$main.find('[data-chart="trend"]');
		$target.empty();

		if (!this.trend || !this.trend.data || !this.trend.data.labels.length) {
			$target.html('<div class="bsd-empty">No structure changes recorded in this range yet.</div>');
			return;
		}

		this.trend_chart = new frappe.Chart($target[0], {
			data: this.trend.data,
			type: this.trend.type || "line",
			height: this.trend.height || 260,
			colors: this.trend.colors || [BSD_GREEN, BSD_ACCENT],
		});
	}

	render_missing_panel() {
		const $target = this.$main.find("[data-missing]");

		if (!this.missing.length) {
			$target.html('<div class="bsd-empty">Every branch in this scope currently has a valid Site Organogram.</div>');
			return;
		}

		$target.html(
			this.missing
				.map(
					(branch) => `
					<div class="bsd-missing__row">
						<span class="bsd-missing__branch">${frappe.utils.escape_html(branch)}</span>
						<span class="bsd-missing__actions">
							<a data-route="ir-site-plan-design">Site Plan Designer</a>
							<a data-route="ir-organogram-design">Organogram Designer</a>
						</span>
					</div>
				`
				)
				.join("")
		);

		$target.find("a[data-route]").on("click", (e) => {
			frappe.set_route($(e.currentTarget).attr("data-route"));
		});
	}

	render_table() {
		const $target = this.$main.find("[data-table]");

		if (!this.snapshot.length) {
			$target.html('<div class="bsd-empty">No current Organogram data for this scope.</div>');
			return;
		}

		const rows = [...this.snapshot].sort(
			(a, b) => a.branch.localeCompare(b.branch) || a.designation.localeCompare(b.designation)
		);

		$target.html(`
			<table class="bsd-table__el">
				<thead>
					<tr>
						<th>Branch</th>
						<th>Designation</th>
						<th>Total</th>
						<th>Filled</th>
						<th>Vacant</th>
					</tr>
				</thead>
				<tbody>
					${rows
						.map(
							(r) => `
						<tr class="bsd-table__row" data-branch="${frappe.utils.escape_html(r.branch)}" data-designation="${frappe.utils.escape_html(r.designation)}">
							<td>${frappe.utils.escape_html(r.branch)}</td>
							<td>${frappe.utils.escape_html(r.designation)}</td>
							<td>${r.total}</td>
							<td class="bsd-table__filled">${r.filled}</td>
							<td>${r.vacant}</td>
						</tr>
					`
						)
						.join("")}
				</tbody>
			</table>
		`);

		$target.find(".bsd-table__filled").on("click", (e) => {
			e.stopPropagation();
			const $row = $(e.currentTarget).closest(".bsd-table__row");
			frappe.route_options = {
				branch: $row.data("branch"),
				designation: $row.data("designation"),
				status: "Active",
			};
			frappe.set_route("List", "Employee", "List");
		});

		$target.find(".bsd-table__row").on("click", (e) => {
			const $row = $(e.currentTarget);
			frappe.route_options = { branches: [$row.data("branch")] };
			frappe.set_route("query-report", "Branch Staffing Overview");
		});
	}
}
