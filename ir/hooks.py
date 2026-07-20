# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from frappe import _
from . import __version__ as app_version
app_name = "ir"
app_title = "Industrial Relations"
app_publisher = "BuFf0k"
app_description = "Industrial Relations management Application for ERPNext and with HRMS"
app_email = "buff0k@buff0k.co.za"
app_license = "mit"
required_apps = ["frappe/erpnext", "frappe/hrms", "https://github.com/EPIUSECX/cohenix_local_za"]
source_link = "http://github.com/buff0k/ir"
app_home = "/desk/ir-general"
add_to_apps_screen = [
	{
		"name": "ir",
		"logo": "/assets/ir/desktop_icons/ir-logo.png",
		"title": "Industrial Relations",
		"route": "/desk/ir-general",
		"has_permission": "ir.industrial_relations.utils.check_app_permission",
	}
]
app_include_icons = ["/assets/ir/icons/ir-icons.svg"]
app_include_css = ["/assets/ir/css/ir_ui.css"]
fixtures = [
	{"dt": "Role", "filters": [["name", "in", [
		"IR Manager",
        "IR Officer",
		"IR User",
		"Training Manager",
		"Training Administrator",
		"Training Faciliator",
		"Anonymous Report Investigator"
	]]]},
    {"dt": "Client Script", "filters": [["dt", "=", "Employee"]]},
	{"dt": "Custom DocPerm", "filters": [["role", "in", [
		"IR Manager",
        "IR Officer",
		"IR User",
		"Training Administrator",
		"Training Facilitator",
		"Training Manager",
		"Anonymous Report Investigator"
	]]]},
	{"dt": "Report", "filters": [["name", "in", ["Disciplinary Offence Report"]]]},
	{"dt": "Contract Section", "filters": [["sec_head", "in", [
		"Working Hours Placeholder",
		"Remuneration Placeholder",
		"Employment (Fixed Term Period)",
		"Employment (Fixed Term Project)",
		"Employment (Indefinite)",
		"Position",
		"Commencement and Nature of Contract (Fixed Term Period)",
		"Commencement and Nature of Contract (Fixd Term Period)",
		"Commencement and Nature of Contract (Indefinite)",
		"Deductions (Fixed Term Period)",
		"Deductions (Fixed Term Project)",
		"Deductions (Indefinite)", "Leave",
		"Duties", "Industrial Action",
		"Termination of Employment (Fixed Term Period)",
		"Termination of Employment (Fixed Term Project)",
		"Termination of Employment (Indefinite)",
		"Other Benefits", "Rules and Regulations",
		"Safety and Security",
		"Confidentiality of Company and/or Client Information",
		"Protection of Personal Information in terms of the Protection of Personal Information Act, 2013 (POPIA)",
		"General"
	]]]},
	{"dt": "Contract Type", "filters": [["name", "in", [
		"2.1 Rev.24 - Period Based Fixed Term",
		"2.2 Rev.24 - Project Based Fixed Term",
		"2.3 Rev.24 - Indefinite"
	]]]},
	{"dt": "Employee Rights", "filters": [["name", "in", [
		"Demotion",
		"Disciplinary Hearing",
		"Dismissal",
		"Incapacity",
		"Pay Deduction",
		"Pay Reduction",
		"Suspension",
		"Warning Form",
        "Poor Performance",
        "Performance Improved"
	]]]},
	{"dt": "Grounds for Appeal", "filters": [["name", "in", [
		"Procedural",
		"Substantive",
		"New Evidence"
	]]]},
	{"dt": "External Dispute Resolution Outcome", "filters": [["name", "in", [
		"Settled",
		"Monetary Award",
		"Re-instatement",
		"Retrospective Re-instatement",
		"Matter Dismissed"
	]]]},
	{"dt": "External Dispute Resolution Process", "filters": [["name", "in", [
		"Con/Arb",
		"In-Limine",
		"Arbitration",
		"Conciliation"
	]]]},
	{"dt": "Dispute Resolution Forum", "filters": [["name", "in", [
		"CCMA",
		"Labour Court",
		"Labour Appeal Court",
		"Constitutional Court"
	]]]},
	{"dt": "Custom Field", "filters": [["name", "in", [
        "Designation-ir_occupational_level",
		"Employee Checkin-custom_site",
		"Leave Application-ir_total_leave_hours",
        "Leave Application-ir_attach_signed_leave_form",
        "Leave Application-ir_working_days_leave",
        "Leave Application-ir_leave_as_per_payroll",
		"Employee-custom_ir_section",
        "Employee-custom_employee_audit_trail",
		"Employee-custom_ir_column_break",
		"Employee-custom_trade_union",
		"Employee-custom_trade_union_membership_start",
		"Employee-ir_employee_audit",
        "Employee-ir_section_break_records",
        "Employee-ir_employee_records",
        "Job Requisition-ir_employment_type",
        "Job Requisition-ir_site",
        "Job Requisition-ir_advertisement_type",
        "Job Requisition-ir_urgency",
        "Job Requisition-ir_vacancy_type",
        "Job Requisition-ir_enddate",
        "Job Requisition-ir_qualifications__skills_required",
        "Job Requisition-ir_experience_required",
        "Job Requisition-ir_main_duties_and_responsibilities",
        "Job Requisition-ir_acceptable_disabilities",
        "Job Requisition-ir_remarks"
	]]]},
	{"dt": "Property Setter", "filters": [["name", "in", [
        "Designation-ir_occupational_level",
		"Employee Checkin-custom_site",
		"Leave Application-ir_total_leave_hours",
        "Leave Application-ir_attach_signed_leave_form",
    	"Leave Application-ir_working_days_leave",
        "Leave Application-ir_leave_as_per_payroll",
		"Employee-custom_ir_section",
        "Employee-custom_employee_audit_trail",
		"Employee-custom_ir_column_break",
		"Employee-custom_trade_union",
		"Employee-custom_trade_union_membership_start",
		"Employee-ir_employee_audit",
        "Employee-ir_section_break_records",
        "Employee-ir_employee_records",
        "Job Requisition-ir_employment_type",
        "Job Requisition-ir_site",
        "Job Requisition-ir_advertisement_type",
        "Job Requisition-ir_urgency",
        "Job Requisition-ir_vacancy_type",
        "Job Requisition-ir_enddate",
        "Job Requisition-ir_qualifications__skills_required",
        "Job Requisition-ir_experience_required",
        "Job Requisition-ir_main_duties_and_responsibilities",
        "Job Requisition-ir_acceptable_disabilities",
        "Job Requisition-ir_remarks"
	]]]},
	{"dt": "Type of Incapacity", "filters": [["name", "in", [
		"General Incapacity",
		"Medical Incapacity",
		"Incompatibility"
	]]]},
    {"dt": "Reason for Termination", "filters": [["name", "in", [
		"Employee Deceased",
		"Transfer of Employment",
		"End of Fixed-Term Contract",
		"Retirement",
		"Dismissal for Operational Requirements (Retrenchment)",
        "Dismissal for Poor Performance",
        "Dismissal for Incapacity",
        "Asbcondment / Desertion",
        "Dismissal for Misconduct",
        "Resignation"
	]]]},
    {"dt": "Offence Outcome", "filters": [["name", "in", [
		"NGG",
		"PI",
		"CAN",
		"NG",
		"VSP",
        "USUS",
        "TRANS",
        "TDM",
        "PSUS",
        "PDUC",
        "IDM",
        "FWW",
        "DIS",
        "2WW",
        "1WW",
        "FIT",
        "PRED"
	]]]}
]
scheduler_events = {
	"weekly": [
    	"ir.controllers.fixed_term_expiry.fixed_term_expiry",
		"ir.controllers.fixed_term_expiry_lapsed.fixed_term_expiry_lapsed",
		"ir.controllers.outstanding_disciplinaries.outstanding_disciplinaries",
		"ir.controllers.outstanding_incapacities.outstanding_incapacities",
		"ir.controllers.outstanding_external_disputes.outstanding_external_disputes",
		"ir.controllers.retirement_age.retirement_age",
		"ir.controllers.retirement_age_lapsed.retirement_age_lapsed",
		"ir.controllers.outstanding_poor_performance.outstanding_poor_performance",
		"ir.controllers.notifications.send_weekly_induction_expiring_soon_notifications",
		"ir.controllers.notifications.send_weekly_induction_expired_notifications",
        "ir.controllers.notifications.send_weekly_outstanding_leave_application_notifications",
		"ir.controllers.notifications.send_weekly_outstanding_employee_change_form_notifications",
	],
	"daily": [
		"ir.controllers.attendance_sync.enqueue_daily_sync",
		"ir.controllers.employee_termination_sync.run_daily"
	]
}
after_migrate = [
	"ir.setup.add_employee_doclinks.ensure_employee_links"
]
doc_events = {
	"Termination Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
	"NTA Enquiry": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
		"validate": "ir.permissions.validate_nta_enquiry",
	},
	"Status Change Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
	"Site Transfer Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
    "Employee Checkin": {
		"after_insert": "ir.controllers.attendance_sync.on_employee_checkin",
	},
	"Leave Application": {
        "before_submit": "ir.overrides.leave_application.validate_signed_leave_form_attached",
		"on_submit": "ir.controllers.attendance_sync.on_leave_application_change",
		"on_cancel": "ir.controllers.attendance_sync.on_leave_application_change",
		"on_update_after_submit": "ir.controllers.attendance_sync.on_leave_application_change",
	},
	"Contract of Employment": {
        "validate": "ir.permissions.validate_contract_of_employment",
    },
	"Disciplinary Action": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
        "validate": "ir.permissions.validate_disciplinary_action",
    },
	"Anonymous Report": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
    "Incapacity Proceedings": {
        "validate": "ir.permissions.validate_incapacity_proceedings",
    },
    "Poor Performance": {
        "validate": "ir.permissions.validate_poor_performance",
    },
    "Written Outcome": {
        "validate": "ir.permissions.validate_written_outcome",
    },
}
permission_query_conditions = {
    "Contract of Employment": "ir.permissions.contract_of_employment_permission_query_conditions",
    "Disciplinary Action": "ir.permissions.disciplinary_action_permission_query_conditions",
    "Incapacity Proceedings": "ir.permissions.incapacity_proceedings_permission_query_conditions",
    "Poor Performance": "ir.permissions.poor_performance_permission_query_conditions",
    "NTA Enquiry": "ir.permissions.nta_enquiry_permission_query_conditions",
    "Written Outcome": "ir.permissions.written_outcome_permission_query_conditions",
}
has_permission = {
    "Contract of Employment": "ir.permissions.contract_of_employment_has_permission",
    "Disciplinary Action": "ir.permissions.disciplinary_action_has_permission",
    "Incapacity Proceedings": "ir.permissions.incapacity_proceedings_has_permission",
    "Poor Performance": "ir.permissions.poor_performance_has_permission",
    "NTA Enquiry": "ir.permissions.nta_enquiry_has_permission",
    "Written Outcome": "ir.permissions.written_outcome_has_permission",
}