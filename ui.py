"""The "Clear ledger" look of AlphaScope: styles and small reusable page pieces.

Design rules:
- Colors: warm off-white page, white cards, ink text, one blue for actions,
  green for gains, red for losses, orange for the Step fund.
- Type: Fraunces (serif) for headings and big numbers, Inter for everything else.
- Spacing: multiples of 8px, 12px corners, generous padding.
- Hierarchy: one headline number, then one main card or chart, then details.
"""

from html import escape

import streamlit as st


# Two palettes: the design is light, but the pieces below must stay readable
# if Streamlit is showing its dark theme (for example before a restart picks
# up .streamlit/config.toml, or if someone switches theme in the menu).
LIGHT = {
    "ink": "#14171A", "muted": "#5B6470", "border": "#E5E3DC", "card": "#FFFFFF",
    "action": "#1F4FD8", "gain": "#0E8A5F", "loss": "#C8372D",
    "skeleton_a": "#EFEDE6", "skeleton_b": "#F7F6F1",
    "disabled_bg": "#C9CDD3", "disabled_text": "#5B6470",
}
DARK = {
    "ink": "#F2F2F0", "muted": "#A9AEB6", "border": "#343841", "card": "#1A1D24",
    "action": "#4F74E8", "gain": "#3DBE8B", "loss": "#F0766A",
    "skeleton_a": "#1E2128", "skeleton_b": "#2A2E37",
    "disabled_bg": "#343841", "disabled_text": "#A9AEB6",
}


def palette():
    """The colors that match the theme Streamlit is currently showing."""
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:
        return LIGHT


STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500&family=Inter:wght@400;500;600&display=swap');

/* Inter for all text. Icons are separate elements and keep their own font. */
.stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button,
.stApp summary, .stApp [data-testid="stMarkdownContainer"],
.stApp [data-testid="stMetricLabel"], .stApp [data-testid="stCaptionContainer"],
.stApp [data-baseweb="tab"], .stApp [data-baseweb="select"] {{
    font-family: 'Inter', system-ui, sans-serif !important;
}}
h1, h2, h3, [data-testid="stMetricValue"] {{
    font-family: 'Fraunces', Georgia, serif !important;
    font-weight: 500 !important;
    letter-spacing: -0.01em;
}}
[data-testid="stMetricValue"] {{ font-variant-numeric: tabular-nums; }}
.block-container {{ padding-top: 3rem; padding-bottom: 4rem; max-width: 1200px; }}

/* Primary buttons use the design's action color in either theme. */
button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
    background: {action} !important; border-color: {action} !important; color: #FFFFFF !important;
}}
button[kind="primary"]:disabled, button[data-testid="stBaseButton-primary"]:disabled {{
    background: {disabled_bg} !important; border-color: {disabled_bg} !important;
    color: {disabled_text} !important;
}}

/* Numbers and labels wrap instead of being cut off on narrow screens. */
[data-testid="stMetricValue"] {{ font-size: 1.75rem; }}
[data-testid="stMetricValue"] > div, [data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] > div {{
    white-space: normal !important; overflow: visible !important; text-overflow: clip !important;
}}

/* Touch targets of at least 44px. */
.stButton button, .stDownloadButton button, [data-testid="stFileUploader"] button,
[data-baseweb="tab"], [data-baseweb="select"] > div, .stTextInput input,
.stNumberInput input, [data-testid="stExpander"] summary {{
    min-height: 44px;
}}
.stButton button, .stDownloadButton button {{ border-radius: 12px; font-weight: 500; }}
[data-baseweb="tab"] {{ padding-left: 12px; padding-right: 12px; font-size: 15px; }}
[data-baseweb="tab-list"] {{ gap: 4px; }}

/* A clear focus ring for keyboard users. */
button:focus-visible, input:focus-visible, [data-baseweb="tab"]:focus-visible,
summary:focus-visible, a:focus-visible {{
    outline: 3px solid {action} !important;
    outline-offset: 2px;
}}

.as-hero {{ margin: 8px 0 24px; }}
.as-eyebrow {{ font-size: 14px; color: {muted}; margin-bottom: 4px; }}
.as-hero-number {{
    font-family: 'Fraunces', Georgia, serif; font-weight: 500;
    font-size: clamp(40px, 7vw, 64px); line-height: 1.1; color: {ink};
    font-variant-numeric: tabular-nums;
}}
.as-hero-line {{ font-size: 16px; margin-top: 8px; color: {ink}; }}
.as-gain {{ color: {gain}; font-weight: 600; }}
.as-loss {{ color: {loss}; font-weight: 600; }}
.as-muted {{ color: {muted}; }}

.as-card {{
    background: {card}; border: 1px solid {border}; border-radius: 12px;
    padding: 24px; margin-bottom: 16px;
}}
.as-card h3 {{ margin: 0 0 12px; font-size: 20px; padding: 0; }}
.as-row {{
    display: flex; justify-content: space-between; gap: 16px;
    padding: 12px 0; border-top: 1px solid {border}; font-size: 15px;
}}
.as-row:first-of-type {{ border-top: none; }}
.as-row strong {{ font-weight: 600; }}

.as-empty {{
    background: {card}; border: 1px dashed {border}; border-radius: 12px;
    padding: 40px 24px; text-align: center; margin: 16px 0;
}}
.as-empty h3 {{ margin: 0 0 8px; font-size: 22px; padding: 0; }}
.as-empty p {{ color: {muted}; margin: 0 auto; max-width: 480px; font-size: 16px; }}

.as-skeleton {{
    border-radius: 12px; margin-bottom: 16px;
    background: linear-gradient(90deg, {skeleton_a} 25%, {skeleton_b} 50%, {skeleton_a} 75%);
    background-size: 200% 100%; animation: as-shimmer 1.4s ease-in-out infinite;
}}
@keyframes as-shimmer {{ from {{ background-position: 200% 0; }} to {{ background-position: -200% 0; }} }}
@media (prefers-reduced-motion: reduce) {{ .as-skeleton {{ animation: none; }} }}

@media (max-width: 640px) {{
    .block-container {{ padding-left: 1rem; padding-right: 1rem; padding-top: 2rem; }}
    .as-card {{ padding: 16px; }}
    .as-row {{ flex-direction: column; gap: 4px; }}
}}
</style>
"""


def apply_styles():
    """Add the app's fonts and styles to the page."""
    st.html(STYLES.format(**palette()))


# ---------------------------------------------------------------------------
# Feedback: messages that survive a page rerun
# ---------------------------------------------------------------------------
def flash(message, icon="✅"):
    """Show a toast after the next rerun, so button clicks always get feedback."""
    st.session_state.flash = (message, icon)


def show_flash():
    """Show a waiting toast, if there is one."""
    if "flash" in st.session_state:
        message, icon = st.session_state.pop("flash")
        st.toast(message, icon=icon)


# ---------------------------------------------------------------------------
# Page pieces
# ---------------------------------------------------------------------------
def hero(label, value, change_text, is_gain, context=""):
    """The one headline number on the page, with a plain-language line under it."""
    arrow, word, css = ("▲", "Up", "as-gain") if is_gain else ("▼", "Down", "as-loss")
    st.html(
        f"""
        <div class="as-hero" role="status" aria-live="polite">
          <div class="as-eyebrow">{escape(label)}</div>
          <div class="as-hero-number">{escape(value)}</div>
          <div class="as-hero-line">
            <span class="{css}">{arrow} {word} {escape(change_text)}</span>
            <span class="as-muted">{escape(context)}</span>
          </div>
        </div>
        """
    )


def card(title, rows, footer=""):
    """A white card with a title and a list of (label, detail, tone) rows.

    Tone is "gain", "loss", or "" and colors the detail text.
    """
    body = "".join(
        f'<div class="as-row"><strong>{escape(label)}</strong>'
        f'<span class="{"as-" + tone if tone else "as-muted"}">{escape(detail)}</span></div>'
        for label, detail, tone in rows
    )
    footer_html = f'<p class="as-muted" style="margin:12px 0 0;font-size:14px;">{escape(footer)}</p>' if footer else ""
    st.html(f'<div class="as-card"><h3>{escape(title)}</h3>{body}{footer_html}</div>')


def empty_state(title, message):
    """A friendly placeholder that says what belongs here and what to do next."""
    st.html(
        f'<div class="as-empty"><h3>{escape(title)}</h3><p>{escape(message)}</p></div>'
    )


def skeleton():
    """Grey placeholder blocks shown while market data loads."""
    return """
    <div role="status" aria-label="Loading market data">
      <div class="as-skeleton" style="height:24px;width:160px;"></div>
      <div class="as-skeleton" style="height:72px;width:320px;max-width:100%;"></div>
      <div class="as-skeleton" style="height:24px;width:420px;max-width:100%;"></div>
      <div class="as-skeleton" style="height:320px;"></div>
    </div>
    """
