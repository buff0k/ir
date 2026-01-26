from frappe import _
from . import __version__ as app_version
app_name = "ir"
app_title = "Industrial Relations"
app_publisher = "BuFf0k"
app_description = "Industrial Relations management Application for ERPNext and with HRMS"
app_email = "buff0k@buff0k.co.za"
app_license = "mit"
app_version = "1.0.2"
required_apps = ["frappe/hrms"]
source_link = "http://github.com/buff0k/ir"
app_logo_url = "/assets/ir/images/ir-logo.svg"
app_home = "/app/industrial-relations"
add_to_apps_screen = [
	{
		"name": "ir",
		"logo": "/assets/ir/images/ir-logo.svg",
		"title": "Industrial Relations",
		"route": "/app/industrial-relations",
		"has_permission": "ir.industrial_relations.utils.check_app_permission",
	}
]
fixtures = [
	{"dt": "Role", "filters": [["name", "in", [
		"IR Manager",
        "IR Officer",
		"IR User",
		"Training Manager",
		"Training Administrator",
		"Training Faciliator"
	]]]},
    {"dt": "Client Script", "filters": [["dt", "=", "Employee"]]},
	{"dt": "Custom DocPerm", "filters": [["role", "in", [
		"IR Manager",
        "IR Officer",
		"IR User",
		"Training Administrator",
		"Training Facilitator",
		"Training Manager"
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
		"Warning Form"
	]]]},
	{"dt": "Module Profile", "filters": [["name", "in", [
        "Industrial Relations",
        "IR Manager"
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
	{"dt": "Custom Field", "filters": [["dt", "in", [
    	"Employee",
    	"Designation",
		"Employee Checkin",
        "Leave Application"
	]]]},
	{"dt": "Property Setter", "filters": [["doc_type", "in", [
    	"Employee",
        "Designation"
    ]]]},
	{"dt": "Type of Incapacity", "filters": [["name", "in", [
		"General Incapacity",
		"Medical Incapacity",
		"Incompatibility"
	]]]},
	{"dt": "Designated Group", "filters": [["name", "in", [
		"African",
		"Coloured",
		"Indian",
		"White",
		"Unknown"
	]]]},
	{"dt": "Occupational Level", "filters": [["name", "in", [
		"Unskilled",
		"Semi-skilled",
		"Skilled technical",
		"Professionally qualified",
		"Senior management",
        "Top management"
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
	{"dt": "Employment Equity Sectors", "filters": [["name", "in", [
		"Accomodation and Food Service Activities",
		"Administrative and Support Activities",
		"Agriculture, Forestry & Fishing",
		"Arts, Entertainment and Recreation",
		"Construction",
        "Education",
        "Electricity, Gas, Steam and Air Conditioning Supply",
        "Financial and Insurance Activities",
        "Human Health and Social Work Activities",
        "Information and Communication",
		"Manufacturing",
		"Mining and Quarrying",
		"Other Service Activities",
		"Professional, Scientific and Technical Activities",
		"Public Administration and Defence; Compulsory Social Security",
		"Real Estate Activities",
		"Transportation and Storage",
		"Water Supply; Sewerage, Waste Management and Remediation Activities",
		"Wholesale and Retail Trade; Repair of Motor Vehicles and Motorcycles"
	]]]},
	{"dt": "Custom HTML Block", "filters": [["name", "in", [
		"EEA2 Employment Equity Widget"
	]]]}
]
scheduler_events = {
	"weekly": [
    	"ir.controllers.fixed_term_expiry.fixed_term_expiry",
		"ir.controllers.outstanding_disciplinaries.outstanding_disciplinaries",
		"ir.controllers.outstanding_incapacities.outstanding_incapacities",
    	"ir.controllers.outstanding_external_disputes.outstanding_external_disputes",
        "ir.controllers.retirement_age.retirement_age"
	],
	"daily": [
		"ir.controllers.attendance_sync.enqueue_daily_sync",
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
	"NTA Hearing": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_update": "ir.controllers.notifications.handle_doc_event_update",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
    "Employee Checkin": {
		"after_insert": "ir.controllers.attendance_sync.on_employee_checkin",
	},
	"Leave Application": {
		"on_submit": "ir.controllers.attendance_sync.on_leave_application_change",
		"on_cancel": "ir.controllers.attendance_sync.on_leave_application_change",
		"on_update_after_submit": "ir.controllers.attendance_sync.on_leave_application_change",
	}
}