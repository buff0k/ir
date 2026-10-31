# South African Localisation Practitioner Guide

This guide is the starting point for payroll, VAT, accounting, HR, labour, and compliance practitioners who need to configure and validate South African localisation in `ir` (Industrial Relations), on top of ERPNext and HRMS.

The documentation is written for Desk users. It focuses on configuration, operational workflow, practical validation, and review evidence. Developer commands are intentionally kept out of the practitioner flow unless they are needed in the project README.

## How To Use This Guide

1. Start with the setup guide.
2. Configure one module at a time.
3. Complete the Desk test cases for the module before using it for live statutory work.
4. Keep screenshots or exported reports as review evidence.
5. Ask a qualified practitioner to validate statutory rates, calculations, and final submissions before filing.

Recommended reading order:

1. [SA Setup Practitioner Guide](sa_overview_setup_practitioner_guide.md)
2. [SA VAT Configuration and Testing](sa_vat_configuration_and_testing.md)
3. [SA Payroll Configuration and Testing](sa_payroll_configuration_and_testing.md)
4. [SA Labour Configuration and Testing](sa_labour_configuration_and_testing.md)
5. [SA COIDA Configuration and Testing](sa_coida_configuration_and_testing.md)

## Module Map

South African localisation lives in five of `ir`'s modules, each reachable from the single unified **Industrial Relations** sidebar (there is no separate app or app tile to switch into):

| Module | Workspace | Main Purpose |
| --- | --- | --- |
| ir_setup | IR Setup | Installation, the ZA Local Setup wizard, master/reference data, custom fields |
| ir_vat | SA VAT | VAT settings, VAT201 working papers, tax-invoice readiness, and VAT reports |
| ir_payroll | SA Payroll | PAYE, UIF, SDL, ETI, Salary Slip calculations, EMP201, EMP501, IRP5 / IT3(a), and payroll reports |
| ir_labour | SA Labour | SETA, bargaining council, sectoral wage references, business trips, WSP, ATR, skills records, and Employment Equity reports |
| ir_coida | SA COIDA | COIDA settings, industry rates, annual return working papers, workplace injuries, and OID claims |

`ir` requires both ERPNext and HRMS — there is no payroll-optional install. Every South African company configured through `ir` has the full set of VAT, payroll, labour and COIDA features available.

## Minimum Implementation Sequence

Use this sequence for a new South African company:

1. Confirm ERPNext company details, chart of accounts, fiscal year, currencies, and users.
2. Run `ZA Local Setup` for the company (from the IR Setup workspace).
3. Complete the setup checks in the SA Setup Practitioner Guide.
4. Configure SA VAT for the company and test VAT invoices before live VAT201 use.
5. Configure SA Payroll.
6. Configure SA Labour reference data before using WSP, ATR, business trips, or Employment Equity reports.
7. Configure SA COIDA before preparing the annual return or recording workplace injuries.
8. Run each module's Desk test cases.
9. Save test evidence and practitioner sign-off before using the app for production submissions.

## Validation Standard

A module should be considered ready only when:

- Required settings and master data have been reviewed.
- At least one positive test case has passed.
- At least one exception or review-control test case has passed.
- Reports agree with the source documents they are based on.
- Print formats render with the required South African details where applicable.
- The practitioner understands which activities remain manual filing or external portal work.

## App-Wide Compliance Boundary

`ir`'s South African localisation provides configuration, calculation support, working papers, reports, print formats, and workflow guidance. It does not replace professional statutory review.

VAT201, EMP201, EMP501 and IRP5/IT3(a) records are internal working papers. The app does not generate a SARS BRS payroll-import file or submit to SARS/eCOID. Payroll EFT is enabled only for FNB Online Banking Enterprise CSV through a submitted Payroll Payment Batch. Generic exports must not be described as authority- or bank-approved files.

This South African localisation content originated in the standalone `za_local` app ("SA Localisation", published by Cohenix) and has since been absorbed into `ir`. Cohenix, EPI-USE, `ir`'s maintainers, contributors, and implementers do not accept responsibility for incorrect calculations, incorrect setup, incorrect statutory interpretation, or missed submissions. The employer, payroll practitioner, tax practitioner, and appointed reviewers remain responsible for validating all calculations, statutory rates, return values, exports, and filings before submission to SARS, the Compensation Fund, SETAs, the Department of Employment and Labour, or any other authority.
