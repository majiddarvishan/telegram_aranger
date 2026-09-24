# Changelog

All notable Telegram Harbor changes are recorded here.

## Unreleased

- Increase the dedicated message scroll area from 420px to 620px by default.
- Add `MESSAGE_SCROLL_HEIGHT` so deployments can tune the main message panel height without changing code.

## 1.0.1 - 2026-09-25

- Reworked the message page so the controls stay above a dedicated scrollable message area.
- Moved Previous/Next date navigation into the control header.
- Removed the fragile fixed/sticky overlay approach that caused clipping and message/header overlap.
- Added regression coverage for the dedicated message scroll architecture.
- Preserved all media, tagging, deletion, filtering, and pagination behavior.

## 1.0.0 - 2026-09-24

Initial stable Telegram Harbor release checkpoint.

Highlights:
- Telegram Harbor product branding.
- Local multi-user Web authentication with Remember Me.
- Multiple Telegram accounts per Web user.
- Telegram phone/code/2FA login and encrypted session persistence.
- Private chat, group, supergroup, channel, and Saved Messages browsing.
- Date-range history with Load More pagination.
- Search and chat-scoped local tags.
- Lazy photo preview.
- Inline video/video-note/animation playback.
- Browser video download with real transfer progress.
- Bounded media cache and interrupted-download recovery.
- Confirmed Telegram message deletion.
- SQLite schema migration/versioning and backup/restore helpers.
- Structured secret-safe JSON logging.
- Docker/Compose deployment and health checks.
- Automated GitHub Actions regression and Docker-health validation.
- Real Telegram/browser media validation completed successfully.

Release checkpoint commit:
`bd8c8b211aa8e3ee5ca09c864b3e4803eac6807b`
