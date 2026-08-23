import asyncio
import threading
from concurrent.futures import Future
import streamlit as st
# 5. Telegram Runtime
# =========================================================

class TelegramRuntime:
    """
    Owns one asyncio event loop and one Pyrogram Client.

    The event loop lives in a dedicated background thread.
    This prevents a Pyrogram Client from being moved between
    different asyncio event loops during Streamlit reruns.
    """

    def __init__(self):
        self.loop = asyncio.new_event_loop()

        self.thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
        )

        self.thread.start()

        self.client = None

    def _run_loop(self):
        """Run the background asyncio event loop."""

        asyncio.set_event_loop(
            self.loop
        )

        self.loop.run_forever()

    def run(
        self,
        coro,
    ):
        """Execute a coroutine on the Telegram event loop."""

        future: Future = (
            asyncio.run_coroutine_threadsafe(
                coro,
                self.loop,
            )
        )

        return future.result()

    def stop(self):
        """Stop the runtime."""

        if self.loop.is_running():

            self.loop.call_soon_threadsafe(
                self.loop.stop
            )

        self.thread.join(
            timeout=2
        )


def get_runtime() -> TelegramRuntime:
    """Get the Telegram runtime for the current Web session."""

    runtime = st.session_state.get(
        "telegram_runtime"
    )

    if runtime is None:

        runtime = TelegramRuntime()

        st.session_state.telegram_runtime = (
            runtime
        )

    return runtime


