# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
import json
from frappe.model.document import Document
from frappe.utils import getdate, today, add_months

class DisciplinaryAction(Document):
    pass

@frappe.whitelist()
def fetch_employee_data(employee, fields):
    frappe.flags.ignore_permissions = True

    # Parse the fields argument from JSON string to dictionary
    fields = json.loads(fields)

    data = {}
    for field in fields:
        value = frappe.db.get_value('Employee', employee, field)
        data[fields[field]] = value if value else ''
    
    return data

@frappe.whitelist()
def fetch_default_letter_head(company):
    frappe.flags.ignore_permissions = True

    letter_head = frappe.db.get_value('Company', company, 'default_letter_head')
    return letter_head if letter_head else ''

@frappe.whitelist()
def fetch_disciplinary_history(accused, current_doc_name):
    frappe.flags.ignore_permissions = True

    disciplinary_actions = frappe.get_all('Disciplinary Action', filters={
        'accused': accused,
        'name': ['!=', current_doc_name]
    }, fields=['name', 'outcome_date', 'outcome'])

    history = []

    for action in disciplinary_actions:
        action_doc = frappe.get_doc('Disciplinary Action', action.name)
        charges = '\n'.join([f"({charge_row.code_item}) {charge_row.charge}" for charge_row in action_doc.final_charges])

        # Check if the outcome is linked to an "Offence Outcome" document
        if action_doc.outcome:
            offence_outcome = frappe.get_doc('Offence Outcome', action_doc.outcome)
            sanction = offence_outcome.disc_offence_out if offence_outcome else f"Pending {action_doc.name}"
        else:
            sanction = f"Pending {action_doc.name}"

        history.append({
            'disc_action': action_doc.name,
            'date': action_doc.outcome_date,
            'sanction': sanction,
            'charges': charges
        })

    return history

import frappe

@frappe.whitelist()
def get_linked_doctypes(disciplinary_action_name: str) -> dict:
    """
    Build row lists for the 13 virtual Table Multiselect fields on Disciplinary Action,
    by scanning target doctypes for records linked back to this Disciplinary Action.

    Returns:
        {
          "<tms_field>": [ { "<child_link_field>": "<TARGET-NAME>" }, ... ],
          ...
        }
    """
    frappe.flags.ignore_permissions = True

    # Map: TMS field (on Disciplinary Action) -> (Child Table, Target Doctype, Backref field on target)
    mappings = [
        ("linked_nta",             "NTA Selector",                  "NTA Hearing",                     "linked_disciplinary_action"),
        ("linked_outcome",         "Outcome Selector",              "Written Outcome",                 "linked_intervention"),
        ("linked_disc_outcome",    "Disciplinary Outcome Selector", "Disciplinary Outcome Report",     "linked_disciplinary_action"),
        ("linked_warning",         "Warning Selector",              "Warning Form",                    "linked_disciplinary_action"),
        ("linked_dismissal",       "Dismissal Selector",            "Dismissal Form",                  "linked_disciplinary_action"),
        ("linked_demotion",        "Demotion Selector",             "Demotion Form",                   "linked_disciplinary_action"),
        ("linked_pay_deduction",   "Pay Deduction Selector",        "Pay Deduction Form",              "linked_disciplinary_action"),
        ("linked_pay_reduction",   "Pay Reduction Selector",        "Pay Reduction Form",              "linked_disciplinary_action"),
        ("linked_not_guilty",      "Not Guilty Selector",           "Not Guilty Form",                 "linked_disciplinary_action"),
        ("linked_suspension",      "Suspension Selector",           "Suspension Form",                 "linked_disciplinary_action"),
        ("linked_vsp",             "Voluntary Separation Selector", "Voluntary Seperation Agreement",  "linked_disciplinary_action"),
        ("linked_cancellation",    "Cancellation Selector",         "Hearing Cancellation Form",       "linked_disciplinary_action"),
        ("linked_appeal",          "Appeal Selector",               "Appeal Against Outcome",          "linked_disciplinary_action"),
    ]

    def get_child_link_field(child_doctype: str, target_doctype: str) -> str | None:
        """
        Return the (single) Link fieldname in the child table that points to the target doctype.
        If multiple Link fields exist, prefer the one whose options == target_doctype.
        """
        try:
            meta = frappe.get_meta(child_doctype)
        except Exception as e:
            frappe.log_error(f"Meta load failed for {child_doctype}: {e}", "get_linked_doctypes")
            return None

        link_fields = [df for df in meta.fields if df.fieldtype == "Link"]
        if not link_fields:
            return None

        # Prefer an exact match on options
        for df in link_fields:
            if (df.options or "").strip() == target_doctype:
                return df.fieldname

        # Else, if there's exactly one Link field, use it
        if len(link_fields) == 1:
            return link_fields[0].fieldname

        # Fallback: first Link field (shouldn't be needed if your schema matches the spec)
        return link_fields[0].fieldname

    def fetch_target_names(target_doctype: str, backref_field: str, da_name: str) -> list[str]:
        try:
            rows = frappe.get_all(
                target_doctype,
                filters={backref_field: da_name},
                fields=["name"],
                order_by="modified desc",
            )
            # Deduplicate while preserving order
            seen = set()
            out = []
            for r in rows:
                nm = r["name"]
                if nm not in seen:
                    seen.add(nm)
                    out.append(nm)
            return out
        except Exception as e:
            frappe.log_error(
                f"Query failed for {target_doctype}.{backref_field}='{da_name}': {e}",
                "get_linked_doctypes",
            )
            return []

    result: dict[str, list[dict]] = {}

    for tms_field, child_dt, target_dt, backref in mappings:
        try:
            child_link_field = get_child_link_field(child_dt, target_dt)
            if not child_link_field:
                frappe.log_error(
                    f"No Link field detected in child table '{child_dt}' for target '{target_dt}'",
                    "get_linked_doctypes",
                )
                result[tms_field] = []
                continue

            target_names = fetch_target_names(target_dt, backref, disciplinary_action_name)

            # Convert to child row dicts: [{child_link_field: "DOCNAME"}, ...]
            rows = [{child_link_field: nm} for nm in target_names]

            # Sort rows by the linked name for stable UI (optional; targets already fetched by modified desc)
            rows.sort(key=lambda d: (d.get(child_link_field) or "").lower())

            result[tms_field] = rows
        except Exception as e:
            frappe.log_error(
                f"Assembly failed for TMS '{tms_field}' -> child '{child_dt}' -> target '{target_dt}': {e}",
                "get_linked_doctypes",
            )
            result[tms_field] = []

    return result

# --- Minimal compatibility wrapper for your existing JS (keep JS unchanged) ---
@frappe.whitelist()
def get_linked_documents(disciplinary_action_name: str, linked_doctype: str, linking_field: str) -> list[str]:
    """
    Compatibility endpoint used by your current JS fetch_linked_documents(frm).

    Returns a simple list of names in `linked_doctype` where `linking_field == disciplinary_action_name`.
    """
    frappe.flags.ignore_permissions = True
    try:
        rows = frappe.get_all(
            linked_doctype,
            filters={linking_field: disciplinary_action_name},
            fields=["name"],
            order_by="modified desc",  # explicit to avoid subquery validator trips
        )
        # Dedupe (paranoid) while preserving order
        seen = set()
        out = []
        for r in rows:
            nm = r["name"]
            if nm not in seen:
                seen.add(nm)
                out.append(nm)
        return out
    except Exception as e:
        frappe.log_error(
            f"get_linked_documents failed for {linked_doctype}.{linking_field}='{disciplinary_action_name}': {e}",
            "get_linked_documents",
        )
        return []

@frappe.whitelist()
def fetch_complainant_data(complainant):
    frappe.flags.ignore_permissions = True

    data = {
        'compl_name': frappe.db.get_value('Employee', complainant, 'employee_name') or '',
        'compl_pos': frappe.db.get_value('Employee', complainant, 'designation') or ''
    }
    
    return data

@frappe.whitelist()
def check_if_ss(accused):
    frappe.flags.ignore_permissions = True

    # Explicit order_by prevents inheriting unsafe ListView/DocType defaults after the Frappe upgrade
    trade_unions = frappe.get_all(
        "Trade Union",
        fields=["name"],
        order_by="name asc"
    )

    for tu in trade_unions:
        ss_list = frappe.get_all(
            "Union Shop Stewards",
            filters={"parent": tu.name, "parentfield": "ss_list", "ss_id": accused},
            fields=["ss_id"],
            order_by="modified desc"
        )
        if ss_list:
            return {"is_ss": True, "ss_union": tu.name}

    return {"is_ss": False, "ss_union": None}
