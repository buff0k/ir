# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Contract of Employment Template: wording, dynamic clauses and rendering.

Contract of Employment imports the wording engine below to render its own
contracts: it builds a ContractContext (values, rows, conditions) for one
employee and calls render_contract().

Storage
-------
The template editor (ir/public/js/coe_template_editor.bundle.js) stores the
wording in `contract_wording` as a Quill Delta ({"ops": [...]}); the Markdown
tab (`contract_markdown`) is the same content in Contract Markdown, kept in
step on every save. Every line is one of:

- heading: a numbered section heading (1, 2, 3 ...)
- clause:  a numbered clause; its indent (0..MAX_INDENT) is its depth below
           the heading, so indent 0 -> 4.1, indent 1 -> 4.1.1, and so on
- text:    unnumbered wording; never affects numbering

Inline content is text (bold/italic/underline only), variables
({"coe-var": key}) and cross-references ({"coe-ref": {"anchor", "label"}})
that resolve to the number of the heading/clause carrying that anchor.

Dynamic clauses
---------------
Each line can carry, independently:

- Show when ({"coe-when": key}): the line appears only in contracts where that
  condition holds - e.g. "shift:fixed", "pay:hourly",
  "deduction:Employee Provident Fund". Conditions are decided per contract,
  never per template, so one template serves every pay basis, roster and
  component mix.
- Repeat for each ({"coe-repeat": kind}): the line is written once per row of
  that kind (each earning, deduction, working day or shift) at the same depth,
  so every row becomes its own numbered sub-paragraph. Row variables
  ({{earning_label}}, {{day_start}} ...) belong on repeat lines. A repeat with
  no rows disappears.

Hidden lines are dropped and repeats expanded before numbering, so the
numbers always close up.

Numbering rule (shared with the editor's CSS counters, keep them in step):
a heading increments the section number and clears every clause level; a
clause at indent k increments level k and clears every level below it; text
lines change nothing.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate, now_datetime


class ContractofEmploymentTemplate(Document):
	def autoname(self):
		# Amendments never reach here - Frappe names them "<name>-1" first.
		contract_name = (self.contract_name or "").strip()
		if not contract_name:
			frappe.throw(_("Contract of Employment Template Name is required before naming."))

		# creation is stamped before naming on insert; DD-MM-YYYY matches
		# Contract of Employment's own autoname.
		created = getdate(self.creation or now_datetime()).strftime("%d-%m-%Y")
		candidate_name = f"{contract_name} - {created}"

		if frappe.db.exists(self.doctype, candidate_name):
			frappe.throw(
				_(
					"A Contract of Employment Template named {0} already exists. Amend the existing "
					"template instead, or use a different name."
				).format(frappe.bold(candidate_name)),
				title=_("Duplicate Contract of Employment Template"),
			)

		self.contract_name = contract_name
		self.name = candidate_name

	def validate(self):
		lines = self.lines_from_input()
		self.raise_for(validate_lines(lines))
		# Store only what the editor can produce (strips pasted formats/embeds
		# and duplicate anchors), and keep the Markdown tab in step.
		self.contract_wording = json.dumps(to_delta(lines), ensure_ascii=False, separators=(",", ":"))
		self.contract_markdown = to_markdown(lines)

	def lines_from_input(self) -> list[Line]:
		"""The editor wins, unless only the Markdown tab was edited."""
		markdown_edited = self.has_value_changed("contract_markdown") and (self.contract_markdown or "").strip()
		wording_edited = self.has_value_changed("contract_wording") and load_delta(self.contract_wording)["ops"]
		if markdown_edited and not wording_edited:
			return parse_markdown(self.contract_markdown)
		return parse_wording(self.contract_wording)

	def before_submit(self):
		lines = parse_wording(self.contract_wording)
		if not any(line.kind in ("heading", "clause") for line in lines):
			frappe.throw(_("Add the contract wording before submitting."))
		self.raise_for(validate_lines(lines, for_submit=True))

	@staticmethod
	def raise_for(errors):
		if errors:
			frappe.throw("<br>".join(errors), title=_("Contract Wording"))


@frappe.whitelist()
def get_editor_config():
	frappe.has_permission("Contract of Employment Template", "read", throw=True)
	earnings, deductions = salary_component_options()
	return {
		"max_indent": MAX_INDENT,
		"variables": [
			{
				"key": v.key,
				"label": v.label,
				"group": v.group,
				"repeat": v.repeat,
				"description": v.description,
			}
			for v in VARIABLES
		],
		"conditions": [
			{"key": c.key, "label": c.label, "group": c.group, "exclusive": c.exclusive, "description": c.description}
			for c in all_conditions()
		],
		"repeats": [{"key": r.key, "label": r.label, "description": r.description} for r in REPEATS],
		"earning_components": earnings,
		"deduction_components": deductions,
	}


@frappe.whitelist()
def preview_wording(contract_wording=None, scenario=None):
	"""Render the wording for a sample scenario (see preview_context)."""
	frappe.has_permission("Contract of Employment Template", "read", throw=True)
	scenario = frappe.parse_json(scenario) if isinstance(scenario, str) else (scenario or {})
	if scenario.get("shift_design"):
		frappe.has_permission("Shift Design", "read", doc=scenario["shift_design"], throw=True)
	return render_contract(parse_wording(contract_wording), preview_context(scenario))


@frappe.whitelist()
def wording_to_markdown(contract_wording=None):
	frappe.has_permission("Contract of Employment Template", "read", throw=True)
	return to_markdown(parse_wording(contract_wording))


@frappe.whitelist()
def markdown_to_wording(contract_markdown=None):
	"""Markdown tab -> editor content; problems come back as messages, not errors,
	so half-typed Markdown never interrupts the user."""
	frappe.has_permission("Contract of Employment Template", "read", throw=True)
	lines = parse_markdown(contract_markdown or "")
	return {"contract_wording": json.dumps(to_delta(lines), ensure_ascii=False), "errors": validate_lines(lines)}


# ---- Template wording engine ----
# Shared with Contract of Employment, which renders its contracts through it.

MAX_INDENT = 24
INLINE_FORMATS = ("bold", "italic", "underline")
VAR_EMBED = "coe-var"
REF_EMBED = "coe-ref"
ANCHOR_ATTR = "coe-anchor"
WHEN_ATTR = "coe-when"
REPEAT_ATTR = "coe-repeat"


@dataclass(frozen=True)
class TemplateVariable:
	key: str
	label: str
	group: str
	# How Contract of Employment formats the raw value (see format_value):
	# text | long_date | rand_words | int_words | number | time
	fmt: str = "text"
	# Row variables only make sense on a line repeating this kind.
	repeat: str | None = None
	# The `{placeholder}` the legacy Contract Section wording used.
	legacy_token: str | None = None
	description: str = ""


@dataclass(frozen=True)
class TemplateRepeat:
	key: str
	label: str
	description: str = ""


REPEATS: tuple[TemplateRepeat, ...] = (
	TemplateRepeat("earnings", "Earning", "Each allowance/earning on the contract other than the basic rate."),
	TemplateRepeat("deductions", "Deduction", "Each deduction on the contract (UIF, PAYE, Provident Fund ...)."),
	TemplateRepeat("working_days", "Working Day", "Each working day of a fixed shift (from the Shift Design)."),
	TemplateRepeat("shifts", "Shift", "Each shift in a rotating roster (from the Shift Design)."),
)
REPEATS_BY_KEY = {r.key: r for r in REPEATS}

VARIABLES: tuple[TemplateVariable, ...] = (
	# Employee
	TemplateVariable("employee_name", "Employee Name", "Employee", legacy_token="{employee_name}"),
	TemplateVariable("employee_number", "Employee Number", "Employee", legacy_token="{employee_number}"),
	TemplateVariable("id_number", "RSA ID / Passport No.", "Employee", legacy_token="{custom_id_number}"),
	TemplateVariable("current_address", "Current Address", "Employee", legacy_token="{current_address}"),
	TemplateVariable("designation", "Designation", "Employee", legacy_token="{designation}"),
	TemplateVariable("branch", "Site", "Employee", legacy_token="{branch}"),
	TemplateVariable("company", "Company", "Employee", legacy_token="{company}"),
	TemplateVariable(
		"date_of_joining", "Date of Joining", "Employee", fmt="long_date", legacy_token="{date_of_joining}"
	),
	# Contract
	TemplateVariable("contract_type", "Contract Template", "Contract", legacy_token="{contract_type}"),
	TemplateVariable("start_date", "Start Date", "Contract", fmt="long_date", legacy_token="{start_date}"),
	TemplateVariable("end_date", "End Date", "Contract", fmt="long_date", legacy_token="{end_date}"),
	TemplateVariable("project", "Project", "Contract", legacy_token="{project}"),
	TemplateVariable(
		"retirement_age", "Retirement Age", "Contract", fmt="int_words", legacy_token="{retirement_age}"
	),
	TemplateVariable("retirement_date", "Retirement Date", "Contract", fmt="long_date"),
	TemplateVariable("restraint_period", "Restraint Period", "Contract", legacy_token="{restraint_period}"),
	TemplateVariable(
		"restraint_territory", "Restraint Territory", "Contract", legacy_token="{restraint_territory}"
	),
	# Remuneration
	TemplateVariable(
		"rate",
		"Rate of Pay",
		"Remuneration",
		fmt="rand_words",
		legacy_token="{rate}",
		description="Basic hourly or monthly rate, e.g. 1 500.00 (One Thousand Five Hundred).",
	),
	TemplateVariable(
		"earning_label", "Earning Name", "Each Earning", repeat="earnings", description="e.g. Housing Allowance"
	),
	TemplateVariable("earning_amount", "Earning Amount", "Each Earning", fmt="rand_words", repeat="earnings"),
	TemplateVariable(
		"earning_basis", "Earning Basis", "Each Earning", repeat="earnings", description="per month / per hour"
	),
	TemplateVariable("deduction_label", "Deduction Name", "Each Deduction", repeat="deductions"),
	TemplateVariable(
		"deduction_amount",
		"Deduction Amount",
		"Each Deduction",
		repeat="deductions",
		description="An amount or a percentage, as on the contract.",
	),
	# Working Hours
	TemplateVariable("day_name", "Day", "Each Working Day", repeat="working_days", description="e.g. Monday"),
	TemplateVariable("day_start", "Day Start Time", "Each Working Day", fmt="time", repeat="working_days"),
	TemplateVariable("day_end", "Day End Time", "Each Working Day", fmt="time", repeat="working_days"),
	TemplateVariable("shift_name", "Shift Name", "Each Shift", repeat="shifts"),
	TemplateVariable("shift_start", "Shift Start Time", "Each Shift", fmt="time", repeat="shifts"),
	TemplateVariable("shift_end", "Shift End Time", "Each Shift", fmt="time", repeat="shifts"),
	TemplateVariable(
		"ordinary_hours_limit",
		"Ordinary Hours Limit",
		"Working Hours",
		fmt="number",
		description="Ordinary hours per pay period before overtime, from the Shift Design.",
	),
	TemplateVariable("shift_cycle_length", "Shift Cycle Length (days)", "Working Hours", fmt="int_words"),
	TemplateVariable("shift_team_count", "Number of Shift Teams", "Working Hours", fmt="int_words"),
)
VARIABLES_BY_KEY = {v.key: v for v in VARIABLES}

# Legacy placeholders that are now rows: the 5 allowance slots are the
# earnings repeat, the 14 per-day times are the working_days repeat.
LEGACY_TOKENS_SUPERSEDED = {
	**{f"{{allowance_{n}}}": "earnings" for n in range(1, 6)},
	**{
		f"{{{day}_{edge}}}": "working_days"
		for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
		for edge in ("start", "end")
	},
}


@dataclass(frozen=True)
class TemplateCondition:
	key: str
	label: str
	group: str
	# Exclusive groups are alternatives: every contract is exactly one of them.
	exclusive: bool = True
	description: str = ""


STATIC_CONDITIONS: tuple[TemplateCondition, ...] = (
	TemplateCondition("shift:fixed", "Fixed shift", "Working Hours", description="Same hours every week."),
	TemplateCondition("shift:rotating", "Rotating shift", "Working Hours", description="Hours follow a roster."),
	TemplateCondition("pay:hourly", "Hourly rate", "Pay Basis"),
	TemplateCondition("pay:monthly", "Monthly salary", "Pay Basis"),
	TemplateCondition("allowances:any", "Has allowances", "Allowances", description="At least one earning row."),
	TemplateCondition("allowances:none", "No allowances", "Allowances"),
	TemplateCondition("retirement:yes", "Has a retirement age", "Retirement"),
	TemplateCondition("retirement:no", "No retirement age", "Retirement"),
)
EARNING_PREFIX = "earning:"
DEDUCTION_PREFIX = "deduction:"


def salary_component_options() -> tuple[list[str], list[str]]:
	"""Earning components (excluding Basic/Wages, which is the rate) and
	deduction components a template can condition on."""
	from ir.ir_setup.doctype.ir_payroll_cost_settings.ir_payroll_cost_settings import (
		get_basic_wage_components,
	)

	basic = get_basic_wage_components()
	rows = frappe.get_all(
		"Salary Component",
		filters={"type": ["in", ["Earning", "Deduction"]], "disabled": 0},
		fields=["name", "type"],
		order_by="name",
	)
	earnings = [r.name for r in rows if r.type == "Earning" and r.name not in basic]
	deductions = [r.name for r in rows if r.type == "Deduction"]
	return earnings, deductions


def all_conditions() -> list[TemplateCondition]:
	earnings, deductions = salary_component_options()
	return [
		*STATIC_CONDITIONS,
		*(
			TemplateCondition(f"{EARNING_PREFIX}{c}", _("Has {0}").format(c), "Earnings", exclusive=False)
			for c in earnings
		),
		*(
			TemplateCondition(f"{DEDUCTION_PREFIX}{c}", _("Has {0}").format(c), "Deductions", exclusive=False)
			for c in deductions
		),
	]


def is_known_condition(key: str) -> bool:
	if any(c.key == key for c in STATIC_CONDITIONS):
		return True
	for prefix, doctype_type in ((EARNING_PREFIX, "Earning"), (DEDUCTION_PREFIX, "Deduction")):
		if key.startswith(prefix):
			return bool(frappe.db.exists("Salary Component", {"name": key[len(prefix) :], "type": doctype_type}))
	return False


@dataclass
class ContractContext:
	"""What one contract supplies to the template. Every value is ready-to-insert
	HTML (see format_value); rows are keyed by repeat kind; conditions are the
	keys that hold for this contract."""

	values: dict[str, str] = field(default_factory=dict)
	rows: dict[str, list[dict[str, str]]] = field(default_factory=dict)
	conditions: set[str] = field(default_factory=set)
	# What a missing value prints as - the legacy contract blanks.
	blank: str = "_____________________"
	blank_amount: str = "__________"


# ---- lines ----


@dataclass
class Segment:
	kind: str  # text | var | ref
	value: Any
	attrs: dict = field(default_factory=dict)


@dataclass
class Line:
	kind: str  # heading | clause | text
	indent: int = 0
	anchor: str | None = None
	segments: list[Segment] = field(default_factory=list)
	when: str | None = None  # condition key; None = every contract
	repeat: str | None = None  # repeat kind; None = written once
	row: dict | None = None  # set on the copies render_contract() expands

	def is_blank(self) -> bool:
		return all(s.kind == "text" and not s.value.strip() for s in self.segments)


def load_delta(value) -> dict:
	if not value:
		return {"ops": []}
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			frappe.throw(_("Contract Wording is not valid editor content."))
	if isinstance(value, list):
		value = {"ops": value}
	if not isinstance(value, dict) or not isinstance(value.get("ops"), list):
		frappe.throw(_("Contract Wording is not valid editor content."))
	return value


def parse_wording(value) -> list[Line]:
	"""Delta -> lines, dropping every format and embed the template doesn't support."""
	lines: list[Line] = []
	segments: list[Segment] = []

	for op in load_delta(value)["ops"]:
		if not isinstance(op, dict):
			continue
		insert = op.get("insert")
		attrs = op.get("attributes") or {}
		if isinstance(insert, str):
			inline = {k: True for k in INLINE_FORMATS if attrs.get(k)}
			parts = insert.split("\n")
			for i, part in enumerate(parts):
				if part:
					segments.append(Segment("text", _clean_text(part), inline))
				if i < len(parts) - 1:
					lines.append(_make_line(attrs, segments))
					segments = []
		elif isinstance(insert, dict):
			if isinstance(insert.get(VAR_EMBED), str):
				segments.append(Segment("var", insert[VAR_EMBED]))
			elif isinstance(insert.get(REF_EMBED), dict):
				ref = insert[REF_EMBED]
				segments.append(
					Segment("ref", {"anchor": str(ref.get("anchor") or ""), "label": str(ref.get("label") or "")})
				)
	if segments:
		lines.append(_make_line({}, segments))
	return lines


def _clean_text(text: str) -> str:
	return text.replace("\t", " ").replace("\u00a0", " ")


def _make_line(attrs: dict, segments: list[Segment]) -> Line:
	if attrs.get("header"):
		kind = "heading"
	elif attrs.get("list") == "ordered":
		kind = "clause"
	else:
		kind = "text"
	indent = 0 if kind == "heading" else max(0, min(cint(attrs.get("indent")), MAX_INDENT))
	return Line(
		kind,
		indent,
		str(attrs[ANCHOR_ATTR]) if attrs.get(ANCHOR_ATTR) else None,
		segments,
		str(attrs[WHEN_ATTR]) if attrs.get(WHEN_ATTR) else None,
		str(attrs[REPEAT_ATTR]) if attrs.get(REPEAT_ATTR) else None,
	)


def to_delta(lines: list[Line]) -> dict:
	"""Lines -> the canonical Delta the editor loads. Duplicate anchors keep their first line."""
	ops: list[dict] = []
	seen_anchors: set[str] = set()
	for line in lines:
		for seg in line.segments:
			if seg.kind == "text":
				op = {"insert": seg.value}
				if seg.attrs:
					op["attributes"] = dict(seg.attrs)
				ops.append(op)
			elif seg.kind == "var":
				ops.append({"insert": {VAR_EMBED: seg.value}})
			elif seg.kind == "ref":
				ops.append({"insert": {REF_EMBED: dict(seg.value)}})
		attrs: dict = {}
		if line.kind == "heading":
			attrs["header"] = 1
		elif line.kind == "clause":
			attrs["list"] = "ordered"
		if line.indent and line.kind != "heading":
			attrs["indent"] = line.indent
		if line.anchor and line.anchor not in seen_anchors:
			attrs[ANCHOR_ATTR] = line.anchor
			seen_anchors.add(line.anchor)
		if line.when:
			attrs[WHEN_ATTR] = line.when
		if line.repeat:
			attrs[REPEAT_ATTR] = line.repeat
		op = {"insert": "\n"}
		if attrs:
			op["attributes"] = attrs
		ops.append(op)
	return {"ops": ops}


def number_lines(lines: list[Line]) -> list[str | None]:
	numbers: list[str | None] = []
	section = 0
	levels: list[int] = []
	for line in lines:
		if line.kind == "heading":
			section += 1
			levels = []
			numbers.append(str(section))
		elif line.kind == "clause":
			k = line.indent
			levels = (levels + [0] * (k + 1))[: k + 1]
			levels[k] += 1
			numbers.append(".".join(str(n) for n in (section, *levels)))
		else:
			numbers.append(None)
	return numbers


def validate_lines(lines: list[Line], for_submit: bool = False) -> list[str]:
	"""Human-readable problems. Structural ones always block a save; the
	drafting ones (empty or orphan clauses) only block submit."""
	errors: list[str] = []
	numbers = number_lines(lines)
	anchored = {line.anchor: (line, number) for line, number in zip(lines, numbers) if line.anchor}
	seen_heading = False
	known_conditions: dict[str, bool] = {}

	for line, number in zip(lines, numbers):
		where = _("line {0}").format(number) if number else _("an unnumbered line")
		if line.when:
			if line.when not in known_conditions:
				known_conditions[line.when] = is_known_condition(line.when)
			if not known_conditions[line.when]:
				errors.append(_("Unknown condition {0} on {1}.").format(frappe.bold(line.when), where))
		if line.repeat and line.repeat not in REPEATS_BY_KEY:
			errors.append(_("Unknown repeat {0} on {1}.").format(frappe.bold(line.repeat), where))
		for seg in line.segments:
			if seg.kind == "var":
				var = VARIABLES_BY_KEY.get(seg.value)
				if not var:
					errors.append(_("Unknown variable {0} on {1}.").format(frappe.bold(seg.value), where))
				elif var.repeat and var.repeat != line.repeat:
					errors.append(
						_("{0} only works on a line set to Repeat for each {1} ({2}).").format(
							frappe.bold(var.label), REPEATS_BY_KEY[var.repeat].label, where
						)
					)
			elif seg.kind == "ref":
				target = anchored.get(seg.value["anchor"])
				if not target:
					errors.append(
						_("The reference to {0} on {1} points to a heading or clause that no longer exists.").format(
							frappe.bold(seg.value["label"] or "?"), where
						)
					)
				elif not target[1]:
					errors.append(
						_("The reference to {0} on {1} points to unnumbered text.").format(
							frappe.bold(seg.value["label"] or "?"), where
						)
					)

		if line.kind == "heading":
			seen_heading = True
		if for_submit and line.kind in ("heading", "clause"):
			if line.is_blank():
				errors.append(_("Numbered line {0} is empty.").format(number))
			if line.kind == "clause" and not seen_heading:
				errors.append(_("Clause {0} comes before the first Heading.").format(number))
	return errors


# ---- rendering ----


def resolve_lines(lines: list[Line], context: ContractContext) -> list[Line]:
	"""Drop lines whose condition doesn't hold, then write each repeat line once per row."""
	resolved: list[Line] = []
	for line in lines:
		if line.when and line.when not in context.conditions:
			continue
		if not line.repeat:
			resolved.append(line)
			continue
		for i, row in enumerate(context.rows.get(line.repeat) or []):
			resolved.append(replace(line, anchor=line.anchor if i == 0 else None, row=row))
	return resolved


def render_contract(lines: list[Line], context: ContractContext) -> str:
	"""Render to the same number | wording table layout legacy contracts use."""
	lines = resolve_lines(lines, context)
	numbers = number_lines(lines)
	anchors = {line.anchor: number for line, number in zip(lines, numbers) if line.anchor and number}

	rows = []
	seen_heading = False
	for line, number in zip(lines, numbers):
		if line.kind == "text" and line.is_blank():
			continue
		content = "".join(_render_segment(seg, line, context, anchors) for seg in line.segments)
		if line.kind == "heading":
			seen_heading = True
			rows.append(f"<tr><td><b>{number}</b></td><td><b>{content}</b></td></tr>")
		elif line.kind == "clause":
			rows.append(f"<tr><td><b>{number}</b></td><td>{content}</td></tr>")
		elif seen_heading:
			rows.append(f"<tr><td></td><td>{content}</td></tr>")
		else:
			rows.append(f'<tr><td colspan="2">{content}</td></tr>')
	return '<table border="0" cellpadding="5" cellspacing="0">' + "".join(rows) + "</table>"


def _render_segment(seg: Segment, line: Line, context: ContractContext, anchors: dict[str, str]) -> str:
	if seg.kind == "var":
		var = VARIABLES_BY_KEY.get(seg.value)
		if not var:
			return ""
		source = line.row if var.repeat else context.values
		blank = context.blank_amount if var.fmt in ("rand_words", "int_words", "number") else context.blank
		return f"<b>{(source or {}).get(var.key) or blank}</b>"
	if seg.kind == "ref":
		return html.escape(anchors.get(seg.value["anchor"], "??"))
	out = html.escape(seg.value)
	if seg.attrs.get("bold"):
		out = f"<b>{out}</b>"
	if seg.attrs.get("italic"):
		out = f"<i>{out}</i>"
	if seg.attrs.get("underline"):
		out = f"<u>{out}</u>"
	return out


# ---- value formatting (what Contract of Employment will use to fill a context) ----


def format_value(var: TemplateVariable, raw) -> str:
	"""Raw contract value -> the HTML a contract shows, per the variable's format."""
	if raw is None or raw == "":
		return ""
	if var.fmt == "long_date":
		return html.escape(long_date(raw))
	if var.fmt == "rand_words":
		amount = flt(raw)
		return html.escape(f"{amount:,.2f}".replace(",", " ") + f" ({number_to_words(amount)})")
	if var.fmt == "int_words":
		return html.escape(f"{cint(raw)} ({number_to_words(cint(raw))})")
	if var.fmt == "number":
		return html.escape(f"{flt(raw):g}")
	if var.fmt == "time":
		return html.escape(str(raw)[:5])
	return html.escape(str(raw))


def long_date(value) -> str:
	"""'Monday, the 18th of November 2024' - the legacy contract date wording."""
	d = getdate(value)
	suffix = "th" if 11 <= d.day % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d.day % 10, "th")
	return d.strftime(f"%A, the {d.day}{suffix} of %B %Y")


_UNITS = ("Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine")
_TEENS = ("Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen")
_TENS = ("Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety")


def number_to_words(number) -> str:
	"""Legacy contract wording for amounts: whole numbers in words, decimals read
	digit by digit without trailing zeros ('28.80' -> 'Twenty-Eight Point Eight',
	'28.05' -> '... Point Zero Five'). Whole amounts never get a 'Point Zero'
	(the legacy float bug)."""
	amount = round(flt(number), 2)
	whole = int(amount)
	decimals = f"{round((amount - whole) * 100):02d}".rstrip("0")
	words = _int_words(whole)
	if decimals:
		words += " Point " + " ".join(_UNITS[int(d)] for d in decimals)
	return words


def _int_words(n: int) -> str:
	if n < 10:
		return _UNITS[n]
	if n < 20:
		return _TEENS[n - 10]
	if n < 100:
		return _TENS[n // 10 - 2] + ("" if n % 10 == 0 else "-" + _UNITS[n % 10])
	if n < 1000:
		return _UNITS[n // 100] + " Hundred" + ("" if n % 100 == 0 else " and " + _int_words(n % 100))
	for size, name in ((1_000_000_000, "Billion"), (1_000_000, "Million"), (1000, "Thousand")):
		if n >= size:
			return _int_words(n // size) + f" {name}" + ("" if n % size == 0 else " " + _int_words(n % size))
	return str(n)


# ---- preview ----


def preview_context(scenario: dict) -> ContractContext:
	"""Sample contract for Preview: every value is a [Label] placeholder; the
	scenario picks pay basis, retirement, earnings/deductions and working hours
	(a real Shift Design supplies its own days/shifts and style)."""
	from ir.industrial_relations.doctype.shift_design.shift_design import CONTRACT_STYLE_CONDITIONS

	def label(text: str) -> str:
		return f'<span class="coe-preview-var">[{html.escape(text)}]</span>'

	context = ContractContext(values={v.key: label(v.label) for v in VARIABLES if not v.repeat})
	conditions = context.conditions

	conditions.add("pay:monthly" if scenario.get("pay_basis") == "monthly" else "pay:hourly")
	conditions.add("retirement:no" if scenario.get("retirement") == "no" else "retirement:yes")

	earnings = [c for c in scenario.get("earnings") or [] if c]
	deductions = [c for c in scenario.get("deductions") or [] if c]
	basis = "per month"
	context.rows["earnings"] = [
		{"earning_label": html.escape(c), "earning_amount": label(_("{0} amount").format(c)), "earning_basis": basis}
		for c in earnings
	]
	context.rows["deductions"] = [
		{"deduction_label": html.escape(c), "deduction_amount": label(_("{0} amount").format(c))} for c in deductions
	]
	conditions.add("allowances:any" if earnings else "allowances:none")
	conditions.update(f"{EARNING_PREFIX}{c}" for c in earnings)
	conditions.update(f"{DEDUCTION_PREFIX}{c}" for c in deductions)

	if scenario.get("shift_design"):
		hours = frappe.get_doc("Shift Design", scenario["shift_design"]).get_contract_working_hours()
		conditions.add(CONTRACT_STYLE_CONDITIONS[hours.style])
		context.rows["working_days"] = [
			{"day_name": html.escape(d["day"]), "day_start": d["start"], "day_end": d["end"]} for d in hours.days
		]
		context.rows["shifts"] = [
			{"shift_name": html.escape(s["name"]), "shift_start": s["start"], "shift_end": s["end"]}
			for s in hours.shifts
		]
		context.values["ordinary_hours_limit"] = html.escape(f"{hours.ordinary_hours_limit:g}")
		context.values["shift_cycle_length"] = html.escape(str(hours.cycle_length))
		context.values["shift_team_count"] = html.escape(str(hours.number_of_teams))
	else:
		conditions.add("shift:rotating" if scenario.get("working_hours") == "rotating" else "shift:fixed")
		context.rows["working_days"] = [
			{"day_name": day, "day_start": label(_("Start")), "day_end": label(_("End"))}
			for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
		]
		context.rows["shifts"] = [
			{"shift_name": label(_("Shift {0}").format(n)), "shift_start": label(_("Start")), "shift_end": label(_("End"))}
			for n in (1, 2)
		]
	return context


# ---- Contract Markdown (the power-user tab) ----
#
#   # Remuneration {#remuneration}
#   1. Paid at **R** {{rate}} per hour worked. {when=pay:hourly}
#   1. Entitled to the following allowances: {when=allowances:any}
#       1. {{earning_label}}: **R** {{earning_amount}} per month; {repeat=earnings}
#   1. See paragraph [Termination](#termination). {when="deduction:Employee Provident Fund"}
#   Unnumbered text (indent with 4 spaces per level)
#
# Inline: **bold**, *italic*, <u>underline</u>, {{variable}}, [label](#anchor).
# A trailing {#anchor when=... repeat=...} block sets the line's options.
# Escape a literal * { [ < or \ with a backslash.

MD_INDENT = "    "
_MD_ATTRS = re.compile(r"\s*\{((?:#[\w-]+|when=|repeat=)(?:[^{}\"]|\"[^\"]*\")*)\}\s*$")
_MD_ATTR_ITEM = re.compile(r"#([\w-]+)|(when|repeat)=(\"[^\"]*\"|\S+)")
_MD_INLINE = re.compile(
	r"\\(?P<esc>.)|(?P<bold>\*\*)|(?P<italic>\*)|(?P<u_open><u>)|(?P<u_close></u>)"
	r"|\{\{\s*(?P<var>[\w:.-]+)\s*\}\}|\[(?P<ref_label>[^\]]*)\]\(#(?P<ref_anchor>[\w-]+)\)"
)


def to_markdown(lines: list[Line]) -> str:
	out = []
	for line in lines:
		if line.kind == "heading":
			prefix = "# "
		elif line.kind == "clause":
			prefix = MD_INDENT * line.indent + "1. "
		else:
			prefix = MD_INDENT * line.indent
		text = _segments_to_markdown(line.segments)
		if line.kind == "text":
			text = re.sub(r"^(#)(?= )|^(\d+)\.(?=\s)", lambda m: "\\#" if m.group(1) else m.group(2) + "\\.", text)
		attrs = []
		if line.anchor:
			attrs.append(f"#{line.anchor}")
		if line.when:
			attrs.append(f"when={_md_attr_value(line.when)}")
		if line.repeat:
			attrs.append(f"repeat={_md_attr_value(line.repeat)}")
		suffix = (" {" + " ".join(attrs) + "}") if attrs else ""
		if line.kind == "text" and not text and not suffix:
			out.append("")
		else:
			out.append(f"{prefix}{text}{suffix}")
	return "\n".join(out).rstrip("\n") + "\n"


def _md_attr_value(value: str) -> str:
	return f'"{value}"' if re.search(r'[\s{}"]', value) else value


def _segments_to_markdown(segments: list[Segment]) -> str:
	out = []
	state = {"bold": False, "italic": False, "underline": False}
	markers = {"bold": ("**", "**"), "italic": ("*", "*"), "underline": ("<u>", "</u>")}

	def set_state(wanted: dict):
		# close inner-most first, then open
		for fmt in ("underline", "italic", "bold"):
			if state[fmt] and not wanted.get(fmt):
				out.append(markers[fmt][1])
				state[fmt] = False
		for fmt in ("bold", "italic", "underline"):
			if wanted.get(fmt) and not state[fmt]:
				out.append(markers[fmt][0])
				state[fmt] = True

	for seg in segments:
		if seg.kind == "text":
			set_state(seg.attrs)
			out.append(re.sub(r"([\\*{\[<])", r"\\\1", seg.value))
		else:
			set_state({})
			if seg.kind == "var":
				out.append("{{" + seg.value + "}}")
			else:
				label = re.sub(r"([\\\]\[])", r"\\\1", seg.value["label"])
				out.append(f"[{label}](#{seg.value['anchor']})")
	set_state({})
	return "".join(out).rstrip()


def parse_markdown(text: str) -> list[Line]:
	lines: list[Line] = []
	for raw in (text or "").replace("\r\n", "\n").split("\n"):
		raw = raw.replace("\t", MD_INDENT).rstrip()
		attrs: dict[str, str] = {}
		match = _MD_ATTRS.search(raw)
		if match and not raw[: match.start()].endswith("\\"):
			for item in _MD_ATTR_ITEM.finditer(match.group(1)):
				if item.group(1):
					attrs["anchor"] = item.group(1)
				else:
					attrs[item.group(2)] = item.group(3).strip('"')
			raw = raw[: match.start()]

		stripped = raw.lstrip(" ")
		indent = min((len(raw) - len(stripped)) // len(MD_INDENT), MAX_INDENT)
		if stripped.startswith("# "):
			kind, body, indent = "heading", stripped[2:], 0
		elif m := re.match(r"\d+\.\s+", stripped):
			kind, body = "clause", stripped[m.end() :]
		else:
			kind, body = "text", stripped
		lines.append(
			Line(kind, indent, attrs.get("anchor"), _parse_inline(body), attrs.get("when"), attrs.get("repeat"))
		)
	while lines and lines[-1].kind == "text" and not lines[-1].segments and not lines[-1].when:
		lines.pop()
	return lines


def _parse_inline(body: str) -> list[Segment]:
	segments: list[Segment] = []
	state = {"bold": False, "italic": False, "underline": False}
	buffer: list[str] = []

	def flush():
		if buffer:
			segments.append(Segment("text", _clean_text("".join(buffer)), {k: True for k, v in state.items() if v}))
			buffer.clear()

	pos = 0
	for m in _MD_INLINE.finditer(body):
		buffer.append(body[pos : m.start()])
		pos = m.end()
		if m.group("esc") is not None:
			buffer.append(m.group("esc"))
			continue
		flush()
		if m.group("bold"):
			state["bold"] = not state["bold"]
		elif m.group("italic"):
			state["italic"] = not state["italic"]
		elif m.group("u_open"):
			state["underline"] = True
		elif m.group("u_close"):
			state["underline"] = False
		elif m.group("var"):
			segments.append(Segment("var", m.group("var")))
		else:
			label = re.sub(r"\\(.)", r"\1", m.group("ref_label"))
			segments.append(Segment("ref", {"anchor": m.group("ref_anchor"), "label": label}))
	buffer.append(body[pos:])
	flush()
	return [s for s in segments if s.kind != "text" or s.value]


# ---- Legacy Contract Type import (lab preview of the old wording in the new format) ----


def import_legacy_contract_types(contract_types: list[str] | None = None) -> list[str]:
	"""Convert legacy Contract Types (Contract Sections/Paragraphs) into draft
	templates, once per Contract Type: re-running refreshes the existing draft.

	The per-contract Remuneration and Working Hours placeholders become single
	dynamic sections built from the legacy wording (rate per hour/month, one
	line per allowance, Fixed/Rotating hours). Run with
	`bench --site <site> execute ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template.import_legacy_contract_types`.
	"""
	names = contract_types or frappe.get_all("Contract Type", filters={"docstatus": 1}, pluck="name", order_by="name")
	results = []
	for contract_type in names:
		markdown, notes = _legacy_contract_markdown(contract_type)
		existing = frappe.db.get_value(
			"Contract of Employment Template", {"source_contract_type": contract_type, "docstatus": 0}, "name"
		)
		doc = (
			frappe.get_doc("Contract of Employment Template", existing)
			if existing
			else frappe.new_doc("Contract of Employment Template")
		)
		doc.contract_name = doc.contract_name or contract_type
		doc.source_contract_type = contract_type
		doc.contract_markdown = markdown
		doc.contract_wording = None  # rebuild from the Markdown
		doc.save()
		results.append(f"{doc.name}: {'; '.join(notes) if notes else 'ok'}")
	return results


_LEGACY_TOKEN_TO_VAR = {v.legacy_token: v.key for v in VARIABLES if v.legacy_token}


def _legacy_contract_markdown(contract_type: str) -> tuple[str, list[str]]:
	terms = frappe.get_all(
		"Contract Terms", filters={"parent": contract_type}, fields=["sec_no", "section"], order_by="sec_no"
	)
	notes: list[str] = []
	sections = []  # (sec_head, [(depth, ss_num, text)])
	for term in terms:
		if term.section == "Remuneration Placeholder":
			sections.append(("Remuneration", _legacy_remuneration(), "remuneration"))
		elif term.section == "Working Hours Placeholder":
			sections.append(("Working Hours", _legacy_working_hours(), "working-hours"))
		else:
			section = frappe.get_doc("Contract Section", term.section)
			paragraphs = [
				(_legacy_depth(p), cint(p.ss_num), p.clause_text or "", None, None)
				for p in sorted(section.sec_par, key=lambda p: p.idx)
			]
			sections.append((section.sec_head, paragraphs, _slug(section.sec_head)))

	# anchors: every heading, and every top-level clause (references point at
	# "{section}.{ss}" e.g. Deductions .2)
	heading_anchor = {head: slug for head, _paras, slug in sections}
	anchors = {slug for _head, _paras, slug in sections} | {
		f"{slug}-{ss}" for _head, paras, slug in sections for depth, ss, *_rest in paras if depth == 0 and ss
	}
	out = []
	for head, paragraphs, slug in sections:
		out.append(f"# {_md_escape(head)} {{#{slug}}}")
		for depth, ss, text, when, repeat in paragraphs:
			body = _legacy_inline(text, heading_anchor, anchors, notes)
			attrs = []
			if depth == 0 and ss:
				attrs.append(f"#{slug}-{ss}")
			if when:
				attrs.append(f"when={_md_attr_value(when)}")
			if repeat:
				attrs.append(f"repeat={repeat}")
			suffix = (" {" + " ".join(attrs) + "}") if attrs else ""
			out.append(f"{MD_INDENT * depth}1. {body}{suffix}")
	return "\n".join(out) + "\n", notes


def _legacy_depth(p) -> int:
	return max(sum(1 for n in (p.ss_num, p.par_num, p.spar_num, p.item_num, p.sitem_num) if cint(n) > 0) - 1, 0)


def _slug(text: str) -> str:
	return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "section"


def _md_escape(text: str) -> str:
	return re.sub(r"([\\*{\[<])", r"\\\1", text)


def _legacy_inline(text: str, heading_anchor: dict[str, str], anchors: set[str], notes: list[str]) -> str:
	"""Legacy clause text -> Contract Markdown inline. Legacy markup: **bold**,
	//italic//, __underline__, {placeholder}, {par."Heading"}[.N]."""
	tokens = re.split(r'(\{par\.\s*"?[^}"]*"?\}(?:\.\d+)?|\{[a-z_0-9]+\}|\*\*|//|__)', text)
	out = []
	for tok in tokens:
		if not tok:
			continue
		if ref := re.fullmatch(r'\{par\.\s*"?([^}"]*)"?\}(?:\.(\d+))?', tok):
			head, ss = ref.group(1).strip(), ref.group(2)
			slug = heading_anchor.get(head)
			if not slug or (ss and f"{slug}-{ss}" not in anchors):
				notes.append(f"reference to missing '{head}{'.' + ss if ss else ''}' kept as text")
				out.append(_md_escape(tok))
			elif ss:
				out.append(f"[{_md_escape(head)} {ss}](#{slug}-{ss})")
			else:
				out.append(f"[{_md_escape(head)}](#{slug})")
		elif tok in _LEGACY_TOKEN_TO_VAR:
			out.append("{{" + _LEGACY_TOKEN_TO_VAR[tok] + "}}")
		elif tok[1:-1] in VARIABLES_BY_KEY and tok.startswith("{"):
			out.append("{{" + tok[1:-1] + "}}")
		elif tok == "**":
			out.append("**")
		elif tok == "//":
			out.append("*")
		elif tok == "__":
			out.append("<u>")  # legacy pairs __x__; toggled below
		elif re.fullmatch(r"\{[a-z_0-9]+\}", tok):
			notes.append(f"unknown placeholder {tok} kept as text")
			out.append(_md_escape(tok))
		else:
			out.append(_md_escape(tok))
	joined = "".join(out)
	# legacy __x__ is a pair: second marker closes
	parts = joined.split("<u>")
	joined = parts[0] + "".join(("<u>" if i % 2 == 1 else "</u>") + p for i, p in enumerate(parts[1:], 1))
	return joined


def _legacy_paragraph(contains: str, parent_like: str = "Remuneration (%") -> str:
	text = frappe.db.get_value(
		"Contract Paragraph",
		{"parent": ["like", parent_like], "clause_text": ["like", f"%{contains}%"]},
		"clause_text",
		order_by="creation asc",
	)
	if not text:
		frappe.throw(_("Legacy paragraph containing '{0}' not found.").format(contains))
	return text


def _legacy_remuneration():
	"""The 29 legacy Remuneration sections as one dynamic section."""
	allowance_line = "{earning_label}: **R** {earning_amount} per month;"
	return [
		(0, 1, _legacy_paragraph("per hour worked"), "pay:hourly", None),
		(0, 1, _legacy_paragraph("per month worked"), "pay:monthly", None),
		(0, 2, _legacy_paragraph("entitled to the following allowances"), "allowances:any", None),
		(1, 0, allowance_line, "allowances:any", "earnings"),
		(0, 3, _legacy_paragraph("contribute 5%"), None, None),
		(0, 4, _legacy_paragraph("No other form of remuneration"), None, None),
	]


def _legacy_working_hours():
	"""Monday-Friday/Monday-Sunday (Fixed) and Shift Roster (Rotating) as one
	dynamic section; their remaining paragraphs were identical."""
	fixed = "Working Hours (Monday to Friday)"
	paragraphs = frappe.get_all(
		"Contract Paragraph", filters={"parent": fixed}, fields=["ss_num", "par_num", "clause_text"], order_by="idx"
	)
	lead_in = next(p.clause_text for p in paragraphs if cint(p.ss_num) == 1 and not cint(p.par_num))
	roster = _legacy_paragraph("determined by a Shift Roster", "Working Hours (Shift Roster)")
	rest = [(0, cint(p.ss_num), p.clause_text, None, None) for p in paragraphs if cint(p.ss_num) > 1 and not cint(p.par_num)]
	return [
		(0, 1, lead_in, "shift:fixed", None),
		(1, 0, "{day_name}s: {day_start} to {day_end}", "shift:fixed", "working_days"),
		(0, 1, roster, "shift:rotating", None),
		*rest,
	]
