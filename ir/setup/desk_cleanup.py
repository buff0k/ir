# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

# ir/setup/desk_cleanup.py
import frappe

SIDEBARS_TO_DELETE = [
    "Disciplinary Action",
    "IR General",
    "IR Setup",
    "IR Training",
    "IR Attendance",
]

ICONS_TO_DELETE = [
    "Disciplinary Action",
    "IR General",
    "IR Setup",
    "IR Training",
    "IR Attendance",
]

def cleanup_autogen_workspaces_sidebars_and_icons():
    # Delete Workspace Sidebars (ignore if missing)
    for name in SIDEBARS_TO_DELETE:
        if frappe.db.exists("Workspace Sidebar", name):
            frappe.delete_doc("Workspace Sidebar", name, force=1)

    # Delete Desktop Icons (ignore if missing)
    for name in ICONS_TO_DELETE:
        if frappe.db.exists("Desktop Icon", name):
            frappe.delete_doc("Desktop Icon", name, force=1)

    frappe.db.commit()
