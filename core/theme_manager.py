"""
Theme Manager for Answer Sheet Grader.
Configured exclusively with a clean, high-contrast White and Red theme.
"""

WHITE_RED_THEME = {
    "name": "White & Red",
    "bg_base": "#ffffff",
    "bg_gradient": "linear-gradient(145deg, #ffffff 0%, #f8fafc 40%, #f1f5f9 100%)",
    "sidebar_bg": "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
    "card_bg": "#ffffff",
    "card_bg_hover": "#ffffff",
    "card_border": "rgba(225, 29, 72, 0.15)",
    "card_border_hover": "rgba(225, 29, 72, 0.45)",
    "accent_primary": "#e11d48",
    "accent_secondary": "#f43f5e",
    "accent_glow": "rgba(225, 29, 72, 0.25)",
    "accent_gradient": "linear-gradient(135deg, #e11d48 0%, #f43f5e 50%, #be123c 100%)",
    "btn_gradient": "linear-gradient(135deg, #e11d48 0%, #be123c 100%)",
    "btn_hover_gradient": "linear-gradient(135deg, #f43f5e 0%, #e11d48 100%)",
    "nav_btn_bg": "rgba(225, 29, 72, 0.05)",
    "nav_btn_hover": "rgba(225, 29, 72, 0.12)",
    "nav_active_bg": "linear-gradient(90deg, rgba(225, 29, 72, 0.14) 0%, rgba(244, 63, 94, 0.06) 100%)",
    "nav_active_border": "#e11d48",
    "text_primary": "#0f172a",
    "text_secondary": "#334155",
    "text_muted": "#64748b",
    "border_subtle": "#e2e8f0",
    "badge_bg": "rgba(225, 29, 72, 0.1)",
    "badge_border": "rgba(225, 29, 72, 0.25)",
    "input_bg": "#ffffff",
    "input_border": "#cbd5e1",
    "chart_colors": ["#e11d48", "#f43f5e", "#fb7185", "#0f172a", "#64748b"],
}


def get_theme(*args, **kwargs) -> dict:
    """Returns the dedicated White & Red theme."""
    return WHITE_RED_THEME


def generate_theme_css(*args, **kwargs) -> str:
    """Generates CSS variables for the White & Red theme."""
    t = WHITE_RED_THEME
    return f"""
    <style>
    :root {{
        --bg-base: {t['bg_base']};
        --bg-gradient: {t['bg_gradient']};
        --sidebar-bg: {t['sidebar_bg']};
        --card-bg: {t['card_bg']};
        --card-bg-hover: {t['card_bg_hover']};
        --card-border: {t['card_border']};
        --card-border-hover: {t['card_border_hover']};
        --accent-primary: {t['accent_primary']};
        --accent-secondary: {t['accent_secondary']};
        --accent-glow: {t['accent_glow']};
        --accent-gradient: {t['accent_gradient']};
        --btn-gradient: {t['btn_gradient']};
        --btn-hover-gradient: {t['btn_hover_gradient']};
        --nav-btn-bg: {t['nav_btn_bg']};
        --nav-btn-hover: {t['nav_btn_hover']};
        --nav-active-bg: {t['nav_active_bg']};
        --nav-active-border: {t['nav_active_border']};
        --text-primary: {t['text_primary']};
        --text-secondary: {t['text_secondary']};
        --text-muted: {t['text_muted']};
        --border-subtle: {t['border_subtle']};
        --badge-bg: {t['badge_bg']};
        --badge-border: {t['badge_border']};
        --input-bg: {t['input_bg']};
        --input-border: {t['input_border']};
    }}
    </style>
    """
