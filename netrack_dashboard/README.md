# NETRACK — OT Network Switch Monitor (Hero MotoCorp)

Rebuilt as a modular, production-ready desktop dashboard (CustomTkinter).
Every original feature is preserved 1:1 — brand header, green-header NOC
panels, KPI row, canvas charts, click-to-filter KPIs, footer ribbon, ping
scan engine — plus the new capabilities below.

## Run it

```bash
pip install customtkinter
python main.py
```

`switches.csv` sits next to `main.py` and is created automatically (with
sample data) if missing.

## Project layout

```
main.py                 entry point
switches.csv             data file (Location, Model, IP, Priority)
netrack/
  config.py               all colors/fonts/timing constants in one place
  data_manager.py          CRUD + two-way CSV sync (atomic writes, thread-safe)
  scanner.py               threaded ping sweep, decoupled from the UI
  ui_panels.py             the green-header panel factory + maximize button
  charts.py                pure chart-drawing functions (reused at 2 sizes)
  switch_monitor.py        compact, priority-coded switch status grid
  dialogs.py               Add/Edit form, CRUD table, maximize/detail window
  app.py                   NetackDashboard — wires it all together
```

## What's new vs. the original

- **CRUD** — "⚙ Manage Switches" in the header opens a full add / edit /
  delete table. Double-click any row in the Switch Monitor to edit it inline.
- **Two-way CSV sync** — every CRUD change writes straight back to
  `switches.csv` (atomic temp-file + replace). A background watcher also
  reloads the file every 4s if it changed on disk (e.g. edited externally),
  without ever wiping live scan results for switches that still exist.
- **15s auto-scan + manual scan** — countdown now defaults to 15s
  (`config.AUTO_SCAN_SECONDS`), plus the original "⚡ RUN SCAN" button and
  clickable Scan Engine KPI card.
- **Maximize / minimize widgets** — the status chart, model-distribution
  chart, donut, and Switch Monitor each have a "⛶" button that opens a large
  detail window: bigger chart + a sortable data table (click any column
  header to sort), auto-refreshing every 2s. "Minimize ▾" closes it back to
  the compact docked view.
- **Compact Switch Monitor with OT priority bars** — each row shows a
  High/Medium/Low priority accent strip alongside the live Online/Offline
  pill, so criticality and health are both visible without opening anything.
- **Search / filter / sort** — the existing search box and status-filter
  KPI clicks now combine with a new Sort dropdown (Priority / Location /
  Model / IP / Status).
- **Modular codebase** — data, scanning, charts, and UI are separated so any
  piece (e.g. swapping ping for SNMP) can change without touching the rest.

No regressions: colors, fonts, panel styling, layout proportions, and all
original interactions are unchanged.
