// Copyright (c) 2024, BuFf0k and contributors
// For license information, please see license.txt

frappe.ui.form.on('Contract of Employment', {
    refresh: function(frm) {
        frm.events.toggle_allowance_sections(frm);
        frm.events.toggle_working_hours_section(frm);
        frm.events.toggle_retirement_fields(frm);
        frm.events.toggle_expiry_field(frm);
        frm.events.toggle_project_fields(frm);

        // Always display values if they exist
        frm.toggle_display('end_date', frm.doc.has_expiry);
        frm.toggle_display('project', frm.doc.has_project);
        frm.toggle_display('end_date', frm.doc.has_project);
        frm.toggle_display('retirement_age', frm.doc.has_retirement);
        frm.toggle_display('monday_section', frm.doc.has_hours);
        
        // Check if allowance descriptions exist and toggle accordingly
        frm.events.toggle_allowance_sections(frm);
    },

    employee: function(frm) {
        if (frm.doc.employee) {
            frappe.db.get_doc('Employee', frm.doc.employee).then(doc => {
                frm.set_value('employee_name', doc.employee_name || '');
                frm.set_value('date_of_birth', doc.date_of_birth || '');
                frm.set_value('date_of_joining', doc.date_of_joining || '');
                frm.set_value('company', doc.company || '');
                frm.set_value('designation', doc.designation || '');
                frm.set_value('custom_id_number', doc.custom_id_number || '');
                frm.set_value('branch', doc.branch || '');
            
                // Combine the current address lines into a single line
                const addressLines = (doc.current_address || '').split('\n').map(line => line.trim());
                const combinedAddress = addressLines.join(', '); // Use a comma and space as a separator
                frm.set_value('current_address', combinedAddress);

                // Fetch default letter head
                if (doc.company) {
                    frappe.db.get_value('Company', doc.company, 'default_letter_head', (r) => {
                        frm.set_value('letter_head', r.default_letter_head || '');
                    });
                }
            });
        }
    },

    contract_type: function(frm) {
        if (frm.doc.contract_type) {
            frappe.model.with_doc('Contract Type', frm.doc.contract_type, function() {
                let contract_type_doc = frappe.get_doc('Contract Type', frm.doc.contract_type);

                // Update fields in Contract of Employment
                frm.set_value('has_expiry', contract_type_doc.has_expiry || 0);
                frm.set_value('has_project', contract_type_doc.has_project || 0);
                frm.set_value('has_retirement', contract_type_doc.has_retirement || 0);
                frm.set_value('retirement_age', contract_type_doc.retirement_age || '');

                // Handle has_retirement logic
                if (contract_type_doc.has_retirement) {
                    let retirement_age = contract_type_doc.retirement_age;
                    let notification_date = frappe.datetime.add_months(frappe.datetime.add_years(frm.doc.date_of_birth, retirement_age), -1);
                    // Add notification logic here if needed
                }

                // Handle has_expiry logic
                if (contract_type_doc.has_expiry) {
                    frm.set_df_property('end_date', 'reqd', 1);
                    frm.set_df_property('project', 'reqd', 1);
                } else {
                    frm.set_df_property('end_date', 'reqd', 0);
                    frm.set_df_property('project', 'reqd', 0);
                }
            
                // Handle has_project logic
                if (contract_type_doc.has_project) {
                    frm.set_df_property('project', 'reqd', 1);
                } else {
                    frm.set_df_property('project', 'reqd', 0);
                }
            });
        }
    },

    working_hours: function(frm) {
        if (frm.doc.working_hours) {
            frappe.db.get_doc('Contract Section', frm.doc.working_hours).then(doc => {
                frm.set_value('has_hours', doc.has_hours || 0);
            });
        }
    },

    remuneration: function(frm) {
        if (frm.doc.remuneration) {
            frappe.db.get_doc('Contract Section', frm.doc.remuneration).then(doc => {
                frm.set_value('has_allowances', doc.has_allowances || 0);
                
                // Initialize fields to empty strings
                const allowances = {
                    allowance_1_desc: "",
                    allowance_2_desc: "",
                    allowance_3_desc: "",
                    allowance_4_desc: "",
                    allowance_5_desc: ""
                };
                
                // Iterate over the child table rows
                doc.sec_par.forEach(row => {
                    if (row.clause_text) {
                        if (row.clause_text.includes("{allowance_1}")) {
                            allowances.allowance_1_desc = row.clause_text;
                        } else if (row.clause_text.includes("{allowance_2}")) {
                            allowances.allowance_2_desc = row.clause_text;
                        } else if (row.clause_text.includes("{allowance_3}")) {
                            allowances.allowance_3_desc = row.clause_text;
                        } else if (row.clause_text.includes("{allowance_4}")) {
                            allowances.allowance_4_desc = row.clause_text;
                        } else if (row.clause_text.includes("{allowance_5}")) {
                            allowances.allowance_5_desc = row.clause_text;
                        }
                    }
                });
                
                // Set the allowance description fields
                frm.set_value('allowance_1_desc', allowances.allowance_1_desc);
                frm.set_value('allowance_2_desc', allowances.allowance_2_desc);
                frm.set_value('allowance_3_desc', allowances.allowance_3_desc);
                frm.set_value('allowance_4_desc', allowances.allowance_4_desc);
                frm.set_value('allowance_5_desc', allowances.allowance_5_desc);

                // Call the function to toggle allowance sections
                frm.events.toggle_allowance_sections(frm);
            });
        }
    },

    has_hours: function(frm) {
        frm.events.toggle_working_hours_section(frm);
    },

    has_retirement: function(frm) {
        frm.events.toggle_retirement_fields(frm);
    },

    has_expiry: function(frm) {
        frm.events.toggle_expiry_field(frm);
    },

    has_project: function(frm) {
        frm.events.toggle_project_fields(frm);
    },

    toggle_working_hours_section: function(frm) {
        let should_display = frm.doc.has_hours ? 1 : 0;
        frm.toggle_display('monday_section', should_display);
    },

    toggle_retirement_fields: function(frm) {
        let should_display = frm.doc.has_retirement ? 1 : 0;
        frm.toggle_display('retirement_age', should_display);
    },

    toggle_expiry_field: function(frm) {
        let should_display = frm.doc.has_expiry ? 1 : 0;
        frm.toggle_display('end_date', should_display);
    },

    toggle_project_fields: function(frm) {
        let should_display = frm.doc.has_project ? 1 : 0;
        frm.toggle_display('project', should_display);
        frm.toggle_display('end_date', should_display);
    },

    // New function to toggle allowance sections based on description fields
    toggle_allowance_sections: function(frm) {
        frm.toggle_display('allowance1', frm.doc.allowance_1_desc ? 1 : 0);
        frm.toggle_display('allowance_1_desc', frm.doc.allowance_1_desc ? 1 : 0);
        frm.toggle_display('allowance_1_rate', frm.doc.allowance_1_desc ? 1 : 0);
        frm.toggle_display('allowance2', frm.doc.allowance_2_desc ? 1 : 0);
        frm.toggle_display('allowance_2_desc', frm.doc.allowance_2_desc ? 1 : 0);
        frm.toggle_display('allowance_2_rate', frm.doc.allowance_2_desc ? 1 : 0);
        frm.toggle_display('allowance3', frm.doc.allowance_3_desc ? 1 : 0);
        frm.toggle_display('allowance_3_desc', frm.doc.allowance_3_desc ? 1 : 0);
        frm.toggle_display('allowance_3_rate', frm.doc.allowance_3_desc ? 1 : 0);
        frm.toggle_display('allowance4', frm.doc.allowance_4_desc ? 1 : 0);
        frm.toggle_display('allowance_4_desc', frm.doc.allowance_4_desc ? 1 : 0);
        frm.toggle_display('allowance_4_rate', frm.doc.allowance_4_desc ? 1 : 0);
        frm.toggle_display('allowance5', frm.doc.allowance_5_desc ? 1 : 0);
        frm.toggle_display('allowance_5_desc', frm.doc.allowance_5_desc ? 1 : 0);
        frm.toggle_display('allowance_5_rate', frm.doc.allowance_5_desc ? 1 : 0);
    }
});
