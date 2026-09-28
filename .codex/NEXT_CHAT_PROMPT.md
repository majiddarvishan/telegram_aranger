# NEXT CHAT PROMPT — YARA

Copy/paste the block below into a new ChatGPT conversation.

---

We are continuing work on the private GitHub repository:

`majiddarvishan/yara`

Project: **YARA — Your Archive & Retrieval Assistant**

The old repository name `majiddarvishan/telegram_aranger` has been renamed to `majiddarvishan/yara`.

The YouTube feature branch has already been merged into `main`.
At the previous handoff:
- `main` HEAD was `0934e67401e078bc57f0f4acddffd1f72bf6a768`;
- `feature/youtube-download` was already merged and behind main;
- do not continue new work on that old feature branch.

Before doing anything:
1. Re-check the current repository and `main` HEAD.
2. Read `.codex/START_HERE.md`.
3. Read `.codex/PROJECT_CONTEXT.md`.
4. Read `.codex/DECISIONS.md`.
5. Read `.codex/TASKS.md`.
6. Read the latest section of `.codex/SESSION.md`.
7. Read `.codex/YOUTUBE_PLAN.md` and `.codex/YOUTUBE_VALIDATION.md` if the next work concerns YouTube.

For any new code work, create a **fresh branch from current main** unless I explicitly tell you to work directly on main.
Do not merge to main unless I explicitly ask.

Current product state:
- product name is **YARA**;
- repository is **majiddarvishan/yara**;
- Telegram and YouTube share one SOCKS5 control in the Sidebar;
- default proxy values should be `127.0.0.1:1080` when enabled and blank/invalid;
- YouTube supports Inspect, authenticated cookies, SOCKS5, Deno/JS challenge solving, per-format downloads, audio, subtitles, cancellation, native Save-directory browsing, and remembered Save directory;
- Browser Session auth exists, but Chrome on current Windows may fail because of Chromium App-Bound/DPAPI cookie encryption; youtube.com-only `cookies.txt` remains a supported fallback;
- no DRM/paywall/private/member access-control bypass.

Recent real-UI issues were fixed in code and CI but still need manual confirmation:
- proxy toggle visibly defaults to `127.0.0.1` / `1080`;
- Browse folder no longer throws `StreamlitWidgetAlreadyInstantiatedError`;
- old Inspect error does not remain on screen after URL change/new Inspect;
- all video/audio formats are present (no first-40 truncation);
- formats header stays visible above the scrollable rows;
- every format row has one Download menu;
- Download menu offers Video + Audio, Audio and Subtitle as appropriate;
- Subtitle action lets the user select language inside the menu;
- redundant global Output/Quality/subtitle controls and standalone subtitle table are gone;
- Cancel download works during a real transfer;
- deprecated `use_container_width` warnings are removed from the touched YouTube/sidebar flow.

Branding:
- YARA = **Your Archive & Retrieval Assistant**.
- The user selected a dark YARA logo: central circular YARA wordmark, Persian `یارا`, cyan/purple circuit/network background.
- Repository rename is complete.
- The selected binary logo was not present in the Git tree at the previous handoff and GitHub Social Preview still needed the approved image uploaded through a binary-capable/UI workflow. Do not substitute a different logo.

Start by reporting the current `main` HEAD, CI status, and whether the manual UX items above are still pending. Then continue from the user's next priority without re-planning completed work.

---
