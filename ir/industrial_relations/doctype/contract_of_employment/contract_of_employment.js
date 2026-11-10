// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contract of Employment', {
    refresh: function(frm) {
        frm.events.toggle_retirement_fields(frm);
        frm.events.toggle_expiry_field(frm);
        frm.events.toggle_project_fields(frm);
        frm.events.toggle_end_date_field(frm);
        frm.events.toggle_working_hours_section(frm);
        render_earnings_editor(frm);
        render_deductions_editor(frm);

        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Pull Contract Defaults'), () => {
                frm.events.prefill_contract_defaults(frm, true);
            });
        }
    },

    working_hours_type: function(frm) {
        frm.events.toggle_working_hours_section(frm);
    },

    toggle_working_hours_section: function(frm) {
        frm.toggle_display('monday_section', frm.doc.working_hours_type !== 'Shift Worker');
    },

    after_save: function(frm) {
        render_earnings_editor(frm);
        render_deductions_editor(frm);
    },

    onload: function(frm) {
        frm.set_query('contract_template', () => ({ filters: { docstatus: 1 } }));
    },

    employee: function(frm) {
        if (frm.doc.employee) {
            frappe.db.get_doc('Employee', frm.doc.employee).then(doc => {
                frm.set_value('employee_name', doc.employee_name || '');
                frm.set_value('date_of_birth', doc.date_of_birth || '');
                frm.set_value('date_of_joining', doc.date_of_joining || '');
                frm.set_value('company', doc.company || '');
                frm.set_value('designation', doc.designation || '');
                frm.set_value('branch', doc.branch || '');
                const addressLines = (doc.current_address || '').split('\n').map(line => line.trim());
                const combinedAddress = addressLines.join(', ');
                frm.set_value('current_address', combinedAddress);
                const zaId = (doc.za_id_number || '').trim();
                const passport = (doc.passport_number || '').trim();
                let idValue = "With ID: ________________________";
                if (zaId) {
                    idValue = `With RSA ID: ${zaId}`;
                } else if (passport) {
                    idValue = `With Passport No: ${passport}`;
                }
                frm.set_value('custom_id_number', idValue);
                if (doc.company) {
                    frappe.db.get_value('Company', doc.company, 'default_letter_head', (r) => {
                        frm.set_value('letter_head', r.default_letter_head || '');
                    });
                }
            }).then(() => {
                frm.events.check_pending_status_change(frm);
                // Convenience default for a brand-new contract only - an
                // existing Draft never gets its Deductions/Provident Fund
                // silently touched just because Employee changed. Use the
                // "Pull Contract Defaults" button (see refresh) to run the
                // same thing explicitly, any time, on any Draft.
                if (frm.is_new()) {
                    frm.events.prefill_contract_defaults(frm);
                }
            });
        }
    },

    prefill_contract_defaults: function(frm, explicit) {
        // Mirrors the server's own _prefill_contract_defaults() (contract_
        // of_employment.py) - adds whichever of the site's default
        // Deductions aren't already on this contract (never duplicates one
        // already present, so it's safe to run on a contract that already
        // has some), and fills Provident Fund only while it's still blank
        // (never overwrites a value someone - or a prior save - already
        // set). Usable on any Draft, not just a brand-new one - see the
        // "Pull Contract Defaults" button in refresh, which is how an
        // existing Draft missing rows (e.g. one saved before this prefill
        // existed) gets them without retyping each one by hand.
        if (frm.doc.docstatus !== 0) return;
        frappe.db.get_doc('Contract Defaults').then((defaults) => {
            const existing = new Set((frm.doc.deductions || []).map((row) => row.salary_component));
            let added = 0;
            (defaults.default_deductions || []).forEach((row) => {
                if (existing.has(row.salary_component)) return;
                frm.add_child('deductions', { salary_component: row.salary_component });
                existing.add(row.salary_component);
                added += 1;
            });
            if (added) {
                frm.refresh_field('deductions');
                render_deductions_editor(frm);
                frm.dirty();
            }

            let pf_set = false;
            if (!frm.doc.provident_fund_contribution && defaults.provident_fund_contribution) {
                frm.set_value('provident_fund_contribution', defaults.provident_fund_contribution);
                pf_set = true;
            }

            if (explicit) {
                if (added || pf_set) {
                    const parts = [];
                    if (added) parts.push(__('{0} deduction(s) added', [added]));
                    if (pf_set) parts.push(__('Provident Fund rate set'));
                    frappe.show_alert({ message: parts.join(' - '), indicator: 'green' });
                } else {
                    frappe.show_alert({ message: __('Already up to date with Contract Defaults.'), indicator: 'blue' });
                }
            }
        });
    },

    check_pending_status_change: function(frm) {
        frappe.call({
            method: 'ir.industrial_relations.doctype.contract_of_employment.contract_of_employment.get_pending_status_change',
            args: { employee: frm.doc.employee },
            callback: function(r) {
                const pending = r.message;
                if (!pending) return;

                const branch_differs = pending.new_branch && pending.new_branch !== frm.doc.branch;
                const designation_differs = pending.new_designation && pending.new_designation !== frm.doc.designation;
                if (!branch_differs && !designation_differs) return;

                let diff_html = `<p>${__("A Draft Status Change Form ({0}, effective {1}) is pending for this employee:", [pending.name, frappe.datetime.str_to_user(pending.effective_date)])}</p>`;
                diff_html += `<table class="table table-bordered"><thead><tr><th></th><th>${__("Employee Record")}</th><th>${__("Pending Status Change")}</th></tr></thead><tbody>`;
                if (branch_differs) {
                    diff_html += `<tr><td>${__("Branch")}</td><td>${frm.doc.branch || ""}</td><td>${pending.new_branch}</td></tr>`;
                }
                if (designation_differs) {
                    diff_html += `<tr><td>${__("Designation")}</td><td>${frm.doc.designation || ""}</td><td>${pending.new_designation}</td></tr>`;
                }
                diff_html += `</tbody></table>`;

                const dialog = new frappe.ui.Dialog({
                    title: __("Pending Status Change Found"),
                    fields: [{ fieldtype: "HTML", options: diff_html }],
                    primary_action_label: __("Use Pending Status Change"),
                    primary_action: () => {
                        if (branch_differs) frm.set_value('branch', pending.new_branch);
                        if (designation_differs) frm.set_value('designation', pending.new_designation);
                        dialog.hide();
                    },
                    secondary_action_label: __("Use Employee Record"),
                    secondary_action: () => dialog.hide(),
                });
                dialog.show();
            }
        });
    },

    contract_template: function(frm) {
        // Period/Project/Retirement classification now comes from the
        // Template, not Contract Type - Contract Type is deprecated and no
        // longer drives any live behaviour, only kept on existing contracts
        // for historical reference.
        if (frm.doc.contract_template) {
            frappe.model.with_doc('Contract of Employment Template', frm.doc.contract_template, function() {
                let template_doc = frappe.get_doc('Contract of Employment Template', frm.doc.contract_template);

                frm.set_value('has_expiry', template_doc.has_expiry || 0);
                frm.set_value('has_project', template_doc.has_project || 0);
                frm.set_value('has_retirement', template_doc.has_retirement || 0);
                frm.set_value('retirement_age', template_doc.retirement_age || '');

                if (template_doc.has_expiry) {
                    frm.set_df_property('end_date', 'reqd', 1);
                    frm.set_df_property('project', 'reqd', 1);
                } else {
                    frm.set_df_property('end_date', 'reqd', 0);
                    frm.set_df_property('project', 'reqd', 0);
                }

                if (template_doc.has_project) {
                    frm.set_df_property('project', 'reqd', 1);
                } else {
                    frm.set_df_property('project', 'reqd', 0);
                }

                frm.events.toggle_end_date_field(frm);
            });
        }
    },

    has_retirement: function(frm) {
        frm.events.toggle_retirement_fields(frm);
    },

    has_expiry: function(frm) {
        frm.events.toggle_expiry_field(frm);
        frm.events.toggle_end_date_field(frm);
    },

    has_project: function(frm) {
        frm.events.toggle_project_fields(frm);
        frm.events.toggle_end_date_field(frm);
    },

    toggle_retirement_fields: function(frm) {
        let should_display = frm.doc.has_retirement ? 1 : 0;
        frm.toggle_display('retirement_age', should_display);
    },

    toggle_expiry_field: function(frm) {
        let should_display = frm.doc.has_expiry ? 1 : 0;
    },

    toggle_project_fields: function(frm) {
        let should_display = frm.doc.has_project ? 1 : 0;
        frm.toggle_display('project', should_display);
    },

    toggle_end_date_field: function(frm) {
        let should_display = frm.doc.has_expiry || frm.doc.has_project;
        frm.toggle_display('end_date', should_display);
    },
});

// ---- Earnings / Deductions HTML table editors ----
// Modelled directly on status_change_form.js's status_change_details
// editor: a plain HTML table bound to the child table, Link cells filtered
// to the right Salary Component type, read-only once docstatus != 0. Reuses
// ir_ui.css's existing .scd-table styling - it's generic table chrome, not
// specific to Status Change Form.

function render_earnings_editor(frm) {
    render_component_table_editor(frm, {
        fieldname: 'earnings',
        html_fieldname: 'earnings_html',
        child_doctype: 'Contract of Employment Earning',
        component_type: 'Earning',
        has_amount: true,
        add_label: __('+ Add Earning'),
    });
}

function render_deductions_editor(frm) {
    // No Amount: Deductions only ever records which Salary Components
    // apply (for conditions/reference) - it never had per-contract amounts
    // historically either.
    render_component_table_editor(frm, {
        fieldname: 'deductions',
        html_fieldname: 'deductions_html',
        child_doctype: 'Contract of Employment Deduction',
        component_type: 'Deduction',
        has_amount: false,
        add_label: __('+ Add Deduction'),
    });
}

function render_component_table_editor(frm, opts) {
    if (!frm.fields_dict[opts.html_fieldname]) return;

    const $wrapper = frm.get_field(opts.html_fieldname).$wrapper;
    const rows = frm.doc[opts.fieldname] || [];
    const read_only = frm.doc.docstatus !== 0;

    const column_count = opts.has_amount ? 3 : 2;
    $wrapper.html(`
        <table class="table table-sm scd-table">
            <thead>
                <tr>
                    <th style="width: ${opts.has_amount ? '60%' : '90%'};">${__("Salary Component")}</th>
                    ${opts.has_amount ? `<th style="width: 30%;">${__("Amount")}</th>` : ""}
                    <th style="width: 10%;"></th>
                </tr>
            </thead>
            <tbody>
                ${
                    rows.length
                        ? rows.map((row) => `<tr data-row="${row.name}"></tr>`).join("")
                        : `<tr><td colspan="${column_count}" class="text-muted">${__("No rows yet.")}</td></tr>`
                }
            </tbody>
        </table>
        ${read_only ? "" : `<button type="button" class="btn btn-xs btn-default coe-add-row">${opts.add_label}</button>`}
    `);

    rows.forEach((row) => render_component_table_row(frm, $wrapper, row, read_only, opts));
    bind_component_table_editor_events(frm, $wrapper, read_only, opts);
}

function render_component_table_row(frm, $wrapper, row, read_only, opts) {
    const $tr = $wrapper.find(`tr[data-row="${row.name}"]`);

    const $component_cell = $("<td></td>").appendTo($tr);
    make_component_table_control(frm, $component_cell, row, read_only, opts, {
        fieldname: "salary_component",
        fieldtype: "Link",
        options: "Salary Component",
        get_query: () => ({ filters: { type: opts.component_type, disabled: 0 } }),
    });

    if (opts.has_amount) {
        const $amount_cell = $("<td></td>").appendTo($tr);
        make_component_table_control(frm, $amount_cell, row, read_only, opts, {
            fieldname: "amount",
            fieldtype: "Currency",
        });
    }

    if (!read_only) {
        $("<td></td>")
            .html(`<button type="button" class="btn btn-xs btn-danger coe-remove-row" title="${__("Remove")}">×</button>`)
            .appendTo($tr);
    } else {
        $("<td></td>").appendTo($tr);
    }
}

function make_component_table_control(frm, $cell, row, read_only, opts, df) {
    if (read_only) {
        $cell.text(row[df.fieldname] != null && row[df.fieldname] !== "" ? row[df.fieldname] : "");
        return;
    }

    const control = frappe.ui.form.make_control({
        df: Object.assign({ label: "" }, df),
        parent: $cell,
        render_input: true,
    });
    control.$input.val(row[df.fieldname] != null ? row[df.fieldname] : "");
    control.df.onchange = function () {
        const value = this.get_value();
        frappe.model.set_value(row.doctype, row.name, df.fieldname, value).then(() => {
            frm.dirty();
        });
    };
    control.$wrapper.find(".control-label").remove();
}

function bind_component_table_editor_events(frm, $wrapper, read_only, opts) {
    $wrapper.off();
    if (read_only) return;

    $wrapper.on("click", ".coe-add-row", () => {
        frm.add_child(opts.fieldname, {});
        frm.dirty();
        frm.refresh_field(opts.fieldname);
        render_component_table_editor(frm, opts);
    });

    $wrapper.on("click", ".coe-remove-row", (e) => {
        const row_name = $(e.currentTarget).closest("tr").data("row");
        frappe.model.clear_doc(opts.child_doctype, row_name);
        frm.dirty();
        frm.refresh_field(opts.fieldname);
        render_component_table_editor(frm, opts);
    });
}
