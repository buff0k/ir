// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

const STATUS_CHANGE_DETAIL_CHANGE_TYPES = ["Designation", "Branch", "Conditions of Employment", "Salary Component"];
const STATUS_CHANGE_DETAIL_CONDITION_OPTIONS = ["", "Fixed Term", "Project", "Indefinite"];

frappe.ui.form.on("Status Change Form", {
  async requested_by(frm) {
    await frm.events.pull_requested_by_details(frm);
  },

  async employee(frm) {
    await frm.events.pull_employee_details(frm);
  },

  refresh(frm) {
    refresh_employee_fields_cache_and_render(frm);
  },

  after_save(frm) {
    refresh_employee_fields_cache_and_render(frm);
  },

  before_submit(frm) {
    if (!frm.doc.attach) {
      frappe.throw(__("You must attach the signed status change form before submitting."));
    }
  },

  async pull_requested_by_details(frm) {
    if (!frm.doc.requested_by) {
      frm.set_value("requested_by_name", "");
      frm.set_value("requested_by_designation", "");
      return;
    }

    const r = await frappe.db.get_value("Employee", frm.doc.requested_by, [
      "employee_name",
      "designation",
    ]);

    const v = (r && r.message) || {};
    await frm.set_value("requested_by_name", v.employee_name || "");
    await frm.set_value("requested_by_designation", v.designation || "");
  },

  async pull_employee_details(frm) {
    if (!frm.doc.employee) {
      frm.set_value("employee_name", "");
      frm.__scd_employee_fields = {};
      frm.__scd_employee_fields_for = frm.doc.employee;
      render_status_change_details_editor(frm);
      return;
    }

    const r = await frappe.db.get_value("Employee", frm.doc.employee, [
      "employee_name",
      "designation",
      "branch",
    ]);

    const v = (r && r.message) || {};
    await frm.set_value("employee_name", v.employee_name || "");
    frm.__scd_employee_fields = { designation: v.designation, branch: v.branch };
    frm.__scd_employee_fields_for = frm.doc.employee;
    render_status_change_details_editor(frm);
  },
});

function refresh_employee_fields_cache_and_render(frm) {
  if (frm.__scd_employee_fields_for === frm.doc.employee) {
    render_status_change_details_editor(frm);
    return;
  }
  if (!frm.doc.employee) {
    frm.__scd_employee_fields = {};
    frm.__scd_employee_fields_for = frm.doc.employee;
    render_status_change_details_editor(frm);
    return;
  }
  frappe.db.get_value("Employee", frm.doc.employee, ["designation", "branch"]).then((r) => {
    frm.__scd_employee_fields = (r && r.message) || {};
    frm.__scd_employee_fields_for = frm.doc.employee;
    render_status_change_details_editor(frm);
  });
}

function get_status_change_detail_clear_values(change_type) {
  const is_link_row = change_type === "Branch" || change_type === "Designation";
  const is_condition_row = change_type === "Conditions of Employment";
  const is_salary_row = change_type === "Salary Component";

  const clears = {};
  if (!is_link_row) {
    clears.old_value = "";
    clears.new_value = "";
  }
  if (!is_condition_row) {
    clears.old_condition = "";
    clears.new_condition = "";
  }
  if (!is_salary_row) {
    clears.salary_component = "";
    clears.old_amount = 0;
    clears.new_amount = 0;
  }
  return clears;
}

frappe.ui.form.on("Status Change Detail", {
  change_type(frm, cdt, cdn) {
    const row = frappe.get_doc(cdt, cdn);
    const clears = get_status_change_detail_clear_values(row.change_type);
    Object.entries(clears).forEach(([fieldname, value]) => {
      frappe.model.set_value(cdt, cdn, fieldname, value);
    });
  },
});

let _status_change_details_rendering = false;

function render_status_change_details_editor(frm) {
  if (_status_change_details_rendering) return;
  if (!frm.fields_dict.status_change_details_html) return;
  _status_change_details_rendering = true;
  try {
    _render_status_change_details_editor(frm);
  } finally {
    _status_change_details_rendering = false;
  }
}

function _render_status_change_details_editor(frm) {
  const $wrapper = frm.get_field("status_change_details_html").$wrapper;
  const rows = frm.doc.status_change_details || [];
  const read_only = frm.doc.docstatus !== 0;

  $wrapper.html(`
    <table class="table table-sm scd-table">
      <thead>
        <tr>
          <th style="width: 20%;">${__("Change Type")}</th>
          <th style="width: 20%;">${__("Component")}</th>
          <th style="width: 25%;">${__("Old")}</th>
          <th style="width: 25%;">${__("New")}</th>
          <th style="width: 10%;"></th>
        </tr>
      </thead>
      <tbody>
        ${
          rows.length
            ? rows.map((row) => `<tr data-row="${row.name}"></tr>`).join("")
            : `<tr><td colspan="5" class="text-muted">${__("No changes recorded yet.")}</td></tr>`
        }
      </tbody>
    </table>
    ${read_only ? "" : `<button type="button" class="btn btn-xs btn-default scd-add-row">+ ${__("Add Change")}</button>`}
  `);
  rows.forEach((row) => render_status_change_detail_row(frm, $wrapper, row, read_only));
  bind_status_change_details_editor_events(frm, $wrapper, read_only);
}

function render_status_change_detail_row(frm, $wrapper, row, read_only) {
  const $tr = $wrapper.find(`tr[data-row="${row.name}"]`);

  const $type_cell = $("<td></td>").appendTo($tr);
  make_status_change_detail_control(frm, $type_cell, row, read_only, {
    fieldname: "change_type",
    fieldtype: "Select",
    options: STATUS_CHANGE_DETAIL_CHANGE_TYPES.join("\n"),
  });

  const $component_cell = $("<td></td>").appendTo($tr);
  if (row.change_type === "Salary Component") {
    make_status_change_detail_control(frm, $component_cell, row, read_only, {
      fieldname: "salary_component",
      fieldtype: "Link",
      options: "Salary Component",
      get_query: () => ({ filters: { type: "Earning" } }),
    });
  } else {
    $component_cell.html(`<span class="text-muted">—</span>`);
  }

  const $old_cell = $("<td></td>").appendTo($tr);
  const $new_cell = $("<td></td>").appendTo($tr);

  if (row.change_type === "Designation" || row.change_type === "Branch") {
    const live_employee_fields = frm.__scd_employee_fields || {};
    const live_old_value =
      row.change_type === "Designation" ? live_employee_fields.designation : live_employee_fields.branch;
    if (live_old_value && row.old_value !== live_old_value) {
      row.old_value = live_old_value;
      frappe.model.set_value("Status Change Detail", row.name, "old_value", live_old_value);
    }
    $old_cell.text(row.old_value || "");
    make_status_change_detail_control(frm, $new_cell, row, read_only, {
      fieldname: "new_value",
      fieldtype: "Link",
      options: row.change_type,
    });
  } else if (row.change_type === "Conditions of Employment") {
    make_status_change_detail_control(frm, $old_cell, row, read_only, {
      fieldname: "old_condition",
      fieldtype: "Select",
      options: STATUS_CHANGE_DETAIL_CONDITION_OPTIONS.join("\n"),
    });
    make_status_change_detail_control(frm, $new_cell, row, read_only, {
      fieldname: "new_condition",
      fieldtype: "Select",
      options: STATUS_CHANGE_DETAIL_CONDITION_OPTIONS.join("\n"),
    });
  } else if (row.change_type === "Salary Component") {
    make_status_change_detail_control(frm, $old_cell, row, read_only, {
      fieldname: "old_amount",
      fieldtype: "Currency",
    });
    make_status_change_detail_control(frm, $new_cell, row, read_only, {
      fieldname: "new_amount",
      fieldtype: "Currency",
    });
  } else {
    $old_cell.html(`<span class="text-muted">${__("Select a Change Type")}</span>`);
  }

  if (!read_only) {
    $("<td></td>")
      .html(
        `<button type="button" class="btn btn-xs btn-danger scd-remove-row" title="${__("Remove")}">×</button>`
      )
      .appendTo($tr);
  } else {
    $("<td></td>").appendTo($tr);
  }
}

function make_status_change_detail_control(frm, $cell, row, read_only, df) {
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
    frappe.model.set_value("Status Change Detail", row.name, df.fieldname, value).then(() => {
      if (df.fieldname !== "change_type") return;
      const clears = get_status_change_detail_clear_values(value);
      return Promise.all(
        Object.entries(clears).map(([fieldname, clear_value]) =>
          frappe.model.set_value("Status Change Detail", row.name, fieldname, clear_value)
        )
      );
    }).then(() => {
      frm.dirty();
      render_status_change_details_editor(frm);
    });
  };
  control.$wrapper.find(".control-label").remove();
}

function bind_status_change_details_editor_events(frm, $wrapper, read_only) {
  $wrapper.off();
  if (read_only) return;

  $wrapper.on("click", ".scd-add-row", () => {
    frm.add_child("status_change_details", { change_type: "" });
    frm.dirty();
    frm.refresh_field("status_change_details");
    render_status_change_details_editor(frm);
  });

  $wrapper.on("click", ".scd-remove-row", (e) => {
    const row_name = $(e.currentTarget).closest("tr").data("row");
    frappe.model.clear_doc("Status Change Detail", row_name);
    frm.dirty();
    frm.refresh_field("status_change_details");
    render_status_change_details_editor(frm);
  });
}
