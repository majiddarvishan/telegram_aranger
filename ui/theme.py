from html import escape

import streamlit as st


DESIGN_TOKENS = {
    "space_1": "4px",
    "space_2": "8px",
    "space_3": "12px",
    "space_4": "16px",
    "space_5": "24px",
    "space_6": "32px",
    "radius_control": "8px",
    "radius_panel": "12px",
    "radius_pill": "999px",
    "control_height": "40px",
    "top_safe_area": "48px",
    "motion_fast": "120ms",
    "motion_normal": "180ms",
}


MESSAGE_HEADER_CSS = """
.st-key-message-header {
    position: relative;
    z-index: 2;
    padding: var(--th-space-3) var(--th-space-4) var(--th-space-4);
    margin-top: var(--th-space-2);
    margin-bottom: var(--th-space-3);
    overflow: visible;
    background: var(--th-surface);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-panel);
    box-shadow: var(--th-shadow-sm);
}

.st-key-message-header::before {
    content: "";
    position: absolute;
    top: var(--th-space-3);
    bottom: var(--th-space-3);
    left: 0;
    width: 3px;
    border-radius: 0 var(--th-radius-pill) var(--th-radius-pill) 0;
    background: var(--th-accent);
    opacity: 0.72;
}

.st-key-message-header [data-testid="stHorizontalBlock"] {
    align-items: end;
    gap: var(--th-space-3);
}

.st-key-message-header label {
    margin-bottom: var(--th-space-1);
    font-weight: 600;
}

.st-key-message-header [data-testid="stDateInput"],
.st-key-message-header [data-testid="stDateInput"] > div {
    width: 100%;
}

.st-key-message-header button {
    min-height: var(--th-control-height);
}

.st-key-message-scroll-area {
    border: 1px solid var(--th-border) !important;
    border-radius: var(--th-radius-panel) !important;
    background: var(--th-surface);
    box-shadow: var(--th-shadow-sm);
}
"""


APP_CSS = f"""
<style>
:root {{
    --th-bg: transparent;
    --th-surface: rgba(128, 128, 128, 0.06);
    --th-accent: var(--primary-color, #229ed9);

    --th-space-1: {DESIGN_TOKENS["space_1"]};
    --th-space-2: {DESIGN_TOKENS["space_2"]};
    --th-space-3: {DESIGN_TOKENS["space_3"]};
    --th-space-4: {DESIGN_TOKENS["space_4"]};
    --th-space-5: {DESIGN_TOKENS["space_5"]};
    --th-space-6: {DESIGN_TOKENS["space_6"]};

    --th-radius-control: {DESIGN_TOKENS["radius_control"]};
    --th-radius-panel: {DESIGN_TOKENS["radius_panel"]};
    --th-radius-pill: {DESIGN_TOKENS["radius_pill"]};
    --th-control-height: {DESIGN_TOKENS["control_height"]};
    --th-top-safe-area: {DESIGN_TOKENS["top_safe_area"]};
    --th-motion-fast: {DESIGN_TOKENS["motion_fast"]};
    --th-motion-normal: {DESIGN_TOKENS["motion_normal"]};

    --th-border: rgba(128, 128, 128, 0.22);
    --th-border-strong: rgba(128, 128, 128, 0.34);
    --th-text-muted: rgba(128, 128, 128, 0.92);
    --th-shadow-sm: 0 4px 16px rgba(0, 0, 0, 0.06);

    --th-success: #16a34a;
    --th-warning: #d97706;
    --th-danger: #dc2626;
    --th-info: #0284c7;
}}

html,
body,
[class*="css"] {{
    text-rendering: optimizeLegibility;
}}

[data-testid="stAppViewContainer"] .block-container,
[data-testid="stMainBlockContainer"] {{
    padding-top: var(--th-top-safe-area);
    padding-bottom: var(--th-space-6);
    overflow: visible;
}}

[data-testid="stSidebar"] {{
    border-right: 1px solid var(--th-border);
}}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: var(--th-space-2);
}}

[data-testid="stSidebar"] hr {{
    margin: var(--th-space-3) 0;
}}

.st-key-sidebar-web-logout {{
    margin-top: calc(var(--th-space-1) * -1);
}}

[data-testid="stExpander"] summary {{
    border-radius: var(--th-radius-control);
    transition:
        background-color var(--th-motion-fast) ease,
        color var(--th-motion-fast) ease;
}}

[data-testid="stExpander"] summary:hover {{
    background: var(--th-surface);
}}

[data-testid="stForm"] {{
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-panel);
    padding: var(--th-space-4);
}}

.stButton > button,
.stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {{
    min-height: var(--th-control-height);
    border-radius: var(--th-radius-control);
    font-weight: 600;
    transition:
        border-color var(--th-motion-fast) ease,
        background-color var(--th-motion-fast) ease,
        box-shadow var(--th-motion-fast) ease,
        transform var(--th-motion-fast) ease;
}}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
    border-color: var(--th-border-strong);
}}

.stButton > button:active,
.stDownloadButton > button:active,
[data-testid="stFormSubmitButton"] > button:active {{
    transform: translateY(1px);
}}

.stButton > button:disabled,
.stDownloadButton > button:disabled {{
    opacity: 0.52;
}}

.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible,
[data-testid="stFormSubmitButton"] > button:focus-visible {{
    outline: 2px solid var(--th-accent);
    outline-offset: 2px;
}}

.stTextInput input,
.stNumberInput input,
[data-testid="stDateInput"] input,
[data-baseweb="select"] > div {{
    min-height: var(--th-control-height);
    border-radius: var(--th-radius-control) !important;
    transition:
        border-color var(--th-motion-fast) ease,
        box-shadow var(--th-motion-fast) ease;
}}

.stTextInput:focus-within input,
.stNumberInput:focus-within input,
[data-testid="stDateInput"]:focus-within input,
[data-baseweb="select"]:focus-within > div {{
    border-color: var(--th-accent) !important;
    box-shadow: 0 0 0 1px var(--th-accent);
}}

.st-key-chat_selector [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div {{
    box-shadow: inset 3px 0 0 var(--th-accent);
}}

[data-testid="stAlert"] {{
    border-radius: var(--th-radius-panel);
}}

[data-testid="stCaptionContainer"],
small {{
    color: var(--th-text-muted);
}}

hr {{
    border-color: var(--th-border);
}}

a[href] {{
    text-underline-offset: 2px;
    text-decoration-thickness: 1px;
    transition: opacity var(--th-motion-fast) ease;
}}

a[href]:hover {{
    opacity: 0.82;
}}

.th-badge {{
    display: inline-flex;
    align-items: center;
    gap: var(--th-space-1);
    min-height: 24px;
    padding: 2px var(--th-space-2);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-pill);
    background: var(--th-surface);
    color: inherit;
    font-size: 0.78rem;
    font-weight: 600;
    line-height: 1.2;
}}

.th-badge::before {{
    content: "";
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--th-text-muted);
}}

.th-badge--success::before {{
    background: var(--th-success);
}}

.th-badge--warning::before {{
    background: var(--th-warning);
}}

.th-badge--danger::before {{
    background: var(--th-danger);
}}

.th-badge--info::before {{
    background: var(--th-info);
}}

.th-section-title {{
    margin: 0 0 var(--th-space-2);
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--th-text-muted);
}}

[class*="st-key-message-card-"] {{
    margin-bottom: var(--th-space-3);
}}

[class*="st-key-message-card-"] [data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: var(--th-border) !important;
    border-radius: var(--th-radius-panel) !important;
    background: transparent;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.035);
    transition:
        border-color var(--th-motion-normal) ease,
        box-shadow var(--th-motion-normal) ease;
}}

[class*="st-key-message-card-"] [data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color: var(--th-border-strong) !important;
    box-shadow: var(--th-shadow-sm);
}}

[class*="st-key-message-card-"] p {{
    line-height: 1.55;
}}

.th-message-meta {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--th-space-2);
    margin-bottom: var(--th-space-2);
    color: var(--th-text-muted);
    font-size: 0.78rem;
    line-height: 1.2;
}}

.th-message-meta__separator {{
    opacity: 0.55;
}}

.th-message-body {{
    margin: 0 0 var(--th-space-3);
    color: inherit;
    font-size: 0.94rem;
    line-height: 1.72;
    text-align: start;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    unicode-bidi: plaintext;
}}

[class*="st-key-message-footer-"] {{
    margin-top: var(--th-space-2);
    padding-top: var(--th-space-2);
    border-top: 1px solid var(--th-border);
}}

[class*="st-key-message-footer-"] [data-testid="stHorizontalBlock"] {{
    align-items: center;
}}

[class*="st-key-message-footer-"] .th-tag-row {{
    margin: 0;
}}

[class*="st-key-message-footer-"] button {{
    min-height: 30px;
}}

[class*="st-key-message-card-"] [data-testid="stVerticalBlock"] {{
    gap: var(--th-space-2);
}}

.th-tag-row {{
    display: flex;
    flex-wrap: wrap;
    gap: var(--th-space-1);
    margin-top: var(--th-space-3);
    margin-bottom: var(--th-space-2);
}}

.th-tag-chip {{
    display: inline-flex;
    align-items: center;
    min-height: 24px;
    padding: 2px var(--th-space-2);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-pill);
    background: var(--th-surface);
    color: inherit;
    font-size: 0.76rem;
    font-weight: 600;
    line-height: 1.2;
    transition:
        border-color var(--th-motion-fast) ease,
        background-color var(--th-motion-fast) ease;
}}

.th-tag-chip:hover {{
    border-color: var(--th-border-strong);
    background: rgba(128, 128, 128, 0.10);
}}

[class*="st-key-edit-tags-"] button,
[class*="st-key-delete-message-"] button {{
    min-height: 32px;
    border-color: transparent !important;
    background: transparent !important;
    box-shadow: none !important;
    font-size: 0.82rem;
    font-weight: 600;
}}

[class*="st-key-edit-tags-"] button {{
    color: var(--th-text-muted) !important;
}}

[class*="st-key-delete-message-"] button {{
    color: var(--th-danger) !important;
}}

[class*="st-key-edit-tags-"] button:hover,
[class*="st-key-delete-message-"] button:hover {{
    background: var(--th-surface) !important;
    border-color: var(--th-border) !important;
}}

[class*="st-key-confirm-delete-message-"] button {{
    border-color: var(--th-danger) !important;
    background: var(--th-danger) !important;
    color: #ffffff !important;
}}


.th-sidebar-brand {{
    display: flex;
    align-items: center;
    gap: var(--th-space-3);
    padding: var(--th-space-2) 0 var(--th-space-3);
}}

.th-sidebar-brand__mark {{
    display: inline-flex;
    width: 36px;
    height: 36px;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--th-border);
    border-radius: 10px;
    background: var(--th-surface);
    font-size: 1.05rem;
}}

.th-sidebar-brand__name {{
    color: inherit;
    font-size: 1rem;
    font-weight: 750;
    line-height: 1.1;
}}

.th-sidebar-brand__version {{
    margin-top: 2px;
    color: var(--th-text-muted);
    font-size: 0.74rem;
}}

.th-account-card {{
    padding: var(--th-space-3);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-panel);
    background: var(--th-surface);
}}

.th-account-card__name {{
    color: inherit;
    font-weight: 700;
}}

.th-account-card__meta {{
    margin-top: 2px;
    color: var(--th-text-muted);
    font-size: 0.8rem;
}}

.th-action-summary {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: var(--th-space-2);
    min-height: var(--th-control-height);
    color: var(--th-text-muted);
    font-size: 0.8rem;
}}

.th-action-summary strong {{
    color: inherit;
    font-weight: 700;
}}

.th-auth-brand {{
    text-align: center;
    margin-bottom: var(--th-space-4);
}}

.th-auth-brand__mark {{
    display: inline-flex;
    width: 44px;
    height: 44px;
    align-items: center;
    justify-content: center;
    margin-bottom: var(--th-space-2);
    border: 1px solid var(--th-border);
    border-radius: 12px;
    background: var(--th-surface);
    font-size: 1.2rem;
}}

.th-auth-brand__name {{
    color: inherit;
    font-size: 1.25rem;
    font-weight: 760;
}}

.th-auth-brand__tagline {{
    margin-top: var(--th-space-1);
    color: var(--th-text-muted);
    font-size: 0.82rem;
}}

.st-key-auth-card {{
    margin-top: 6vh;
}}

.st-key-auth-card [data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: var(--th-border) !important;
    border-radius: 16px !important;
    box-shadow: var(--th-shadow-sm);
    background: transparent;
}}

.th-empty-state {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 180px;
    padding: var(--th-space-5);
    text-align: center;
    color: var(--th-text-muted);
}}

.th-empty-state__mark {{
    display: inline-flex;
    width: 42px;
    height: 42px;
    align-items: center;
    justify-content: center;
    margin-bottom: var(--th-space-3);
    border: 1px solid var(--th-border);
    border-radius: 50%;
    background: var(--th-surface);
    color: inherit;
    font-weight: 700;
}}

.th-empty-state__title {{
    color: inherit;
    font-weight: 700;
    margin-bottom: var(--th-space-1);
}}

.th-empty-state__body {{
    max-width: 440px;
    font-size: 0.84rem;
}}

.th-media-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: var(--th-space-2);
    margin: var(--th-space-2) 0;
    color: var(--th-text-muted);
    font-size: 0.78rem;
}}

[class*="st-key-media-play-"] button,
[class*="st-key-media-photo-"] button {{
    border-color: color-mix(in srgb, var(--th-accent) 42%, var(--th-border)) !important;
}}

[class*="st-key-media-redownload-"] button {{
    border-color: transparent !important;
    background: transparent !important;
    color: var(--th-text-muted) !important;
    box-shadow: none !important;
}}

[class*="st-key-media-redownload-"] button:hover {{
    border-color: var(--th-border) !important;
    background: var(--th-surface) !important;
}}

.st-key-sidebar-web-logout button,
.st-key-sidebar-disconnect-telegram button {{
    border-color: transparent !important;
    background: transparent !important;
    color: var(--th-text-muted) !important;
    box-shadow: none !important;
}}

.st-key-sidebar-web-logout button:hover,
.st-key-sidebar-disconnect-telegram button:hover {{
    border-color: var(--th-border) !important;
    background: var(--th-surface) !important;
}}

.st-key-sidebar-logout-telegram button {{
    border-color: color-mix(
        in srgb,
        var(--th-danger) 45%,
        var(--th-border)
    ) !important;
    color: var(--th-danger) !important;
}}

.st-key-load_more_messages button {{
    border-color: var(--th-accent) !important;
}}

.st-key-load_more_messages button:hover {{
    box-shadow: 0 0 0 1px var(--th-accent);
}}

.st-key-sidebar-add-first-account button,
.st-key-sidebar-add-account-connected button,
.st-key-sidebar-add-account-disconnected button {{
    border-color: color-mix(
        in srgb,
        var(--th-accent) 40%,
        var(--th-border)
    ) !important;
}}

{MESSAGE_HEADER_CSS}

@media (max-width: 900px) {{
    [data-testid="stAppViewContainer"] .block-container,
    [data-testid="stMainBlockContainer"] {{
        padding-top: 40px;
    }}

    .st-key-message-header [data-testid="stHorizontalBlock"] {{
        gap: var(--th-space-2);
    }}

    .th-action-summary {{
        justify-content: flex-start;
    }}

    .st-key-auth-card {{
        margin-top: var(--th-space-3);
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] > button,
    [class*="st-key-message-card-"] [data-testid="stVerticalBlockBorderWrapper"],
    .th-tag-chip,
    [data-testid="stExpander"] summary {{
        transition: none;
    }}
}}
</style>
"""


def apply_theme() -> None:
    """Inject the Telegram Harbor presentation layer once per script run."""
    st.markdown(APP_CSS, unsafe_allow_html=True)


def badge_html(label: str, tone: str = "neutral") -> str:
    """Return safe badge markup for compact status indicators."""
    normalized_tone = tone if tone in {
        "neutral",
        "success",
        "warning",
        "danger",
        "info",
    } else "neutral"
    suffix = "" if normalized_tone == "neutral" else f" th-badge--{normalized_tone}"
    return f'<span class="th-badge{suffix}">{escape(label)}</span>'


def section_title_html(label: str) -> str:
    """Return safe markup for small UI section headings."""
    return f'<div class="th-section-title">{escape(label)}</div>'



def tag_chips_html(tags: list[str]) -> str:
    """Return safe read-mode tag chips for a message card."""
    if not tags:
        return ""
    chips = "".join(
        f'<span class="th-tag-chip">{escape(tag)}</span>'
        for tag in tags
    )
    return f'<div class="th-tag-row">{chips}</div>'


def message_meta_html(
    timestamp: str,
    message_id: int,
    media_label: str | None = None,
) -> str:
    """Return safe compact metadata for the top of a message card."""
    parts = [
        f"<span>{escape(timestamp)}</span>",
        '<span class="th-message-meta__separator">•</span>',
        f"<span>ID {int(message_id)}</span>",
    ]
    if media_label:
        parts.extend(
            [
                '<span class="th-message-meta__separator">•</span>',
                f"<span>{escape(media_label)}</span>",
            ]
        )
    return f'<div class="th-message-meta">{"".join(parts)}</div>'



def sidebar_brand_html(name: str, version: str) -> str:
    return (
        '<div class="th-sidebar-brand">'
        '<span class="th-sidebar-brand__mark">⚓</span>'
        '<span>'
        f'<div class="th-sidebar-brand__name">{escape(name)}</div>'
        f'<div class="th-sidebar-brand__version">v{escape(version)}</div>'
        '</span>'
        '</div>'
    )


def account_card_html(display_name: str, username: str) -> str:
    return (
        '<div class="th-account-card">'
        f'<div class="th-account-card__name">{escape(display_name)}</div>'
        f'<div class="th-account-card__meta">@{escape(username)}</div>'
        '</div>'
    )


def action_summary_html(visible: int, loaded: int) -> str:
    return (
        '<div class="th-action-summary">'
        f'<span><strong>{int(visible)}</strong> visible</span>'
        '<span>•</span>'
        f'<span><strong>{int(loaded)}</strong> loaded</span>'
        '</div>'
    )


def media_meta_html(parts: list[str]) -> str:
    safe_parts = [
        f"<span>{escape(part)}</span>"
        for part in parts
        if part
    ]
    return f'<div class="th-media-meta">{"<span>•</span>".join(safe_parts)}</div>'



def auth_brand_html(
    name: str,
    tagline: str,
    version: str,
) -> str:
    return (
        '<div class="th-auth-brand">'
        '<div class="th-auth-brand__mark">⚓</div>'
        f'<div class="th-auth-brand__name">{escape(name)}</div>'
        f'<div class="th-auth-brand__tagline">{escape(tagline)} · '
        f'v{escape(version)}</div>'
        '</div>'
    )


def empty_state_html(
    title: str,
    body: str,
    mark: str = "—",
) -> str:
    return (
        '<div class="th-empty-state">'
        f'<div class="th-empty-state__mark">{escape(mark)}</div>'
        f'<div class="th-empty-state__title">{escape(title)}</div>'
        f'<div class="th-empty-state__body">{escape(body)}</div>'
        '</div>'
    )



def message_body_html(text: str) -> str:
    """Render message text safely while letting the browser choose RTL/LTR."""
    safe_text = escape(text or "")
    return (
        '<div class="th-message-body" dir="auto">'
        f"{safe_text}"
        "</div>"
    )
