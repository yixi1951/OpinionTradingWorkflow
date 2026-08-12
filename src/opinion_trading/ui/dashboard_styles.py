"""Soft warm minimal-futurism theme for the Streamlit dashboard.

Injected via st.markdown. Frosted glass uses backdrop-filter when the
browser/Streamlit surface allows it; otherwise semi-opaque matte fills apply.
"""

from __future__ import annotations

from typing import Dict


def _light_tokens() -> Dict[str, str]:
    return {
        # Matte warm gray / off-white — low chroma, not cream-paper or terracotta.
        "dash_bg": "#F0EEEC",
        "dash_surface": "rgba(255, 253, 251, 0.58)",
        "dash_surface_solid": "#FAF8F6",
        "dash_surface_raised": "rgba(255, 253, 251, 0.72)",
        "dash_surface_muted": "rgba(238, 234, 230, 0.72)",
        "dash_ink": "#2C2824",
        "dash_muted": "#6E6760",
        "dash_subtle": "#8A827A",
        "dash_border": "rgba(140, 120, 100, 0.18)",
        "dash_border_glow": "rgba(255, 255, 255, 0.55)",
        "dash_accent": "#8B7355",
        "dash_accent_soft": "rgba(139, 115, 85, 0.10)",
        "dash_positive": "#3D6B4F",
        "dash_negative": "#A24B45",
        "dash_shadow": "0 8px 28px rgba(44, 40, 36, 0.06)",
        "dash_shadow_sm": "0 2px 12px rgba(44, 40, 36, 0.04)",
        "dash_shadow_hover": "0 14px 36px rgba(44, 40, 36, 0.09)",
        "sidebar_bg": "#F0EEEC",
        "sidebar_bg_solid": "#F0EEEC",
        "sidebar_border": "rgba(140, 120, 100, 0.14)",
        "sidebar_ink": "#2C2824",
        "sidebar_muted": "#6E6760",
        "sidebar_label": "#2C2824",
        "sidebar_input_bg": "rgba(255, 253, 251, 0.78)",
        "sidebar_input_border": "rgba(140, 120, 100, 0.22)",
        "sidebar_alert_bg": "rgba(255, 253, 251, 0.78)",
        "sidebar_expander_bg": "rgba(255, 253, 251, 0.72)",
        "sidebar_toolbar_bg": "rgba(255, 253, 251, 0.55)",
        "sidebar_hr": "rgba(140, 120, 100, 0.14)",
        "hero_title": "#2C2824",
        "hero_sub": "#6E6760",
        "kicker": "#8B7355",
        "pick_bg": "rgba(255, 253, 251, 0.62)",
        "metric_bg": "rgba(255, 253, 251, 0.55)",
        "openclaw_on": "#4A5C48",
        "tab_active_ink": "#FAF8F6",
        "tab_active_bg": "#8B7355",
        "btn_primary_ink": "#FAF8F6",
        "live_pill_bg": "rgba(139, 115, 85, 0.10)",
        "geo_line": "rgba(139, 115, 85, 0.28)",
        "status_sticky_bg": "rgba(240, 238, 236, 0.82)",
        "chip_bg": "rgba(238, 234, 230, 0.85)",
        "quote_pos_bg": "rgba(61, 107, 79, 0.08)",
        "quote_neg_bg": "rgba(162, 75, 69, 0.07)",
        "badge_ai_bg": "#8B7355",
        "badge_ai_ink": "#FAF8F6",
        "badge_kw_bg": "#8A827A",
        "badge_kw_ink": "#FAF8F6",
        "badge_user_bg": "rgba(61, 107, 79, 0.14)",
        "badge_user_ink": "#3D6B4F",
        "badge_news_bg": "rgba(139, 115, 85, 0.14)",
        "badge_news_ink": "#6B563E",
        "badge_ref_bg": "rgba(238, 234, 230, 0.9)",
        "badge_ref_ink": "#6E6760",
        "trend_pos_bg": "rgba(61, 107, 79, 0.12)",
        "trend_neg_bg": "rgba(162, 75, 69, 0.12)",
        "trend_neu_bg": "rgba(238, 234, 230, 0.95)",
        "sidebar_off_bg": "rgba(162, 75, 69, 0.08)",
        "sidebar_off_ink": "#A24B45",
        "sidebar_on_bg": "rgba(139, 115, 85, 0.12)",
        "sidebar_on_ink": "#4A5C48",
        "chart_ink": "#2C2824",
        "chart_muted": "#6E6760",
        "chart_grid": "rgba(140, 120, 100, 0.14)",
        "chart_fill": "#FAF8F6",
    }


def _dark_tokens() -> Dict[str, str]:
    return {
        "dash_bg": "#1A1816",
        "dash_surface": "rgba(42, 38, 34, 0.62)",
        "dash_surface_solid": "#24201C",
        "dash_surface_raised": "rgba(52, 46, 40, 0.72)",
        "dash_surface_muted": "rgba(36, 32, 28, 0.78)",
        "dash_ink": "#EDE8E2",
        "dash_muted": "#A89F94",
        "dash_subtle": "#8A8178",
        "dash_border": "rgba(200, 180, 160, 0.14)",
        "dash_border_glow": "rgba(255, 245, 235, 0.08)",
        "dash_accent": "#C4A882",
        "dash_accent_soft": "rgba(196, 168, 130, 0.12)",
        "dash_positive": "#7BA88A",
        "dash_negative": "#D08880",
        "dash_shadow": "0 10px 28px rgba(0, 0, 0, 0.32)",
        "dash_shadow_sm": "0 4px 14px rgba(0, 0, 0, 0.22)",
        "dash_shadow_hover": "0 16px 40px rgba(0, 0, 0, 0.38)",
        "sidebar_bg": "#1A1816",
        "sidebar_bg_solid": "#1A1816",
        "sidebar_border": "rgba(200, 180, 160, 0.12)",
        "sidebar_ink": "#EDE8E2",
        "sidebar_muted": "#A89F94",
        "sidebar_label": "#EDE8E2",
        "sidebar_input_bg": "rgba(42, 38, 34, 0.85)",
        "sidebar_input_border": "rgba(200, 180, 160, 0.20)",
        "sidebar_alert_bg": "rgba(42, 38, 34, 0.85)",
        "sidebar_expander_bg": "rgba(42, 38, 34, 0.78)",
        "sidebar_toolbar_bg": "rgba(42, 38, 34, 0.55)",
        "sidebar_hr": "rgba(200, 180, 160, 0.12)",
        "hero_title": "#EDE8E2",
        "hero_sub": "#A89F94",
        "kicker": "#C4A882",
        "pick_bg": "rgba(42, 38, 34, 0.62)",
        "metric_bg": "rgba(42, 38, 34, 0.55)",
        "openclaw_on": "#C4A882",
        "tab_active_ink": "#1A1816",
        "tab_active_bg": "#C4A882",
        "btn_primary_ink": "#1A1816",
        "live_pill_bg": "rgba(196, 168, 130, 0.12)",
        "geo_line": "rgba(196, 168, 130, 0.32)",
        "status_sticky_bg": "rgba(26, 24, 22, 0.85)",
        "chip_bg": "rgba(52, 46, 40, 0.9)",
        "quote_pos_bg": "rgba(123, 168, 138, 0.10)",
        "quote_neg_bg": "rgba(208, 136, 128, 0.10)",
        "badge_ai_bg": "#C4A882",
        "badge_ai_ink": "#1A1816",
        "badge_kw_bg": "#6E6760",
        "badge_kw_ink": "#EDE8E2",
        "badge_user_bg": "rgba(123, 168, 138, 0.16)",
        "badge_user_ink": "#7BA88A",
        "badge_news_bg": "rgba(196, 168, 130, 0.16)",
        "badge_news_ink": "#C4A882",
        "badge_ref_bg": "rgba(52, 46, 40, 0.9)",
        "badge_ref_ink": "#A89F94",
        "trend_pos_bg": "rgba(123, 168, 138, 0.14)",
        "trend_neg_bg": "rgba(208, 136, 128, 0.14)",
        "trend_neu_bg": "rgba(52, 46, 40, 0.95)",
        "sidebar_off_bg": "rgba(208, 136, 128, 0.12)",
        "sidebar_off_ink": "#D08880",
        "sidebar_on_bg": "rgba(196, 168, 130, 0.14)",
        "sidebar_on_ink": "#C4A882",
        "chart_ink": "#EDE8E2",
        "chart_muted": "#A89F94",
        "chart_grid": "rgba(200, 180, 160, 0.12)",
        "chart_fill": "#24201C",
    }


def chart_theme_colors(theme: str = "light") -> Dict[str, str]:
    tok = _dark_tokens() if theme == "dark" else _light_tokens()
    return {
        "ink": tok["chart_ink"],
        "muted": tok["chart_muted"],
        "grid": tok["chart_grid"],
        "view_fill": tok["chart_fill"],
        "font": "Inter",
    }


def build_dashboard_css(theme: str = "light") -> str:
    tok = _dark_tokens() if theme == "dark" else _light_tokens()
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');

:root {{
    --dash-bg: {tok["dash_bg"]};
    --dash-surface: {tok["dash_surface"]};
    --dash-surface-solid: {tok["dash_surface_solid"]};
    --dash-surface-raised: {tok["dash_surface_raised"]};
    --dash-surface-muted: {tok["dash_surface_muted"]};
    --dash-ink: {tok["dash_ink"]};
    --dash-muted: {tok["dash_muted"]};
    --dash-subtle: {tok["dash_subtle"]};
    --dash-border: {tok["dash_border"]};
    --dash-border-glow: {tok["dash_border_glow"]};
    --dash-accent: {tok["dash_accent"]};
    --dash-accent-soft: {tok["dash_accent_soft"]};
    --dash-positive: {tok["dash_positive"]};
    --dash-negative: {tok["dash_negative"]};
    --dash-shadow: {tok["dash_shadow"]};
    --dash-shadow-sm: {tok["dash_shadow_sm"]};
    --dash-shadow-hover: {tok["dash_shadow_hover"]};
    --sidebar-bg: {tok["sidebar_bg"]};
    --sidebar-bg-solid: {tok["sidebar_bg_solid"]};
    --sidebar-border: {tok["sidebar_border"]};
    --sidebar-ink: {tok["sidebar_ink"]};
    --sidebar-muted: {tok["sidebar_muted"]};
    --sidebar-label: {tok["sidebar_label"]};
    --sidebar-input-bg: {tok["sidebar_input_bg"]};
    --sidebar-input-border: {tok["sidebar_input_border"]};
    --sidebar-alert-bg: {tok["sidebar_alert_bg"]};
    --sidebar-expander-bg: {tok["sidebar_expander_bg"]};
    --sidebar-toolbar-bg: {tok["sidebar_toolbar_bg"]};
    --sidebar-hr: {tok["sidebar_hr"]};
    --hero-title: {tok["hero_title"]};
    --hero-sub: {tok["hero_sub"]};
    --kicker: {tok["kicker"]};
    --pick-bg: {tok["pick_bg"]};
    --metric-bg: {tok["metric_bg"]};
    --openclaw-on: {tok["openclaw_on"]};
    --tab-active-ink: {tok["tab_active_ink"]};
    --tab-active-bg: {tok["tab_active_bg"]};
    --btn-primary-ink: {tok["btn_primary_ink"]};
    --live-pill-bg: {tok["live_pill_bg"]};
    --geo-line: {tok["geo_line"]};
    --status-sticky-bg: {tok["status_sticky_bg"]};
    --chip-bg: {tok["chip_bg"]};
    --quote-pos-bg: {tok["quote_pos_bg"]};
    --quote-neg-bg: {tok["quote_neg_bg"]};
    --badge-ai-bg: {tok["badge_ai_bg"]};
    --badge-ai-ink: {tok["badge_ai_ink"]};
    --badge-kw-bg: {tok["badge_kw_bg"]};
    --badge-kw-ink: {tok["badge_kw_ink"]};
    --badge-user-bg: {tok["badge_user_bg"]};
    --badge-user-ink: {tok["badge_user_ink"]};
    --badge-news-bg: {tok["badge_news_bg"]};
    --badge-news-ink: {tok["badge_news_ink"]};
    --badge-ref-bg: {tok["badge_ref_bg"]};
    --badge-ref-ink: {tok["badge_ref_ink"]};
    --trend-pos-bg: {tok["trend_pos_bg"]};
    --trend-neg-bg: {tok["trend_neg_bg"]};
    --trend-neu-bg: {tok["trend_neu_bg"]};
    --sidebar-off-bg: {tok["sidebar_off_bg"]};
    --sidebar-off-ink: {tok["sidebar_off_ink"]};
    --sidebar-on-bg: {tok["sidebar_on_bg"]};
    --sidebar-on-ink: {tok["sidebar_on_ink"]};
    --space-xs: 0.25rem;
    --space-sm: 0.5rem;
    --space-md: 1rem;
    --space-lg: 1.5rem;
    --radius-sm: 10px;
    --radius-md: 14px;
    --radius-lg: 16px;
    --ease-soft: cubic-bezier(0.22, 1, 0.36, 1);
    --dur-soft: 160ms;
    --font-sans: 'Inter', 'Segoe UI', sans-serif;
    --font-mono: 'Inter', ui-monospace, monospace;
    --panel-gap: 1.35rem;
    --glass-blur: 14px;
}}

html, body, [class*="css"] {{
    font-family: var(--font-sans);
    font-size: 0.9375rem;
    font-weight: 400;
    line-height: 1.55;
    color: var(--dash-ink);
    -webkit-font-smoothing: antialiased;
}}

.stApp {{
    background: var(--dash-bg);
}}

/* Thin-line geometric accent — top edge only */
.stApp::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(
        90deg,
        transparent 0%,
        var(--geo-line) 22%,
        var(--geo-line) 78%,
        transparent 100%
    );
    pointer-events: none;
    z-index: 20;
}}

[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebarContent"] {{
    background: var(--sidebar-bg-solid) !important;
    background-color: var(--sidebar-bg-solid) !important;
    border-right: 1px solid var(--sidebar-border) !important;
    border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
    margin: 0.65rem 0 0.65rem 0.65rem;
}}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h4,
[data-testid="stSidebar"] h5,
[data-testid="stSidebar"] h6,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
    color: var(--sidebar-ink) !important;
    line-height: 1.6;
}}

[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {{
    color: var(--sidebar-muted) !important;
}}

[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stRadio label {{
    color: var(--sidebar-label) !important;
    font-size: 0.8125rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.01em;
    margin-bottom: 0.28rem !important;
}}

[data-testid="stSidebar"] input,
[data-testid="stSidebar"] textarea {{
    background: var(--sidebar-input-bg) !important;
    color: var(--sidebar-label) !important;
    border: 1px solid var(--sidebar-input-border) !important;
    border-radius: var(--radius-sm) !important;
    transition: border-color var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft);
}}

[data-testid="stSidebar"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-baseweb="input"] > div {{
    background: var(--sidebar-input-bg) !important;
    color: var(--sidebar-label) !important;
    border-color: var(--sidebar-input-border) !important;
    border-radius: var(--radius-sm) !important;
}}

[data-testid="stSidebar"] [data-baseweb="select"] svg,
[data-testid="stSidebar"] [data-baseweb="input"] svg,
[data-testid="stSidebar"] [data-baseweb="select"] path {{
    color: var(--sidebar-muted) !important;
    fill: var(--sidebar-muted) !important;
}}

[data-testid="stSidebar"] [data-testid="stAlert"] {{
    background: var(--sidebar-alert-bg) !important;
    color: var(--sidebar-label) !important;
    border: 1px solid var(--dash-border) !important;
    border-radius: var(--radius-md) !important;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
}}

[data-testid="stSidebar"] [data-testid="stAlert"] * {{
    color: var(--sidebar-label) !important;
}}

[data-testid="stSidebar"] .status-pill.openclaw-off {{
    background: var(--sidebar-off-bg) !important;
    color: var(--sidebar-off-ink) !important;
    border-color: rgba(162, 75, 69, 0.28) !important;
}}

[data-testid="stSidebar"] .status-pill.openclaw-on {{
    background: var(--sidebar-on-bg) !important;
    color: var(--sidebar-on-ink) !important;
    border-color: var(--dash-border) !important;
}}

[data-testid="stSidebar"] .stButton > button {{
    background: var(--dash-accent) !important;
    color: var(--btn-primary-ink) !important;
    border: 1px solid var(--dash-border) !important;
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-family: var(--font-sans) !important;
    padding: 0.5rem 1.1rem !important;
    transition: transform var(--dur-soft) var(--ease-soft),
                opacity var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft);
    cursor: pointer;
    box-shadow: none;
}}

[data-testid="stSidebar"] .stButton > button:hover {{
    opacity: 0.94;
    box-shadow: var(--dash-shadow-sm);
}}

[data-testid="stSidebar"] .stButton > button:focus-visible {{
    outline: 2px solid var(--dash-accent);
    outline-offset: 2px;
}}

[data-testid="stSidebar"] hr {{
    border-color: var(--sidebar-hr) !important;
    margin: 1rem 0 !important;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] {{
    background: var(--sidebar-expander-bg) !important;
    border: 1px solid var(--sidebar-border) !important;
    border-radius: var(--radius-md) !important;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    overflow: hidden;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
    font-weight: 500 !important;
    color: var(--sidebar-label) !important;
    padding: 0.15rem 0.1rem;
}}

[data-testid="stSidebar"] [data-testid="stExpander"] .streamlit-expanderContent {{
    padding-top: 0.2rem;
}}

.sidebar-toolbar {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.4rem;
    margin: 0.35rem 0 0.85rem;
    padding: 0.7rem 0.75rem;
    border: 1px solid var(--sidebar-border);
    border-radius: var(--radius-md);
    background: var(--sidebar-toolbar-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

.symbol-sentiment-card {{
    margin-bottom: 0.85rem;
}}

.symbol-sentiment-head {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
    margin-top: 0.35rem;
}}

.symbol-sentiment-title {{
    font-family: var(--font-sans);
    font-size: 1.2rem;
    font-weight: 500;
    color: var(--dash-ink);
}}

.symbol-sentiment-meta {{
    display: flex;
    align-items: center;
    gap: 0.65rem;
    flex-wrap: wrap;
    margin: 0.5rem 0;
}}

.symbol-sentiment-platforms {{
    margin: 0.5rem 0;
}}

.symbol-quote {{
    font-size: 0.8125rem;
    line-height: 1.55;
    padding: 0.55rem 0.65rem;
    border-radius: var(--radius-sm);
    margin-top: 0.45rem;
    color: var(--dash-muted);
    border: 1px solid var(--dash-border);
}}

.symbol-quote-label {{
    display: block;
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
    color: var(--dash-subtle);
}}

.symbol-quote--pos {{
    background: var(--quote-pos-bg);
}}

.symbol-quote--neg {{
    background: var(--quote-neg-bg);
}}

.sidebar-toolbar-label {{
    font-size: 0.68rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--dash-subtle);
    font-weight: 500;
}}

.sidebar-toolbar-actions {{
    display: flex;
    gap: 0.45rem;
    flex-wrap: wrap;
}}

.sidebar-toolbar-chip {{
    display: inline-flex;
    align-items: center;
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--dash-border);
    background: var(--dash-accent-soft);
    color: var(--dash-accent);
    font-size: 0.72rem;
    font-weight: 500;
}}

.sidebar-status-fixed {{
    position: sticky;
    top: 0.5rem;
    z-index: 4;
    background: var(--status-sticky-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    padding-bottom: 0.35rem;
}}

.sidebar-status-fixed .openclaw-status-card {{
    margin-bottom: 0.6rem;
}}

.sidebar-brand {{
    font-family: var(--font-sans);
    font-size: 0.72rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--dash-accent) !important;
    margin-bottom: 0.12rem;
    font-weight: 500;
}}

.sidebar-title {{
    font-family: var(--font-sans);
    font-size: 1.2rem;
    font-weight: 500;
    color: var(--sidebar-ink) !important;
    margin-bottom: var(--space-sm);
    line-height: 1.2;
}}

[data-testid="stSidebar"] section[data-testid="stSidebarContent"] > div {{
    padding-top: 0.2rem;
    padding-bottom: 0.2rem;
}}

[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
    background: var(--dash-surface) !important;
    border: 1px solid var(--dash-border) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    padding: 0.6rem 0.75rem;
}}

[data-testid="stSidebar"] .stTextInput,
[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stRadio {{
    margin-bottom: 0.8rem;
}}

[data-testid="stSidebar"] .stButton {{
    margin-top: 0.35rem;
    margin-bottom: 0.9rem;
}}

.block-container {{
    padding: 1.1rem 1.25rem 2.75rem;
    max-width: 1320px;
}}

.main .block-container {{
    gap: var(--panel-gap);
}}

.main .stTabs {{
    background: var(--dash-surface);
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-lg);
    padding: 0.75rem 0.85rem 0.35rem;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: var(--dash-border) !important;
    border-radius: var(--radius-lg) !important;
    background: var(--dash-surface) !important;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    padding: 0.35rem 0.65rem;
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft);
}}

.panel-card {{
    background: var(--dash-surface);
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-lg);
    padding: 1.35rem 1.5rem;
    margin-bottom: var(--panel-gap);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft);
}}

.panel-card:hover {{
    box-shadow:
        inset 0 0 0 1px var(--dash-border-glow),
        var(--dash-shadow-hover);
}}

.panel-card--compact {{
    padding: 0.85rem 1.15rem;
    margin-bottom: 0.85rem;
}}

.panel-card--accent {{
    background: var(--dash-accent-soft);
    border-color: var(--dash-border);
    color: var(--dash-ink);
}}

.panel-card--dark {{
    background: var(--dash-surface-muted);
    border-color: var(--dash-border);
    color: var(--dash-ink);
}}

.comment-panel {{
    background: var(--dash-surface-muted);
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 1rem 1.1rem;
    min-height: 120px;
    backdrop-filter: blur(calc(var(--glass-blur) * 0.6));
    -webkit-backdrop-filter: blur(calc(var(--glass-blur) * 0.6));
}}

.comment-panel-title {{
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--dash-ink);
    margin-bottom: 0.65rem;
}}

h1, h2, h3, h4, h5, h6 {{
    color: var(--dash-ink) !important;
    font-family: var(--font-sans) !important;
    font-weight: 500 !important;
    letter-spacing: -0.02em;
    text-wrap: balance;
}}

.section-kicker {{
    font-family: var(--font-sans);
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--dash-accent);
    font-weight: 500;
    margin-bottom: 0.25rem;
}}

div[data-testid="stDataFrame"] {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    overflow: hidden;
}}

div[data-testid="stDataFrame"] tbody tr:hover {{
    background: var(--dash-accent-soft);
}}

[data-testid="stAlert"] {{
    border-radius: var(--radius-md);
}}

hr {{
    border-color: var(--dash-border) !important;
    margin: var(--space-md) 0 !important;
}}

.dashboard-hero {{
    position: relative;
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-lg);
    padding: 1.5rem 1.65rem;
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    margin-bottom: var(--panel-gap);
    overflow: hidden;
}}

.dashboard-hero--terminal {{
    background: var(--dash-surface);
}}

/* Thin geometric corner marks */
.dashboard-hero::before,
.dashboard-hero::after {{
    content: "";
    position: absolute;
    width: 18px;
    height: 18px;
    border-color: var(--geo-line);
    border-style: solid;
    pointer-events: none;
}}

.dashboard-hero::before {{
    top: 10px;
    left: 10px;
    border-width: 1px 0 0 1px;
}}

.dashboard-hero::after {{
    bottom: 10px;
    right: 10px;
    border-width: 0 1px 1px 0;
}}

.hero-scanline {{
    display: none;
}}

.hero-kpi-grid--6,
.hero-kpi-grid--7 {{
    grid-template-columns: repeat(2, minmax(96px, 1fr));
}}

@media (min-width: 720px) {{
    .hero-kpi-grid--7 {{
        grid-template-columns: repeat(4, minmax(88px, 1fr));
    }}
    .block-container {{
        padding: 1.35rem 1.75rem 3rem;
    }}
}}

@media (min-width: 1100px) {{
    .hero-kpi-grid--6 {{
        grid-template-columns: repeat(6, minmax(88px, 1fr));
    }}
    .hero-kpi-grid--7 {{
        grid-template-columns: repeat(7, minmax(80px, 1fr));
    }}
}}

.hero-kpi-value--warn {{
    color: var(--dash-negative) !important;
    font-weight: 600;
}}

.hero-kpi-value.mono {{
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}}

.sentiment-engine-strip {{
    margin-bottom: var(--panel-gap);
}}

.sentiment-engine-title {{
    font-family: var(--font-sans);
    font-size: 1.05rem;
    font-weight: 500;
    color: var(--dash-ink);
    margin-bottom: 0.35rem;
}}

.sentiment-engine-body {{
    font-size: 0.8125rem;
    color: var(--dash-muted);
    line-height: 1.55;
    margin: 0 0 0.75rem 0;
    max-width: 72ch;
    text-wrap: pretty;
}}

.sentiment-engine-metrics {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
}}

.engine-metric {{
    display: inline-flex;
    align-items: baseline;
    gap: 0.35rem;
    padding: 0.28rem 0.65rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--dash-border);
    background: var(--dash-surface-muted);
    font-family: var(--font-mono);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--dash-ink);
    font-variant-numeric: tabular-nums;
}}

.engine-metric-label {{
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dash-accent);
}}

.hero-top {{
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-lg);
    align-items: flex-start;
    justify-content: space-between;
}}

.hero-copy {{
    flex: 1 1 320px;
    min-width: 0;
}}

.dashboard-kicker {{
    font-family: var(--font-sans);
    font-size: 0.75rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--kicker);
    margin-bottom: 0.35rem;
    font-weight: 500;
}}

.dashboard-title {{
    font-family: var(--font-sans);
    font-size: 1.65rem;
    font-weight: 500;
    line-height: 1.25;
    color: var(--hero-title);
    text-wrap: balance;
}}

.dashboard-subtitle {{
    font-size: 0.875rem;
    font-weight: 300;
    color: var(--hero-sub);
    margin-top: 0.45rem;
    max-width: 58ch;
    line-height: 1.55;
}}

.hero-kpi-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(120px, 1fr));
    gap: 0.55rem;
    flex: 0 1 280px;
}}

.hero-kpi {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    background: var(--dash-surface-muted);
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    transition: border-color var(--dur-soft) var(--ease-soft), background var(--dur-soft) var(--ease-soft);
}}

.hero-kpi:hover {{
}}

.hero-kpi-label {{
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dash-muted);
    margin-bottom: 0.35rem;
}}

.hero-kpi-value {{
    font-family: var(--font-sans);
    font-size: 1.3rem;
    font-weight: 500;
    color: var(--dash-ink);
    line-height: 1.2;
    font-variant-numeric: tabular-nums;
}}

.hero-kpi-value.small {{
    font-size: 0.8125rem;
    font-weight: 400;
}}

.status-strip {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.75rem 0 0.15rem 0;
}}

.status-pill {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.32rem 0.7rem;
    border-radius: var(--radius-sm);
    font-size: 0.8125rem;
    font-weight: 500;
    border: 1px solid var(--dash-border);
    background: var(--dash-surface);
    color: var(--dash-muted);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}}

.status-dot {{
    width: 0.4rem;
    height: 0.4rem;
    border-radius: 50%;
    background: var(--dash-subtle);
    flex-shrink: 0;
}}

.status-pill.live .status-dot {{
    background: var(--dash-accent);
}}

.status-pill.live {{
    border-color: var(--dash-border);
    background: var(--live-pill-bg);
    color: var(--dash-accent);
}}

.status-pill.openclaw-on {{
    border-color: var(--dash-border);
    background: var(--live-pill-bg);
    color: var(--openclaw-on);
}}

.status-pill.openclaw-on .status-dot {{
    background: var(--dash-positive);
}}

.status-pill.openclaw-off {{
    border-color: var(--dash-border);
    background: var(--dash-surface);
    color: var(--dash-subtle);
}}

.status-pill.openclaw-off .status-dot {{
    background: var(--dash-negative);
}}

.openclaw-status-card {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 0.8rem 0.9rem;
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    margin-bottom: 0.55rem;
}}

.openclaw-status-meta {{
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--dash-accent);
    margin-bottom: 0.45rem;
}}

.status-pill--dashboard {{
    width: 100%;
    justify-content: space-between;
    padding: 0.52rem 0.8rem;
    border-radius: var(--radius-sm);
    background: var(--live-pill-bg);
    border-color: var(--dash-border);
}}

.status-pill--dashboard span:last-child {{
    flex: 1;
    text-align: right;
}}

.oc-badge {{
    display: inline-block;
    margin-right: 0.35rem;
    padding: 0.12rem 0.45rem;
    border-radius: 6px;
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.02em;
}}

.oc-badge.ai {{ background: var(--badge-ai-bg); color: var(--badge-ai-ink); }}
.oc-badge.kw {{ background: var(--badge-kw-bg); color: var(--badge-kw-ink); }}
.oc-badge.user {{ background: var(--badge-user-bg); color: var(--badge-user-ink); }}
.oc-badge.news {{ background: var(--badge-news-bg); color: var(--badge-news-ink); }}
.oc-badge.ref {{ background: var(--badge-ref-bg); color: var(--badge-ref-ink); }}

.ref-snippet {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    margin: 0.5rem 0;
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft),
                border-color var(--dur-soft) var(--ease-soft);
    cursor: default;
}}

.ref-snippet:hover {{
    border-color: var(--geo-line);
    box-shadow:
        inset 0 0 0 1px var(--dash-border-glow),
        var(--dash-shadow-hover);
}}

.ref-snippet-head {{
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--dash-muted);
    margin-bottom: 0.35rem;
}}

.ref-snippet-body {{
    font-size: 0.875rem;
    font-weight: 300;
    color: var(--dash-ink);
    line-height: 1.5;
}}

.pipeline-flow {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 0.5rem 0 0.75rem;
}}

.pipeline-step {{
    flex: 1 1 140px;
    padding: 0.65rem 0.75rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--dash-border);
    background: var(--dash-accent-soft);
    font-size: 0.8125rem;
    font-weight: 500;
    color: var(--dash-accent);
}}

.pick-card {{
    position: relative;
    overflow: hidden;
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 1.15rem 1.25rem 1.2rem;
    background: var(--pick-bg);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    min-height: 168px;
    transform: none;
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft),
                border-color var(--dur-soft) var(--ease-soft);
}}

.pick-card::before {{
    content: "";
    position: absolute;
    top: 12px;
    right: 12px;
    width: 12px;
    height: 12px;
    border-top: 1px solid var(--geo-line);
    border-right: 1px solid var(--geo-line);
    pointer-events: none;
    opacity: 0.7;
}}

.pick-card::after {{
    display: none;
}}

.pick-card.rank-1 {{
    border-color: var(--geo-line);
}}

.pick-card.rank-2,
.pick-card.rank-3 {{
    background: var(--pick-bg);
}}

.pick-card:hover {{
    border-color: var(--dash-accent);
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

.disclaimer-banner {{
    padding: 0.45rem 0.85rem;
    margin: 0 0 0.75rem 0;
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-sm);
    background: var(--dash-surface-muted);
    color: var(--dash-muted);
    font-size: 0.78rem;
    font-weight: 300;
    line-height: 1.45;
    box-shadow: none;
    position: relative;
    z-index: 1;
}}

.disclaimer-banner--compact {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.65rem;
    align-items: baseline;
}}

.disclaimer-banner-text {{
    flex: 1 1 240px;
    min-width: 0;
}}

.disclaimer-banner strong {{
    color: var(--dash-ink);
    font-weight: 500;
    white-space: nowrap;
}}

.hero-picks-panel {{
    margin-top: 1rem;
    padding: 0.85rem 1rem;
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    background: var(--dash-surface-muted);
    max-width: 28rem;
}}

.hero-picks-title {{
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dash-accent);
    margin-bottom: 0.55rem;
}}

.hero-pick-row {{
    display: flex;
    align-items: baseline;
    gap: 0.65rem;
    padding: 0.28rem 0;
    border-bottom: 1px solid var(--dash-border);
}}

.hero-pick-row:last-child {{
    border-bottom: none;
}}

.hero-pick-rank {{
    font-size: 0.72rem;
    color: var(--dash-muted);
    width: 1.6rem;
}}

.hero-pick-sym {{
    flex: 1;
    font-weight: 500;
    color: var(--dash-ink);
}}

.hero-pick-score {{
    font-variant-numeric: tabular-nums;
    font-weight: 500;
}}

.hero-pick-score.pos {{ color: var(--dash-positive); }}
.hero-pick-score.neg {{ color: var(--dash-negative); }}
.hero-pick-score.neu {{ color: var(--dash-subtle); }}

.hero-pick-empty {{
    color: var(--dash-muted);
    font-size: 0.85rem;
}}

.hero-kpi-grid--4 {{
    grid-template-columns: repeat(2, minmax(96px, 1fr));
    flex: 1 1 340px;
}}

@media (min-width: 900px) {{
    .hero-kpi-grid--4 {{
        grid-template-columns: repeat(3, minmax(100px, 1fr));
    }}
}}

.command-board {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-lg);
    background: var(--dash-surface-solid);
    padding: 1.15rem 1.25rem 1.05rem;
    margin-bottom: 1rem;
}}

.command-board-head {{
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    align-items: flex-start;
    margin-bottom: 0.95rem;
}}

.command-board-purpose {{
    margin: 0.4rem 0 0;
    max-width: 52ch;
    color: var(--dash-muted);
    font-size: 0.9rem;
    line-height: 1.5;
}}

.command-kpi-row {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 0.65rem;
}}

@media (min-width: 900px) {{
    .command-kpi-row {{
        grid-template-columns: repeat(6, minmax(0, 1fr));
    }}
}}

.command-kpi {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-sm);
    background: var(--dash-surface-muted);
    padding: 0.65rem 0.75rem;
    min-height: 4.5rem;
}}

.workspace-section-title {{
    font-size: 1rem;
    font-weight: 560;
    color: var(--dash-ink);
    margin: 0.85rem 0 0.35rem;
    letter-spacing: 0.01em;
}}

.workspace-section-sub {{
    color: var(--dash-muted);
    font-size: 0.85rem;
    margin: 0 0 0.75rem;
    max-width: 70ch;
    line-height: 1.45;
}}

/* Tabs: readable labels, no float */
.stTabs [data-baseweb="tab-list"] {{
    gap: 0.25rem;
    flex-wrap: wrap;
}}

.main .stTabs {{
    padding-top: 0.35rem;
}}

@media (prefers-reduced-motion: reduce) {{
    .pick-card,
    .ref-snippet,
    .panel-card,
    .hero-kpi,
    [data-testid="stSidebar"] .stButton > button,
    .stTabs [data-baseweb="tab"],
    .main .stButton > button,
    [data-testid="stVerticalBlockBorderWrapper"] {{
        transition: none !important;
        animation: none !important;
    }}
    .pick-card:hover,
    .ref-snippet:hover,
    .panel-card:hover,
    .hero-kpi:hover,
    [data-testid="stSidebar"] .stButton > button:hover,
    .stTabs [data-baseweb="tab"]:hover {{
        transform: none !important;
    }}
}}

.pick-rank {{
    display: inline-block;
    font-size: 0.6875rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--dash-muted);
    font-weight: 500;
    background: var(--chip-bg);
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--dash-border);
    margin-bottom: 0.5rem;
}}

.pick-symbol {{
    font-family: var(--font-sans);
    font-size: 1.1rem;
    font-weight: 500;
    color: var(--dash-ink);
    margin: 0.12rem 0 0.35rem 0;
}}

.pick-score {{
    font-family: var(--font-sans);
    font-size: 1.55rem;
    font-weight: 500;
    line-height: 1;
    font-variant-numeric: tabular-nums;
}}

.pick-score.pos {{ color: var(--dash-positive); }}
.pick-score.neg {{ color: var(--dash-negative); }}
.pick-score.neu {{ color: var(--dash-subtle); }}

.reason-card {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 1rem;
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    min-height: 220px;
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft);
}}

.reason-card:hover {{
    box-shadow:
        inset 0 0 0 1px var(--dash-border-glow),
        var(--dash-shadow-hover);
}}

.section-surface {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    background: var(--dash-surface);
    padding: 0.2rem 0.4rem;
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

div[data-testid="stMetric"] {{
    background: var(--metric-bg);
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    padding: 0.85rem 1rem;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    transition: border-color var(--dur-soft) var(--ease-soft), background var(--dur-soft) var(--ease-soft);
}}

div[data-testid="stMetric"]:hover {{
}}

div[data-testid="stMetric"] label {{
    color: var(--dash-subtle) !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}

div[data-testid="stMetric"] [data-testid="stMetricValue"] {{
    font-family: var(--font-mono);
    color: var(--dash-ink) !important;
    font-weight: 500 !important;
    font-variant-numeric: tabular-nums;
}}

.stTabs [data-baseweb="tab-list"] {{
    gap: 0.35rem;
    border-bottom: none;
    background: var(--dash-surface-muted);
    border-radius: var(--radius-md);
    padding: 0.3rem;
    width: fit-content;
    max-width: 100%;
    border: 1px solid var(--dash-border);
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    overflow-x: auto;
}}

.stTabs [data-baseweb="tab-list"]::before {{
    display: none;
}}

.stTabs [data-baseweb="tab"] {{
    position: relative;
    z-index: 1;
    border-radius: var(--radius-sm) !important;
    padding: 0.5rem 0.95rem !important;
    font-weight: 500;
    font-size: 0.8125rem;
    color: var(--dash-muted);
    cursor: pointer;
    transition: color var(--dur-soft) var(--ease-soft),
                background var(--dur-soft) var(--ease-soft),
                transform var(--dur-soft) var(--ease-soft);
    border: 1px solid transparent !important;
    background: transparent !important;
}}

.stTabs [data-baseweb="tab"]:hover {{
    color: var(--dash-ink);
    background: var(--dash-accent-soft) !important;
}}

.stTabs [aria-selected="true"] {{
    color: var(--tab-active-ink) !important;
    background: var(--tab-active-bg) !important;
    border-bottom: none !important;
    box-shadow: none;
}}

.stTabs [aria-selected="true"]::after {{
    display: none;
}}

.stTabs [data-baseweb="tab-panel"] {{
    padding-top: 1.25rem;
}}

.main .stButton > button {{
    border-radius: var(--radius-sm) !important;
    font-weight: 500 !important;
    font-family: var(--font-sans) !important;
    border: 1px solid var(--dash-border) !important;
    background: var(--dash-surface) !important;
    color: var(--dash-ink) !important;
    transition: transform var(--dur-soft) var(--ease-soft),
                box-shadow var(--dur-soft) var(--ease-soft),
                opacity var(--dur-soft) var(--ease-soft);
    cursor: pointer;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}}

.main .stButton > button:hover {{
    box-shadow: var(--dash-shadow-sm);
}}

.main .stButton > button[kind="primary"],
.main .stButton > button[data-testid="baseButton-primary"] {{
    background: var(--dash-accent) !important;
    color: var(--btn-primary-ink) !important;
    border: 1px solid var(--dash-border) !important;
}}

.guide-card {{
    border: 1px solid var(--dash-border);
    padding: 0.9rem 1rem;
    margin: 0.35rem 0 0.8rem 0;
    background: var(--dash-surface-muted);
    border-radius: var(--radius-md);
    color: var(--dash-muted);
    font-size: 0.875rem;
    font-weight: 300;
    line-height: 1.65;
    max-width: 72ch;
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

.guide-card-title {{
    font-family: var(--font-sans);
    font-weight: 500;
    color: var(--dash-ink);
    margin-bottom: 0.5rem;
    font-size: 1rem;
}}

.panel-rail {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    padding: 0.6rem 0.7rem 0.8rem;
    margin: 0.35rem 0 1rem 0;
}}

.panel-rail--compact {{
    padding: 0.55rem 0.65rem 0.7rem;
}}

.panel-section-title {{
    font-family: var(--font-sans);
    font-size: 0.76rem;
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--dash-ink);
    margin-bottom: 0.25rem;
}}

.panel-subtitle {{
    font-size: 0.74rem;
    font-weight: 300;
    color: var(--dash-muted);
    margin-bottom: 0.55rem;
    line-height: 1.45;
}}

.panel-rail::before {{
    content: "";
    display: block;
    height: 1px;
    background: linear-gradient(
        90deg,
        transparent,
        var(--geo-line),
        transparent
    );
    margin-bottom: 0.55rem;
}}

.panel-headbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-bottom: 0.65rem;
}}

.panel-headbar-left {{
    min-width: 0;
}}

.panel-headbar-right {{
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    flex-wrap: wrap;
}}

.panel-headbar-chip {{
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.18rem 0.52rem;
    border-radius: var(--radius-sm);
    border: 1px solid var(--dash-border);
    background: var(--dash-accent-soft);
    color: var(--dash-accent);
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.03em;
    text-transform: uppercase;
}}

.chart-shell {{
    border: 1px solid var(--dash-border);
    border-radius: var(--radius-md);
    background: var(--dash-surface);
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
    padding: 0.75rem;
    margin-top: 0.5rem;
}}

.chart-shell .stDataFrame,
.chart-shell [data-testid="stDataFrame"] {{
    background: transparent !important;
}}

.panel-control-grid {{
    display: grid;
    gap: 0.6rem;
}}

.panel-control-row {{
    border: 1px solid var(--dash-border);
    background: var(--dash-surface);
    border-radius: var(--radius-md);
    padding: 0.75rem 0.8rem;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    box-shadow: inset 0 0 0 1px var(--dash-border-glow);
}}

.panel-control-row + .panel-control-row {{
    margin-top: 0.5rem;
}}

.panel-control-label {{
    font-size: 0.72rem;
    font-weight: 500;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--dash-subtle);
    margin-bottom: 0.4rem;
}}

.panel-control-hint {{
    font-size: 0.75rem;
    font-weight: 300;
    color: var(--dash-subtle);
    margin-top: 0.35rem;
}}

.panel-control-actions {{
    display: grid;
    gap: 0.55rem;
    margin-top: 0.65rem;
}}

.trend-pill {{
    display: inline-block;
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    font-size: 0.75rem;
    font-weight: 500;
}}

.trend-pill.pos {{ background: var(--trend-pos-bg); color: var(--dash-positive); }}
.trend-pill.neg {{ background: var(--trend-neg-bg); color: var(--dash-negative); }}
.trend-pill.neu {{ background: var(--trend-neu-bg); color: var(--dash-subtle); }}

.score-badge {{
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 6px;
    font-size: 0.6875rem;
    font-weight: 500;
    letter-spacing: 0.03em;
    font-family: var(--font-mono);
    font-variant-numeric: tabular-nums;
}}

.score-badge.strong {{ background: var(--dash-positive); color: #F5F7F5; }}
.score-badge.positive {{ background: var(--dash-accent); color: var(--btn-primary-ink); }}
.score-badge.risk {{ background: var(--dash-negative); color: #FFF5F4; }}
.score-badge.weak {{ background: #9A7B5C; color: #FAF8F6; }}
.score-badge.neutral {{ background: var(--dash-subtle); color: #FAF8F6; }}

.platform-chip {{
    display: inline-block;
    margin: 0.15rem 0.35rem 0 0;
    padding: 0.2rem 0.55rem;
    border-radius: var(--radius-sm);
    background: var(--chip-bg);
    border: 1px solid var(--dash-border);
    font-size: 0.75rem;
    font-weight: 500;
}}

.platform-chip-label {{ font-weight: 400; }}

.trend-up {{ color: var(--dash-positive); font-size: 1rem; }}
.trend-down {{ color: var(--dash-negative); font-size: 1rem; }}
.trend-flat {{ color: var(--dash-subtle); font-size: 0.75rem; }}

@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {{
    .panel-card,
    .pick-card,
    .dashboard-hero,
    .openclaw-status-card,
    .reason-card,
    .chart-shell,
    .panel-rail,
    .main .stTabs,
    [data-testid="stVerticalBlockBorderWrapper"],
    .disclaimer-banner {{
        background: var(--dash-surface-solid);
    }}
}}
</style>
"""


def inject_dashboard_styles(theme: str = "light") -> None:
    import streamlit as st

    st.markdown(build_dashboard_css(theme), unsafe_allow_html=True)
