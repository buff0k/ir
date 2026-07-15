// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SHIFT_DESIGN_API =
  "ir.industrial_relations.doctype.shift_design.shift_design";

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
  if (!frm.doc.sunday_rule) frm.set_value("sunday_rule", "Follow Pattern");
}

function add_buttons(frm) {
  frm.add_custom_button(
    __("Open Shift Pattern Modeller"),
    () => frappe.set_route("ir-shift-design", frm.doc.name),
    __("Shift Design"),
  );

  frm.add_custom_button(
    __("Import Organogram Teams"),
    () => show_import_dialog(frm),
    __("Setup"),
  );

  frm.add_custom_button(
    __("Generate Team Rows"),
    () => generate_team_rows(frm),
    __("Setup"),
  );
}

function show_import_dialog(frm) {
  const dialog = new frappe.ui.Dialog({
    title: __("Import Organogram Teams"),
    fields: [
      {
        fieldname: "site_organogram",
        fieldtype: "Link",
        label: __("Site Organogram"),
        options: "Site Organogram",
        reqd: 1,
        get_query() {
          return {
            filters: frm.doc.branch ? { branch: frm.doc.branch } : {},
          };
        },
      },
      {
        fieldname: "mode",
        fieldtype: "Select",
        label: __("Mode"),
        options: "Replace\nMerge",
        default: "Replace",
        reqd: 1,
      },
    ],
    primary_action_label: __("Import"),
    primary_action: async (values) => {
      const response = await frappe.call({
        method: `${SHIFT_DESIGN_API}.get_site_organogram_import_data`,
        args: {
          site_organogram: values.site_organogram,
        },
        freeze: true,
        freeze_message: __("Importing Organogram teams..."),
      });

      const data = response.message || {};

      if (values.mode === "Replace") {
        frm.clear_table("teams");
        frm.clear_table("pattern");
      }

      if (!frm.doc.branch && data.branch) {
        await frm.set_value("branch", data.branch);
      }

      const existingNames = new Set(
        (frm.doc.teams || []).map((row) =>
          String(row.team_name || "").trim().toLowerCase(),
        ),
      );

      for (const source of data.teams || []) {
        const normalizedName = String(source.team_name || "")
          .trim()
          .toLowerCase();

        if (!normalizedName || existingNames.has(normalizedName)) {
          continue;
        }

        const row = frm.add_child("teams");
        row.team_key = source.team_key || "";
        row.team_name = source.team_name || "";
        row.display_order = source.display_order || 0;
        row.pattern_offset = source.pattern_offset || 0;
        row.enabled = source.enabled === 0 ? 0 : 1;
        existingNames.add(normalizedName);
      }

      await frm.set_value(
        "number_of_teams",
        (frm.doc.teams || []).filter((row) => cint(row.enabled)).length || 1,
      );

      frm.refresh_field("teams");
      frm.refresh_field("pattern");
      frm.dirty();
      dialog.hide();
    },
  });

  dialog.show();
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
