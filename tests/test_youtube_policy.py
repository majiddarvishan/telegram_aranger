import unittest

from services.youtube_policy import (
    GENERAL_RIGHTS_NOTICE,
    evaluate_download_policy,
)
from services.youtube_service import YouTubeServiceError


def public_metadata(**overrides):
    value = {
        "availability": "public",
        "age_limit": 0,
        "is_live": False,
        "live_status": "not_live",
        "has_drm": False,
        "formats": [
            {
                "format_id": "22",
                "has_video": True,
                "has_audio": True,
            }
        ],
    }
    value.update(overrides)
    return value


class YouTubePolicyTests(unittest.TestCase):
    def test_general_notice_always_requires_explicit_acknowledgement(self):
        pending = evaluate_download_policy(public_metadata())
        accepted = evaluate_download_policy(
            public_metadata(),
            acknowledged=True,
        )

        self.assertEqual(pending.notice, GENERAL_RIGHTS_NOTICE)
        self.assertTrue(pending.requires_acknowledgement)
        self.assertFalse(pending.can_download)
        self.assertTrue(accepted.can_download)

    def test_age_restriction_is_warning_not_legal_block_for_accessible_content(self):
        policy = evaluate_download_policy(
            public_metadata(age_limit=18),
            acknowledged=True,
        )

        self.assertFalse(policy.blocked)
        self.assertTrue(policy.can_download)
        self.assertIn(
            "age_restricted",
            {warning.code for warning in policy.warnings},
        )

    def test_live_state_is_warning_not_block(self):
        policy = evaluate_download_policy(
            public_metadata(is_live=True, live_status="is_live"),
            acknowledged=True,
        )

        self.assertFalse(policy.blocked)
        self.assertTrue(policy.can_download)
        self.assertIn(
            "live_content",
            {warning.code for warning in policy.warnings},
        )

    def test_no_reported_formats_is_stronger_warning(self):
        policy = evaluate_download_policy(
            public_metadata(formats=[]),
            acknowledged=True,
        )

        self.assertFalse(policy.blocked)
        self.assertIn(
            "formats_unavailable",
            {warning.code for warning in policy.warnings},
        )

    def test_access_control_availability_states_are_blocked(self):
        cases = {
            "private": "private_content",
            "premium_only": "premium_only",
            "subscriber_only": "members_only",
            "needs_auth": "login_required",
            "unavailable": "video_unavailable",
        }

        for availability, expected_code in cases.items():
            with self.subTest(availability=availability):
                policy = evaluate_download_policy(
                    public_metadata(availability=availability),
                    acknowledged=True,
                )
                self.assertTrue(policy.blocked)
                self.assertFalse(policy.can_download)
                self.assertEqual(policy.block_code, expected_code)

    def test_needs_auth_message_points_to_supported_sign_in_flow(self):
        policy = evaluate_download_policy(
            public_metadata(availability="needs_auth"),
            acknowledged=True,
        )
        self.assertTrue(policy.blocked)
        self.assertEqual(policy.block_code, "login_required")
        self.assertIn("Browser session", policy.block_message)
        self.assertNotIn("outside Telegram Harbor V1", policy.block_message)

    def test_needs_auth_is_allowed_when_authenticated_session_is_configured(self):
        policy = evaluate_download_policy(
            public_metadata(availability="needs_auth"),
            acknowledged=True,
            authenticated_session=True,
        )

        self.assertFalse(policy.blocked)
        self.assertTrue(policy.can_download)
        self.assertIn(
            "signed_in_access",
            {warning.code for warning in policy.warnings},
        )
        self.assertIn(
            "availability_signal",
            {warning.code for warning in policy.warnings},
        )

    def test_private_and_member_content_stay_blocked_with_authenticated_session(self):
        for availability, expected in (
            ("private", "private_content"),
            ("subscriber_only", "members_only"),
            ("premium_only", "premium_only"),
        ):
            with self.subTest(availability=availability):
                policy = evaluate_download_policy(
                    public_metadata(availability=availability),
                    acknowledged=True,
                    authenticated_session=True,
                )
                self.assertTrue(policy.blocked)
                self.assertEqual(policy.block_code, expected)

    def test_unknown_non_public_availability_fails_closed(self):
        policy = evaluate_download_policy(
            public_metadata(availability="needs_subscription"),
            acknowledged=True,
        )

        self.assertTrue(policy.blocked)
        self.assertFalse(policy.can_download)
        self.assertEqual(
            policy.block_code,
            "restricted_availability",
        )

    def test_unlisted_remains_downloadable_after_acknowledgement(self):
        policy = evaluate_download_policy(
            public_metadata(availability="unlisted"),
            acknowledged=True,
        )

        self.assertFalse(policy.blocked)
        self.assertTrue(policy.can_download)

    def test_drm_metadata_is_blocked_even_after_acknowledgement(self):
        policy = evaluate_download_policy(
            public_metadata(has_drm=True),
            acknowledged=True,
        )

        self.assertTrue(policy.blocked)
        self.assertFalse(policy.can_download)
        self.assertEqual(policy.block_code, "drm_protected")

    def test_normalized_downloader_error_blocks_execution(self):
        error = YouTubeServiceError(
            "members_only",
            "Membership is required.",
            access_restricted=True,
        )
        policy = evaluate_download_policy(
            None,
            error=error,
            acknowledged=True,
        )

        self.assertTrue(policy.blocked)
        self.assertEqual(policy.block_code, "members_only")
        self.assertFalse(policy.can_download)

    def test_notice_does_not_claim_to_determine_copyright_status(self):
        lowered = GENERAL_RIGHTS_NOTICE.lower()
        self.assertNotIn("copyrighted", lowered)
        self.assertNotIn("copyright infringement", lowered)
        self.assertIn("allowed to save", lowered)


if __name__ == "__main__":
    unittest.main()
