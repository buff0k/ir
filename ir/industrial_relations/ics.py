# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Minimal RFC 5545 iCalendar (.ics) builder for a single-event meeting
invite - deliberately dependency-free (no `icalendar` package) since a
METHOD:REQUEST VEVENT attached to a plain email is already the universal,
client-independent way to deliver a calendar invite: Outlook/Exchange, Google
Calendar, Apple Calendar/iCal and Thunderbird all recognise a `.ics`
attachment without any client-specific API integration (Graph, Google
Calendar API, etc.).
"""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import frappe
from frappe.utils import get_datetime, get_system_timezone, now_datetime


def _fold(line: str) -> str:
    """RFC 5545 line folding: no physical line may exceed 75 octets; a
    continuation line starts with a single space."""
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    parts = []
    while len(encoded) > 75:
        cut = 75
        # Never split a multi-byte UTF-8 sequence in half.
        while cut > 0 and (encoded[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(encoded[:cut].decode("utf-8"))
        encoded = encoded[cut:]
    parts.append(encoded.decode("utf-8"))
    return "\r\n ".join(parts)


def _escape_text(value) -> str:
    """Escape a value for use in an ICS TEXT property (SUMMARY, DESCRIPTION,
    LOCATION, ...) per RFC 5545 §3.3.11."""
    value = str(value or "")
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _to_utc(value) -> datetime.datetime:
    """A Frappe Datetime value (naive, wall-clock time in the site's own
    timezone) converted to an aware UTC datetime."""
    dt = get_datetime(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(get_system_timezone()))
    return dt.astimezone(ZoneInfo("UTC"))


def _format_utc(dt) -> str:
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics_invite(
    *,
    uid: str,
    sequence: int,
    summary: str,
    description: str,
    location: str,
    start,
    end,
    organizer_email: str,
    organizer_name: str,
    attendees: list[dict],
    method: str = "REQUEST",
) -> bytes:
    """Build a single-VEVENT .ics calendar invite.

    `attendees` is a list of {"email": ..., "name": ...} dicts. `uid` should
    be stable across re-sends of the same meeting (e.g. derived from the
    source document's name) so a calendar client updates the existing event
    on the recipient's calendar instead of creating a duplicate; bump
    `sequence` on every re-send of a changed event, per RFC 5545 §3.8.7.4.
    """
    start_utc = _to_utc(start)
    end_utc = _to_utc(end)
    dtstamp = _format_utc(now_datetime())

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//buff0k//Industrial Relations//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{method}",
        "BEGIN:VEVENT",
        f"UID:{_escape_text(uid)}",
        f"SEQUENCE:{int(sequence)}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{_format_utc(start_utc)}",
        f"DTEND:{_format_utc(end_utc)}",
        f"SUMMARY:{_escape_text(summary)}",
        f"DESCRIPTION:{_escape_text(description)}",
        f"LOCATION:{_escape_text(location)}",
        f"ORGANIZER;CN={_escape_text(organizer_name)}:mailto:{organizer_email}",
    ]

    for attendee in attendees:
        email = attendee.get("email")
        if not email:
            continue
        name = _escape_text(attendee.get("name") or email)
        lines.append(
            "ATTENDEE;CUTYPE=INDIVIDUAL;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;"
            f"RSVP=TRUE;CN={name}:mailto:{email}"
        )

    lines += [
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
        "END:VEVENT",
        "END:VCALENDAR",
    ]

    folded = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    return folded.encode("utf-8")


def new_uid(doc) -> str:
    """A stable per-document UID, namespaced by site so two sites' events
    never collide even if their document names do."""
    site = frappe.local.site or "ir"
    return f"{doc.doctype}-{doc.name}@{site}".replace(" ", "-")
