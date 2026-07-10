"""
NETRACK — Central configuration: colors, fonts, constants.
Keeping every visual token in one place makes the rest of the app themeable
and keeps modules decoupled from raw hex strings.
"""

# ── Hero MotoCorp Brand ─────────────────────────────────────────────────────
HERO_RED       = "#D9241C"
HERO_RED_HOVER = "#B91C1C"
HERO_BLUE      = "#1E4D9B"
HERO_BLUE_HOVER = "#153B73"
HERO_DARK      = "#19212B"

# ── Template Panel Colors ───────────────────────────────────────────────────
PANEL_GREEN    = HERO_BLUE
PANEL_HDR_TXT  = "#FFFFFF"
PANEL_ACCENT   = "#F4F7FA"

# ── Page ────────────────────────────────────────────────────────────────────
BG_PAGE     = "#EEF2F6"
CARD_BG     = "#FFFFFF"
CARD_BORDER = "#D8DEE7"

# ── Text ────────────────────────────────────────────────────────────────────
T_DARK  = "#1F2937"
T_BODY  = "#4B5563"
T_SEC   = "#6B7280"
T_LIGHT = "#9CA3AF"
T_WHITE = "#FFFFFF"

# ── Status ──────────────────────────────────────────────────────────────────
S_GREEN     = "#2E8B57"
S_GREEN_BG  = "#E8F5EE"
S_GREEN_ALT = "#C8E6D2"
S_RED       = "#F44336"
S_RED_BG    = "#FFEBEE"
S_RED_ALT   = "#FFCDD2"
S_YELLOW    = "#F59E0B"
S_YELLOW_BG = "#FFF7ED"
S_YELLOW_ALT= "#FDE68A"
S_AMBER     = "#FF9800"
S_BLUE      = HERO_BLUE

# ── Chart Palette ───────────────────────────────────────────────────────────
CHART_PAL = [
    HERO_BLUE, HERO_RED, S_AMBER, "#8B5CF6",
    "#14B8A6", "#EF4444", "#64748B", "#0F766E",
]

# ── OT Priority Levels ──────────────────────────────────────────────────────
PRIORITIES = ["High", "Medium", "Low"]

PRIORITY_COLORS = {
    "High":   (HERO_RED, "#FEF2F2", "#C62828"),
    "Medium": (S_AMBER, "#FFF7ED", "#E65100"),
    "Low":    (HERO_BLUE, "#EFF6FF", "#153B73"),
}

STATUS_COLOR_MAP = {
    "online":   (S_GREEN,  S_GREEN_BG,  "#2E7D32"),
    "offline":  (S_RED,    S_RED_BG,    "#C62828"),
    "checking": (S_YELLOW, S_YELLOW_BG, "#F57F17"),
    "pending":  (T_LIGHT,  "#F5F5F5",   T_SEC),
}

# ── Timing ──────────────────────────────────────────────────────────────────
AUTO_SCAN_SECONDS = 15          # auto re-scan cadence
SCAN_MAX_WORKERS  = 50          # thread-pool size for ping sweep
PING_TIMEOUT_MS   = 800

# During a sweep, individual ping results can land many times a second.
# Redrawing on every single one is what causes visible flicker, so UI
# refreshes during a scan are coalesced into batches at this interval
# instead — still feels live, never flickers.
UI_REFRESH_THROTTLE_MS = 250

# ── CSV Schema ──────────────────────────────────────────────────────────────
CSV_FIELDS = ["Location", "Model", "IP", "Priority"]
DEFAULT_PRIORITY = "Medium"

# ── Fonts ───────────────────────────────────────────────────────────────────
F_BRAND   = ("Segoe UI", 14, "bold")
F_SUBTLE  = ("Segoe UI", 8)
F_HEADER  = ("Segoe UI", 9, "bold")
F_BODY    = ("Segoe UI", 10)
F_MONO    = ("Consolas", 14, "bold")

# ── Primary KPI card fonts (Total / Online / Offline / Availability / Critical) ──
F_KPI_TITLE    = ("Segoe UI", 19, "bold")   # card header title
F_KPI_SUBTITLE = ("Segoe UI", 16)           # descriptive line under header ("High-Priority Nodes Offline", etc.)
F_KPI_VALUE    = ("Segoe UI", 36, "bold")   # big number
F_KPI_UNIT     = ("Segoe UI", 14)           # small text under the value

# ── Secondary KPI strip fonts (High/Medium/Low priority, Scanning Now, Scan Engine) ──
F_KPI_SEC_TITLE = ("Segoe UI", 13, "bold")
F_KPI_SEC_VALUE = ("Segoe UI", 24, "bold")
F_KPI_SEC_UNIT  = ("Segoe UI", 11)
