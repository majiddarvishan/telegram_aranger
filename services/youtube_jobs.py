from __future__ import annotations

from dataclasses import dataclass, field
import threading
from typing import Any, Callable, Mapping

from services.youtube_download import (
    DownloadProgress,
    DownloadRequest,
    download_video,
)
from services.youtube_service import YouTubeServiceError


@dataclass
class YouTubeDownloadJob:
    cancel_event: threading.Event = field(default_factory=threading.Event)
    lock: threading.Lock = field(default_factory=threading.Lock)
    status: str = "running"
    progress: DownloadProgress | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
    thread: threading.Thread | None = None

    def request_cancel(self) -> None:
        self.cancel_event.set()
        with self.lock:
            if self.status == "running":
                self.status = "cancelling"

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def update_progress(self, event: DownloadProgress) -> None:
        with self.lock:
            self.progress = event

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "status": self.status,
                "progress": self.progress,
                "result": self.result,
                "error": dict(self.error) if self.error else None,
            }


def start_youtube_download_job(
    request: Any,
    metadata: Mapping[str, Any],
    *,
    allowed_roots: tuple[str, ...] = (),
    runner: Callable[..., Any] = download_video,
) -> YouTubeDownloadJob:
    job = YouTubeDownloadJob()

    def worker() -> None:
        try:
            result = runner(
                request,
                metadata,
                allowed_roots=allowed_roots,
                progress_callback=job.update_progress,
                cancel_check=job.is_cancelled,
            )
        except YouTubeServiceError as exc:
            with job.lock:
                if exc.code == "download_cancelled" or job.cancel_event.is_set():
                    job.status = "cancelled"
                    job.error = None
                else:
                    job.status = "failed"
                    job.error = exc.as_dict()
            return
        except Exception:
            with job.lock:
                if job.cancel_event.is_set():
                    job.status = "cancelled"
                    job.error = None
                else:
                    job.status = "failed"
                    job.error = {
                        "code": "download_failed",
                        "message": "YouTube download failed unexpectedly.",
                        "access_restricted": False,
                    }
            return

        with job.lock:
            if job.cancel_event.is_set():
                job.status = "cancelled"
                job.result = None
            else:
                job.status = "completed"
                job.result = result

    thread = threading.Thread(
        target=worker,
        name="yara-youtube-download",
        daemon=True,
    )
    job.thread = thread
    thread.start()
    return job
