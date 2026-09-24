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
- [ ] Compact brand block.
- [ ] Web-account presentation.
- [ ] Telegram account/status hierarchy.
- [ ] Move destructive account actions into a lower-emphasis group.
- [ ] Put proxy settings in an expander.
- [ ] Normalize spacing/dividers/button priorities.

### GUI-P2 — Toolbar
- [ ] Redesign Chat/Search/Tag hierarchy.
- [ ] Compact date navigation.
- [ ] Integrate message counts into action bar.
- [ ] Normalize primary/secondary action styling.
- [ ] Consider active-filter chips after baseline styling.

### GUI-P3 — Message cards
- [ ] Make message content the dominant visual element.
- [ ] Add compact card header/meta.
- [ ] Render tags as read-mode chips.
- [ ] Make tag editing on-demand.
- [ ] De-emphasize delete until requested.
- [ ] Standardize media action hierarchy.
- [ ] Normalize card spacing.

### GUI-P4 — Auth and state screens
- [ ] Centered branded auth card.
- [ ] Dedicated empty states.
- [ ] Unified warning/error/success treatment.
- [ ] Consistent loading feedback.

### GUI-P5 — Responsive/accessibility
- [ ] Desktop/laptop/tablet breakpoints.
- [ ] Toolbar wrapping rules.
- [ ] Stacked message-card controls on narrow screens.
- [ ] Contrast/focus/hit-target review.
- [ ] Manual screenshot review at multiple widths.

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
