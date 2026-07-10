"""
NETRACK — Panel factory.

Recreates the original NOC-template green-header card, plus an optional
maximize (⛶) button that any widget can hook up to open a detailed
analytics window (see dialogs.DetailWindow).
"""

import customtkinter as ctk

from .config import CARD_BG, CARD_BORDER, PANEL_GREEN, PANEL_HDR_TXT, T_LIGHT, T_DARK


def panel(parent, title, subtitle=None, on_maximize=None, collapsible=False,
          title_font=("Segoe UI", 9, "bold"), subtitle_font=("Segoe UI", 7),
          header_height=32, subtitle_height=16, wrap_text=False):
    """Create a NOC-template panel with a polished Hero-inspired header.

    `title_font` / `subtitle_font` / `header_height` / `subtitle_height`
    default to the original compact sizing used by chart panels and the
    Switch Monitor. Larger KPI cards pass bigger values plus
    `wrap_text=True`, which binds the title/subtitle labels to their
    container's width so long text wraps instead of overflowing the card
    at any window size.
    """
    outer = ctk.CTkFrame(parent, fg_color=CARD_BG, corner_radius=14,
                         border_width=1, border_color=CARD_BORDER)

    hdr = ctk.CTkFrame(outer, fg_color=PANEL_GREEN, height=header_height, corner_radius=12)
    hdr.pack(fill="x", padx=10, pady=(10, 0))
    hdr.pack_propagate(False)
    title_lbl = ctk.CTkLabel(hdr, text=f"  {title}", font=title_font,
                              text_color=PANEL_HDR_TXT, justify="left", anchor="w")
    if wrap_text:
        title_lbl.pack(side="left", padx=4, pady=4, fill="both", expand=True)
        title_lbl.bind("<Configure>",
                        lambda e, lbl=title_lbl: lbl.configure(wraplength=max(50, e.width - 6)))
    else:
        title_lbl.pack(side="left", padx=4, pady=6)

    controls = {}

    if on_maximize:
        btn_max = ctk.CTkButton(hdr, text="⛶", width=24, height=18,
                                 font=("Segoe UI", 9, "bold"),
                                 fg_color="transparent", hover_color="#2C5FB1",
                                 text_color=PANEL_HDR_TXT, corner_radius=4,
                                 command=on_maximize)
        btn_max.pack(side="right", padx=(0, 4), pady=6)
        controls["maximize_btn"] = btn_max
    else:
        ctk.CTkLabel(hdr, text="●", font=("Segoe UI", 9),
                     text_color="#D7E7FF").pack(side="right", padx=8, pady=6)

    body = ctk.CTkFrame(outer, fg_color="transparent", corner_radius=0)

    if subtitle:
        sub = ctk.CTkFrame(outer, fg_color="transparent", height=subtitle_height, corner_radius=0)
        sub.pack(fill="x")
        sub.pack_propagate(False)
        sub_lbl = ctk.CTkLabel(sub, text=f"  {subtitle}", font=subtitle_font,
                                text_color=T_LIGHT, justify="left", anchor="w")
        if wrap_text:
            sub_lbl.pack(side="left", padx=10, pady=(3, 0), fill="both", expand=True)
            sub_lbl.bind("<Configure>",
                         lambda e, lbl=sub_lbl: lbl.configure(wraplength=max(50, e.width - 4)))
        else:
            sub_lbl.pack(side="left", padx=10, pady=(4, 0))

    if collapsible:
        state = {"collapsed": False}

        def _toggle():
            if state["collapsed"]:
                body.pack(fill="both", expand=True, padx=10, pady=(4, 10))
                controls["minimize_btn"].configure(text="–")
            else:
                body.pack_forget()
                controls["minimize_btn"].configure(text="+")
            state["collapsed"] = not state["collapsed"]

        btn_min = ctk.CTkButton(hdr, text="–", width=22, height=18,
                                 font=("Segoe UI", 9, "bold"),
                                 fg_color="transparent", hover_color="#2C5FB1",
                                 text_color=PANEL_HDR_TXT, corner_radius=4,
                                 command=_toggle)
        btn_min.pack(side="right", padx=(0, 2), pady=6)
        controls["minimize_btn"] = btn_min

    body.pack(fill="both", expand=True, padx=10, pady=(4, 10))
    return outer, body, controls


def bind_click_recursive(widget, callback):
    """Bind a left-click callback to a widget and every descendant, so
    clicking anywhere on a card (labels included) triggers the action."""
    widget.bind("<Button-1>", lambda _e: callback())
    for child in widget.winfo_children():
        bind_click_recursive(child, callback)
