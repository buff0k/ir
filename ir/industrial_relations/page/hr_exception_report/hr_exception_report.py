# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, date_diff, flt, get_first_day, getdate, now_datetime, today


RACE_KEYS = {
    "African": "african",
    "Coloured": "coloured",
    "Indian": "indian",
    "White": "white",
}

EE_LEVELS = [
    "Top Management",
    "Senior Management",
    "Professionally Qualified and Experienced Specialists and Mid-Management",
    "Skilled Technical and Academically Qualified Workers, Junior Management, Supervisors, Foremen and Superintendents",
    "Semi-Skilled and Discretionary Decision Making",
    "Unskilled and Defined Decision Making",
]

TERMINAL_POOR_PERFORMANCE_OUTCOMES = {"Performance Improved", "Dismissal"}


def _field_exists(doctype, fieldname):
    return bool(frappe.get_meta(doctype).get_field(fieldname))


def _first_existing_field(doctype, candidates, labels=None):
    meta = frappe.get_meta(doctype)

    for fieldname in candidates:
        if fieldname and meta.get_field(fieldname):
            return fieldname

    wanted_labels = {str(label).strip().lower() for label in (labels or []) if label}
    if wanted_labels:
        for df in meta.fields:
            if str(df.label or "").strip().lower() in wanted_labels:
                return df.fieldname

    return None


def _validate_filters(company, from_date, to_date):
    if not company:
        frappe.throw(_("Company is required."))
    if not from_date or not to_date:
        frappe.throw(_("From Date and To Date are required."))

    from_date = getdate(from_date)
    to_date = getdate(to_date)

    if from_date > to_date:
        frappe.throw(_("From Date cannot be after To Date."))

    if not frappe.db.exists("Company", company):
        frappe.throw(_("Company {0} does not exist.").format(frappe.bold(company)))

    return from_date, to_date


def _employee_fields():
    return {
        "designated_group": _first_existing_field(
            "Employee",
            [
                "custom_designated_group",
                "custom_race",
                "designated_group",
                "race",
            ],
            labels=["Designated Group", "Race", "Population Group"],
        ),
        "occupational_level": _first_existing_field(
            "Employee",
            [
                "custom_occupational_level",
                "ir_occupational_level",
                "occupational_level",
            ],
            labels=["Occupational Level", "EE Occupational Level"],
        ),
        "disabled": _first_existing_field(
            "Employee",
            [
                "custom_disabled_employee",
                "custom_disability",
                "disabled_employee",
                "person_with_disability",
            ],
            labels=["Disabled Employee", "Disability", "Person with Disability"],
        ),
        "nationality": _first_existing_field(
            "Employee", ["nationality", "custom_nationality", "country"], labels=["Nationality"]
        ),
        "employment_type": _first_existing_field(
            "Employee", ["employment_type", "custom_employment_type"], labels=["Employment Type"]
        ),
    }


def _designation_level_field():
    return _first_existing_field(
        "Designation",
        ["ir_occupational_level", "custom_occupational_level", "occupational_level"],
        labels=["Occupational Level", "EE Occupational Level"],
    )


def _normalise_race(value):
    value = " ".join(str(value or "").replace("/", " ").replace("-", " ").split()).lower()
    if not value:
        return None

    if "african" in value or value in {"black", "a"}:
        return "African"
    if "coloured" in value or value == "c":
        return "Coloured"
    if "indian" in value or "asian" in value or value == "i":
        return "Indian"
    if "white" in value or value == "w":
        return "White"
    return None


def _normalise_level(value):
    raw = str(value or "").strip()
    value = " ".join(raw.replace("/", " ").replace("-", " ").replace("_", " ").split()).lower()
    if not value:
        return "Unclassified"

    # Accept common numeric prefixes/codes used by EE custom fields.
    first_token = value.split(" ", 1)[0].rstrip(".):")
    numeric_map = {str(index + 1): level for index, level in enumerate(EE_LEVELS)}
    if first_token in numeric_map:
        return numeric_map[first_token]

    checks = [
        (("top management", "executive management", "top managers"), EE_LEVELS[0]),
        (("senior management", "senior managers"), EE_LEVELS[1]),
        (("professionally qualified", "experienced specialist", "middle management", "mid management", "specialists and mid"), EE_LEVELS[2]),
        (("skilled technical", "academically qualified", "junior management", "supervisor", "foreman", "superintendent"), EE_LEVELS[3]),
        (("semi skilled", "discretionary decision"), EE_LEVELS[4]),
        (("unskilled", "defined decision"), EE_LEVELS[5]),
    ]
    for needles, level in checks:
        if any(needle in value for needle in needles):
            return level

    return "Unclassified"


def _is_foreign_national(nationality):
    value = (nationality or "").strip().lower()
    if not value:
        return False
    return value not in {
        "south africa",
        "south african",
        "za",
        "zaf",
        "republic of south africa",
    }


def _is_temporary(employment_type):
    value = (employment_type or "").strip().lower()
    return any(token in value for token in ("temporary", "temp", "fixed term", "fixed-term", "contract"))


def _empty_ee_counts():
    return {
        "african_male": 0,
        "coloured_male": 0,
        "indian_male": 0,
        "white_male": 0,
        "african_female": 0,
        "coloured_female": 0,
        "indian_female": 0,
        "white_female": 0,
        "foreign_male": 0,
        "foreign_female": 0,
        "total": 0,
        "unclassified": 0,
    }


def _add_ee_person(counts, gender, race, is_foreign):
    gender_key = "male" if (gender or "").strip().lower() == "male" else "female" if (gender or "").strip().lower() == "female" else None

    if is_foreign and gender_key:
        counts[f"foreign_{gender_key}"] += 1
    elif race and gender_key:
        counts[f"{RACE_KEYS[race]}_{gender_key}"] += 1
    else:
        counts["unclassified"] += 1

    counts["total"] += 1


def _add_race_gender_person(counts, gender, race):
    """Add a person to an A/I/C/W matrix regardless of nationality."""
    gender_key = (gender or "").strip().lower()
    if gender_key not in {"male", "female"} or not race:
        counts["unclassified"] += 1
        counts["total"] += 1
        return

    counts[f"{RACE_KEYS[race]}_{gender_key}"] += 1
    counts["total"] += 1


def _combine_counts(target, source):
    for key in target:
        target[key] += cint(source.get(key))


def _build_ee_profile(company, snapshot_date):
    employee_fields = _employee_fields()
    designation_level = _designation_level_field()

    selected = [
        "e.name",
        "e.employee_name",
        "e.gender",
        "e.designation",
        "e.date_of_joining",
        "e.relieving_date",
    ]

    for alias, fieldname in employee_fields.items():
        if fieldname:
            selected.append(f"e.`{fieldname}` AS `{alias}`")
        else:
            selected.append(f"NULL AS `{alias}`")

    if designation_level:
        selected.append(f"d.`{designation_level}` AS designation_occupational_level")
    else:
        selected.append("NULL AS designation_occupational_level")

    rows = frappe.db.sql(
        f"""
        SELECT {', '.join(selected)}
        FROM `tabEmployee` e
        LEFT JOIN `tabDesignation` d ON d.name = e.designation
        WHERE e.company = %(company)s
          AND e.date_of_joining <= %(snapshot_date)s
          AND (e.relieving_date IS NULL OR e.relieving_date = '' OR e.relieving_date > %(snapshot_date)s)
        ORDER BY e.employee_name, e.name
        """,
        {"company": company, "snapshot_date": snapshot_date},
        as_dict=True,
    )

    all_levels = {level: _empty_ee_counts() for level in EE_LEVELS}
    disabled_levels = {level: _empty_ee_counts() for level in EE_LEVELS}
    temporary_all = _empty_ee_counts()
    temporary_disabled = _empty_ee_counts()
    disabled_matrix = _empty_ee_counts()
    foreign_matrix = _empty_ee_counts()
    unclassified_levels = []
    unclassified_demographics = []

    for row in rows:
        raw_level = row.get("occupational_level") or row.get("designation_occupational_level")
        level = _normalise_level(raw_level)
        race = _normalise_race(row.get("designated_group"))
        foreign = _is_foreign_national(row.get("nationality"))
        temporary = _is_temporary(row.get("employment_type"))
        disabled = cint(row.get("disabled")) == 1 or str(row.get("disabled") or "").strip().lower() in {
            "yes",
            "y",
            "true",
            "disabled",
        }

        if disabled:
            _add_race_gender_person(disabled_matrix, row.get("gender"), race)
        if foreign:
            _add_race_gender_person(foreign_matrix, row.get("gender"), race)

        if level == "Unclassified":
            unclassified_levels.append(
                {
                    "employee": row.name,
                    "employee_name": row.employee_name,
                    "designation": row.designation,
                    "occupational_level": raw_level or "",
                }
            )
            continue

        target = temporary_all if temporary else all_levels[level]
        _add_ee_person(target, row.get("gender"), race, foreign)

        if not foreign and not race:
            unclassified_demographics.append(
                {
                    "employee": row.name,
                    "employee_name": row.employee_name,
                    "gender": row.get("gender") or "",
                    "race_value": row.get("designated_group") or "",
                }
            )

        if disabled:
            disability_target = temporary_disabled if temporary else disabled_levels[level]
            _add_ee_person(disability_target, row.get("gender"), race, foreign)

    def table(level_data, temporary_data):
        permanent_total = _empty_ee_counts()
        for level in EE_LEVELS:
            _combine_counts(permanent_total, level_data[level])

        grand_total = _empty_ee_counts()
        _combine_counts(grand_total, permanent_total)
        _combine_counts(grand_total, temporary_data)

        return {
            "levels": [{"level": level, **level_data[level]} for level in EE_LEVELS],
            "total_permanent": permanent_total,
            "temporary": temporary_data,
            "grand_total": grand_total,
        }

    return {
        "snapshot_date": str(snapshot_date),
        "all_employees": table(all_levels, temporary_all),
        "people_with_disabilities": table(disabled_levels, temporary_disabled),
        "special_rows": {
            "people_with_disabilities": disabled_matrix,
            "foreign_nationals": foreign_matrix,
        },
        "employee_count_at_snapshot": len(rows),
        "unclassified_levels": unclassified_levels,
        "unclassified_demographics": unclassified_demographics,
        "field_map": {
            **employee_fields,
            "designation_occupational_level": designation_level,
        },
    }


def _employee_movements(company, from_date, to_date):
    new_employees = frappe.get_all(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": ["between", [from_date, to_date]],
        },
        fields=[
            "name",
            "employee_name",
            "date_of_joining",
            "branch",
            "department",
            "designation",
            "status",
        ],
        order_by="date_of_joining asc, employee_name asc",
    )

    terminated_employees = frappe.get_all(
        "Employee",
        filters={
            "company": company,
            "relieving_date": ["between", [from_date, to_date]],
        },
        fields=[
            "name",
            "employee_name",
            "relieving_date",
            "reason_for_leaving",
            "branch",
            "department",
            "designation",
            "status",
        ],
        order_by="relieving_date asc, employee_name asc",
    )

    reasons = defaultdict(int)
    for row in terminated_employees:
        reasons[row.get("reason_for_leaving") or _("Unspecified")] += 1

    opening_headcount = frappe.db.count(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": ["<", from_date],
            "relieving_date": ["in", [None, ""]],
        },
    )
    opening_headcount += frappe.db.count(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": ["<", from_date],
            "relieving_date": [">=", from_date],
        },
    )

    closing_headcount = frappe.db.count(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": ["<=", to_date],
            "relieving_date": ["in", [None, ""]],
        },
    )
    closing_headcount += frappe.db.count(
        "Employee",
        filters={
            "company": company,
            "date_of_joining": ["<=", to_date],
            "relieving_date": [">", to_date],
        },
    )

    return {
        "new": {"count": len(new_employees), "rows": new_employees},
        "terminated": {
            "count": len(terminated_employees),
            "rows": terminated_employees,
            "reasons": [
                {"reason": reason, "count": count}
                for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
        "headcount": {
            "opening": opening_headcount,
            "closing": closing_headcount,
            "net_change": closing_headcount - opening_headcount,
        },
    }


def _process_summary(doctype, employee_field, company, from_date, to_date):
    frappe.has_permission(doctype, "read", throw=True)
    meta = frappe.get_meta(doctype)
    name_field = "employee_name" if meta.get_field("employee_name") else "accused_name"
    branch_field = "branch" if meta.get_field("branch") else None
    responsible_field = None
    for candidate in ("responsible_ir_name", "ir_name", "responsible_ir", "ir"):
        if meta.get_field(candidate):
            responsible_field = candidate
            break

    fields = [
        "name",
        employee_field,
        name_field,
        "request_date",
        "outcome",
        "outcome_date",
        "docstatus",
    ]
    if branch_field:
        fields.append(branch_field)
    if responsible_field:
        fields.append(responsible_field)

    opened = frappe.get_all(
        doctype,
        filters={
            "company": company,
            "docstatus": ["<", 2],
            "request_date": ["between", [from_date, to_date]],
        },
        fields=fields,
        order_by="request_date asc, name asc",
    )

    closed = frappe.get_all(
        doctype,
        filters={
            "company": company,
            "docstatus": ["<", 2],
            "outcome_date": ["between", [from_date, to_date]],
        },
        fields=fields,
        order_by="outcome_date asc, name asc",
    )

    outstanding = frappe.get_all(
        doctype,
        filters={
            "company": company,
            "docstatus": 0,
        },
        fields=fields,
        order_by="request_date asc, name asc",
    )

    for collection in (opened, closed, outstanding):
        for row in collection:
            row["employee_name"] = row.get(name_field) or row.get(employee_field) or ""
            if responsible_field:
                row["responsible_ir_display"] = row.get(responsible_field) or ""

    today = getdate()
    ageing = {"0_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for row in outstanding:
        age = max(date_diff(today, getdate(row.request_date)), 0) if row.request_date else 0
        row["age_days"] = age
        if age <= 30:
            ageing["0_30"] += 1
        elif age <= 60:
            ageing["31_60"] += 1
        elif age <= 90:
            ageing["61_90"] += 1
        else:
            ageing["over_90"] += 1

    duration_values = [
        date_diff(getdate(row.outcome_date), getdate(row.request_date))
        for row in closed
        if row.get("outcome_date") and row.get("request_date")
    ]

    return {
        "opened": {"count": len(opened), "rows": opened},
        "closed": {"count": len(closed), "rows": closed},
        "outstanding": {"count": len(outstanding), "rows": outstanding, "ageing": ageing},
        "average_days_to_close": flt(sum(duration_values) / len(duration_values), 1) if duration_values else 0,
    }


def _outcome_labels():
    return {
        row.name: (row.disc_offence_out or row.name)
        for row in frappe.get_all("Offence Outcome", fields=["name", "disc_offence_out"])
    }


def _poor_performance_summary(company, from_date, to_date):
    frappe.has_permission("Poor Performance", "read", throw=True)
    labels = _outcome_labels()
    fields = [
        "name",
        "employee",
        "employee_name",
        "branch",
        "request_date",
        "creation",
        "outcome",
        "outcome_date",
        "docstatus",
        "ir_name",
    ]

    rows = frappe.get_all(
        "Poor Performance",
        filters={"company": company, "docstatus": ["<", 2]},
        fields=fields,
        order_by="employee asc, creation asc",
    )

    def outcome_label(row):
        return labels.get(row.get("outcome"), row.get("outcome") or "")

    opened = [
        row for row in rows if row.get("request_date") and from_date <= getdate(row.request_date) <= to_date
    ]
    closed = [
        row
        for row in rows
        if row.get("outcome_date")
        and from_date <= getdate(row.outcome_date) <= to_date
        and outcome_label(row) in TERMINAL_POOR_PERFORMANCE_OUTCOMES
    ]

    outstanding = []
    for row in rows:
        if row.docstatus == 0:
            row["status_reason"] = _("Draft - not submitted")
            outstanding.append(row)

    today = getdate()
    ageing = {"0_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for row in outstanding:
        row["outcome_label"] = outcome_label(row)
        age = max(date_diff(today, getdate(row.request_date)), 0) if row.request_date else 0
        row["age_days"] = age
        if age <= 30:
            ageing["0_30"] += 1
        elif age <= 60:
            ageing["31_60"] += 1
        elif age <= 90:
            ageing["61_90"] += 1
        else:
            ageing["over_90"] += 1

    durations = [
        date_diff(getdate(row.outcome_date), getdate(row.request_date))
        for row in closed
        if row.get("request_date") and row.get("outcome_date")
    ]

    return {
        "opened": {"count": len(opened), "rows": opened},
        "closed": {"count": len(closed), "rows": closed},
        "outstanding": {"count": len(outstanding), "rows": outstanding, "ageing": ageing},
        "average_days_to_close": flt(sum(durations) / len(durations), 1) if durations else 0,
    }


def _external_dispute_summary(company, from_date, to_date):
    doctype = "External Dispute Resolution"
    frappe.has_permission(doctype, "read", throw=True)

    fields = [
        "name",
        "case_no",
        "forum",
        "applicant_external",
        "respondent_external",
        "company",
        "outcome",
        "creation",
        "modified",
        "docstatus",
    ]

    rows = frappe.get_all(
        doctype,
        filters={"company": company, "docstatus": ["<", 2]},
        fields=fields,
        order_by="creation asc, name asc",
    )

    opened = [
        row for row in rows
        if row.get("creation") and from_date <= getdate(row.creation) <= to_date
    ]
    closed = [
        row for row in rows
        if row.get("outcome") and row.get("modified") and from_date <= getdate(row.modified) <= to_date
    ]
    outstanding = [row for row in rows if row.docstatus == 0]

    today_date = getdate()
    ageing = {"0_30": 0, "31_60": 0, "61_90": 0, "over_90": 0}
    for row in outstanding:
        row["request_date"] = row.get("creation")
        row["employee_name"] = row.get("applicant_external") or ""
        row["status_reason"] = _("Draft - not submitted")
        age = max(date_diff(today_date, getdate(row.creation)), 0) if row.get("creation") else 0
        row["age_days"] = age
        if age <= 30:
            ageing["0_30"] += 1
        elif age <= 60:
            ageing["31_60"] += 1
        elif age <= 90:
            ageing["61_90"] += 1
        else:
            ageing["over_90"] += 1

    durations = [
        date_diff(getdate(row.modified), getdate(row.creation))
        for row in closed
        if row.get("creation") and row.get("modified")
    ]

    forum_counts = defaultdict(int)
    for row in outstanding:
        forum_counts[row.get("forum") or _("Unspecified")] += 1

    return {
        "opened": {"count": len(opened), "rows": opened},
        "closed": {"count": len(closed), "rows": closed},
        "outstanding": {"count": len(outstanding), "rows": outstanding, "ageing": ageing},
        "average_days_to_close": flt(sum(durations) / len(durations), 1) if durations else 0,
        "fora": [
            {"forum": forum, "count": count}
            for forum, count in sorted(forum_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }


@frappe.whitelist()
def get_page_defaults():
    company = (
        frappe.defaults.get_user_default("Company")
        or frappe.defaults.get_global_default("company")
        or frappe.db.get_value("Company", {}, "name", order_by="creation asc")
    )
    current_date = getdate(today())
    return {
        "company": company,
        "from_date": str(get_first_day(current_date)),
        "to_date": str(current_date),
    }


@frappe.whitelist()
def get_report_data(company, from_date, to_date):
    frappe.only_for(["System Manager", "IR Manager", "IR Officer", "IR User"])
    frappe.has_permission("Employee", "read", throw=True)
    from_date, to_date = _validate_filters(company, from_date, to_date)

    workforce = _employee_movements(company, from_date, to_date)
    disciplinary = _process_summary(
        "Disciplinary Action", "accused", company, from_date, to_date
    )
    incapacity = _process_summary(
        "Incapacity Proceedings", "accused", company, from_date, to_date
    )
    poor_performance = _poor_performance_summary(company, from_date, to_date)
    external_disputes = _external_dispute_summary(company, from_date, to_date)

    opened_total = (
        disciplinary["opened"]["count"]
        + incapacity["opened"]["count"]
        + poor_performance["opened"]["count"]
        + external_disputes["opened"]["count"]
    )
    closed_total = (
        disciplinary["closed"]["count"]
        + incapacity["closed"]["count"]
        + poor_performance["closed"]["count"]
        + external_disputes["closed"]["count"]
    )
    outstanding_total = (
        disciplinary["outstanding"]["count"]
        + incapacity["outstanding"]["count"]
        + poor_performance["outstanding"]["count"]
        + external_disputes["outstanding"]["count"]
    )

    return {
        "company": company,
        "from_date": str(from_date),
        "to_date": str(to_date),
        "generated_at": str(now_datetime()),
        "workforce": workforce,
        "disciplinary": disciplinary,
        "incapacity": incapacity,
        "poor_performance": poor_performance,
        "external_disputes": external_disputes,
        "combined": {
            "opened": opened_total,
            "closed": closed_total,
            "outstanding": outstanding_total,
            "net_backlog_change": opened_total - closed_total,
        },
        "employment_equity": _build_ee_profile(company, to_date),
    }
