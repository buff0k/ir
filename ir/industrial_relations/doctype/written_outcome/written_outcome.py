# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import re
import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import escape_html, get_url_to_form, formatdate


SUPPORTED_LINKED_INTERVENTIONS = {
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
}


def _normalise_text(value):
    return (value or "").strip()


def _normalise_charge(value):
    return re.sub(r"\s+", " ", _normalise_text(value)).casefold()


def _written_outcome_charges(doc):
    return [
        _normalise_text(row.get("indiv_charge"))
        for row in (doc.get("final_charges") or [])
        if _normalise_text(row.get("indiv_charge"))
    ]


def _source_disciplinary_charges(doc):
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
        result["changed"] = (
            _written_outcome_charges(written_outcome)
            != _source_disciplinary_charges(source)
        )
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
    desired = _written_outcome_charges(written_outcome)
    current = list(source.get("final_charges") or [])
    offences = list(source.get("offences") or [])

    current_by_charge = {}
    for row in current:
        key = _normalise_charge(row.get("charge"))
        if key:
            current_by_charge.setdefault(key, []).append(row)

    replacement = []
    used_names = set()

    for index, charge in enumerate(desired):
        code_item = None
        key = _normalise_charge(charge)

        for row in current_by_charge.get(key, []):
            if row.name not in used_names:
                code_item = row.get("code_item")
                used_names.add(row.name)
                break

        if not code_item and index < len(current):
            code_item = current[index].get("code_item")

        if not code_item and index < len(offences):
            code_item = offences[index].get("code_item")

        if not code_item:
            frappe.throw(_(
                'Cannot update Disciplinary Action {0}: the charge "{1}" '
                'has no Disciplinary Code Item to preserve. Add or correct '
                'the corresponding charge on the source Disciplinary Action first.'
            ).format(source.name, charge))

        replacement.append({"code_item": code_item, "charge": charge})

    source.set("final_charges", [])
    for row in replacement:
        source.append("final_charges", row)


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


def _get_request_arg(key, default=None):
    args = getattr(frappe.flags, "args", None) or {}
    if isinstance(args, dict):
        return args.get(key, default)
    return default


def _get_nta_link_field(intervention_type: str | None) -> str | None:
    return {
        "Disciplinary Action": "linked_disciplinary_action",
        "Incapacity Proceedings": "linked_incapacity_proceeding",
        "Poor Performance": "linked_poor_performance",
    }.get(intervention_type)


def _get_latest_linked_nta(intervention: str | None, intervention_type: str | None) -> str | None:
    link_field = _get_nta_link_field(intervention_type)
    if not intervention or not link_field:
        return None

    rows = frappe.get_all(
        "NTA Hearing",
        filters={link_field: intervention},
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

    nta = frappe.get_doc("NTA Hearing", nta_name)

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


def _get_disciplinary_history_charges(action_doc) -> str:
    charges = []

    for row in action_doc.get("final_charges") or []:
        charge = _normalise_text(row.get("charge"))
        if not charge:
            continue

        code_item = _normalise_text(row.get("code_item"))
        charges.append(f"({code_item}) {charge}" if code_item else charge)

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

    # Core linkage only
    doc.ir_intervention = source_doctype
    doc.linked_intervention = source.name

    # Map only stable base fields
    if source_doctype == "Disciplinary Action":
        doc.employee = source.accused
        doc.employee_name = source.accused_name
        doc.employee_designation = source.accused_pos
        doc.company = source.company
        doc.letter_head = source.letter_head
        doc.complainant = source.complainant
        doc.complainant_name = source.compl_name
        doc.employee_branch = source.branch

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

    # Do NOT populate linked_nta or NTA-derived fields here.
    # The form refresh already calls fetch_intervention_data(),
    # which will resolve the latest NTA and populate those fields.

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
        link_field = _get_nta_link_field(intervention_type)
        if link_field:
            actual_link = frappe.db.get_value("NTA Hearing", nta_name, link_field)
            if actual_link != linked_intervention:
                frappe.throw(
                    f"NTA Hearing {nta_name} is not linked to {intervention_type} {linked_intervention}"
                )

    return _get_nta_payload(nta_name, intervention_type)


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