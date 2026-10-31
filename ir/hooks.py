# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from . import __version__ as app_version

app_name = "ir"
app_title = "Industrial Relations"
app_publisher = "BuFf0k"
app_description = "Industrial Relations management Application for ERPNext and with HRMS"
app_email = "buff0k@buff0k.co.za"
app_license = "mit"
required_apps = ["frappe/erpnext", "frappe/hrms"]
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
# Modules absorbed from za_local ship their own doctypes/workspaces but carry
# no separate dock/sidebar entry - their workspaces are linked into the
# "Industrial Relations" sidebar instead, so nav stays unified as more
# modules land here (same pattern frappe.Core uses for its own doctypes).
code_only_modules = {
	"ir_coida": ["Industrial Relations"],
	"ir_labour": ["Industrial Relations"],
	"ir_vat": ["Industrial Relations"],
	"ir_payroll": ["Industrial Relations"],
	"ir_setup": ["Industrial Relations"],
}
app_include_css = ["/assets/ir/css/ir_ui.css"]
app_include_js = ["/assets/ir/js/ir_feedback.js"]
fixtures = [
	{"dt": "Role", "filters": [["name", "in", [
        "IR Officer",
		"IR User",
		"Training Manager",
		"Training Administrator",
		"Training Faciliator",
		"Anonymous Report Investigator"
	]]]},
    {"dt": "Client Script", "filters": [["dt", "in", ["Employee", "Job Requisition"]]]},
	{"dt": "Custom DocPerm", "filters": [["role", "in", [
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
        "Designation-ir_experience_required",
        "Designation-ir_main_duties_and_responsibilities",
        "Designation-ir_acceptable_disabilities",
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
        "Job Requisition-ir_geographic_area",
        "Job Requisition-ir_advertisement_type",
        "Job Requisition-ir_urgency",
        "Job Requisition-ir_vacancy_type",
        "Job Requisition-ir_enddate",
        "Job Requisition-ir_advertisement_closing_date",
        "Job Requisition-ir_submit_cv_to",
        "Job Requisition-ir_qualifications__skills_required",
        "Job Requisition-ir_designation_skills",
        "Job Requisition-ir_experience_required",
        "Job Requisition-ir_main_duties_and_responsibilities",
        "Job Requisition-ir_acceptable_disabilities",
        "Job Requisition-ir_remarks",
		# South African fields absorbed from za_local - names kept exactly
		# as-is (za_... prefix) per the migration's "retain legacy names"
		# decision. Source of truth is now this fixture, not an imperative
		# creation script. Kept in the SAME filter entry as the block above:
		# a second separate {"dt": "Custom Field", ...} entry would overwrite
		# this one's exported file on the next export-fixtures run instead of
		# merging with it.
		"Additional Salary-za_is_company_contribution",
		"Address-za_address_column_break",
		"Address-za_address_line_3",
		"Address-za_address_line_4",
		"Address-za_care_of",
		"Address-za_complex_name",
		"Address-za_country_code",
		"Address-za_postal_address_type",
		"Address-za_postal_service_number",
		"Address-za_south_african_address_section",
		"Address-za_street_no",
		"Address-za_suburb_or_district",
		"Address-za_unit_no",
		"Company-za_additional_configuration_section",
		"Company-za_bargaining_council",
		"Company-za_business_address",
		"Company-za_coida_registration_number",
		"Company-za_paye_reference_number",
		"Company-za_registration_column_break",
		"Company-za_sdl_reference_number",
		"Company-za_sectoral_determination",
		"Company-za_seta",
		"Company-za_south_african_registration_section",
		"Company-za_trading_name",
		"Company-za_uif_reference_number",
		"Company-za_vat_number",
		"Customer-za_company_registration",
		"Customer-za_is_vat_vendor",
		"Employee Separation-za_bcea_settlement_section",
		"Employee Separation-za_leave_payout",
		"Employee Separation-za_notice_period_days",
		"Employee Separation-za_severance_pay",
		"Employee Separation-za_termination_type",
		"Employee-za_additional_column_break",
		"Employee-za_bank_account_holder_name",
		"Employee-za_bank_account_holder_relationship",
		"Employee-za_bank_account_type",
		"Employee-za_business_address_override",
		"Employee-za_ee_column_break",
		"Employee-za_employee_type",
		"Employee-za_employment_equity_section",
		"Employee-za_eti_eligibility_section",
		"Employee-za_eti_minimum_wage_basis",
		"Employee-za_eti_minimum_wage_rate",
		"Employee-za_has_children",
		"Employee-za_has_other_employments",
		"Employee-za_highest_qualification",
		"Employee-za_hours_per_month",
		"Employee-za_id_number",
		"Employee-za_identity_type",
		"Employee-za_income_tax_reference_number",
		"Employee-za_is_connected_person_to_employer",
		"Employee-za_is_disabled",
		"Employee-za_is_domestic_worker",
		"Employee-za_nationality",
		"Employee-za_nature_of_person",
		"Employee-za_not_paid_electronically",
		"Employee-za_number_of_dependants",
		"Employee-za_occupational_level",
		"Employee-za_passport_country_of_issue",
		"Employee-za_payroll_column_break",
		"Employee-za_payroll_payable_bank_account",
		"Employee-za_personal_information_section",
		"Employee-za_postal_address",
		"Employee-za_race",
		"Employee-za_residential_address",
		"Employee-za_south_african_details_section",
		"Employee-za_special_economic_zone",
		"Employee-za_tax_certificate_bank_section",
		"Employee-za_tax_certificate_column_break",
		"Employee-za_tax_certificate_section",
		"Employee-za_working_hours_per_week",
		"Expense Claim-business_trip",
		"HR Settings-za_amount_per_kilometer",
		"Item Group-is_capital_goods",
		"Journal Entry Account-za_is_company_contribution",
		"Journal Entry Account-za_is_payroll_entry",
		"Leave Type-za_applicable_gender",
		"Leave Type-za_bcea_compliant",
		"Leave Type-za_bcea_section",
		"Leave Type-za_medical_certificate_required_after",
		"Payroll Employee Detail-za_is_bank_entry_created",
		"Payroll Employee Detail-za_is_company_contribution_created",
		"Payroll Settings-za_calculate_annual_taxable_amount_based_on",
		"Payroll Settings-za_coida_salary_component",
		"Payroll Settings-za_disable_eti_calculation",
		"Payroll Settings-za_eti_unregulated_minimum_monthly_wage",
		"Payroll Settings-za_official_interest_rate",
		"Payroll Settings-za_paye_salary_component",
		"Payroll Settings-za_payroll_column_break",
		"Payroll Settings-za_sdl_salary_component",
		"Payroll Settings-za_south_african_settings_section",
		"Payroll Settings-za_statutory_column_break",
		"Payroll Settings-za_statutory_components_section",
		"Payroll Settings-za_uif_employee_salary_component",
		"Payroll Settings-za_uif_employer_salary_component",
		"Salary Component-za_coida_applicable",
		"Salary Component-za_eti_wage_component",
		"Salary Component-za_exclude_from_irp5",
		"Salary Component-za_is_annual_bonus",
		"Salary Component-za_is_reimbursement",
		"Salary Component-za_paye_inclusion_percentage",
		"Salary Component-za_payroll_treatment",
		"Salary Component-za_sars_payroll_code",
		"Salary Component-za_sdl_applicable",
		"Salary Component-za_statutory_bases_section",
		"Salary Component-za_uif_applicable",
		"Salary Component-za_variable_pay_treatment",
		"Salary Slip-company_contribution",
		"Salary Slip-company_contribution_section",
		"Salary Slip-total_company_contribution",
		"Salary Slip-za_eti_hours",
		"Salary Slip-za_monthly_eti",
		"Salary Slip-za_paye_inclusion_adjustment",
		"Salary Slip-za_retirement_fund_taxable_excess",
		"Salary Structure Assignment-za_annual_bonus",
		"Salary Structure-company_contribution",
		"Salary Structure-company_contribution_section",
		# VAT custom fields absorbed from ir.ir_vat.setup.ensure_vat_custom_fields
		# (a second, separate custom-field source from za_local's main
		# custom_fields.py, found while retiring that function's own call).
		"Account-custom_sa_vat_compliance_section",
		"Account-custom_vat_return_debit_classification",
		"Account-custom_vat_return_credit_classification",
		"Item-is_zero_rated",
		"Item-custom_sa_vat_category",
		"Sales Invoice Item-is_zero_rated",
		"Sales Invoice Item-custom_sa_vat_category",
		"Purchase Invoice Item-is_zero_rated",
		"Purchase Invoice Item-custom_sa_vat_category"
	]]]},
	{"dt": "Property Setter", "filters": [["name", "in", [
        "Designation-ir_occupational_level",
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
        "Job Requisition-ir_remarks",
		# South African property setters absorbed from za_local - kept in
		# this same filter entry for the same reason as Custom Field above
		# (a second {"dt": "Property Setter", ...} entry would overwrite
		# this one's exported file instead of merging with it).
		"Additional Salary-main-protect_attached_files",
		"Asset Depreciation Schedule-main-protect_attached_files",
		"Asset-main-protect_attached_files",
		"Business Trip-main-protect_attached_files",
		"COIDA Annual Return-main-protect_attached_files",
		"Company-default_currency-default",
		"Contract-main-protect_attached_files",
		"Delivery Note-main-protect_attached_files",
		"EMP201 Submission-main-protect_attached_files",
		"EMP501 Reconciliation-main-protect_attached_files",
		"Employee Final Settlement-main-protect_attached_files",
		"Employee Separation-main-protect_attached_files",
		"Employee-current_accommodation_type-hidden",
		"Employee-permanent_accommodation_type-hidden",
		"Employee-salary_currency-default",
		"Employee-salary_mode-default",
		"Expense Claim-main-protect_attached_files",
		"IRP5 Certificate-main-protect_attached_files",
		"Journal Entry-main-protect_attached_files",
		"Leave Application-main-protect_attached_files",
		"OID Claim-main-protect_attached_files",
		"POS Invoice-main-protect_attached_files",
		"Payment Entry-main-protect_attached_files",
		"Payroll Entry-main-protect_attached_files",
		"Period Closing Voucher-main-protect_attached_files",
		"Purchase Invoice-main-protect_attached_files",
		"Purchase Order-main-protect_attached_files",
		"Purchase Receipt-main-protect_attached_files",
		"Quotation-main-protect_attached_files",
		"Request for Quotation-main-protect_attached_files",
		"Salary Component-type-options",
		"Salary Slip-main-protect_attached_files",
		"Salary Structure Assignment-employee_benefits-hidden",
		"Salary Structure Assignment-employee_benefits_section-hidden",
		"Salary Structure Assignment-max_benefits-hidden",
		"Salary Structure-currency-default",
		"Salary Structure-employee_benefits-hidden",
		"Salary Structure-max_benefits-hidden",
		"Sales Invoice-main-protect_attached_files",
		"Sales Order-main-protect_attached_files",
		"Supplier Quotation-main-protect_attached_files",
		"Tax Directive-main-protect_attached_files",
		"Uif U19 Declaration-main-protect_attached_files",
		"VAT201 Return-main-protect_attached_files",
		"Workplace Injury-main-protect_attached_files"
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
        "PRED",
        "RETR"
	]]]},
	# Print Format is NOT a fixture here - the absorbed SA print formats ship
	# as standard=Yes module-doc files under each module's print_format/
	# folder (same mechanism ir's own print formats already use), synced
	# automatically by bench migrate. A fixture entry would duplicate that
	# and risk silently overwriting a module-file edit on the next migrate.
	# South African reference/master data absorbed from za_local - generic
	# lookup data with no company/account linkage, so it's a plain fixture
	# rather than a seed function. (Salary Component is the one exception
	# in this list - it DOES carry a company-scoped `accounts` child table,
	# which fixture export would otherwise bake in as this site's specific
	# mappings; that child table is stripped from the exported fixture file
	# after each export, since per-company GL account mapping is handled
	# separately, as a real "needs a wizard" step - see ir.ir_setup.install.
	# ETI Slab is the other exception - it's a plain reconciling function,
	# ir.ir_setup.install.ensure_eti_slabs, not a fixture: a fixture creates/
	# matches by `name`, but ETI Slab's real identity constraint is a unique
	# `title`, so any site with its own pre-existing ETI Slab history (under
	# its own naming-series-assigned names) would hit a title collision the
	# moment a frozen-name fixture tried to insert a same-titled row -
	# confirmed on a lab bench with real prior ETI Slab usage.)
	{"dt": "SARS Payroll Code", "filters": [["name", "in", [
		"3805", "4497", "4477", "4476", "4475", "4474", "4472", "4142",
		"4141", "4120", "4115", "4118", "4116", "4102", "4010", "4008",
		"4007", "4006", "4005", "4001", "3907", "3901", "3802", "3713",
		"3704", "3702", "3701", "3607", "3605", "3601", "3801", "4473",
		"4003"
	]]]},
	{"dt": "Salary Component", "filters": [["name", "in", [
		"Other Fringe Benefit",
		"Low Interest Loan Fringe Benefit",
		"Housing Fringe Benefit",
		"Company Car PAYE Adjustment",
		"Company Car Benefit",
		"Special Allowance",
		"Shift Allowance",
		"Safety Bonus",
		"Overtime 2.0",
		"Overtime 1.5",
		"Opencast Allowance",
		"Hourly Earnings",
		"Health4Me Taxable Fringe Benefit",
		"Employer Provident Fund",
		"Employer Health4Me Contribution",
		"Employee Provident Fund",
		"Cellphone Allowance",
		"Tax on Lump Sum",
		"Notice Pay",
		"Leave Payout",
		"Severance Benefit",
		"Commission",
		"Overtime",
		"Performance Bonus",
		"13th Cheque",
		"Transport Allowance",
		"Housing Allowance",
		"Basic Salary",
		"SDL Contribution",
		"UIF Employer Contribution",
		"UIF Employee Contribution",
		"PAYE",
		"Leave Encashment",
		"Arrear",
		"Basic",
		"Income Tax"
	]]]},
	{"dt": "Business Trip Region", "filters": [["name", "in", [
		"International - Oceania",
		"International - Middle East",
		"International - Americas",
		"International - Asia",
		"International - Europe",
		"International - Africa",
		"Kimberley",
		"Nelspruit",
		"Polokwane",
		"East London",
		"Bloemfontein",
		"Port Elizabeth",
		"Pretoria",
		"Durban",
		"Cape Town",
		"Johannesburg"
	]]]},
	{"dt": "SETA", "filters": [["name", "in", [
		"W&R SETA", "THETA", "TETA", "Services SETA", "SASSETA", "PSETA",
		"MIMSSETA", "MICTSETA", "MICT SETA", "MerSETA", "MAPPP-SETA",
		"LGSETA", "INSETA", "HWSETA", "FP&M SETA", "FoodBev SETA", "FASSET",
		"EWSETA", "ESETA", "CTFL SETA", "CETA", "CHIETA", "BANKSETA",
		"AGRISETA"
	]]]},
	{"dt": "Bargaining Council", "filters": [["name", "in", [
		"Bargaining Council for the Private Security Sector",
		"Bargaining Council for the Contract Cleaning Industry",
		"National Bargaining Council for the Electrical Industry",
		"Furniture Bargaining Council",
		"Civil Engineering and Allied Trades Bargaining Council",
		"Building Industry Bargaining Council",
		"Restaurant, Catering and Allied Trades Bargaining Council",
		"Road Freight and Logistics Industry Bargaining Council",
		"National Bargaining Council for the Chemical Industry",
		"Motor Industry Bargaining Council",
		"Metal and Engineering Industries Bargaining Council"
	]]]},
	{"dt": "VAT Vendor Type", "filters": [["name", "in", [
		"Foreign Supplier",
		"Voluntary",
		"Small Business",
		"Micro Business",
		"Standard"
	]]]}
]
# ir requires HRMS (required_apps below), so HRMS-dependent registrations are
# unconditional - it is always installed wherever ir is.
doctype_js = {
	"COIDA Annual Return": "public/js/coida_annual_return.js",
	"Workplace Injury": "public/js/workplace_injury.js",
	"OID Claim": "public/js/oid_claim.js",
	"Sales Invoice": "public/js/vat_tax_calculation.js",
	"Purchase Invoice": "public/js/vat_tax_calculation.js",
	"Employee": "public/js/employee.js",
	"Payroll Entry": "public/js/payroll_entry.js",
	"Employee Benefit Claim": "public/js/employee_benefit_claim.js",
	"Salary Structure": "public/js/salary_structure.js",
	"Salary Structure Assignment": "public/js/salary_structure_assignment.js",
}
extend_doctype_class = {
	"Sales Invoice": "ir.overrides.vat_invoices.ZASalesInvoice",
	"Purchase Invoice": "ir.overrides.vat_invoices.ZAPurchaseInvoice",
	"Salary Slip": [
		"ir.ir_payroll.fringe_benefits.salary_slip.FringeBenefitSalarySlipMixin",
	],
}
override_doctype_class = {
	"Salary Slip": "ir.overrides.salary_slip.ZASalarySlip",
	"Payroll Entry": "ir.overrides.payroll_entry.ZAPayrollEntry",
	"Additional Salary": "ir.overrides.additional_salary.ZAAdditionalSalary",
	"Leave Application": "ir.overrides.leave_application.ZALeaveApplication",
	"Employee Separation": "ir.overrides.employee_separation.ZAEmployeeSeparation",
	"Salary Structure Assignment": "ir.overrides.salary_structure_assignment.ZASalaryStructureAssignment",
}
jinja = {
	"methods": [
		"ir.industrial_relations.doctype.written_outcome.written_outcome.get_outcome_body",
		"ir.industrial_relations.doctype.written_outcome.written_outcome.get_case_details_html",
	],
}
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
		"ir.controllers.employee_termination_sync.run_daily",
        "ir.controllers.demotion_expiry.run_daily",
	],
	"daily_long": [
		"ir.ir_payroll.fringe_benefits.tasks.refresh_fringe_benefit_statuses",
		# Absorbed from za_local.tasks as part of absorbing za_local into ir.
		"ir.tasks.daily",
	],
	"weekly_long": [
		"ir.tasks.weekly",
	],
	"monthly_long": [
		"ir.tasks.monthly",
		"ir.tasks.quarterly",
	],
}
# Absorbed from za_local - the post-ERPNext-setup-wizard SA stage (chart of
# accounts augmentation + salary component account repair + default print
# formats for a freshly created South African company).
setup_wizard_stages = "ir.ir_setup.setup_wizard.get_sa_localization_stages"
after_migrate = [
	"ir.setup.doctype_connections.ensure_employee_links",
	# Absorbed from za_local.sa_setup.custom_fields._get_doctype_link_records
	# - a "custom_records" hook that was never a real Frappe/ERPNext/HRMS
	# hook, so it was never actually consumed.
	"ir.setup.doctype_connections.ensure_doctype_connection_links",
	# Absorbed from za_local - company-scoped SA payroll/VAT setup that
	# can't be a fixture (varies per Company). Each is independently
	# idempotent and self-guards on table existence.
	"ir.ir_setup.install.ensure_all_company_tax_configuration",
	"ir.ir_setup.install.seed_statutory_rate_packs",
	"ir.ir_setup.install.ensure_eti_slabs",
	"ir.ir_setup.install.repair_salary_component_accounts",
	"ir.ir_vat.setup.migrate_legacy_vat_account_rows",
]
doc_events = {
	"Item": {
		"validate": "ir.ir_vat.item_sync.sync_item_zero_rated_flag",
	},
	"Customer": {
		"validate": "ir.overrides.customer.validate",
	},
	# SARS audit-trail deletion protection, absorbed from za_local/custom/
	# {sales,purchase}.py - found disconnected from any hook there.
	"Quotation": {"on_trash": "ir.overrides.sales.on_trash"},
	"Sales Order": {"on_trash": "ir.overrides.sales.on_trash"},
	"Sales Invoice": {"on_trash": "ir.overrides.sales.on_trash"},
	"Request for Quotation": {"on_trash": "ir.overrides.purchase.on_trash"},
	"Supplier Quotation": {"on_trash": "ir.overrides.purchase.on_trash"},
	"Purchase Order": {"on_trash": "ir.overrides.purchase.on_trash"},
	"Purchase Receipt": {"on_trash": "ir.overrides.purchase.on_trash"},
	"Purchase Invoice": {"on_trash": "ir.overrides.purchase.on_trash"},
	"Company": {
		"after_insert": "ir.ir_setup.install.configure_new_south_african_company",
	},
	# Absorbed from za_local/overrides/journal_entry.py as part of
	# absorbing za_local into ir.
	"Journal Entry": {
		"on_trash": "ir.overrides.journal_entry.on_trash",
		"on_cancel": "ir.overrides.journal_entry.on_cancel",
	},
	"Termination Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"validate": "ir.permissions.validate_termination_form",
	},
	"NTA Enquiry": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"validate": "ir.permissions.validate_nta_enquiry",
	},
	"Status Change Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
		"validate": "ir.permissions.validate_status_change_form",
	},
	"Site Transfer Form": {
		"after_insert": "ir.controllers.notifications.handle_doc_event_create",
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
		"validate": "ir.permissions.validate_site_transfer_form",
	},
	"Leave Application": {
        "validate": "ir.overrides.leave_application.set_letter_head_from_company",
        "before_submit": "ir.overrides.leave_application.validate_signed_leave_form_attached",
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
		"on_submit": "ir.controllers.notifications.handle_doc_event_submit",
	},
    "Incapacity Proceedings": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
        "validate": "ir.permissions.validate_incapacity_proceedings",
    },
    "Poor Performance": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
        "validate": "ir.permissions.validate_poor_performance",
    },
    "External Dispute Resolution": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
    },
    "Job Requisition": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
    },
    "Retrenchment Process": {
        "after_insert": "ir.controllers.notifications.handle_doc_event_create",
        "validate": "ir.permissions.validate_retrenchment_process",
    },
    "Written Outcome": {
        "validate": "ir.permissions.validate_written_outcome",
    },
    "Warning Form": {
        "validate": "ir.permissions.validate_warning_form",
    },
    "Suspension Form": {
        "validate": "ir.permissions.validate_suspension_form",
    },
    "Dismissal Form": {
        "validate": "ir.permissions.validate_dismissal_form",
    },
    "Demotion Form": {
        "validate": "ir.permissions.validate_demotion_form",
    },
    "Pay Deduction Form": {
        "validate": "ir.permissions.validate_pay_deduction_form",
    },
    "Pay Reduction Form": {
        "validate": "ir.permissions.validate_pay_reduction_form",
    },
    "No Further Action Form": {
        "validate": "ir.permissions.validate_no_further_action_form",
    },
    "Appeal Against Outcome": {
        "validate": "ir.permissions.validate_appeal_against_outcome",
    },
}
permission_query_conditions = {
    "Contract of Employment": "ir.permissions.contract_of_employment_permission_query_conditions",
    "Termination Form": "ir.permissions.termination_form_permission_query_conditions",
    "Status Change Form": "ir.permissions.status_change_form_permission_query_conditions",
    "Site Transfer Form": "ir.permissions.site_transfer_form_permission_query_conditions",
    "Disciplinary Action": "ir.permissions.disciplinary_action_permission_query_conditions",
    "Incapacity Proceedings": "ir.permissions.incapacity_proceedings_permission_query_conditions",
    "Poor Performance": "ir.permissions.poor_performance_permission_query_conditions",
    "NTA Enquiry": "ir.permissions.nta_enquiry_permission_query_conditions",
    "Written Outcome": "ir.permissions.written_outcome_permission_query_conditions",
    "Warning Form": "ir.permissions.warning_form_permission_query_conditions",
    "Suspension Form": "ir.permissions.suspension_form_permission_query_conditions",
    "Dismissal Form": "ir.permissions.dismissal_form_permission_query_conditions",
    "Demotion Form": "ir.permissions.demotion_form_permission_query_conditions",
    "Pay Deduction Form": "ir.permissions.pay_deduction_form_permission_query_conditions",
    "Pay Reduction Form": "ir.permissions.pay_reduction_form_permission_query_conditions",
    "No Further Action Form": "ir.permissions.no_further_action_form_permission_query_conditions",
    "Appeal Against Outcome": "ir.permissions.appeal_against_outcome_permission_query_conditions",
    "Retrenchment Process": "ir.permissions.retrenchment_process_permission_query_conditions",
    "Section 189 Notice": "ir.permissions.section_189_notice_permission_query_conditions",
    "S189 Consultation": "ir.permissions.s189_consultation_permission_query_conditions",
}
has_permission = {
    "Contract of Employment": "ir.permissions.contract_of_employment_has_permission",
    "Termination Form": "ir.permissions.termination_form_has_permission",
    "Status Change Form": "ir.permissions.status_change_form_has_permission",
    "Site Transfer Form": "ir.permissions.site_transfer_form_has_permission",
    "Disciplinary Action": "ir.permissions.disciplinary_action_has_permission",
    "Incapacity Proceedings": "ir.permissions.incapacity_proceedings_has_permission",
    "Poor Performance": "ir.permissions.poor_performance_has_permission",
    "NTA Enquiry": "ir.permissions.nta_enquiry_has_permission",
    "Written Outcome": "ir.permissions.written_outcome_has_permission",
    "Warning Form": "ir.permissions.warning_form_has_permission",
    "Suspension Form": "ir.permissions.suspension_form_has_permission",
    "Dismissal Form": "ir.permissions.dismissal_form_has_permission",
    "Demotion Form": "ir.permissions.demotion_form_has_permission",
    "Pay Deduction Form": "ir.permissions.pay_deduction_form_has_permission",
    "Pay Reduction Form": "ir.permissions.pay_reduction_form_has_permission",
    "No Further Action Form": "ir.permissions.no_further_action_form_has_permission",
    "Appeal Against Outcome": "ir.permissions.appeal_against_outcome_has_permission",
    "Retrenchment Process": "ir.permissions.retrenchment_process_has_permission",
    "Section 189 Notice": "ir.permissions.section_189_notice_has_permission",
    "S189 Consultation": "ir.permissions.s189_consultation_has_permission",
}