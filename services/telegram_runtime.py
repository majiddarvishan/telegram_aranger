import asyncio
import logging
import os
import threading
import time
from concurrent.futures import Future

from utils.logging import log_event


logger = logging.getLogger("telegram_aranger.telegram_runtime")


def _slow_call_threshold() -> float:
    try:
        return max(0.0, float(os.getenv("TELEGRAM_SLOW_CALL_SECONDS", "1.0")))
    except ValueError:
        return 1.0


class TelegramRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="TelegramRuntime",
        )
        self.client = None
        self.run_calls = 0
        self.last_wait_seconds = 0.0
        self.max_wait_seconds = 0.0
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        finally:
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            finally:
                self.loop.close()

    def submit(self, coro) -> Future:
        if self.loop.is_closed():
            raise RuntimeError("Telegram runtime is already stopped.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def run(self, coro):
        started = time.monotonic()
        try:
            return self.submit(coro).result()
        finally:
            elapsed = time.monotonic() - started
            self.run_calls += 1
            self.last_wait_seconds = elapsed
            self.max_wait_seconds = max(self.max_wait_seconds, elapsed)
            if elapsed >= _slow_call_threshold():
                log_event(
                    logger,
                    "telegram_runtime_slow_wait",
                    level=logging.WARNING,
                    wait_seconds=round(elapsed, 3),
                    run_calls=self.run_calls,
                )

    def metrics(self) -> dict:
        return {
            "run_calls": self.run_calls,
            "last_wait_seconds": self.last_wait_seconds,
            "max_wait_seconds": self.max_wait_seconds,
        }

    async def _disconnect_active_client(self):
        client = self.client
        if client is None:
            return

        try:
            if getattr(client, "is_connected", False):
                await client.disconnect()
        finally:
            self.client = None

    def stop(self):
        if self.loop.is_closed():
            self.client = None
            return

        if self.loop.is_running() and self.client is not None:
            try:
                self.submit(self._disconnect_active_client()).result(timeout=5)
            except Exception:
                # Shutdown must still be able to stop the event loop even if
                # Telegram disconnect itself fails.
                self.client = None

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        if (
            self.thread.is_alive()
            and threading.current_thread() is not self.thread
        ):
            self.thread.join(timeout=5)


def get_runtime() -> TelegramRuntime:
    import streamlit as st

    runtime = st.session_state.get("telegram_runtime")
    if runtime is None:
        runtime = TelegramRuntime()
        st.session_state.telegram_runtime = runtime
    return runtime
