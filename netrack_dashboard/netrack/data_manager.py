"""
NETRACK — Data layer.

Owns the authoritative in-memory list of switches and mirrors every change
(add / edit / delete) straight back to switches.csv, so the CSV file and the
UI are always in sync. All file I/O is funnelled through one lock so scans,
UI edits, and periodic reloads never race each other.
"""

import csv
import ipaddress
import os
import shutil
import threading
from datetime import datetime

from .config import CSV_FIELDS, DEFAULT_PRIORITY, PRIORITIES


def _valid_ipv4(ip):
    """True only for well-formed IPv4 addresses (rejects hostnames, IPv6,
    stray whitespace, etc. that could otherwise reach the ping engine)."""
    try:
        ipaddress.IPv4Address(ip)
        return True
    except (ipaddress.AddressValueError, ValueError):
        return False


class DataManager:
    """CRUD + CSV persistence for the switch inventory."""

    def __init__(self, csv_path):
        self.csv_path = csv_path
        self._lock = threading.RLock()
        self.switches = []          # list[dict]: Location, Model, IP, Priority
        self.status_map = {}        # ip -> {"status": str, "tag": str}
        self.last_loaded = None
        # Populated by load(): counts of rows dropped/fixed for visibility
        # in the UI (footer / manage dialog), without ever raising or
        # crashing on messy real-world CSV data.
        self.load_warnings = {"invalid_ip": 0, "duplicate_ip": 0, "bad_priority": 0}

    # ── Loading ─────────────────────────────────────────────────────────

    def load(self):
        """(Re)load switches from disk. Preserves existing status_map
        entries for IPs that still exist, so a reload never blanks out
        live scan results."""
        with self._lock:
            if not os.path.exists(self.csv_path):
                self._seed_default_csv()

            switches = []
            seen_ips = set()
            warnings = {"invalid_ip": 0, "duplicate_ip": 0, "bad_priority": 0}
            with open(self.csv_path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) < 3:
                        continue
                    loc, mod, ip = row[0].strip(), row[1].strip(), row[2].strip()
                    if not ip:
                        continue
                    if not _valid_ipv4(ip):
                        # Malformed address (typo, hostname, IPv6, stray
                        # whitespace) — never hand this to the ping engine.
                        warnings["invalid_ip"] += 1
                        continue
                    if ip in seen_ips:
                        warnings["duplicate_ip"] += 1
                        continue
                    seen_ips.add(ip)

                    priority = row[3].strip() if len(row) >= 4 and row[3].strip() else DEFAULT_PRIORITY
                    if priority not in PRIORITIES:
                        priority = DEFAULT_PRIORITY
                        warnings["bad_priority"] += 1
                    switches.append({
                        "Location": loc or "(Unnamed location)",
                        "Model": mod or "(Unknown model)",
                        "IP": ip,
                        "Priority": priority,
                    })

            self.load_warnings = warnings
            old_status = self.status_map
            new_status = {}
            for sw in switches:
                ip = sw["IP"]
                new_status[ip] = old_status.get(ip, {"status": "Pending", "tag": "pending"})

            self.switches = switches
            self.status_map = new_status
            self.last_loaded = datetime.now()
            return self.switches

    def _seed_default_csv(self):
        """Create a starter CSV if none exists, so the app never crashes
        on first run."""
        sample = [
            ["Plant-1 Assembly Line A", "Cisco IE-2000", "192.168.92.11", "High"],
            ["Plant-1 Assembly Line B", "Cisco IE-2000", "192.168.92.12", "High"],
            ["Paint Shop Control Room", "Hirschmann RSPE", "192.168.92.21", "High"],
            ["Weld Shop Zone 1", "Moxa EDS-508A", "192.168.92.31", "Medium"],
            ["Weld Shop Zone 2", "Moxa EDS-508A", "192.168.92.32", "Medium"],
            ["Warehouse Gate 3", "Netgear GS724T", "192.168.92.41", "Low"],
            ["Utility Substation", "Siemens Scalance", "192.168.92.51", "High"],
            ["Quality Lab", "TP-Link TL-SG108", "192.168.92.61", "Low"],
        ]
        with open(self.csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(CSV_FIELDS)
            w.writerows(sample)

    # ── Persistence ─────────────────────────────────────────────────────

    def _write_csv(self):
        """Atomic-ish write: write to a temp file then replace, so a crash
        mid-write never corrupts switches.csv."""
        tmp_path = self.csv_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(CSV_FIELDS)
            for sw in self.switches:
                w.writerow([sw["Location"], sw["Model"], sw["IP"], sw["Priority"]])
        shutil.move(tmp_path, self.csv_path)

    # ── CRUD ────────────────────────────────────────────────────────────

    def add_switch(self, location, model, ip, priority=DEFAULT_PRIORITY):
        with self._lock:
            if not _valid_ipv4(ip):
                raise ValueError(f"'{ip}' is not a valid IPv4 address.")
            if any(s["IP"] == ip for s in self.switches):
                raise ValueError(f"A switch with IP {ip} already exists.")
            if priority not in PRIORITIES:
                priority = DEFAULT_PRIORITY
            self.switches.append({
                "Location": location, "Model": model, "IP": ip, "Priority": priority,
            })
            self.status_map[ip] = {"status": "Pending", "tag": "pending"}
            self._write_csv()

    def update_switch(self, original_ip, location, model, ip, priority):
        with self._lock:
            if not _valid_ipv4(ip):
                raise ValueError(f"'{ip}' is not a valid IPv4 address.")
            target = next((s for s in self.switches if s["IP"] == original_ip), None)
            if target is None:
                raise ValueError(f"Switch {original_ip} not found.")
            if ip != original_ip and any(s["IP"] == ip for s in self.switches):
                raise ValueError(f"A switch with IP {ip} already exists.")
            if priority not in PRIORITIES:
                priority = DEFAULT_PRIORITY

            target.update({"Location": location, "Model": model, "IP": ip, "Priority": priority})

            if ip != original_ip:
                self.status_map[ip] = self.status_map.pop(
                    original_ip, {"status": "Pending", "tag": "pending"})
            self._write_csv()

    def delete_switch(self, ip):
        with self._lock:
            self.switches = [s for s in self.switches if s["IP"] != ip]
            self.status_map.pop(ip, None)
            self._write_csv()

    # ── Status updates (called by the scanner) ─────────────────────────

    def set_status(self, ip, status, tag):
        with self._lock:
            self.status_map[ip] = {"status": status, "tag": tag}

    def get_status(self, ip):
        with self._lock:
            return self.status_map.get(ip, {"status": "Pending", "tag": "pending"})

    def snapshot(self):
        """Thread-safe copy of switches + status for read-only rendering."""
        with self._lock:
            return list(self.switches), dict(self.status_map)
