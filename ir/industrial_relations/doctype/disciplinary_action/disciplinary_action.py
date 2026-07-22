# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, escape_html, get_url_to_form

from ir.industrial_relations import utils


class DisciplinaryAction(Document):
    def validate(self):
        self._sync_offence_codes_and_final_charges()

    def _sync_offence_codes_and_final_charges(self):
        """Keep offence display codes and final charges aligned without altering child schemas."""
        offences = list(self.offences or [])
        charges = list(self.final_charges or [])

        descriptions = {}
        code_items = {row.code_item for row in offences if row.code_item}
        if code_items:
            descriptions = {
                row.name: row.offence_description or ""
                for row in frappe.get_all(
                    "Disciplinary Offence",
                    filters={"name": ["in", list(code_items)]},
                    fields=["name", "offence_description"],
                )
            }

        for index, offence in enumerate(offences):
            offence.offence_code = offence.code_item or ""

            if index < len(charges):
                charge = charges[index]
                code_changed = (charge.code_item or "") != (offence.code_item or "")
                charge.code_item = offence.code_item or ""
                if code_changed or not charge.charge:
                    charge.charge = descriptions.get(offence.code_item, "")
            else:
                self.append(
                    "final_charges",
                    {
                        "code_item": offence.code_item or "",
                        "charge": descriptions.get(offence.code_item, ""),
                    },
                )

        while len(self.final_charges or []) > len(offences):
            self.remove(self.final_charges[-1])


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    return utils.fetch_employee_fields(employee, fields)


@frappe.whitelist()
def fetch_default_letter_head(company):
    """
    IMPORTANT: Must return a STRING (your existing JS expects res.message to be the letter head string)
    """
    return utils.get_letter_head_string(company)


def _get_action_sanction_status(action) -> tuple[str, str]:
    """
    Returns (sanction, status) for a Disciplinary Action row.

    status is one of:
    - pending
    - cancelled
    - tracked
    """
    if not action.outcome:
        return "Pending", "pending"

    offence_outcome = frappe.get_doc("Offence Outcome", action.outcome)
    sanction = offence_outcome.disc_offence_out if offence_outcome else ""

    # Check both the linked outcome name and the displayed sanction value so existing
    # outcome naming/configuration stays supported.
    if (action.outcome or "").strip().lower() == "cancelled" or (sanction or "").strip().lower() == "cancelled":
        return sanction or "Cancelled", "cancelled"

    return sanction, "tracked"


def _get_action_charges(action_doc) -> str:
    return "\n".join(
        [f"({row.code_item}) {row.charge}" for row in (action_doc.final_charges or [])]
    )


def _get_disciplinary_actions_for_employee(accused, current_doc_name):
    filters = {"accused": accused}

    if current_doc_name:
        filters["name"] = ["!=", current_doc_name]

    return frappe.get_all(
        "Disciplinary Action",
        filters=filters,
        fields=["name", "outcome_date", "outcome"],
        order_by="outcome_date desc, modified desc",
    )


@frappe.whitelist()
def fetch_disciplinary_history(accused, current_doc_name):
    """
    IMPORTANT: Must match existing JS signature + output format.

    Only returns tracked/completed disciplinary outcomes.
    Pending and Cancelled actions are rendered separately in untracked_disciplinary_actions.
    """
    frappe.flags.ignore_permissions = True

    history = []

    for action in _get_disciplinary_actions_for_employee(accused, current_doc_name):
        sanction, status = _get_action_sanction_status(action)

        if status in ("pending", "cancelled"):
            continue

        action_doc = frappe.get_doc("Disciplinary Action", action.name)

        history.append(
            {
                "disc_action": action_doc.name,
                "date": action_doc.outcome_date,
                "sanction": sanction,
                "charges": _get_action_charges(action_doc),
            }
        )

    return history


@frappe.whitelist()
def get_untracked_disciplinary_actions_html(accused, current_doc_name=None) -> str:
    """
    Renders Pending and Cancelled disciplinary actions into the read-only HTML field
    `untracked_disciplinary_actions`.

    This keeps them visible for accounting/audit purposes without treating them as
    previous disciplinary outcomes.
    """
    frappe.flags.ignore_permissions = True

    if not accused:
        return ""

    rows = []

    for action in _get_disciplinary_actions_for_employee(accused, current_doc_name):
        sanction, status = _get_action_sanction_status(action)

        if status not in ("pending", "cancelled"):
            continue

        action_doc = frappe.get_doc("Disciplinary Action", action.name)
        action_url = get_url_to_form("Disciplinary Action", action_doc.name)
        charges = escape_html(_get_action_charges(action_doc)).replace("\n", "<br>")
        status_label = "Pending" if status == "pending" else "Cancelled"
        indicator_colour = "orange" if status == "pending" else "gray"
        date_value = action_doc.outcome_date or ""

        rows.append(
            f"""
            <tr>
              <td style="width: 15%;">
                <span class="indicator-pill {escape_html(indicator_colour)}">
                  {escape_html(status_label)}
                </span>
              </td>
              <td style="width: 18%;">
                <a href="{escape_html(action_url)}" target="_blank" rel="noopener">
                  {escape_html(action_doc.name)}
                </a>
              </td>
              <td style="width: 17%;">{escape_html(str(date_value))}</td>
              <td style="width: 20%;">{escape_html(sanction or status_label)}</td>
              <td style="width: 30%;">{charges}</td>
            </tr>
            """
        )

    if not rows:
        return ""

    return f"""
    <div class="form-grid">
      <div class="grid-heading-row">
        <div class="grid-row">
          <div class="data-row row">
            <div class="col grid-static-col bold">Pending and Cancelled Disciplinary Actions</div>
          </div>
        </div>
      </div>
      <div class="grid-body">
        <table class="table table-bordered" style="margin: 0; background: var(--fg-color);">
          <thead>
            <tr>
              <th>Status</th>
              <th>Disciplinary Action</th>
              <th>Outcome Date</th>
              <th>Outcome</th>
              <th>Charges</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
      </div>
    </div>
    """


@frappe.whitelist()
def get_linked_documents(disciplinary_action_name: str, linked_doctype: str, linking_field: str) -> list[str]:
    """
    Legacy endpoint retained for backward compatibility.
    (You can remove it later once you're sure nothing calls it anymore.)
    """
    frappe.flags.ignore_permissions = True

    try:
        docs = frappe.get_all(
            linked_doctype,
            filters={linking_field: disciplinary_action_name},
            fields=["name"],
            order_by="modified desc",
        )
        return [d.name for d in docs]
    except Exception:
        frappe.log_error(
            title="get_linked_documents error",
            message=frappe.get_traceback(),
        )
        return []


@frappe.whitelist()
def fetch_complainant_data(complainant):
    data = utils.fetch_complainant_fields(complainant)
    return {"compl_name": data["name"], "compl_pos": data["designation"]}


@frappe.whitelist()
def check_if_ss(accused):
    return utils.check_if_ss(accused)


def _linked_doc_mappings():
    return [
        ("NTA Enquiries", "NTA Enquiry",
            {
                "ir_intervention": "Disciplinary Action",
                "linked_intervention": None,
            },
        ),
        ("Written Outcomes", "Written Outcome",
            {
                "ir_intervention": "Disciplinary Action",
                "linked_intervention": None,
            },
        ),
        ("Warnings", "Warning Form",
            {
                "ir_intervention": "Disciplinary Action",
                "linked_intervention": None,
            },
        ),
        ("Dismissals", "Dismissal Form", "linked_disciplinary_action"),
        ("Demotions", "Demotion Form", "linked_disciplinary_action"),
        ("Pay Deductions", "Pay Deduction Form", "linked_disciplinary_action"),
        ("Pay Reductions", "Pay Reduction Form", "linked_disciplinary_action"),
        ("No Further Action Forms", "No Further Action Form",
            {
                "ir_intervention": "Disciplinary Action",
                "linked_intervention": None,
            },
        ),
        ("Suspensions", "Suspension Form", "linked_disciplinary_action"),
        ("Voluntary Separations", "Voluntary Seperation Agreement", "linked_disciplinary_action"),
        ("Hearing Cancellations", "Hearing Cancellation Form", "linked_disciplinary_action"),
        ("Appeals", "Appeal Against Outcome", "linked_disciplinary_action"),
    ]


@frappe.whitelist()
def get_linked_docs_html(disciplinary_action_name: str) -> str:
    """
    Returns HTML to render inside HTML field `linked_docs`.
    Uses get_url_to_form so routes never break (written-outcome vs written_outcome).
    """
    return utils.render_linked_docs_html(disciplinary_action_name, _linked_doc_mappings())

SANCTION_FIELDS = (
    (1, "sanction_on_first_offence", "First offence"),
    (2, "sanction_on_second_offence", "Second offence"),
    (3, "sanction_on_third_offence", "Third offence"),
    (4, "sanction_on_fourth_offence", "Fourth or subsequent offence"),
)


def _get_prior_offence_counts(accused: str, current_doc_name: str | None, code_items: list[str]) -> dict[str, int]:
    counts = {code_item: 0 for code_item in code_items}
    if not accused or not code_items:
        return counts

    parent_filters = {
        "accused": accused,
        "docstatus": ["!=", 2],
        "outcome": ["is", "set"],
    }
    if current_doc_name and not current_doc_name.startswith("new-"):
        parent_filters["name"] = ["!=", current_doc_name]

    action_names = frappe.get_all(
        "Disciplinary Action",
        filters=parent_filters,
        pluck="name",
    )
    if not action_names:
        return counts

    cancelled_outcomes = set(
        frappe.get_all(
            "Offence Outcome",
            filters={"iscancellation": 1},
            pluck="name",
        )
    )
    if cancelled_outcomes:
        action_names = [
            name
            for name in action_names
            if frappe.db.get_value("Disciplinary Action", name, "outcome") not in cancelled_outcomes
        ]
    if not action_names:
        return counts

    rows = frappe.get_all(
        "Disciplinary Charges",
        filters={
            "parent": ["in", action_names],
            "parenttype": "Disciplinary Action",
            "parentfield": "final_charges",
            "code_item": ["in", code_items],
        },
        fields=["code_item"],
    )
    for row in rows:
        counts[row.code_item] = counts.get(row.code_item, 0) + 1
    return counts


def _get_outcome_details(outcome_names: set[str]) -> dict[str, dict]:
    if not outcome_names:
        return {}

    has_rank = frappe.db.has_column("Offence Outcome", "severity_rank")
    fields = ["name", "disc_offence_out"]
    if has_rank:
        fields.append("severity_rank")

    result = {}
    for row in frappe.get_all(
        "Offence Outcome",
        filters={"name": ["in", list(outcome_names)]},
        fields=fields,
    ):
        result[row.name] = {
            "label": row.disc_offence_out or row.name,
            "rank": int(getattr(row, "severity_rank", 0) or 0),
        }
    return result


@frappe.whitelist()
def get_offence_qol_data(accused=None, current_doc_name=None, code_items=None):
    """Return offence descriptions, applicable sanctions and rendered summary HTML."""
    if isinstance(code_items, str):
        code_items = json.loads(code_items or "[]")
    code_items = [code for code in (code_items or []) if code]

    unique_codes = list(dict.fromkeys(code_items))
    if not unique_codes:
        return {"offences": {}, "html": "", "harshest_outcome": None}

    offence_fields = [
        "name",
        "offence_description",
        "sanction_on_first_offence",
        "sanction_on_second_offence",
        "sanction_on_third_offence",
        "sanction_on_fourth_offence",
    ]
    offence_rows = frappe.get_all(
        "Disciplinary Offence",
        filters={"name": ["in", unique_codes]},
        fields=offence_fields,
    )
    offences = {row.name: row for row in offence_rows}
    prior_counts = _get_prior_offence_counts(accused, current_doc_name, unique_codes)

    outcome_names = set()
    for offence in offence_rows:
        for _, fieldname, _ in SANCTION_FIELDS:
            value = getattr(offence, fieldname, None)
            if value:
                outcome_names.add(value)
    outcomes = _get_outcome_details(outcome_names)

    offence_payload = {}
    summary_rows = []
    harshest = None

    for code_item in unique_codes:
        offence = offences.get(code_item)
        if not offence:
            continue

        prior_count = prior_counts.get(code_item, 0)
        occurrence = min(prior_count + 1, 4)
        sanction_field = SANCTION_FIELDS[occurrence - 1][1]
        occurrence_label = SANCTION_FIELDS[occurrence - 1][2]
        sanction_name = getattr(offence, sanction_field, None) or ""
        sanction = outcomes.get(sanction_name, {"label": sanction_name or "Not configured", "rank": 0})

        offence_payload[code_item] = {
            "offence_code": code_item,
            "offence_description": offence.offence_description or "",
            "prior_count": prior_count,
            "occurrence": occurrence,
            "occurrence_label": occurrence_label,
            "sanction": sanction_name,
            "sanction_label": sanction["label"],
            "severity_rank": sanction["rank"],
        }

        candidate = {
            "name": sanction_name,
            "label": sanction["label"],
            "rank": sanction["rank"],
            "code_item": code_item,
        }
        if harshest is None or candidate["rank"] > harshest["rank"]:
            harshest = candidate

        summary_rows.append(
            f"""
            <tr>
              <td><strong>{escape_html(code_item)}</strong></td>
              <td>{escape_html(offence.offence_description or '')}</td>
              <td>{prior_count}</td>
              <td>{escape_html(occurrence_label)}</td>
              <td>{escape_html(sanction['label'])}</td>
              <td>{sanction['rank']}</td>
            </tr>
            """
        )

    harshest_label = harshest["label"] if harshest else "Not configured"
    harshest_code = harshest["code_item"] if harshest else ""
    html = f"""
    <div class="ir-sanction-summary">
      <div class="alert alert-warning" style="margin-bottom: 12px;">
        <strong>Harshest applicable guideline:</strong>
        {escape_html(harshest_label)}
        {f' <span class="text-muted">({escape_html(harshest_code)})</span>' if harshest_code else ''}
      </div>
      <div class="table-responsive">
        <table class="table table-bordered table-sm" style="margin-bottom: 0;">
          <thead>
            <tr>
              <th>Code</th>
              <th>Offence</th>
              <th>Previous findings</th>
              <th>Applicable level</th>
              <th>Guideline sanction</th>
              <th>Severity rank</th>
            </tr>
          </thead>
          <tbody>{''.join(summary_rows)}</tbody>
        </table>
      </div>
      <div class="text-muted small" style="margin-top: 8px;">
        This is a guideline only. Previous findings are counted from non-cancelled disciplinary actions with an outcome.
      </div>
    </div>
    """

    return {
        "offences": offence_payload,
        "html": html,
        "harshest_outcome": harshest,
    }
