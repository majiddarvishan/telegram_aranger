from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from services.youtube_service import YouTubeServiceError


GENERAL_RIGHTS_NOTICE = (
    "Only download content you are allowed to save. "
    "YouTube/service terms and copyright rules may apply."
)

_BLOCKED_AVAILABILITY = {
    "private": (
        "private_content",
        "This video is private and is outside Telegram Harbor V1.",
    ),
    "premium_only": (
        "premium_only",
        "This video requires paid/premium access and is outside Telegram Harbor V1.",
    ),
    "subscriber_only": (
        "members_only",
        "This video requires channel membership and is outside Telegram Harbor V1.",
    ),
    "needs_auth": (
        "login_required",
        (
            "YouTube requires a signed-in session for this video. "
            "Enable Browser session or cookies.txt fallback and Inspect again."
        ),
    ),
    "unavailable": (
        "video_unavailable",
        "This video is unavailable.",
    ),
}


@dataclass(frozen=True)
class RestrictionWarning:
    code: str
    message: str
    signal: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class DownloadPolicy:
    notice: str
    warnings: tuple[RestrictionWarning, ...]
    requires_acknowledgement: bool
    acknowledged: bool
    blocked: bool
    block_code: str | None = None
    block_message: str | None = None

    @property
    def can_download(self) -> bool:
        return not self.blocked and (
            self.acknowledged or not self.requires_acknowledgement
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "notice": self.notice,
            "warnings": [warning.as_dict() for warning in self.warnings],
            "requires_acknowledgement": self.requires_acknowledgement,
            "acknowledged": self.acknowledged,
            "blocked": self.blocked,
            "block_code": self.block_code,
            "block_message": self.block_message,
            "can_download": self.can_download,
        }


def evaluate_download_policy(
    metadata: Mapping[str, Any] | None = None,
    *,
    error: YouTubeServiceError | None = None,
    acknowledged: bool = False,
) -> DownloadPolicy:
    """Classify product warnings without making a copyright/legal determination."""
    if error is not None:
        return DownloadPolicy(
            notice=GENERAL_RIGHTS_NOTICE,
            warnings=(),
            requires_acknowledgement=True,
            acknowledged=acknowledged,
            blocked=True,
            block_code=error.code,
            block_message=error.message,
        )

    info = metadata or {}
    availability = str(info.get("availability") or "").strip().lower()

    if bool(info.get("has_drm")):
        return _blocked(
            acknowledged,
            "drm_protected",
            "This video is DRM-protected and cannot be downloaded by Telegram Harbor.",
        )

    if availability in _BLOCKED_AVAILABILITY:
        code, message = _BLOCKED_AVAILABILITY[availability]
        return _blocked(acknowledged, code, message)

    if availability and availability not in {"public", "unlisted"}:
        return _blocked(
            acknowledged,
            "restricted_availability",
            "YouTube reports a restricted or unsupported availability state "
            "that is outside Telegram Harbor V1.",
        )

    warnings = _restriction_warnings(info, availability)
    return DownloadPolicy(
        notice=GENERAL_RIGHTS_NOTICE,
        warnings=tuple(warnings),
        requires_acknowledgement=True,
        acknowledged=acknowledged,
        blocked=False,
    )


def _blocked(
    acknowledged: bool,
    code: str,
    message: str,
) -> DownloadPolicy:
    return DownloadPolicy(
        notice=GENERAL_RIGHTS_NOTICE,
        warnings=(),
        requires_acknowledgement=True,
        acknowledged=acknowledged,
        blocked=True,
        block_code=code,
        block_message=message,
    )


def _restriction_warnings(
    info: Mapping[str, Any],
    availability: str,
) -> list[RestrictionWarning]:
    warnings: list[RestrictionWarning] = []
    seen: set[str] = set()

    def add(code: str, message: str, signal: str) -> None:
        if code in seen:
            return
        seen.add(code)
        warnings.append(
            RestrictionWarning(
                code=code,
                message=message,
                signal=signal,
            )
        )

    age_limit = _positive_int(info.get("age_limit"))
    if age_limit:
        add(
            "age_restricted",
            f"YouTube reports an age restriction ({age_limit}+).",
            "age_limit",
        )

    live_status = str(info.get("live_status") or "").strip().lower()
    if bool(info.get("is_live")) or live_status in {
        "is_live",
        "is_upcoming",
        "post_live",
    }:
        add(
            "live_content",
            "This video is live, upcoming, or recently live; available formats may change.",
            "live_status",
        )

    formats = info.get("formats")
    if isinstance(formats, list) and not any(
        isinstance(item, Mapping)
        and (item.get("has_video") or item.get("has_audio"))
        for item in formats
    ):
        add(
            "formats_unavailable",
            "No downloadable media format is currently reported.",
            "formats",
        )

    if availability and availability not in {"public", "unlisted"}:
        add(
            "availability_signal",
            f"YouTube reports availability state: {availability}.",
            "availability",
        )

    return warnings


def _positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return result if result > 0 else None
