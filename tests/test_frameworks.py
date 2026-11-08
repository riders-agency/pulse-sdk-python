import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pulse_sdk.frameworks import from_authorization, from_request


class FrameworkTests(unittest.TestCase):
    def test_request_scope_and_missing_authorization(self):
        with patch("pulse_sdk.frameworks.PulseClient") as client:
            from_request(
                "https://pulse.example.test",
                SimpleNamespace(headers={"authorization": "Bearer alice"}),
            )
            from_authorization("https://pulse.example.test", "bearer bob")
            self.assertEqual(client.call_args_list[0].args[1], "alice")
            self.assertEqual(client.call_args_list[1].args[1], "bob")
            for header in (
                None,
                "",
                "Basic token",
                "Bearer invalid token",
                "Bearer token\n",
            ):
                with self.assertRaises(ValueError):
                    from_authorization("https://pulse.example.test", header)
            self.assertEqual(client.call_count, 2)
