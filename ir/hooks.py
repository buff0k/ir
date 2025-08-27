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
		"IR User"
	]]]},
    {"dt": "Client Script", "filters": [["dt", "=", "Employee"]]},
	{"dt": "Custom DocPerm", "filters": [["role", "in", [
		"IR Manager",
        "IR Officer",
		"IR User"
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
	{"dt": "Module Profile", "filters": [["name", "in", ["Industrial Relations"]]]},
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
    	"Designation"
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
	}
}
# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ir/css/ir.css"
# app_include_js = "/assets/ir/js/ir.js"

# include js, css files in header of web template
# web_include_css = "/assets/ir/css/ir.css"
# web_include_js = "/assets/ir/js/ir.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ir/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ir/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ir.utils.jinja_methods",
# 	"filters": "ir.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ir.install.before_install"
# after_install = "ir.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ir.uninstall.before_uninstall"
# after_uninstall = "ir.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ir.utils.before_app_install"
# after_app_install = "ir.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ir.utils.before_app_uninstall"
# after_app_uninstall = "ir.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ir.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Testing
# -------

# before_tests = "ir.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ir.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ir.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ir.utils.before_request"]
# after_request = ["ir.utils.after_request"]

# Job Events
# ----------
# before_job = ["ir.utils.before_job"]
# after_job = ["ir.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ir.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

