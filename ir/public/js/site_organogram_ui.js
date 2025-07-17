// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

async function render_organogram_ui(frm) {
    if (!frm.doc.branch || !frm.doc.location) return;

    const wrapper = frm.fields_dict.html.$wrapper;
    wrapper.empty().html(`<p>Rendering organogram...</p>`);

    const asset_categories = (frm.doc.asset_categories || []).map(r => r.asset_category);
    const team_shifts = ['Team A', 'Team B', 'Team C'];
    const assigned = frm.doc.employee_list || [];

    const [employeesRes, assetsRes] = await Promise.all([
        frappe.call('frappe.client.get_list', {
            doctype: 'Employee',
            filters: { branch: frm.doc.branch },
            fields: ['name', 'employee_name', 'designation']
        }),
        frappe.call('frappe.client.get_list', {
            doctype: 'Asset',
            filters: {
                location: frm.doc.location,
                ...(asset_categories.length && { asset_category: ['in', asset_categories] })
            },
            fields: ['name', 'item_name', 'asset_category']
        })
    ]);

    const employees = employeesRes.message || [];
    const assets = assetsRes.message || [];

    let html = `<style>
        .drop-zone {
            border: 1px dashed #aaa; min-height: 12px; padding: 3px;
            background: #f0f8ff; margin: 2px 0; border-radius: 4px;
        }
        .card {
            border: 1px solid #999; padding: 6px; border-radius: 4px;
            font-size: 12px; margin: 2px; cursor: grab; background: white;
            width: 160px; display: inline-block; position: relative;
        }
        .employee-card { border-left: 5px solid #007bff; }
        .card .remove-btn {
            position: absolute; top: -6px; right: -6px; background: red;
            color: white; border-radius: 50%; padding: 2px 6px; cursor: pointer;
            font-size: 10px; line-height: 1;
        }
        .card-pool { border: 1px solid #ccc; padding: 6px; margin: 10px 0; border-radius: 6px; background: #f9f9f9; }
        .header-cell { font-weight: bold; padding: 6px 0; }
        .machine-label { font-weight: bold; }
        .panel-title { font-weight: bold; font-size: 14px; margin: 12px 0 6px; }
        .side-by-side { display: flex; gap: 12px; }
        .machine-grid { display: grid; grid-template-columns: 1fr repeat(3, 1fr); gap: 4px; align-items: start; }
    </style>`;

    // Unassigned Employees Pool
    html += `<div class="panel-title">Unassigned Employees</div><div class="card-pool drop-zone" id="unassigned-pool" data-unassigned="true">`;
    for (let emp of employees) {
        if (assigned.find(a => a.employee === emp.name)) continue;
        html += render_card_html({
            employee: emp.name,
            employee_name: emp.employee_name,
            designation: emp.designation
        });
    }
    html += `</div>`;

    // Day Shift and Support side-by-side
    html += `<div class="panel-title">Day Shift Assignments</div><div class="side-by-side">`;
    html += render_shift_panel('Day Shift', assigned, [], 'General Roles');
    html += render_shift_panel('Support', assigned, [], 'Support Team');
    html += `</div>`;

    // Shift Teams - Asset column + Team columns
    html += `<div class="panel-title">Shift Teams</div><div class="machine-grid">`;
    html += `<div class="header-cell">Asset</div>`;
    for (let shift of team_shifts) html += `<div class="header-cell">${shift}</div>`;

    for (let asset of assets) {
        html += `<div class="machine-label">${asset.name} - ${asset.item_name}</div>`;
        for (let shift of team_shifts) {
            const match = assigned.find(r => r.asset === asset.name && r.shift === shift);
            html += `<div class="drop-zone" data-shift="${shift}" data-asset="${asset.name}" data-asset_name="${asset.item_name}">`;
            if (match) html += render_card_html(match, true);
            html += `</div>`;
        }
    }
    html += `</div>`;

    // Night Shift
    html += `<div class="panel-title">Night Shift (General Roles)</div>`;
    html += render_shift_panel('Night Shift', assigned);

    wrapper.html(html);
    enable_organogram_drag_and_drop(frm);
}

function render_shift_panel(shift, assigned, assets = [], label = '') {
    let html = `<div class="card-pool" style="flex:1"><div class="header-cell">${label || shift}</div>`;
    const rows = assigned.filter(r => r.shift === shift && !r.asset);
    for (let r of rows) {
        html += `<div class="drop-zone" data-shift="${shift}"></div>`;
        html += render_card_html(r, true);
    }
    html += `<div class="drop-zone" data-shift="${shift}"></div>`;
    html += `</div>`;
    return html;
}

function render_card_html(r, show_remove = false) {
    const removeBtn = show_remove
        ? `<div class="remove-btn" data-remove="${r.employee}">×</div>`
        : '';
    return `<div class="card employee-card" draggable="true"
                data-employee="${r.employee}"
                data-employee_name="${r.employee_name || ''}"
                data-designation="${r.designation || ''}">
                ${removeBtn}
                ${r.employee_name || r.employee} (${r.employee})<br>${r.designation || ''}
            </div>`;
}

function enable_organogram_drag_and_drop(frm) {
    document.querySelectorAll('.card').forEach(card => {
        card.addEventListener('dragstart', e => {
            const data = {};
            for (const attr of card.attributes) {
                if (attr.name.startsWith('data-')) {
                    data[attr.name.replace('data-', '')] = attr.value;
                }
            }
            e.dataTransfer.setData('application/json', JSON.stringify(data));
        });
    });

    document.querySelectorAll('.drop-zone').forEach(zone => {
        zone.addEventListener('dragover', e => e.preventDefault());
        zone.addEventListener('drop', async e => {
            e.preventDefault();
            const data = JSON.parse(e.dataTransfer.getData('application/json'));

            const shift = zone.dataset.shift;
            const asset = zone.dataset.asset || null;
            const asset_name = zone.dataset.asset_name || null;

            // Handle unassigned drag
            if (zone.dataset.unassigned) {
                frm.doc.employee_list = frm.doc.employee_list.filter(r => r.employee !== data.employee);
                frm.refresh_field('employee_list');
                render_organogram_ui(frm);
                return;
            }

            // prevent duplicates
            const exists = frm.doc.employee_list.find(r =>
                r.employee === data.employee &&
                r.shift === shift &&
                (r.asset || "") === (asset || "")
            );
            if (exists) {
                frappe.msgprint(`Employee ${data.employee_name} is already assigned to this slot.`);
                return;
            }

            // remove prior assignment of this employee (so dragging acts like move)
            frm.doc.employee_list = frm.doc.employee_list.filter(r => r.employee !== data.employee);

            const row = frm.add_child('employee_list');
            row.employee = data.employee;
            row.shift = shift;
            row.asset = asset;
            row.asset_name = asset_name;

            await frappe.call({
                method: 'frappe.client.get',
                args: { doctype: 'Employee', name: data.employee },
                callback: function(r) {
                    if (r.message) {
                        frappe.model.set_value(row.doctype, row.name, 'employee_name', r.message.employee_name);
                        frappe.model.set_value(row.doctype, row.name, 'designation', r.message.designation);
                    }
                }
            });

            frm.refresh_field('employee_list');
            render_organogram_ui(frm);
        });
    });

    // remove buttons
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', e => {
            const id = btn.dataset.remove;
            frm.doc.employee_list = frm.doc.employee_list.filter(r => r.employee !== id);
            frm.refresh_field('employee_list');
            render_organogram_ui(frm);
        });
    });
}
