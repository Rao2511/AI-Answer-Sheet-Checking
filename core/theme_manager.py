"""
Theme Manager for Answer Sheet Grader.
Configured exclusively with a clean, high-contrast White and Red theme.
"""

WHITE_RED_THEME = {
    "name": "upGrad School of Technology",
    "bg_base": "#ffffff",
    "bg_gradient": "linear-gradient(155deg, #ffffff 0%, #f8fafc 50%, #f1f5f9 100%)",
    "sidebar_bg": "#ffffff",
    "card_bg": "#ffffff",
    "card_bg_hover": "#ffffff",
    "card_border": "#e2e8f0",
    "card_border_hover": "#eb1c24",
    "accent_primary": "#eb1c24",
    "accent_secondary": "#ff2b34",
    "accent_glow": "rgba(235, 28, 36, 0.25)",
    "accent_gradient": "linear-gradient(135deg, #eb1c24 0%, #d4141c 100%)",
    "btn_gradient": "linear-gradient(135deg, #eb1c24 0%, #d4141c 100%)",
    "btn_hover_gradient": "linear-gradient(135deg, #ff2b34 0%, #eb1c24 100%)",
    "nav_btn_bg": "transparent",
    "nav_btn_hover": "#f8fafc",
    "nav_active_bg": "#eb1c24",
    "nav_active_border": "#eb1c24",
    "text_primary": "#0f172a",
    "text_secondary": "#334155",
    "text_muted": "#64748b",
    "border_subtle": "#e2e8f0",
    "badge_bg": "rgba(235, 28, 36, 0.08)",
    "badge_border": "rgba(235, 28, 36, 0.2)",
    "input_bg": "#ffffff",
    "input_border": "#cbd5e1",
    "chart_colors": ["#eb1c24", "#ff4d55", "#0f172a", "#3b82f6", "#10b981"],
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
