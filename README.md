## Industrial Relations

An Industrial Relations Management App built on the Frappe Framework.


### Requirements:

1. [Frappe Framework](https://github.com/frappe/frappe) Installed and Running a Bench serving a site;
2. [ERPNext](https://github.com/frappe/erpnext) Installed on your Bench Instance;
3. [HRMS](https://github.com/frappe/hrms) Installed on your Bench Instance;
4. Having set up at least one Company in ERPNext;
5. Having set up at least one Branch in HRMS; and
6. Having set up at least one Employee in HRMS.


### How to Install

Log into your server as your frappe-bench user and cd to your frappe-bench folder

````
bench get-app https://github.com/buff0k/ir
````

````
bench --site your.site install-app ir
````


### What is Working

So far I haven't gotten to everything yet, but you can capture your discipllinary code schedule of offences, create a disciplinary action and a warning. There is still a lot to do and if you would like to get interrested, please contact me directly.

Onboarding Walkthrough

Disciplinary Action Workflow and DocTypes (Production Testing)

Trade Union Members (Functionally Complete)

Disciplinary Schedule of Offences (Functionally Complete)
   
### Currently Working On

Production Testing and Optimization of Disciplinary Action workflows

Grievance Procedure

Appeals Procedure

Desertion\Absconsion Procedure

Dispute Forum (CCMA, Labour Court, etc.) Procedure

Dashboard Chart (To display all disciplinary outcomes rendered in the last 3 month period by colour)

Disciplinary Code Report (A formatted report to use as a Schedule of Offences)


#### License

mit
