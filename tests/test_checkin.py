import unittest
from datetime import date

from checkin import CheckinError, checked_today, classify, credentials, redact


class ResultTests(unittest.TestCase):
    def test_verification_rejections_are_never_success(self):
        for response in ({"code": 5}, {"code": 4, "reason": "device-mismatch"},
                         {"code": -2}, {"code": 2, "reason": "turnstile"},
                         {"code": False}, {"code": "0"}, {"code": 999}, []):
            with self.subTest(response=response), self.assertRaises(CheckinError):
                classify(response)

    def test_ambiguous_old_success_code_needs_ledger(self):
        self.assertEqual(classify({"code": 1}), "needs_confirmation")

    def test_new_and_repeated_success_are_distinct(self):
        self.assertEqual(classify({"code": 0}), "success")
        self.assertEqual(classify({"code": 0, "repeated": True}), "already_checked")

    def test_beijing_midnight_and_milliseconds(self):
        for time in ("2026-11-14T16:00:00Z", 1794672000, 1794672000000):
            self.assertTrue(checked_today({"code": 0, "history": [
                {"business": "checkin", "time": time}]}, date(2026, 11, 15)))

    def test_yesterday_other_business_and_unknown_dates_do_not_skip(self):
        for record in ({"business": "checkin", "time": "2026-11-14T15:59:59Z"},
                       {"business": "exchange", "time": "2026-11-15T00:00:00Z"},
                       {"business": "checkin", "time": "2026-11-15T00:00:00"},
                       {"business": "checkin", "time": None},
                       {"business": "checkin", "time": True}):
            self.assertFalse(checked_today({"code": 0, "history": [record]}, date(2026, 11, 15)))

    def test_missing_ledger_is_not_proof(self):
        for response in ({"code": 0}, {"code": -2, "history": []}, {"code": False}, []):
            self.assertFalse(checked_today(response))

    def test_cookie_value_keeps_equals(self):
        cookies, _ = credentials({"GLADOS_COOKIE": "Cookie: session=abc==; signature=xyz",
                                  "GLADOS_USER_AGENT": "test-agent"})
        self.assertEqual(cookies[0]["value"], "abc==")
        self.assertEqual(cookies[0]["url"], "https://glados.cloud/")

    def test_credentials_reject_header_injection(self):
        with self.assertRaises(CheckinError):
            credentials({"GLADOS_COOKIE": "a=b\nInjected: yes", "GLADOS_USER_AGENT": "agent"})

    def test_secret_redaction(self):
        cookies = [{"value": 'secret"value'}]
        self.assertEqual(redact('echo secret"value', cookies), "echo [REDACTED]")


if __name__ == "__main__":
    unittest.main()
