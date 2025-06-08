from frappe import _

def get_data():
    return [
        {
            "module_name": "Industrial Relations",
            "category": "Modules",
            "label": _("Industrial Relations"),
            "color": "FF5733",
            "icon": "/assets/ir/images/ir-logo.svg",
            "type": "module",
            "description": _("Industrial Relations Management Suite"),
            "onboard_present": 1,
        }
    ]
