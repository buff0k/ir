# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""South African post-setup-wizard stage.

Ported from za_local.sa_setup.setup_wizard (get_sa_localization_stages /
setup_za_localization / setup_sa_print_formats) as part of absorbing
za_local into ir. ERPNext remains responsible for Company, Fiscal Year,
chart, defaults, and core masters; this stage only augments an existing
South African company immediately after the wizard creates it - Company,
tax period/slab/rebate/public-holiday seeding is already handled by
Company.after_insert (ir.ir_setup.install.configure_new_south_african_company),
so this stage is left with just the two things that aren't: chart-of-
accounts augmentation (needs ERPNext's own accounts to already exist) and
salary component account repair, plus setting sensible default print
formats. ir requires HRMS (required_apps in hooks.py), so unlike za_local's
original version this never needs an HRMS-absent branch.
"""

import frappe
from frappe import _

from ir.ir_setup.install import load_sa_chart_of_accounts, repair_salary_component_accounts

PRINT_FORMAT_MAPPING = {
	"Sales Invoice": "SA Sales Invoice",
	"Quotation": "SA Quotation",
	"Sales Order": "SA Sales Order",
	"Delivery Note": "SA Delivery Note",
	"Purchase Invoice": "SA Purchase Invoice",
	"Purchase Order": "SA Purchase Order",
	"Payment Entry": "SA Payment Entry",
	"Salary Slip": "SA Salary Slip",
	"IRP5 Certificate": "IRP5 Employee Certificate",
}


def setup_sa_print_formats():
	"""Set available SA print formats as site defaults."""
	print("\n→ Setting up SA-compliant print formats...")

	for doctype, print_format in PRINT_FORMAT_MAPPING.items():
		try:
			if frappe.db.exists("DocType", doctype) and frappe.db.exists("Print Format", print_format):
				frappe.db.set_value("DocType", doctype, "default_print_format", print_format)
				print(f"  ✓ Set {print_format} as default for {doctype}")
		except Exception as e:
			print(f"  ! Error setting print format for {doctype}: {e}")

	print("  ✓ SA print formats configured successfully")


def get_sa_localization_stages(args):
	"""Return the minimal ir post-ERPNext setup stage.

	Called by Frappe's setup wizard via the setup_wizard_stages hook.
	"""
	country = args.get("country")
	if country != "South Africa":
		return []

	return [
		{
			"status": _("Configuring South African Localization"),
			"fail_msg": _("Failed to configure SA localization"),
			"tasks": [
				{
					"fn": setup_za_localization,
					"args": args,
					"fail_msg": _("Failed to setup SA localization"),
				}
			],
		}
	]


def setup_za_localization(args):
	"""Execute the minimal non-blocking ir setup during ERPNext first run.

	ERPNext remains responsible for Company, Fiscal Year, chart, defaults, and
	core masters. This stage only augments an existing South African company.
	"""
	company = (
		args.get("company_name")
		or args.get("company")
		or frappe.defaults.get_user_default("Company")
	)
	if not company:
		companies = frappe.get_all(
			"Company",
			filters={"country": "South Africa"},
			pluck="name",
			limit=1,
		)
		company = companies[0] if companies else None

	try:
		if not company or not frappe.db.exists("Company", company):
			print("  ⊙ ZA setup skipped: ERPNext Company is not available yet")
			return

		account_count = frappe.db.count("Account", {"company": company})
		if not account_count:
			print(f"  ⊙ ZA chart augmentation skipped for {company}: no ERPNext accounts found")
			return
		else:
			added = load_sa_chart_of_accounts(company)
			if added:
				print("  ✓ ZA statutory accounts added to ERPNext Chart of Accounts")
			repair_salary_component_accounts(company)

		setup_sa_print_formats()
		frappe.clear_cache()
		print("✓ South African localization post-setup completed")

	except Exception as e:
		# Log the error but don't raise - allow setup wizard to continue
		frappe.log_error(frappe.get_traceback(), "IR Setup")
		print(f"✗ SA Localization setup encountered errors: {e}")
		print("  Note: Some features may not be configured. Check error logs for details.")
