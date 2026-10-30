# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Company-scoped South African payroll/accounting setup, absorbed from
za_local's install.py / sa_setup/statutory_setup.py / accounts/setup_chart.py.

This is deliberately the one part of that absorption that stays real code
rather than becoming a fixture: chart-of-accounts augmentation and
statutory-master seeding are per-Company, so a static fixture can't express
them correctly (a fresh install has a different set of companies/accounts).
Everything that WAS genuinely global reference data (Custom Fields, Property
Setters, ETI Slab, SARS Payroll Code, Salary Component definitions, etc.)
already moved to ir's own fixtures instead - see ir/ir/fixtures/.
"""

from copy import deepcopy
from functools import lru_cache
from pathlib import Path

import frappe
from frappe import _
from frappe.utils import flt, getdate

from ir.utils.statutory_rates import get_tax_year_for_date


def _data_path(filename: str) -> Path:
	return Path(frappe.get_app_path("ir")) / "ir_setup" / "data" / filename


def _read_data_json(filename: str):
	return frappe.get_file_json(str(_data_path(filename)))


def _read_records(filename: str):
	data = _read_data_json(filename)
	return data if isinstance(data, list) else [data]


# ---------------------------------------------------------------------------
# Chart of Accounts augmentation (absorbed from za_local/accounts/setup_chart.py)
# ---------------------------------------------------------------------------


def load_sa_chart_of_accounts(company):
	"""Augment an existing company Chart of Accounts with South African accounts.

	ERPNext creates the base chart during company setup; this only adds
	ZA-specific statutory accounts after the base accounts exist.
	"""
	if not company:
		frappe.log_error("Company is required to load Chart of Accounts", "IR Chart of Accounts")
		return False
	if not frappe.db.exists("Company", company):
		frappe.log_error(f"Company '{company}' does not exist", "IR Chart of Accounts")
		return False

	try:
		existing_accounts = frappe.db.count("Account", {"company": company})
		if existing_accounts == 0:
			frappe.log_error(
				f"No accounts found for company {company} when attempting to load ZA Chart of Accounts. "
				"Skipping ZA chart augmentation.",
				"IR Chart of Accounts",
			)
			return False

		_add_sa_tax_accounts(company)
		return True

	except Exception as e:
		frappe.log_error(
			f"Error loading Chart of Accounts for {company}: {e!s}\n{frappe.get_traceback()}",
			"IR Chart of Accounts",
		)
		return False


def _get_root_account(company, root_type):
	name = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": root_type, "parent_account": ("in", ("", None))},
		"name",
	)
	return frappe.get_doc("Account", name) if name else None


def _get_account_by_name_and_parent(company, account_name, parent_account_name):
	parent = frappe.db.get_value(
		"Account", {"company": company, "account_name": parent_account_name}, "name"
	)
	if not parent:
		return None
	name = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": account_name, "parent_account": parent},
		"name",
	)
	return frappe.get_doc("Account", name) if name else None


def _get_child_account_under(company, parent_doc, preferred_names):
	children = frappe.get_all(
		"Account",
		filters={"company": company, "parent_account": parent_doc.name},
		fields=["name", "account_name"],
	)
	if not children:
		return None
	preferred = list(preferred_names)
	for c in children:
		if c.account_name in preferred:
			return frappe.get_doc("Account", c.name)
		if preferred and c.account_name and c.account_name.startswith(preferred[0]):
			return frappe.get_doc("Account", c.name)
	return None


def _get_or_create_tax_group_under(company, parent_account_doc, preferred_names, account_type="Tax"):
	for preferred_name in preferred_names:
		existing = frappe.db.get_value(
			"Account",
			{
				"company": company,
				"account_name": preferred_name,
				"parent_account": parent_account_doc.name,
				"is_group": 1,
			},
			"name",
		)
		if existing:
			return frappe.get_doc("Account", existing)
	return _get_or_create_account(
		company, preferred_names[0], account_type, parent=parent_account_doc.name, is_group=1
	)


def _add_sa_tax_accounts(company):
	"""Add SA-specific tax ledgers into Current Assets/Liabilities of an existing chart."""
	liabilities_root = _get_root_account(company, "Liability")
	assets_root = _get_root_account(company, "Asset")
	if not liabilities_root or not assets_root:
		raise ValueError(
			f"Could not find Chart of Accounts roots for company {company} "
			f"(Liability root={bool(liabilities_root)}, Asset root={bool(assets_root)})"
		)

	current_liabilities = _get_child_account_under(
		company, liabilities_root, ["Current Liabilities"]
	) or _get_account_by_name_and_parent(company, "Current Liabilities", liabilities_root.account_name)
	current_assets = _get_child_account_under(
		company, assets_root, ["Current Assets"]
	) or _get_account_by_name_and_parent(company, "Current Assets", assets_root.account_name)
	if not current_liabilities or not current_assets:
		raise ValueError(f"Could not find Current Liabilities or Current Assets for company {company}")

	tax_liabilities = _get_or_create_tax_group_under(
		company, current_liabilities, ["Tax Liabilities", "Duties and Taxes"]
	)
	tax_assets = _get_or_create_tax_group_under(company, current_assets, ["Tax Assets"])

	for account_name in (
		"VAT Collected - Sales",
		"VAT Payable - SARS",
		"PAYE Payable - SARS",
		"UIF Employee Contribution",
		"UIF Employer Contribution",
		"SDL Payable - SARS",
		"COIDA Payable",
	):
		_get_or_create_account(company, account_name, "Tax", parent=tax_liabilities.name, is_group=0)

	for account_name in ("VAT Paid - Purchases",):
		_get_or_create_account(company, account_name, "Tax", parent=tax_assets.name, is_group=0)

	expense_root = _get_root_account(company, "Expense")
	if not expense_root:
		return

	indirect_expenses = (
		_get_child_account_under(company, expense_root, ["Indirect Expenses", "Expenses"]) or expense_root
	)

	employer_contribution_group = _get_or_create_account(
		company,
		"Employer Payroll Contributions",
		"Expense Account",
		parent=indirect_expenses.name,
		is_group=1,
	)

	for account_name in (
		"Salaries and Wages",
		"COIDA Expense",
		"UIF Employer Expense",
		"SDL Expense",
		"Pension Fund Employer Expense",
		"Medical Aid Employer Expense",
	):
		_get_or_create_account(
			company, account_name, "Expense Account", parent=employer_contribution_group.name, is_group=0
		)


def _get_or_create_account(company, account_name, account_type, parent=None, is_group=0, root_type=None):
	existing = frappe.db.get_value("Account", {"company": company, "account_name": account_name}, "name")
	if existing:
		return frappe.get_doc("Account", existing)

	account_doc = frappe.get_doc(
		{
			"doctype": "Account",
			"company": company,
			"account_name": account_name,
			"account_type": account_type,
			"parent_account": parent or "",
			"is_group": is_group,
			"root_type": root_type,
		}
	)
	if root_type:
		account_doc.flags.ignore_mandatory = True
	account_doc.flags.ignore_permissions = True
	account_doc.insert()
	return account_doc


# ---------------------------------------------------------------------------
# Salary Component GL account mapping (absorbed from za_local/sa_setup/install.py)
# ---------------------------------------------------------------------------

DEFAULT_SALARY_COMPONENT_ACCOUNT_NAMES = {
	"Basic": "Salaries and Wages",
	"Basic Salary": "Salaries and Wages",
	"Arrear": "Salaries and Wages",
	"Leave Encashment": "Salaries and Wages",
	"PAYE": "PAYE Payable - SARS",
	"Income Tax": "PAYE Payable - SARS",
	"UIF": "UIF Employee Contribution",
	"UIF Employee Contribution": "UIF Employee Contribution",
	"UIF Employer Contribution": "UIF Employer Expense",
	"SDL": "SDL Expense",
	"SDL Contribution": "SDL Expense",
	"COIDA": "COIDA Expense",
	"COIDA Contribution": "COIDA Expense",
}


def repair_salary_component_accounts(company: str | None = None):
	"""Map HRMS/ZA salary components to ZA statutory accounts when accounts exist."""
	if not frappe.db.table_exists("Salary Component") or not frappe.db.table_exists("Salary Component Account"):
		return

	companies = [company] if company else frappe.get_all(
		"Company", filters={"country": "South Africa"}, pluck="name"
	)
	if not companies:
		return

	repaired = 0
	for company_name in companies:
		if not company_name or not frappe.db.exists("Company", company_name):
			continue

		load_sa_chart_of_accounts(company_name)

		for component, account_name in DEFAULT_SALARY_COMPONENT_ACCOUNT_NAMES.items():
			if not frappe.db.exists("Salary Component", component):
				continue

			account = frappe.db.get_value(
				"Account", {"company": company_name, "account_name": account_name, "is_group": 0}, "name"
			)
			if not account:
				continue

			row_name = frappe.db.get_value(
				"Salary Component Account", {"parent": component, "company": company_name}, "name"
			)
			if row_name:
				frappe.db.set_value("Salary Component Account", row_name, "account", account, update_modified=False)
				repaired += 1
				continue

			doc = frappe.get_doc("Salary Component", component)
			doc.append("accounts", {"company": company_name, "account": account})
			doc.save(ignore_permissions=True)
			repaired += 1

	if repaired:
		print(f"  ✓ Repaired Salary Component account mappings ({repaired})")


# ---------------------------------------------------------------------------
# Per-company statutory masters (absorbed from za_local/sa_setup/statutory_setup.py)
# ---------------------------------------------------------------------------

PAYROLL_PERIOD_FILES = ("payroll_period_2025.json", "payroll_period_2026.json", "payroll_period_2027.json")
INCOME_TAX_SLAB_FILES = ("tax_slabs_2025.json", "tax_slabs_2026.json", "tax_slabs_2027.json")
TAX_REBATE_FILES = ("tax_rebates_2025.json", "tax_rebates_2026.json", "tax_rebates_2027.json")
PUBLIC_HOLIDAY_FILES = ("holiday_list_2025.json", "holiday_list_2026.json", "holiday_list_2027.json")


def ensure_all_company_tax_configuration():
	"""Create missing statutory tax masters for every South African company."""
	ensure_sa_public_holiday_lists()

	companies = frappe.get_all(
		"Company", filters={"country": "South Africa"}, pluck="name", order_by="creation asc"
	)
	results = {}
	for company in companies:
		results[company] = ensure_company_tax_configuration(company)
	return results


def ensure_sa_public_holiday_lists():
	"""Synchronize the app-owned official public-holiday reference lists.

	Public holidays only - not forced as Company defaults, since weekly-off
	rules differ by employer.
	"""
	if not frappe.db.exists("DocType", "Holiday List"):
		return []

	synchronized = []
	for filename in PUBLIC_HOLIDAY_FILES:
		for source in _read_records(filename):
			name = source["holiday_list_name"]
			doc = frappe.get_doc("Holiday List", name) if frappe.db.exists("Holiday List", name) else frappe.new_doc(
				"Holiday List"
			)
			desired_holidays = [
				(str(row["holiday_date"]), row.get("description") or "", int(row.get("weekly_off") or 0))
				for row in source.get("holidays") or []
			]
			current_holidays = [
				(str(row.holiday_date), row.description or "", int(row.weekly_off or 0))
				for row in doc.get("holidays") or []
			]
			is_current = (
				not doc.is_new()
				and str(doc.from_date) == str(source["from_date"])
				and str(doc.to_date) == str(source["to_date"])
				and current_holidays == desired_holidays
			)
			if is_current:
				synchronized.append(name)
				continue

			doc.holiday_list_name = name
			doc.from_date = source["from_date"]
			doc.to_date = source["to_date"]
			doc.set("holidays", [])
			for row in source.get("holidays") or []:
				doc.append("holidays", row)
			doc.flags.ignore_permissions = True
			if doc.is_new():
				doc.insert(ignore_permissions=True)
			else:
				doc.save(ignore_permissions=True)
			synchronized.append(doc.name)
	return synchronized


def configure_new_south_african_company(doc, method=None):
	"""Create required payroll masters after ERPNext creates an SA company.

	Registered as the Company.after_insert doc_event in ir/ir/hooks.py.
	"""
	if doc.country != "South Africa":
		return

	ensure_company_tax_configuration(doc.name)
	seed_statutory_rate_packs()


def ensure_company_tax_configuration(company: str):
	"""Create missing payroll periods, slabs, rebates and credits for one company.

	Existing statutory documents are never overwritten. Annual changes must be
	shipped as a new rate pack/fixture and applied through a versioned patch.
	"""
	_validate_company(company)
	period_names = {}
	created = []

	for filename in PAYROLL_PERIOD_FILES:
		for record in _read_records(filename):
			original_name = record["name"]
			actual_name, was_created = _ensure_company_record(record, company)
			period_names[original_name] = actual_name
			if was_created:
				created.append(actual_name)

	for filename in INCOME_TAX_SLAB_FILES:
		for record in _read_records(filename):
			actual_name, was_created = _ensure_company_record(record, company)
			if was_created:
				created.append(actual_name)

	settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
	for filename in TAX_REBATE_FILES:
		data = _read_data_json(filename)
		_upsert_missing_child_rows(settings, "tax_rebates_rate", data, period_names)
		_upsert_missing_child_rows(settings, "medical_tax_credit", data, period_names)
	settings.flags.ignore_permissions = True
	settings.save(ignore_permissions=True)

	return {"created": created, "payroll_periods": period_names}


def get_missing_current_tax_configuration(company: str, date_value=None) -> list[str]:
	"""Return actionable missing-master messages for the supplied tax year."""
	date_value = getdate(date_value or frappe.utils.today())
	tax_year = get_tax_year_for_date(date_value)
	missing = []

	period = frappe.db.get_value(
		"Payroll Period",
		{"company": company, "start_date": ["<=", date_value], "end_date": [">=", date_value]},
		"name",
	)
	if not period:
		missing.append(_("Payroll Period for {0} ({1})").format(company, tax_year))

	slab = frappe.db.get_value(
		"Income Tax Slab",
		{"company": company, "effective_from": ["<=", date_value], "disabled": 0, "docstatus": 1},
		"name",
		order_by="effective_from desc",
	)
	if not slab:
		missing.append(_("submitted Income Tax Slab for {0} ({1})").format(company, tax_year))

	if period:
		settings = frappe.get_single("Tax Rebates and Medical Tax Credit")
		if not any(row.payroll_period == period for row in settings.tax_rebates_rate or []):
			missing.append(_("Tax Rebate row for Payroll Period {0}").format(period))
		if not any(row.payroll_period == period for row in settings.medical_tax_credit or []):
			missing.append(_("Medical Tax Credit row for Payroll Period {0}").format(period))

	return missing


def validate_current_tax_configuration(company: str, date_value=None):
	"""Fail payroll setup loudly when statutory masters are incomplete."""
	missing = get_missing_current_tax_configuration(company, date_value)
	if missing:
		frappe.throw(
			_("South African payroll setup is incomplete:<br>{0}").format(
				"<br>".join(f"• {frappe.utils.escape_html(item)}" for item in missing)
			),
			title=_("Incomplete South African Payroll Setup"),
		)


def _validate_company(company: str):
	if not company or not frappe.db.exists("Company", company):
		frappe.throw(_("A valid Company is required to configure South African payroll."))
	if frappe.db.get_value("Company", company, "country") != "South Africa":
		frappe.throw(_("Company {0} is not configured for South Africa.").format(company))


def _ensure_company_record(source: dict, company: str) -> tuple[str, bool]:
	record = deepcopy(source)
	doctype = record["doctype"]
	base_name = record["name"]
	name = _get_company_scoped_name(doctype, base_name, company)
	record["name"] = name
	record["company"] = company

	if frappe.db.exists(doctype, name):
		return name, False

	doc = frappe.get_doc(record)
	doc.insert(ignore_permissions=True)
	if doc.meta.is_submittable and doc.docstatus == 0:
		doc.submit()
	return doc.name, True


def _get_company_scoped_name(doctype: str, base_name: str, company: str) -> str:
	if frappe.db.exists(doctype, base_name):
		existing_company = frappe.db.get_value(doctype, base_name, "company")
		if existing_company in (None, "", company):
			return base_name

	company_count = frappe.db.count("Company", {"country": "South Africa"})
	if company_count <= 1 and not frappe.db.exists(doctype, base_name):
		return base_name

	abbr = frappe.db.get_value("Company", company, "abbr") or company
	return f"{base_name} - {abbr}"


def _upsert_missing_child_rows(settings, child_field: str, data: dict, period_names: dict):
	existing = {row.payroll_period for row in settings.get(child_field) or []}
	for source in data.get(child_field) or []:
		row = deepcopy(source)
		row["payroll_period"] = period_names.get(row["payroll_period"], row["payroll_period"])
		if row["payroll_period"] in existing:
			continue
		settings.append(child_field, row)
		existing.add(row["payroll_period"])


# ---------------------------------------------------------------------------
# Per-company travel allowance rates (absorbed from za_local/sa_setup/install.py)
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def _load_rate_packs():
	packs = []
	for filename in ("statutory_rates_2025.json", "statutory_rates_2026.json", "statutory_rates_2027.json"):
		pack = _read_data_json(filename)
		if pack.get("is_active", 1):
			packs.append(pack)
	return tuple(packs)


def clear_rate_pack_cache():
	_load_rate_packs.cache_clear()


def seed_statutory_rate_packs():
	"""Seed per-company travel allowance rates from the statutory rate packs.

	ETI Slab seeding is not ported here - those are now ir's own fixtures
	(ir/ir/fixtures/eti_slab.json), since ETI Slab is generic reference data
	with no company scoping.
	"""
	clear_rate_pack_cache()
	companies = frappe.get_all("Company", filters={"country": "South Africa"}, pluck="name")
	for pack in _load_rate_packs():
		for company in companies:
			_seed_travel_rate_from_rate_pack(pack, company)


def _seed_travel_rate_from_rate_pack(pack: dict, company: str):
	if not frappe.db.exists("DocType", "Travel Allowance Rate"):
		return
	travel = pack.get("travel") or {}
	rate_name = f"Travel Allowance {pack.get('tax_year')}"
	existing_name = frappe.db.get_value(
		"Travel Allowance Rate",
		{"rate_name": rate_name, "company": company, "docstatus": ["<", 2]},
		"name",
		order_by="creation desc",
	)
	doc = (
		frappe.get_doc("Travel Allowance Rate", existing_name)
		if existing_name
		else frappe.new_doc("Travel Allowance Rate")
	)
	desired_rate = flt(travel.get("reimbursive_rate_per_km"))
	desired_fixed_rate = flt(travel.get("fixed_allowance_default_paye_inclusion_percentage"))
	if (
		existing_name
		and flt(doc.reimbursive_rate_per_km) == desired_rate
		and flt(doc.fixed_allowance_rate) == desired_fixed_rate
		and str(doc.effective_from) == str(pack.get("effective_from"))
	):
		return
	if existing_name and doc.docstatus == 1:
		doc.cancel()
		amended_from = doc.name
		doc = frappe.copy_doc(doc)
		doc.amended_from = amended_from
	doc.rate_name = rate_name
	doc.effective_from = pack.get("effective_from")
	doc.reimbursive_rate_per_km = desired_rate
	doc.fixed_allowance_rate = desired_fixed_rate
	doc.company = company
	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	if doc.docstatus == 0:
		doc.submit()


# ---------------------------------------------------------------------------
# ZA Local Setup wizard (absorbed from za_local/sa_setup/install.py's
# run_za_local_setup/run_za_local_setup_job and friends)
# ---------------------------------------------------------------------------
#
# As with the rest of this absorption, every checkbox that used to
# imperatively create Custom Fields, Property Setters, or generic
# (non-company-scoped) reference/master data - VAT custom fields, VAT vendor
# types, salary components, earnings components, SARS payroll codes, salary
# component classifications, ETI slabs, business trip regions, SETA list,
# bargaining councils - no longer runs any code here. That content is ir's
# own fixtures (ir/ir/fixtures/*.json), applied automatically by bench
# migrate regardless of this wizard. Only the genuinely company-scoped
# pieces, which can't be a fixture since they vary per Company, still run
# here. za_local's own warning-suppression wrapper (a global monkey-patch of
# frappe.msgprint) was not ported, consistent with dropping the other
# monkey patches during this absorption - at most a few more benign
# messages may surface during setup, nothing functional.


def ensure_accounts_settings_for_za_vat():
	"""Configure Accounts Settings so SA VAT tax rows come from document
	templates only (see ir.patches.set_accounts_settings_for_za_vat for why).
	"""
	if not frappe.db.exists("DocType", "Accounts Settings"):
		return

	settings = frappe.get_single("Accounts Settings")
	if (
		settings.add_taxes_from_taxes_and_charges_template == 1
		and settings.add_taxes_from_item_tax_template == 0
	):
		return

	settings.add_taxes_from_taxes_and_charges_template = 1
	settings.add_taxes_from_item_tax_template = 0
	settings.flags.ignore_permissions = True
	settings.save()


def setup_default_retirement_funds(company):
	"""Create default retirement fund types for one South African company."""
	retirement_funds = [
		{"fund_name": "Company Pension Fund", "fund_type": "Pension Fund"},
		{"fund_name": "Company Provident Fund", "fund_type": "Provident Fund"},
		{"fund_name": "Retirement Annuity", "fund_type": "Retirement Annuity"},
	]

	for fund in retirement_funds:
		if frappe.db.exists("Retirement Fund", {"fund_name": fund["fund_name"], "company": company}):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Retirement Fund",
				**fund,
				"employee_contribution_percentage": 7.5,
				"employer_contribution_percentage": 10.0,
				"tax_deductible_limit": 27.5,  # 27.5% of taxable income
				"company": company,
			}
		)
		doc.insert(ignore_permissions=True)


def get_setup_field_label(setup_doc, fieldname: str) -> str:
	meta = getattr(setup_doc, "meta", None)
	if meta:
		try:
			field = meta.get_field(fieldname)
			if field and field.label:
				return field.label
		except Exception:
			pass
	return fieldname.replace("_", " ").title()


def build_za_local_setup_feedback(setup_doc, applied, warnings):
	return {
		"title": _("ZA Local Setup Complete"),
		"indicator": "orange" if warnings else "green",
		"message": _("South African localisation configuration was applied."),
		"details": [
			{"label": _("Company"), "value": setup_doc.company},
			{"label": _("Applied Configuration"), "value": applied},
			{"label": _("Setup Status"), "value": setup_doc.setup_status},
			{"label": _("Completed On"), "value": setup_doc.setup_completed_on},
		],
		"warnings": warnings,
		"next_steps": [
			_("Open South Africa VAT Settings and confirm the company VAT details."),
			_("Review VAT accounts, tax templates, and VAT201 mappings before filing."),
			_("Use VAT201 Return to fetch and review transactions for the first period."),
		],
		"status": setup_doc.setup_status,
		"setup_completed_on": setup_doc.setup_completed_on,
		"applied": applied,
	}


def _publish_setup_progress(progress_user, percent, message):
	"""Push a realtime progress update to the user who launched the setup."""
	if not progress_user:
		return
	frappe.publish_realtime(
		"za_local_setup_progress",
		{"progress": percent, "message": message},
		user=progress_user,
	)


def run_za_local_setup(setup_doc, progress_user=None):
	"""
	Execute the SA setup wizard based on user selections.
	Called from ZA Local Setup DocType when user completes the setup wizard.

	Args:
		setup_doc: ZA Local Setup document instance
		progress_user: if set, realtime progress is published to this user
	"""
	from ir.ir_vat.setup import migrate_legacy_vat_account_rows

	applied = []
	warnings = []

	def _p(percent, message):
		_publish_setup_progress(progress_user, percent, message)

	setup_doc.setup_status = "In Progress"
	setup_doc.save()

	try:
		_p(5, _("Applying VAT accounts and settings"))
		migrated = migrate_legacy_vat_account_rows()
		ensure_accounts_settings_for_za_vat()
		applied.append(_("VAT accounts and settings"))
		if migrated:
			applied.append(_("{0} legacy VAT account rows migrated").format(migrated))

		# These records form one interdependent statutory configuration. Create
		# missing company-scoped records together and preserve existing masters.
		if setup_doc.load_tax_slabs or setup_doc.load_tax_rebates or setup_doc.load_medical_credits:
			_p(42, _("Ensuring company payroll tax configuration"))
			ensure_company_tax_configuration(setup_doc.company)
			if setup_doc.load_tax_slabs:
				applied.append(get_setup_field_label(setup_doc, "load_tax_slabs"))
			if setup_doc.load_tax_rebates:
				applied.append(get_setup_field_label(setup_doc, "load_tax_rebates"))
			if setup_doc.load_medical_credits:
				applied.append(get_setup_field_label(setup_doc, "load_medical_credits"))

		# Travel allowance rates (company-scoped; ETI slabs are ir's own fixture now)
		if setup_doc.get("load_eti_slabs"):
			_p(56, _("Seeding travel allowance rates"))
			seed_statutory_rate_packs()
			applied.append(get_setup_field_label(setup_doc, "load_eti_slabs"))

		# Retirement fund defaults
		if setup_doc.get("load_retirement_funds") and setup_doc.company:
			_p(78, _("Loading retirement funds"))
			setup_default_retirement_funds(setup_doc.company)
			applied.append(get_setup_field_label(setup_doc, "load_retirement_funds"))

		# Load Chart of Accounts
		if setup_doc.load_chart_of_accounts and setup_doc.company:
			_p(92, _("Loading South African chart of accounts"))
			try:
				load_sa_chart_of_accounts(setup_doc.company)
				applied.append(get_setup_field_label(setup_doc, "load_chart_of_accounts"))
			except Exception as e:
				frappe.log_error(f"Chart of Accounts loading failed: {e!s}", "IR Setup")
				warnings.append(_("Chart of Accounts could not be loaded automatically. Review Error Log."))

		if setup_doc.company:
			repair_salary_component_accounts(setup_doc.company)

		# Mark as completed
		_p(98, _("Finalising"))
		setup_doc.setup_status = "Completed"
		setup_doc.setup_completed_on = frappe.utils.now()
		setup_doc.save()

		return build_za_local_setup_feedback(setup_doc, applied, warnings)

	except Exception as e:
		setup_doc.setup_status = "Pending"
		setup_doc.save()
		frappe.log_error(f"Setup failed: {e!s}", "IR Setup")
		frappe.throw(f"Setup failed: {e!s}")


def run_za_local_setup_job(setup_name, user=None):
	"""Background-job wrapper for run_za_local_setup.

	Runs the setup on a worker (enqueued by ZA Local Setup.start_setup), publishing
	realtime progress and a completion event to ``user``. On failure it rolls back,
	resets the status to "Pending", and notifies the user instead of leaving the
	request to time out. Never re-raises (so the status reset is committed by the
	job wrapper).
	"""
	user = user or frappe.session.user
	try:
		setup_doc = frappe.get_doc("ZA Local Setup", setup_name)
		result = run_za_local_setup(setup_doc, progress_user=user)
		_publish_setup_progress(user, 100, _("Setup complete"))
		frappe.publish_realtime("za_local_setup_done", result, user=user)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "IR Setup job")
		frappe.db.set_value("ZA Local Setup", setup_name, "setup_status", "Pending", update_modified=False)
		frappe.publish_realtime(
			"za_local_setup_done",
			{
				"title": _("Setup Failed"),
				"indicator": "red",
				"message": _("ZA Local Setup did not complete. Review the Error Log, then try again."),
				"failed": True,
			},
			user=user,
		)
