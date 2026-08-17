# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Shared presentation helpers for every IR app notification email.

Every email in this app is sent via frappe.sendmail(). Frappe already ships a
complete transactional-email design (frappe/templates/emails/standard.html +
email.bundle.scss): a rounded white card on a light canvas, an optional brand
masthead, and a bold title row with a coloured status dot - but it only
activates when you actually pass `header=[title, indicator_colour]` to
sendmail(). None of this app's controllers did, so every IR notification has
been rendering as bare, unstyled HTML outside that card the whole time.

`email_header()` below turns that on. `EMAIL_STYLE_BLOCK` layers one small,
consistent accent on top - a table treatment matching the deep red (#b40000)
banner rule already used across every IR Print Format (Schedule of Offences
Standard, etc.), so a report table looks like it belongs to the same app as
the documents it links to. Frappe sends every email through Premailer at
send time (frappe.email.email_body.inline_style_in_html), which inlines any
<style> block present in the message body - so this can be written as normal
CSS, not hand-rolled inline `style=` attributes on every cell.
"""

import frappe

IR_ACCENT = "#b40000"

# Maps to Frappe's own .indicator-{colour} classes (email.bundle.scss) - the same
# dot frappe/hrms use on their own transactional emails (e.g. an overdue Task).
INDICATOR_BY_SEVERITY = {
    "urgent": "red",  # requires action now: overdue, already-lapsed, a new case
    "attention": "orange",  # approaching a deadline, worth a look this week
    "info": "blue",  # administrative / already actioned, for the record
}

EMAIL_STYLE_BLOCK = f"""
<style>
  .ir-email-intro {{ margin: 0 0 16px; color: #525252; }}
  .ir-email-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  .ir-email-table th {{
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.01em;
    color: #525252;
    background-color: #f5f5f5;
    padding: 8px 10px;
    border-bottom: 2px solid {IR_ACCENT};
  }}
  .ir-email-table td {{
    padding: 8px 10px;
    font-size: 13px;
    line-height: 1.45;
    vertical-align: top;
    border-bottom: 1px solid #ededed;
    word-wrap: break-word;
  }}
  .ir-email-table tbody tr:last-child td {{ border-bottom: none; }}
  .ir-email-table tbody tr:nth-child(even) td {{ background-color: #fafafa; }}
  .ir-email-empty {{
    padding: 16px;
    color: #999999;
    font-size: 13px;
    text-align: center;
    background-color: #f8f8f8;
    border-radius: 8px;
  }}
  .ir-email-signoff {{ margin-top: 20px; color: #525252; }}
</style>
"""


def email_header(title, severity="info"):
    """The (title, indicator_colour) pair frappe.sendmail(header=...) expects -
    this is what actually turns on Frappe's rounded-card email chrome."""
    return [title, INDICATOR_BY_SEVERITY.get(severity, "blue")]


def greeting(first_name):
    return f'<p class="ir-email-intro">Dear {frappe.utils.escape_html(first_name or "Valued IR Team")},</p>'


def intro(text):
    return f'<p class="ir-email-intro">{text}</p>'


def empty_state(message):
    return f'<div class="ir-email-empty">{message}</div>'


def signoff():
    return '<p class="ir-email-signoff">Kind regards,<br>Industrial Relations</p>'


def view_link(url, label="View in the system"):
    """Frappe's own .btn/.btn-primary classes (email.bundle.scss) - used exactly
    the way Frappe's core transactional emails (password reset, workflow action,
    etc.) link back to a record, instead of a bare <a> tag."""
    return f'<p><a class="btn btn-primary" href="{url}">{frappe.utils.escape_html(label)}</a></p>'
