# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
import frappe
from bs4 import BeautifulSoup, Tag
from frappe.model.document import Document
from frappe import _
from frappe.utils import escape_html, get_url_to_form
from frappe.utils import markdown as render_markdown


SUPPORTED_LINKED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


def _normalise_text(value):
    return (value or "").strip()


def _charge_texts(doc):
    # Written Outcome's final_charges uses the same "Disciplinary Charges"
    # child schema as the source Disciplinary Action (code_item + charge).
    return [
        _normalise_text(row.get("charge"))
        for row in (doc.get("final_charges") or [])
        if _normalise_text(row.get("charge"))
    ]


def _get_linked_update_state(written_outcome):
    intervention_type = written_outcome.get("ir_intervention")
    intervention_name = written_outcome.get("linked_intervention")

    result = {
        "supported": intervention_type in SUPPORTED_LINKED_INTERVENTIONS,
        "changed": False,
        "intervention_type": intervention_type,
        "intervention_name": intervention_name,
        "source_field": None,
        "source_label": None,
    }

    if not result["supported"] or not intervention_name:
        return result

    if not frappe.db.exists(intervention_type, intervention_name):
        frappe.throw(_("{0} {1} no longer exists.").format(
            intervention_type, intervention_name
        ))

    source = frappe.get_doc(intervention_type, intervention_name)

    if intervention_type == "Disciplinary Action":
        result["source_field"] = "final_charges"
        result["source_label"] = _("Final Charges")
        result["changed"] = _charge_texts(written_outcome) != _charge_texts(source)
    elif intervention_type == "Incapacity Proceedings":
        result["source_field"] = "details_of_incapacity"
        result["source_label"] = _("Details of Incapacity")
        result["changed"] = (
            _normalise_text(written_outcome.get("final_incapacity_details"))
            != _normalise_text(source.get("details_of_incapacity"))
        )
    elif intervention_type == "Poor Performance":
        result["source_field"] = "details_of_poor_performance"
        result["source_label"] = _("Details of Poor Performance")
        result["changed"] = (
            _normalise_text(written_outcome.get("final_performance_details"))
            != _normalise_text(source.get("details_of_poor_performance"))
        )

    return result


def _replace_disciplinary_final_charges(source, written_outcome):
    # Written Outcome's final_charges and Disciplinary Action's final_charges
    # are both "Disciplinary Charges" rows (code_item + charge), so this is a
    # direct replace - no need to reverse-engineer a code_item by matching
    # charge text.
    source.set("final_charges", [])
    for row in written_outcome.get("final_charges") or []:
        charge = _normalise_text(row.get("charge"))
        if not charge:
            continue
        source.append(
            "final_charges",
            {"code_item": row.get("code_item") or "", "charge": charge},
        )


@frappe.whitelist()
def get_linked_intervention_update_status(docname):
    written_outcome = frappe.get_doc("Written Outcome", docname)
    written_outcome.check_permission("read")
    return _get_linked_update_state(written_outcome)


@frappe.whitelist()
def update_linked_intervention_from_outcome(docname):
    written_outcome = frappe.get_doc("Written Outcome", docname)
    written_outcome.check_permission("write")

    state = _get_linked_update_state(written_outcome)
    if not state["supported"]:
        return {"updated": False, "reason": "unsupported_intervention"}
    if not state["changed"]:
        return {"updated": False, "reason": "unchanged"}

    source = frappe.get_doc(
        written_outcome.ir_intervention,
        written_outcome.linked_intervention,
    )
    source.check_permission("write")

    if written_outcome.ir_intervention == "Disciplinary Action":
        _replace_disciplinary_final_charges(source, written_outcome)
    elif written_outcome.ir_intervention == "Incapacity Proceedings":
        source.details_of_incapacity = (
            written_outcome.final_incapacity_details or ""
        )
    elif written_outcome.ir_intervention == "Poor Performance":
        source.details_of_poor_performance = (
            written_outcome.final_performance_details or ""
        )

    # The intervention may already be submitted. We still use Document.save()
    # so modified metadata, hooks and Version tracking are preserved.
    source.flags.ignore_validate_update_after_submit = True
    source.save()
    source.add_comment(
        "Info",
        _("Updated from Written Outcome {0} by {1}. Source field: {2}.").format(
            written_outcome.name,
            frappe.session.user,
            state["source_label"],
        ),
    )

    return {
        "updated": True,
        "intervention_type": source.doctype,
        "intervention_name": source.name,
        "source_field": state["source_field"],
        "source_label": state["source_label"],
    }


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

    def validate(self):
        self._assign_annexure_letters()

    def _assign_annexure_letters(self):
        # Single continuous sequence across both tables (complainant rows
        # first) so "[Annexure C]" typed into a summary field unambiguously
        # identifies one evidence row regardless of which side submitted it.
        # Recomputed on every save so it stays correct after rows are
        # added/removed/reordered - this is what makes the client-side
        # read-only grid toggle safe rather than merely cosmetic.
        rows = list(self.get("complainant_evidence") or []) + list(self.get("accused_evidence") or [])
        for i, row in enumerate(rows):
            row.evidence_annexure = f"Annexure {_excel_style_letters(i)}"


def _excel_style_letters(index: int) -> str:
    """0 -> A, 1 -> B, ..., 25 -> Z, 26 -> AA, 27 -> AB, ... (bijective base-26)."""
    index += 1
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _get_request_arg(key, default=None):
    args = getattr(frappe.flags, "args", None) or {}
    if isinstance(args, dict):
        return args.get(key, default)
    return default


def _get_latest_linked_nta(
    intervention: str | None,
    intervention_type: str | None,
) -> str | None:
    if (
        not intervention
        or intervention_type not in SUPPORTED_LINKED_INTERVENTIONS
    ):
        return None

    rows = frappe.get_all(
        "NTA Enquiry",
        filters={
            "ir_intervention": intervention_type,
            "linked_intervention": intervention,
        },
        fields=["name", "creation"],
        order_by="creation desc, modified desc",
        limit_page_length=1,
    )
    return rows[0].name if rows else None


def _get_nta_payload(nta_name: str | None, intervention_type: str | None) -> dict:
    out = {
        "nta_charges": [],
        "incap_type_nta": None,
        "incapacity_details_nta": "",
        "performance_details_nta": "",
    }

    if not nta_name:
        return out

    nta = frappe.get_doc("NTA Enquiry", nta_name)

    if intervention_type == "Disciplinary Action":
        out["nta_charges"] = []
        for row in (nta.get("nta_charges") or []):
            value = (row.indiv_charge or "").strip()
            if value:
                out["nta_charges"].append({"indiv_charge": value})

    elif intervention_type == "Incapacity Proceedings":
        out["incap_type_nta"] = nta.get("type_of_incapacity")
        out["incapacity_details_nta"] = nta.get("details_of_incapacity") or ""

    elif intervention_type == "Poor Performance":
        out["performance_details_nta"] = nta.get("performance_details_nta") or ""

    return out


def _charge_lines(doc, fieldname: str) -> list[str]:
    lines = []
    for row in doc.get(fieldname) or []:
        charge = _normalise_text(row.get("charge"))
        if not charge:
            continue
        code_item = _normalise_text(row.get("code_item"))
        lines.append(f"({code_item}) {charge}" if code_item else charge)
    return lines


def _get_disciplinary_history_charges(action_doc) -> str:
    charges = _charge_lines(action_doc, "final_charges")
    return "\n".join(charges) if charges else "No charges recorded"


def _get_disciplinary_history_for_written_outcome(
    accused: str | None,
    current_action: str | None,
) -> list[dict]:
    """
    Return every other Disciplinary Action for the employee.

    Completed, Cancelled and Pending actions are all included. The action
    currently linked to this Written Outcome is excluded because it is the
    matter being decided, not previous history.
    """
    if not accused:
        return []

    filters = {"accused": accused}
    if current_action:
        filters["name"] = ["!=", current_action]

    actions = frappe.get_all(
        "Disciplinary Action",
        filters=filters,
        fields=["name", "outcome_date", "outcome"],
        order_by="outcome_date desc, modified desc",
    )

    history = []

    for action in actions:
        action_doc = frappe.get_doc("Disciplinary Action", action.name)

        if not action.outcome:
            sanction = "Pending"
        else:
            sanction = frappe.db.get_value(
                "Offence Outcome",
                action.outcome,
                "disc_offence_out",
            ) or action.outcome

            if (
                _normalise_text(action.outcome).casefold() == "cancelled"
                or _normalise_text(sanction).casefold() == "cancelled"
            ):
                sanction = "Cancelled"

        history.append(
            {
                "disc_action": action_doc.name,
                "date": action_doc.get("outcome_date"),
                "sanction": sanction,
                "charges": _get_disciplinary_history_charges(action_doc),
            }
        )

    return history


@frappe.whitelist()
def create_written_outcome(source_name=None, source_doctype=None):
    source_name = source_name or frappe.form_dict.get("source_name")
    source_doctype = source_doctype or frappe.form_dict.get("source_doctype")

    if not source_doctype:
        frappe.throw("source_doctype is required")

    if not source_name:
        frappe.throw("source_name is required")

    if not frappe.db.exists(source_doctype, source_name):
        frappe.throw(f"{source_doctype} {source_name} not found")

    source = frappe.get_doc(source_doctype, source_name)
    doc = frappe.new_doc("Written Outcome")

    doc.ir_intervention = source_doctype
    doc.linked_intervention = source.name

    if source_doctype == "Disciplinary Action":
        doc.employee = source.accused
        doc.employee_name = source.accused_name
        doc.employee_designation = source.accused_pos
        doc.company = source.company
        doc.letter_head = source.letter_head
        doc.complainant = source.complainant
        doc.complainant_name = source.compl_name
        doc.employee_branch = source.branch

        # Final Charges starts out as a copy of the Disciplinary Action's
        # current Charges - the IR practitioner then edits/formulates them
        # independently within the Written Outcome from here on, and the
        # source is only updated back from this on submit.
        for row in source.get("final_charges") or []:
            charge = (row.charge or "").strip()
            if not charge:
                continue
            doc.append(
                "final_charges",
                {"code_item": row.code_item or "", "charge": charge},
            )

    elif source_doctype == "Incapacity Proceedings":
        doc.employee = source.accused
        doc.employee_name = source.accused_name
        doc.employee_designation = source.accused_pos
        doc.company = source.company
        doc.letter_head = source.letter_head
        doc.complainant = source.complainant
        doc.complainant_name = source.compl_name
        doc.employee_branch = source.branch

    elif source_doctype == "Poor Performance":
        doc.employee = source.employee
        doc.employee_name = source.employee_name
        doc.employee_designation = source.employee_designation
        doc.company = source.company
        doc.letter_head = source.letter_head
        doc.complainant = source.complainant
        doc.complainant_name = source.complainant_name
        doc.employee_branch = source.branch

    elif source_doctype == "Appeal Against Outcome":
        doc.employee = getattr(source, "appellant", None)
        doc.employee_name = getattr(source, "appellant_name", None)
        doc.company = getattr(source, "company", None)
        doc.letter_head = getattr(source, "letter_head", None)

    elif source_doctype == "External Dispute Resolution":
        doc.employee = getattr(source, "employee", None)
        doc.employee_name = getattr(source, "employee_name", None)
        doc.company = getattr(source, "company", None)
        doc.letter_head = getattr(source, "letter_head", None)

    else:
        frappe.throw(f"Unsupported source DocType: {source_doctype}")

    return doc.as_dict()

@frappe.whitelist()
def fetch_intervention_data(intervention, intervention_type):
    field_maps = {
        "Disciplinary Action": {
            "source_fields": [
                "accused",
                "accused_name",
                "accused_pos",
                "company",
                "complainant",
                "branch",
                "compl_name",
            ],
            "target_fields": [
                "employee",
                "employee_name",
                "employee_designation",
                "company",
                "complainant",
                "employee_branch",
                "complainant_name",
            ],
        },
        "Incapacity Proceedings": {
            "source_fields": [
                "accused",
                "accused_name",
                "accused_pos",
                "company",
                "complainant",
                "compl_name",
                "branch",
            ],
            "target_fields": [
                "employee",
                "employee_name",
                "employee_designation",
                "company",
                "complainant",
                "complainant_name",
                "employee_branch",
            ],
        },
        "Poor Performance": {
            "source_fields": [
                "employee",
                "employee_name",
                "employee_designation",
                "company",
                "complainant",
                "complainant_name",
                "branch",
            ],
            "target_fields": [
                "employee",
                "employee_name",
                "employee_designation",
                "company",
                "complainant",
                "complainant_name",
                "employee_branch",
            ],
        },
        "Appeal Against Outcome": {
            "source_fields": ["appellant", "appellant_name", "company"],
            "target_fields": ["employee", "employee_name", "company"],
        },
        "External Dispute Resolution": {
            "source_fields": ["employee", "employee_name", "company"],
            "target_fields": ["employee", "employee_name", "company"],
        },
    }

    if intervention_type not in field_maps:
        frappe.throw(f"Unsupported intervention type: {intervention_type}")

    mapping = field_maps[intervention_type]

    data = frappe.db.get_value(
        intervention_type,
        intervention,
        mapping["source_fields"],
        as_dict=True,
    ) or {}

    transformed = {
        target: data.get(source)
        for source, target in zip(mapping["source_fields"], mapping["target_fields"])
    }

    latest_nta = _get_latest_linked_nta(intervention, intervention_type)
    transformed["linked_nta"] = latest_nta
    transformed.update(_get_nta_payload(latest_nta, intervention_type))

    if intervention_type == "Disciplinary Action":
        transformed["disciplinary_history"] = (
            _get_disciplinary_history_for_written_outcome(
                accused=data.get("accused"),
                current_action=intervention,
            )
        )

    elif intervention_type == "Incapacity Proceedings":
        source_doc = frappe.get_doc(intervention_type, intervention)
        transformed["previous_incapacity_outcomes"] = [
            {
                "incap_proc": row.get("incap_proc"),
                "date": row.get("date"),
                "incap_details": row.get("incap_details") or "",
                "sanction": row.get("sanction") or "",
            }
            for row in (source_doc.get("previous_incapacity_outcomes") or [])
        ]

    elif intervention_type == "Poor Performance":
        source_doc = frappe.get_doc(intervention_type, intervention)
        transformed["previous_performance_outcomes"] = [
            {
                "performance_action": row.get("performance_action"),
                "date": row.get("date"),
                "charges": row.get("charges") or "",
                "sanction": row.get("sanction") or "",
            }
            for row in (source_doc.get("previous_disciplinary_outcomes") or [])
        ]

    return transformed


@frappe.whitelist()
def get_nta_details(nta_name, intervention_type=None, linked_intervention=None):
    if not nta_name:
        return {
            "nta_charges": [],
            "incap_type_nta": None,
            "incapacity_details_nta": "",
            "performance_details_nta": "",
        }

    if intervention_type and linked_intervention:
        actual = frappe.db.get_value(
            "NTA Enquiry",
            nta_name,
            ["ir_intervention", "linked_intervention"],
            as_dict=True,
        )
        if not actual:
            frappe.throw(_("NTA Enquiry {0} does not exist.").format(nta_name))

        if (
            actual.ir_intervention != intervention_type
            or actual.linked_intervention != linked_intervention
        ):
            frappe.throw(
                _(
                    "NTA Enquiry {0} is not linked to {1} {2}."
                ).format(nta_name, intervention_type, linked_intervention)
            )

    return _get_nta_payload(nta_name, intervention_type)


OUTCOME_MARKDOWN_FIELDS = {
    "summary_introduction": "Introduction",
    "summary_complainant": "Complainant's Case",
    "summary_accused": "Accused Employee Case",
    "summary_analysis": "Analysis of Evidence",
    "summary_finding": "Finding by Chairperson",
    "summary_mitigation": "Mitigating Considerations",
    "summary_aggravation": "Aggravating Considerations",
    "summary_outcome": "Outcome",
}

ANNEXURE_REFERENCE_RE = re.compile(r"\[([^\[\]]+)\]")

# A line starting with one or more ">" marks a sub-point of the point above
# it - "&gt;" -> [parent.n], "&gt;&gt;" -> [parent.child.n], etc - rather than
# relying on markdown's own indentation-sensitive nested-list syntax, which
# is easy to get wrong by hand in a plain-text editor (missing/miscounted
# leading spaces silently produces a flat list instead of a nested one).
LEVEL_PREFIX_RE = re.compile(r"^\s*(>+)\s*")

HEADING_TAG_RE = re.compile(r"^h[1-6]$")


def get_outcome_body(doc):
    """
    Render the Chairperson Summary sections as continuously numbered points
    (South African judgment style: [1], [2], ..., with ">"/"&gt;&gt;"-prefixed
    lines becoming hierarchical sub-points [n.n]/[n.n.n]), converting inline
    "[Annexure Name]" references into superscript footnote markers.

    Returns (html, footnotes) where footnotes is an ordered list of
    {number, annexure, description, attach} dicts, first-appearance order.

    Registered as a Jinja method (see ir/hooks.py) so the Written Outcome
    print format can call it directly at render time.
    """
    annexure_lookup = {
        row.evidence_annexure: row
        for row in list(doc.get("complainant_evidence") or []) + list(doc.get("accused_evidence") or [])
        if row.evidence_annexure
    }

    footnote_no_by_annexure = {}
    footnotes = []
    counters = [0]
    sections = []

    for field, heading in OUTCOME_MARKDOWN_FIELDS.items():
        content = doc.get(field)
        if content:
            parts = [f"<h4>{escape_html(heading)}</h4>"]

            for raw_line in content.split("\n"):
                match = LEVEL_PREFIX_RE.match(raw_line)
                level = len(match.group(1)) if match else 0
                line_text = (raw_line[match.end():] if match else raw_line).lstrip(" \t")
                if not line_text.strip():
                    continue

                # Render this one line's own markdown (bold/italic/links/a bare
                # "1. " list marker, etc.) in isolation, then unwrap whatever
                # single block element it produced - the numbering/indentation
                # here is ours, not markdown's.
                line_soup = BeautifulSoup(render_markdown(line_text), "html.parser")
                top_nodes = [n for n in line_soup.contents if isinstance(n, Tag)]
                if not top_nodes:
                    continue
                node = top_nodes[0]

                if node.name in ("ol", "ul"):
                    # A bare "1. " / "- " line renders as a single-item list on
                    # its own - unwrap to that one <li>, since the numbering and
                    # indentation here are ours, not the list's.
                    node = node.find("li") or node

                _linkify_annexure_refs(node, annexure_lookup, footnote_no_by_annexure, footnotes)

                if HEADING_TAG_RE.match(node.name or ""):
                    parts.append(str(node))
                    continue

                number = _advance_counters(counters, level)
                parts.append(
                    f'<div class="numbered-para level-{level}">'
                    f'<span class="para-number">[{number}]</span>'
                    f'<span class="para-text">{node.decode_contents()}</span>'
                    f"</div>"
                )

            sections.append("\n".join(parts))

        # These two fixed-position sections pull from the linked NTA / final
        # charge fields rather than a Markdown Editor field, so they aren't
        # part of OUTCOME_MARKDOWN_FIELDS - they're spliced in here, after
        # Introduction and after Finding, sharing the same `counters` state
        # so the numbering continues seamlessly around them.
        if field == "summary_introduction":
            nta_section = _nta_background_points(doc)
            if nta_section:
                heading, points = nta_section
                section_html = _render_points_section(
                    heading, points, counters, annexure_lookup, footnote_no_by_annexure, footnotes
                )
                if section_html:
                    sections.append(section_html)
        elif field == "summary_finding":
            final_section = _final_details_points(doc)
            if final_section:
                heading, points = final_section
                section_html = _render_points_section(
                    heading, points, counters, annexure_lookup, footnote_no_by_annexure, footnotes
                )
                if section_html:
                    sections.append(section_html)

    return "\n".join(sections), footnotes


def _render_points_section(heading, points, counters, annexure_lookup, footnote_no_by_annexure, footnotes):
    """Render a fixed heading + a short run of numbered points from plain
    (non-Markdown) field values, advancing the same counters/footnote state
    the main Markdown-field loop in get_outcome_body() uses, so it numbers
    continuously with the sections around it.
    """
    if not heading or not points:
        return ""

    parts = [f"<h4>{escape_html(heading)}</h4>"]
    for level, text in points:
        node = BeautifulSoup(f"<span>{escape_html(text)}</span>", "html.parser").find("span")
        _linkify_annexure_refs(node, annexure_lookup, footnote_no_by_annexure, footnotes)
        number = _advance_counters(counters, level)
        parts.append(
            f'<div class="numbered-para level-{level}">'
            f'<span class="para-number">[{number}]</span>'
            f'<span class="para-text">{node.decode_contents()}</span>'
            f"</div>"
        )
    return "\n".join(parts)


def _nta_background_points(doc):
    """Points for the "as per NTA" section inserted after Introduction."""
    intervention = doc.get("ir_intervention")

    if intervention == "Disciplinary Action":
        charges = [
            _normalise_text(row.get("indiv_charge"))
            for row in (doc.get("nta_charges") or [])
            if _normalise_text(row.get("indiv_charge"))
        ]
        if not charges:
            return None
        if len(charges) == 1:
            return "Charges as per NTA", [(0, charges[0])]
        points = [(0, "The Employee was charged as per the Notice to Attend as follows:")]
        points += [(1, charge) for charge in charges]
        return "Charges as per NTA", points

    if intervention == "Incapacity Proceedings":
        incap_type = _normalise_text(doc.get("incap_type_nta"))
        details = _normalise_text(doc.get("incapacity_details_nta"))
        if not incap_type and not details:
            return None
        points = []
        if incap_type:
            points.append((0, f"Type of Incapacity: {incap_type}"))
        if details:
            points.append((1 if incap_type else 0, f"Details of Incapacity: {details}"))
        return "Type of Incapacity and Details of Incapacity", points

    if intervention == "Poor Performance":
        details = _normalise_text(doc.get("performance_details_nta"))
        if not details:
            return None
        return "Details of Poor Performance as per NTA", [(0, details)]

    return None


def _final_details_points(doc):
    """Points for the "Final ..." section inserted after Finding by Chairperson."""
    intervention = doc.get("ir_intervention")

    if intervention == "Disciplinary Action":
        charges = _charge_lines(doc, "final_charges")
        if not charges:
            return None
        if len(charges) == 1:
            return "Final Charges", [(0, charges[0])]
        points = [(0, "The final charges against the Employee were as follows:")]
        points += [(1, charge) for charge in charges]
        return "Final Charges", points

    if intervention == "Incapacity Proceedings":
        details = _normalise_text(doc.get("final_incapacity_details"))
        if not details:
            return None
        return "Final Incapacity Details", [(0, details)]

    if intervention == "Poor Performance":
        details = _normalise_text(doc.get("final_performance_details"))
        if not details:
            return None
        return "Final Poor Performance Details", [(0, details)]

    return None


def _advance_counters(counters, level):
    """Advance a legal-style hierarchical counter (1, 1.1, 1.1.1, 2, 2.1, ...).

    Any counter deeper than `level` is dropped, since a new point at this
    level starts a fresh run of sub-points beneath it.
    """
    while len(counters) <= level:
        counters.append(0)
    counters[level] += 1
    del counters[level + 1:]
    return ".".join(str(c) for c in counters[: level + 1])


def _linkify_annexure_refs(node, annexure_lookup, footnote_no_by_annexure, footnotes):
    """Replace "[Annexure Name]" text tokens with superscript footnote markers, in place.

    Only brackets whose contents exactly match a real Annexure Name on this
    doc are touched, so ordinary markdown links ("[text](url)") and other
    incidental bracket text are left untouched.
    """
    for text_node in list(node.find_all(string=True)):
        original = str(text_node)
        if "[" not in original:
            continue

        def _replace(match):
            token = match.group(1)
            row = annexure_lookup.get(token)
            if not row:
                return match.group(0)
            if token not in footnote_no_by_annexure:
                footnote_no_by_annexure[token] = len(footnotes) + 1
                footnotes.append({
                    "number": footnote_no_by_annexure[token],
                    "annexure": token,
                    "description": row.evidence_description or "",
                    "attach": row.evidence_attach or "",
                })
            return f'<sup class="footnote-ref">{footnote_no_by_annexure[token]}</sup>'

        replaced = ANNEXURE_REFERENCE_RE.sub(_replace, original)
        if replaced != original:
            text_node.replace_with(*BeautifulSoup(replaced, "html.parser").contents)


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
    if not linked_intervention or linked_intervention.startswith("new-"):
        return {
            "linked_rulings": _empty_block("Linked documents will appear here once the record is saved."),
        }

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

    linked_rulings_html = (
        _chips_block("Rulings", "Ruling", ruling_names)
        if ruling_names
        else _empty_block("No linked Rulings yet.")
    )

    return {
        "linked_rulings": linked_rulings_html,
    }


@frappe.whitelist()
def get_linked_documents(reference_name, linked_doctype, linking_field):
    if not reference_name or not linked_doctype or not linking_field:
        return []

    return frappe.get_all(
        linked_doctype,
        filters={linking_field: reference_name},
        pluck="name",
    )