import unittest
from pathlib import Path


def _workflow_text() -> str:
    workflow_dir = Path(".github/workflows")
    files = sorted(
        [
            *workflow_dir.glob("*.yml"),
            *workflow_dir.glob("*.yaml"),
        ]
    )
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in files
        if path.is_file()
    )


class YouTubeCiPolicyTests(unittest.TestCase):
    def test_ci_does_not_call_live_youtube(self):
        lowered = _workflow_text().lower()

        self.assertNotIn("youtube.com/watch", lowered)
        self.assertNotIn("youtu.be/", lowered)
        self.assertNotIn("youtube_manual_validate.py --url", lowered)

    def test_ci_manual_runner_invocation_is_preflight_only(self):
        workflow = _workflow_text()
        lowered = workflow.lower()

        self.assertIn(
            "scripts/youtube_manual_validate.py",
            workflow,
        )
        self.assertIn("--mode preflight", lowered)
        self.assertNotIn("--mode inspect", lowered)
        self.assertNotIn("--mode video_audio", lowered)
        self.assertNotIn("--mode audio_only", lowered)

    def test_ci_still_runs_manual_runner_offline_unit_tests(self):
        workflow = _workflow_text()
        self.assertIn(
            'python -m unittest discover -s tests '
            '-p "test_youtube_manual_validate.py" -v',
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
