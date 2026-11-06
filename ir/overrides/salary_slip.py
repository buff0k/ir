"""
South African Salary Slip Override

This module extends the standard HRMS Salary Slip functionality to support
South African payroll requirements including PAYE, UIF, SDL, COIDA, and ETI.

ir requires HRMS (required_apps in hooks.py), so it is always installed here.
"""

from math import ceil

import frappe
from frappe import _
from frappe.utils import flt, getdate
from hrms.payroll.doctype.payroll_period.payroll_period import get_period_factor
from hrms.payroll.doctype.salary_slip.salary_slip import (
    SalarySlip,
    calculate_tax_by_tax_slab,
    get_salary_component_data,
)

from ir.utils.eti_utils import (
    calculate_eti_amount,
    cancel_eti_log,
    check_eti_eligibility,
    log_eti_calculation,
    submit_eti_log,
)
from ir.utils.payroll_utils import (
    get_additional_salaries,
    get_current_block_period,
    get_employee_frequency_map,
    is_payroll_processed,
)
from ir.utils.statutory_rates import (
    get_default_travel_paye_inclusion_percentage,
    get_retirement_annual_cap,
    get_retirement_deduction_percentage,
    get_sdl_rate,
)
from ir.utils.tax_utils import (
    calculate_sdl_contribution,
    calculate_uif_contribution,
    get_medical_aid_credit,
    get_tax_rebate,
)

RETIREMENT_FUND_DEDUCTION_CODES = {"4001", "4003", "4006"}
UIF_CODES = {"4141"}
SDL_CODES = {"4142"}
PAYE_CODES = {"4102", "4115"}


class ZASalarySlip(SalarySlip):
    """
    South African Salary Slip implementation.

    Extends the standard Salary Slip with:
    - SA tax calculations (PAYE with rebates and medical credits)
    - Employment Tax Incentive (ETI)
    - UIF, SDL, and COIDA contributions
    - Annual bonus handling
    - Company contributions
    """

    def validate(self):
        if self.is_new() and not flt(self.get("za_eti_hours")) and self.employee:
            self.za_eti_hours = flt(
                frappe.get_cached_value("Employee", self.employee, "za_hours_per_month")
            )
        super().validate()
        self.validate_payroll_frequency()

    def apply_sa_component_classification_defaults(self):
        """Apply retirement classification after deduction rows have been built."""
        for deduction in self.get("deductions") or []:
            if self.is_retirement_fund_component(deduction.salary_component):
                deduction.exempted_from_income_tax = 1

    def add_tax_components(self):
        """Classify populated deduction rows immediately before HRMS calculates PAYE."""
        self.apply_sa_component_classification_defaults()
        return super().add_tax_components()

    def before_submit(self):
        # Parent class (SalarySlip) has no before_submit, so there's no super() to call.
        self.validate_component_accounts()

    def after_insert(self):
        """Persist ETI audit evidence only after the Salary Slip link exists."""
        self._log_current_eti_calculation()

    def validate_payroll_frequency(self):
        try:
            frequency = get_current_block_period(self)
            employee_frequency = get_employee_frequency_map()

            if self.employee in employee_frequency:
                if is_payroll_processed(self.employee, frequency[employee_frequency[self.employee]]):
                    frappe.throw(
                        _("Salary Slip already created for current {0}").format(
                            employee_frequency[self.employee]
                        )
                    )
        except Exception as e:
            # This check is best-effort: a failure here must not block slip creation.
            frappe.log_error(
                f"Error validating payroll frequency for employee {self.employee}: {e!s}",
                "Salary Slip Frequency Validation",
            )

    def validate_component_accounts(self):
        """All salary components need GL accounts for SA payroll compliance."""
        components_missing_accounts = []

        for component_type in ["earnings", "deductions"]:
            for row in self.get(component_type):
                if not frappe.db.exists(
                    "Salary Component Account", {"parent": row.salary_component, "company": self.company}
                ):
                    components_missing_accounts.append(row.salary_component)

        if components_missing_accounts:
            unique_components = []
            seen = set()
            for comp in components_missing_accounts:
                if comp not in seen:
                    unique_components.append(comp)
                    seen.add(comp)

            if len(unique_components) == 1:
                error_msg = _(
                    "Salary Component <a href='/app/salary-component/{0}'>{0}</a> is missing an account configuration. "
                    "Please set an account for this component in the Salary Component Account section for company {1}. "
                    "Accounts are required for SA payroll compliance."
                ).format(unique_components[0], self.company)
            else:
                component_links = ", ".join(
                    [f"<a href='/app/salary-component/{comp}'>{comp}</a>" for comp in unique_components]
                )
                error_msg = _(
                    "The following Salary Components are missing account configurations: {0}. "
                    "Please set accounts for these components in their respective Salary Component Account sections for company {1}. "
                    "All components must have associated accounts for SA payroll compliance."
                ).format(component_links, self.company)

            frappe.throw(error_msg, title=_("Missing Salary Component Accounts"))

    def compute_taxable_earnings_for_year(self):
        super().compute_taxable_earnings_for_year()

        self.apply_sa_paye_inclusion_adjustments()

        self.annual_bonus = self.get_annual_bonus()
        self.total_taxable_earnings += self.annual_bonus

        self.apply_retirement_fund_deduction_cap()

        self.total_taxable_earnings_without_full_tax_addl_components = self.total_taxable_earnings - getattr(
            self, "current_additional_earnings_with_full_tax", 0
        )

    def apply_retirement_fund_deduction_cap(self):
        """Add back retirement fund deductions above the SARS annual cap.

        HRMS reduces taxable earnings by deduction rows marked
        ``exempted_from_income_tax``. For South Africa, pension/provident/RA
        deductions must still be capped to the lower of actual contributions,
        27.5% of remuneration/taxable base, and the annual statutory cap.
        """
        if not getattr(self, "tax_slab", None) or not self.tax_slab.allow_tax_exemption:
            return

        annual_contribution = self.get_annual_retirement_fund_contribution()
        if annual_contribution <= 0:
            return

        base_before_retirement_deduction = flt(self.total_taxable_earnings) + annual_contribution
        max_by_percentage = base_before_retirement_deduction * get_retirement_deduction_percentage(
            self.end_date
        )
        allowed_deduction = min(
            annual_contribution, max_by_percentage, get_retirement_annual_cap(self.end_date)
        )
        disallowed_deduction = max(0, annual_contribution - allowed_deduction)

        if disallowed_deduction:
            self.total_taxable_earnings += disallowed_deduction
            self.za_retirement_fund_taxable_excess = disallowed_deduction

    def get_annual_retirement_fund_contribution(self):
        """Annualise retirement-fund deduction rows used before PAYE."""
        current_contribution = 0
        for deduction in self.get("deductions") or []:
            if not deduction.get("exempted_from_income_tax"):
                continue
            if self.is_retirement_fund_component(deduction.salary_component):
                current_contribution += flt(deduction.amount)

        if not current_contribution:
            return 0

        previous_contribution = self.get_previous_retirement_fund_contribution()
        future_periods = max(ceil(flt(getattr(self, "remaining_sub_periods", 1))) - 1, 0)
        return previous_contribution + current_contribution + (current_contribution * future_periods)

    def get_previous_retirement_fund_contribution(self):
        if not self.payroll_period:
            return 0

        previous_slips = frappe.get_all(
            "Salary Slip",
            filters={
                "employee": self.employee,
                "company": self.company,
                "docstatus": 1,
                "start_date": [">=", self.payroll_period.start_date],
                "end_date": ["<", self.start_date],
            },
            pluck="name",
        )
        if not previous_slips:
            return 0

        total = 0
        for row in frappe.get_all(
            "Salary Detail",
            filters={
                "parent": ["in", previous_slips],
                "parentfield": "deductions",
                "exempted_from_income_tax": 1,
            },
            fields=["salary_component", "amount"],
        ):
            if self.is_retirement_fund_component(row.salary_component):
                total += flt(row.amount)

        return total

    def is_retirement_fund_component(self, salary_component):
        return self.get_required_sars_code(salary_component) in RETIREMENT_FUND_DEDUCTION_CODES

    def apply_sa_paye_inclusion_adjustments(self):
        """Remove the non-PAYE portion of classified earnings from annual taxable earnings."""
        adjustment = self.get_annual_paye_exclusion_adjustment()
        if adjustment:
            self.total_taxable_earnings = max(0, flt(self.total_taxable_earnings) - adjustment)
            self.za_paye_inclusion_adjustment = adjustment

    def get_annual_paye_exclusion_adjustment(self):
        total = 0
        for row in self.get("earnings") or []:
            if not flt(row.amount):
                continue
            if not row.get("is_tax_applicable"):
                continue
            inclusion_percentage = self.get_component_paye_inclusion_percentage(row.salary_component)
            if inclusion_percentage >= 100:
                continue
            excluded_current = flt(row.amount) * (100 - inclusion_percentage) / 100
            total += self.get_annualized_component_adjustment(row, excluded_current)
        return flt(total, 2)

    def get_annualized_component_adjustment(self, row, current_amount):
        if row.get("additional_salary") and not row.get("is_recurring_additional_salary"):
            return flt(current_amount)

        previous_amount = self.get_previous_component_paye_exclusion(row.salary_component)
        future_periods = max(ceil(flt(getattr(self, "remaining_sub_periods", 1))) - 1, 0)
        return flt(previous_amount) + flt(current_amount) + (flt(current_amount) * future_periods)

    def get_previous_component_paye_exclusion(self, salary_component):
        if not self.payroll_period:
            return 0

        inclusion_percentage = self.get_component_paye_inclusion_percentage(salary_component)
        if inclusion_percentage >= 100:
            return 0

        previous_slips = frappe.get_all(
            "Salary Slip",
            filters={
                "employee": self.employee,
                "company": self.company,
                "docstatus": 1,
                "start_date": [">=", self.payroll_period.start_date],
                "end_date": ["<", self.start_date],
            },
            pluck="name",
        )
        if not previous_slips:
            return 0

        total = 0
        for row in frappe.get_all(
            "Salary Detail",
            filters={
                "parent": ["in", previous_slips],
                "parentfield": "earnings",
                "salary_component": salary_component,
            },
            fields=["amount"],
        ):
            total += flt(row.amount) * (100 - inclusion_percentage) / 100
        return total

    def get_component_paye_inclusion_percentage(self, salary_component):
        metadata = self.get_sa_component_metadata(salary_component)
        treatment = metadata.get("za_payroll_treatment")
        value = metadata.get("za_paye_inclusion_percentage")
        if treatment and value is not None:
            return flt(value)
        if treatment == "Fixed Travel Allowance":
            return get_default_travel_paye_inclusion_percentage(self.end_date)
        if treatment in {"Reimbursive Travel", "Non-Taxable Reimbursement"}:
            return 0
        return 100

    def get_sa_component_metadata(self, salary_component):
        if not salary_component:
            return frappe._dict()

        fields = [
            "za_sars_payroll_code",
            "za_payroll_treatment",
            "za_paye_inclusion_percentage",
            "za_uif_applicable",
            "za_sdl_applicable",
            "za_coida_applicable",
            "za_is_reimbursement",
            "za_variable_pay_treatment",
        ]
        try:
            meta = frappe.get_meta("Salary Component")
            fields = [field for field in fields if meta.has_field(field)]
        except Exception:
            fields = ["za_sars_payroll_code"]

        if not fields:
            return frappe._dict()
        # Cached read: this metadata is fetched repeatedly per component within
        # the payroll loop, and Salary Component master data rarely changes.
        return (
            frappe.get_cached_value("Salary Component", salary_component, fields, as_dict=True)
            or frappe._dict()
        )

    def get_annual_bonus(self):
        """From the employee's current Salary Structure Assignment."""
        annual_bonus = (
            frappe.db.get_value(
                "Salary Structure Assignment",
                {
                    "employee": self.employee,
                    "salary_structure": self.salary_structure,
                    "docstatus": 1,
                    "from_date": ("<=", self.end_date),
                },
                "za_annual_bonus",
                order_by="from_date desc",
            )
            or 0
        )

        if not annual_bonus:
            return 0

        bonus_component = frappe.get_all(
            "Salary Component", filters={"disabled": False, "za_is_annual_bonus": True}, pluck="name"
        )

        if not bonus_component:
            return annual_bonus

        is_bonus_paid = frappe.db.exists(
            "Additional Salary",
            {
                "docstatus": 1,
                "employee": self.employee,
                "salary_component": ["in", bonus_component],
                "company": self.company,
                "payroll_date": ["between", [self.payroll_period.start_date, self.end_date]],
            },
        )

        return 0 if is_bonus_paid else annual_bonus

    def calculate_variable_based_on_taxable_salary(self, tax_component):
        if not self.payroll_period:
            frappe.msgprint(
                _("Start and end dates not in a valid Payroll Period, cannot calculate {0}.").format(
                    tax_component
                )
            )
            return

        self.calculate_variable_tax(tax_component)

        if tax_component in self._component_based_variable_tax:
            tax_rebates = self.get_tax_rebates()
            medical_credits = self.get_medical_aid_credits()

            annual_tax_after_rebates = max(
                0,
                self._component_based_variable_tax[tax_component]["total_structured_tax_amount"]
                - tax_rebates
                - medical_credits,
            )

            # Recalculate structured PAYE after rebates/credits. Full-tax
            # additional earnings remain payable in the selected payroll run.
            previous_total_paid_taxes = self._component_based_variable_tax[tax_component][
                "previous_total_paid_taxes"
            ]
            remaining_sub_periods = flt(self.remaining_sub_periods)
            current_structured_tax_amount = 0
            if remaining_sub_periods > 0:
                current_structured_tax_amount = max(
                    0,
                    (annual_tax_after_rebates - previous_total_paid_taxes) / remaining_sub_periods,
                )
            full_tax_amount = flt(
                self._component_based_variable_tax[tax_component].get("full_tax_on_additional_earnings")
            )
            current_tax_amount = current_structured_tax_amount + full_tax_amount

            self.total_structured_tax_amount = annual_tax_after_rebates
            self.current_structured_tax_amount = current_structured_tax_amount
            self.current_tax_amount = current_tax_amount
            self._component_based_variable_tax[tax_component].update(
                {
                    "total_structured_tax_amount": annual_tax_after_rebates,
                    "current_structured_tax_amount": current_structured_tax_amount,
                    "current_tax_amount": current_tax_amount,
                }
            )

    def calculate_variable_tax(self, tax_component, has_additional_salary_tax_component=False):
        """Same tax slab calculation as standard HRMS, with SA-specific rebates/
        credits applied by the caller - eval_locals is guarded against None here
        since HRMS's own version doesn't need to (it's never None in that flow)."""
        self.previous_total_paid_taxes = self.get_tax_paid_in_period(
            self.payroll_period.start_date, self.start_date, tax_component
        )

        eval_locals, _default_data = self.get_data_for_eval()
        self.total_structured_tax_amount, __ = calculate_tax_by_tax_slab(
            self.total_taxable_earnings_without_full_tax_addl_components,
            self.tax_slab,
            self.whitelisted_globals,
            eval_locals if eval_locals is not None else {},
        )

        if has_additional_salary_tax_component:
            self.current_structured_tax_amount = self.additional_salary_amount
        elif self.remaining_sub_periods > 0:
            self.current_structured_tax_amount = (
                self.total_structured_tax_amount - self.previous_total_paid_taxes
            ) / self.remaining_sub_periods
        else:
            self.current_structured_tax_amount = 0.0

        self.full_tax_on_additional_earnings = 0.0
        if self.current_additional_earnings_with_full_tax:
            self.total_tax_amount, __ = calculate_tax_by_tax_slab(
                self.total_taxable_earnings,
                self.tax_slab,
                self.whitelisted_globals,
                eval_locals if eval_locals is not None else {},
            )
            self.full_tax_on_additional_earnings = (
                self.total_tax_amount - self.total_structured_tax_amount
            )

        self.current_tax_amount = max(
            0,
            flt(
                self.current_structured_tax_amount
                if has_additional_salary_tax_component
                else (self.current_structured_tax_amount + self.full_tax_on_additional_earnings)
            ),
        )

        self._component_based_variable_tax.setdefault(tax_component, {})
        self._component_based_variable_tax[tax_component].update(
            {
                "previous_total_paid_taxes": self.previous_total_paid_taxes,
                "total_structured_tax_amount": self.total_structured_tax_amount,
                "current_structured_tax_amount": self.current_structured_tax_amount,
                "full_tax_on_additional_earnings": self.full_tax_on_additional_earnings,
                "current_tax_amount": self.current_tax_amount,
            }
        )

    def get_tax_rebates(self):
        """Based on employee age."""
        dob = frappe.db.get_value("Employee", self.employee, "date_of_birth")
        if dob:
            return get_tax_rebate(self, dob)
        return 0

    def get_medical_aid_credits(self):
        # Active medical aid details from Employee Private Benefit. A main
        # member with zero dependants still qualifies for the main-member credit.
        benefits = frappe.get_all(
            "Employee Private Benefit",
            filters={
                "effective_from": ["<=", self.end_date],
                "disable": 0,
                "employee": self.employee,
            },
            fields=[
                "private_medical_aid",
                "medical_aid_dependant",
                "effective_from",
                "to",
            ],
            order_by="effective_from desc",
        )

        for benefit in benefits:
            if benefit.to and getdate(benefit.to) < getdate(self.start_date):
                continue
            if flt(benefit.private_medical_aid) <= 0:
                continue
            return get_medical_aid_credit(
                self,
                benefit.medical_aid_dependant or 0,
                membership_start_date=benefit.effective_from,
                membership_end_date=benefit.to,
            )
        return 0

    def calculate_net_pay(self, skip_tax_breakup_computation: bool = False):
        super().calculate_net_pay(skip_tax_breakup_computation)
        self.apply_statutory_deduction_amounts()
        self.apply_eti()
        self.calculate_company_contributions()

    def apply_eti(self):
        remuneration = self.get_statutory_earning_basis("za_uif_applicable")
        eligibility = check_eti_eligibility(self.employee, self, remuneration)

        if not eligibility["eligible"]:
            self.za_monthly_eti = 0
            if not self.is_new():
                log_eti_calculation(self.employee, self, 0, eligibility)
            return

        eti_amount = calculate_eti_amount(
            self.employee,
            self,
            remuneration,
            eligibility=eligibility,
        )

        if eti_amount <= 0:
            eligibility["eligible"] = False
            eligibility["reason"] = "No ETI is available at the employee's monthly remuneration"

        self.za_monthly_eti = eti_amount

        if not self.is_new():
            log_eti_calculation(self.employee, self, eti_amount, eligibility)

    def _log_current_eti_calculation(self):
        remuneration = self.get_statutory_earning_basis("za_uif_applicable")
        eligibility = check_eti_eligibility(self.employee, self, remuneration)
        eti_amount = flt(self.za_monthly_eti)
        if eligibility["eligible"] and eti_amount <= 0:
            eligibility["eligible"] = False
            eligibility["reason"] = "No ETI is available at the employee's monthly remuneration"
        log_eti_calculation(self.employee, self, eti_amount, eligibility)

    def calculate_company_contributions(self):
        """UIF employer, SDL, COIDA."""
        if not self.salary_structure:
            return

        salary_structure = frappe.get_doc("Salary Structure", self.salary_structure)
        self.company_contribution = []

        additional_contributions = get_additional_salaries(
            self.employee, self.start_date, self.end_date, "company_contributions"
        )

        contribution_dict = {}
        data = self.get_data_for_eval()

        if isinstance(data, tuple):
            data = data[0]

        for component in salary_structure.company_contribution:
            component.name = None
            component.amount = self.eval_condition_and_formula(component, data)

            if component.amount <= 0:
                continue

            self.append("company_contribution", component)
            contribution_dict[component.salary_component] = len(self.company_contribution) - 1

        for contrib in additional_contributions:
            if contrib.component in contribution_dict:
                idx = contribution_dict[contrib.component]
                self.company_contribution[idx].amount += flt(contrib.amount)
            else:
                self.append(
                    "company_contribution",
                    {"salary_component": contrib.component, "amount": flt(contrib.amount)},
                )

        self.apply_statutory_company_contribution_amounts()
        self.total_company_contribution = sum(flt(row.amount) for row in self.get("company_contribution", []))

    def apply_statutory_deduction_amounts(self):
        uif_basis = self.get_statutory_earning_basis("za_uif_applicable")
        employee_uif, _employer_uif = calculate_uif_contribution(uif_basis, self.end_date)

        changed = False
        for row in self.get("deductions") or []:
            if self.is_component_in_codes(row.salary_component, UIF_CODES):
                row.amount = flt(employee_uif, 2)
                row.default_amount = row.amount
                row.depends_on_payment_days = 0
                changed = True

        if changed:
            self.recalculate_totals_after_statutory_adjustment()

    def apply_statutory_company_contribution_amounts(self):
        uif_basis = self.get_statutory_earning_basis("za_uif_applicable")
        sdl_basis = self.get_statutory_earning_basis("za_sdl_applicable")
        _employee_uif, employer_uif = calculate_uif_contribution(uif_basis, self.end_date)
        sdl = sdl_basis * get_sdl_rate(self.end_date)

        for row in self.get("company_contribution") or []:
            if self.is_component_in_codes(row.salary_component, UIF_CODES):
                row.amount = flt(employer_uif, 2)
                row.default_amount = row.amount
                row.depends_on_payment_days = 0
            elif self.is_component_in_codes(row.salary_component, SDL_CODES):
                row.amount = flt(sdl, 2)
                row.default_amount = row.amount
                row.depends_on_payment_days = 0

    def get_statutory_earning_basis(self, applicability_field):
        total = 0
        for row in self.get("earnings") or []:
            if not flt(row.amount) or row.get("statistical_component") or row.get("do_not_include_in_total"):
                continue
            metadata = self.get_sa_component_metadata(row.salary_component)
            self.get_required_sars_code(row.salary_component, metadata)
            if applicability_field not in metadata:
                frappe.throw(
                    _("Salary Component {0} is missing the {1} classification field.").format(
                        frappe.bold(row.salary_component), frappe.bold(applicability_field)
                    ),
                    title=_("Incomplete SARS Payroll Classification"),
                )
            treatment = metadata.get("za_payroll_treatment")
            if treatment in {"Reimbursive Travel", "Non-Taxable Reimbursement", "Working Paper Only"}:
                continue
            if metadata.get("za_is_reimbursement"):
                continue
            if metadata.get(applicability_field) in (0, "0", False, None, ""):
                continue
            total += flt(row.amount)
        return flt(total, 2)

    def is_component_in_codes(self, salary_component, codes):
        metadata = self.get_sa_component_metadata(salary_component)
        return self.get_required_sars_code(salary_component, metadata) in codes

    def get_required_sars_code(self, salary_component, metadata=None):
        metadata = metadata or self.get_sa_component_metadata(salary_component)
        code = metadata.get("za_sars_payroll_code")
        if code:
            return code

        frappe.throw(
            _("Salary Component {0} must have a SARS Payroll Code before payroll can be calculated.").format(
                frappe.bold(salary_component)
            ),
            title=_("Missing SARS Payroll Classification"),
        )

    def recalculate_totals_after_statutory_adjustment(self):
        self.set_net_pay()

    def add_additional_salary_components(self, component_type):
        additional_salaries = get_additional_salaries(
            self.employee, self.start_date, self.end_date, component_type
        )

        for additional_salary in additional_salaries:
            component_data = get_salary_component_data(additional_salary.component)
            remove_if_zero_valued = frappe.get_cached_value(
                "Salary Component", additional_salary.component, "remove_if_zero_valued"
            )
            if flt(additional_salary.amount) == 0 and remove_if_zero_valued:
                continue
            self.update_component_row(
                component_data,
                additional_salary.amount,
                component_type,
                additional_salary,
                is_recurring=additional_salary.is_recurring,
            )

            if component_type == "earnings" and hasattr(self, "benefit_ledger_components"):
                if (
                    additional_salary.ref_doctype == "Employee Benefit Claim"
                    and component_data.is_flexible_benefit
                ) or component_data.accrual_component:
                    if additional_salary.ref_doctype == "Employee Benefit Claim":
                        remarks = f"Payout against Employee Benefit Claim {additional_salary.ref_docname}"
                        flexible_benefit = 1
                    else:
                        remarks = "Accrual Component payout via Additional Salary"
                        flexible_benefit = 0

                    self.benefit_ledger_components.append(
                        {
                            "salary_component": additional_salary.component,
                            "amount": additional_salary.amount,
                            "is_accrual": 0,
                            "transaction_type": "Payout",
                            "flexible_benefit": flexible_benefit,
                            "remarks": remarks,
                        }
                    )

    def on_submit(self):
        super().on_submit()
        submit_eti_log(self.employee, self)

        if self.get("loans"):
            self.make_loan_repayment_entries()

    def on_cancel(self):
        cancel_eti_log(self.employee, self)
        super().on_cancel()

        if self.get("loans"):
            self.cancel_loan_repayment_entries()


def get_eti_deduction(salary_slip):
    remuneration = (
        salary_slip.get_statutory_earning_basis("za_uif_applicable")
        if hasattr(salary_slip, "get_statutory_earning_basis")
        else salary_slip.gross_pay
    )
    eligibility = check_eti_eligibility(salary_slip.employee, salary_slip, remuneration)

    if not eligibility["eligible"]:
        return 0

    return calculate_eti_amount(
        salary_slip.employee,
        salary_slip,
        remuneration,
        eligibility=eligibility,
    )


def get_tax_rebate_value(salary_slip, date_of_birth):
    return get_tax_rebate(salary_slip, date_of_birth)


def get_medical_aid_value(salary_slip, dependants):
    return get_medical_aid_credit(salary_slip, dependants)
