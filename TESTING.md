# Testing Guide for ir

`ir` (Industrial Relations, including the absorbed South African localisation content) combines Frappe server tests, static/repository checks, and staged manual payroll and statutory scenarios. Passing tests is necessary engineering evidence; it is not tax, payroll, banking, SARS, Compensation Fund, or legal signoff.

## Supported test baseline

- Frappe Framework, ERPNext and Frappe HR/HRMS v16 (HRMS is a hard dependency - `ir` cannot be installed without it)
- Python 3.10 or later (the current CI job uses the version declared in its workflow)
- MariaDB and Redis services required by the bench
- A dedicated test site with the same app versions as the target deployment

Never run tests or E2E staging against a production site. Take a database/files backup before migration or destructive acceptance testing.

## Static checks

From the app directory:

```bash
ruff check .
git diff --check
```

## Server tests

Run the complete suite on a dedicated site:

```bash
bench --site <site> run-tests --app ir --lightmode
```

`za_local` still owns a small amount of South African content pending full retirement (see its own module docstrings for what's left) - its own remaining suite should also stay green:

```bash
bench --site <site> run-tests --app za_local --lightmode
```

Run a focused module while developing:

```bash
bench --site <site> run-tests --app ir --module ir.tests.test_statutory_compliance --lightmode
```

The suite covers statutory calculations, document-controller behavior, permission gates, scheduler registration, setup/fixture integrity, repository hygiene, and selected workflow regressions. Tests that use mocks are not a substitute for the staged lifecycle scenarios below.

## Manual acceptance matrix

### Migration and setup

1. Restore a recent production backup to staging.
2. Record app versions and current customizations.
3. Run `bench --site <staging> migrate`, build assets, clear cache, and **restart the app's workers** in a maintenance window (the statutory rate-pack loader is an in-process cache that `bench clear-cache` alone does not clear - see `docs/annual_statutory_rate_update.md`).
4. Review migration output and Error Log; verify custom fields, workspaces, statutory rate coverage and company-specific settings.
5. Run `ZA Local Setup` as System Manager only for deliberately selected data sets. Review warnings and the records created or updated.
6. Repeat the migration on the same staging snapshot to check idempotency before approving production deployment.

### Payroll

Verify ordinary monthly, timesheet/hourly, additional salary, recurring additional salary, retirement contribution, medical scheme credit, ETI, fringe benefit, leave/termination, loan repayment and back-dated scenarios. Reconcile Salary Slips, Payroll Entry, GL, Payroll Payable, EMP201, certificates and EMP501 working papers.

### Payments

Generate an FNB Online Banking Enterprise CSV only from a submitted Payroll Payment Batch. Confirm role access, private-file storage, source hash, employee bank details, control total and a low-value bank acceptance upload. ABSA, Nedbank and Standard Bank formats are not supported.

### VAT and sales

Test standard, zero-rated, exempt, mixed-rate, credit-note, debit-note, capital and import scenarios. Reconcile posted tax rows to VAT reports, GL and the VAT201 working paper. Verify the no-invoice/abridged/full-invoice thresholds on a ZAR basis and inspect every issued print format.

### COIDA and labour

Test the exact 1 March-to-February COIDA year, component classification, per-employee cap, company/class industry rate, injury-to-claim workflow, medical reports and role restrictions. Validate Employment Equity, WSP/ATR and labour outputs against source records and current external requirements.

### External filing and statutory review

`ir` does not generate a SARS BRS payroll-import file or submit VAT201, EMP201, EMP501, IRP5/IT3(a), COIDA, WSP/ATR or Employment Equity returns to external authorities. Validate and capture working-paper figures through the approved external channel. Retain submission receipts and payment confirmations outside the app record as required by the employer's control framework.

### Disciplinary/IR workflow lifecycle

Not South African-specific, but exercised by the same acceptance pass: verify a Main Action (Disciplinary Action, Incapacity Proceedings, Poor Performance) cannot be submitted without a recorded Outcome and Outcome Date (`ir.industrial_relations.utils.require_outcome_before_submit`); that recording an outcome via a Warning/Dismissal/Pay Deduction/Pay Reduction Form against a still-draft Main Action, then submitting the Main Action, is the supported order of operations; and that cancelling an outcome form correctly clears and reinstates the source record.

## Disposable-site E2E staging

There is currently no automated multi-stage E2E data harness (a prior one, `za_local.tests.e2e_data`, existed but had zero real callers and was retired along with the rest of that app's dead code). Staged, disposable-site E2E verification for a release currently means manually working through the **Manual acceptance matrix** above on a disposable site restored from a known snapshot - not running a scripted stage sequence. If an automated harness is rebuilt, it belongs here.

## Release evidence

Retain:

- commit and app-version identifiers;
- backup/restore evidence and migration logs;
- static and server-test output;
- E2E scenario results and reconciliations;
- practitioner-approved statutory source references;
- sample print/PDF review evidence;
- bank acceptance evidence for FNB OBE CSV;
- role/permission test results; and
- documented unresolved limitations and go-live decision.

Re-run the relevant checks after changes to hooks, controllers, setup/migration, custom fields, permissions, statutory rate packs, reports, print formats, bank exports or seed data.
