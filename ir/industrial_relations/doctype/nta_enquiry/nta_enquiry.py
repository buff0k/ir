# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from __future__ import annotations

import json
import re
from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import format_datetime, get_datetime
from ir.industrial_relations import ics
from ir.industrial_relations.email_style import (
    EMAIL_STYLE_BLOCK,
    email_header,
    greeting,
    intro,
    signoff,
    view_link,
)
from ir.industrial_relations.utils import (
    employee_email,
    fetch_company_letter_head as _fetch_company_letter_head,
    fetch_employee_name,
    fetch_performance_data,
)


SUPPORTED_INTERVENTIONS = (
    "Disciplinary Action",
    "Incapacity Proceedings",
    "Poor Performance",
)

# The subject-line label for each intervention type, per the calendar invite
# format: "{label} - {Company} // {Accused Employee (Coy)}".
INVITE_SUBJECT_LABEL = {
    "Disciplinary Action": "Hearing",
    "Incapacity Proceedings": "Incapacity",
    "Poor Performance": "Performance Counselling",
}

# NTA Enquiry has no explicit end-time/duration field - only a single
# hearing_date_time - so the invite defaults to this length. Easy to adjust
# here if IR wants a different default.
DEFAULT_INVITE_DURATION_MINUTES = 60


class NTAEnquiry(Document):
    def autoname(self):
        if not self.linked_intervention:
            return

        base_name = f"NTA-{self.linked_intervention}"
        existing_names = frappe.get_all(
            self.doctype,
            filters={
                "ir_intervention": self.ir_intervention,
                "linked_intervention": self.linked_intervention,
            },
            pluck="name",
        )

        if not existing_names:
            self.name = base_name
            return

        revision_pattern = re.compile(rf"^{re.escape(base_name)}-(\d+)$")
        revisions = []

        for existing_name in existing_names:
            match = revision_pattern.match(existing_name or "")
            if match:
                revisions.append(int(match.group(1)))

        self.name = f"{base_name}-{max(revisions, default=0) + 1}"

    def validate(self):
        if self.ir_intervention not in SUPPORTED_INTERVENTIONS:
            frappe.throw(
                _("Unsupported IR Intervention: {0}").format(
                    self.ir_intervention or _("Not selected")
                )
            )

        if not self.linked_intervention:
            frappe.throw(_("Linked IR Intervention is required."))

        if not frappe.db.exists(self.ir_intervention, self.linked_intervention):
            frappe.throw(
                _("{0} {1} does not exist.").format(
                    self.ir_intervention,
                    self.linked_intervention,
                )
            )

    def before_submit(self):
        if not self.signed_nta:
            frappe.throw(
                _(
                    "You cannot submit this document until you have attached "
                    "a signed copy of the NTA."
                )
            )


def _safe_value(doc, fieldname, default=None):
    value = doc.get(fieldname)
    return default if value is None else value


def _disciplinary_payload(source) -> dict:
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "position": source.accused_pos,
        "company": source.company,
        "letter_head": _safe_value(source, "letter_head"),
        "complainant": _safe_value(source, "complainant"),
        "compl_name": _safe_value(source, "compl_name", ""),
        "applied_rights": "Disciplinary Hearing",
        "nta_charges": [
            {
                "indiv_charge": (
                    f"({row.code_item}) {row.charge}"
                    if row.code_item
                    else row.charge
                )
            }
            for row in (source.final_charges or [])
            if row.charge
        ],
        # This intentionally uses the tracked history already maintained on
        # Disciplinary Action. Pending and Cancelled matters are excluded.
        "disciplinary_history": [
            {
                "disc_action": row.disc_action,
                "date": row.date,
                "sanction": row.sanction,
                "charges": row.charges,
            }
            for row in (source.previous_disciplinary_outcomes or [])
        ],
        "type_of_incapacity": None,
        "details_of_incapacity": "",
        "previous_incapacity_outcomes": [],
        "performance_details_nta": "",
        "previous_performance_outcomes": [],
    }


def _incapacity_payload(source) -> dict:
    return {
        "employee": source.accused,
        "names": source.accused_name,
        "position": source.accused_pos,
        "company": source.company,
        "letter_head": _safe_value(source, "letter_head"),
        "complainant": _safe_value(source, "complainant"),
        "compl_name": _safe_value(source, "compl_name", ""),
        "applied_rights": "Incapacity",
        "nta_charges": [],
        "disciplinary_history": [],
        "type_of_incapacity": source.type_of_incapacity,
        "details_of_incapacity": source.details_of_incapacity or "",
        "previous_incapacity_outcomes": [
            {
                "incap_proc": row.incap_proc,
                "date": row.date,
                "sanction": row.sanction,
                "incap_details": row.incap_details,
            }
            for row in (source.previous_incapacity_outcomes or [])
        ],
        "performance_details_nta": "",
        "previous_performance_outcomes": [],
    }


def _poor_performance_payload(source) -> dict:
    performance_data = fetch_performance_data(source.name) or {}

    return {
        "employee": source.employee,
        "names": source.employee_name,
        "position": source.employee_designation,
        "company": source.company,
        "letter_head": _safe_value(source, "letter_head"),
        "complainant": _safe_value(source, "complainant"),
        "compl_name": _safe_value(source, "complainant_name", ""),
        "applied_rights": "Poor Performance",
        "nta_charges": [],
        "disciplinary_history": [],
        "type_of_incapacity": None,
        "details_of_incapacity": "",
        "previous_incapacity_outcomes": [],
        "performance_details_nta": source.details_of_poor_performance or "",
        "previous_performance_outcomes": performance_data.get(
            "previous_performance_outcomes", []
        ),
    }


def _get_intervention_payload(source_doctype: str, source_name: str) -> dict:
    if source_doctype not in SUPPORTED_INTERVENTIONS:
        frappe.throw(
            _("Unsupported source DocType: {0}").format(
                source_doctype or _("Not selected")
            )
        )

    if not source_name or not frappe.db.exists(source_doctype, source_name):
        frappe.throw(
            _("{0} {1} was not found.").format(
                source_doctype,
                source_name or "",
            )
        )

    source = frappe.get_doc(source_doctype, source_name)
    source.check_permission("read")

    if source_doctype == "Disciplinary Action":
        return _disciplinary_payload(source)

    if source_doctype == "Incapacity Proceedings":
        return _incapacity_payload(source)

    return _poor_performance_payload(source)


def _source_doctype_from_request(source_name: str, source_doctype: str | None = None) -> str:
    if source_doctype in SUPPORTED_INTERVENTIONS:
        return source_doctype

    request_args = frappe.form_dict.get("args")
    if request_args:
        try:
            parsed_args = json.loads(request_args) if isinstance(request_args, str) else request_args
        except (TypeError, ValueError):
            parsed_args = {}

        requested_doctype = (parsed_args or {}).get("source_doctype")
        if requested_doctype in SUPPORTED_INTERVENTIONS:
            return requested_doctype

    matches = [
        doctype
        for doctype in SUPPORTED_INTERVENTIONS
        if frappe.db.exists(doctype, source_name)
    ]

    if len(matches) == 1:
        return matches[0]

    if not matches:
        frappe.throw(
            _("Could not determine the source DocType for {0}.").format(source_name)
        )

    frappe.throw(
        _(
            "Source name {0} exists in more than one supported DocType. "
            "Use a source-specific NTA Enquiry creation method."
        ).format(source_name)
    )


def _new_nta_enquiry(source_name: str, source_doctype: str):
    _get_intervention_payload(source_doctype, source_name)

    target = frappe.new_doc("NTA Enquiry")
    target.ir_intervention = source_doctype
    target.linked_intervention = source_name
    target.linked_intervention_processed = 0
    return target


@frappe.whitelist()
def create_nta_enquiry(
    source_name: str,
    target_doc=None,
    source_doctype: str | None = None,
):
    resolved_doctype = _source_doctype_from_request(source_name, source_doctype)
    return _new_nta_enquiry(source_name, resolved_doctype).as_dict()


@frappe.whitelist()
def make_nta_enquiry_disciplinary(source_name: str, target_doc=None):
    return _new_nta_enquiry(source_name, "Disciplinary Action").as_dict()


@frappe.whitelist()
def make_nta_enquiry_incapacity(source_name: str, target_doc=None):
    return _new_nta_enquiry(source_name, "Incapacity Proceedings").as_dict()


@frappe.whitelist()
def make_nta_enquiry_poor_performance(source_name: str, target_doc=None):
    return _new_nta_enquiry(source_name, "Poor Performance").as_dict()


@frappe.whitelist()
def fetch_intervention_data(intervention: str, intervention_type: str):
    return _get_intervention_payload(intervention_type, intervention)


@frappe.whitelist()
def fetch_company_letter_head(company: str):
    return _fetch_company_letter_head(company)


@frappe.whitelist()
def fetch_employee_display(employee: str):
    return fetch_employee_name(employee)


def _invite_details_text(doc) -> str:
    """The Charges / Details of Incapacity / Details of Poor Performance block
    for the invite body - whichever applies to this NTA Enquiry's own
    ir_intervention, read directly off the enquiry (it already carries its
    own copy of these fields, fetched from the source case when linked)."""
    if doc.ir_intervention == "Disciplinary Action":
        charges = [row.indiv_charge for row in (doc.nta_charges or []) if row.indiv_charge]
        if not charges:
            return _("Charges: Not yet specified.")
        return _("Charges:") + "\n" + "\n".join(f"- {charge}" for charge in charges)

    if doc.ir_intervention == "Incapacity Proceedings":
        return _("Details of Incapacity:") + "\n" + (doc.details_of_incapacity or _("Not yet specified."))

    if doc.ir_intervention == "Poor Performance":
        return _("Details of Poor Performance:") + "\n" + (doc.performance_details_nta or _("Not yet specified."))

    return ""


def _invite_subject(doc) -> str:
    label = INVITE_SUBJECT_LABEL.get(doc.ir_intervention, doc.ir_intervention or _("Enquiry"))
    accused = f"{doc.names or doc.employee} ({doc.employee})" if doc.employee else (doc.names or "")
    return f"{label} - {doc.company or ''} // {accused}"


def _invite_attendees(doc) -> tuple[list[dict], list[str]]:
    """(attendees, skipped_labels) - an Employee is skipped (rather than
    failing the whole send) when they have no resolvable email, so the other
    party still gets their invite."""
    attendees = []
    skipped = []
    for employee, fallback_name, label in (
        (doc.complainant, doc.compl_name, _("Complainant")),
        (doc.chairperson, doc.chairperson_name, _("Chairperson")),
    ):
        if not employee:
            continue
        email = employee_email(employee)
        if not email:
            skipped.append(label)
            continue
        attendees.append({"email": email, "name": fallback_name or employee})
    return attendees, skipped


@frappe.whitelist()
def send_calendar_invite(nta_enquiry: str):
    """Email a client-independent (.ics, METHOD:REQUEST) calendar invite to
    the Complainant and Chairperson for this NTA Enquiry's hearing - works by
    plain email attachment, so it renders in Outlook/Exchange, Google
    Calendar, Apple Calendar/iCal and anything else that understands
    iCalendar, with no client-specific API integration required."""
    doc = frappe.get_doc("NTA Enquiry", nta_enquiry)
    doc.check_permission("read")

    missing = [
        label
        for value, label in (
            (doc.hearing_date_time, _("Date and Time")),
            (doc.venue, _("Venue")),
            (doc.complainant, _("Complainant")),
            (doc.chairperson, _("Chairperson")),
        )
        if not value
    ]
    if missing:
        frappe.throw(_("Please set {0} before sending a calendar invite.").format(", ".join(missing)))

    attendees, skipped = _invite_attendees(doc)
    if not attendees:
        frappe.throw(
            _("Neither the Complainant nor the Chairperson has a usable email address on file.")
        )

    start = get_datetime(doc.hearing_date_time)
    end = start + timedelta(minutes=DEFAULT_INVITE_DURATION_MINUTES)
    subject = _invite_subject(doc)
    details_text = _invite_details_text(doc)
    venue = doc.venue or ""
    when_display = format_datetime(start, "EEEE, d MMMM y 'at' HH:mm")

    description_lines = [
        f"{_('Venue')}: {venue}",
        f"{_('Date & Time')}: {when_display}",
        "",
        details_text,
    ]
    description = "\n".join(description_lines)

    # The same "main"/shared account frappe.sendmail() itself falls back to
    # whenever no explicit sender is given (EmailAccount.default_sender) - used
    # here as the ICS ORGANIZER too, so the invite consistently comes from
    # the site's configured outgoing account rather than whichever staff
    # member happened to click the button.
    from frappe.email.doctype.email_account.email_account import EmailAccount

    outgoing_account = EmailAccount.find_default_outgoing()
    organizer_email = outgoing_account.email_id if outgoing_account else frappe.session.user
    organizer_name = outgoing_account.name if outgoing_account else "Industrial Relations"

    sequence = frappe.utils.cint(doc.calendar_invite_sequence)

    ics_bytes = ics.build_ics_invite(
        uid=ics.new_uid(doc),
        sequence=sequence,
        summary=subject,
        description=description,
        location=venue,
        start=start,
        end=end,
        organizer_email=organizer_email,
        organizer_name=organizer_name,
        attendees=attendees,
    )

    url = frappe.utils.get_url(doc.get_url())

    for attendee in attendees:
        message = EMAIL_STYLE_BLOCK
        message += greeting(attendee["name"])
        message += intro(f"You are invited to a {INVITE_SUBJECT_LABEL.get(doc.ir_intervention, doc.ir_intervention)}.")
        message += intro(f"<b>{_('Venue')}:</b> {frappe.utils.escape_html(venue)}")
        message += intro(f"<b>{_('Date &amp; Time')}:</b> {frappe.utils.escape_html(when_display)}")
        message += intro(frappe.utils.escape_html(details_text).replace("\n", "<br>"))
        message += intro(_("A calendar invite is attached - open it to add this to your calendar."))
        message += view_link(url)
        message += signoff()

        frappe.sendmail(
            recipients=[attendee["email"]],
            subject=subject,
            message=message,
            header=email_header(subject, "urgent"),
            reference_doctype=doc.doctype,
            reference_name=doc.name,
            attachments=[
                {
                    "fname": f"{frappe.scrub(subject)}.ics",
                    "fcontent": ics_bytes,
                    "content_type": "text/calendar",
                }
            ],
        )

    frappe.db.set_value("NTA Enquiry", doc.name, "calendar_invite_sequence", sequence + 1, update_modified=False)

    return {
        "sent_to": [a["email"] for a in attendees],
        "skipped": skipped,
    }
