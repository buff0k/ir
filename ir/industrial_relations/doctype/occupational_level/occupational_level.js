// Copyright (c) 2026, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Occupational Level', {
  onload_post_render: function(frm) {
    if (frm.is_new()) return;

    frappe.call({
      method: 'ir.industrial_relations.doctype.occupational_level.occupational_level.get_designations_for_occupational_level',
      args: {
        occupational_level: frm.doc.name
      },
      callback: function(r) {
        const rows = r.message || [];

        let html = `
          <div class="frappe-control">
            <div class="table-responsive">
              <table class="table table-bordered table-hover">
                <thead class="table-head">
                  <tr>
                    <th>Linked Designation</th>
                  </tr>
                </thead>
                <tbody>
        `;

        rows.forEach(row => {
          html += `
            <tr>
              <td>
                <a href="/app/designation/${encodeURIComponent(row.designation)}" target="_blank">
                  ${frappe.utils.escape_html(row.designation)}
                </a>
              </td>
            </tr>
          `;
        });

        html += `
                </tbody>
              </table>
            </div>
          </div>
        `;

        frm.fields_dict.designations_html.$wrapper.html(html);
      }
    });
  }
});
