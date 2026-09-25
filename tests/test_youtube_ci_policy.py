import unittest
from pathlib import Path


class YouTubeCiPolicyTests(unittest.TestCase):
    def test_ci_does_not_call_live_youtube(self):
        workflow = Path(".github/workflows/tests.yml").read_text(
            encoding="utf-8"
        )
        lowered = workflow.lower()

        self.assertNotIn("youtube.com/watch", lowered)
        self.assertNotIn("youtu.be/", lowered)
        self.assertNotIn(
            "python scripts/youtube_manual_validate.py",
            lowered,
        )

    def test_ci_only_runs_manual_runner_through_offline_unit_tests(self):
        workflow = Path(".github/workflows/tests.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'python -m unittest discover -s tests '
            '-p "test_youtube_manual_validate.py" -v',
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
