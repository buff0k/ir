# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
import frappe
from frappe.model.document import Document
from frappe.utils import escape_html, get_url_to_form, formatdate


class WrittenOutcome(Document):
    def autoname(self):
        """
        Stable naming:
          OUT-<linked_intervention>        (first record)
          OUT-<linked_intervention>-<n>    (revisions, n starts at 1)
        """
        if not self.linked_intervention:
            return

        base = f"OUT-{self.linked_intervention}"

        existing = frappe.get_all(
            self.doctype,
            filters={"linked_intervention": self.linked_intervention},
            fields=["name"],
        )

        if not existing:
            self.name = base
            return

        pat = re.compile(rf"^{re.escape(base)}-(\d+)$")
        revs = []
        for row in existing:
            m = pat.match(row.name or "")
            if m:
                try:
                    revs.append(int(m.group(1)))
                except Exception:
                    pass

        next_rev = (max(revs) + 1) if revs else 1
        self.name = f"{base}-{next_rev}"


# ---------------------------------------------------------------------
# Compile outcome
# ---------------------------------------------------------------------

@frappe.whitelist()
def normalize_headings(content):
    if not content:
        return content
    return re.sub(r"^(#{1,})\s*(\S.*)", r"### \2", content, flags=re.MULTILINE)


@frappe.whitelist()
def compile_outcome(docname):
    doc = frappe.get_doc("Written Outcome", docname)

    chair = doc.get("chairperson_name") or doc.get("chairperson") or ""
    enquiry_date = doc.get("enquiry_date")

    compiled = (
        "| **Field** | **Value** |\n"
        "|------------------------------------|-----------------------------------|\n"
        f"| **Employee Name** | {doc.get('employee_name') or ''} ({doc.get('employee_branch') or ''}) |\n"
        f"| **Chairperson** | {chair} |\n"
        f"| **Date of Enquiry** | {formatdate(enquiry_date, 'd MMMM YYYY') if enquiry_date else ''} |\n\n"
    )

    markdown_fields = {
        "summary_introduction": "Introduction",
        "summary_complainant": "Complainant's Case",
        "summary_accused": "Accused Employee Case",
        "summary_analysis": "Analysis of Evidence",
        "summary_finding": "Finding by Chairperson",
        "summary_mitigation": "Mitigating Considerations",
        "summary_aggravation": "Aggravating Considerations",
        "summary_outcome": "Outcome",
    }

    for field, heading in markdown_fields.items():
        content = doc.get(field)
        if content:
            compiled += f"### {heading}\n\n{normalize_headings(content)}\n\n"

    doc.complete_outcome = compiled
    doc.save(ignore_permissions=True)
    return {"ok": True}


# ---------------------------------------------------------------------
# Linked docs HTML (for HTML fields linked_nta + linked_rulings)
# ---------------------------------------------------------------------

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
def get_linked_sections_html(linked_intervention: str | None):
    """
    Returns HTML for:
      - linked_nta (NTA Hearing docs linked to a Disciplinary Action)
      - linked_rulings (Ruling docs linked to the intervention)

    Intended to be rendered into HTML fields with the SAME fieldnames:
      linked_nta, linked_rulings
    """
    if not linked_intervention or linked_intervention.startswith("new-"):
        return {
            "linked_nta": _empty_block("Linked documents will appear here once the record is saved."),
            "linked_rulings": _empty_block("Linked documents will appear here once the record is saved."),
        }

    # NTA hearings (only exist when linked_intervention is a Disciplinary Action name)
    try:
        nta_names = frappe.get_all(
            "NTA Hearing",
            filters={"linked_disciplinary_action": linked_intervention},
            pluck="name",
            order_by="modified desc",
        )
    except Exception:
        frappe.log_error(title="WrittenOutcome: NTA query failed", message=frappe.get_traceback())
        nta_names = []

    # Rulings
    try:
        ruling_names = frappe.get_all(
            "Ruling",
            filters={"linked_intervention": linked_intervention},
            pluck="name",
            order_by="modified desc",
        )
    except Exception:
        frappe.log_error(title="WrittenOutcome: Ruling query failed", message=frappe.get_traceback())
        ruling_names = []

    linked_nta_html = (
        _chips_block("NTA Hearings", "NTA Hearing", nta_names)
        if nta_names
        else _empty_block("No linked NTA Hearings yet.")
    )

    linked_rulings_html = (
        _chips_block("Rulings", "Ruling", ruling_names)
        if ruling_names
        else _empty_block("No linked Rulings yet.")
    )

    return {
        "linked_nta": linked_nta_html,
        "linked_rulings": linked_rulings_html,
    }


# ---------------------------------------------------------------------
# Keep this helper for any existing callers (do not break other usage)
# ---------------------------------------------------------------------

@frappe.whitelist()
def get_linked_documents(reference_name, linked_doctype, linking_field):
    if not reference_name or not linked_doctype or not linking_field:
        return []

    return frappe.get_all(
        linked_doctype,
        filters={linking_field: reference_name},
        pluck="name",
    )
