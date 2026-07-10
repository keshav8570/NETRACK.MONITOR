"""
NETRACK — Switch Status Monitor.

Compact grid of per-switch status bars. Each row is colour-accented by OT
Priority (High/Medium/Low) on the left edge, with the live Online/Offline
pill on the right — so criticality and health are both visible at a glance.
Supports search, status filter, and sorting; the canvas is fully responsive
(recomputes columns on resize) and doubles as the compact "minimized" view
that expands via the panel's maximize button.
"""

from tkinter import Canvas

from .config import (
    CARD_BG, CARD_BORDER, T_DARK, T_SEC, T_LIGHT, PRIORITY_COLORS, STATUS_COLOR_MAP,
)

SORT_KEYS = {
    "Location": lambda sw, st: sw["Location"].lower(),
    "Model": lambda sw, st: sw["Model"].lower(),
    "IP": lambda sw, st: tuple(int(p) for p in sw["IP"].split(".")) if sw["IP"].count(".") == 3 and all(p.isdigit() for p in sw["IP"].split(".")) else sw["IP"],
    "Priority": lambda sw, st: {"High": 0, "Medium": 1, "Low": 2}.get(sw.get("Priority", "Medium"), 1),
    "Status": lambda sw, st: {"online": 0, "checking": 1, "pending": 2, "offline": 3}.get(st.get("tag", "pending"), 2),
}


class SwitchMonitor:
    """Compact, responsive canvas grid of switch status bars."""

    ROW_H_COMPACT = 42
    ROW_H_BIG = 60
    ROW_GAP = 8
    COL_MIN_COMPACT = 280
    COL_MIN_BIG = 400
    COL_GAP = 10

    def __init__(self, canvas: Canvas, compact=True):
        self.canvas = canvas
        self.compact = compact
        self.on_row_click = None
        self._last_signature = None

    def draw(self, switches, status_map, search_query="", status_filter="ALL",
              priority_filter="ALL", sort_by="Priority", force=False):
        c = self.canvas
        w = c.winfo_width()
        if w < 40:
            return

        q = (search_query or "").lower().strip()
        rows = []
        for sw in switches:
            loc, mod, ip = sw["Location"], sw["Model"], sw["IP"]
            st = status_map.get(ip, {"status": "Pending", "tag": "pending"})

            if status_filter == "ONLINE" and st["status"] != "● ONLINE":
                continue
            if status_filter == "OFFLINE" and st["status"] != "✖ OFFLINE":
                continue
            if status_filter == "CRITICAL" and not (
                    sw.get("Priority") == "High" and st["status"] == "✖ OFFLINE"):
                continue
            if priority_filter != "ALL" and sw.get("Priority") != priority_filter:
                continue
            if q and q not in loc.lower() and q not in mod.lower() and q not in ip.lower():
                continue
            rows.append((sw, st))

        key_fn = SORT_KEYS.get(sort_by, SORT_KEYS["Priority"])
        rows.sort(key=lambda pair: key_fn(pair[0], pair[1]))

        # Skip the clear-and-redraw entirely when nothing visible changed —
        # this is the main source of the flicker during a fast scan sweep,
        # since previously every single ping result triggered a full
        # delete("all") + redraw of every row on screen.
        signature = (
            w, self.compact, status_filter, priority_filter, sort_by, q,
            tuple((sw["IP"], sw["Location"], sw["Model"], sw["Priority"], st["tag"])
                  for sw, st in rows),
        )
        if not force and signature == self._last_signature:
            return
        self._last_signature = signature

        c.delete("all")
        self._rows = rows  # keep for click hit-testing

        if not rows:
            c.create_text(w // 2, 40, text="No switches match the current filter",
                           font=("Segoe UI", 10), fill=T_LIGHT)
            c.configure(scrollregion=(0, 0, w, 80))
            return

        row_h = self.ROW_H_BIG if not self.compact else self.ROW_H_COMPACT
        col_min = self.COL_MIN_BIG if not self.compact else self.COL_MIN_COMPACT
        ncols = max(1, int(w // (col_min + self.COL_GAP)))
        col_w = (w - self.COL_GAP * (ncols + 1)) / ncols

        self._layout = {"ncols": ncols, "col_w": col_w, "row_h": row_h}

        for i, (sw, st) in enumerate(rows):
            loc, mod, ip = sw["Location"], sw["Model"], sw["IP"]
            priority = sw.get("Priority", "Medium")
            pr_color, pr_bg, pr_txt = PRIORITY_COLORS.get(priority, PRIORITY_COLORS["Medium"])
            _, status_bg, status_txt = STATUS_COLOR_MAP.get(st["tag"], STATUS_COLOR_MAP["pending"])

            col = i % ncols
            row = i // ncols
            x0 = self.COL_GAP + col * (col_w + self.COL_GAP)
            y0 = self.ROW_GAP + row * (row_h + self.ROW_GAP)
            x1, y1 = x0 + col_w, y0 + row_h

            c.create_rectangle(x0, y0, x1, y1, fill=status_bg, outline=CARD_BORDER,
                                tags=("row", f"row{i}"))
            # Priority accent strip (left edge)
            c.create_rectangle(x0, y0, x0 + 5, y1, fill=pr_color, outline="",
                                tags=("row", f"row{i}"))

            if self.compact:
                c.create_text(x0 + 12, y0 + row_h * 0.30,
                               text=f"{loc}", font=("Segoe UI", 9, "bold"),
                               fill=T_DARK, anchor="w", tags=("row", f"row{i}"))
                c.create_text(x0 + 12, y0 + row_h * 0.68,
                               text=f"{mod}  ·  {ip}", font=("Segoe UI", 7),
                               fill=T_SEC, anchor="w", tags=("row", f"row{i}"))
                c.create_text(x1 - 8, y0 + row_h * 0.30, text=st["status"],
                               font=("Segoe UI", 8, "bold"), fill=status_txt,
                               anchor="e", tags=("row", f"row{i}"))
                c.create_text(x1 - 8, y0 + row_h * 0.68, text=priority,
                               font=("Segoe UI", 7, "bold"), fill=pr_txt,
                               anchor="e", tags=("row", f"row{i}"))
            else:
                c.create_text(x0 + 16, y0 + 16,
                               text=f"{loc}", font=("Segoe UI", 10, "bold"),
                               fill=T_DARK, anchor="w", tags=("row", f"row{i}"))
                c.create_text(x0 + 16, y0 + 38,
                               text=f"{mod}  ·  {ip}", font=("Segoe UI", 9),
                               fill=T_SEC, anchor="w", tags=("row", f"row{i}"))
                c.create_text(x1 - 14, y0 + 18, text=st["status"],
                               font=("Segoe UI", 10, "bold"), fill=status_txt, anchor="e",
                               tags=("row", f"row{i}"))
                c.create_text(x1 - 14, y0 + 40, text=f"{priority} priority",
                               font=("Segoe UI", 8, "bold"), fill=pr_txt, anchor="e",
                               tags=("row", f"row{i}"))

        n_rows = -(-len(rows) // ncols)
        total_h = self.ROW_GAP + n_rows * (row_h + self.ROW_GAP)
        c.configure(scrollregion=(0, 0, w, max(total_h, c.winfo_height())))

        c.tag_bind("row", "<Button-1>", self._handle_click)

    def _handle_click(self, event):
        if not self.on_row_click or not getattr(self, "_rows", None):
            return
        item = self.canvas.find_closest(event.x, event.y)
        if not item:
            return
        tags = self.canvas.gettags(item[0])
        idx_tag = next((t for t in tags if t.startswith("row") and t != "row"), None)
        if not idx_tag:
            return
        try:
            idx = int(idx_tag[3:])
        except ValueError:
            return
        if 0 <= idx < len(self._rows):
            sw, _st = self._rows[idx]
            self.on_row_click(sw["IP"])
