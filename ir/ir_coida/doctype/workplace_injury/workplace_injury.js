frappe.ui.form.on('Workplace Injury', {
	refresh: function(frm) {
		frappe.call({
			method: 'ir.industrial_relations.utils.is_hrms_installed',
			callback: function(r) {
				if (!r.message) {
					frm.set_df_property('requires_leave', 'hidden', 1);
					frm.set_df_property('leave_days', 'hidden', 1);
					frm.set_df_property('leave_application', 'hidden', 1);

					if (frm.doc.requires_leave) {
						frm.set_value('requires_leave', 0);
					}
				}
			}
		});
	}
});

