# Copyright (c) 2025, BuFf0k and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class KPITemplate(Document):
    def before_save(self):
        self.recompute_weights()

    def validate(self):
        self.validate_total_weight()
        self.validate_group_alignment()

    def recompute_weights(self):
        # Step 1: Compute summed weights for each group KPI
        group_map = {}
        for row in self.kpi:
            if row.parent_kpi and row.weight:
                group_map[row.parent_kpi] = group_map.get(row.parent_kpi, 0) + row.weight

        # Step 2: Update group KPI weights based on their children
        for row in self.kpi:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if kpi_doc.is_group and row.kpi in group_map:
                row.weight = round(group_map[row.kpi], 2)

        # Step 3: Compute total top-level weight (groups and orphans)
        total = 0
        for row in self.kpi:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if kpi_doc.is_group or not row.parent_kpi:
                total += row.weight or 0
        self.total = round(total, 2)

        # Step 4: Compute effective_weight for each row
        parent_weights = {}
        for row in self.kpi:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if kpi_doc.is_group:
                parent_weights[row.kpi] = row.weight or 0

        for row in self.kpi:
            if row.parent_kpi:
                parent_weight = parent_weights.get(row.parent_kpi, 0)
                row.effective_weight = round((row.weight or 0) * (parent_weight / 100), 2)
            else:
                row.effective_weight = row.weight or 0

    def validate_total_weight(self):
        total = 0
        errors = []

        for row in self.kpi:
            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)
            if kpi_doc.is_group or not row.parent_kpi:
                total += row.weight or 0

        if abs(total - 100) > 0.01:
            errors.append(
                f"Top-level KPI weights must total 100%. Current: <b>{total:.2f}%</b>."
            )

        if errors:
            frappe.throw("<br>".join(errors))

    def validate_group_alignment(self):
        actual = {}
        expected = {}
        errors = []

        # Step 1: Build actual and expected weight maps
        for row in self.kpi:
            if not row.weight:
                continue

            kpi_doc = frappe.get_cached_doc("Key Performance Indicator", row.kpi)

            if kpi_doc.is_group:
                expected[row.kpi] = row.weight
            elif row.parent_kpi:
                actual[row.parent_kpi] = actual.get(row.parent_kpi, 0) + row.weight

        # Step 2: Compare
        for parent, child_total in actual.items():
            group_weight = expected.get(parent, 0)
            if abs(child_total - group_weight) > 0.01:
                errors.append(
                    f"Children of <b>{parent}</b> sum to <b>{child_total:.2f}%</b>, "
                    f"but parent shows <b>{group_weight:.2f}%</b>."
                )

        if errors:
            frappe.throw("<br>".join(errors))
