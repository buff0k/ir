import json
from pathlib import Path

from za_local.tests.compat import UnitTestCase


class TestCompanyContribution(UnitTestCase):
	def test_company_contribution_is_a_standard_app_doctype(self):
		path = Path(__file__).resolve().parent / "company_contribution.json"
		data = json.loads(path.read_text())
		self.assertEqual("ir_payroll", data["module"])
		self.assertEqual(1, data["istable"])
		self.assertFalse(data.get("custom", 0))
