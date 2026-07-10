"""
NETRACK — Scan engine.

Isolated from the UI: does ICMP pings on a thread pool and reports progress
through plain callbacks. The dashboard is responsible for marshalling those
callbacks onto the Tk main thread via root.after(0, ...).
"""

import platform
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .config import SCAN_MAX_WORKERS, PING_TIMEOUT_MS


class NetworkScanner:
    """Runs a parallel ping sweep over a list of switches."""

    def __init__(self, data_manager):
        self.dm = data_manager
        self.is_scanning = False
        self.last_scan_time = None

    @staticmethod
    def ping_device(ip):
        param = "-n" if platform.system().lower() == "windows" else "-c"
        timeout_flag = "-w" if platform.system().lower() == "windows" else "-W"
        timeout_val = str(PING_TIMEOUT_MS) if platform.system().lower() == "windows" \
            else str(max(1, PING_TIMEOUT_MS // 1000))
        cmd = ["ping", param, "1", timeout_flag, timeout_val, ip]
        try:
            si = None
            if platform.system().lower() == "windows":
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            result = subprocess.run(cmd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, startupinfo=si)
            return result.returncode == 0
        except Exception:
            return False

    def run_sweep(self, on_progress=None, on_switch_done=None, on_complete=None):
        """Blocking call — intended to be run inside a worker thread.

        on_progress(processed, total)
        on_switch_done(ip)                 -- fired right after a switch flips to "checking"
        on_complete(timestamp)
        """
        self.is_scanning = True
        switches, _ = self.dm.snapshot()
        total = len(switches)
        processed = 0

        def _scan_one(sw):
            nonlocal processed
            ip = sw["IP"]
            self.dm.set_status(ip, "Scanning…", "checking")
            if on_switch_done:
                on_switch_done(ip)

            alive = self.ping_device(ip)
            if alive:
                self.dm.set_status(ip, "● ONLINE", "online")
            else:
                self.dm.set_status(ip, "✖ OFFLINE", "offline")

            processed += 1
            if on_progress:
                on_progress(processed, total)
            if on_switch_done:
                on_switch_done(ip)

        if total:
            with ThreadPoolExecutor(max_workers=SCAN_MAX_WORKERS) as pool:
                pool.map(_scan_one, switches)

        self.last_scan_time = datetime.now()
        self.is_scanning = False
        if on_complete:
            on_complete(self.last_scan_time)

    def run_sweep_async(self, **callbacks):
        if self.is_scanning:
            return
        threading.Thread(target=self.run_sweep, kwargs=callbacks, daemon=True).start()
