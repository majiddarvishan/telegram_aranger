import unittest

from ui.theme import (
    APP_CSS,
    DESIGN_TOKENS,
    MESSAGE_HEADER_CSS,
    account_card_html,
    action_summary_html,
    auth_brand_html,
    badge_html,
    empty_state_html,
    media_meta_html,
    message_body_html,
    message_meta_html,
    section_title_html,
    sidebar_brand_html,
    tag_chips_html,
)


class ThemeFoundationTests(unittest.TestCase):
    def test_semantic_design_tokens_are_defined(self):
        self.assertEqual(DESIGN_TOKENS["space_1"], "4px")
        self.assertEqual(DESIGN_TOKENS["space_6"], "32px")
        self.assertEqual(DESIGN_TOKENS["radius_control"], "8px")
        self.assertEqual(DESIGN_TOKENS["radius_panel"], "12px")
        self.assertEqual(DESIGN_TOKENS["control_height"], "40px")
        self.assertEqual(DESIGN_TOKENS["top_safe_area"], "48px")
        self.assertEqual(DESIGN_TOKENS["motion_fast"], "120ms")
        self.assertEqual(DESIGN_TOKENS["motion_normal"], "180ms")

    def test_theme_uses_streamlit_accent_and_transparent_surfaces(self):
        self.assertIn("var(--primary-color", APP_CSS)
        self.assertIn("--th-bg: transparent", APP_CSS)
        self.assertIn(
            "--th-surface: rgba(128, 128, 128, 0.06)",
            APP_CSS,
        )
        self.assertNotIn(
            "--th-text: var(--text-color",
            APP_CSS,
        )

    def test_theme_does_not_force_light_card_backgrounds(self):
        self.assertNotIn(
            "background: var(--th-bg)",
            APP_CSS,
        )
        self.assertIn("background: transparent", APP_CSS)
        self.assertIn("color: inherit", APP_CSS)

    def test_main_content_keeps_safe_distance_from_streamlit_toolbar(self):
        self.assertIn("--th-top-safe-area: 48px", APP_CSS)
        self.assertIn(
            "padding-top: var(--th-top-safe-area)",
            APP_CSS,
        )
        self.assertIn(
            '[data-testid="stMainBlockContainer"]',
            APP_CSS,
        )
        self.assertIn("overflow: visible", APP_CSS)
        self.assertIn(
            "margin-top: var(--th-space-2)",
            MESSAGE_HEADER_CSS,
        )

    def test_message_layout_styles_are_centralized(self):
        self.assertIn(".st-key-message-header", MESSAGE_HEADER_CSS)
        self.assertIn(".st-key-message-scroll-area", MESSAGE_HEADER_CSS)
        self.assertIn("position: relative", MESSAGE_HEADER_CSS)
        self.assertNotIn("position: fixed", MESSAGE_HEADER_CSS)

    def test_polish_states_cover_hover_focus_and_active_context(self):
        self.assertIn(
            ".st-key-chat_selector [data-baseweb=\"select\"] > div",
            APP_CSS,
        )
        self.assertIn(
            '[data-testid="stSidebar"] [data-testid="stSelectbox"]',
            APP_CSS,
        )
        self.assertIn(":focus-within", APP_CSS)
        self.assertIn(":active", APP_CSS)
        self.assertIn(
            '[data-testid="stVerticalBlockBorderWrapper"]:hover',
            APP_CSS,
        )
        self.assertIn(".th-tag-chip:hover", APP_CSS)
        self.assertIn(
            ".st-key-message-header::before",
            MESSAGE_HEADER_CSS,
        )

    def test_compact_viewport_polish_is_defined(self):
        self.assertIn("@media (max-width: 700px)", APP_CSS)
        self.assertIn("padding-top: 36px", APP_CSS)

    def test_reduced_motion_is_respected(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", APP_CSS)

    def test_badge_markup_escapes_user_visible_text(self):
        markup = badge_html("<Admin>", "success")

        self.assertIn("th-badge--success", markup)
        self.assertIn("&lt;Admin&gt;", markup)
        self.assertNotIn("<Admin>", markup)

    def test_unknown_badge_tone_falls_back_to_neutral(self):
        markup = badge_html("Connected", "unknown")

        self.assertIn('class="th-badge"', markup)
        self.assertNotIn("th-badge--unknown", markup)

    def test_section_title_markup_escapes_text(self):
        markup = section_title_html("<Network>")

        self.assertIn("th-section-title", markup)
        self.assertIn("&lt;Network&gt;", markup)

    def test_tag_chips_escape_user_text(self):
        markup = tag_chips_html(["work", "<admin>"])

        self.assertIn("th-tag-chip", markup)
        self.assertIn("work", markup)
        self.assertIn("&lt;admin&gt;", markup)
        self.assertNotIn("<admin>", markup)

    def test_message_meta_markup_is_compact_and_safe(self):
        markup = message_meta_html(
            "2026-09-25 10:00:00",
            42,
            "<Video>",
        )

        self.assertIn("th-message-meta", markup)
        self.assertIn("ID 42", markup)
        self.assertIn("&lt;Video&gt;", markup)

    def test_message_body_is_safe_and_direction_aware(self):
        markup = message_body_html("<b>سلام</b>")

        self.assertIn('class="th-message-body"', markup)
        self.assertIn('dir="auto"', markup)
        self.assertIn("&lt;b&gt;سلام&lt;/b&gt;", markup)
        self.assertNotIn("<b>سلام</b>", markup)

    def test_sidebar_brand_and_account_markup_are_safe(self):
        brand = sidebar_brand_html("<Harbor>", "1.0.4")
        account = account_card_html("<Admin>", "user<1>")

        self.assertIn("&lt;Harbor&gt;", brand)
        self.assertIn("&lt;Admin&gt;", account)
        self.assertIn("user&lt;1&gt;", account)

    def test_action_summary_and_media_meta_are_compact(self):
        summary = action_summary_html(12, 100)
        media = media_meta_html(["Video", "2.0 MB", "49s"])

        self.assertIn("12", summary)
        self.assertIn("100", summary)
        self.assertIn("th-media-meta", media)
        self.assertIn("2.0 MB", media)

    def test_auth_and_empty_state_markup_are_safe(self):
        auth = auth_brand_html(
            "<Harbor>",
            "Message <manager>",
            "1.0.4",
        )
        empty = empty_state_html(
            "<No messages>",
            "Try <again>",
            "0",
        )

        self.assertIn("&lt;Harbor&gt;", auth)
        self.assertIn("Message &lt;manager&gt;", auth)
        self.assertIn("&lt;No messages&gt;", empty)
        self.assertIn("Try &lt;again&gt;", empty)


if __name__ == "__main__":
    unittest.main()
