"""
NETRACK — Chart rendering.

Every function draws onto a given Canvas at whatever size it currently is.
Because size is read from the canvas itself, the exact same function powers
the small in-dashboard chart and the enlarged maximize/detail view.
"""

from collections import Counter

from .config import (
    S_GREEN, S_RED, S_YELLOW, T_DARK, T_BODY, T_SEC, T_LIGHT, CARD_BG, CHART_PAL,
)


def _fit_label(text, max_chars):
    """Truncate long switch-model names with an ellipsis instead of letting
    them overflow into the chart area or get silently clipped by Tk."""
    if len(text) <= max_chars:
        return text
    return text[: max(1, max_chars - 1)] + "…"


def status_counts(status_map):
    on  = sum(1 for s in status_map.values() if s["status"] == "● ONLINE")
    off = sum(1 for s in status_map.values() if s["status"] == "✖ OFFLINE")
    chk = sum(1 for s in status_map.values() if "Scanning" in s["status"])
    pnd = sum(1 for s in status_map.values() if s["status"] == "Pending")
    return on, off, chk, pnd


def draw_status_bars(canvas, status_map, big=False):
    """Vertical bar chart: Online / Offline / Scanning / Pending."""
    c = canvas
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    if w < 80 or h < 60:
        return

    on, off, chk, pnd = status_counts(status_map)
    raw = [("Online", on, S_GREEN), ("Offline", off, S_RED),
           ("Scanning", chk, S_YELLOW), ("Pending", pnd, "#BDBDBD")]
    data = [(n, v, cl) for n, v, cl in raw if v > 0]

    if not data:
        c.create_text(w // 2, h // 2, text="Awaiting scan…",
                       font=("Segoe UI", 11), fill=T_LIGHT)
        return

    mx = max(v for _, v, _ in data) or 1
    ml, mr = 48, (120 if big else 108)
    mt, mb = (32 if big else 22), (60 if big else 52)
    cw, ch_ = w - ml - mr, h - mt - mb
    n = len(data)
    bw = min(90 if big else 54, cw // max(n * 2, 1))
    gap = (cw - bw * n) // max(n + 1, 1)

    for i in range(5):
        y = mt + ch_ - (i / 4) * ch_
        val = int(mx * i / 4)
        c.create_line(ml, y, ml + cw, y, fill="#EEEEEE")
        c.create_text(ml - 6, y, text=str(val),
                       font=("Segoe UI", 9 if big else 8), fill=T_LIGHT, anchor="e")

    for i, (name, val, color) in enumerate(data):
        x = ml + gap + i * (bw + gap)
        bh = (val / mx) * ch_
        y1, y2 = mt + ch_ - bh, mt + ch_
        c.create_rectangle(x, y1, x + bw, y2, fill=color, outline="")
        c.create_text(x + bw // 2, y1 - (12 if big else 8), text=str(val),
                       font=("Segoe UI", 13 if big else 10, "bold"), fill=T_DARK)
        c.create_text(x + bw // 2, y2 + (18 if big else 14), text=name,
                       font=("Segoe UI", 11 if big else 9), fill=T_SEC)

    lx = ml + cw + 12
    for i, (name, val, color) in enumerate(raw):
        ly = mt + 4 + i * (24 if big else 20)
        sz = 16 if big else 14
        c.create_rectangle(lx, ly, lx + sz, ly + sz - 2, fill=color, outline="")
        c.create_text(lx + sz + 4, ly + sz // 2 - 1, text=f"{val}  {name}",
                       font=("Segoe UI", 10 if big else 8), fill=T_BODY, anchor="w")


def draw_model_bars(canvas, switches, big=False):
    """Horizontal bars: switch count per model.

    Label margin is sized from the actual longest label (in the visible
    set) instead of a fixed guess, so real model names like
    'C9300L-48T-4X-E' never get clipped or run into the bars. When there
    are more distinct models than the compact card can show, the long tail
    is folded into an 'Other' bucket rather than silently disappearing.
    """
    c = canvas
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    if w < 80 or h < 60:
        return

    if not switches:
        c.create_text(w // 2, h // 2, text="No switches configured",
                       font=("Segoe UI", 11), fill=T_LIGHT)
        return

    counts = Counter(sw["Model"] for sw in switches).most_common()

    mt, mb = 12, 12
    ch_avail = h - mt - mb
    max_bh = 30 if big else 22
    min_bh = 14
    max_rows = max(1, ch_avail // (min_bh + 3))

    if not big and len(counts) > max_rows:
        head = counts[: max_rows - 1]
        other_count = sum(c_ for _, c_ in counts[max_rows - 1:])
        counts = head + [("Other models", other_count)]

    n = len(counts)
    mx = counts[0][1] if counts else 1

    # Dynamic left margin: fit the longest visible label at this font size
    # (~6.2px/char at size 9, ~6.8px/char at size 10) plus fixed padding.
    font_size = 10 if big else 9
    char_w = 6.8 if big else 6.2
    max_label_chars = max((len(m) for m, _ in counts), default=10)
    ml = min(int(w * 0.45), max(90, int(max_label_chars * char_w) + 16))
    max_label_chars_fit = max(6, int((ml - 16) / char_w))
    mr = 56 if big else 44

    cw = max(10, w - ml - mr)
    ch_ = ch_avail
    bh = min(max_bh, max(min_bh, (ch_ - 8) // max(n, 1)))
    gap = max(3, (ch_ - bh * n) // max(n + 1, 1))

    for i, (model, cnt) in enumerate(counts):
        y = mt + gap + i * (bh + gap)
        bar_w = (cnt / mx) * cw if mx > 0 else 0
        color = CHART_PAL[i % len(CHART_PAL)]

        c.create_rectangle(ml, y, ml + bar_w, y + bh, fill=color, outline="")
        disp = _fit_label(model, max_label_chars_fit)
        c.create_text(ml - 8, y + bh // 2, text=disp,
                       font=("Segoe UI", font_size), fill=T_BODY, anchor="e")
        c.create_text(ml + bar_w + 8, y + bh // 2, text=str(cnt),
                       font=("Segoe UI", font_size + 1, "bold"), fill=T_DARK, anchor="w")


def draw_donut(canvas, switches, status_map, big=False):
    """Donut chart: Online / Offline / Pending."""
    c = canvas
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    if w < 80 or h < 80:
        return

    on, off, chk, pnd = status_counts(status_map)
    # Anything configured but not yet reflected in status_map (e.g. a switch
    # added between scans) still counts as pending, so totals always
    # reconcile with len(switches) — this is the actual source of truth,
    # not just whatever happens to be in status_map.
    accounted = on + off + chk + pnd
    unaccounted = max(0, len(switches) - accounted)
    pnd += unaccounted
    total = on + off + chk + pnd
    if total == 0:
        return

    cx, cy = w // 2, h // 2 - (26 if big else 18)
    r = min(w, h) // 2 - (48 if big else 34)
    ir = int(r * 0.55)

    segs = [(v, cl, lb) for v, cl, lb in
            [(on, S_GREEN, "Online"), (off, S_RED, "Offline"),
             (chk, S_YELLOW, "Scanning"), (pnd, "#BDBDBD", "Pending")] if v > 0]

    start = 90
    for val, color, _ in segs:
        ext = (val / total) * 360
        c.create_arc(cx - r, cy - r, cx + r, cy + r,
                      start=start, extent=ext, fill=color,
                      outline=CARD_BG, width=2)
        start += ext

    c.create_oval(cx - ir, cy - ir, cx + ir, cy + ir, fill=CARD_BG, outline=CARD_BG)

    c.create_text(cx, cy - (10 if big else 8), text=str(on),
                   font=("Segoe UI", 30 if big else 24, "bold"), fill=S_GREEN)
    c.create_text(cx, cy + (22 if big else 18), text="Online",
                   font=("Segoe UI", 12 if big else 10), fill=T_SEC)

    # Legend: fit as many items per row as the actual canvas width allows
    # (fixed-width slots used to overflow off-canvas once a 4th segment
    # — Scanning — was added), wrapping to a second row if needed.
    item_w = 96 if big else 78
    per_row = max(1, min(len(segs), (w - 16) // item_w))
    n_rows = -(-len(segs) // per_row)
    row_h = 20 if big else 17
    ly0 = h - 8 - n_rows * row_h

    for i, (val, color, label) in enumerate(segs):
        row, col = divmod(i, per_row)
        this_row_n = min(per_row, len(segs) - row * per_row)
        row_w = this_row_n * item_w
        lx0 = max(8, (w - row_w) // 2)
        lx = lx0 + col * item_w
        ly = ly0 + row * row_h
        c.create_oval(lx, ly, lx + 12, ly + 12, fill=color, outline="")
        c.create_text(lx + 16, ly + 6, text=f"{val} {label}",
                       font=("Segoe UI", 10 if big else 8), fill=T_BODY, anchor="w")


def draw_priority_breakdown(canvas, switches, status_map, big=True):
    """Stacked bars: Online/Offline count per OT priority tier — used in the
    Switch Monitor detail/maximize view."""
    from .config import PRIORITIES, PRIORITY_COLORS

    c = canvas
    c.delete("all")
    w, h = c.winfo_width(), c.winfo_height()
    if w < 80 or h < 60:
        return

    by_priority = {p: {"online": 0, "offline": 0, "other": 0} for p in PRIORITIES}
    for sw in switches:
        st = status_map.get(sw["IP"], {"status": "Pending"})
        p = sw.get("Priority", "Medium")
        if p not in by_priority:
            p = "Medium"
        if st["status"] == "● ONLINE":
            by_priority[p]["online"] += 1
        elif st["status"] == "✖ OFFLINE":
            by_priority[p]["offline"] += 1
        else:
            by_priority[p]["other"] += 1

    mx = max((v["online"] + v["offline"] + v["other"] for v in by_priority.values()), default=0) or 1
    ml, mr, mt, mb = 90, 40, 24, 40
    cw, ch_ = w - ml - mr, h - mt - mb
    n = len(PRIORITIES)
    bh = min(46, (ch_ - 8) // n)
    gap = max(6, (ch_ - bh * n) // (n + 1))

    for i, p in enumerate(PRIORITIES):
        y = mt + gap + i * (bh + gap)
        vals = by_priority[p]
        total = vals["online"] + vals["offline"] + vals["other"]
        bar_color, _, _ = PRIORITY_COLORS[p]
        c.create_text(ml - 10, y + bh // 2, text=p, font=("Segoe UI", 11, "bold"),
                       fill=bar_color, anchor="e")
        x = ml
        for val, color in ((vals["online"], S_GREEN), (vals["offline"], S_RED),
                            (vals["other"], "#BDBDBD")):
            seg_w = (val / mx) * cw if mx else 0
            if seg_w > 0:
                c.create_rectangle(x, y, x + seg_w, y + bh, fill=color, outline=CARD_BG)
                x += seg_w
        c.create_text(ml + cw + 10, y + bh // 2, text=f"{total} nodes",
                       font=("Segoe UI", 9), fill=T_SEC, anchor="w")

    ly = h - 20
    for i, (label, color) in enumerate([("Online", S_GREEN), ("Offline", S_RED), ("Pending", "#BDBDBD")]):
        lx = ml + i * 100
        c.create_rectangle(lx, ly, lx + 12, ly + 12, fill=color, outline="")
        c.create_text(lx + 16, ly + 6, text=label, font=("Segoe UI", 9), fill=T_BODY, anchor="w")
