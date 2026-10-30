# Prerequisites & Installation

## Prerequisites

| Requirement | Notes |
|---|---|
| Frappe Framework | v16 (the app targets `>=16.0.0,<17.0.0`). |
| ERPNext | **Required.** ir depends on ERPNext accounting. |
| Frappe HR (HRMS) | **Required.** ir declares HRMS as a hard dependency (`required_apps`) - installing ir installs HRMS automatically if it isn't already on the site. There is no payroll-optional mode. |
| A site | A Frappe site on the bench where you will install the app. |

## Install the app

From the bench directory:

```bash
# 1. Fetch the app into the bench (use your repository URL/branch)
bench get-app ir <repo-url> --branch main

# 2. Install ir on the site - this also installs ERPNext and HRMS
#    automatically if either is not already installed
bench --site <site> install-app ir

# 3. Build assets and clear cache
bench build --app ir
bench --site <site> clear-cache
```

## What installation does automatically

Custom Fields, Property Setters, print formats, SARS Payroll Codes, ETI Slabs and other generic reference data are plain ir fixtures - they are synced automatically by `bench migrate`'s standard fixture mechanism, the same way any other ir fixture is, with no special install-time script involved:

- **Custom fields** are applied to Company, Customer, Item Group, Address, Employee, Salary Component, Payroll Settings, Salary Structure, Salary Slip, Salary Structure Assignment and more.
- **Property setters** adjust standard fields for the SA context.
- **Print formats** are installed: SA Sales Invoice, SA Full Tax Invoice, SA Abridged Tax Invoice, SA Credit Note, SA Debit Note, SA Quotation, SA Sales Order, SA Delivery Note, SA Purchase Invoice, SA Purchase Order, SA Payment Entry, SA Salary Slip, IRP5 Employee Certificate and IRP5-it3 Certificate.
- **SARS Payroll Codes** are seeded (income, deduction, employer-contribution codes used on IRP5).
- **Salary Components** with SA payroll treatment are seeded (PAYE, UIF Employee, UIF Employer, SDL, Severance Benefit, Leave Payout, Notice Pay, Tax on Lump Sum).
- **ETI Slab** records are seeded as fixtures.

Separately, genuinely company-scoped setup - which can't be a fixture since it varies per Company - runs as real code: creating a new South African Company automatically triggers chart-of-accounts augmentation, statutory tax configuration (Payroll Period, Income Tax Slab, Tax Rebates) and travel-allowance-rate seeding for that company.

**Workspaces and navigation:** the South African content (SA VAT, SA Payroll, SA Labour, SA COIDA workspaces, plus setup/master data under IR Setup) is reached through the single unified **Industrial Relations** sidebar - there is no separate "SA Localisation" app tile.

Install/migrate synchronizes app-owned schema and defaults. It may create or update configuration, so do not treat it as a harmless repair button. Back up database and files, rehearse on a restored staging site, review logs and local customizations, then run it in a controlled production maintenance window.

## Upgrading

To pick up a newer version on an existing site, first restore the production backup to staging and complete the documented acceptance matrix. In the controlled deployment window:

```bash
bench --site <site> migrate
bench build --app ir
bench --site <site> clear-cache
```

`migrate` synchronizes schema/configuration. Review migration output, Error Log, custom fields, statutory coverage, accounts, permissions and navigation afterwards; successful execution is not practitioner signoff.

## Next

Continue to [Post-Install Verification](post-install-verification).
