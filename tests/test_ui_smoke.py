import unittest
from datetime import datetime

from ui.main import (
    MESSAGE_HEADER_CSS,
    MESSAGE_HEADER_KEY,
    MESSAGE_SCROLL_KEY,
    _delete_state_key,
    _message_card_key,
    _message_matches_filters,
    _tag_editor_state_key,
    _remove_message_from_state,
)
from ui.sidebar import _apply_account_selection


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


    def test_bottom_navigation_container_is_removed(self):
        self.assertNotIn(".st-key-message-navigation", MESSAGE_HEADER_CSS)

    def test_load_more_control_is_not_rendered_inside_scroll_panel(self):
        import inspect
        from ui.main import _render_message_actions, _render_message_scroll_area

        actions_source = inspect.getsource(_render_message_actions)
        scroll_source = inspect.getsource(_render_message_scroll_area)

        self.assertIn("Load more", actions_source)
        self.assertIn("Refresh", actions_source)
        self.assertIn("action_summary_html", actions_source)
        self.assertNotIn("Load more", scroll_source)

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

    def test_message_card_uses_on_demand_tag_editor(self):
        import inspect
        from ui.main import _render_message_card, _render_tag_controls

        card_source = inspect.getsource(_render_message_card)
        tag_source = inspect.getsource(_render_tag_controls)

        self.assertIn("tag_chips_html", tag_source)
        self.assertIn("Edit tags", tag_source)
        self.assertIn("st.text_input", tag_source)
        self.assertNotIn("Tags (comma-separated)", card_source)

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

    def test_message_card_and_editor_keys_are_stable(self):
        self.assertEqual(_message_card_key(7, 42), "message-card-7-42")
        self.assertEqual(
            _tag_editor_state_key(7, -100, 42),
            "7:-100:42",
        )

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
        self.assertIn("Logout & remove account", actions_source)
        self.assertIn("Sign out", web_source)


class UiAccountSelectionSmokeTests(unittest.TestCase):
    def test_account_switch_resets_chat_messages_runtime_view_state(self):
        state = {
            "selected_telegram_account_id": 1,
            "selected_chat_id": -100,
            "messages": [{"id": 1}],
            "dialogs": [{"id": -100}],
            "telegram_user": {"id": 123},
            "media_files": {"1:-100:1:preview": {"path": "cached"}},
        }

        changed = _apply_account_selection(state, 2)

        self.assertTrue(changed)
        self.assertEqual(state["selected_telegram_account_id"], 2)
        self.assertIsNone(state["selected_chat_id"])
        self.assertEqual(state["messages"], [])
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
