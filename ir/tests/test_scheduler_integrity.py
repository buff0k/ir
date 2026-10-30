from ir import hooks
from ir.tests.compat import UnitTestCase


class TestSchedulerHookIntegrity(UnitTestCase):
	def test_scheduler_events_use_supported_event_names(self):
		allowed_events = {
			"all",
			"hourly",
			"hourly_long",
			"daily",
			"daily_long",
			"weekly",
			"weekly_long",
			"monthly",
			"monthly_long",
			"cron",
			"yearly",
			"annual",
		}
		self.assertTrue(set(hooks.scheduler_events).issubset(allowed_events))

	def test_absorbed_compliance_scheduler_entrypoints_are_registered(self):
		registered = {
			method
			for methods in hooks.scheduler_events.values()
			if isinstance(methods, list)
			for method in methods
		}
		self.assertTrue(
			{
				"ir.tasks.daily",
				"ir.tasks.weekly",
				"ir.tasks.monthly",
				"ir.tasks.quarterly",
			}.issubset(registered)
		)
