# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class KPIReview(Document):
    def validate(self):
        self.recalculate_weighted_scores()
        self.ensure_score_limits()

    def before_submit(self):
        if not self.kpi_attach:
            frappe.throw("You must attach a KPI document before submitting.")

    def recalculate_weighted_scores(self):
        scores = {}
        parents = {}
        kpi_lookup = {}

        for row in self.review_data:
            # Fetch KPI doc
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            kpi_lookup[row.kpi] = kpi_doc

            if kpi_doc.is_group:
                parents[row.kpi] = row
            else:
                # Compute individual weighted score
                row.weighted_score = round((row.score or 0) / row.max_score * row.weight, 2)

                # Resolve parent from KPI master
                parent = getattr(kpi_doc, "parent_kpi", None)
                if parent:
                    scores.setdefault(parent, []).append(row)

        # Aggregate parent (group) scores
        for parent_kpi, children in scores.items():
            if parent_kpi in parents:
                total = sum(child.weighted_score for child in children)
                parents[parent_kpi].weighted_score = round(total, 2)

    def ensure_score_limits(self):
        for row in self.review_data:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if not kpi_doc.is_group and row.score > row.max_score:
                frappe.throw(f"Score for KPI '{row.kpi}' cannot exceed its max of {row.max_score}.")
