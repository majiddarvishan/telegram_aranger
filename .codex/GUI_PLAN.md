# GUI Redesign Plan

Branch: `gui`
Baseline: `main@2bd6fbd18ac6ab03a38ee5ffc586c2d76c8ccc49`

This branch is dedicated to visual/UI work. Functional Telegram behavior must remain unchanged unless explicitly approved.

## Design direction

Target style:
- clean utility interface;
- calm visual hierarchy;
- content-first message reading;
- compact operational controls;
- subtle Telegram Harbor identity;
- minimal CSS fragility against Streamlit DOM changes.

## Main findings

- Native Streamlit widgets currently have too-similar visual weight.
- Sidebar is functionally correct but dense.
- Message cards look form-heavy because tags/delete controls are always prominent.
- Spacing, radii and semantic colors are not yet governed by a shared design system.
- Emoji are functioning as an inconsistent icon system.
- Auth, empty, loading and error states lack a unified product treatment.
- Responsive behavior is mostly defensive rather than deliberately designed.

## Planned phases

### GUI-P0 — Foundation
- [x] Centralize UI CSS/theme in `ui/theme.py`.
- [x] Add semantic design tokens.
- [x] Standardize baseline spacing/radius/border/shadow/typography.
- [x] Base colors on Streamlit theme variables for light/dark compatibility.
- [x] Add regression coverage for sensitive Streamlit selectors and safe badge/section markup.
- [x] Manually review the resulting UI in both Light and Dark themes.

### GUI-P1 — Sidebar
- [x] Compact brand block.
- [x] Web-account presentation.
- [x] Telegram account/status hierarchy.
- [x] Move destructive account actions into a lower-emphasis Account actions group.
- [x] Put proxy settings in a Network & proxy expander.
- [x] Normalize spacing/dividers/button priorities.
- [ ] Manually review the expanded sidebar on desktop and a narrow viewport.

### GUI-P2 — Toolbar
- [x] Redesign Chat/Search/Tag hierarchy with shorter labels.
- [x] Compact date navigation.
- [x] Integrate visible/loaded message counts into the action bar.
- [x] Normalize Refresh vs Load more hierarchy.
- [ ] Consider active-filter chips after manual review of the simplified toolbar.

### GUI-P3 — Message cards
- [x] Make message content the dominant visual element.
- [x] Add compact card header/meta.
- [x] Render tags as read-mode chips.
- [x] Make tag editing on-demand.
- [x] De-emphasize delete until requested.
- [x] Standardize media action hierarchy for preview/play/download/redownload.
- [x] Normalize baseline card spacing.
- [x] Desktop screenshot review completed for text/video cards.
- [x] Photo-card desktop review completed.

### GUI-P4 — Auth and state screens
- [x] Centered branded auth card.
- [x] Dedicated empty states for no account, no chats and no matching messages.
- [x] Apply shared radius/surface treatment to warning/error/success components.
- [x] Standardize loading microcopy while preserving byte-level media progress.

### GUI-P5 — Responsive/accessibility
- [x] Add a first responsive breakpoint at 900px for spacing/action alignment.
- [x] Keep Streamlit column stacking as the safe narrow-layout fallback.
- [x] Add keyboard focus-visible treatment and reduced-motion support.
- [x] Keep baseline control hit targets at 40px.
- [x] Light-theme contrast reviewed on desktop.
- [x] Dark-theme screenshot review identified forced-light custom surfaces; adaptive-surface fix implemented.
- [x] Re-verified Dark mode after the adaptive-surface fix; custom surfaces and text contrast are correct.
- [x] Desktop screenshot review completed for the light theme.
- [x] First narrow-viewport screenshot reviewed; it exposed truncated action/footer buttons with Sidebar open.
- [ ] Re-review narrow viewport after the compact-workspace wrapping fix.

### GUI-P6 — Polish
- [x] Subtle hover/transition behavior for buttons, cards, tags, links and expanders.
- [x] Consistent icon treatment: remove application-added chat emoji and reserve the anchor mark for Telegram Harbor branding.
- [x] Microcopy cleanup for loading, navigation, account actions and destructive confirmation.
- [x] Selected/active state polish for the active chat workspace and account/chat selectors.
- [x] Add compact <=700px spacing refinement without overriding Streamlit's native stacking behavior.
- [x] First narrow-viewport screenshot identified remaining truncation issues.
- [ ] Final narrow-viewport re-review after responsive region wrapping.

## Implementation order

Recommended sequence:
1. GUI-P0
2. GUI-P3
3. GUI-P1
4. GUI-P2
5. GUI-P4
6. GUI-P5
7. GUI-P6

Message cards are intentionally prioritized ahead of the sidebar because they dominate the user's working time.

## Guardrails

Do not change in GUI phases unless separately approved:
- Telegram runtime/service behavior;
- session encryption/authentication;
- dialog cache semantics;
- message history/pagination semantics;
- media cache rules;
- tag identity/data model;
- database schema;
- Remember Me behavior.

## Acceptance rule per phase

Before moving to the next phase:
- CI green;
- no behavior regression;
- desktop screenshot review;
- narrow-width screenshot review for layout-affecting changes;
- update this file and `.codex/SESSION.md`.

Full Persian design audit:
`docs/GUI_DESIGN_PLAN_FA.md`


## Correctness fixes discovered during GUI validation
- [x] Persist Pyrogram peer ID/type/access-hash metadata with the dialog cache and hydrate it into in-memory sessions after restart.
- [x] Upgrade SQLite schema to v4 and refresh legacy pre-peer-metadata dialog snapshots once.
- [x] Retain username/bounded-dialog lazy peer recovery as a fallback for stale records.
- [x] Distinguish message-fetch failure state from a legitimate empty result.
- [ ] Backport the persisted-peer correctness fix to main before the next release if gui is not merged wholesale.
