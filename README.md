## Industrial Relations

An Industrial Relations Management App built on the Frappe Framework.


### Requirements:

1. [Frappe Framework](https://github.com/frappe/frappe) Installed and Running a Bench serving a site;
2. [ERPNext](https://github.com/frappe/erpnext) Installed on your Bench Instance;
3. [HRMS](https://github.com/frappe/hrms) Installed on your Bench Instance;
4. [za_local](https://github.com/ePIUSECX/cohenix_local_za/) Installed on your Bench Instance;
5. Having set up at least one Company in ERPNext;
6. Having set up at least one Branch in HRMS; and
7. Having set up at least one Employee in HRMS.


### How to Install

Log into your server as your frappe-bench user and cd to your frappe-bench folder

````
bench get-app https://github.com/buff0k/ir
````

For latest Development Branch:

````
bench --site your.site install-app ir
````
For current Production Branch:

````
bench --site your.site install-app ir
````

### What is Working

There is still a lot to do and if you would like to get interrested, please contact me directly.

Disciplinary Action Workflow and DocTypes (Functionally Complete)

Trade Union Members (Functionally Complete)

Disciplinary Schedule of Offences (Functionally Complete)

Contract of Employment Workflow and DocTypes (Functionally Complete)

Incapacity Proceedings Workflow and DocTypes (Functionally Complete)

External Dispute Management (Functionally Complete)

Internal Training Tracking (Functionally Complete)

Anomymous Whistleblowing Reports (Functionally Complete - For Use on Public Website)

KPI Tracking (Functionally Complete)
   
### Currently Working On

Grievance Procedure

Appeals Procedure

Desertion\Absconsion Procedure

Disciplinary Code Report (A formatted report to use as a Schedule of Offences) - Functional but not pretty

Importing of Clocking from Biometric Sources

Continued integration with [za_local application by Cohenix](https://github.com/ePIUSECX/cohenix_local_za/).

### Sample Templates Included (As Fixtures)

Basic Contracts of Employment (Period Based Fixed Term, Project Based Fixed Term, Indefinite)

Usual External Dispute Resolution Fora

#### License

mit
