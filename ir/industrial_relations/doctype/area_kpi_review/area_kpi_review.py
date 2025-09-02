# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

# area_kpi_review.py

import frappe
from frappe.model.document import Document
from frappe.utils import get_first_day, get_last_day
from collections import defaultdict

class AreaKPIReview(Document):
    def before_submit(self):
        if not self.kpi_attach:
            frappe.throw("You must attach a signed KPI Review before submitting.")

@frappe.whitelist()
def fetch_kpi_reviews_for_area(docname):
    doc = frappe.get_doc("Area KPI Review", docname)
    area_doc = frappe.get_doc("Area Setup", doc.area)
    start = get_first_day(doc.date_under_review)
    end = get_last_day(doc.date_under_review)

    doc.set("kpi_reviews", [])

    for row in area_doc.branches:
        branch = row.branch
        review = frappe.get_all("KPI Review", filters={
            "branch": branch,
            "date_under_review": (">=", start),
            "date_under_review": ("<=", end),
            "docstatus": ["in", [0, 1]]
        }, fields=["name", "branch", "kpi_template", "score"], limit=1)

        if review:
            review = review[0]
            doc.append("kpi_reviews", {
                "kpi_review": review.name,
                "branch": review.branch,
                "kpi_template": review.kpi_template,
                "score": review.score
            })
        else:
            frappe.msgprint(f"No KPI Review found for site '{branch}' in selected month.")

    doc.save()

@frappe.whitelist()
def aggregate_area_kpi_data(docname):
    doc = frappe.get_doc("Area KPI Review", docname)

    # Check templates
    templates = {row.kpi_template for row in doc.kpi_reviews if row.kpi_template}
    if len(templates) > 1:
        raise frappe.ValidationError("All KPI Reviews must use the same KPI Template.")

    template = list(templates)[0] if templates else None
    if template:
        doc.kpi_template = template

    # Pull all review_data rows from referenced KPI Reviews
    aggregate = defaultdict(lambda: {
        "weight": 0, "max_score": 0, "score": 0, "weighted_score": 0, "notes": []
    })

    for row in doc.kpi_reviews:
        review = frappe.get_doc("KPI Review", row.kpi_review)
        for r in review.review_data:
            a = aggregate[r.kpi]
            a["weight"] = r.weight
            a["max_score"] += r.max_score or 0
            a["score"] += r.score or 0
            a["weighted_score"] += r.weighted_score or 0
            if r.notes:
                a["notes"].append(f"{review.branch}:\n{r.notes.strip()}")

    doc.set("review_data", [])

    for kpi, values in aggregate.items():
        doc.append("review_data", {
            "kpi": kpi,
            "weight": values["weight"],
            "max_score": values["max_score"],
            "score": round(values["score"], 2),
            "weighted_score": round(values["weighted_score"], 2),
            "notes": "\n\n".join(values["notes"])
        })

    # Calculate total score exactly like in KPI Review
    total_score = 0
    total_max = 0

    for row in doc.review_data:
        try:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if not kpi_doc.is_group:
                total_score += row.score or 0
                total_max += row.max_score or 0
        except Exception:
            frappe.log_error(title="Missing KPI", message=f"Could not fetch KPI: {row.kpi}")

    if total_max > 0:
        percentage = round((total_score / total_max) * 100, 2)
        doc.score = f"{round(total_score, 2)} / {round(total_max, 2)} ({percentage}%)"
    else:
        doc.score = ""

    doc.save()
    frappe.msgprint("KPI scores aggregated successfully.")