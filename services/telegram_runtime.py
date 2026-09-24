import asyncio
import threading
from concurrent.futures import Future


class TelegramRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="TelegramRuntime",
        )
        self.client = None
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
        return self.submit(coro).result()

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
