import unittest
from datetime import datetime

from ui.main import (
    MESSAGE_ACTIONS_KEY,
    MESSAGE_DATE_NAV_KEY,
    MESSAGE_FILTERS_KEY,
    MESSAGE_HEADER_CSS,
    MESSAGE_HEADER_KEY,
    MESSAGE_SCROLL_KEY,
    _chat_label,
    _default_chat_id,
    _delete_state_key,
    _display_message_text,
    _message_card_key,
    _latest_message_date_range,
    _message_footer_key,
    _message_matches_filters,
    _tag_editor_state_key,
    _remove_message_from_state,
)
from ui.sidebar import WEB_ACCOUNT_CARD_KEY, _apply_account_selection


class StickyHeaderTests(unittest.TestCase):
    def test_message_header_stays_in_flow_above_scrollable_messages(self):
        self.assertEqual(MESSAGE_HEADER_KEY, "message-header")
        self.assertEqual(MESSAGE_SCROLL_KEY, "message-scroll-area")
        self.assertIn(".st-key-message-header", MESSAGE_HEADER_CSS)
        self.assertIn("position: relative", MESSAGE_HEADER_CSS)
        self.assertNotIn("position: fixed", MESSAGE_HEADER_CSS)
        self.assertNotIn(".message-header-backdrop", MESSAGE_HEADER_CSS)
        self.assertNotIn(".message-header-fixed-spacer", MESSAGE_HEADER_CSS)
        self.assertIn(".st-key-message-scroll-area", MESSAGE_HEADER_CSS)


    def test_compact_workspace_regions_are_keyed_for_responsive_css(self):
        self.assertEqual(MESSAGE_FILTERS_KEY, "message-filters")
        self.assertEqual(MESSAGE_DATE_NAV_KEY, "message-date-nav")
        self.assertEqual(MESSAGE_ACTIONS_KEY, "message-actions")

    def test_bottom_navigation_container_is_removed(self):
        self.assertNotIn(".st-key-message-navigation", MESSAGE_HEADER_CSS)

    def test_message_actions_use_responsive_container(self):
        import inspect
        from ui.main import _render_message_actions

        source = inspect.getsource(_render_message_actions)

        self.assertIn("MESSAGE_ACTIONS_KEY", source)
        self.assertIn("st.container", source)

    def test_load_more_control_is_not_rendered_inside_scroll_panel(self):
        import inspect
        from ui.main import _render_message_actions, _render_message_scroll_area

        actions_source = inspect.getsource(_render_message_actions)
        scroll_source = inspect.getsource(_render_message_scroll_area)

        self.assertIn("Load more", actions_source)
        self.assertIn("Refresh", actions_source)
        self.assertIn("action_summary_html", actions_source)
        self.assertNotIn("Load more", scroll_source)

class ChatLabelPolishTests(unittest.TestCase):
    def test_chat_labels_use_textual_type_not_decorative_emoji(self):
        label = _chat_label(
            {
                "title": "Operations",
                "type": "supergroup",
                "username": "ops",
            }
        )

        self.assertEqual(
            label,
            "Operations · @ops · Group",
        )
        self.assertNotIn("👤", label)
        self.assertNotIn("👥", label)
        self.assertNotIn("📢", label)
        self.assertNotIn("💬", label)


    def test_saved_messages_is_default_chat_for_current_telegram_user(self):
        dialogs = [
            {
                "id": -100,
                "title": "Operations",
                "type": "group",
                "username": "",
            },
            {
                "id": 1001,
                "title": "Majid",
                "type": "private",
                "username": "majiddarvishan",
            },
        ]

        self.assertEqual(
            _default_chat_id(dialogs, {"id": 1001}),
            1001,
        )
        self.assertEqual(
            _chat_label(dialogs[1], 1001),
            "Saved Messages · Private",
        )

    def test_default_chat_falls_back_to_first_dialog(self):
        dialogs = [
            {
                "id": -100,
                "title": "Operations",
                "type": "group",
                "username": "",
            }
        ]

        self.assertEqual(
            _default_chat_id(dialogs, {"id": 1001}),
            -100,
        )


class AutoLatestRangeTests(unittest.TestCase):
    def test_latest_message_date_range_tracks_latest_batch_span(self):
        messages = [
            {"date": datetime(2026, 9, 25, 14, 0)},
            {"date": datetime(2026, 9, 23, 10, 0)},
            {"date": datetime(2026, 9, 24, 8, 0)},
        ]

        self.assertEqual(
            _latest_message_date_range(messages),
            (
                datetime(2026, 9, 23).date(),
                datetime(2026, 9, 25).date(),
            ),
        )

    def test_latest_message_date_range_handles_empty_batch(self):
        self.assertIsNone(_latest_message_date_range([]))

    def test_empty_new_chat_has_one_shot_latest_fallback(self):
        import inspect
        from ui.main import _maybe_align_empty_chat_to_latest

        source = inspect.getsource(_maybe_align_empty_chat_to_latest)

        self.assertIn("message_auto_latest_chat_id", source)
        self.assertIn("latest_history", source)
        self.assertIn("_set_pending_date_range", source)
        self.assertIn("message_query_signature", source)
        self.assertIn("st.rerun()", source)


class UiMessageSmokeTests(unittest.TestCase):
    def setUp(self):
        self.message = {
            "id": 42,
            "date": datetime(2026, 9, 24, 12, 0, 0),
            "text": "Hello Telegram",
        }

    def test_message_filter_accepts_matching_date_search_and_tag(self):
        self.assertTrue(
            _message_matches_filters(
                self.message,
                ["work", "important"],
                datetime(2026, 9, 24).date(),
                datetime(2026, 9, 24).date(),
                "telegram",
                "work",
            )
        )

    def test_message_filter_rejects_search_tag_and_date_mismatches(self):
        date_value = datetime(2026, 9, 24).date()

        self.assertFalse(
            _message_matches_filters(
                self.message,
                ["work"],
                date_value,
                date_value,
                "missing",
                "All",
            )
        )
        self.assertFalse(
            _message_matches_filters(
                self.message,
                ["work"],
                date_value,
                date_value,
                "",
                "family",
            )
        )
        self.assertFalse(
            _message_matches_filters(
                self.message,
                ["work"],
                datetime(2026, 9, 23).date(),
                datetime(2026, 9, 23).date(),
                "",
                "All",
            )
        )

    def test_message_card_uses_compact_on_demand_footer(self):
        import inspect
        from ui.main import _render_message_card, _render_message_footer

        card_source = inspect.getsource(_render_message_card)
        footer_source = inspect.getsource(_render_message_footer)

        self.assertIn("tag_chips_html", footer_source)
        self.assertIn("Edit tags", footer_source)
        self.assertIn("Delete", footer_source)
        self.assertIn("st.text_input", footer_source)
        self.assertIn("message_body_html", card_source)
        self.assertNotIn("Tags (comma-separated)", card_source)

    def test_footer_and_media_actions_have_responsive_keys(self):
        import inspect
        from ui.main import _render_media, _render_message_footer

        media_source = inspect.getsource(_render_media)
        footer_source = inspect.getsource(_render_message_footer)

        self.assertIn("media-actions-", media_source)
        self.assertIn("media-download-actions-", media_source)
        self.assertIn("message-footer-actions-", footer_source)
        self.assertIn("message-footer-edit-actions-", footer_source)
        self.assertIn("message-footer-delete-actions-", footer_source)

    def test_voice_and_audio_use_inline_audio_player(self):
        import inspect
        from ui.main import _render_media

        source = inspect.getsource(_render_media)

        self.assertIn('media_type in ("voice", "audio")', source)
        self.assertIn("Play voice", source)
        self.assertIn("Play audio", source)
        self.assertIn("st.audio", source)
        self.assertNotIn(
            "Voice media is detected. Preview is not implemented yet.",
            source,
        )

    def test_media_actions_use_compact_hierarchy(self):
        import inspect
        from ui.main import _render_media

        source = inspect.getsource(_render_media)

        self.assertIn("Play video", source)
        self.assertIn("Prepare download", source)
        self.assertIn("Download", source)
        self.assertIn("Redownload", source)
        self.assertNotIn("Load Video", source)
        self.assertNotIn("Prepare Video Download", source)

    def test_message_card_footer_and_editor_keys_are_stable(self):
        self.assertEqual(_message_card_key(7, 42), "message-card-7-42")
        self.assertEqual(
            _message_footer_key(7, 42),
            "message-footer-7-42",
        )
        self.assertEqual(
            _tag_editor_state_key(7, -100, 42),
            "7:-100:42",
        )

    def test_media_only_placeholder_is_hidden_from_card_body(self):
        message = {
            "text": "[Video]",
            "media": {"type": "video"},
        }
        captioned = {
            "text": "Actual caption",
            "media": {"type": "video"},
        }

        self.assertEqual(_display_message_text(message), "")
        self.assertEqual(
            _display_message_text(captioned),
            "Actual caption",
        )

    def test_delete_microcopy_is_explicit_and_irreversible(self):
        import inspect
        from ui.main import _render_message_footer

        source = inspect.getsource(_render_message_footer)

        self.assertIn("This cannot be undone", source)
        self.assertIn("Delete message", source)

    def test_delete_confirmation_key_is_scoped_to_account_chat_and_message(self):
        self.assertEqual(_delete_state_key(7, -100, 42), "7:-100:42")
        self.assertNotEqual(
            _delete_state_key(7, -100, 42),
            _delete_state_key(8, -100, 42),
        )
        self.assertNotEqual(
            _delete_state_key(7, -100, 42),
            _delete_state_key(7, -200, 42),
        )

    def test_delete_state_removes_only_target_message_and_its_media(self):
        messages = [
            {"id": 41},
            {"id": 42},
            {"id": 43},
        ]
        media_files = {
            "7:-100:42:preview": {"path": "preview.mp4"},
            "7:-100:42:download": {"path": "download.mp4"},
            "7:-100:43:preview": {"path": "other.mp4"},
            "8:-100:42:preview": {"path": "other-account.mp4"},
        }

        remaining, cleaned = _remove_message_from_state(
            messages,
            media_files,
            account_id=7,
            chat_id=-100,
            message_id=42,
        )

        self.assertEqual([item["id"] for item in remaining], [41, 43])
        self.assertNotIn("7:-100:42:preview", cleaned)
        self.assertNotIn("7:-100:42:download", cleaned)
        self.assertIn("7:-100:43:preview", cleaned)
        self.assertIn("8:-100:42:preview", cleaned)


class AuthAndStateSmokeTests(unittest.TestCase):
    def test_auth_screen_uses_centered_branded_card(self):
        import inspect
        from ui.auth import render_web_auth

        source = inspect.getsource(render_web_auth)

        self.assertIn('key="auth-card"', source)
        self.assertIn("auth_brand_html", source)
        self.assertNotIn("st.title", source)

    def test_message_workspace_has_dedicated_empty_state(self):
        import inspect
        from ui.main import _render_message_scroll_area

        source = inspect.getsource(_render_message_scroll_area)

        self.assertIn("No messages found", source)
        self.assertIn("Messages unavailable", source)
        self.assertIn("message_fetch_error", source)
        self.assertIn("empty_state_html", source)


class SidebarHierarchySmokeTests(unittest.TestCase):
    def test_sidebar_groups_network_and_destructive_actions(self):
        import inspect
        from ui.sidebar import (
            _render_connected_account_actions,
            _render_network_settings,
            _render_web_account,
        )

        network_source = inspect.getsource(_render_network_settings)
        actions_source = inspect.getsource(
            _render_connected_account_actions
        )
        web_source = inspect.getsource(_render_web_account)

        self.assertIn("Network & proxy", network_source)
        self.assertIn("Account actions", actions_source)
        self.assertIn("Log out & remove", actions_source)
        self.assertIn("Sign out", web_source)
        self.assertIn("st.sidebar.container", web_source)
        self.assertIn("WEB_ACCOUNT_CARD_KEY", web_source)
        self.assertEqual(WEB_ACCOUNT_CARD_KEY, "web-account-card")


class WorkspaceSidebarSmokeTests(unittest.TestCase):
    def test_youtube_workspace_hides_telegram_network_controls(self):
        import inspect
        from ui.sidebar import render_sidebar

        source = inspect.getsource(render_sidebar)
        youtube_branch = source.index(
            'if workspace == "YouTube Download":'
        )
        proxy_render = source.index("_render_network_settings()")

        self.assertLess(youtube_branch, proxy_render)
        self.assertIn(
            "Telegram SOCKS5 proxy settings are not reused.",
            source,
        )
        self.assertIn("return workspace", source)

    def test_sidebar_owns_workspace_selector(self):
        import inspect
        from ui.sidebar import render_sidebar

        source = inspect.getsource(render_sidebar)
        self.assertIn(
            '("Telegram Messages", "YouTube Download")',
            source,
        )
        self.assertIn('key="workspace"', source)


class UiAccountSelectionSmokeTests(unittest.TestCase):
    def test_account_switch_resets_chat_messages_runtime_view_state(self):
        state = {
            "selected_telegram_account_id": 1,
            "selected_chat_id": -100,
            "messages": [{"id": 1}],
            "message_fetch_error": "old error",
            "message_auto_latest_chat_id": -100,
            "dialogs": [{"id": -100}],
            "telegram_user": {"id": 123},
            "media_files": {"1:-100:1:preview": {"path": "cached"}},
        }

        changed = _apply_account_selection(state, 2)

        self.assertTrue(changed)
        self.assertEqual(state["selected_telegram_account_id"], 2)
        self.assertIsNone(state["selected_chat_id"])
        self.assertEqual(state["messages"], [])
        self.assertIsNone(state["message_fetch_error"])
        self.assertIsNone(state["message_auto_latest_chat_id"])
        self.assertEqual(state["dialogs"], [])
        self.assertIsNone(state["telegram_user"])
        self.assertEqual(state["media_files"], {})

    def test_selecting_same_account_does_not_reset_state(self):
        state = {
            "selected_telegram_account_id": 1,
            "selected_chat_id": -100,
            "messages": [{"id": 1}],
            "dialogs": [{"id": -100}],
            "telegram_user": {"id": 123},
            "media_files": {"1:-100:1:preview": {"path": "cached"}},
        }

        changed = _apply_account_selection(state, 1)

        self.assertFalse(changed)
        self.assertEqual(state["selected_chat_id"], -100)
        self.assertEqual(state["messages"], [{"id": 1}])


if __name__ == "__main__":
    unittest.main()



class SidebarWebAccountPolishTests(unittest.TestCase):
    def test_web_account_sign_out_is_compact(self):
        import inspect
        from ui.sidebar import _render_web_account

        source = inspect.getsource(_render_web_account)

        self.assertIn('key="sidebar-web-logout"', source)
        self.assertIn("use_container_width=False", source)
