# Design tokens and vendor constants for prates.fyi
# Keep in sync with static/css/style.css

# ── Design tokens ────────────────────────────────────────────────────────────
BG       = "#0c0e14"
SURFACE  = "#131720"
SURFACE2 = "#1a1f2e"
BORDER   = "#252b3b"
TEXT     = "#dde2f0"
MUTED    = "#8892aa"
AMBER    = "#f5a623"
GREEN    = "#34d399"
RED      = "#f87171"
BLUE     = "#60a5fa"

# ── Vendor accent colors ──────────────────────────────────────────────────────
VENDOR_COLORS: dict[str, str] = {
    "Anthropic": "#c96442",
    "OpenAI":    "#10a37f",
    "Google":    "#4285f4",
    "xAI":       "#9b59b6",
    "Cursor":    "#06b6d4",
    "Microsoft": "#00a4ef",
    "Apple":     "#a8b0bf",
    "Meta":      "#0866ff",
    "Industry":  "#f5a623",
}

# CSS class suffix per vendor (used by templates: bar-{key}, tag-{key})
VENDOR_CSS_KEY: dict[str, str] = {
    "Anthropic": "anthropic",
    "OpenAI":    "openai",
    "Google":    "google",
    "xAI":       "xai",
    "Cursor":    "cursor",
    "Microsoft": "microsoft",
    "Apple":     "apple",
    "Meta":      "meta",
    "Industry":  "industry",
}

# Canonical vendor list (controls section order on daily/weekly pages)
VENDORS: list[str] = list(VENDOR_COLORS)
