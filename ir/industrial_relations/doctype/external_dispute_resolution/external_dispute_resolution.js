// Copyright (c) 2025, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on("External Dispute Resolution", {
    employee: function (frm) {
        let employees = (frm.doc.employee || []).map(e => e.employee);  // Extract employee IDs
        let existing_applicants = (frm.doc.applicant_history || []).map(a => a.applicant);

        // Remove rows for employees no longer selected
        frm.doc.applicant_history = frm.doc.applicant_history.filter(a => employees.includes(a.applicant));

        // Add missing employees
        employees.forEach(emp => {
            if (!existing_applicants.includes(emp)) {
                let row = frm.add_child("applicant_history");
                row.applicant = emp;
            }
        });

        frm.refresh_field("applicant_history");
    }
});
