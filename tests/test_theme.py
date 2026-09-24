import unittest

from ui.theme import (
    APP_CSS,
    DESIGN_TOKENS,
    MESSAGE_HEADER_CSS,
    badge_html,
    message_meta_html,
    section_title_html,
    tag_chips_html,
)


class ThemeFoundationTests(unittest.TestCase):
    def test_semantic_design_tokens_are_defined(self):
        self.assertEqual(DESIGN_TOKENS["space_1"], "4px")
        self.assertEqual(DESIGN_TOKENS["space_6"], "32px")
        self.assertEqual(DESIGN_TOKENS["radius_control"], "8px")
        self.assertEqual(DESIGN_TOKENS["radius_panel"], "12px")
        self.assertEqual(DESIGN_TOKENS["control_height"], "40px")

    def test_theme_uses_streamlit_theme_variables(self):
        self.assertIn("var(--background-color", APP_CSS)
        self.assertIn("var(--secondary-background-color", APP_CSS)
        self.assertIn("var(--text-color", APP_CSS)
        self.assertIn("var(--primary-color", APP_CSS)

    def test_message_layout_styles_are_centralized(self):
        self.assertIn(".st-key-message-header", MESSAGE_HEADER_CSS)
        self.assertIn(".st-key-message-scroll-area", MESSAGE_HEADER_CSS)
        self.assertIn("position: relative", MESSAGE_HEADER_CSS)
        self.assertNotIn("position: fixed", MESSAGE_HEADER_CSS)

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


if __name__ == "__main__":
    unittest.main()
