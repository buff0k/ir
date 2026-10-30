# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Move legacy site-specific IRP5 source fields into the app-owned za_ fields.

Ported from za_local.sa_setup.install.migrate_irp5_legacy_source_fields as
part of absorbing za_local into ir - that function ran unconditionally on
every install/migrate even though it is a one-time backfill, not a
recurring task.
"""

import frappe


def execute():
	if frappe.db.exists("DocType", "Company") and frappe.db.has_column(
		"Company", "custom_paye_reference_number"
	):
		for company in frappe.get_all(
			"Company", fields=["name", "za_paye_reference_number", "custom_paye_reference_number"]
		):
			if company.za_paye_reference_number:
				continue
			if company.custom_paye_reference_number:
				frappe.db.set_value(
					"Company",
					company.name,
					"za_paye_reference_number",
					company.custom_paye_reference_number,
					update_modified=False,
				)

	if frappe.db.exists("DocType", "Employee") and frappe.db.has_column("Employee", "custom_tax_number"):
		for employee in frappe.get_all(
			"Employee",
			fields=["name", "za_income_tax_reference_number", "custom_tax_number"],
		):
			if employee.za_income_tax_reference_number:
				continue
			if employee.custom_tax_number:
				frappe.db.set_value(
					"Employee",
					employee.name,
					"za_income_tax_reference_number",
					employee.custom_tax_number,
					update_modified=False,
				)

	if frappe.db.exists("DocType", "Employee") and frappe.db.has_column(
		"Employee", "custom_residential_address"
	):
		for employee in frappe.get_all(
			"Employee",
			fields=["name", "employee_name", "za_residential_address", "custom_residential_address"],
		):
			if employee.za_residential_address:
				continue
			address_text = (employee.custom_residential_address or "").strip()
			if not address_text:
				continue

			address_name = _create_irp5_address_from_legacy_text(
				employee.name, employee.employee_name, address_text
			)
			if address_name:
				frappe.db.set_value(
					"Employee",
					employee.name,
					"za_residential_address",
					address_name,
					update_modified=False,
				)

	frappe.db.commit()


def _create_irp5_address_from_legacy_text(
	employee_name: str, employee_display_name: str | None, address_text: str
):
	title = employee_display_name or employee_name
	existing = frappe.get_all(
		"Address",
		filters={"address_title": title, "address_type": "Personal"},
		fields=["name", "address_line1", "address_line2"],
		limit=1,
	)
	if existing:
		return existing[0].name

	lines = [line.strip() for line in address_text.splitlines() if line.strip()]
	if not lines:
		return None

	address = frappe.new_doc("Address")
	address.address_title = title
	address.address_type = "Personal"
	address.address_line1 = lines[0]
	if len(lines) > 1:
		address.address_line2 = lines[1]
	if len(lines) > 2:
		address.city = lines[2][:140]
	if len(lines) > 3:
		address.pincode = lines[3][:10]
	address.append(
		"links",
		{
			"link_doctype": "Employee",
			"link_name": employee_name,
			"link_title": employee_display_name or employee_name,
		},
	)
	address.flags.ignore_permissions = True
	address.insert(ignore_permissions=True)
	return address.name
