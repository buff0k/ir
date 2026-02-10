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
