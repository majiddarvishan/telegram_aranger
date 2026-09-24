import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ui.auth as auth


class SessionState(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name, value):
        self[name] = value


class RememberMeRestoreTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            db_file="test.db",
            remember_me_days=7,
        )

    def test_restore_refreshes_browser_cookies_instead_of_stale_manager_snapshot(self):
        token = "remember-token"
        user = {"id": 1, "username": "alice", "display_name": "Alice"}

        manager = Mock()
        manager.get.return_value = None
        manager.get_all.return_value = {auth.COOKIE_NAME: token}

        fake_st = SimpleNamespace(
            session_state=SessionState(
                web_user=None,
                remember_token=None,
                _remember_cookie_hydrated=False,
            ),
            stop=Mock(),
        )

        with (
            patch.object(auth, "st", fake_st),
            patch.object(auth, "get_cookie_manager", return_value=manager),
            patch.object(auth, "get_user_by_session", return_value=user) as get_user,
        ):
            restored = auth.restore_remembered_user(self.settings)

        self.assertTrue(restored)
        manager.get_all.assert_called_once_with(key="restore_remember_cookies")
        manager.get.assert_not_called()
        get_user.assert_called_once_with("test.db", token)
        self.assertEqual(fake_st.session_state.web_user, user)
        self.assertEqual(fake_st.session_state.remember_token, token)

    def test_first_empty_cookie_snapshot_waits_for_browser_hydration(self):
        manager = Mock()
        manager.get_all.return_value = {}

        fake_st = SimpleNamespace(
            session_state=SessionState(
                web_user=None,
                remember_token=None,
                _remember_cookie_hydrated=False,
            ),
            stop=Mock(side_effect=RuntimeError("streamlit stop")),
        )

        with (
            patch.object(auth, "st", fake_st),
            patch.object(auth, "get_cookie_manager", return_value=manager),
        ):
            with self.assertRaisesRegex(RuntimeError, "streamlit stop"):
                auth.restore_remembered_user(self.settings)

        self.assertTrue(fake_st.session_state._remember_cookie_hydrated)
        manager.get_all.assert_called_once_with(key="restore_remember_cookies")

    def test_empty_cookie_after_hydration_shows_login_normally(self):
        manager = Mock()
        manager.get_all.return_value = {}

        fake_st = SimpleNamespace(
            session_state=SessionState(
                web_user=None,
                remember_token=None,
                _remember_cookie_hydrated=True,
            ),
            stop=Mock(),
        )

        with (
            patch.object(auth, "st", fake_st),
            patch.object(auth, "get_cookie_manager", return_value=manager),
        ):
            restored = auth.restore_remembered_user(self.settings)

        self.assertFalse(restored)
        fake_st.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
