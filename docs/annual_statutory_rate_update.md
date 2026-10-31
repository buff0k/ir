# Annual Statutory Rate Update Runbook

This runbook describes how to roll `ir`'s South African statutory rate data forward to a new tax year. Most rates are data-driven, so a normal year requires editing JSON files (and one hardcoded file-list per data type) with no calculation-logic changes. This is the authoritative, detailed version referenced by the in-app practitioner guide's shorter [Annual Statutory Update](../ir/practitioner_guide/content/81_annual_statutory_update.md) page.

The SA tax year runs **1 March to the last day of February**. The "year of assessment" is the calendar year in which the tax year ends, e.g. the **2026-2027** tax year (1 March 2026 to 28 February 2027) has year of assessment **2027**, and its files are suffixed `_2027`.

## When to run

After National Treasury's annual Budget (usually late February) and once SARS publishes the new PAYE tables, rebates, thresholds and the updated Budget Tax Guide. Some figures are gazetted separately and on different dates (see "Watch list" below); confirm each before relying on it.

## Step 1 — Add the statutory rate pack (single source of truth for calculations)

The rate pack drives all date-effective **calculations**: PAYE, UIF, SDL, ETI amounts, medical credits, travel, subsistence, retirement, COIDA, lump-sum tax.

1. Copy the most recent pack in `ir/ir_setup/data/`, e.g. `statutory_rates_2027.json` → `statutory_rates_2028.json`.
2. Update the metadata block: `tax_year`, `year_of_assessment`, `effective_from`, `effective_to`, `source_reference`, and keep `is_active: 1`.
3. Update the values that changed (see the watch list). Leave structurally stable values as-is.
4. Recompute the PAYE `base_tax` (cumulative tax) for each bracket. For a bracket, `base_tax = base_tax_of_previous_bracket + (previous_bracket_width × previous_bracket_rate)`. The `amount_over` value equals the bracket's lower bound.

The loader (`ir.utils.statutory_rates`) globs `statutory_rates_*.json` in `ir_setup/data/` automatically and selects the pack whose `effective_from`/`effective_to` window contains the payroll date. No registration step is needed for this file.

## Step 2 — Add the supporting fixtures and register them

In the same `ir/ir_setup/data/` directory, add the matching files for the new year (copy the previous year's file and adjust):

- `tax_slabs_<YYYY>.json` — Income Tax Slab for the year (used by the Desk-reviewable tax slab).
- `tax_rebates_<YYYY>.json` — rebates and medical tax credits for the `Tax Rebates and Medical Tax Credit` Single.
- `payroll_period_<YYYY>.json` — the payroll period dates.
- `holiday_list_<YYYY>.json` — South African public holidays for the calendar year(s) the tax year spans. **Check for any once-off public holidays declared for that year** (e.g. election days).

Unlike the rate pack, these four are **not** auto-discovered — `ir/ir/ir_setup/install.py` reads them from four hardcoded tuples (`PAYROLL_PERIOD_FILES`, `INCOME_TAX_SLAB_FILES`, `TAX_REBATE_FILES`, `PUBLIC_HOLIDAY_FILES`). **Add the new filename to each relevant tuple**, or `ensure_company_tax_configuration`/`ensure_sa_public_holiday_lists` will silently skip the new year's file.

Travel allowance rates are company-scoped and are seeded from the rate pack (`ir.ir_setup.install.seed_statutory_rate_packs`) — no separate file needed for those. **ETI Slab is not derived from the rate pack** — it is `ir`'s own plain fixture (`ir/ir/fixtures/eti_slab.json`). Add the new year's ETI Slab record to that fixture directly and re-export (`bench export-fixtures --app ir`) or hand-edit the JSON; the rate pack's own `eti` block still feeds the ETI *amount calculation* (`calculate_eti_from_pack`), so both places need the new year's figures.

Treat the JSON pack and these four fixture files as the source-controlled source of truth; Desk records are review surfaces, not a separate place to invent rates.

## Step 3 — Clear the cache and verify

The rate pack loader (`ir.utils.statutory_rates._load_rate_packs`) is an in-process `functools.lru_cache`, not a Frappe/Redis cache — `bench clear-cache` does **not** clear it. It gets cleared automatically, in the process running the migration, via `ir`'s `after_migrate` hook (`ir.ir_setup.install.seed_statutory_rate_packs` → `clear_rate_pack_cache()`). Any *other* already-running gunicorn worker still holds the old cache until it restarts, so **restart the app's workers after every production migration that changes a rate pack** — don't rely on `bench clear-cache` alone. For interactive testing without a full migrate, call `ir.utils.statutory_rates.clear_rate_pack_cache()` directly from `bench console`/`bench execute` after changing a pack.

Run the compliance tests:

```bash
bench --site <site> run-tests --app ir --module ir.tests.test_statutory_compliance
```

Add or update date-parameterised tests asserting headline values, bracket boundaries, mid-year effective-date changes, the UIF cap, ETI bands, COIDA cap, official interest rate periods and JSON validity. Never let a test resolve against `today()` when it is intended to prove a fixed historic year.

## Step 4 — After deploying

Migration creates the new year's company-scoped Payroll Period/Income Tax Slab/Tax Rebates rows automatically via `ir`'s `after_migrate` hook (`ensure_all_company_tax_configuration`) — this never overwrites existing records, only fills in what's missing. The `ZA Local Setup` record's **Load Tax Slabs**/**Load Tax Rebates**/**Load Medical Tax Credits** checkboxes trigger the same thing on demand (e.g. for a company added outside a migrate window).

Update each employee's **Salary Structure Assignment** from 1 March to link the new year's **Income Tax Slab**, so PAYE uses the new brackets from the new tax year's first payroll run — this is a manual per-employee step, nothing automates it.

## Watch list — figures that change and must be confirmed each year

These are gazetted on varying dates and from different authorities. Do not assume they carried forward:

- **PAYE brackets, rebates, thresholds** — SARS Budget Tax Guide. (Note: brackets were *not* adjusted for 2024-2025 and 2025-2026.)
- **Medical scheme tax credits** — SARS.
- **ETI band amounts and thresholds** — gazetted via the Taxation Laws Amendment Act; the amounts increased from 1 April 2025. Confirm both the amounts and the effective month, and remember this needs both the rate pack *and* the `eti_slab.json` fixture updated (see Step 2).
- **UIF monthly remuneration cap** — Department of Employment & Labour (held at R17,712 since June 2021, but verify).
- **Prescribed reimbursive travel rate per km** — SARS notice.
- **Subsistence allowance daily amounts** (incidental-only; meals and incidentals) — SARS notice.
- **COIDA annual earnings cap** — Department of Employment & Labour notice (separate assessment-year cycle).
- **Retirement lump-sum / severance tax tables** — change infrequently (last reset 1 March 2023); confirm the exemption and brackets.

## Deployment control

Do not edit a production site first. Commit the pack and source references, run static/unit tests, restore a representative backup to staging, migrate there, run payroll and statutory E2E scenarios, and obtain practitioner signoff. Back up production before the controlled deployment, and restart workers immediately after migrating it (see Step 3). A successful migration proves technical execution only; it does not prove that the copied statutory values or interpretations are legally correct.

## Primary reference starting points

- [SARS Guide for Employers in respect of Employees' Tax (2027)](https://www.sars.gov.za/guide-for-employers-in-respect-of-employees-tax-2027/)
- [SARS Budget 2026 frequently asked questions](https://www.sars.gov.za/about/sars-tax-and-customs-system/budget/budget-2026-frequently-asked-questions/)
- [South African Government notices](https://www.gov.za/documents/notices) for separately gazetted COIDA and labour figures

Archive the exact publication/PDF/version used for signoff; a landing-page link alone is not sufficient audit evidence.

## Note on backfilled prior-year packs

`statutory_rates_2025.json` (2024-2025) and `statutory_rates_2026.json` (2025-2026) were backfilled so prior-year recalculations resolve. Their PAYE brackets, rebates, thresholds and medical credits are sourced from the repo's vetted prior-year data; the annually-gazetted figures listed in each file's `verification_notes.verify_before_use` block were carried forward and should be confirmed against the original SARS/DEL gazettes before being relied upon for historical recalculation.
