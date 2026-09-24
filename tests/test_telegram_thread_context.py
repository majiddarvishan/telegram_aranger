import inspect
import unittest

import services.telegram_service as telegram_service


class TelegramThreadContextTests(unittest.TestCase):
    def test_async_telegram_coroutines_do_not_read_streamlit_runtime(self):
        async_functions = (
            telegram_service._send_code,
            telegram_service._verify_code,
            telegram_service._verify_2fa,
            telegram_service._export,
            telegram_service._restore,
            telegram_service._disconnect,
            telegram_service._dialogs,
            telegram_service._history,
            telegram_service._download_media,
            telegram_service._delete,
        )

        for function in async_functions:
            with self.subTest(function=function.__name__):
                source = inspect.getsource(function)
                self.assertNotIn("get_runtime()", source)
                self.assertNotIn("streamlit", source)
                self.assertNotIn("st.session_state", source)


if __name__ == "__main__":
    unittest.main()
