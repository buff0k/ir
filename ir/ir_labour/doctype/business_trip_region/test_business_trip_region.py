from unittest.mock import patch

from ir.ir_labour.doctype.business_trip_region.business_trip_region import get_active_regions
from ir.tests.compat import UnitTestCase


class TestBusinessTripRegion(UnitTestCase):
	def test_active_region_query_requires_read_permission(self):
		with (
			patch("frappe.has_permission") as has_permission,
			patch("frappe.db.sql", return_value=[]),
		):
			get_active_regions(None, "", "name", 0, 20, {})

		has_permission.assert_called_once_with("Business Trip Region", "read", throw=True)
