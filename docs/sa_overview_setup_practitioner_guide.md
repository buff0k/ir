# SA Setup Practitioner Guide

This guide explains how to configure South African localisation in `ir` before working in the VAT, Payroll, Labour, or COIDA modules.

## Purpose And Scope

South African localisation is reached through `ir`'s single unified **Industrial Relations** sidebar, not a separate landing workspace or app tile. This guide helps a practitioner or implementer confirm that the app is installed, South African defaults are loaded, each module's workspace is visible, and each statutory area has a clear next step.

Use this guide before configuring any individual module.

## Prerequisites

Before starting:

- ERPNext and HRMS are installed and the site is accessible through Desk (`ir` requires both — there is no payroll-optional install).
- At least one South African company exists.
- The company's chart of accounts has the accounts required for VAT, payroll liabilities, payroll expenses, and statutory clearing accounts.
- The current fiscal year and payroll period exist where payroll will be used.
- A System Manager performs installation, migration, ZA Local Setup and company VAT bootstrap. Operational users receive only the module roles and Company User Permissions needed for their work.

## Initial Setup Tutorial

1. Open Desk.
2. Search for `ZA Local Setup`.
3. Create or open the setup record for the company.
4. Select the South African company.
5. Tick the data sets you want to load for that company (see the checkbox list in the ZA Local Setup record — only the company-scoped options still trigger an action; the rest are generic reference data already applied as `ir` fixtures on every `bench migrate`).
6. Save the setup record, then click **Apply Selected Configuration**.
7. Open the **Industrial Relations** sidebar.
8. Confirm the module workspaces are visible:
   - IR Setup
   - SA VAT
   - SA Payroll
   - SA Labour
   - SA COIDA
9. Confirm the `Getting Started` onboarding card is visible where onboarding has not been completed.

## App-Wide Configuration Checks

### Company

Open the Company record and confirm:

- Company name and abbreviation are correct.
- Country is South Africa where applicable.
- Default currency is correct.
- VAT registration number is captured if the company is VAT registered.
- PAYE, UIF, SDL, and COIDA reference numbers are captured.
- Default receivable, payable, expense, liability, and payroll accounts are configured.

### Users And Roles

Confirm the right users have access:

- Accounts Managers can configure and submit VAT working papers; Accounts Users are review users unless separately granted broader ERPNext rights.
- Payroll and HR roles must be limited by company and job function; certificates, bank data and statutory references are sensitive personal/financial data.
- HR Users may prepare injury/claim records but approval/submission is reserved for the configured HR Manager/System Manager controls.
- System Managers alone should run setup, migration helpers, VAT bootstrap and practitioner-guide publishing.

### Workspaces

Open each workspace from the Industrial Relations sidebar:

- IR Setup
- SA VAT
- SA Payroll
- SA Labour
- SA COIDA

For each workspace, confirm:

- The sidebar opens and stays on the unified Industrial Relations nav (it does not switch to a separate app).
- The module onboarding card appears where applicable.
- Links open the intended DocType, Report, or Workspace.
- No module exposes unrelated country-specific reports.

### Print Formats

Open `Print Format` and confirm the expected South African formats are enabled:

- SA Sales Invoice
- SA Full Tax Invoice
- SA Abridged Tax Invoice
- SA Credit Note
- SA Purchase Invoice
- SA Debit Note
- SA Quotation
- SA Sales Order
- SA Delivery Note
- SA Purchase Order
- SA Payment Entry
- SA Salary Slip
- IRP5 Employee Certificate
- IRP5-it3 Certificate

## Desk Test Cases

### Test 1: Setup Record Opens And Saves

Steps:

1. Open `ZA Local Setup`.
2. Select a company.
3. Review the setup status.
4. Save the record.

Expected result:

- The record saves without error.
- Setup status remains a system-controlled status field.
- No unexpected script errors appear.

### Test 2: Workspaces Are Available

Steps:

1. Open the Industrial Relations sidebar.
2. Open each South African localisation workspace.

Expected result:

- IR Setup, SA VAT, SA Payroll, SA Labour, and SA COIDA are available.
- Each workspace contains relevant module links.

### Test 3: Module Onboarding Appears

Steps:

1. Open each module workspace.
2. Review the `Getting Started` card.
3. Click one onboarding step.

Expected result:

- The onboarding card appears.
- Steps follow the practitioner workflow: settings first, transactions next, reports last.
- Clicked steps route to the intended list, form, or report.

### Test 4: Custom Fields Are Visible

Steps:

1. Open Company.
2. Open Employee.
3. Open Salary Component.
4. Open Item.

Expected result:

- Company has South African statutory reference fields.
- Employee has South African identity, tax, Employment Equity, and IRP5 source fields.
- Salary Component has SARS payroll code fields.
- Item has VAT category fields used by SA VAT.

### Test 5: Print Formats Are Selectable

Steps:

1. Open a compatible document such as Sales Invoice, Purchase Invoice, Salary Slip, or IRP5 Certificate.
2. Open the print view.
3. Select the relevant South African print format.

Expected result:

- The format appears in the print format selector.
- The preview renders without template errors.
- South African fields show where the source document has values.

## Troubleshooting

- If a workspace is missing, inspect the migration log and app installation first. Back up and reproduce on staging before re-running migration in production.
- If onboarding or sidebar links are missing or wrong, check the `industrial_relations` Sidebar record under `ir`'s own `Industrial Relations` module — that single record is the source of the whole nav; there is no separate per-module sidebar to check.
- If print formats do not appear, confirm the Print Format records are enabled and linked to the correct DocType.
- If custom fields are missing, migration did not complete correctly; ZA Local Setup is not a substitute for schema synchronization.

## Practitioner Responsibility

The setup process creates a starting point. A green setup status means the background configuration job finished; it is not statutory signoff. Review its warnings, Error Log, created/updated records, accounts, rates, permissions and reports before live use.
