from types import SimpleNamespace
from unittest.mock import patch

from ir.overrides.customer import validate as validate_customer
from za_local.tests.compat import UnitTestCase


class TestCustomerVATValidation(UnitTestCase):
	def test_customer_vat_validation_uses_explicit_vendor_flag(self):
		with patch("ir.overrides.customer.validate_sa_vat_number") as validate_number:
			validate_customer(SimpleNamespace(tax_id="4123456789", za_is_vat_vendor=0), None)
			validate_number.assert_not_called()
			validate_customer(SimpleNamespace(tax_id="4123456789", za_is_vat_vendor=1), None)
			validate_number.assert_called_once()
