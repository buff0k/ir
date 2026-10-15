# Copyright (c) 2026, BuFf0k and Contributors
# See license.txt

import json

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from ir.industrial_relations.doctype.contract_of_employment_template.contract_of_employment_template import (
	LEGACY_TOKENS_SUPERSEDED,
	MAX_INDENT,
	REPEATS_BY_KEY,
	VARIABLES_BY_KEY,
	ContractContext,
	_legacy_inline,
	format_value,
	long_date,
	number_lines,
	number_to_words,
	parse_markdown,
	parse_wording,
	preview_context,
	render_contract,
	to_delta,
	to_markdown,
	validate_lines,
)

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def heading(text, anchor=None):
	attrs = {"header": 1}
	if anchor:
		attrs["coe-anchor"] = anchor
	return [{"insert": text}, {"insert": "\n", "attributes": attrs}]


def clause(*inserts, indent=0, anchor=None, when=None, repeat=None):
	attrs = {"list": "ordered"}
	if indent:
		attrs["indent"] = indent
	if anchor:
		attrs["coe-anchor"] = anchor
	if when:
		attrs["coe-when"] = when
	if repeat:
		attrs["coe-repeat"] = repeat
	ops = [i if isinstance(i, dict) else {"insert": i} for i in inserts]
	return [*ops, {"insert": "\n", "attributes": attrs}]


def text(value, indent=0):
	return [{"insert": value}, {"insert": "\n", **({"attributes": {"indent": indent}} if indent else {})}]


def var(key):
	return {"insert": {"coe-var": key}}


def ref(anchor, label="x"):
	return {"insert": {"coe-ref": {"anchor": anchor, "label": label}}}


def delta(*blocks):
	return {"ops": [op for block in blocks for op in block]}


def context(conditions=(), values=None, **rows):
	return ContractContext(values=values or {}, rows=rows, conditions=set(conditions))


REMUNERATION = delta(
	heading("Remuneration"),
	clause("Paid **R** ", var("rate"), " per hour worked.", when="pay:hourly"),
	clause("Paid **R** ", var("rate"), " per month worked.", when="pay:monthly"),
	clause("Entitled to the following allowances:", when="allowances:any"),
	clause(var("earning_label"), ": R ", var("earning_amount"), " per month;", indent=1, repeat="earnings"),
	clause("The Company and Employee shall each contribute 5% to the provident fund.", when="deduction:PAYE"),
	clause("No other form of remuneration.", anchor="none"),
	clause("See ", ref("none")),
)


class UnitTestTemplateEngine(UnitTestCase):
	def test_numbering_nests_without_limit_and_text_never_counts(self):
		lines = parse_wording(
			delta(
				heading("Employment"),
				clause("a"),
				clause("b", indent=1),
				text("unnumbered aside", indent=1),
				clause("c", indent=1),
				clause("d", indent=2),
				clause("e"),
				heading("Remuneration"),
				clause("f"),
				*[clause(f"deep {k}", indent=k) for k in range(1, 7)],
			)
		)
		self.assertEqual(
			number_lines(lines),
			[
				"1", "1.1", "1.1.1", None, "1.1.2", "1.1.2.1", "1.2",
				"2", "2.1", "2.1.1", "2.1.1.1", "2.1.1.1.1", "2.1.1.1.1.1", "2.1.1.1.1.1.1", "2.1.1.1.1.1.1.1",
			],
		)

	def test_skipped_level_shows_zero_like_the_editor(self):
		lines = parse_wording(delta(heading("H"), clause("deep first", indent=2)))
		self.assertEqual(number_lines(lines), ["1", "1.0.0.1"])

	def test_unsupported_formats_and_embeds_are_dropped(self):
		dirty = delta(
			[{"insert": "Big", "attributes": {"bold": True, "color": "red", "size": "huge"}}],
			[{"insert": {"image": "x.png"}}],
			[{"insert": "\n", "attributes": {"header": 3, "align": "center"}}],
			clause("x", indent=MAX_INDENT + 10),
		)
		self.assertEqual(
			to_delta(parse_wording(dirty))["ops"],
			[
				{"insert": "Big", "attributes": {"bold": True}},
				{"insert": "\n", "attributes": {"header": 1}},
				{"insert": "x"},
				{"insert": "\n", "attributes": {"list": "ordered", "indent": MAX_INDENT}},
			],
		)

	def test_tabs_and_non_breaking_spaces_become_spaces(self):
		lines = parse_wording(delta(heading("H"), clause("a\tb c ")))
		self.assertEqual(lines[1].segments[0].value, "a b c ")

	def test_round_trip_is_stable(self):
		once = to_delta(parse_wording(REMUNERATION))
		self.assertEqual(once, to_delta(parse_wording(once)))

	def test_duplicate_anchor_keeps_first_line(self):
		ops = to_delta(parse_wording(delta(heading("A", anchor="dup"), clause("B", anchor="dup"))))["ops"]
		anchors = [op["attributes"].get("coe-anchor") for op in ops if op["insert"] == "\n"]
		self.assertEqual(anchors, ["dup", None])

	# ---- dynamic clauses ----

	def test_hourly_with_allowances_and_provident_fund(self):
		out = render_contract(
			parse_wording(REMUNERATION),
			context(
				{"pay:hourly", "allowances:any", "deduction:PAYE"},
				values={"rate": "45.00"},
				earnings=[
					{"earning_label": "Housing Allowance", "earning_amount": "1 500.00"},
					{"earning_label": "Shift Allowance", "earning_amount": "600.00"},
				],
			),
		)
		self.assertIn("<td><b>1.1</b></td><td>Paid **R** <b>45.00</b> per hour worked.</td>", out)
		self.assertNotIn("per month worked", out)
		self.assertIn("<td><b>1.2.1</b></td><td><b>Housing Allowance</b>: R <b>1 500.00</b> per month;</td>", out)
		self.assertIn("<td><b>1.2.2</b></td><td><b>Shift Allowance</b>", out)
		self.assertIn("<td><b>1.3</b></td><td>The Company and Employee", out)
		self.assertIn("<td><b>1.4</b></td><td>No other form", out)
		self.assertIn("See 1.4", out)

	def test_monthly_without_allowances_or_provident_fund_closes_up(self):
		out = render_contract(parse_wording(REMUNERATION), context({"pay:monthly", "allowances:none"}))
		self.assertIn("per month worked.", out)
		self.assertIn("<b>__________</b>", out)  # missing amount -> the legacy amount blank
		self.assertNotIn("allowances", out)
		self.assertNotIn("provident fund", out)
		self.assertIn("<td><b>1.2</b></td><td>No other form", out)
		self.assertIn("See 1.2", out)

	def test_repeat_with_no_rows_disappears(self):
		lines = parse_wording(delta(heading("H"), clause(var("deduction_label"), repeat="deductions"), clause("after")))
		out = render_contract(lines, context())
		self.assertIn("<td><b>1.1</b></td><td>after</td>", out)

	def test_validation_catches_bad_variables_conditions_repeats_and_references(self):
		lines = parse_wording(
			delta(
				heading("H"),
				clause(var("not_a_variable")),
				clause(var("earning_amount")),  # row variable without its repeat
				clause("x", when="nope"),
				clause("x", when="earning:No Such Component"),
				clause("x", repeat="nope"),
				clause("See ", ref("gone", "Gone")),
			)
		)
		errors = " ".join(validate_lines(lines))
		for expected in ("not_a_variable", "Earning Amount", "nope", "No Such Component", "Gone"):
			self.assertIn(expected, errors)

	def test_submit_only_checks(self):
		lines = parse_wording(delta(clause("orphan"), heading(""), clause("ok")))
		self.assertEqual(validate_lines(lines), [])
		errors = " ".join(validate_lines(lines, for_submit=True))
		self.assertIn("before the first Heading", errors)
		self.assertIn("is empty", errors)

	def test_text_is_escaped(self):
		out = render_contract(parse_wording(delta(text("Preamble <script>"), heading("H"))), context())
		self.assertIn('<tr><td colspan="2">Preamble &lt;script&gt;</td></tr>', out)

	def test_every_legacy_placeholder_is_covered(self):
		legacy = {
			"{employee_name}", "{date_of_joining}", "{company}", "{employee_number}", "{designation}",
			"{current_address}", "{start_date}", "{end_date}", "{project}", "{custom_id_number}", "{branch}",
			"{contract_type}", "{restraint_period}", "{restraint_territory}", "{rate}", "{retirement_age}",
			*(f"{{allowance_{n}}}" for n in range(1, 6)),
			*(f"{{{d}_{e}}}" for d in ("mon", "tue", "wed", "thu", "fri", "sat", "sun") for e in ("start", "end")),
		}
		mapped = {v.legacy_token for v in VARIABLES_BY_KEY.values() if v.legacy_token}
		self.assertEqual(legacy - mapped - set(LEGACY_TOKENS_SUPERSEDED), set())
		self.assertTrue(set(LEGACY_TOKENS_SUPERSEDED.values()) <= set(REPEATS_BY_KEY))

	# ---- Contract Markdown ----

	def test_markdown_round_trip(self):
		lines = parse_wording(REMUNERATION)
		markdown = to_markdown(lines)
		self.assertIn("1. Paid \\*\\*R\\*\\* {{rate}} per hour worked. {when=pay:hourly}", markdown)
		self.assertIn("    1. {{earning_label}}: R {{earning_amount}} per month; {repeat=earnings}", markdown)
		self.assertIn("1. See [x](#none)", markdown)
		self.assertEqual(to_delta(parse_markdown(markdown)), to_delta(lines))

	def test_markdown_escapes_literal_markup_and_quotes_spaced_values(self):
		lines = parse_wording(
			delta(
				heading("H"),
				clause("5 * 3 {not a var} [not a link] <u>", when="deduction:Employee Provident Fund"),
				text("1. looks like a clause"),
				text("# looks like a heading"),
				clause({"insert": "all", "attributes": {"bold": True, "italic": True, "underline": True}}),
			)
		)
		markdown = to_markdown(lines)
		self.assertIn('{when="deduction:Employee Provident Fund"}', markdown)
		self.assertEqual(to_delta(parse_markdown(markdown)), to_delta(lines))

	def test_power_user_markdown(self):
		lines = parse_markdown(
			"# Working Hours {#wh}\n"
			"1. Hours are: {when=shift:fixed}\n"
			"    1. {{day_name}}s: {{day_start}} to {{day_end}} {when=shift:fixed repeat=working_days}\n"
			"1. Per the *Shift Roster*. {when=shift:rotating}\n"
			"Unnumbered <u>note</u> per [Working Hours](#wh)\n"
		)
		self.assertEqual([line.kind for line in lines], ["heading", "clause", "clause", "clause", "text"])
		self.assertEqual(lines[2].indent, 1)
		self.assertEqual((lines[2].when, lines[2].repeat), ("shift:fixed", "working_days"))
		self.assertEqual(lines[3].segments[1].attrs, {"italic": True})
		self.assertEqual(lines[4].segments[1].attrs, {"underline": True})
		self.assertEqual(lines[4].segments[-1].kind, "ref")

	# ---- legacy markup and value formatting ----

	def test_legacy_inline_markup(self):
		notes = []
		out = _legacy_inline(
			'Paid **R** {rate} per //force majeur// as in {par."Deductions"}.2 and {par."Gone"}',
			{"Deductions": "deductions"},
			{"deductions", "deductions-2"},
			notes,
		)
		self.assertEqual(
			out, 'Paid **R** {{rate}} per *force majeur* as in [Deductions 2](#deductions-2) and \\{par."Gone"}'
		)
		self.assertEqual(len(notes), 1)

	def test_value_formats(self):
		self.assertEqual(number_to_words(1500.0), "One Thousand Five Hundred")  # no "Point Zero"
		self.assertEqual(number_to_words(28.79), "Twenty-Eight Point Seven Nine")
		self.assertEqual(number_to_words(28.80), "Twenty-Eight Point Eight")
		self.assertEqual(number_to_words(28.05), "Twenty-Eight Point Zero Five")
		self.assertEqual(long_date("2024-11-18"), "Monday, the 18th of November 2024")
		self.assertEqual(long_date("2026-10-11"), "Sunday, the 11th of October 2026")
		self.assertEqual(long_date("2026-10-22"), "Thursday, the 22nd of October 2026")
		self.assertEqual(format_value(VARIABLES_BY_KEY["rate"], 1500), "1 500.00 (One Thousand Five Hundred)")
		self.assertEqual(format_value(VARIABLES_BY_KEY["retirement_age"], 62), "62 (Sixty-Two)")
		self.assertEqual(format_value(VARIABLES_BY_KEY["employee_name"], "<b>"), "&lt;b&gt;")


class IntegrationTestContractofEmploymentTemplate(IntegrationTestCase):
	def make(self, name="Test COE Template", wording=None, markdown=None):
		doc = frappe.get_doc({"doctype": "Contract of Employment Template", "contract_name": name})
		if markdown is not None:
			doc.contract_markdown = markdown
		else:
			doc.contract_wording = json.dumps(wording or delta(heading("Employment"), clause("Hello")))
		return doc.insert()

	def test_autoname_is_name_and_creation_date(self):
		doc = self.make("  Test Naming Template  ")
		expected_date = frappe.utils.getdate(doc.creation).strftime("%d-%m-%Y")
		self.assertEqual(doc.name, f"Test Naming Template - {expected_date}")
		self.assertEqual(doc.contract_name, "Test Naming Template")

	def test_same_name_same_day_is_rejected(self):
		self.make("Test Duplicate Template")
		with self.assertRaises(frappe.ValidationError):
			self.make("Test Duplicate Template")

	def test_amendment_keeps_frappe_suffix(self):
		doc = self.make("Test Amend Template")
		doc.submit()
		doc.cancel()
		amended = frappe.copy_doc(doc)
		amended.docstatus = 0
		amended.amended_from = doc.name
		amended.insert()
		self.assertEqual(amended.name, f"{doc.name}-1")

	def test_save_stores_cleaned_wording_and_markdown(self):
		doc = self.make(
			"Test Clean Template",
			delta([{"insert": "H", "attributes": {"color": "red"}}, {"insert": "\n", "attributes": {"header": 2}}]),
		)
		self.assertEqual(
			json.loads(doc.contract_wording),
			{"ops": [{"insert": "H"}, {"insert": "\n", "attributes": {"header": 1}}]},
		)
		self.assertEqual(doc.contract_markdown, "# H\n")

	def test_markdown_only_edit_rebuilds_the_wording(self):
		doc = self.make("Test Markdown Template", markdown="# Pay\n1. Rate {{rate}} {when=pay:hourly}\n")
		self.assertEqual(
			json.loads(doc.contract_wording)["ops"][-1],
			{"insert": "\n", "attributes": {"list": "ordered", "coe-when": "pay:hourly"}},
		)
		doc.contract_markdown = "# Pay\n1. Changed {when=pay:monthly}\n"
		doc.save()
		self.assertIn("Changed", doc.contract_wording)
		self.assertIn("pay:monthly", doc.contract_wording)

	def test_unknown_variable_blocks_save(self):
		with self.assertRaises(frappe.ValidationError):
			self.make("Test Bad Variable", delta(heading("H"), clause(var("nope"))))

	def test_component_conditions_use_real_salary_components(self):
		component = frappe.db.get_value("Salary Component", {"type": "Deduction", "disabled": 0}, "name")
		self.make("Test Component Condition", delta(heading("H"), clause("x", when=f"deduction:{component}")))

	def test_preview_scenario(self):
		out = render_contract(
			parse_wording(REMUNERATION),
			preview_context({"pay_basis": "monthly", "earnings": [], "deductions": ["PAYE"]}),
		)
		self.assertIn("per month worked", out)
		self.assertNotIn("allowances", out)
		self.assertIn("provident fund", out)  # REMUNERATION shows that clause when deduction:PAYE
