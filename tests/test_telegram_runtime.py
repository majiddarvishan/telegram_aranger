import asyncio
import unittest

from services.telegram_runtime import TelegramRuntime


class FakeTelegramClient:
    def __init__(self, fail=False):
        self.is_connected = True
        self.fail = fail
        self.disconnect_calls = 0

    async def disconnect(self):
        self.disconnect_calls += 1
        if self.fail:
            raise RuntimeError("disconnect failed")
        self.is_connected = False


class TelegramRuntimeShutdownTests(unittest.TestCase):
    def test_run_records_blocking_wait_metrics(self):
        runtime = TelegramRuntime()

        async def delayed_value():
            await asyncio.sleep(0.01)
            return 42

        try:
            self.assertEqual(runtime.run(delayed_value()), 42)
            metrics = runtime.metrics()
        finally:
            runtime.stop()

        self.assertEqual(metrics["run_calls"], 1)
        self.assertGreater(metrics["last_wait_seconds"], 0)
        self.assertGreaterEqual(
            metrics["max_wait_seconds"],
            metrics["last_wait_seconds"],
        )

    def test_stop_disconnects_active_client_and_closes_loop(self):
        runtime = TelegramRuntime()
        client = FakeTelegramClient()
        runtime.client = client

        runtime.stop()

        self.assertEqual(client.disconnect_calls, 1)
        self.assertIsNone(runtime.client)
        self.assertFalse(runtime.thread.is_alive())
        self.assertTrue(runtime.loop.is_closed())

    def test_stop_still_closes_loop_when_disconnect_fails(self):
        runtime = TelegramRuntime()
        client = FakeTelegramClient(fail=True)
        runtime.client = client

        runtime.stop()

        self.assertEqual(client.disconnect_calls, 1)
        self.assertIsNone(runtime.client)
        self.assertFalse(runtime.thread.is_alive())
        self.assertTrue(runtime.loop.is_closed())

    def test_stop_without_client_is_idempotent(self):
        runtime = TelegramRuntime()

        runtime.stop()
        runtime.stop()

        self.assertFalse(runtime.thread.is_alive())
        self.assertTrue(runtime.loop.is_closed())


if __name__ == "__main__":
    unittest.main()
