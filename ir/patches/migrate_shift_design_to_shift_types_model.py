# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

DOCTYPE = "Shift Design"
CALENDAR_RULE_DOCTYPE = "Shift Design Calendar Rule"

DAY_ACTIONS = {
	"Day Shift Only": "Restrict to Shift Type",
	"Continue Previous Day Team": "Continue Previous Shift Team",
	"Continue Saturday Day Team": "Continue Previous Shift Team",
}
NIGHT_ACTIONS = {
	"Night Shift Only": "Restrict to Shift Type",
	"Continue Previous Night Team": "Continue Previous Shift Team",
}


def execute():
	if not frappe.db.exists("DocType", DOCTYPE):
		return

	if not frappe.db.has_column(DOCTYPE, "day_shift_type"):
		# Old schema already gone (fresh install, or already migrated).
		return

	parents = frappe.db.sql(
		f"""
		SELECT name, day_shift_type, night_shift_type, sunday_rule
		FROM `tab{DOCTYPE}`
		""",
		as_dict=True,
	)

	has_hour_columns = frappe.db.has_column(CALENDAR_RULE_DOCTYPE, "day_shift_hours")

	for parent in parents:
		day_type = parent.day_shift_type
		night_type = parent.night_shift_type

		doc = frappe.get_doc(DOCTYPE, parent.name)

		existing_types = {row.shift_type for row in doc.shift_types or []}
		for shift_type in (day_type, night_type):
			if shift_type and shift_type not in existing_types:
				doc.append("shift_types", {"shift_type": shift_type})
				existing_types.add(shift_type)

		for table_field in ("pattern", "date_overrides"):
			for child in doc.get(table_field) or []:
				if child.assignment == "Day":
					child.assignment = day_type or ""
				elif child.assignment == "Night":
					child.assignment = night_type or ""
				elif child.assignment == "Off":
					child.assignment = ""

		if has_hour_columns:
			hour_rows = {
				row.name: row
				for row in frappe.db.sql(
					f"""
					SELECT name, day_shift_hours, night_shift_hours
					FROM `tab{CALENDAR_RULE_DOCTYPE}`
					WHERE parent = %(parent)s
					""",
					{"parent": parent.name},
					as_dict=True,
				)
			}
		else:
			hour_rows = {}

		for rule in doc.get("calendar_rules") or []:
			action = rule.action

			if action in DAY_ACTIONS:
				rule.action = DAY_ACTIONS[action]
				rule.target_shift_type = day_type or ""
			elif action in NIGHT_ACTIONS:
				rule.action = NIGHT_ACTIONS[action]
				rule.target_shift_type = night_type or ""

			hour_row = hour_rows.get(rule.name)
			if hour_row:
				rule.hours_override = _pick_hours(
					hour_row.day_shift_hours, hour_row.night_shift_hours
				)

		has_sunday_rule = any(
			row.rule_type == "Weekday" and row.day_of_week == "Sunday"
			for row in doc.get("calendar_rules") or []
		)

		if not has_sunday_rule and parent.sunday_rule not in (None, "", "Follow Pattern"):
			if parent.sunday_rule == "No Work":
				doc.append(
					"calendar_rules",
					{
						"priority": 10,
						"rule_type": "Weekday",
						"day_of_week": "Sunday",
						"action": "No Work",
						"enabled": 1,
					},
				)
			elif parent.sunday_rule == "Extend Saturday Day Team" and day_type:
				doc.append(
					"calendar_rules",
					{
						"priority": 10,
						"rule_type": "Weekday",
						"day_of_week": "Sunday",
						"action": "Continue Previous Shift Team",
						"target_shift_type": day_type,
						"enabled": 1,
					},
				)
			elif parent.sunday_rule == "Extend Saturday Night Team" and night_type:
				doc.append(
					"calendar_rules",
					{
						"priority": 10,
						"rule_type": "Weekday",
						"day_of_week": "Sunday",
						"action": "Continue Previous Shift Team",
						"target_shift_type": night_type,
						"enabled": 1,
					},
				)

		doc.flags.ignore_validate_update_after_submit = True
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)

	frappe.db.commit()


def _pick_hours(day_hours, night_hours):
	# At most one Shift Type is ever active on a ruled date (full-takeover
	# semantics), so whichever legacy hour value is meaningfully set is the
	# one that applies - prefer Day, then Night, else no override.
	if day_hours not in (None, 0, 0.0):
		return flt(day_hours)
	if night_hours not in (None, 0, 0.0):
		return flt(night_hours)
	return None
