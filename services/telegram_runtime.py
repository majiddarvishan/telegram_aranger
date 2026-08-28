import asyncio
import threading
from concurrent.futures import Future

class TelegramRuntime:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run, daemon=True, name="TelegramRuntime")
        self.client = None
        self.thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run(self, coro):
        future: Future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def stop(self):
        if self.loop.is_running(): self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


def get_runtime() -> TelegramRuntime:
    import streamlit as st
    runtime = st.session_state.get("telegram_runtime")
    if runtime is None:
        runtime = TelegramRuntime()
        st.session_state.telegram_runtime = runtime
    return runtime
