// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Area KPI Review', {
    onload(frm) {
        setup_buttons(frm);
        if (frm.doc.kpi_template && !frm.doc.__islocal) {
            render_kpi_sections(frm);
        }
    },

    refresh(frm) {
        setup_buttons(frm);
        if (frm.doc.kpi_template && !frm.doc.__islocal) {
            render_kpi_sections(frm);
        }
    },

    date_of_review(frm) {
        if (frm.doc.date_of_review) {
            let date = frappe.datetime.str_to_obj(frm.doc.date_of_review);
            date.setMonth(date.getMonth() - 1);
            frm.set_value('date_under_review', frappe.datetime.obj_to_str(date));
        }
    }
});

function setup_buttons(frm) {
    frm.add_custom_button('Fetch KPI Reviews for Area', async () => {
        if (!frm.doc.area || !frm.doc.date_under_review) {
            frappe.msgprint("Please select an Area and Date Under Review first.");
            return;
        }

        const area_doc = await frappe.db.get_doc('Area Setup', frm.doc.area);
        const { start, end } = getMonthRange(frm.doc.date_under_review);

        frm.clear_table('kpi_reviews');

        let collected_templates = new Set();

        for (const row of area_doc.branches) {
            const site = row.branch;

            const result = await frappe.db.get_list('KPI Review', {
                filters: {
                    branch: site,
                    date_under_review: ['between', [start, end]],
                    docstatus: 1
                },
                fields: ['name', 'branch', 'kpi_template', 'score'],
                limit: 1
            });

            if (result.length) {
                const r = result[0];
                frm.add_child('kpi_reviews', {
                    kpi_review: r.name,
                    branch: r.branch,
                    kpi_template: r.kpi_template,
                    score: r.score
                });
                if (r.kpi_template) {
                    collected_templates.add(r.kpi_template);
                }
            } else {
                frappe.msgprint(`No submitted KPI Review for site <b>${site}</b> in selected month.`);
            }
        }

        frm.refresh_field('kpi_reviews');

        if (collected_templates.size === 1) {
            frm.set_value('kpi_template', [...collected_templates][0]);
        } else if (collected_templates.size > 1) {
            frappe.msgprint("Warning: Multiple KPI Templates found across reviews. Please fix before aggregation.");
        }
    });

    frm.add_custom_button('Aggregate KPI Data', () => {
        frappe.call({
            method: 'ir.industrial_relations.doctype.area_kpi_review.area_kpi_review.aggregate_area_kpi_data',
            args: { docname: frm.doc.name },
            callback: r => {
                frm.reload_doc();
            }
        });
    });
}

function getMonthRange(date_str) {
    const date = frappe.datetime.str_to_obj(date_str);
    const firstDay = new Date(date.getFullYear(), date.getMonth(), 1);
    const lastDay = new Date(date.getFullYear(), date.getMonth() + 1, 0);
    return {
        start: frappe.datetime.obj_to_str(firstDay),
        end: frappe.datetime.obj_to_str(lastDay)
    };
}

frappe.ui.form.on('Area KPI Review Sites', {
    kpi_review(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.kpi_review) {
            frappe.db.get_doc('KPI Review', row.kpi_review).then(doc => {
                frappe.model.set_value(cdt, cdn, 'branch', doc.branch);
                frappe.model.set_value(cdt, cdn, 'kpi_template', doc.kpi_template);
                frappe.model.set_value(cdt, cdn, 'score', doc.score);

                if (!frm.doc.kpi_template) {
                    frm.set_value('kpi_template', doc.kpi_template);
                }
            });
        }
    }
});

frappe.ui.form.on('KPI Review Employees', {
    employee(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.employee) {
            frappe.db.get_doc('Employee', row.employee).then(emp => {
                frappe.model.set_value(cdt, cdn, 'employee_name', emp.employee_name);
                frappe.model.set_value(cdt, cdn, 'designation', emp.designation);
            });
        }
    }
});

frappe.ui.form.on('KPI Review Reviewers', {
    reviewer(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (row.reviewer) {
            frappe.db.get_doc('Employee', row.reviewer).then(emp => {
                frappe.model.set_value(cdt, cdn, 'employee_name', emp.employee_name);
                frappe.model.set_value(cdt, cdn, 'designation', emp.designation);
            });
        }
    }
});

function render_kpi_sections(frm) {
    const data = frm.doc.review_data || [];
    const kpiMap = {};

    const render = () => {
        const html = data.map((row, i) => {
            const isGroup = kpiMap[row.kpi]?.is_group;
            const childNames = data
                .filter(r => kpiMap[r.kpi]?.parent_kpi === row.kpi)
                .map(r => r.kpi)
                .join(", ");

            return `
                <div class="kpi-section" style="margin-bottom: 20px; border-bottom: 1px solid #ddd; padding-bottom: 10px;">
                    <h5>${row.kpi} (${row.weight}%)</h5>
                    ${kpiMap[row.kpi]?.description ? `<p class="text-muted">${frappe.utils.escape_html(kpiMap[row.kpi].description)}</p>` : ''}

                    ${!isGroup ? `
                        <div class="d-flex align-items-center">
                            <input type="range" class="form-range score-input" min="0" max="${row.max_score}" step="1" data-row="${i}" value="${row.score || 0}" />
                            <span class="ms-2">${row.score || 0} / ${row.max_score}</span>
                        </div>` : `
                        <div>
                            <em>Score will be calculated from: ${childNames || 'its children'}</em>
                        </div>`}

                    <div class="mt-2">
                        <label>Notes:</label>
                        <div class="form-control" style="white-space: pre-line; min-height: 6em; max-height: 150px; overflow-y: auto;">${frappe.utils.escape_html(row.notes || '')}</div>
                    </div>

                    <div class="mt-2">
                        <strong>Weighted Score:</strong> <span>${row.weighted_score || 0}%</span>
                    </div>
                </div>
            `;
        }).join("");

        frm.fields_dict.kpi_rendered.$wrapper.html(html);

        frm.fields_dict.kpi_rendered.$wrapper.find('.score-input').on('input', function () {
            const i = parseInt($(this).data('row'));
            const val = parseFloat($(this).val()) || 0;
            const row = frm.doc.review_data[i];

            frappe.model.set_value(row.doctype, row.name, 'score', val);
            frm.set_value('score', ''); // clear calculated score until re-aggregated if needed
        });
    };

    const uniqueKPIs = [...new Set(data.map(row => row.kpi))];
    const kpiPromises = uniqueKPIs.map(kpi =>
        frappe.db.get_doc('Key Performance Indicator', kpi).then(doc => {
            kpiMap[kpi] = doc;
        })
    );

    Promise.all(kpiPromises).then(render);
}
