import json
import logging
import unittest

from utils.logging import JsonFormatter, sanitize_context


class StructuredLoggingTests(unittest.TestCase):
    def test_sensitive_context_keys_are_redacted_recursively(self):
        safe = sanitize_context(
            {
                "account_id": 7,
                "token": "secret-token",
                "nested": {
                    "proxy_pass": "secret-password",
                    "media_type": "video",
                },
            }
        )

        self.assertEqual(safe["account_id"], 7)
        self.assertEqual(safe["token"], "[REDACTED]")
        self.assertEqual(safe["nested"]["proxy_pass"], "[REDACTED]")
        self.assertEqual(safe["nested"]["media_type"], "video")

    def test_json_formatter_emits_event_and_safe_context(self):
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="media_ready",
            args=(),
            exc_info=None,
        )
        record.event = "media_ready"
        record.context = {
            "message_id": 42,
            "session_string": "do-not-log",
        }

        payload = json.loads(JsonFormatter().format(record))

        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["event"], "media_ready")
        self.assertEqual(payload["context"]["message_id"], 42)
        self.assertEqual(
            payload["context"]["session_string"],
            "[REDACTED]",
        )
        self.assertNotIn("do-not-log", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
