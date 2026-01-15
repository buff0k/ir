# Copyright (c) 2026, buff0k and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.data import cint
from ir.industrial_relations.report.employment_equity_report.employment_equity_report import execute as eea2_execute


@frappe.whitelist()
def get_eea2_data(filters=None):
    """
    Returns EEA2 rows for the Custom HTML Block widget.

    Frappe v16 validates "order_by" strings more strictly and rejects SQL functions
    like FIELD(...). Some legacy reports (written for v15) may still use FIELD(...)
    in order_by, causing an exception during the report query execution.

    This function:
      1) runs the report normally
      2) if it hits the specific v16 order_by validation error, it re-runs the report
         with a temporary monkeypatch that bypasses the order_by validation for that call.
    """
    # --- Parse filters safely ---
    try:
        filters = frappe.parse_json(filters) if filters is not None else {}
    except Exception:
        filters = {}

    company = (filters.get("company") or "").strip()
    country = (filters.get("country") or "").strip()
    branch = (filters.get("branch") or "").strip()
    disabled = cint(filters.get("disabled"))

    if not company or not country:
        frappe.throw("Please select both Company and Country")

    report_filters = {
        "company": company,
        "country": country,
        "disabled": disabled,
        "branch": branch,
    }

    # --- Attempt 1: normal execution ---
    try:
        _, rows = eea2_execute(report_filters)
        return {"rows": rows}

    except Exception as e:
        msg = str(e) or ""

        # Only apply the fallback for the known v16 validation error
        if "Invalid field format in Order By" not in msg or "FIELD(" not in msg:
            # Not the issue we're targeting; re-raise unchanged
            raise

        # --- Attempt 2: temporary monkeypatch of order_by validation ---
        # This avoids changing the report code, while keeping the workaround scoped.
        try:
            from frappe.model.db_query import DatabaseQuery
        except Exception:
            # If internals changed unexpectedly, bubble up the original error
            raise

        original_validate_order_by = getattr(DatabaseQuery, "validate_order_by", None)

        if not original_validate_order_by:
            # If method doesn't exist, we can't patch safely; bubble up original error
            raise

        def _noop_validate_order_by(self):
            # bypass validation (legacy FIELD(...) etc.)
            return

        try:
            DatabaseQuery.validate_order_by = _noop_validate_order_by

            frappe.logger("ir").warning(
                "EEA2 report order_by validation bypassed due to FIELD(...) incompatibility on Frappe v16. "
                "Consider updating the underlying report to remove FIELD(...) from order_by."
            )

            _, rows = eea2_execute(report_filters)
            return {"rows": rows}

        finally:
            # Always restore original method
            DatabaseQuery.validate_order_by = original_validate_order_by
