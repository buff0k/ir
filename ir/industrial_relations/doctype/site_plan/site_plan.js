// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SITE_PLAN_PY = "ir.industrial_relations.doctype.site_plan.site_plan";

frappe.ui.form.on("Site Plan", {
  onload(frm) {
    if (!frm.doc.status) frm.set_value("status", "Draft");
    if (frm.doc.enabled === undefined) frm.set_value("enabled", 1);
  },

  refresh(frm) {
    frm.add_custom_button(
      __("Open Site Plan Designer"),
      () => frappe.set_route("ir-site-plan-design", frm.doc.name),
      __("Site Plan"),
    );
    add_excel_export_button(frm);
  },

  status(frm) {
    if (["Superseded", "Archived"].includes(frm.doc.status)) {
      frm.set_value("enabled", 0);
    }
  },
});

function add_excel_export_button(frm) {
  frm.add_custom_button(
    __("Export Excel"),
    () => {
      if (frm.is_new()) {
        frappe.msgprint(__("Save the Site Plan before exporting."));
        return;
      }
      if (frm.is_dirty()) {
        frappe.msgprint(__("Save the Site Plan so the export includes the latest changes."));
        return;
      }
      const url =
        `/api/method/${SITE_PLAN_PY}.export_site_plan_excel` +
        `?name=${encodeURIComponent(frm.doc.name)}`;
      window.open(url, "_blank");
    },
    __("Actions"),
  );
}
