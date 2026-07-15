# Industrial Relations

A Frappe Framework application for managing industrial relations, employee relations, workplace discipline, incapacity, poor performance, employment records, training, employee changes, disputes, and related compliance processes in ERPNext and HRMS.

> **Current application series:** 16.x  
> **Current repository version at the time of this README:** 16.4.14  
> **Primary branch:** `main`

## Contents

- [Overview](#overview)
- [Major capabilities](#major-capabilities)
- [Process and outcome model](#process-and-outcome-model)
- [Requirements](#requirements)
- [Installation](#installation)
- [Upgrading an existing installation](#upgrading-an-existing-installation)
- [Getting started](#getting-started)
- [Roles and access](#roles-and-access)
- [Configuration](#configuration)
- [Scheduled processes and notifications](#scheduled-processes-and-notifications)
- [Employee integration](#employee-integration)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Project status](#project-status)
- [License](#license)

## Overview

Industrial Relations extends Frappe, ERPNext, and HRMS with connected processes for:

- disciplinary action;
- incapacity proceedings;
- poor-performance management;
- contracts of employment;
- warnings and formal outcomes;
- hearings, appeals, cancellations, suspensions, demotions, deductions, reductions, dismissals, and voluntary separation;
- external disputes;
- employee induction and training;
- trade-union and shop-steward information;
- employee status changes, transfers, and termination;
- anonymous workplace reports;
- employee records, audit information, and linked-document navigation;
- site organograms and shift planning;
- scheduled compliance and outstanding-item notifications.

The application is designed around the HRMS `Employee` record. Related industrial-relations documents are linked back to the employee and, where applicable, to the originating IR intervention.

## Major capabilities

### Disciplinary management

The disciplinary process begins with **Disciplinary Action** and can produce linked documents such as:

- NTA Enquiry;
- Written Outcome;
- Warning Form;
- No Further Action Form;
- Suspension Form;
- Demotion Form;
- Pay Deduction Form;
- Pay Reduction Form;
- Dismissal Form;
- Voluntary Seperation Agreement;
- Hearing Cancellation Form;
- Appeal Against Outcome.

Disciplinary history distinguishes between adverse tracked outcomes and non-adverse or unresolved matters. Pending, cancelled, and not-guilty matters remain visible for audit and context without being treated as previous disciplinary sanctions.

### Incapacity management

**Incapacity Proceedings** supports incapacity-specific enquiries and outcomes, including:

- NTA Enquiry;
- Written Outcome;
- No Further Action Form;
- suspension;
- demotion;
- pay reduction;
- dismissal;
- voluntary separation;
- cancellation;
- appeal.

A Warning Form is not an incapacity outcome.

### Poor-performance management

**Poor Performance** is managed separately from disciplinary action and supports its own history and outcome flow, including:

- NTA Enquiry;
- Written Outcome;
- Warning Form;
- No Further Action Form / performance improved;
- suspension;
- demotion;
- pay deduction;
- pay reduction;
- dismissal;
- voluntary separation;
- cancellation;
- appeal.

### Employment and employee administration

The application includes or extends processes for:

- Contract of Employment;
- Termination Form;
- Status Change Form;
- Site Transfer Form;
- employee audit information;
- trade-union membership;
- employee-linked record navigation;
- employee termination synchronisation.

### Training and induction

Training functionality includes:

- Employee Induction Tracking;
- Employee Induction Record;
- training matrices;
- induction expiry monitoring;
- branch-specific and global trainer notification recipients.

### Other functional areas

Additional features include:

- external dispute management;
- anonymous workplace reporting;
- trade unions and union shop stewards;
- KPI review integration;
- site organograms;
- shift planning;
- leave-form and attendance integration;
- recurring compliance and outstanding-item notifications.

## Process and outcome model

Several outcome-producing DocTypes use a consolidated intervention relationship:

| Field | Purpose |
|---|---|
| `ir_intervention` | The source intervention DocType, such as `Disciplinary Action` or `Poor Performance` |
| `linked_intervention` | Dynamic Link to the source intervention record |
| `linked_intervention_processed` | Internal processing flag where required |

This model is used by consolidated documents such as NTA Enquiry, Written Outcome, No Further Action Form, and Warning Form where applicable.

### Outcome classification

Not every completed process is an adverse history item.

| Classification | Behaviour |
|---|---|
| Tracked adverse outcome | Included in the relevant previous-outcome/history table |
| Pending | Shown as unresolved information; not treated as previous adverse history |
| Cancelled | Shown for audit; not treated as previous adverse history |
| Not Guilty / No Further Action | Shown for audit and context; not treated as previous adverse history |
| Performance Improved | Non-adverse resolution; should not be treated as negative performance history |
| Not Incapacitated | Non-adverse resolution; should not be treated as an adverse incapacity outcome |

Implementations and custom outcome records should preserve this distinction.

## Requirements

The current 16.x series requires:

- Python 3.14 or later;
- Frappe Framework 16.x;
- ERPNext 16.x;
- HRMS 16.x;
- `za_local` / Cohenix Local ZA;
- MariaDB or another database supported by the installed Frappe version;
- a working Frappe Bench;
- at least one Company;
- at least one Branch;
- at least one Employee.

The application declares Frappe, ERPNext, and HRMS 16.x compatibility. Keep all three applications on mutually compatible version-16 revisions.

### Required application repositories

- Frappe: `https://github.com/frappe/frappe`
- ERPNext: `https://github.com/frappe/erpnext`
- HRMS: `https://github.com/frappe/hrms`
- Local ZA: `https://github.com/EPIUSECX/cohenix_local_za`
- Industrial Relations: `https://github.com/buff0k/ir`

## Installation

The commands below assume that Frappe, ERPNext, HRMS, and Local ZA are already present in the bench.

From the bench directory:

```bash
bench get-app https://github.com/buff0k/ir
bench --site your.site.name install-app ir
bench --site your.site.name migrate
bench build --app ir
bench restart
```

Replace `your.site.name` with the actual site name.

Confirm installation:

```bash
bench --site your.site.name list-apps
bench version
```

`ir` should appear in the installed-app list.

### Installing Local ZA when it is not already present

```bash
bench get-app https://github.com/EPIUSECX/cohenix_local_za
bench --site your.site.name install-app za_local
bench --site your.site.name migrate
```

Use the application name reported by that repository if it differs on the branch being installed.

## Upgrading an existing installation

Always create a current backup before upgrading:

```bash
bench --site your.site.name backup --with-files
```

Then update and migrate:

```bash
cd apps/ir
git pull
cd ../..

bench --site your.site.name migrate
bench build --app ir
bench --site your.site.name clear-cache
bench --site your.site.name clear-website-cache
bench restart
```

### Migration notes

The application includes historical patches that migrate retired fields and DocTypes into newer consolidated models.

Important points:

- do not run `bench trim-tables` before the relevant migration patches have completed;
- Frappe normally retains removed physical columns until tables are trimmed;
- post-model-sync patches use those retained columns to migrate legacy values;
- test upgrades in a lab or staging site before production;
- review the migration log and Error Log after each significant upgrade.

Useful commands:

```bash
bench --site your.site.name migrate
bench --site your.site.name doctor
bench --site your.site.name console
```

To inspect application patch records from the console:

```python
frappe.get_all(
    "Patch Log",
    filters={"patch": ["like", "ir.patches.%"]},
    fields=["patch", "creation"],
    order_by="creation desc",
)
```

## Getting started

### 1. Complete the ERPNext and HRMS foundation

Before using the IR workflows, configure:

- Company;
- Branch;
- Departments;
- Designations;
- Employees;
- users and role assignments;
- letterheads;
- Holiday Lists where required by HRMS processes.

Employee, Company, Branch, Designation, and letterhead information is reused throughout the application.

### 2. Assign Industrial Relations roles

Assign the appropriate roles to users:

- **IR Manager**
- **IR Officer**
- **IR User**

Additional functional roles include:

- **Training Manager**
- **Training Administrator**
- **Training Facilitator**
- **Anonymous Report Investigator**

Role permissions and designation restrictions determine which records a user may create, view, update, submit, or report on.

### 3. Configure IR Role Restrictions

Open **IR Role Restrictions** and configure:

- restricted designations for IR Manager, IR Officer, and IR User where required;
- report recipients;
- HR recipients by branch;
- trainers by branch;
- global trainers.

Restrictions are enforced in list queries, direct document access, and validation for supported intervention DocTypes.

### 4. Review master data and fixtures

Review and adapt the supplied master data:

- Employee Rights;
- Offence Outcome;
- Type of Incapacity;
- Grounds for Appeal;
- Contract Type and Contract Section;
- Dispute Resolution Forum;
- External Dispute Resolution Process;
- External Dispute Resolution Outcome;
- Reason for Termination.

Fixtures provide a starting point and should be reviewed against the organisation's policies and legal requirements.

### 5. Configure the disciplinary code

Set up the organisation's:

- offences;
- offence categories;
- charge wording;
- available sanctions and outcomes;
- warning validity periods;
- outcome classifications.

The wording and sanctions must align with the organisation's disciplinary code and applicable law.

### 6. Configure employee rights

Review **Employee Rights** records used by forms such as:

- Disciplinary Hearing;
- Warning Form;
- Suspension;
- Demotion;
- Pay Deduction;
- Pay Reduction;
- Dismissal;
- Incapacity;
- Poor Performance.

These records populate the rights shown to employees in generated forms and print formats.

### 7. Configure notifications

Set recipients in IR Role Restrictions and any applicable settings DocTypes.

Then verify:

```bash
bench --site your.site.name enable-scheduler
bench --site your.site.name doctor
```

Use **Scheduled Job Type**, **RQ Job**, **Scheduler Log**, and **Error Log** to monitor execution.

### 8. Test a complete process

Before production use, test at least one full process in a lab:

1. create a Disciplinary Action or Poor Performance record;
2. create an NTA Enquiry;
3. create and submit a Written Outcome or other applicable outcome;
4. verify linked-document cards;
5. verify employee history;
6. verify non-adverse outcomes are not included as adverse history;
7. verify print formats;
8. verify notifications and permissions;
9. verify the Employee dashboard links.

## Roles and access

### IR Manager

Intended for senior Industrial Relations users. Typically has the broadest operational access, including management of restrictions and sensitive processes.

### IR Officer

Intended for Industrial Relations practitioners who create and manage cases within the permitted scope.

### IR User

Intended for restricted or read-oriented access, often subject to ownership and designation restrictions.

### Training roles

Training roles separate management, administration, and facilitation responsibilities.

### Permission restrictions

The application applies custom permission logic to supported DocTypes including:

- Contract of Employment;
- Disciplinary Action;
- Incapacity Proceedings;
- Poor Performance;
- NTA Enquiry;
- Written Outcome.

The highest applicable IR role is used when a user has more than one IR role.

## Configuration

### Offence Outcome

Offence Outcome records drive outcome names, display values, warning behaviour, and validity periods.

Keep stable outcome codes where existing logic or historical data depends on them.

Common supplied codes include outcomes representing:

- not guilty;
- performance improved;
- cancelled;
- voluntary separation;
- suspension;
- demotion;
- pay deduction;
- dismissal;
- warnings;
- fitness or incapacity-related results.

Review each record before production use.

### Letterheads and print formats

Configure the default letterhead on each Company.

Review all supplied print formats to ensure:

- organisation names and policy wording are correct;
- signature blocks provide sufficient writing space;
- conditional sections use the current consolidated intervention fields;
- empty history sections are hidden;
- page numbering renders correctly in the selected PDF engine.

### Employee dashboard links

The application adds and reconciles Industrial Relations links on the HRMS Employee DocType after migration.

The setup routine:

- adds required current links;
- removes known retired IR links;
- removes invalid IR links whose DocType or field no longer exists;
- avoids changing dashboard links belonging to other applications.

### Employee and designation fields

The application supplies custom fields and property setters for Employee, Designation, Leave Application, Employee Checkin, and Job Requisition.

Review custom-field conflicts when installing alongside other localisation or HR applications.

## Scheduled processes and notifications

The application registers recurring jobs for:

### Weekly

- fixed-term contract expiry;
- lapsed fixed-term contracts;
- outstanding disciplinary actions;
- outstanding incapacity proceedings;
- outstanding poor-performance matters;
- outstanding external disputes;
- retirement-age notifications;
- lapsed retirement notifications;
- expiring induction notifications;
- expired induction notifications;
- outstanding leave applications;
- outstanding employee change forms.

### Daily

- attendance synchronisation;
- employee termination synchronisation.

Schedulers must be enabled and workers must be running.

Check:

```bash
bench --site your.site.name doctor
bench doctor
```

## Employee integration

Industrial Relations extends the Employee DocType with:

- trade-union information;
- audit information;
- IR-related records;
- linked-document dashboard entries.

The Employee record acts as the central reference for employment, disciplinary, incapacity, poor-performance, training, transfer, status-change, and termination records.

Where the Employee dashboard fails to load open-count or timeline information, verify that Frappe, ERPNext, HRMS, and built assets are on compatible revisions and that all Python workers have been restarted.

## Development

### Clone for development

```bash
bench get-app https://github.com/buff0k/ir
bench --site development.localhost install-app ir
bench --site development.localhost set-config developer_mode 1
bench --site development.localhost migrate
bench build --app ir
```

### Application structure

```text
ir/
├── controllers/              Scheduled jobs, notifications, and process controllers
├── fixtures/                 Exported roles, master data, permissions, fields, and settings
├── industrial_relations/     DocTypes, reports, pages, workspaces, and print formats
├── overrides/                Frappe or HRMS event overrides
├── patches/                  Data and schema migration patches
├── setup/                    Post-migration setup and reconciliation
├── hooks.py                  Application hooks, fixtures, events, permissions, and scheduler jobs
└── patches.txt               Ordered migration patch registry
```

### Adding schema changes

Use standard Frappe DocType changes and export the model JSON.

For data migration:

1. create a small, idempotent patch;
2. register it in `patches.txt`;
3. place it under `[post_model_sync]` when it depends on the new model;
4. guard for absent historical DocTypes and columns;
5. do not swallow genuine migration failures;
6. avoid explicit commits inside patches;
7. test old, partially upgraded, and fresh installation states.

### Fixtures

After changing fixture-managed records:

```bash
bench --site development.localhost export-fixtures
```

Review the generated diff before committing.

### Testing

At minimum, test:

- fresh installation;
- upgrade from a site containing legacy fields;
- partially upgraded site;
- role and designation restrictions;
- direct URL access;
- list-query restrictions;
- complete disciplinary, incapacity, and poor-performance flows;
- adverse versus non-adverse history;
- linked-document renderers;
- print formats and PDF generation;
- scheduler jobs;
- Employee dashboard links.

## Troubleshooting

### `bench migrate` fails on a historical patch

Check the traceback and confirm:

- the latest patch file is deployed;
- the patch is registered under the correct section;
- the new model has synced;
- legacy source columns have not been trimmed;
- the site has the expected dependent applications.

Do not manually insert a Patch Log record merely to bypass a failure unless the data migration has been independently verified.

### A linked-document panel logs missing DocTypes

Search the relevant parent controller's `_linked_doc_mappings()` function for retired DocTypes or fields.

Dictionary mappings are used for consolidated intervention documents:

```python
{
    "ir_intervention": "Disciplinary Action",
    "linked_intervention": None,
}
```

The renderer must detect dictionary mappings before constructing filters.

### Employee timeline endpoint returns 404

Verify the HRMS source and assets are aligned:

```bash
grep -n "def get_timeline_data" apps/hrms/hrms/overrides/employee_master.py
bench version
bench --site your.site.name list-apps
bench build --app hrms
bench restart
```

### JavaScript changes do not appear

```bash
bench build --app ir
bench --site your.site.name clear-cache
bench --site your.site.name clear-website-cache
bench restart
```

Then perform a hard refresh in the browser.

### Scheduler jobs do not run

```bash
bench --site your.site.name enable-scheduler
bench --site your.site.name doctor
bench doctor
```

Inspect Scheduler Log, RQ Job, and Error Log.

### Permission results appear inconsistent

Confirm:

- the user's assigned IR roles;
- designation restrictions in IR Role Restrictions;
- document employee/designation fields;
- whether the document was created before restriction changes;
- direct-access and list-query behaviour separately.

## Project status

This repository is under active development.

The core disciplinary, incapacity, poor-performance, employment-contract, training, dispute, employee-change, organogram, and notification functionality is implemented, but production deployment still requires:

- organisation-specific master-data review;
- policy and legal review;
- role and permission testing;
- print-format review;
- staging migration testing;
- scheduler and email configuration;
- user acceptance testing.

Contributions, issue reports, and tested improvements are welcome.

## Security and legal notice

This application handles sensitive employee and labour-relations information.

Deployers are responsible for:

- access control;
- retention and deletion policies;
- backups;
- audit review;
- privacy and data-protection compliance;
- validation against applicable labour law and organisational policies.

The supplied workflows, templates, outcomes, and wording are technical starting points and are not legal advice.

## License

MIT
