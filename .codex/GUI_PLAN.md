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
- [ ] Manually review the resulting UI in both Light and Dark themes before closing GUI-P0.

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
- [ ] Manually review a photo card before closing GUI-P3.

### GUI-P4 — Auth and state screens
- [x] Centered branded auth card.
- [x] Dedicated empty states for no account, no chats and no matching messages.
- [x] Apply shared radius/surface treatment to warning/error/success components.
- [ ] Review loading feedback after the visual pass; existing media progress remains unchanged.

### GUI-P5 — Responsive/accessibility
- [x] Add a first responsive breakpoint at 900px for spacing/action alignment.
- [x] Keep Streamlit column stacking as the safe narrow-layout fallback.
- [x] Add keyboard focus-visible treatment and reduced-motion support.
- [x] Keep baseline control hit targets at 40px.
- [ ] Manual Light/Dark contrast review.
- [x] Desktop screenshot review completed for the light theme.
- [ ] Manual screenshot review at a narrow viewport.

### GUI-P6 — Polish
- [ ] Subtle hover/transition behavior.
- [ ] Consistent icon treatment.
- [ ] Microcopy cleanup.
- [ ] Selected/active state polish.

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
