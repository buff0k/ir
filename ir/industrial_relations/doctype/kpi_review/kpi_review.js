// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('KPI Review', {
    onload(frm) {
        if (frm.doc.kpi_template && !frm.doc.__islocal) {
            render_kpi_sections(frm);
        }
    },

    employee(frm) {
        if (frm.doc.employee) {
            frappe.db.get_doc('Employee', frm.doc.employee).then(emp => {
                frm.set_value('employee_name', emp.employee_name);
                frm.set_value('employee_designation', emp.designation);
            });
        }
    },

    manager(frm) {
        if (frm.doc.manager) {
            frappe.db.get_doc('Employee', frm.doc.manager).then(emp => {
                frm.set_value('manager_name', emp.employee_name);
                frm.set_value('manager_designation', emp.designation);
            });
        }
    },

    kpi_template(frm) {
        if (!frm.doc.kpi_template) return;

        frappe.db.get_doc('KPI Template', frm.doc.kpi_template).then(template => {
            frm.clear_table('review_data');

            (template.kpi || []).forEach(row => {
                frm.add_child('review_data', {
                    kpi: row.kpi,
                    weight: row.weight,
                    max_score: row.max_score,
                    score: 0,
                    weighted_score: 0,
                    notes: ''
                });
            });

            frm.refresh_field('review_data');
            render_kpi_sections(frm);
        });
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

                    ${!isGroup ? `
                        <div>
                            <input type="range" class="form-range score-input" min="0" max="${row.max_score}" step="1" data-row="${i}" value="${row.score || 0}" />
                            <span class="score-value" id="sv-${i}">${row.score || 0}</span> / ${row.max_score}
                        </div>` : `
                        <div>
                            <em>Score will be calculated from: ${childNames || 'its children'}</em>
                        </div>`}

                    <div class="mt-2">
                        <label>Notes:</label>
                        <textarea class="form-control note-input" rows="2" data-row="${i}">${row.notes || ''}</textarea>
                    </div>

                    <div class="mt-2">
                        <strong>Weighted Score:</strong> <span class="weighted-output" id="ws-${i}">${row.weighted_score || 0}%</span>
                    </div>
                </div>
            `;
        }).join("");

        frm.fields_dict.kpi_rendered.$wrapper.html(html);

        const updateScoreSummary = () => {
            let total = 0;
            let max = 0;

            const isGroup = {};
            const parentMap = {};

            frm.doc.review_data.forEach(r => {
                const kpi = kpiMap[r.kpi];
                if (!kpi) return;
                isGroup[r.kpi] = kpi.is_group;

                const parent = kpi.parent_kpi;
                if (parent) {
                    parentMap[parent] = parentMap[parent] || [];
                    parentMap[parent].push(r);
                }
            });

            // 1. Calculate weighted scores for leaf KPIs
            frm.doc.review_data.forEach((r, i) => {
                if (!isGroup[r.kpi]) {
                    const ws = flt((r.score / r.max_score) * r.weight, 2);
                    frappe.model.set_value(r.doctype, r.name, 'weighted_score', ws);
                    frm.fields_dict.kpi_rendered.$wrapper.find(`#ws-${i}`).text(`${ws}%`);
                }
            });

            // 2. Calculate parent scores and weighted scores (preserving fixed max_score)
            frm.doc.review_data.forEach((r, i) => {
                if (isGroup[r.kpi]) {
                    const children = parentMap[r.kpi] || [];

                    const total_score = children.reduce((acc, c) => acc + (c.score || 0), 0);
                    const total_max = children.reduce((acc, c) => acc + (c.max_score || 0), 0);
                    const ratio = total_max > 0 ? total_score / total_max : 0;

                    const scaled_score = flt(ratio * r.max_score, 2);
                    const group_ws = children.reduce((acc, c) => acc + (c.weighted_score || 0), 0);

                    frappe.model.set_value(r.doctype, r.name, 'score', scaled_score);
                    frappe.model.set_value(r.doctype, r.name, 'weighted_score', flt(group_ws, 2));

                    frm.fields_dict.kpi_rendered.$wrapper.find(`#sv-${i}`).text(`${scaled_score}`);
                    frm.fields_dict.kpi_rendered.$wrapper.find(`#ws-${i}`).text(`${flt(group_ws, 2)}%`);
                }
            });

            // 3. Total score and max from leaf (non-group) KPIs only
            let total_score = 0;
            let total_max = 0;
            frm.doc.review_data.forEach(r => {
                if (!isGroup[r.kpi]) {
                    total_score += r.score || 0;
                    total_max += r.max_score || 0;
                }
            });

            const total_pct = total_max > 0 ? flt((total_score / total_max) * 100, 2) : 0;
            frm.set_value("score", `${flt(total_score, 2)} / ${flt(total_max, 2)} (${total_pct}%)`);
        };

        // Score input
        frm.fields_dict.kpi_rendered.$wrapper.find('.score-input').on('input', function () {
            const i = parseInt($(this).data('row'));
            const val = parseFloat($(this).val()) || 0;
            const row = frm.doc.review_data[i];

            frappe.model.set_value(row.doctype, row.name, 'score', val);
            frm.fields_dict.kpi_rendered.$wrapper.find(`#sv-${i}`).text(`${val}`);
            updateScoreSummary();
        });

        // Notes input
        frm.fields_dict.kpi_rendered.$wrapper.find('.note-input').on('input', function () {
            const i = parseInt($(this).data('row'));
            const val = $(this).val();
            const row = frm.doc.review_data[i];

            frappe.model.set_value(row.doctype, row.name, 'notes', val);
        });

        updateScoreSummary();
    };

    const uniqueKPIs = [...new Set(data.map(row => row.kpi))];
    const kpiPromises = uniqueKPIs.map(kpi =>
        frappe.db.get_doc('Key Performance Indicator', kpi).then(doc => {
            kpiMap[kpi] = doc;
        })
    );

    Promise.all(kpiPromises).then(render);
}
