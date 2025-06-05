// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('KPI Template', {
    onload_post_render(frm) {
        setup_live_hooks(frm);
        update_kpi_visuals(frm);
    },

    refresh(frm) {
        setup_live_hooks(frm);
        update_kpi_visuals(frm);
    }
});

frappe.ui.form.on('KPI Template Criteria', {
    weight(frm) {
        update_kpi_visuals(frm);
    },
    parent_kpi(frm) {
        update_kpi_visuals(frm);
    },
    kpi(frm, cdt, cdn) {
        frappe.db.get_doc('Key Performance Indicator', locals[cdt][cdn].kpi).then(doc => {
            frappe.model.set_value(cdt, cdn, 'parent_kpi', doc.is_group ? null : doc.parent_kpi || null);
            update_kpi_visuals(frm);
        });
    }
});

function setup_live_hooks(frm) {
    if (frm.fields_dict.kpi?.grid) {
        frm.fields_dict.kpi.grid.on_grid_after_edit = () => {
            update_kpi_visuals(frm);
        };
    }
}

function update_kpi_visuals(frm) {
    const group_map = {};

    // Sum weights per parent KPI
    frm.doc.kpi.forEach(row => {
        if (row.weight && row.parent_kpi) {
            group_map[row.parent_kpi] = (group_map[row.parent_kpi] || 0) + row.weight;
        }
    });

    // Apply to group KPIs
    frm.doc.kpi.forEach(row => {
        if (group_map[row.kpi] !== undefined) {
            row.weight = flt(group_map[row.kpi], 2);
        }
    });

    // Update total
    let total = 0;
    frm.doc.kpi.forEach(row => {
        if (row.weight && (!row.parent_kpi || group_map[row.kpi] !== undefined)) {
            total += row.weight;
        }
    });
    frm.set_value('total', flt(total, 2));

    // Update effective weight
    const group_weights = {};
    frm.doc.kpi.forEach(row => {
        if (group_map[row.kpi] !== undefined) {
            group_weights[row.kpi] = row.weight || 0;
        }
    });

    frm.doc.kpi.forEach(row => {
        if (row.parent_kpi) {
            const parent_weight = group_weights[row.parent_kpi] || 0;
            row.effective_weight = flt((row.weight || 0) * (parent_weight / 100), 2);
        } else {
            row.effective_weight = row.weight || 0;
        }
    });

    frm.fields_dict.kpi.grid.refresh();
}
