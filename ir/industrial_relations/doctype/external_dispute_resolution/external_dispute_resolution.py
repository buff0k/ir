# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.model.document import Document
from frappe.utils import escape_html, get_url_to_form


class ExternalDisputeResolution(Document):
    def before_submit(self):
        if not self.outcome:
            frappe.throw("You cannot submit this record without selecting an Outcome.")


def _empty_block(msg: str) -> str:
    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__empty">{escape_html(msg)}</div>
    </div>
    """


def _chips_block(label: str, doctype: str, names: list[str]) -> str:
    chips = []
    for name in names:
        url = get_url_to_form(doctype, name)
        chips.append(
            f"""
            <a class="ir-linked-docs__chip"
               href="{escape_html(url)}"
               target="_blank"
               rel="noopener">
               {escape_html(name)}
            </a>
            """
        )

    return f"""
    <div class="ir-linked-docs">
      <div class="ir-linked-docs__grid">
        <div class="ir-linked-docs__card">
          <div class="ir-linked-docs__card-header">
            <div class="ir-linked-docs__title">{escape_html(label)}</div>
            <div class="ir-linked-docs__badge">{len(names)}</div>
          </div>
          <div class="ir-linked-docs__chips">
            {''.join(chips)}
          </div>
        </div>
      </div>
    </div>
    """


# fieldname on External Dispute Resolution Applicants -> (doctype to search,
# the Employee-link field on that doctype). Retrenchment Process is
# deliberately absent here - it's multi-employee via a child table, handled
# separately below, same reasoning as External Dispute Resolution itself.
LATEST_LINK_SOURCES = {
    "contract": ("Contract of Employment", "employee"),
    "disc_action": ("Disciplinary Action", "accused"),
    "incap_proceeding": ("Incapacity Proceedings", "accused"),
    "appeal": ("Appeal Against Outcome", "employee"),
}


@frappe.whitelist()
def get_latest_linked_records(applicant: str, exclude_edr: str | None = None) -> dict:
    """For a given Employee (an EDR "Applicant"), find the latest (most
    recently created) linked record of each related IR intervention type.
    Where more than one linked record of a type exists, the latest one
    wins."""
    result = {}

    for fieldname, (doctype, employee_field) in LATEST_LINK_SOURCES.items():
        rows = frappe.get_all(
            doctype,
            filters={employee_field: applicant},
            fields=["name"],
            order_by="creation desc",
            limit_page_length=1,
        )
        result[fieldname] = rows[0].name if rows else None

    # Retrenchment Process only carries the Employee link via its own
    # affected_employees child table - resolve to that row's parent (the
    # actual process), not the child row's own name.
    retrenchment_rows = frappe.get_all(
        "Retrenchment Affected Employee",
        filters={"employee": applicant},
        fields=["parent"],
        order_by="creation desc",
        limit_page_length=1,
    )
    result["retrenchment"] = retrenchment_rows[0].parent if retrenchment_rows else None

    # External Dispute Resolution is itself multi-employee - find the latest
    # OTHER EDR case this applicant was linked to, excluding the one this
    # row itself lives on, so a case never links to itself.
    edr_rows = frappe.get_all(
        "External Dispute Resolution Applicants",
        filters={"applicant": applicant, "parenttype": "External Dispute Resolution"},
        fields=["parent"],
        order_by="creation desc",
    )
    other_edr = [row.parent for row in edr_rows if row.parent != exclude_edr]
    result["external_dispute"] = other_edr[0] if other_edr else None

    return result


@frappe.whitelist()
def get_linked_outcome_html(edr_name: str | None):
    """
    Render the linked outcome section as HTML for the HTML field `linked_outcome`.

    We treat "linked outcomes" as Written Outcome docs linked to this EDR via:
      - Written Outcome.ir_intervention = "External Dispute Resolution"
      - Written Outcome.linked_intervention = <this EDR name>
    """
    if not edr_name or edr_name.startswith("new-"):
        return _empty_block("Linked outcomes will appear here once the record is saved.")

    names = frappe.get_all(
        "Written Outcome",
        filters={
            "ir_intervention": "External Dispute Resolution",
            "linked_intervention": edr_name,
        },
        pluck="name",
        order_by="modified desc",
    )

    if not names:
        return _empty_block("No linked Written Outcomes yet.")

    return _chips_block("Written Outcomes", "Written Outcome", names)
