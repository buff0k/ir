// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const SITE_ORGANOGRAM_PY =
  "ir.industrial_relations.doctype.site_organogram.site_organogram";

frappe.ui.form.on("Site Organogram", {
  refresh(frm) {
    add_organogram_designer_button(frm);
    add_excel_export_button(frm);
  },
});

function add_organogram_designer_button(frm) {
  frm.add_custom_button(
    __("Open Organogram Designer"),
    () => {
      const route = ["ir-organogram-design"];

      if (!frm.is_new()) {
        route.push(frm.doc.name);
      }

      frappe.set_route(...route);
    },
    __("Actions")
  );
}

function add_excel_export_button(frm) {
  frm.add_custom_button(
    __("Export Excel"),
    () => {
      if (frm.is_new()) {
        frappe.msgprint(__("Save the Site Organogram before exporting."));
        return;
      }

      if (frm.is_dirty()) {
        frappe.msgprint(
          __("Save the Site Organogram so the export includes the latest changes.")
        );
        return;
      }

      const url =
        `/api/method/${SITE_ORGANOGRAM_PY}.export_site_organogram_excel` +
        `?name=${encodeURIComponent(frm.doc.name)}`;

      window.open(url, "_blank");
    },
    __("Actions")
  );
}
