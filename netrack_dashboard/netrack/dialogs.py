"""
NETRACK — Dialog windows.

  * SwitchFormDialog   — Add / Edit a single switch (modal form).
  * ManageSwitchesDialog — full CRUD table (list, add, edit, delete), backed
    live by DataManager so every change is written straight to switches.csv.
  * DetailWindow        — generic "maximize" popup: a bigger chart plus a
    sortable data table, used by every widget's ⛶ button.
"""

from tkinter import ttk, messagebox, Canvas

import customtkinter as ctk

from .config import (
    CARD_BG, CARD_BORDER, HERO_RED, HERO_RED_HOVER, T_DARK, T_SEC, T_WHITE,
    PRIORITIES, BG_PAGE, S_RED, S_GREEN, PRIORITY_COLORS,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Add / Edit switch form
# ═══════════════════════════════════════════════════════════════════════════

class SwitchFormDialog(ctk.CTkToplevel):
    def __init__(self, parent, title="Add Switch", initial=None, on_submit=None):
        super().__init__(parent)
        self.title(title)
        self.geometry("380x340")
        self.resizable(False, False)
        self.configure(fg_color=BG_PAGE)
        self.on_submit = on_submit
        self.original_ip = initial["IP"] if initial else None
        self.grab_set()

        pad = {"padx": 16, "pady": (10, 2)}

        ctk.CTkLabel(self, text=title, font=("Segoe UI", 13, "bold")).pack(pady=(14, 6))

        ctk.CTkLabel(self, text="Location", font=("Segoe UI", 9), anchor="w").pack(fill="x", **pad)
        self.e_loc = ctk.CTkEntry(self, height=30)
        self.e_loc.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="Model", font=("Segoe UI", 9), anchor="w").pack(fill="x", **pad)
        self.e_model = ctk.CTkEntry(self, height=30)
        self.e_model.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="IP Address", font=("Segoe UI", 9), anchor="w").pack(fill="x", **pad)
        self.e_ip = ctk.CTkEntry(self, height=30)
        self.e_ip.pack(fill="x", padx=16)

        ctk.CTkLabel(self, text="OT Priority", font=("Segoe UI", 9), anchor="w").pack(fill="x", **pad)
        self.v_priority = ctk.StringVar(value=initial["Priority"] if initial else "Medium")
        self.opt_priority = ctk.CTkOptionMenu(self, values=PRIORITIES, variable=self.v_priority)
        self.opt_priority.pack(fill="x", padx=16)

        if initial:
            self.e_loc.insert(0, initial["Location"])
            self.e_model.insert(0, initial["Model"])
            self.e_ip.insert(0, initial["IP"])

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=18)
        ctk.CTkButton(btn_row, text="Cancel", fg_color="#BDBDBD", hover_color="#9E9E9E",
                      text_color=T_DARK, command=self.destroy).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(btn_row, text="Save", fg_color=HERO_RED, hover_color=HERO_RED_HOVER,
                      command=self._submit).pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _submit(self):
        loc = self.e_loc.get().strip()
        model = self.e_model.get().strip()
        ip = self.e_ip.get().strip()
        priority = self.v_priority.get()

        if not loc or not model or not ip:
            messagebox.showerror("Missing fields", "Location, Model, and IP are all required.", parent=self)
            return
        parts = ip.split(".")
        if len(parts) != 4 or not all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
            messagebox.showerror("Invalid IP", f"'{ip}' is not a valid IPv4 address.", parent=self)
            return

        if self.on_submit:
            try:
                self.on_submit(self.original_ip, loc, model, ip, priority)
            except ValueError as e:
                messagebox.showerror("Save failed", str(e), parent=self)
                return
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════
#  Manage switches — full CRUD table
# ═══════════════════════════════════════════════════════════════════════════

class ManageSwitchesDialog(ctk.CTkToplevel):
    def __init__(self, parent, data_manager, on_change=None):
        super().__init__(parent)
        self.title("Manage Switches — NETRACK")
        self.geometry("760x480")
        self.configure(fg_color=BG_PAGE)
        self.dm = data_manager
        self.on_change = on_change
        self.grab_set()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 6))
        ctk.CTkLabel(top, text="Switch Inventory (CRUD)", font=("Segoe UI", 13, "bold")).pack(side="left")
        ctk.CTkButton(top, text="+ Add Switch", fg_color=HERO_RED, hover_color=HERO_RED_HOVER,
                      width=120, command=self._add).pack(side="right")

        table_wrap = ctk.CTkFrame(self, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER)
        table_wrap.pack(fill="both", expand=True, padx=14, pady=6)

        cols = ("Location", "Model", "IP", "Critical Level", "Status")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=14)
        for col, w in zip(cols, (220, 170, 130, 110, 110)):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.tag_configure("high", foreground=PRIORITY_COLORS["High"][2], background="#FFF5F5")
        self.tree.tag_configure("medium", foreground=PRIORITY_COLORS["Medium"][2], background="#FFF9F0")
        self.tree.tag_configure("low", foreground=PRIORITY_COLORS["Low"][2], background="#F2F8FF")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 14))
        ctk.CTkButton(btn_row, text="Delete Selected", command=self._delete,
                      fg_color=S_RED, hover_color="#C62828").pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="Close", command=self.destroy,
                      fg_color="#BDBDBD", hover_color="#9E9E9E", text_color=T_DARK).pack(side="right")

        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        switches, status_map = self.dm.snapshot()
        for sw in sorted(switches, key=lambda s: s["Location"].lower()):
            st = status_map.get(sw["IP"], {"status": "Pending"})
            priority = sw.get("Priority", "Medium")
            tag = priority.lower()
            self.tree.insert("", "end", iid=sw["IP"],
                              values=(sw["Location"], sw["Model"], sw["IP"], priority, st["status"]),
                              tags=(tag,))

    def _selected_ip(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _add(self):
        def submit(_orig_ip, loc, model, ip, priority):
            self.dm.add_switch(loc, model, ip, priority)
            self.refresh()
            if self.on_change:
                self.on_change()
        SwitchFormDialog(self, title="Add Switch", on_submit=submit)

    def _edit(self):
        ip = self._selected_ip()
        if not ip:
            messagebox.showinfo("Select a switch", "Choose a row first.", parent=self)
            return
        sw = next((s for s in self.dm.switches if s["IP"] == ip), None)
        if not sw:
            return

        def submit(orig_ip, loc, model, new_ip, priority):
            self.dm.update_switch(orig_ip, loc, model, new_ip, priority)
            self.refresh()
            if self.on_change:
                self.on_change()
        SwitchFormDialog(self, title="Edit Switch", initial=sw, on_submit=submit)

    def _delete(self):
        ip = self._selected_ip()
        if not ip:
            messagebox.showinfo("Select a switch", "Choose a row first.", parent=self)
            return
        if messagebox.askyesno("Confirm delete", f"Remove switch {ip} from inventory?", parent=self):
            self.dm.delete_switch(ip)
            self.refresh()
            if self.on_change:
                self.on_change()


# ═══════════════════════════════════════════════════════════════════════════
#  Maximize / detail analytics window
# ═══════════════════════════════════════════════════════════════════════════

class DetailWindow(ctk.CTkToplevel):
    """Generic maximized view: a large chart at top, an optional sortable
    data table below, and live auto-refresh while open."""

    def __init__(self, parent, title, draw_fn, table_columns=None, get_rows=None,
                 refresh_ms=2000):
        super().__init__(parent)
        self.title(f"{title} — Detail View")
        self.geometry("1120x760")
        self.configure(fg_color=BG_PAGE)
        self.draw_fn = draw_fn
        self.get_rows = get_rows
        self.refresh_ms = refresh_ms
        self._closed = False

        hdr = ctk.CTkFrame(self, fg_color="#1B1B1B", height=40, corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f"  {title} — Detailed Analytics", font=("Segoe UI", 13, "bold"),
                     text_color=T_WHITE).pack(side="left", padx=14)
        ctk.CTkButton(hdr, text="Minimize ▾", width=110, fg_color=HERO_RED, hover_color=HERO_RED_HOVER,
                      command=self.destroy).pack(side="right", padx=14, pady=6)

        chart_wrap = ctk.CTkFrame(self, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER,
                                   height=430)
        chart_wrap.pack(fill="x", padx=14, pady=(12, 6))
        chart_wrap.pack_propagate(False)
        self.canvas = Canvas(chart_wrap, bg=CARD_BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)
        self.canvas.bind("<Configure>", lambda _e: self._safe_draw())

        if table_columns and get_rows:
            table_wrap = ctk.CTkFrame(self, fg_color=CARD_BG, border_width=1, border_color=CARD_BORDER)
            table_wrap.pack(fill="both", expand=True, padx=14, pady=(6, 14))
            self.tree = ttk.Treeview(table_wrap, columns=table_columns, show="headings")
            for col in table_columns:
                self.tree.heading(col, text=col, command=lambda c=col: self._sort_table(c))
                self.tree.column(col, width=140, anchor="w")
            self.tree.tag_configure("high", foreground=PRIORITY_COLORS["High"][2], background="#FFF5F5")
            self.tree.tag_configure("medium", foreground=PRIORITY_COLORS["Medium"][2], background="#FFF9F0")
            self.tree.tag_configure("low", foreground=PRIORITY_COLORS["Low"][2], background="#F2F8FF")
            self.tree.pack(side="left", fill="both", expand=True)
            sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            self._sort_state = {"col": "Critical Level", "reverse": False}
            self._refresh_table()
        else:
            self.tree = None

        self.protocol("WM_DELETE_WINDOW", self._close)
        try:
            self.state("zoomed")
        except Exception:
            pass
        self._tick()

    def _safe_draw(self):
        try:
            self.draw_fn(self.canvas)
        except Exception:
            pass

    def _refresh_table(self):
        if not self.tree or not self.get_rows:
            return
        rows = self.get_rows()
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            tag = ""
            if len(r) > 3 and isinstance(r[3], str) and r[3].lower() in {"high", "medium", "low"}:
                tag = r[3].lower()
            self.tree.insert("", "end", values=r, tags=(tag,) if tag else ())

    def _sort_table(self, col):
        state = self._sort_state
        reverse = (state["col"] == col) and not state["reverse"]
        rows = self.get_rows()
        idx = list(self.tree["columns"]).index(col)

        def sort_key(row):
            val = row[idx]
            if col == "Critical Level":
                return {"High": 0, "Medium": 1, "Low": 2}.get(str(val), 99)
            try:
                return float(val)
            except (ValueError, TypeError):
                return str(val).lower()

        rows = sorted(rows, key=sort_key, reverse=reverse)
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            tag = ""
            if len(r) > 3 and isinstance(r[3], str) and r[3].lower() in {"high", "medium", "low"}:
                tag = r[3].lower()
            self.tree.insert("", "end", values=r, tags=(tag,) if tag else ())
        state["col"], state["reverse"] = col, reverse

    def _tick(self):
        if self._closed:
            return
        self._safe_draw()
        self._refresh_table()
        self.after(self.refresh_ms, self._tick)

    def _close(self):
        self._closed = True
        self.destroy()
