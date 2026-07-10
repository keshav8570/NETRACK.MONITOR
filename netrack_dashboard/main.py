"""
NETRACK — OT Network Switch Monitor  |  Hero MotoCorp
Entry point. Run with:  python main.py
Requires: customtkinter  (pip install customtkinter)
"""

import customtkinter as ctk

from netrack.app import NetackDashboard

if __name__ == "__main__":
    root = ctk.CTk()
    app = NetackDashboard(root)
    root.mainloop()
