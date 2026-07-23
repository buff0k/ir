import frappe


@frappe.whitelist()
def get_designation_defaults(designation):
    frappe.has_permission("Designation", "read", throw=True)

    if not designation or not frappe.db.exists("Designation", designation):
        return {
            "experience_required": "",
            "main_duties_and_responsibilities": "",
            "acceptable_disabilities": "",
            "skills": [],
        }

    designation_doc = frappe.db.get_value(
        "Designation",
        designation,
        ["ir_experience_required", "ir_main_duties_and_responsibilities", "ir_acceptable_disabilities"],
        as_dict=True,
    )

    skills = frappe.get_all(
        "Designation Skill",
        filters={"parent": designation, "parenttype": "Designation", "parentfield": "skills"},
        fields=["skill"],
        order_by="idx",
    )

    return {
        "experience_required": designation_doc.ir_experience_required or "",
        "main_duties_and_responsibilities": designation_doc.ir_main_duties_and_responsibilities or "",
        "acceptable_disabilities": designation_doc.ir_acceptable_disabilities or "",
        "skills": [row.skill for row in skills],
    }
