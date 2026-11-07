# Copyright (c) 2026, BuFf0k and contributors
# For license information, please see license.txt

"""Resolves the site's own brand color for print format CSS, instead of a
hardcoded hex value.

Frappe's print rendering (frappe/www/printview.py) appends a Print Format's
`css` field to the page as a raw string - it is never passed through Jinja,
regardless of print_format_type - so `{{ get_brand_primary_color() }}` inside
that field would print literally rather than resolve. CSS custom properties
aren't a workaround either: this bench's wkhtmltopdf (0.12.6.1) drops the
whole declaration, fallback included, when a value contains var(). So the
only reliable mechanism is to resolve the color here in Python and stamp the
literal hex directly into the stored css field - see sync_print_format_brand_colors.
"""

import re

import frappe

FALLBACK_PRIMARY_COLOR = "#b40000"

# Marks the brand-red border declarations in these Print Formats' `css` field
# (added directly after the hex value, e.g. `#b40000 /* ir-brand-primary */`)
# so sync_print_format_brand_colors can find and re-stamp them regardless of
# what hex value is currently sitting there.
BRAND_COLOR_MARKER = re.compile(r"#[0-9a-fA-F]{3,8}(?=\s*/\* ir-brand-primary \*/)")

BRAND_MARKED_PRINT_FORMATS = [
	"Request to Recruit",
	"Dismissal Form",
	"Disciplinary Action Summary",
	"Schedule of Offences Standard",
	"Status Change Form",
	"NTA Enquiry",
	"Suspension Form",
	"Termination Form",
	"Site Transfer Form",
	"No Further Action Form",
	"KPI Review",
	"Warning Form",
	"Voluntary Seperation Agreement",
	"Job Advertisement",
	"Area KPI Review",
]


def get_brand_primary_color(fallback=FALLBACK_PRIMARY_COLOR):
	"""The active Website Theme's Primary Color, resolved to its hex value.

	Website Theme is a public-website-portal concept, not something Frappe
	wires into Desk print formats on its own - this is what makes it apply
	here too. Falls back if no theme is active, or the active one (e.g. the
	stock "Standard" theme) has no Primary Color configured.
	"""
	theme_name = frappe.get_cached_value("Website Settings", "Website Settings", "website_theme")
	if not theme_name:
		return fallback

	color_name = frappe.get_cached_value("Website Theme", theme_name, "primary_color")
	if not color_name:
		return fallback

	hex_value = frappe.get_cached_value("Color", color_name, "color")
	return hex_value or fallback


def sync_print_format_brand_colors():
	"""Re-stamps the marked brand-red borders in BRAND_MARKED_PRINT_FORMATS
	with the site's current brand color. Run from after_migrate (not a
	one-time patch) since the right color can change whenever the active
	Website Theme does, and the marker comment makes each re-stamp
	idempotent regardless of what value was last written.
	"""
	color = get_brand_primary_color()
	for name in BRAND_MARKED_PRINT_FORMATS:
		css = frappe.db.get_value("Print Format", name, "css")
		if not css:
			continue
		new_css = BRAND_COLOR_MARKER.sub(color, css)
		if new_css != css:
			frappe.db.set_value("Print Format", name, "css", new_css, update_modified=False)
	frappe.db.commit()
