# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months, escape_html, get_url_to_form


class DisciplinaryAction(Document):
    pass


@frappe.whitelist()
def fetch_employee_data(employee, fields):
    frappe.flags.ignore_permissions = True

    # Parse the fields argument from JSON string to dictionary
    fields = json.loads(fields)

    data = {}
    for field in fields:
        value = frappe.db.get_value("Employee", employee, field)
        data[fields[field]] = value if value else ""

    return data


@frappe.whitelist()
def fetch_default_letter_head(company):
    """
    IMPORTANT: Must return a STRING (your existing JS expects res.message to be the letter head string)
    """
    frappe.flags.ignore_permissions = True
    letter_head = frappe.db.get_value("Company", company, "default_letter_head")
    return letter_head if letter_head else ""


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
    frappe.flags.ignore_permissions = True

    data = {
        "compl_name": frappe.db.get_value("Employee", complainant, "employee_name") or "",
        "compl_pos": frappe.db.get_value("Employee", complainant, "designation") or "",
    }

    return data


@frappe.whitelist()
def check_if_ss(accused):
    frappe.flags.ignore_permissions = True

    trade_unions = frappe.get_all("Trade Union", fields=["name"], order_by="name asc")

    for tu in trade_unions:
        ss_list = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": tu.name, "parentfield": "ss_list", "ss_id": accused},
            fields=["ss_id"],
            order_by="modified desc",
        )
        if ss_list:
            return {"is_ss": True, "ss_union": tu.name}

    return {"is_ss": False, "ss_union": None}


# --------------------------------------------------------------------------------------
# NEW: Linked documents rendered into a single HTML field "linked_docs"
# --------------------------------------------------------------------------------------

def _linked_doc_mappings():
    """
    label: Display label for the card
    target_doctype: DocType to list documents from
    backref_field: field in target_doctype that points to this Disciplinary Action
    """
    return [
        ("NTA Hearings", "NTA Hearing", "linked_disciplinary_action"),
        ("Written Outcomes", "Written Outcome", "linked_intervention"),
        ("Disciplinary Outcome Reports", "Disciplinary Outcome Report", "linked_disciplinary_action"),
        ("Warnings", "Warning Form", "linked_disciplinary_action"),
        ("Dismissals", "Dismissal Form", "linked_disciplinary_action"),
        ("Demotions", "Demotion Form", "linked_disciplinary_action"),
        ("Pay Deductions", "Pay Deduction Form", "linked_disciplinary_action"),
        ("Pay Reductions", "Pay Reduction Form", "linked_disciplinary_action"),
        ("Not Guilty Outcomes", "Not Guilty Form", "linked_disciplinary_action"),
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
    if not disciplinary_action_name or disciplinary_action_name.startswith("new-"):
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">
            Linked documents will appear here once the record is saved.
          </div>
        </div>
        """

    cards = []
    total = 0

    for label, target_dt, backref in _linked_doc_mappings():
        try:
            rows = frappe.get_all(
                target_dt,
                filters={backref: disciplinary_action_name},
                fields=["name"],
                order_by="modified desc",
            )
        except Exception:
            frappe.log_error(
                title="get_linked_docs_html query failed",
                message=frappe.get_traceback(),
            )
            rows = []

        if not rows:
            continue

        total += len(rows)

        chips = []
        for r in rows:
            url = get_url_to_form(target_dt, r.name)
            chips.append(
                f"""
                <a class="ir-linked-docs__chip"
                   href="{escape_html(url)}"
                   target="_blank"
                   rel="noopener">
                   {escape_html(r.name)}
                </a>
                """
            )

        cards.append(
            f"""
            <div class="ir-linked-docs__card">
              <div class="ir-linked-docs__card-header">
                <div class="ir-linked-docs__title">{escape_html(label)}</div>
                <div class="ir-linked-docs__badge">{len(rows)}</div>
              </div>
              <div class="ir-linked-docs__chips">
                {''.join(chips)}
              </div>
            </div>
            """
        )

    if total == 0:
        return """
        <div class="ir-linked-docs">
          <div class="ir-linked-docs__empty">No linked documents yet.</div>
        </div>
        """

    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__grid">
        {''.join(cards)}
      </div>
    </div>
    """