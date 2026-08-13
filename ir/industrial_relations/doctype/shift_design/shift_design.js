// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SHIFT_DESIGN_PY = "ir.industrial_relations.page.ir_shift_design.ir_shift_design";

frappe.ui.form.on("Shift Design", {
  onload(frm) {
    set_defaults(frm);
  },

  refresh(frm) {
    add_buttons(frm);
  },

  effective_from(frm) {
    if (!frm.doc.anchor_date && frm.doc.effective_from) {
      frm.set_value("anchor_date", frm.doc.effective_from);
    }
  },

  status(frm) {
    if (["Superseded", "Archived"].includes(frm.doc.status)) {
      frm.set_value("enabled", 0);
    }
  },
});

function set_defaults(frm) {
  if (!frm.doc.status) frm.set_value("status", "Draft");
  if (!frm.doc.number_of_teams) frm.set_value("number_of_teams", 1);
  if (!frm.doc.cycle_length) frm.set_value("cycle_length", 1);
  if (!frm.doc.pay_period_start_day) frm.set_value("pay_period_start_day", 1);
  if (!frm.doc.pay_period_end_day) frm.set_value("pay_period_end_day", 31);
  if (!frm.doc.ordinary_hours_limit) frm.set_value("ordinary_hours_limit", 195);
}

function add_buttons(frm) {
  frm.add_custom_button(
    __("Open Shift Pattern Modeller"),
    () => frappe.set_route("ir-shift-design", frm.doc.name),
    __("Shift Design"),
  );

  frm.add_custom_button(
    __("Generate Team Rows"),
    () => generate_team_rows(frm),
    __("Setup"),
  );

  frm.add_custom_button(
    __("Export Excel"),
    () => export_excel(frm),
    __("Shift Design"),
  );
}

function export_excel(frm) {
  if (frm.is_new()) {
    frappe.msgprint(__("Save the Shift Design before exporting."));
    return;
  }
  if (frm.is_dirty()) {
    frappe.msgprint(__("Save the Shift Design so the export includes the latest changes."));
    return;
  }
  const url =
    `/api/method/${SHIFT_DESIGN_PY}.export_shift_design_excel` +
    `?name=${encodeURIComponent(frm.doc.name)}`;
  window.open(url, "_blank");
}

function generate_team_rows(frm) {
  const count = Math.max(cint(frm.doc.number_of_teams), 1);
  const rows = frm.doc.teams || [];

  while (rows.length > count) {
    rows.pop();
  }

  while (rows.length < count) {
    const index = rows.length;
    const row = frm.add_child("teams");
    row.team_name = `Shift ${alpha_label(index)}`;
    row.display_order = index + 1;
    row.pattern_offset = 0;
    row.enabled = 1;
  }

  frm.refresh_field("teams");
  frm.dirty();
}

function alpha_label(index) {
  let value = index + 1;
  let label = "";

  while (value > 0) {
    value -= 1;
    label = String.fromCharCode(65 + (value % 26)) + label;
    value = Math.floor(value / 26);
  }

  return label;
}
