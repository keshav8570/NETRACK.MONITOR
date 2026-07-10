"""
NETRACK — OT Network Switch Monitor  |  Hero MotoCorp
Main dashboard orchestrator.

This module wires together the modular pieces (data_manager, scanner,
charts, switch_monitor, dialogs) into the same NOC-template look as the
original single-file build, while adding: CRUD, two-way CSV sync,
15s auto-scan, maximize/minimize detail views, a compact priority-aware
Switch Monitor, and search/filter/sort.
"""

import os
from tkinter import ttk, Canvas
from datetime import datetime

import customtkinter as ctk

from . import charts
from .config import (
    HERO_RED, HERO_RED_HOVER, HERO_DARK, HERO_BLUE, PANEL_GREEN, BG_PAGE, CARD_BG, CARD_BORDER,
    T_DARK, T_BODY, T_SEC, T_LIGHT, T_WHITE, S_GREEN, S_RED, S_AMBER,
    AUTO_SCAN_SECONDS, PRIORITIES, UI_REFRESH_THROTTLE_MS,
    F_KPI_TITLE, F_KPI_SUBTITLE, F_KPI_VALUE, F_KPI_UNIT,
    F_KPI_SEC_TITLE, F_KPI_SEC_VALUE, F_KPI_SEC_UNIT,
)
from .data_manager import DataManager
from .dialogs import ManageSwitchesDialog, DetailWindow, SwitchFormDialog
from .scanner import NetworkScanner
from .switch_monitor import SwitchMonitor
from .ui_panels import panel, bind_click_recursive

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

SORT_OPTIONS = ["Priority", "Location", "Model", "IP", "Status"]


class NetackDashboard:
    """NOC-template OT network monitoring dashboard for Hero MotoCorp."""

    def __init__(self, root):
        self.root = root
        self.root.title("NETRACK — OT Network Switch Monitor  |  Hero MotoCorp")
        self.root.geometry("1520x980")
        self.root.configure(fg_color=BG_PAGE)
        self.root.minsize(1280, 860)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(os.path.dirname(script_dir), "switches.csv")

        # ── Data / scan engine ─────────────────────────────────────
        self.dm = DataManager(csv_path)
        self.scanner = NetworkScanner(self.dm)

        # ── State ───────────────────────────────────────────────────
        self.is_scanning = False
        self.countdown_seconds = AUTO_SCAN_SECONDS
        self.active_status_filter = "ALL"
        self.active_priority_filter = "ALL"
        self.active_sort = "Priority"
        self.processed_pings = 0
        self._redraw_job = None

        # Coalesced-refresh state: a scan fires on_switch_done up to
        # SCAN_MAX_WORKERS times per second. Rather than redrawing on every
        # single one (the old behaviour, and the source of the flicker),
        # callbacks just raise this flag and a fixed-interval ticker (below)
        # does the actual redraw — at most once per UI_REFRESH_THROTTLE_MS.
        self._refresh_pending = False
        # Cache of "last text/color shown" per widget, so a periodic tick
        # that recomputes the same value never issues a redundant
        # .configure() call (and therefore never repaints) when nothing
        # actually changed.
        self._last_widget_state = {}

        # ── Treeview Theme (used by CRUD / detail tables) ─────────────
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"),
                              background="#E8E8E8", foreground=T_DARK, borderwidth=1, relief="flat")
        self.style.map("Treeview.Heading", background=[("active", "#D0D0D0")])
        self.style.configure("Treeview", rowheight=28, font=("Segoe UI", 10),
                              background=CARD_BG, foreground=T_BODY, fieldbackground=CARD_BG,
                              borderwidth=0)
        self.style.map("Treeview", background=[("selected", "#BBDEFB")],
                        foreground=[("selected", T_DARK)])

        # ── Build UI ────────────────────────────────────────────────
        self._build_header()
        self._build_kpi_primary()      # 5 large, at-a-glance KPIs
        self._build_controls()
        self._build_kpi_secondary()    # smaller, lower-priority breakdown
        self._build_middle_row()
        self._build_bottom_row()
        self._build_footer()

        self.switch_monitor = SwitchMonitor(self.cv_switches, compact=True)
        self.switch_monitor.on_row_click = None
        self._priority_summary = {"High": 0, "Medium": 0, "Low": 0}

        # ── Load Data & Start ───────────────────────────────────────
        self.dm.load()
        self._warn_on_bad_csv_rows()
        self.apply_filter()
        self.update_counters()

        self.root.after(500, self._tick_clock)
        self.root.after(800, self._redraw_charts)
        self.root.after(1000, self.start_scan)
        self.root.after(1000, self._tick_auto_scan)
        self.root.after(4000, self._tick_csv_watch)
        self.root.after(UI_REFRESH_THROTTLE_MS, self._tick_ui_refresh)

    # ═══════════════════════════════════════════════════════════════
    #  CHANGE-DETECTED WIDGET UPDATES  (no-op if value is unchanged)
    # ═══════════════════════════════════════════════════════════════

    def _set_text(self, key, widget, text, **kwargs):
        """configure(text=..., **kwargs) only if this exact combination
        wasn't already showing — this is what stops widgets from being
        needlessly re-rendered (and visually flashing) every tick when
        their value hasn't actually moved."""
        state = (text, tuple(sorted(kwargs.items())))
        if self._last_widget_state.get(key) == state:
            return
        self._last_widget_state[key] = state
        widget.configure(text=text, **kwargs)

    def _warn_on_bad_csv_rows(self):
        w = self.dm.load_warnings
        bad = w.get("invalid_ip", 0) + w.get("duplicate_ip", 0)
        if bad:
            parts = []
            if w.get("invalid_ip"):
                parts.append(f"{w['invalid_ip']} invalid IP")
            if w.get("duplicate_ip"):
                parts.append(f"{w['duplicate_ip']} duplicate IP")
            text = "⚠ switches.csv: skipped " + ", ".join(parts)
        else:
            text = ""
        if hasattr(self, "ft_warning"):
            self._set_text("ft_warning", self.ft_warning, text)

    # ═══════════════════════════════════════════════════════════════
    #  HEADER
    # ═══════════════════════════════════════════════════════════════

    def _build_header(self):
        hdr = ctk.CTkFrame(self.root, fg_color=HERO_DARK, height=48, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        self.watermark = ctk.CTkLabel(self.root, text="HM", font=("Segoe UI", 96, "bold"),
                                      text_color="#DDE6F0")
        self.watermark.place(relx=0.5, rely=0.48, anchor="center")

        brand = ctk.CTkFrame(hdr, fg_color="transparent")
        brand.pack(side="left", padx=20, pady=4)

        bar = ctk.CTkFrame(brand, fg_color=HERO_RED, width=3, height=26, corner_radius=2)
        bar.pack(side="left", padx=(0, 10))
        bar.pack_propagate(False)

        txt = ctk.CTkFrame(brand, fg_color="transparent")
        txt.pack(side="left")
        ctk.CTkLabel(txt, text="NETRACK", font=("Segoe UI", 14, "bold"),
                     text_color=T_WHITE).pack(anchor="w")
        ctk.CTkLabel(txt, text="HERO MOTOCORP  ·  OT Network Infrastructure",
                     font=("Segoe UI", 8), text_color="#9E9E9E").pack(anchor="w")

        # Right: CRUD entry point + live clock
        right = ctk.CTkFrame(hdr, fg_color="transparent")
        right.pack(side="right", padx=20, pady=4)

        clk = ctk.CTkFrame(right, fg_color="transparent")
        clk.pack(side="right", padx=(14, 0))
        self.lbl_clock = ctk.CTkLabel(clk, text="--:--:--", font=("Consolas", 14, "bold"),
                                       text_color=T_WHITE)
        self.lbl_clock.pack(anchor="e")
        self.lbl_date = ctk.CTkLabel(clk, text="", font=("Segoe UI", 8), text_color="#9E9E9E")
        self.lbl_date.pack(anchor="e")

        ctk.CTkButton(right, text="⚙  Manage Switches", font=("Segoe UI", 10, "bold"),
                      fg_color="transparent", border_width=1, border_color="#5F6B7A",
                      hover_color="#2C3A4A", height=30, width=160,
                      command=self._open_manage_dialog).pack(side="right", padx=(0, 6))

        ctk.CTkFrame(self.root, fg_color=HERO_RED, height=2, corner_radius=0).pack(fill="x")

    # ═══════════════════════════════════════════════════════════════
    #  PRIMARY KPI ROW — 5 large, at-a-glance metrics
    # ═══════════════════════════════════════════════════════════════
    #  Everything an operator needs in the first half-second of looking
    #  at the screen: how many switches exist, how many are up/down,
    #  overall availability, and how many *critical* (High-priority) OT
    #  nodes are currently down. Lower-priority breakdowns (by priority
    #  tier, scan-in-progress count, etc.) live in the smaller secondary
    #  strip below the controls, so they don't compete for attention.

    def _build_kpi_primary(self):
        row = ctk.CTkFrame(self.root, fg_color="transparent", height=210)
        row.pack(fill="x", padx=15, pady=(6, 5))
        row.pack_propagate(False)
        for col in range(5):
            row.grid_columnconfigure(col, weight=1, uniform="kpi_primary")
        row.grid_rowconfigure(0, weight=1)

        def big_card(col, title, subtitle, color):
            c, b, _ = panel(row, title, subtitle,
                             title_font=F_KPI_TITLE, subtitle_font=F_KPI_SUBTITLE,
                             header_height=46, subtitle_height=48, wrap_text=True)
            c.grid(row=0, column=col, sticky="nsew", padx=4)
            val = ctk.CTkLabel(b, text="0", font=F_KPI_VALUE, text_color=color)
            val.pack(expand=True, pady=(4, 0))
            unit = ctk.CTkLabel(b, text="", font=F_KPI_UNIT, text_color=T_SEC,
                                 wraplength=200, justify="center")
            unit.pack(pady=(0, 8))
            return c, val, unit

        c1, self.kpi_total, self.kpi_total_sub = big_card(
            0, "Total Switches", "OT Infrastructure Circuit", T_DARK)
        bind_click_recursive(c1, lambda: self.set_status_filter("ALL"))

        c2, self.kpi_online_big, self.kpi_online_sub = big_card(
            1, "Online", "Active Connected Nodes", S_GREEN)
        bind_click_recursive(c2, lambda: self.set_status_filter("ONLINE"))

        c3, self.kpi_offline_big, self.kpi_offline_sub = big_card(
            2, "Offline", "Unreachable OT Nodes", S_RED)
        bind_click_recursive(c3, lambda: self.set_status_filter("OFFLINE"))

        c4, self.kpi_avail, self.kpi_avail_unit = big_card(
            3, "Network Availability", "Current Infrastructure Uptime", S_GREEN)
        self.kpi_avail_unit.configure(text="% availability")

        c5, self.kpi_critical, self.kpi_critical_sub = big_card(
            4, "Critical Down", "High-Priority Nodes Offline", HERO_RED)
        bind_click_recursive(c5, lambda: self.set_status_filter("CRITICAL"))

        self.kpi_cards = {"ALL": c1, "ONLINE": c2, "OFFLINE": c3, "CRITICAL": c5}

    # ═══════════════════════════════════════════════════════════════
    #  SECONDARY KPI STRIP — smaller, lower-priority breakdowns
    # ═══════════════════════════════════════════════════════════════

    def _build_kpi_secondary(self):
        row = ctk.CTkFrame(self.root, fg_color="transparent", height=88)
        row.pack(fill="x", padx=15, pady=(0, 6))
        row.pack_propagate(False)
        for col in range(5):
            row.grid_columnconfigure(col, weight=1, uniform="kpi_secondary")
        row.grid_rowconfigure(0, weight=1)

        def slim_card(col, title, unit_text, color):
            card = ctk.CTkFrame(row, fg_color=CARD_BG, corner_radius=10,
                                 border_width=1, border_color=CARD_BORDER)
            card.grid(row=0, column=col, sticky="nsew", padx=4)
            ctk.CTkLabel(card, text=title, font=F_KPI_SEC_TITLE,
                         text_color=T_SEC).pack(anchor="w", padx=12, pady=(8, 0))
            val = ctk.CTkLabel(card, text="0", font=F_KPI_SEC_VALUE, text_color=color)
            val.pack(anchor="w", padx=12)
            unit = ctk.CTkLabel(card, text=unit_text, font=F_KPI_SEC_UNIT, text_color=T_LIGHT)
            unit.pack(anchor="w", padx=12, pady=(0, 6))
            return card, val, unit

        self.priority_labels = {}
        self.priority_cards = {}
        c_high, self.priority_labels["High"], _ = slim_card(0, "High Priority", "switches", HERO_RED)
        c_med, self.priority_labels["Medium"], _ = slim_card(1, "Medium Priority", "switches", S_AMBER)
        c_low, self.priority_labels["Low"], _ = slim_card(2, "Low Priority", "switches", HERO_BLUE)
        self.priority_cards = {"High": c_high, "Medium": c_med, "Low": c_low}
        bind_click_recursive(c_high, lambda: self.set_priority_filter("High"))
        bind_click_recursive(c_med, lambda: self.set_priority_filter("Medium"))
        bind_click_recursive(c_low, lambda: self.set_priority_filter("Low"))
        _, self.kpi_scanning, _ = slim_card(3, "Scanning Now", "in progress", S_AMBER)

        c_timer, self.kpi_timer, self.kpi_timer_sub = slim_card(
            4, "Scan Engine", "seconds", S_AMBER)
        self.kpi_timer.configure(text=str(AUTO_SCAN_SECONDS))
        bind_click_recursive(c_timer, self.start_scan)

    # ═══════════════════════════════════════════════════════════════
    #  CONTROLS — Scan · Search · Sort · Progress
    # ═══════════════════════════════════════════════════════════════

    def _build_controls(self):
        strip = ctk.CTkFrame(self.root, fg_color="transparent")
        strip.pack(fill="x", padx=18, pady=(2, 6))

        self.btn_scan = ctk.CTkButton(strip, text="⚡  RUN SCAN", font=("Segoe UI", 10, "bold"),
                                       fg_color=HERO_RED, hover_color=HERO_RED_HOVER, height=30, width=140,
                                       corner_radius=8, command=self.start_scan)
        self.btn_scan.pack(side="left")

        self.entry_search = ctk.CTkEntry(strip, placeholder_text="🔍   Filter by location, model, or IP address…",
                                          width=360, height=30, corner_radius=8, fg_color=CARD_BG,
                                          border_color=CARD_BORDER, text_color=T_DARK,
                                          placeholder_text_color=T_LIGHT, font=("Segoe UI", 10))
        self.entry_search.pack(side="left", padx=10)
        self.entry_search.bind("<KeyRelease>", lambda _e: self.apply_filter())

        ctk.CTkLabel(strip, text="Sort:", font=("Segoe UI", 9), text_color=T_SEC).pack(side="left", padx=(6, 4))
        self.v_sort = ctk.StringVar(value=self.active_sort)
        self.opt_sort = ctk.CTkOptionMenu(strip, values=SORT_OPTIONS, variable=self.v_sort, width=120, height=30,
                                           command=lambda _v: self._on_sort_change())
        self.opt_sort.pack(side="left")

        self.lbl_pct = ctk.CTkLabel(strip, text="", font=("Segoe UI", 9), text_color=T_SEC)
        self.lbl_pct.pack(side="right", padx=(0, 4))

        self.progress = ctk.CTkProgressBar(strip, width=180, height=6, progress_color=HERO_RED,
                                            fg_color="#E0E0E0", corner_radius=3)
        self.progress.pack(side="right", padx=6, pady=8)
        self.progress.set(0)

    def _on_sort_change(self):
        self.active_sort = self.v_sort.get()
        self.apply_filter()

    # ═══════════════════════════════════════════════════════════════
    #  MIDDLE ROW — charts (each maximizable)
    # ═══════════════════════════════════════════════════════════════

    def _build_middle_row(self):
        mid = ctk.CTkFrame(self.root, fg_color="transparent", height=150)
        mid.pack(fill="x", padx=15, pady=(2, 3))
        mid.pack_propagate(False)

        p1, b1, _ = panel(mid, "All Nodes By Status", on_maximize=self._open_status_detail)
        p1.pack(side="left", fill="both", expand=True, padx=3)
        self.cv_bars = Canvas(b1, bg=CARD_BG, highlightthickness=0)
        self.cv_bars.pack(fill="both", expand=True, padx=4, pady=4)
        self.cv_bars.bind("<Configure>", self._schedule_redraw)

        p2, b2, _ = panel(mid, "Switch Model Distribution", on_maximize=self._open_model_detail)
        p2.pack(side="left", fill="both", expand=True, padx=3)
        self.cv_models = Canvas(b2, bg=CARD_BG, highlightthickness=0)
        self.cv_models.pack(fill="both", expand=True, padx=4, pady=4)
        self.cv_models.bind("<Configure>", self._schedule_redraw)

        p3_wrap = ctk.CTkFrame(mid, fg_color="transparent", width=260)
        p3_wrap.pack(side="left", fill="y", padx=3)
        p3_wrap.pack_propagate(False)
        p3, b3, _ = panel(p3_wrap, "Network Health", on_maximize=self._open_donut_detail)
        p3.pack(fill="both", expand=True)
        self.cv_donut = Canvas(b3, bg=CARD_BG, highlightthickness=0)
        self.cv_donut.pack(fill="both", expand=True, padx=4, pady=4)
        self.cv_donut.bind("<Configure>", self._schedule_redraw)

    # ═══════════════════════════════════════════════════════════════
    #  BOTTOM ROW — compact Switch Status Monitor (maximizable)
    # ═══════════════════════════════════════════════════════════════

    def _build_bottom_row(self):
        bot = ctk.CTkFrame(self.root, fg_color="transparent")
        bot.pack(fill="both", expand=True, padx=15, pady=(1, 2))

        pt, bt, _ = panel(bot, "Switch Status Monitor",
                           "All connected switches — priority-coded, live status",
                           on_maximize=self._open_switch_monitor_detail)
        pt.pack(fill="both", expand=True)

        wrap = ctk.CTkFrame(bt, fg_color=CARD_BG, corner_radius=12)
        wrap.pack(fill="both", expand=True, padx=6, pady=6)

        self.cv_switches = Canvas(wrap, bg=CARD_BG, highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.cv_switches.yview)
        self.cv_switches.configure(yscrollcommand=sb.set)
        self.cv_switches.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.cv_switches.bind("<Configure>", lambda _e: self.apply_filter())
        self.cv_switches.bind("<Enter>",
                               lambda _e: self.cv_switches.bind_all("<MouseWheel>", self._on_switch_scroll))
        self.cv_switches.bind("<Leave>", lambda _e: self.cv_switches.unbind_all("<MouseWheel>"))

    def _on_switch_scroll(self, event):
        self.cv_switches.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ═══════════════════════════════════════════════════════════════
    #  FOOTER
    # ═══════════════════════════════════════════════════════════════

    def _build_footer(self):
        ft = ctk.CTkFrame(self.root, height=26, corner_radius=0, fg_color=HERO_DARK)
        ft.pack(side="bottom", fill="x")
        ft.pack_propagate(False)

        self.ft_dot = ctk.CTkLabel(ft, text="●", font=("Segoe UI", 9), text_color=S_GREEN)
        self.ft_dot.pack(side="left", padx=(20, 4), pady=4)
        self.ft_status = ctk.CTkLabel(ft, text="NETRACK Engine: Ready", font=("Segoe UI", 9), text_color="#BDBDBD")
        self.ft_status.pack(side="left", pady=4)

        self.ft_warning = ctk.CTkLabel(ft, text="", font=("Segoe UI", 9, "bold"), text_color=S_AMBER)
        self.ft_warning.pack(side="left", padx=(14, 0), pady=4)

        self.ft_timer = ctk.CTkLabel(ft, text=f"Next scan: {AUTO_SCAN_SECONDS}s",
                                      font=("Consolas", 9, "bold"), text_color=S_AMBER)
        self.ft_timer.pack(side="right", padx=20, pady=4)
        self.ft_last = ctk.CTkLabel(ft, text="Last scan: —", font=("Segoe UI", 9), text_color="#9E9E9E")
        self.ft_last.pack(side="right", padx=(0, 14), pady=4)

    # ═══════════════════════════════════════════════════════════════
    #  CLOCK
    # ═══════════════════════════════════════════════════════════════

    def _tick_clock(self):
        now = datetime.now()
        self.lbl_clock.configure(text=now.strftime("%H:%M:%S"))
        self.lbl_date.configure(text=now.strftime("%A, %d %B %Y"))
        self.root.after(1000, self._tick_clock)

    # ═══════════════════════════════════════════════════════════════
    #  CSV TWO-WAY SYNC — pick up external edits to switches.csv
    # ═══════════════════════════════════════════════════════════════

    def _tick_csv_watch(self):
        try:
            mtime = os.path.getmtime(self.dm.csv_path)
        except OSError:
            mtime = None
        if mtime is not None and mtime != getattr(self, "_last_seen_mtime", None):
            self._last_seen_mtime = mtime
            if getattr(self, "_last_seen_mtime_init", False):
                self.dm.load()
                self._warn_on_bad_csv_rows()
                self.apply_filter()
                self.update_counters()
            self._last_seen_mtime_init = True
        self.root.after(4000, self._tick_csv_watch)

    # ═══════════════════════════════════════════════════════════════
    #  CRUD
    # ═══════════════════════════════════════════════════════════════

    def _open_manage_dialog(self):
        ManageSwitchesDialog(self.root, self.dm, on_change=self._on_data_changed)

    def _open_switch_editor(self, ip):
        sw = next((s for s in self.dm.switches if s["IP"] == ip), None)
        if not sw:
            return

        def submit(orig_ip, loc, model, new_ip, priority):
            self.dm.update_switch(orig_ip, loc, model, new_ip, priority)
            self._on_data_changed()
        SwitchFormDialog(self.root, title="Edit Switch", initial=sw, on_submit=submit)

    def _on_data_changed(self):
        self._last_seen_mtime = os.path.getmtime(self.dm.csv_path)
        self.apply_filter()
        self.update_counters()

    # ═══════════════════════════════════════════════════════════════
    #  FILTERING / SORTING / DISPLAY
    # ═══════════════════════════════════════════════════════════════

    def set_status_filter(self, kind):
        self.active_status_filter = kind
        if kind == "ALL":
            # "Total Switches" doubles as the global reset: clear any active
            # priority-tier filter too, so it behaves as a full reset.
            self.active_priority_filter = "ALL"
            self._refresh_priority_card_highlight()
        self.apply_filter()

        colors = {"ALL": PANEL_GREEN, "ONLINE": S_GREEN, "OFFLINE": S_RED, "CRITICAL": HERO_RED}
        for k, card in self.kpi_cards.items():
            if k == kind:
                card.configure(border_color=colors.get(k, PANEL_GREEN), border_width=2)
            else:
                card.configure(border_color=CARD_BORDER, border_width=1)

    def set_priority_filter(self, level):
        # Toggle: clicking the already-active priority tier resets to ALL.
        self.active_priority_filter = "ALL" if self.active_priority_filter == level else level
        self._refresh_priority_card_highlight()
        self.apply_filter()

    def _refresh_priority_card_highlight(self):
        colors = {"High": HERO_RED, "Medium": S_AMBER, "Low": HERO_BLUE}
        for level, card in self.priority_cards.items():
            if level == self.active_priority_filter:
                card.configure(border_color=colors.get(level, PANEL_GREEN), border_width=2)
            else:
                card.configure(border_color=CARD_BORDER, border_width=1)

    def apply_filter(self):
        switches, status_map = self.dm.snapshot()
        q = self.entry_search.get() if hasattr(self, "entry_search") else ""
        self.switch_monitor.draw(switches, status_map, search_query=q,
                                  status_filter=self.active_status_filter,
                                  priority_filter=self.active_priority_filter,
                                  sort_by=self.active_sort)

    def update_counters(self):
        switches, status_map = self.dm.snapshot()
        total = len(switches)
        on, off, chk, pnd = charts.status_counts(status_map)
        pct = round(on / total * 100, 1) if total else 0

        priority_counts = {"High": 0, "Medium": 0, "Low": 0}
        critical_down = 0
        for sw in switches:
            priority = sw.get("Priority", "Medium")
            if priority in priority_counts:
                priority_counts[priority] += 1
            if priority == "High" and status_map.get(sw["IP"], {}).get("status") == "✖ OFFLINE":
                critical_down += 1

        # ── Primary KPIs (large) — every .configure below is a no-op if
        # the value hasn't actually changed since the last tick, which is
        # what keeps this from visibly flashing on every refresh.
        n_models = len({sw["Model"] for sw in switches})
        self._set_text("kpi_total", self.kpi_total, str(total))
        self._set_text("kpi_total_sub", self.kpi_total_sub,
                        f"{n_models} model{'s' if n_models != 1 else ''}" if switches else "no switches configured")

        self._set_text("kpi_online", self.kpi_online_big, str(on))
        self._set_text("kpi_online_sub", self.kpi_online_sub,
                        f"{(on / total * 100):.0f}% of total" if total else "—")

        self._set_text("kpi_offline", self.kpi_offline_big, str(off))
        self._set_text("kpi_offline_sub", self.kpi_offline_sub,
                        "1 incident" if off == 1 else f"{off} incidents")

        pct_display = str(int(pct)) if pct == int(pct) else str(pct)
        avail_col = S_GREEN if pct >= 80 else S_AMBER if pct >= 50 else S_RED
        self._set_text("kpi_avail", self.kpi_avail, pct_display, text_color=avail_col)

        crit_col = HERO_RED if critical_down else S_GREEN
        self._set_text("kpi_critical", self.kpi_critical, str(critical_down), text_color=crit_col)
        self._set_text("kpi_critical_sub", self.kpi_critical_sub,
                        "all clear" if critical_down == 0
                        else ("1 node" if critical_down == 1 else f"{critical_down} nodes"))

        # ── Secondary KPIs (small) ──────────────────────────────────
        for level, label in self.priority_labels.items():
            self._set_text(f"priority_{level}", label, str(priority_counts.get(level, 0)))
        self._priority_summary = priority_counts

        self._set_text("kpi_scanning", self.kpi_scanning, str(chk))

        self._redraw_charts()

    # ═══════════════════════════════════════════════════════════════
    #  CHART DRAWING (compact, docked)
    # ═══════════════════════════════════════════════════════════════

    def _schedule_redraw(self, _event=None):
        if self._redraw_job:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(80, self._redraw_charts)

    def _redraw_charts(self):
        switches, status_map = self.dm.snapshot()
        charts.draw_status_bars(self.cv_bars, status_map)
        charts.draw_model_bars(self.cv_models, switches)
        charts.draw_donut(self.cv_donut, switches, status_map)
        self.apply_filter()

    # ═══════════════════════════════════════════════════════════════
    #  MAXIMIZE / DETAIL WINDOWS
    # ═══════════════════════════════════════════════════════════════

    def _open_status_detail(self):
        def draw(canvas):
            _s, status_map = self.dm.snapshot()
            charts.draw_status_bars(canvas, status_map, big=True)

        def rows():
            _s, status_map = self.dm.snapshot()
            on, off, chk, pnd = charts.status_counts(status_map)
            total = max(on + off + chk + pnd, 1)
            return [
                ("Online", on, f"{on / total * 100:.1f}%"),
                ("Offline", off, f"{off / total * 100:.1f}%"),
                ("Scanning", chk, f"{chk / total * 100:.1f}%"),
                ("Pending", pnd, f"{pnd / total * 100:.1f}%"),
            ]

        DetailWindow(self.root, "All Nodes By Status", draw,
                     table_columns=("Status", "Count", "Share"), get_rows=rows)

    def _open_model_detail(self):
        def draw(canvas):
            switches, _s = self.dm.snapshot()
            charts.draw_model_bars(canvas, switches, big=True)

        def rows():
            from collections import Counter
            switches, _s = self.dm.snapshot()
            counts = Counter(sw["Model"] for sw in switches).most_common()
            total = max(len(switches), 1)
            return [(m, c, f"{c / total * 100:.1f}%") for m, c in counts]

        DetailWindow(self.root, "Switch Model Distribution", draw,
                     table_columns=("Model", "Count", "Share"), get_rows=rows)

    def _open_donut_detail(self):
        def draw(canvas):
            switches, status_map = self.dm.snapshot()
            charts.draw_donut(canvas, switches, status_map, big=True)

        def rows():
            switches, status_map = self.dm.snapshot()
            on, off, chk, pnd = charts.status_counts(status_map)
            total = max(len(switches), 1)
            return [
                ("Online", on, f"{on / total * 100:.1f}%"),
                ("Offline", off, f"{off / total * 100:.1f}%"),
                ("Pending / Scanning", chk + pnd, f"{(chk + pnd) / total * 100:.1f}%"),
            ]

        DetailWindow(self.root, "Network Health", draw,
                     table_columns=("Segment", "Count", "Share"), get_rows=rows)

    def _open_switch_monitor_detail(self):
        big_monitor_holder = {}

        def draw(canvas):
            switches, status_map = self.dm.snapshot()
            charts.draw_priority_breakdown(canvas, switches, status_map, big=True)

        def rows():
            switches, status_map = self.dm.snapshot()
            out = []
            for sw in sorted(switches, key=lambda s: (
                    {"High": 0, "Medium": 1, "Low": 2}.get(s.get("Priority", "Medium"), 1),
                    s["Location"].lower())):
                st = status_map.get(sw["IP"], {"status": "Pending"})
                out.append((sw["Location"], sw["Model"], sw["IP"], sw.get("Priority", "Medium"), st["status"]))
            return out

        DetailWindow(self.root, "Switch Status Monitor — by OT Priority", draw,
                     table_columns=("Location", "Model", "IP", "Priority", "Status"), get_rows=rows)

    # ═══════════════════════════════════════════════════════════════
    #  NETWORK SCANNING
    # ═══════════════════════════════════════════════════════════════

    def start_scan(self):
        if self.is_scanning:
            return
        self.is_scanning = True
        self.processed_pings = 0
        self.progress.set(0)
        self.btn_scan.configure(state="disabled", fg_color="#BDBDBD", text_color=T_SEC, text="⏳  SCANNING…")
        self.ft_status.configure(text="NETRACK Engine: Running async ping sweep…", text_color=S_AMBER)
        self.ft_dot.configure(text_color=S_AMBER)

        total = max(len(self.dm.switches), 1)

        def on_progress(processed, total_n):
            total_n = max(total_n, 1)
            p = processed / total_n
            pct_int = int(p * 100)

            def _update():
                # Skip the widget update entirely if the percentage hasn't
                # moved since the last tick — cheap, but every skipped
                # .configure() is one less repaint.
                if self._last_widget_state.get("progress_pct") == pct_int:
                    return
                self._last_widget_state["progress_pct"] = pct_int
                self.progress.set(p)
                self.lbl_pct.configure(text=f"{pct_int}%")
            self.root.after(0, _update)

        def on_switch_done(_ip):
            # Ping results can land dozens of times a second across the
            # thread pool. Rather than redrawing the whole switch grid and
            # all three charts on every single one (the old behaviour —
            # and the cause of the visible flicker during a scan), this
            # just raises a flag; _tick_ui_refresh() flushes it on a fixed
            # ~250ms cadence so the screen updates in smooth batches.
            self._refresh_pending = True

        def on_complete(ts):
            def _done():
                self.ft_status.configure(text=f"NETRACK Engine: Sweep complete — "
                                               f"{len(self.dm.switches)} nodes validated", text_color=S_GREEN)
                self.ft_dot.configure(text_color=S_GREEN)
                self.ft_last.configure(text=f"Last scan: {ts.strftime('%H:%M:%S')}")
                self.btn_scan.configure(state="normal", fg_color=HERO_RED, text_color=T_WHITE, text="⚡  RUN SCAN")
                self.lbl_pct.configure(text="")
                self.is_scanning = False
                self.countdown_seconds = AUTO_SCAN_SECONDS
                # One guaranteed full refresh at the end, bypassing the
                # signature/change-detection caches, so the final state is
                # always exactly correct even if the last coalesced tick
                # landed a moment before the very last ping resolved.
                self._refresh_pending = False
                self.apply_filter()
                self.update_counters()
            self.root.after(0, _done)

        self.scanner.run_sweep_async(on_progress=on_progress, on_switch_done=on_switch_done,
                                      on_complete=on_complete)

    # ═══════════════════════════════════════════════════════════════
    #  COALESCED UI REFRESH  (batches rapid scan callbacks; kills flicker)
    # ═══════════════════════════════════════════════════════════════

    def _tick_ui_refresh(self):
        if self._refresh_pending:
            self._refresh_pending = False
            self.update_counters()   # cascades into apply_filter() + chart redraw
        self.root.after(UI_REFRESH_THROTTLE_MS, self._tick_ui_refresh)

    # ═══════════════════════════════════════════════════════════════
    #  AUTO-SCAN TIMER
    # ═══════════════════════════════════════════════════════════════

    def _tick_auto_scan(self):
        if self.is_scanning:
            self._set_text("ft_timer", self.ft_timer, "⏳ Scanning…", text_color=S_AMBER)
            self._set_text("kpi_timer", self.kpi_timer, "⏳", text_color=S_AMBER)
            self._set_text("kpi_timer_sub", self.kpi_timer_sub, "scanning")
        else:
            col = S_AMBER if self.countdown_seconds > 5 else HERO_RED
            self._set_text("ft_timer", self.ft_timer, f"Next scan: {self.countdown_seconds}s", text_color=col)
            self._set_text("kpi_timer", self.kpi_timer, str(self.countdown_seconds), text_color=col)
            self._set_text("kpi_timer_sub", self.kpi_timer_sub, "seconds")
            self.countdown_seconds -= 1
            if self.countdown_seconds < 0:
                self.start_scan()

        self.root.after(1000, self._tick_auto_scan)
