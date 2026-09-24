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
}


MESSAGE_HEADER_CSS = """
.st-key-message-header {
    position: relative;
    z-index: 2;
    padding: var(--th-space-3) var(--th-space-4) var(--th-space-4);
    margin-bottom: var(--th-space-3);
    background: var(--th-surface);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-panel);
    box-shadow: var(--th-shadow-sm);
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
    --th-bg: var(--background-color, #ffffff);
    --th-surface: var(--secondary-background-color, #f6f8fb);
    --th-text: var(--text-color, #1f2937);
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

    --th-border: rgba(128, 128, 128, 0.22);
    --th-border-strong: rgba(128, 128, 128, 0.34);
    --th-text-muted: rgba(128, 128, 128, 0.92);
    --th-shadow-sm: 0 4px 16px rgba(0, 0, 0, 0.06);

    --th-success: #16a34a;
    --th-warning: #d97706;
    --th-danger: #dc2626;
    --th-info: #0284c7;
}}

@supports (color: color-mix(in srgb, black, white)) {{
    :root {{
        --th-border: color-mix(in srgb, var(--th-text) 16%, transparent);
        --th-border-strong: color-mix(in srgb, var(--th-text) 28%, transparent);
        --th-text-muted: color-mix(in srgb, var(--th-text) 64%, transparent);
        --th-shadow-sm: 0 4px 16px color-mix(in srgb, var(--th-text) 8%, transparent);
    }}
}}

html,
body,
[class*="css"] {{
    text-rendering: optimizeLegibility;
}}

[data-testid="stAppViewContainer"] .block-container {{
    padding-top: var(--th-space-5);
    padding-bottom: var(--th-space-6);
}}

[data-testid="stSidebar"] {{
    border-right: 1px solid var(--th-border);
}}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
    gap: var(--th-space-2);
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
        border-color 120ms ease,
        box-shadow 120ms ease,
        transform 120ms ease;
}}

.stButton > button:hover,
.stDownloadButton > button:hover,
[data-testid="stFormSubmitButton"] > button:hover {{
    border-color: var(--th-border-strong);
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

.th-badge {{
    display: inline-flex;
    align-items: center;
    gap: var(--th-space-1);
    min-height: 24px;
    padding: 2px var(--th-space-2);
    border: 1px solid var(--th-border);
    border-radius: var(--th-radius-pill);
    background: var(--th-surface);
    color: var(--th-text);
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

{MESSAGE_HEADER_CSS}

@media (max-width: 900px) {{
    [data-testid="stAppViewContainer"] .block-container {{
        padding-top: var(--th-space-4);
    }}

    .st-key-message-header [data-testid="stHorizontalBlock"] {{
        gap: var(--th-space-2);
    }}
}}

@media (prefers-reduced-motion: reduce) {{
    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] > button {{
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
