from __future__ import annotations

import csv
import html
import ipaddress
import json
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_NAME = "WiFi Vault Pro"
APP_VERSION = "4.10"
APP_TAGLINE = "Network Intelligence Suite"
AUTHOR = "Rice2k"
HOMEPAGE = "https://github.com/rice2k"

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "WiFiVaultPro"
CONFIG_FILE = CONFIG_DIR / "settings.json"

BG = "#081018"
PANEL = "#101a24"
PANEL_2 = "#132232"
PANEL_3 = "#0c1620"
TEXT = "#eaf3ff"
MUTED = "#8fa6bb"
SUBTLE = "#5f7387"
CYAN = "#22d3ee"
GREEN = "#3ee37e"
PURPLE = "#9b7cff"
YELLOW = "#f5c451"
RED = "#ff667a"
BORDER = "#213447"
INPUT_BG = "#0b1520"
SIDEBAR = "#07111b"
BUTTON_BG = "#172839"
BUTTON_HOVER = "#1f3a50"


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)


def set_app_icon(window: tk.Tk | tk.Toplevel) -> None:
    ico_path = resource_path("assets", "wifi_vault_pro.ico")
    png_path = resource_path("assets", "wifi_vault_pro.png")

    try:
        if is_windows() and ico_path.exists():
            window.iconbitmap(str(ico_path))
            return
    except Exception:
        pass

    try:
        if png_path.exists():
            photo = tk.PhotoImage(file=str(png_path))
            window.iconphoto(True, photo)
            setattr(window, "_wifi_vault_icon", photo)
    except Exception:
        pass


def set_windows_app_identity() -> None:
    if not is_windows():
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"Rice2k.WiFiVaultPro.{APP_VERSION}")
    except Exception:
        pass


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def get_startupinfo():
    if os.name != "nt":
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def run_command(args: list[str], timeout: int = 18) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            startupinfo=get_startupinfo(),
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        return completed.returncode, output.strip()
    except FileNotFoundError:
        return 127, f"Command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"Command timed out after {timeout} seconds: {' '.join(args)}"
    except Exception as exc:
        return 1, f"{type(exc).__name__}: {exc}"


def clean_value(line: str) -> str:
    if ":" not in line:
        return ""
    return line.split(":", 1)[1].strip()


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        item = (item or "").strip()
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def safe_percent(value: str | int | None) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return max(0, min(100, value))
    match = re.search(r"(\d+)", value)
    if not match:
        return 0
    return max(0, min(100, int(match.group(1))))


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception as exc:
        messagebox.showerror("Open link", f"Could not open the link.\n\n{exc}")


@dataclass
class WifiProfile:
    name: str
    authentication: str = "Unknown"
    encryption: str = "Unknown"
    password: str = ""
    connection_mode: str = ""
    source: str = "netsh"
    notes: str = ""


@dataclass
class NearbyNetwork:
    ssid: str
    authentication: str = "Unknown"
    encryption: str = "Unknown"
    signal: str = ""
    channel: str = ""
    radio_type: str = ""
    bssid_count: int = 0


@dataclass
class IpDetection:
    local_primary: str = ""
    hostname: str = ""
    hostname_ips: list[str] = field(default_factory=list)
    ipconfig_ips: list[str] = field(default_factory=list)
    powershell_ips: list[str] = field(default_factory=list)
    gateways: list[str] = field(default_factory=list)
    dns_servers: list[str] = field(default_factory=list)
    public_ipv4: str = ""
    public_ipv4_source: str = ""
    public_ipv6: str = ""
    public_ipv6_source: str = ""
    adapters: list[dict[str, str]] = field(default_factory=list)
    raw_errors: list[str] = field(default_factory=list)


@dataclass
class ConnectivityCheck:
    name: str
    status: str
    detail: str


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.after_id: str | None = None
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, _event=None) -> None:
        self.cancel()
        self.after_id = self.widget.after(self.delay_ms, self.show)

    def cancel(self) -> None:
        if self.after_id:
            try:
                self.widget.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

    def show(self) -> None:
        if self.tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        frame = tk.Frame(self.tip, bg="#d5f5ff", bd=0, padx=1, pady=1)
        frame.pack()
        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            bg="#0d1722",
            fg=TEXT,
            padx=10,
            pady=7,
            wraplength=330,
            font=("Segoe UI", 9),
        )
        label.pack()

    def hide(self, _event=None) -> None:
        self.cancel()
        if self.tip:
            self.tip.destroy()
            self.tip = None


def hard_wrap_text(value: str, max_chars: int = 24) -> str:
    text = str(value or "")
    if len(text) <= max_chars:
        return text
    if ", " in text:
        return text.replace(", ", ",\n")
    output: list[str] = []
    for line in text.splitlines() or [text]:
        if len(line) <= max_chars:
            output.append(line)
            continue
        start = 0
        while start < len(line):
            end = min(start + max_chars, len(line))
            if end < len(line):
                colon = line.rfind(":", start, end)
                dot = line.rfind(".", start, end)
                split_at = max(colon, dot)
                if split_at > start + 8:
                    end = split_at + 1
            output.append(line[start:end])
            start = end
    return "\n".join(output)


def responsive_label(
    parent: tk.Widget,
    text: str,
    bg: str,
    fg: str,
    font: tuple,
    *,
    min_wrap: int = 180,
    margin: int = 36,
    **kwargs,
) -> tk.Label:
    label = tk.Label(parent, text=text, bg=bg, fg=fg, font=font, justify="left", anchor="w", **kwargs)

    def update_wrap(event=None) -> None:
        try:
            width = parent.winfo_width() if event is None else event.width
            label.configure(wraplength=max(min_wrap, width - margin))
        except tk.TclError:
            pass

    parent.bind("<Configure>", update_wrap, add="+")
    label.after_idle(update_wrap)
    return label


class ScrollFrame(tk.Frame):
    _active_canvas: tk.Canvas | None = None
    _wheel_bound_roots: set[str] = set()

    def __init__(self, parent: tk.Widget, bg: str = BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.bind("<Enter>", self._activate, add="+")
        self.canvas.bind("<Enter>", self._activate, add="+")
        self.inner.bind("<Enter>", self._activate, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        root = self.winfo_toplevel()
        root_key = str(root)
        if root_key not in self._wheel_bound_roots:
            root.bind_all("<MouseWheel>", self._on_mousewheel, add="+")
            root.bind_all("<Button-4>", self._on_mousewheel, add="+")
            root.bind_all("<Button-5>", self._on_mousewheel, add="+")
            self._wheel_bound_roots.add(root_key)

    def _on_inner_configure(self, _event=None) -> None:
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            pass

    def _on_canvas_configure(self, event) -> None:
        try:
            self.canvas.itemconfig(self.window_id, width=event.width)
        except tk.TclError:
            pass

    def _activate(self, _event=None) -> None:
        ScrollFrame._active_canvas = self.canvas

    def _on_destroy(self, event=None) -> None:
        if event is not None and event.widget is not self:
            return
        if ScrollFrame._active_canvas is self.canvas:
            ScrollFrame._active_canvas = None

    @classmethod
    def _on_mousewheel(cls, event) -> None:
        canvas = cls._active_canvas
        if canvas is None:
            return
        try:
            if not canvas.winfo_exists():
                cls._active_canvas = None
                return
            if getattr(event, "num", None) == 4:
                amount = -3
            elif getattr(event, "num", None) == 5:
                amount = 3
            else:
                amount = int(-1 * (event.delta / 120))
            canvas.yview_scroll(amount, "units")
        except tk.TclError:
            cls._active_canvas = None


def load_settings() -> dict:
    defaults = {
        "clock_format": "12",
        "refresh_on_start": False,
        "include_passwords_in_reports": False,
        "public_ip_on_refresh": False,
    }
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            defaults.update({k: v for k, v in data.items() if k in defaults})
    except Exception:
        pass
    return defaults


def save_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def parse_wifi_profiles(text: str) -> list[str]:
    names = []
    for line in text.splitlines():
        if "All User Profile" in line or "User Profile" in line:
            value = clean_value(line)
            if value:
                names.append(value)
    return unique(names)


def get_wifi_profiles() -> list[str]:
    if not is_windows():
        return []
    code, output = run_command(["netsh", "wlan", "show", "profiles"])
    if code != 0:
        return []
    return parse_wifi_profiles(output)


def get_profile_detail(name: str) -> WifiProfile:
    profile = WifiProfile(name=name)
    if not is_windows():
        profile.notes = "WiFi profile inspection uses Windows netsh and is unavailable on this system."
        return profile

    code, output = run_command(["netsh", "wlan", "show", "profiles", f"name={name}", "key=clear"])
    if code != 0:
        profile.notes = output or "Could not read profile details."
        return profile

    for line in output.splitlines():
        stripped = line.strip()
        key = stripped.split(":", 1)[0].strip().lower() if ":" in stripped else ""
        value = clean_value(stripped)
        if key == "authentication":
            profile.authentication = value or profile.authentication
        elif key == "cipher":
            profile.encryption = value or profile.encryption
        elif key == "key content":
            profile.password = value
        elif key == "connection mode":
            profile.connection_mode = value

    if not profile.password:
        profile.notes = "No key content was returned. The network may be open, unavailable, or protected by Windows permissions."
    return profile


def get_wifi_interface() -> dict[str, str]:
    info = {
        "state": "Unknown",
        "ssid": "Not connected",
        "signal": "",
        "radio": "",
        "channel": "",
        "authentication": "",
        "cipher": "",
    }
    if not is_windows():
        info["state"] = "Windows WiFi tools unavailable"
        return info
    code, output = run_command(["netsh", "wlan", "show", "interfaces"])
    if code != 0:
        info["state"] = "Unavailable"
        return info
    for line in output.splitlines():
        stripped = line.strip()
        key = stripped.split(":", 1)[0].strip().lower() if ":" in stripped else ""
        value = clean_value(stripped)
        if key == "state":
            info["state"] = value
        elif key == "ssid":
            info["ssid"] = value
        elif key == "signal":
            info["signal"] = value
        elif key == "radio type":
            info["radio"] = value
        elif key == "channel":
            info["channel"] = value
        elif key == "authentication":
            info["authentication"] = value
        elif key == "cipher":
            info["cipher"] = value
    return info


def guess_band(channel: str, radio_type: str = "") -> str:
    text = f"{channel} {radio_type}".lower()
    match = re.search(r"\d+", channel or "")
    if "6ghz" in text or "802.11ax" in text and match and int(match.group(0)) > 180:
        return "6 GHz"
    if match:
        num = int(match.group(0))
        if num <= 14:
            return "2.4 GHz"
        if num > 14:
            return "5 GHz"
    return "Unknown"


def signal_quality(signal: str) -> str:
    percent = safe_percent(signal)
    if percent >= 80:
        return "Excellent"
    if percent >= 60:
        return "Good"
    if percent >= 40:
        return "Fair"
    if percent > 0:
        return "Weak"
    return "Unknown"


def nearby_summary(networks: list[NearbyNetwork]) -> dict[str, int | str]:
    bands = {"2.4 GHz": 0, "5 GHz": 0, "6 GHz": 0, "Unknown": 0}
    secure = 0
    open_count = 0
    strongest = ""
    strongest_signal = -1
    for net in networks:
        band = guess_band(net.channel, net.radio_type)
        bands[band] = bands.get(band, 0) + 1
        if "open" in (net.authentication or "").lower():
            open_count += 1
        else:
            secure += 1
        signal = safe_percent(net.signal)
        if signal > strongest_signal:
            strongest_signal = signal
            strongest = net.ssid
    return {
        "total": len(networks),
        "strongest": strongest or "Unavailable",
        "strongest_signal": f"{strongest_signal}%" if strongest_signal >= 0 else "Unavailable",
        "2.4 GHz": bands.get("2.4 GHz", 0),
        "5 GHz": bands.get("5 GHz", 0),
        "6 GHz": bands.get("6 GHz", 0),
        "secure": secure,
        "open": open_count,
    }


def get_nearby_networks() -> list[NearbyNetwork]:
    if not is_windows():
        return []
    code, output = run_command(["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=25)
    if code != 0:
        return []

    networks: list[NearbyNetwork] = []
    current: NearbyNetwork | None = None
    for line in output.splitlines():
        stripped = line.strip()
        if re.match(r"^SSID\s+\d+\s*:", stripped):
            if current and current.ssid:
                networks.append(current)
            current = NearbyNetwork(ssid=clean_value(stripped) or "(Hidden network)")
        elif current and ":" in stripped:
            key = stripped.split(":", 1)[0].strip().lower()
            value = clean_value(stripped)
            if key == "authentication":
                current.authentication = value
            elif key == "encryption":
                current.encryption = value
            elif key == "signal":
                current.signal = value
            elif key == "channel":
                current.channel = value
            elif key == "radio type":
                current.radio_type = value
            elif key.startswith("bssid"):
                current.bssid_count += 1
    if current and current.ssid:
        networks.append(current)

    merged: dict[str, NearbyNetwork] = {}
    for net in networks:
        existing = merged.get(net.ssid)
        if not existing:
            merged[net.ssid] = net
            continue
        if safe_percent(net.signal) > safe_percent(existing.signal):
            merged[net.ssid] = net
            merged[net.ssid].bssid_count += existing.bssid_count
        else:
            existing.bssid_count += net.bssid_count

    return sorted(merged.values(), key=lambda item: safe_percent(item.signal), reverse=True)


def detect_local_socket_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2)
        sock.connect(("8.8.8.8", 80))
        value = sock.getsockname()[0]
        sock.close()
        return value
    except Exception:
        return ""


def detect_hostname_ips() -> list[str]:
    try:
        host = socket.gethostname()
        results = socket.getaddrinfo(host, None, socket.AF_INET)
        return unique([item[4][0] for item in results if not item[4][0].startswith("127.")])
    except Exception:
        return []


def extract_ipv4(text: str) -> str:
    pattern = r"(?<![\d.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?![\d.])"
    match = re.search(pattern, text or "")
    if not match:
        return ""
    value = match.group(1)
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return ""
    return value


def parse_ipconfig(output: str) -> tuple[list[str], list[str], list[str], list[dict[str, str]]]:
    ips: list[str] = []
    gateways: list[str] = []
    dns: list[str] = []
    adapters: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    last_field = ""

    for raw in output.splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            last_field = ""
            continue
        if not raw.startswith(" ") and stripped.endswith(":"):
            current = {"name": stripped[:-1], "ipv4": "", "gateway": "", "dns": ""}
            adapters.append(current)
            continue

        ipv4_match = re.search(r"IPv4 Address[^:]*:\s*(.*)$", stripped)
        gateway_match = re.search(r"Default Gateway[^:]*:\s*(.*)$", stripped)
        dns_match = re.search(r"DNS Servers[^:]*:\s*(.*)$", stripped)
        continuation_value = extract_ipv4(stripped)

        if ipv4_match:
            value = extract_ipv4(ipv4_match.group(1))
            if value:
                ips.append(value)
                if current:
                    current["ipv4"] = value
            last_field = "ipv4"
        elif gateway_match:
            value = extract_ipv4(gateway_match.group(1))
            if value:
                gateways.append(value)
                if current:
                    current["gateway"] = value
            last_field = "gateway"
        elif dns_match:
            value = extract_ipv4(dns_match.group(1))
            if value:
                dns.append(value)
                if current:
                    current["dns"] = value
            last_field = "dns"
        elif continuation_value and last_field in {"gateway", "dns"}:
            value = continuation_value
            target = gateways if last_field == "gateway" else dns
            target.append(value)
            if current and last_field == "gateway":
                current["gateway"] = value
            elif current:
                current["dns"] = ", ".join(unique([current.get("dns", ""), value]))

    adapters = [item for item in adapters if item.get("ipv4") or item.get("gateway") or item.get("dns")]
    return unique(ips), unique(gateways), unique(dns), adapters


def detect_ipconfig() -> tuple[list[str], list[str], list[str], list[dict[str, str]], str]:
    if not is_windows():
        return [], [], [], [], "ipconfig is Windows-specific."
    code, output = run_command(["ipconfig", "/all"], timeout=14)
    if code != 0:
        return [], [], [], [], output
    ips, gateways, dns, adapters = parse_ipconfig(output)
    return ips, gateways, dns, adapters, ""


def detect_powershell_ips() -> tuple[list[str], str]:
    if not is_windows():
        return [], "PowerShell adapter detection is Windows-specific."
    ps = (
        "Get-NetIPAddress -AddressFamily IPv4 "
        "| Where-Object {$_.IPAddress -notlike '169.254*' -and $_.IPAddress -ne '127.0.0.1'} "
        "| Select-Object -ExpandProperty IPAddress"
    )
    code, output = run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=14)
    if code != 0:
        return [], output
    return unique([line.strip() for line in output.splitlines() if re.match(r"^\d+\.\d+\.\d+\.\d+$", line.strip())]), ""


def fetch_public_ip(services: list[tuple[str, str]], timeout: int = 5) -> tuple[str, str, list[str]]:
    errors: list[str] = []
    for label, url in services:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                value = response.read(80).decode("utf-8", "replace").strip()
            if value and re.match(r"^[0-9a-fA-F:.]+$", value):
                return value, label, errors
        except Exception as exc:
            errors.append(f"{label}: {exc}")
    return "", "", errors


def detect_ips(include_public: bool = True) -> IpDetection:
    info = IpDetection()
    try:
        info.hostname = socket.gethostname()
    except Exception:
        info.hostname = "Unknown"
    info.local_primary = detect_local_socket_ip()
    info.hostname_ips = detect_hostname_ips()
    ips, gateways, dns, adapters, err = detect_ipconfig()
    info.ipconfig_ips = ips
    info.gateways = gateways
    info.dns_servers = dns
    info.adapters = adapters
    if err:
        info.raw_errors.append(f"ipconfig: {err}")
    ps_ips, ps_err = detect_powershell_ips()
    info.powershell_ips = ps_ips
    if ps_err:
            info.raw_errors.append(f"PowerShell: {ps_err}")

    if include_public:
        info.public_ipv4, info.public_ipv4_source, errors4 = fetch_public_ip(
            [
                ("api.ipify.org", "https://api.ipify.org"),
                ("checkip.amazonaws.com", "https://checkip.amazonaws.com"),
                ("icanhazip.com", "https://icanhazip.com"),
                ("ifconfig.me", "https://ifconfig.me/ip"),
            ]
        )
        info.raw_errors.extend(errors4[:2])
        info.public_ipv6, info.public_ipv6_source, errors6 = fetch_public_ip(
            [
                ("api6.ipify.org", "https://api6.ipify.org"),
                ("icanhazip IPv6", "https://ipv6.icanhazip.com"),
            ],
            timeout=4,
        )
        if info.public_ipv6 and "." in info.public_ipv6:
            info.public_ipv6 = ""
            info.public_ipv6_source = ""
        info.raw_errors.extend(errors6[:2])
    return info


def detect_quick_ips() -> IpDetection:
    info = IpDetection()
    try:
        info.hostname = socket.gethostname()
    except Exception:
        info.hostname = "Unknown"
    info.local_primary = detect_local_socket_ip()
    info.hostname_ips = detect_hostname_ips()
    return info


def ping_host(target: str, timeout_ms: int = 1500) -> tuple[bool, str]:
    if not target:
        return False, "No target available."
    if is_windows():
        args = ["ping", "-n", "1", "-w", str(timeout_ms), target]
    else:
        args = ["ping", "-c", "1", "-W", str(max(1, int(timeout_ms / 1000))), target]
    code, output = run_command(args, timeout=max(4, int(timeout_ms / 1000) + 3))
    if code == 0:
        match = re.search(r"(?:time[=<]\s*|time=)(\d+)\s*ms", output, re.IGNORECASE)
        latency = f" Reply time {match.group(1)} ms." if match else ""
        return True, f"{target} replied.{latency}"
    short = "No reply."
    if "could not find host" in output.lower():
        short = "Host could not be resolved."
    elif "timed out" in output.lower():
        short = "Request timed out."
    return False, f"{target}: {short}"


def run_connectivity_checks(info: IpDetection) -> list[ConnectivityCheck]:
    checks: list[ConnectivityCheck] = []
    local_ip = info.local_primary or first_ip(info)
    gateway = info.gateways[0] if info.gateways else ""
    dns = info.dns_servers[0] if info.dns_servers else ""

    checks.append(
        ConnectivityCheck(
            "Local IP",
            "Pass" if local_ip else "Fail",
            local_ip or "No local IPv4 address was detected.",
        )
    )
    checks.append(
        ConnectivityCheck(
            "Default Gateway",
            "Pass" if gateway else "Warn",
            gateway or "No IPv4 gateway was detected. This may be normal on some VPN or IPv6-only connections.",
        )
    )
    checks.append(
        ConnectivityCheck(
            "DNS Servers",
            "Pass" if info.dns_servers else "Warn",
            ", ".join(info.dns_servers) or "No IPv4 DNS servers were detected.",
        )
    )

    if gateway:
        ok, detail = ping_host(gateway)
        checks.append(ConnectivityCheck("Gateway Ping", "Pass" if ok else "Warn", detail))
    else:
        checks.append(ConnectivityCheck("Gateway Ping", "Skip", "Skipped because no gateway was detected."))

    try:
        resolved = socket.gethostbyname_ex("github.com")[2]
        checks.append(ConnectivityCheck("DNS Resolve", "Pass", f"github.com resolves to {', '.join(resolved[:3])}."))
    except Exception as exc:
        checks.append(ConnectivityCheck("DNS Resolve", "Fail", f"github.com lookup failed: {exc}"))

    ok, detail = ping_host("1.1.1.1")
    checks.append(ConnectivityCheck("Internet Ping", "Pass" if ok else "Warn", detail))

    if info.public_ipv4:
        checks.append(ConnectivityCheck("Public IPv4", "Pass", f"{info.public_ipv4} from {info.public_ipv4_source or 'public lookup'}." ))
    else:
        checks.append(ConnectivityCheck("Public IPv4", "Warn", "No public IPv4 is loaded yet. Run Full IP Scan if you want this check."))

    if info.public_ipv6:
        checks.append(ConnectivityCheck("Public IPv6", "Pass", f"{info.public_ipv6} from {info.public_ipv6_source or 'public lookup'}." ))
    else:
        checks.append(ConnectivityCheck("Public IPv6", "Info", "No public IPv6 detected. Many home networks do not expose IPv6."))

    return checks


def get_network_driver_inventory() -> tuple[list[dict[str, str]], str]:
    if not is_windows():
        return [], "Network driver inventory uses Windows PowerShell."
    ps = (
        "Get-CimInstance Win32_PnPSignedDriver "
        "| Where-Object {$_.DeviceClass -eq 'NET'} "
        "| Select-Object DeviceName,Manufacturer,DriverVersion,DriverDate,InfName,IsSigned "
        "| ConvertTo-Json -Depth 3"
    )
    code, output = run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=25)
    if code != 0 or not output:
        return [], output or "PowerShell did not return driver data."
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        rows = []
        for item in data:
            rows.append(
                {
                    "device": str(item.get("DeviceName") or ""),
                    "manufacturer": str(item.get("Manufacturer") or ""),
                    "version": str(item.get("DriverVersion") or ""),
                    "date": str(item.get("DriverDate") or ""),
                    "inf": str(item.get("InfName") or ""),
                    "signed": str(item.get("IsSigned") or ""),
                }
            )
        return rows, ""
    except Exception as exc:
        return [], f"Could not parse driver data: {exc}"


def get_network_adapter_inventory() -> tuple[list[dict[str, str]], str]:
    if not is_windows():
        return [], "Network adapter inventory uses Windows PowerShell."
    ps = (
        "Get-NetAdapter "
        "| Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed,MediaType,ifIndex "
        "| ConvertTo-Json -Depth 3"
    )
    code, output = run_command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], timeout=20)
    if code != 0 or not output:
        return [], output or "PowerShell did not return adapter data."
    try:
        data = json.loads(output)
        if isinstance(data, dict):
            data = [data]
        rows = []
        for item in data:
            rows.append(
                {
                    "name": str(item.get("Name") or ""),
                    "description": str(item.get("InterfaceDescription") or ""),
                    "status": str(item.get("Status") or ""),
                    "mac": str(item.get("MacAddress") or ""),
                    "speed": str(item.get("LinkSpeed") or ""),
                    "media": str(item.get("MediaType") or ""),
                    "index": str(item.get("ifIndex") or ""),
                }
            )
        return rows, ""
    except Exception as exc:
        return [], f"Could not parse adapter data: {exc}"


def wifi_qr_payload(ssid: str, password: str, authentication: str) -> str:
    auth = "nopass" if "open" in authentication.lower() or not password else "WPA"
    if "wep" in authentication.lower():
        auth = "WEP"

    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace('"', '\\"')

    return f"WIFI:T:{auth};S:{esc(ssid)};P:{esc(password)};H:false;;"


def qr_support_available() -> bool:
    try:
        import qrcode  # noqa: F401
        from PIL import ImageTk  # noqa: F401

        return True
    except Exception:
        return False


def safe_filename(value: str, fallback: str = "wifi_network") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value or "").strip("._")
    return cleaned[:80] or fallback


class WifiVaultProApp:
    def __init__(self):
        set_windows_app_identity()
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} {APP_VERSION} by {AUTHOR}")
        self.root.geometry("1180x760")
        self.root.minsize(1060, 680)
        self.root.configure(bg=BG)
        set_app_icon(self.root)
        self.is_closing = False
        self.ui_queue: queue.Queue = queue.Queue()
        self.clock_after_id: str | None = None
        self.queue_after_id: str | None = None
        self.progress_reset_after_id: str | None = None

        self.settings = load_settings()
        self.clock_format = tk.StringVar(value=str(self.settings.get("clock_format", "12")))
        self.include_passwords = tk.BooleanVar(value=bool(self.settings.get("include_passwords_in_reports", False)))
        self.public_ip_on_refresh = tk.BooleanVar(value=bool(self.settings.get("public_ip_on_refresh", False)))
        self.refresh_on_start = tk.BooleanVar(value=bool(self.settings.get("refresh_on_start", False)))

        self.current_page = "Dashboard"
        self.nav_buttons: dict[str, tk.Button] = {}
        self.status_text = tk.StringVar(value="Ready")
        self.progress_value = tk.IntVar(value=0)
        self.progress_text = tk.StringVar(value="Idle")
        self.profile_names: list[str] = []
        self.profile_details: dict[str, WifiProfile] = {}
        self.nearby_networks: list[NearbyNetwork] = []
        self.health_checks: list[ConnectivityCheck] = []
        self.driver_inventory: list[dict[str, str]] = []
        self.driver_inventory_note = ""
        self.adapter_inventory: list[dict[str, str]] = []
        self.adapter_inventory_note = ""
        self.interface_info: dict[str, str] = {
            "state": "Not scanned",
            "ssid": "Not scanned",
            "signal": "",
            "radio": "",
            "channel": "",
            "authentication": "",
            "cipher": "",
        }
        self.ip_info: IpDetection = IpDetection()
        self.profiles_loaded = False
        self.nearby_loaded = False
        self.ip_loaded = False
        self.adapters_loaded = False
        self.drivers_loaded = False
        self.selected_profile_name = ""
        self.command_output: tk.Text | None = None
        self.last_command_output = ""
        self.page_body: tk.Frame | None = None

        self._setup_styles()
        self._build_shell()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._tick_clock()
        self.queue_after_id = self.root.after(80, self.process_ui_queue)
        self.show_dashboard()
        if self.refresh_on_start.get():
            self.root.after(350, self.refresh_quick)

    def _setup_styles(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", background=INPUT_BG, foreground=TEXT, fieldbackground=INPUT_BG, rowheight=30, bordercolor=BORDER)
        style.configure("Treeview.Heading", background=PANEL_2, foreground=TEXT, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", "#1e4e66")], foreground=[("selected", "#ffffff")])
        style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=BG, bordercolor=BG, arrowcolor=TEXT)
        style.configure("TEntry", fieldbackground=INPUT_BG, foreground=TEXT, bordercolor=BORDER)
        style.configure("TCombobox", fieldbackground=INPUT_BG, background=INPUT_BG, foreground=TEXT, arrowcolor=TEXT)
        style.configure("TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure(
            "Vault.Horizontal.TProgressbar",
            troughcolor=PANEL_3,
            background=CYAN,
            bordercolor=BORDER,
            lightcolor=CYAN,
            darkcolor=CYAN,
        )

    def _build_shell(self) -> None:
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(self.root, bg=SIDEBAR, width=230)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)

        logo = tk.Canvas(sidebar, width=190, height=92, bg=SIDEBAR, highlightthickness=0)
        logo.pack(padx=20, pady=(20, 8), fill="x")
        logo.create_oval(14, 14, 74, 74, outline=CYAN, width=2)
        logo.create_arc(28, 28, 60, 60, start=30, extent=120, outline=GREEN, width=2, style="arc")
        logo.create_arc(20, 20, 68, 68, start=30, extent=120, outline=CYAN, width=2, style="arc")
        logo.create_text(44, 55, text="WV", fill=TEXT, font=("Segoe UI", 14, "bold"))
        logo.create_text(92, 24, anchor="w", text="WiFi Vault", fill=TEXT, font=("Segoe UI", 13, "bold"))
        logo.create_text(92, 48, anchor="w", text=f"Pro {APP_VERSION}", fill=CYAN, font=("Segoe UI", 10, "bold"))
        logo.create_text(92, 70, anchor="w", text=f"by {AUTHOR}", fill=MUTED, font=("Segoe UI", 9))

        nav_items = [
            ("Dashboard", "Overview of connection, WiFi, IP, and quick actions."),
            ("WiFi Profiles", "Saved WiFi profiles, details, copy tools, and QR payloads."),
            ("Nearby Networks", "Scan visible WiFi networks and compare signal/channel details."),
            ("IP Intelligence", "Detect local, adapter, DNS, gateway, public IPv4, and IPv6 addresses."),
            ("Health Check", "Run quick connectivity tests and get a network health score."),
            ("Drivers & Folders", "Open useful Windows driver/network folders and view network driver info."),
            ("Network Tools", "Ping, DNS lookup, traceroute, ARP, routes, ports, and repair commands."),
            ("Reports", "Export CSV, HTML, and clipboard summaries."),
            ("Help", "Plain-English guide explaining what every section and tool does."),
            ("Settings", "Clock format, report privacy, and refresh preferences."),
            ("About", "Program info, Rice2k branding, and GitHub homepage."),
        ]
        nav_frame = tk.Frame(sidebar, bg=SIDEBAR)
        nav_frame.pack(fill="both", expand=True, padx=12, pady=(4, 6))
        for name, tip in nav_items:
            button = tk.Button(
                nav_frame,
                text=name,
                anchor="w",
                bg=SIDEBAR,
                fg=MUTED,
                activebackground=BUTTON_HOVER,
                activeforeground=TEXT,
                relief="flat",
                bd=0,
                padx=16,
                pady=9,
                font=("Segoe UI", 10, "bold"),
                command=lambda n=name: self.navigate(n),
            )
            button.pack(fill="x", pady=2)
            ToolTip(button, tip)
            self.nav_buttons[name] = button

        footer = tk.Frame(sidebar, bg="#091520", padx=12, pady=10)
        footer.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(footer, text="Homepage", bg="#091520", fg=SUBTLE, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        link = tk.Label(footer, text="GitHub.com/rice2k", bg="#091520", fg=CYAN, cursor="hand2", font=("Segoe UI", 9, "underline"))
        link.pack(anchor="w", pady=(3, 0))
        link.bind("<Button-1>", lambda _event: open_url(HOMEPAGE))
        ToolTip(link, "Open Rice2k's GitHub homepage in your default browser.")

        main = tk.Frame(self.root, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_columnconfigure(0, weight=1)
        main.grid_rowconfigure(1, weight=1)

        header = tk.Frame(main, bg=BG, padx=24, pady=16)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_block = tk.Frame(header, bg=BG)
        title_block.grid(row=0, column=0, sticky="w")
        tk.Label(title_block, text=f"{APP_NAME} {APP_VERSION}", bg=BG, fg=TEXT, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        tk.Label(title_block, text=f"{APP_TAGLINE} - Created by {AUTHOR}", bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(3, 0))

        right_header = tk.Frame(header, bg=BG)
        right_header.grid(row=0, column=1, sticky="e")
        self.clock_label = tk.Label(right_header, text="", bg=BG, fg=TEXT, font=("Segoe UI", 16, "bold"))
        self.clock_label.pack(anchor="e")
        clock_controls = tk.Frame(right_header, bg=BG)
        clock_controls.pack(anchor="e", pady=(8, 0))
        self.clock_12_btn = self.small_button(clock_controls, "12H", lambda: self.set_clock_format("12"), "Use a 12-hour clock with AM/PM.")
        self.clock_12_btn.pack(side="left", padx=(0, 6))
        self.clock_24_btn = self.small_button(clock_controls, "24H", lambda: self.set_clock_format("24"), "Use a 24-hour clock.")
        self.clock_24_btn.pack(side="left")

        self.content = tk.Frame(main, bg=BG)
        self.content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 20))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        status = tk.Frame(main, bg="#07111b", padx=18, pady=8)
        status.grid(row=2, column=0, sticky="ew")
        status.grid_columnconfigure(0, weight=1)
        tk.Label(status, textvariable=self.status_text, bg="#07111b", fg=MUTED, font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w")
        progress_wrap = tk.Frame(status, bg="#07111b")
        progress_wrap.grid(row=0, column=1, sticky="e", padx=(12, 16))
        self.progress_bar = ttk.Progressbar(progress_wrap, orient="horizontal", mode="determinate", maximum=100, variable=self.progress_value, length=170, style="Vault.Horizontal.TProgressbar")
        self.progress_bar.pack(side="left")
        tk.Label(progress_wrap, textvariable=self.progress_text, bg="#07111b", fg=MUTED, font=("Segoe UI", 9), width=18, anchor="w").pack(side="left", padx=(8, 0))
        tk.Label(status, text="Authorized local use only", bg="#07111b", fg=SUBTLE, font=("Segoe UI", 9)).grid(row=0, column=2, sticky="e")

    def navigate(self, name: str) -> None:
        self.current_page = name
        page_map = {
            "Dashboard": self.show_dashboard,
            "WiFi Profiles": self.show_profiles,
            "Nearby Networks": self.show_nearby,
            "IP Intelligence": self.show_ip_intelligence,
            "Health Check": self.show_health_check,
            "Drivers & Folders": self.show_drivers_folders,
            "Network Tools": self.show_tools,
            "Reports": self.show_reports,
            "Help": self.show_help,
            "Settings": self.show_settings,
            "About": self.show_about,
        }
        page_map[name]()

    def set_active_nav(self, name: str) -> None:
        for nav_name, button in self.nav_buttons.items():
            active = nav_name == name
            button.configure(bg=BUTTON_BG if active else SIDEBAR, fg=TEXT if active else MUTED)

    def clear_content(self) -> tk.Frame:
        for child in self.content.winfo_children():
            child.destroy()
        self.set_active_nav(self.current_page)
        frame = tk.Frame(self.content, bg=BG)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        self.page_body = frame
        return frame

    def _tick_clock(self) -> None:
        if self.is_closing:
            return
        try:
            now = datetime.now()
            if self.clock_format.get() == "24":
                text = now.strftime("%H:%M:%S")
            else:
                text = now.strftime("%I:%M:%S %p").lstrip("0")
            if hasattr(self, "clock_label"):
                self.clock_label.configure(text=text)
                self._refresh_clock_buttons()
        except (tk.TclError, RuntimeError):
            return
        try:
            self.clock_after_id = self.root.after(1000, self._tick_clock)
        except (tk.TclError, RuntimeError):
            pass

    def _refresh_clock_buttons(self) -> None:
        if not hasattr(self, "clock_12_btn"):
            return
        for value, button in [("12", self.clock_12_btn), ("24", self.clock_24_btn)]:
            active = self.clock_format.get() == value
            button.configure(bg=CYAN if active else BUTTON_BG, fg="#07111b" if active else TEXT)

    def set_clock_format(self, value: str) -> None:
        self.clock_format.set(value)
        self.settings["clock_format"] = value
        save_settings(self.settings)
        self._refresh_clock_buttons()
        self.set_status(f"Clock set to {value}-hour format.")

    def set_status(self, text: str) -> None:
        if self.is_closing:
            return
        try:
            self.status_text.set(text)
            self.root.update_idletasks()
        except (tk.TclError, RuntimeError):
            pass

    def set_progress(self, percent: int, text: str = "") -> None:
        if self.is_closing:
            return
        percent = max(0, min(100, int(percent)))
        try:
            self.progress_value.set(percent)
            label = f"{percent}%"
            if text:
                label = f"{label} {text}"
            elif percent == 0:
                label = "Idle"
            self.progress_text.set(label)
            self.root.update_idletasks()
        except (tk.TclError, RuntimeError):
            pass

    def schedule_progress(self, percent: int, text: str = "") -> None:
        self.post_ui(self.set_progress, percent, text)

    def post_ui(self, callback: Callable, *args, **kwargs) -> None:
        if self.is_closing:
            return
        try:
            self.ui_queue.put_nowait((callback, args, kwargs))
        except Exception:
            pass

    def process_ui_queue(self) -> None:
        if self.is_closing:
            return
        try:
            while True:
                callback, args, kwargs = self.ui_queue.get_nowait()
                try:
                    callback(*args, **kwargs)
                except (tk.TclError, RuntimeError):
                    if not self.is_closing:
                        raise
        except queue.Empty:
            pass
        try:
            self.queue_after_id = self.root.after(80, self.process_ui_queue)
        except (tk.TclError, RuntimeError):
            pass

    def reset_progress(self) -> None:
        if self.is_closing:
            return
        if self.progress_value.get() >= 100:
            self.set_progress(0, "")

    def close(self) -> None:
        self.is_closing = True
        for after_id in [self.clock_after_id, self.queue_after_id, self.progress_reset_after_id]:
            if after_id:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self.clock_after_id = None
        self.queue_after_id = None
        self.progress_reset_after_id = None
        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def small_button(self, parent: tk.Widget, text: str, command: Callable, tooltip: str = "") -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=BUTTON_BG,
            fg=TEXT,
            activebackground=BUTTON_HOVER,
            activeforeground=TEXT,
            relief="flat",
            bd=0,
            padx=12,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            justify="center",
            wraplength=150,
        )
        if tooltip:
            ToolTip(button, tooltip)
        button.bind("<Enter>", lambda _event: button.configure(bg=BUTTON_HOVER if button["bg"] != CYAN else CYAN), add="+")
        button.bind("<Leave>", lambda _event: self._refresh_button_color(button), add="+")
        return button

    def _refresh_button_color(self, button: tk.Button) -> None:
        if button in [getattr(self, "clock_12_btn", None), getattr(self, "clock_24_btn", None)]:
            self._refresh_clock_buttons()
        else:
            button.configure(bg=BUTTON_BG)

    def accent_button(self, parent: tk.Widget, text: str, command: Callable, tooltip: str = "", accent: str = CYAN) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=accent,
            fg="#061018",
            activebackground="#a7f3ff",
            activeforeground="#061018",
            relief="flat",
            bd=0,
            padx=14,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        if tooltip:
            ToolTip(button, tooltip)
        return button

    def card(self, parent: tk.Widget, title: str, value: str, detail: str = "", accent: str = CYAN, row: int = 0, col: int = 0) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        frame.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        parent.grid_columnconfigure(col, weight=1)
        tk.Frame(frame, bg=accent, height=3).pack(fill="x", pady=(0, 10))
        tk.Label(frame, text=title.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w")
        raw_value = str(value or "Unavailable")
        display_value = hard_wrap_text(raw_value, 22)
        value_font_size = 13 if len(raw_value) > 36 else 16 if len(raw_value) > 18 else 18
        value_label = responsive_label(
            frame,
            display_value,
            PANEL,
            TEXT,
            ("Segoe UI", value_font_size, "bold"),
            min_wrap=150,
            margin=12,
        )
        value_label.pack(anchor="w", fill="x", pady=(5, 3))
        if detail:
            detail_label = responsive_label(frame, detail, PANEL, SUBTLE, ("Segoe UI", 9), min_wrap=150, margin=12)
            detail_label.pack(anchor="w", fill="x")
        return frame

    def section_title(self, parent: tk.Widget, title: str, subtitle: str = "") -> None:
        top = tk.Frame(parent, bg=BG)
        top.pack(fill="x", pady=(0, 12))
        tk.Label(top, text=title, bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(top, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10), wraplength=840, justify="left").pack(anchor="w", pady=(4, 0))

    def section_title_grid(self, parent: tk.Widget, title: str, subtitle: str = "", row: int = 0, column: int = 0, columnspan: int = 1) -> None:
        top = tk.Frame(parent, bg=BG)
        top.grid(row=row, column=column, columnspan=columnspan, sticky="ew", pady=(8, 12))
        tk.Label(top, text=title, bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(top, text=subtitle, bg=BG, fg=MUTED, font=("Segoe UI", 10), wraplength=840, justify="left").pack(anchor="w", pady=(4, 0))

    def info_panel(self, parent: tk.Widget, title: str, body: str, accent: str = CYAN) -> tk.Frame:
        frame = tk.Frame(parent, bg=PANEL_3, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        frame.pack(fill="x", pady=6)
        tk.Label(frame, text=title, bg=PANEL_3, fg=accent, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        body_label = responsive_label(frame, body, PANEL_3, MUTED, ("Segoe UI", 9), min_wrap=180, margin=28)
        body_label.pack(anchor="w", fill="x", pady=(4, 0))
        return frame

    def start_task(self, label: str, worker: Callable, on_success: Callable | None = None) -> None:
        if self.is_closing:
            return
        self.set_status(label)
        self.set_progress(0, "Starting")

        def runner():
            try:
                result = worker()
                if not self.is_closing:
                    self.post_ui(self._task_success, label, result, on_success)
            except Exception as exc:
                if not self.is_closing:
                    self.post_ui(self._task_error, label, exc)

        threading.Thread(target=runner, daemon=True).start()

    def _task_success(self, label: str, result, on_success: Callable | None) -> None:
        if self.is_closing:
            return
        if on_success:
            on_success(result)
        self.set_status(label.replace("...", " complete."))
        self.set_progress(100, "Done")
        try:
            self.progress_reset_after_id = self.root.after(1800, self.reset_progress)
        except (tk.TclError, RuntimeError):
            pass

    def _task_error(self, label: str, exc: Exception) -> None:
        if self.is_closing:
            return
        if isinstance(exc, RuntimeError) and "main thread is not in main loop" in str(exc):
            self.set_status("Refresh was interrupted before the window was ready. Click Quick Refresh or Full Scan to try again.")
            self.set_progress(0, "")
            return
        self.set_status(f"{label.replace('...', '')} failed: {exc}")
        self.set_progress(0, "Error")
        messagebox.showerror(APP_NAME, f"{label}\n\n{type(exc).__name__}: {exc}")

    def refresh_all(self) -> None:
        include_public_ip = bool(self.public_ip_on_refresh.get())

        def worker():
            self.schedule_progress(5, "Profiles")
            profiles = get_wifi_profiles()
            self.schedule_progress(25, "Nearby")
            nearby = get_nearby_networks()
            self.schedule_progress(45, "Interface")
            interface = get_wifi_interface()
            self.schedule_progress(65, "IP data")
            ips = detect_ips(include_public=include_public_ip)
            self.schedule_progress(80, "Adapters")
            adapters, adapter_note = get_network_adapter_inventory()
            self.schedule_progress(90, "Drivers")
            drivers, driver_note = get_network_driver_inventory()
            self.schedule_progress(97, "Finishing")
            return {
                "profiles": profiles,
                "nearby": nearby,
                "interface": interface,
                "ips": ips,
                "adapters": adapters,
                "adapter_note": adapter_note,
                "drivers": drivers,
                "driver_note": driver_note,
            }

        def done(data):
            self.profile_names = data["profiles"]
            self.nearby_networks = data["nearby"]
            self.interface_info = data["interface"]
            self.ip_info = data["ips"]
            self.adapter_inventory = data["adapters"]
            self.adapter_inventory_note = data["adapter_note"]
            self.driver_inventory = data["drivers"]
            self.driver_inventory_note = data["driver_note"]
            self.profiles_loaded = True
            self.nearby_loaded = True
            self.ip_loaded = True
            self.adapters_loaded = True
            self.drivers_loaded = True
            self.render_current_page()

        self.start_task("Running full network scan...", worker, done)

    def refresh_quick(self) -> None:
        def worker():
            self.schedule_progress(20, "WiFi")
            interface = get_wifi_interface()
            self.schedule_progress(70, "Local IP")
            ips = detect_quick_ips()
            self.schedule_progress(95, "Ready")
            return {"interface": interface, "ips": ips}

        def done(data):
            self.interface_info = data["interface"]
            self.ip_info = data["ips"]
            self.ip_loaded = True
            self.render_current_page()

        self.start_task("Refreshing quick dashboard data...", worker, done)

    def render_current_page(self) -> None:
        page = self.current_page
        self.navigate(page)

    def show_dashboard(self) -> None:
        self.current_page = "Dashboard"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(
            inner,
            "Dashboard",
            "A clean overview of the current WiFi connection, IP status, inventory state, and primary actions.",
        )

        cards = tk.Frame(inner, bg=BG)
        cards.pack(fill="x")
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")
        ssid = self.interface_info.get("ssid") or "Not connected"
        state = self.interface_info.get("state") or "Unknown"
        signal = self.interface_info.get("signal") or "No signal data"
        self.card(cards, "Current WiFi", ssid, f"{state} - Signal {signal}", GREEN if state.lower() == "connected" else YELLOW, 0, 0)
        self.card(cards, "Local IP", self.ip_info.local_primary or first_ip(self.ip_info) if self.ip_loaded else "Not scanned", "Use Quick Refresh for local IP or Full Scan for all sources.", CYAN if self.ip_loaded else YELLOW, 0, 1)
        self.card(cards, "Public IPv4", self.ip_info.public_ipv4 or "Not scanned", self.ip_info.public_ipv4_source or "Enable public IP scan in Settings.", PURPLE, 0, 2)
        self.card(cards, "Saved Profiles", str(len(self.profile_names)) if self.profiles_loaded else "Not loaded", "Open WiFi Profiles or run Full Scan.", CYAN if self.profiles_loaded else YELLOW, 1, 0)
        self.card(cards, "Nearby Networks", str(len(self.nearby_networks)) if self.nearby_loaded else "Not loaded", "Open Nearby Networks to scan visible WiFi.", GREEN if self.nearby_loaded else YELLOW, 1, 1)
        gateway_text = ", ".join(self.ip_info.gateways[:2]) or "Unavailable"
        dns_text = ", ".join(self.ip_info.dns_servers[:3]) or "Unavailable"
        self.card(cards, "Gateway / DNS", gateway_text, f"DNS: {dns_text}", YELLOW, 1, 2)
        quick = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        quick.pack(fill="x", pady=(16, 8))
        tk.Label(quick, text="Main Actions", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Label(quick, text="Use Quick Refresh for a fast update. Use Full Scan only when you want profiles, nearby networks, adapters, drivers, and optional public IP data.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9), wraplength=880, justify="left").pack(anchor="w", pady=(2, 10))
        row = tk.Frame(quick, bg=PANEL)
        row.pack(fill="x")
        self.accent_button(row, "Quick Refresh", self.refresh_quick, "Fast update for current WiFi and local IP only.", CYAN).pack(side="left", padx=(0, 8))
        self.small_button(row, "Full Scan", self.refresh_all, "Slower full collection: profiles, nearby networks, interface, IP data, adapters, and drivers.").pack(side="left", padx=(0, 8))
        self.small_button(row, "WiFi Profiles", lambda: self.navigate("WiFi Profiles"), "Show saved WiFi profile details.").pack(side="left", padx=(0, 8))
        self.small_button(row, "Health Check", lambda: self.navigate("Health Check"), "Run gateway, DNS, and internet reachability checks.").pack(side="left", padx=(0, 8))
        self.small_button(row, "Reports", lambda: self.navigate("Reports"), "Open report export options.").pack(side="left", padx=(0, 8))

        visual = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        visual.pack(fill="both", expand=True, pady=(8, 0))
        tk.Label(visual, text="Connection Snapshot", bg=PANEL, fg=TEXT, font=("Segoe UI", 13, "bold")).pack(anchor="w")
        canvas = tk.Canvas(visual, height=170, bg=PANEL, highlightthickness=0)
        canvas.pack(fill="x", pady=(12, 0))
        self.draw_snapshot(canvas)

    def draw_snapshot(self, canvas: tk.Canvas) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 760)
        labels = [
            ("WiFi signal", safe_percent(self.interface_info.get("signal")), GREEN),
            ("Saved profiles", min(100, len(self.profile_names) * 4), CYAN),
            ("Nearby networks", min(100, len(self.nearby_networks) * 5), PURPLE),
            ("IP confidence", ip_confidence(self.ip_info), YELLOW),
        ]
        y = 24
        for label, value, color in labels:
            canvas.create_text(12, y, text=label, fill=MUTED, anchor="w", font=("Segoe UI", 10, "bold"))
            canvas.create_rectangle(150, y - 8, width - 24, y + 8, fill="#0a141e", outline=BORDER)
            filled = 150 + int((width - 174) * (value / 100))
            canvas.create_rectangle(150, y - 8, filled, y + 8, fill=color, outline="")
            canvas.create_text(width - 22, y, text=f"{value}%", fill=TEXT, anchor="e", font=("Segoe UI", 9))
            y += 36
        canvas.create_text(12, y + 16, text="Tip: refresh after connecting to a different network to update the dashboard.", fill=SUBTLE, anchor="w", font=("Segoe UI", 9))

    def show_profiles(self) -> None:
        self.current_page = "WiFi Profiles"
        body = self.clear_content()
        body.grid_columnconfigure(0, weight=3)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(1, weight=1)

        header = tk.Frame(body, bg=BG)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        tk.Label(header, text="WiFi Profiles", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(side="left")
        self.accent_button(header, "Refresh Profiles", self.refresh_profiles, "Reload the saved Windows WiFi profile list.", CYAN).pack(side="right")

        left = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)
        tk.Label(left, text="Saved Networks", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        search_row = tk.Frame(left, bg=PANEL)
        search_row.grid(row=1, column=0, sticky="ew", pady=(10, 8))
        search_row.grid_columnconfigure(0, weight=1)
        self.profile_search = tk.StringVar()
        entry = tk.Entry(search_row, textvariable=self.profile_search, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        entry.grid(row=0, column=0, sticky="ew", ipady=8)
        ToolTip(entry, "Type part of a network name to filter the saved profile list.")
        self.profile_search.trace_add("write", lambda *_: self.populate_profile_table())
        self.small_button(search_row, "Clear", lambda: self.profile_search.set(""), "Clear the search filter.").grid(row=0, column=1, padx=(8, 0))

        columns = ("name", "status")
        self.profile_tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        self.profile_tree.heading("name", text="Profile")
        self.profile_tree.heading("status", text="Detail Status")
        self.profile_tree.column("name", width=320, anchor="w")
        self.profile_tree.column("status", width=150, anchor="w")
        self.profile_tree.grid(row=2, column=0, sticky="nsew")
        self.profile_tree.bind("<<TreeviewSelect>>", self.on_profile_selected)
        ToolTip(self.profile_tree, "Select a saved network to load authentication, encryption, and password details.")

        right = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        right.grid(row=1, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(0, weight=1)
        tk.Label(right, text="Selected Profile", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.profile_detail_frame = tk.Frame(right, bg=PANEL)
        self.profile_detail_frame.grid(row=1, column=0, sticky="ew", pady=(12, 8))
        buttons = tk.Frame(right, bg=PANEL)
        buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self.small_button(buttons, "Copy Password", self.copy_selected_password, "Copy the selected profile password to the clipboard when available.").pack(side="left", padx=(0, 8))
        self.small_button(buttons, "QR Connect", self.show_selected_qr, "Show a WiFi QR payload and QR image when optional QR libraries are installed.").pack(side="left", padx=(0, 8))
        self.small_button(buttons, "Export CSV", self.export_profiles_csv, "Export saved profile details to a CSV file.").pack(side="left")

        self.populate_profile_table()
        self.render_profile_detail(None)

    def refresh_profiles(self) -> None:
        def worker():
            self.schedule_progress(20, "Profiles")
            names = get_wifi_profiles()
            self.schedule_progress(90, "Loaded")
            return names

        def done(names):
            self.profile_names = names
            self.profiles_loaded = True
            self.populate_profile_table()
            self.render_profile_detail(None)

        self.start_task("Refreshing saved WiFi profiles...", worker, done)

    def populate_profile_table(self) -> None:
        if not hasattr(self, "profile_tree"):
            return
        for row in self.profile_tree.get_children():
            self.profile_tree.delete(row)
        term = self.profile_search.get().lower() if hasattr(self, "profile_search") else ""
        for name in self.profile_names:
            if term and term not in name.lower():
                continue
            status = "Loaded" if name in self.profile_details else "Select to load"
            self.profile_tree.insert("", "end", iid=name, values=(name, status))

    def on_profile_selected(self, _event=None) -> None:
        selection = self.profile_tree.selection()
        if not selection:
            return
        name = selection[0]
        self.selected_profile_name = name
        if name in self.profile_details:
            self.render_profile_detail(self.profile_details[name])
            return

        def worker():
            self.schedule_progress(25, "Profile")
            return get_profile_detail(name)

        def done(profile: WifiProfile):
            self.profile_details[name] = profile
            self.populate_profile_table()
            self.render_profile_detail(profile)

        self.start_task(f"Loading profile details for {name}...", worker, done)

    def render_profile_detail(self, profile: WifiProfile | None) -> None:
        for child in self.profile_detail_frame.winfo_children():
            child.destroy()
        if not profile:
            text = "Select a network on the left to view details. Password data is read locally from Windows when available."
            tk.Label(self.profile_detail_frame, text=text, bg=PANEL, fg=MUTED, justify="left", wraplength=360, font=("Segoe UI", 10)).pack(anchor="w")
            return

        fields = [
            ("Network name", profile.name),
            ("Authentication", profile.authentication),
            ("Encryption", profile.encryption),
            ("Connection mode", profile.connection_mode or "Unavailable"),
            ("Password", profile.password or "(not returned)"),
        ]
        for label, value in fields:
            row = tk.Frame(self.profile_detail_frame, bg=PANEL)
            row.pack(fill="x", pady=5)
            tk.Label(row, text=label, bg=PANEL, fg=SUBTLE, font=("Segoe UI", 9, "bold"), width=17, anchor="w").pack(side="left")
            value_text = hard_wrap_text(str(value), 32)
            value_label = responsive_label(row, value_text, PANEL, TEXT, ("Segoe UI", 10), min_wrap=150, margin=150)
            value_label.pack(side="left", fill="x", expand=True)
        if profile.notes:
            self.info_panel(self.profile_detail_frame, "Note", profile.notes, YELLOW)

    def get_selected_profile(self) -> WifiProfile | None:
        if not self.selected_profile_name:
            messagebox.showinfo(APP_NAME, "Select a WiFi profile first.")
            return None
        profile = self.profile_details.get(self.selected_profile_name)
        if not profile:
            messagebox.showinfo(APP_NAME, "Profile details are still loading. Select it again or wait a moment.")
            return None
        return profile

    def copy_selected_password(self) -> None:
        profile = self.get_selected_profile()
        if not profile:
            return
        if not profile.password:
            messagebox.showinfo(APP_NAME, "No password was returned for this profile.")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(profile.password)
        self.set_status(f"Copied password for {profile.name}.")

    def show_selected_qr(self) -> None:
        profile = self.get_selected_profile()
        if not profile:
            return
        payload = wifi_qr_payload(profile.name, profile.password, profile.authentication)
        dialog = tk.Toplevel(self.root)
        dialog.title("WiFi QR Connect")
        dialog.geometry("520x560")
        dialog.minsize(500, 520)
        dialog.configure(bg=BG)
        set_app_icon(dialog)
        dialog.transient(self.root)
        tk.Label(dialog, text="WiFi QR Connect", bg=BG, fg=TEXT, font=("Segoe UI", 16, "bold")).pack(anchor="w", padx=18, pady=(18, 4))
        tk.Label(dialog, text=profile.name, bg=BG, fg=CYAN, font=("Segoe UI", 11, "bold"), wraplength=390).pack(anchor="w", padx=18)
        qr_frame = tk.Frame(dialog, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        qr_frame.pack(fill="both", expand=True, padx=18, pady=14)
        qr_ready = False
        try:
            import qrcode
            from PIL import ImageTk

            image = qrcode.make(payload).resize((220, 220))
            photo = ImageTk.PhotoImage(image)
            label = tk.Label(qr_frame, image=photo, bg=PANEL)
            label.image = photo
            label.pack(pady=(4, 12))
            qr_ready = True
        except Exception:
            tk.Label(
                qr_frame,
                text="Optional QR libraries are not installed. Use Install QR Support, then reopen this QR window to display and download a scannable QR image.",
                bg=PANEL,
                fg=YELLOW,
                font=("Segoe UI", 9),
                justify="left",
                wraplength=350,
            ).pack(anchor="w", pady=(0, 12))
        text = tk.Text(qr_frame, height=5, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word")
        text.insert("1.0", payload)
        text.configure(state="disabled")
        text.pack(fill="x")
        buttons = tk.Frame(dialog, bg=BG)
        buttons.pack(fill="x", padx=18, pady=(0, 16))
        self.small_button(buttons, "Copy Payload", lambda: self.copy_text(payload, "Copied QR payload."), "Copy the WiFi QR payload text.").grid(row=0, column=0, padx=(0, 8), pady=4, sticky="ew")
        self.small_button(buttons, "Download Payload", lambda: self.save_qr_payload(payload, profile.name), "Download the WiFi QR payload as a text file.").grid(row=0, column=1, padx=(0, 8), pady=4, sticky="ew")
        self.small_button(buttons, "Copy SSID", lambda: self.copy_text(profile.name, "Copied SSID."), "Copy the selected network name.").grid(row=0, column=2, padx=(0, 8), pady=4, sticky="ew")
        self.small_button(buttons, "Copy Password", lambda: self.copy_text(profile.password, "Copied password.") if profile.password else messagebox.showinfo(APP_NAME, "No password was returned for this profile."), "Copy the selected profile password when available.").grid(row=1, column=0, padx=(0, 8), pady=4, sticky="ew")
        self.small_button(buttons, "Download QR PNG", lambda: self.save_qr_png(payload, profile.name), "Download a scannable QR code image as a PNG file.").grid(row=1, column=1, padx=(0, 8), pady=4, sticky="ew")
        if not qr_ready:
            self.small_button(buttons, "Install QR Support", self.launch_dependency_installer, "Launch install_requirements.bat to install qrcode and Pillow.").grid(row=1, column=2, padx=(0, 8), pady=4, sticky="ew")
        for col in range(3):
            buttons.grid_columnconfigure(col, weight=1)

    def save_qr_payload(self, payload: str, ssid: str) -> None:
        path = filedialog.asksaveasfilename(
            title="Download WiFi QR Payload",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"{safe_filename(ssid)}_wifi_qr_payload.txt",
        )
        if not path:
            return
        Path(path).write_text(payload, encoding="utf-8")
        self.set_status(f"Downloaded QR payload: {path}")

    def save_qr_png(self, payload: str, ssid: str) -> None:
        try:
            import qrcode
        except Exception:
            messagebox.showinfo(APP_NAME, "QR image support is not installed yet. Use Install QR Support, then try again.")
            return
        path = filedialog.asksaveasfilename(
            title="Download WiFi QR PNG",
            defaultextension=".png",
            filetypes=[("PNG images", "*.png"), ("All files", "*.*")],
            initialfile=f"{safe_filename(ssid)}_wifi_qr.png",
        )
        if not path:
            return
        image = qrcode.make(payload)
        image.save(path)
        self.set_status(f"Downloaded QR image: {path}")

    def launch_dependency_installer(self) -> None:
        installer = Path(__file__).with_name("install_requirements.bat")
        if not installer.exists():
            messagebox.showinfo(APP_NAME, "install_requirements.bat was not found in this app folder.")
            return
        try:
            os.startfile(str(installer))
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not launch the installer.\n\n{exc}")

    def copy_text(self, value: str, status: str = "Copied.") -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.set_status(status)

    def show_nearby(self) -> None:
        self.current_page = "Nearby Networks"
        body = self.clear_content()
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)
        header = tk.Frame(body, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tk.Label(header, text="Nearby Networks", bg=BG, fg=TEXT, font=("Segoe UI", 18, "bold")).pack(side="left")
        self.accent_button(header, "Scan Nearby", self.scan_nearby, "Run a Windows WiFi scan and list visible networks.", CYAN).pack(side="right")

        summary = nearby_summary(self.nearby_networks)
        cards = tk.Frame(body, bg=BG)
        cards.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="nearby")
        self.card(cards, "Visible Networks", str(summary["total"]), f"Secure: {summary['secure']}  Open: {summary['open']}", CYAN, 0, 0)
        self.card(cards, "Strongest Signal", str(summary["strongest"]), str(summary["strongest_signal"]), GREEN, 0, 1)
        self.card(cards, "Bands", f"2.4: {summary['2.4 GHz']}  5: {summary['5 GHz']}", f"6 GHz: {summary['6 GHz']}", PURPLE, 0, 2)

        controls = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=10)
        controls.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)
        tk.Label(controls, text="Search", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.nearby_search = tk.StringVar(value=getattr(self, "_nearby_search_value", ""))
        search_entry = tk.Entry(controls, textvariable=self.nearby_search, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        search_entry.grid(row=0, column=1, sticky="ew", ipady=8)
        ToolTip(search_entry, "Filter nearby networks by SSID, security, band, channel, or signal quality.")
        self.nearby_filter = tk.StringVar(value=getattr(self, "_nearby_filter_value", "All"))
        filter_box = ttk.Combobox(controls, textvariable=self.nearby_filter, values=["All", "Secure", "Open", "2.4 GHz", "5 GHz", "6 GHz"], width=12, state="readonly")
        filter_box.grid(row=0, column=2, padx=(8, 0), sticky="ew")
        ToolTip(filter_box, "Limit the table to secure, open, or a specific WiFi band.")
        self.small_button(controls, "Clear", self.clear_nearby_filters, "Clear nearby network filters.").grid(row=0, column=3, padx=(8, 0))
        self.small_button(controls, "Copy Selected", self.copy_selected_nearby, "Copy selected nearby network details.").grid(row=0, column=4, padx=(8, 0))
        self.small_button(controls, "Export CSV", self.export_nearby_csv, "Export the current nearby network table to CSV.").grid(row=0, column=5, padx=(8, 0))
        self.nearby_search.trace_add("write", lambda *_: self._nearby_filter_changed())
        self.nearby_filter.trace_add("write", lambda *_: self._nearby_filter_changed())

        panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.grid_rowconfigure(0, weight=1)
        panel.grid_columnconfigure(0, weight=1)
        columns = ("ssid", "signal", "quality", "band", "channel", "auth", "encryption", "bssid")
        self.nearby_tree = ttk.Treeview(panel, columns=columns, show="headings")
        headings = {
            "ssid": "SSID",
            "signal": "Signal",
            "quality": "Quality",
            "band": "Band",
            "channel": "Channel",
            "auth": "Security",
            "encryption": "Encryption",
            "bssid": "Radios",
        }
        widths = {"ssid": 250, "signal": 85, "quality": 90, "band": 85, "channel": 85, "auth": 170, "encryption": 120, "bssid": 70}
        for col in columns:
            self.nearby_tree.heading(col, text=headings[col])
            self.nearby_tree.column(col, width=widths[col], anchor="w")
        self.nearby_tree.grid(row=0, column=0, sticky="nsew")
        ToolTip(self.nearby_tree, "Nearby networks are sorted by strongest detected signal. Hidden SSIDs may appear without a name.")
        self.populate_nearby_table()

    def scan_nearby(self) -> None:
        def worker():
            self.schedule_progress(10, "Scanning")
            networks = get_nearby_networks()
            self.schedule_progress(90, "Sorting")
            return networks

        def done(networks):
            self.nearby_networks = networks
            self.nearby_loaded = True
            self.populate_nearby_table()
            self.render_current_page()

        self.start_task("Scanning nearby WiFi networks...", worker, done)

    def _nearby_filter_changed(self) -> None:
        self._nearby_search_value = self.nearby_search.get() if hasattr(self, "nearby_search") else ""
        self._nearby_filter_value = self.nearby_filter.get() if hasattr(self, "nearby_filter") else "All"
        self.populate_nearby_table()

    def clear_nearby_filters(self) -> None:
        if hasattr(self, "nearby_search"):
            self.nearby_search.set("")
        if hasattr(self, "nearby_filter"):
            self.nearby_filter.set("All")
        self.populate_nearby_table()

    def filtered_nearby_networks(self) -> list[NearbyNetwork]:
        term = (self.nearby_search.get() if hasattr(self, "nearby_search") else getattr(self, "_nearby_search_value", "")).lower().strip()
        mode = self.nearby_filter.get() if hasattr(self, "nearby_filter") else getattr(self, "_nearby_filter_value", "All")
        output = []
        for net in self.nearby_networks:
            band = guess_band(net.channel, net.radio_type)
            quality = signal_quality(net.signal)
            haystack = " ".join([net.ssid, net.signal, quality, band, net.channel, net.authentication, net.encryption]).lower()
            if term and term not in haystack:
                continue
            if mode == "Secure" and "open" in (net.authentication or "").lower():
                continue
            if mode == "Open" and "open" not in (net.authentication or "").lower():
                continue
            if mode in {"2.4 GHz", "5 GHz", "6 GHz"} and band != mode:
                continue
            output.append(net)
        return output

    def populate_nearby_table(self) -> None:
        if not hasattr(self, "nearby_tree"):
            return
        for row in self.nearby_tree.get_children():
            self.nearby_tree.delete(row)
        for index, net in enumerate(self.filtered_nearby_networks()):
            band = guess_band(net.channel, net.radio_type)
            self.nearby_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    net.ssid,
                    net.signal,
                    signal_quality(net.signal),
                    band,
                    net.channel,
                    net.authentication,
                    net.encryption,
                    net.bssid_count,
                ),
            )

    def selected_nearby_network(self) -> NearbyNetwork | None:
        if not hasattr(self, "nearby_tree"):
            return None
        selection = self.nearby_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Select a nearby network first.")
            return None
        try:
            return self.filtered_nearby_networks()[int(selection[0])]
        except Exception:
            return None

    def copy_selected_nearby(self) -> None:
        net = self.selected_nearby_network()
        if not net:
            return
        text = "\n".join(
            [
                f"SSID: {net.ssid}",
                f"Signal: {net.signal}",
                f"Quality: {signal_quality(net.signal)}",
                f"Band: {guess_band(net.channel, net.radio_type)}",
                f"Channel: {net.channel}",
                f"Security: {net.authentication}",
                f"Encryption: {net.encryption}",
                f"Radios: {net.bssid_count}",
            ]
        )
        self.copy_text(text, "Copied nearby network details.")

    def export_nearby_csv(self) -> None:
        networks = self.filtered_nearby_networks()
        if not networks:
            messagebox.showinfo(APP_NAME, "No nearby networks are visible with the current filter.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Nearby Networks CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"nearby_networks_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["ssid", "signal", "quality", "band", "channel", "authentication", "encryption", "radios"])
            writer.writeheader()
            for net in networks:
                writer.writerow(
                    {
                        "ssid": net.ssid,
                        "signal": net.signal,
                        "quality": signal_quality(net.signal),
                        "band": guess_band(net.channel, net.radio_type),
                        "channel": net.channel,
                        "authentication": net.authentication,
                        "encryption": net.encryption,
                        "radios": net.bssid_count,
                    }
                )
        self.set_status(f"Exported nearby networks CSV: {path}")

    def show_ip_intelligence(self) -> None:
        self.current_page = "IP Intelligence"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(inner, "IP Intelligence", "Multiple detection methods help find local IPs, gateway, DNS, public IPv4, and public IPv6 even when one source fails.")
        actions = tk.Frame(inner, bg=BG)
        actions.pack(fill="x", pady=(0, 10))
        self.accent_button(actions, "Run Full IP Scan", self.run_full_ip_scan, "Runs socket, hostname, ipconfig, PowerShell, and public-IP checks.", CYAN).pack(side="left", padx=(0, 8))
        self.small_button(actions, "Copy IP Summary", self.copy_ip_summary, "Copy the current IP detection summary to the clipboard.").pack(side="left")

        cards = tk.Frame(inner, bg=BG)
        cards.pack(fill="x")
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="cards")
        self.card(cards, "Primary Local IP", self.ip_info.local_primary or first_ip(self.ip_info), "Detected by opening a local route to the internet.", GREEN, 0, 0)
        self.card(cards, "Hostname IPs", ", ".join(self.ip_info.hostname_ips) or "Unavailable", f"Host: {self.ip_info.hostname or 'Unknown'}", CYAN, 0, 1)
        self.card(cards, "PowerShell IPs", ", ".join(self.ip_info.powershell_ips) or "Unavailable", "Adapter-level IPv4 detection.", PURPLE, 0, 2)
        self.card(cards, "Default Gateway", ", ".join(self.ip_info.gateways) or "Unavailable", "Usually your router or upstream gateway.", YELLOW, 1, 0)
        self.card(cards, "DNS Servers", ", ".join(self.ip_info.dns_servers) or "Unavailable", "Name servers used by this machine.", CYAN, 1, 1)
        self.card(cards, "Public IPv6", self.ip_info.public_ipv6 or "Unavailable", self.ip_info.public_ipv6_source or "IPv6 may not be enabled.", PURPLE, 1, 2)

        adapter_panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        adapter_panel.pack(fill="both", expand=True, pady=(14, 0))
        tk.Label(adapter_panel, text="Adapter Details", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        columns = ("adapter", "ipv4", "gateway", "dns")
        table = ttk.Treeview(adapter_panel, columns=columns, show="headings", height=7)
        for col, text, width in [("adapter", "Adapter", 280), ("ipv4", "IPv4", 150), ("gateway", "Gateway", 150), ("dns", "DNS", 260)]:
            table.heading(col, text=text)
            table.column(col, width=width, anchor="w")
        table.pack(fill="both", expand=True, pady=(10, 0))
        for adapter in self.ip_info.adapters:
            table.insert("", "end", values=(adapter.get("name", ""), adapter.get("ipv4", ""), adapter.get("gateway", ""), adapter.get("dns", "")))
        if self.ip_info.raw_errors:
            self.info_panel(inner, "Detection Notes", "\n".join(self.ip_info.raw_errors[:5]), YELLOW)

    def show_health_check(self) -> None:
        self.current_page = "Health Check"
        body = self.clear_content()
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(3, weight=1)
        self.section_title_grid(
            body,
            "Health Check",
            "Run a quick local connectivity test and get a practical network health score.",
        )

        actions = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        actions.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.accent_button(actions, "Run Health Check", self.run_health_check, "Tests local IP, gateway, DNS resolution, internet ping, and public IP status.", CYAN).pack(side="left", padx=(0, 8))
        self.small_button(actions, "Copy Results", self.copy_health_results, "Copy the current health-check table to the clipboard.").pack(side="left", padx=(0, 8))

        cards = tk.Frame(body, bg=BG)
        cards.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="health")
        score = health_score(self.health_checks)
        score_value = f"{score}%" if self.health_checks else "Not run"
        self.card(cards, "Health Score", score_value, health_status(score) if self.health_checks else "Click Run Health Check.", GREEN if score >= 80 else YELLOW if score >= 50 else RED, 0, 0)
        self.card(cards, "Gateway", self.ip_info.gateways[0] if self.ip_info.gateways else "Unavailable", "Router reachability check uses this address.", YELLOW, 0, 1)
        self.card(cards, "DNS", ", ".join(self.ip_info.dns_servers[:2]) or "Unavailable", "DNS resolve check uses your configured servers.", CYAN, 0, 2)

        panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        panel.grid(row=3, column=0, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(1, weight=1)
        tk.Label(panel, text="Connectivity Results", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        columns = ("name", "status", "detail")
        self.health_tree = ttk.Treeview(panel, columns=columns, show="headings")
        for col, label, width in [("name", "Check", 180), ("status", "Status", 90), ("detail", "Details", 620)]:
            self.health_tree.heading(col, text=label)
            self.health_tree.column(col, width=width, anchor="w")
        self.health_tree.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        ToolTip(self.health_tree, "Pass means healthy, Warn means worth checking, Fail means the check did not work, and Info is neutral context.")
        self.populate_health_table()

    def populate_health_table(self) -> None:
        if not hasattr(self, "health_tree"):
            return
        for row in self.health_tree.get_children():
            self.health_tree.delete(row)
        if not self.health_checks:
            self.health_tree.insert("", "end", values=("Not run", "Info", "Click Run Health Check to test this network."))
            return
        for check in self.health_checks:
            self.health_tree.insert("", "end", values=(check.name, check.status, check.detail))

    def run_health_check(self) -> None:
        def worker():
            self.schedule_progress(10, "Preparing")
            info = self.ip_info
            if not (info.local_primary or first_ip(info) or info.gateways or info.dns_servers):
                self.schedule_progress(35, "IP data")
                info = detect_ips(include_public=False)
            self.schedule_progress(60, "Connectivity")
            checks = run_connectivity_checks(info)
            self.schedule_progress(90, "Scoring")
            return info, checks

        def done(result):
            info, checks = result
            self.ip_info = info
            self.health_checks = checks
            self.render_current_page()

        self.start_task("Running network health check...", worker, done)

    def health_results_text(self) -> str:
        lines = [
            f"{APP_NAME} {APP_VERSION} Health Check",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Score: {health_score(self.health_checks)}%" if self.health_checks else "Score: Not run",
            "",
        ]
        if not self.health_checks:
            lines.append("No health check has been run yet.")
        else:
            for check in self.health_checks:
                lines.append(f"{check.status:>4}  {check.name}: {check.detail}")
        return "\n".join(lines)

    def copy_health_results(self) -> None:
        self.copy_text(self.health_results_text(), "Copied health-check results.")

    def open_router_gateway(self) -> None:
        gateway = self.ip_info.gateways[0] if self.ip_info.gateways else ""
        if not gateway:
            messagebox.showinfo(APP_NAME, "No default gateway is loaded yet. Run Full IP Scan or Health Check first.")
            return
        open_url(f"http://{gateway}")

    def open_wifi_settings(self) -> None:
        if not is_windows():
            messagebox.showinfo(APP_NAME, "Windows WiFi Settings is only available on Windows.")
            return
        try:
            os.startfile("ms-settings:network-wifi")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open Windows WiFi Settings.\n\n{exc}")

    def show_drivers_folders(self) -> None:
        self.current_page = "Drivers & Folders"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(
            inner,
            "Drivers & Folders",
            "One-click access to Windows network driver tools, common folders, app folders, and network adapter driver inventory.",
        )

        cards = tk.Frame(inner, bg=BG)
        cards.pack(fill="x")
        cards.grid_columnconfigure((0, 1, 2), weight=1, uniform="driver_cards")
        adapter_value = str(len(self.adapter_inventory)) if self.adapters_loaded else "Not loaded"
        adapter_detail = "Speed, MAC, and connection state." if self.adapters_loaded else "Run Full Scan or Refresh Adapters."
        self.card(cards, "Network Adapters", adapter_value, adapter_detail, GREEN if self.adapters_loaded else YELLOW, 0, 0)
        driver_value = str(len(self.driver_inventory)) if self.drivers_loaded else "Not loaded"
        driver_detail = "Signed network driver packages." if self.drivers_loaded else "Run Full Scan or Refresh Drivers."
        self.card(cards, "Network Drivers", driver_value, driver_detail, CYAN if self.drivers_loaded else YELLOW, 0, 1)
        self.card(cards, "QR Support", "Ready" if qr_support_available() else "Install needed", "Scannable QR image support.", PURPLE if qr_support_available() else YELLOW, 0, 2)

        tools_panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        tools_panel.pack(fill="x", pady=(14, 8))
        tk.Label(tools_panel, text="Windows Driver & Network Tools", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(tools_panel, text="Open built-in Windows tools for adapter, driver, and network troubleshooting.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))
        tools_grid = tk.Frame(tools_panel, bg=PANEL)
        tools_grid.pack(fill="x")
        tool_buttons = [
            ("Device Manager", lambda: self.open_system_target("devmgmt.msc", "Device Manager"), "Open Windows Device Manager."),
            ("Network Connections", lambda: self.open_system_target("ncpa.cpl", "Network Connections"), "Open classic network adapter connections."),
            ("Services", lambda: self.open_system_target("services.msc", "Services"), "Open Windows Services."),
            ("Event Viewer", lambda: self.open_system_target("eventvwr.msc", "Event Viewer"), "Open Windows Event Viewer."),
            ("Windows Update", lambda: self.open_system_target("ms-settings:windowsupdate", "Windows Update"), "Open Windows Update settings."),
            ("Optional Updates", lambda: self.open_system_target("ms-settings:windowsupdate-optionalupdates", "Optional Updates"), "Open Optional Updates where driver updates may appear."),
            ("WiFi Settings", self.open_wifi_settings, "Open Windows WiFi settings."),
            ("Router Page", self.open_router_gateway, "Open your detected default gateway in a browser."),
        ]
        self.button_grid(tools_grid, tool_buttons, columns=4)

        folder_panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        folder_panel.pack(fill="x", pady=8)
        tk.Label(folder_panel, text="Folders", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(folder_panel, text="Open app folders, Windows driver folders, and common user folders.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 10))
        folder_grid = tk.Frame(folder_panel, bg=PANEL)
        folder_grid.pack(fill="x")
        windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        downloads = Path.home() / "Downloads"
        documents = Path.home() / "Documents"
        folder_buttons = [
            ("App Folder", lambda: self.open_folder(Path(__file__).resolve().parent), "Open the folder where WiFi Vault Pro is running."),
            ("Config Folder", lambda: self.open_folder(CONFIG_DIR, create=True), "Open the saved settings folder."),
            ("Documents", lambda: self.open_folder(documents), "Open your Documents folder."),
            ("Downloads", lambda: self.open_folder(downloads), "Open your Downloads folder."),
            ("Windows Drivers", lambda: self.open_folder(windows_dir / "System32" / "drivers"), "Open C:\\Windows\\System32\\drivers."),
            ("DriverStore", lambda: self.open_folder(windows_dir / "System32" / "DriverStore" / "FileRepository"), "Open the Windows DriverStore FileRepository."),
            ("Windows INF", lambda: self.open_folder(windows_dir / "INF"), "Open the Windows INF folder where driver setup information files live."),
            ("Temp Folder", lambda: self.open_folder(Path(tempfile.gettempdir())), "Open the current Windows temp folder."),
        ]
        self.button_grid(folder_grid, folder_buttons, columns=4)

        adapter_panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        adapter_panel.pack(fill="both", expand=True, pady=(8, 0))
        adapter_top = tk.Frame(adapter_panel, bg=PANEL)
        adapter_top.pack(fill="x")
        tk.Label(adapter_top, text="Adapter Status", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.accent_button(adapter_top, "Refresh Adapters", self.refresh_adapter_inventory, "Read live network adapter status from Windows.", CYAN).pack(side="right")
        adapter_actions = tk.Frame(adapter_panel, bg=PANEL)
        adapter_actions.pack(fill="x", pady=(8, 8))
        self.small_button(adapter_actions, "Export CSV", self.export_adapter_inventory_csv, "Export the network adapter status table to CSV.").pack(side="left", padx=(0, 8))
        self.small_button(adapter_actions, "Copy Selected", self.copy_selected_adapter_row, "Copy the selected adapter row to the clipboard.").pack(side="left", padx=(0, 8))

        adapter_columns = ("name", "status", "speed", "mac", "media", "index")
        self.adapter_tree = ttk.Treeview(adapter_panel, columns=adapter_columns, show="headings", height=7)
        for col, label, width in [
            ("name", "Adapter", 220),
            ("status", "Status", 95),
            ("speed", "Speed", 120),
            ("mac", "MAC Address", 160),
            ("media", "Media", 120),
            ("index", "Index", 70),
        ]:
            self.adapter_tree.heading(col, text=label)
            self.adapter_tree.column(col, width=width, anchor="w")
        self.adapter_tree.pack(fill="both", expand=True)
        ToolTip(self.adapter_tree, "Adapter status comes from Windows Get-NetAdapter and shows connection state, link speed, and MAC address.")
        if self.adapter_inventory_note:
            self.info_panel(adapter_panel, "Adapter Inventory Note", self.adapter_inventory_note, YELLOW)
        self.populate_adapter_table()

        inventory_panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        inventory_panel.pack(fill="both", expand=True, pady=(8, 0))
        inventory_top = tk.Frame(inventory_panel, bg=PANEL)
        inventory_top.pack(fill="x")
        tk.Label(inventory_top, text="Network Driver Inventory", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        self.accent_button(inventory_top, "Refresh Drivers", self.refresh_driver_inventory, "Read signed network driver info from Windows.", CYAN).pack(side="right")
        actions = tk.Frame(inventory_panel, bg=PANEL)
        actions.pack(fill="x", pady=(8, 8))
        self.small_button(actions, "Export CSV", self.export_driver_inventory_csv, "Export the network driver inventory to CSV.").pack(side="left", padx=(0, 8))
        self.small_button(actions, "Copy Selected", self.copy_selected_driver_row, "Copy the selected driver row to the clipboard.").pack(side="left", padx=(0, 8))

        columns = ("device", "manufacturer", "version", "inf", "signed")
        self.driver_tree = ttk.Treeview(inventory_panel, columns=columns, show="headings", height=8)
        for col, label, width in [
            ("device", "Device", 290),
            ("manufacturer", "Manufacturer", 180),
            ("version", "Version", 150),
            ("inf", "INF", 120),
            ("signed", "Signed", 80),
        ]:
            self.driver_tree.heading(col, text=label)
            self.driver_tree.column(col, width=width, anchor="w")
        self.driver_tree.pack(fill="both", expand=True)
        ToolTip(self.driver_tree, "Network adapter driver data comes from Windows signed driver inventory.")
        if self.driver_inventory_note:
            self.info_panel(inventory_panel, "Driver Inventory Note", self.driver_inventory_note, YELLOW)
        self.populate_driver_table()

    def button_grid(self, parent: tk.Widget, buttons: list[tuple[str, Callable, str]], columns: int = 4) -> None:
        for index, (label, command, tip) in enumerate(buttons):
            row = index // columns
            col = index % columns
            button = self.small_button(parent, label, command, tip)
            button.grid(row=row, column=col, sticky="ew", padx=4, pady=4)
        for col in range(columns):
            parent.grid_columnconfigure(col, weight=1)

    def open_folder(self, path: Path, create: bool = False) -> None:
        try:
            if create:
                path.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                messagebox.showinfo(APP_NAME, f"Folder not found:\n{path}")
                return
            os.startfile(str(path))
            self.set_status(f"Opened folder: {path}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open folder.\n\n{path}\n\n{exc}")

    def open_system_target(self, target: str, label: str) -> None:
        if not is_windows():
            messagebox.showinfo(APP_NAME, f"{label} is only available on Windows.")
            return
        try:
            os.startfile(target)
            self.set_status(f"Opened {label}.")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Could not open {label}.\n\n{exc}")

    def refresh_adapter_inventory(self) -> None:
        def worker():
            self.schedule_progress(20, "Adapters")
            result = get_network_adapter_inventory()
            self.schedule_progress(90, "Loaded")
            return result

        def done(result):
            rows, note = result
            self.adapter_inventory = rows
            self.adapter_inventory_note = note
            self.adapters_loaded = True
            self.render_current_page()

        self.start_task("Loading network adapter status...", worker, done)

    def populate_adapter_table(self) -> None:
        if not hasattr(self, "adapter_tree"):
            return
        for row in self.adapter_tree.get_children():
            self.adapter_tree.delete(row)
        if not self.adapter_inventory:
            message = "No adapters found" if self.adapters_loaded else "No adapter inventory loaded"
            action = "Full Scan or Refresh Adapters" if not self.adapters_loaded else (self.adapter_inventory_note or "Scan completed")
            self.adapter_tree.insert("", "end", values=(message, action, "", "", "", ""))
            return
        for index, row in enumerate(self.adapter_inventory):
            self.adapter_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(row.get("name", ""), row.get("status", ""), row.get("speed", ""), row.get("mac", ""), row.get("media", ""), row.get("index", "")),
            )

    def selected_adapter_row(self) -> dict[str, str] | None:
        if not hasattr(self, "adapter_tree"):
            return None
        selection = self.adapter_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Select an adapter row first.")
            return None
        try:
            return self.adapter_inventory[int(selection[0])]
        except Exception:
            return None

    def copy_selected_adapter_row(self) -> None:
        row = self.selected_adapter_row()
        if not row:
            return
        text = "\n".join(f"{key}: {value}" for key, value in row.items())
        self.copy_text(text, "Copied adapter row.")

    def export_adapter_inventory_csv(self) -> None:
        if not self.adapter_inventory:
            messagebox.showinfo(APP_NAME, "Load adapter status first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Network Adapter Status",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"network_adapters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["name", "description", "status", "mac", "speed", "media", "index"])
            writer.writeheader()
            writer.writerows(self.adapter_inventory)
        self.set_status(f"Exported adapter CSV: {path}")

    def refresh_driver_inventory(self) -> None:
        def worker():
            self.schedule_progress(20, "Drivers")
            result = get_network_driver_inventory()
            self.schedule_progress(90, "Loaded")
            return result

        def done(result):
            rows, note = result
            self.driver_inventory = rows
            self.driver_inventory_note = note
            self.drivers_loaded = True
            self.render_current_page()

        self.start_task("Loading network driver inventory...", worker, done)

    def populate_driver_table(self) -> None:
        if not hasattr(self, "driver_tree"):
            return
        for row in self.driver_tree.get_children():
            self.driver_tree.delete(row)
        if not self.driver_inventory:
            message = "No network drivers found" if self.drivers_loaded else "No driver inventory loaded"
            action = "Full Scan or Refresh Drivers" if not self.drivers_loaded else (self.driver_inventory_note or "Scan completed")
            self.driver_tree.insert("", "end", values=(message, action, "", "", ""))
            return
        for index, row in enumerate(self.driver_inventory):
            self.driver_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(row.get("device", ""), row.get("manufacturer", ""), row.get("version", ""), row.get("inf", ""), row.get("signed", "")),
            )

    def selected_driver_row(self) -> dict[str, str] | None:
        if not hasattr(self, "driver_tree"):
            return None
        selection = self.driver_tree.selection()
        if not selection:
            messagebox.showinfo(APP_NAME, "Select a driver row first.")
            return None
        try:
            return self.driver_inventory[int(selection[0])]
        except Exception:
            return None

    def copy_selected_driver_row(self) -> None:
        row = self.selected_driver_row()
        if not row:
            return
        text = "\n".join(f"{key}: {value}" for key, value in row.items())
        self.copy_text(text, "Copied driver row.")

    def export_driver_inventory_csv(self) -> None:
        if not self.driver_inventory:
            messagebox.showinfo(APP_NAME, "Load driver inventory first.")
            return
        path = filedialog.asksaveasfilename(
            title="Export Network Driver Inventory",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"network_drivers_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["device", "manufacturer", "version", "date", "inf", "signed"])
            writer.writeheader()
            writer.writerows(self.driver_inventory)
        self.set_status(f"Exported driver CSV: {path}")

    def run_full_ip_scan(self) -> None:
        include_public_ip = bool(self.public_ip_on_refresh.get())

        def worker():
            self.schedule_progress(10, "Local IP")
            info = detect_ips(include_public=include_public_ip)
            self.schedule_progress(90, "Public IP" if include_public_ip else "IP data")
            return info

        def done(info: IpDetection):
            self.ip_info = info
            self.ip_loaded = True
            self.health_checks = []
            self.render_current_page()

        self.start_task("Running full IP detection...", worker, done)

    def ip_summary(self) -> str:
        info = self.ip_info
        lines = [
            f"{APP_NAME} {APP_VERSION} IP Summary",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Hostname: {info.hostname or 'Unknown'}",
            f"Primary local IP: {info.local_primary or 'Unavailable'}",
            f"Hostname IPs: {', '.join(info.hostname_ips) or 'Unavailable'}",
            f"ipconfig IPs: {', '.join(info.ipconfig_ips) or 'Unavailable'}",
            f"PowerShell IPs: {', '.join(info.powershell_ips) or 'Unavailable'}",
            f"Gateway: {', '.join(info.gateways) or 'Unavailable'}",
            f"DNS: {', '.join(info.dns_servers) or 'Unavailable'}",
            f"Public IPv4: {info.public_ipv4 or 'Unavailable'} {f'({info.public_ipv4_source})' if info.public_ipv4_source else ''}",
            f"Public IPv6: {info.public_ipv6 or 'Unavailable'} {f'({info.public_ipv6_source})' if info.public_ipv6_source else ''}",
        ]
        return "\n".join(lines)

    def copy_ip_summary(self) -> None:
        self.copy_text(self.ip_summary(), "Copied IP summary.")

    def network_snapshot_text(self) -> str:
        lines = [
            f"{APP_NAME} {APP_VERSION} Network Snapshot",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Current WiFi: {self.interface_info.get('ssid', 'Unavailable')}",
            f"WiFi state: {self.interface_info.get('state', 'Unavailable')}",
            f"Signal: {self.interface_info.get('signal', 'Unavailable')}",
            f"Primary local IP: {self.ip_info.local_primary or first_ip(self.ip_info) or 'Unavailable'}",
            f"Gateway: {', '.join(self.ip_info.gateways) or 'Unavailable'}",
            f"DNS: {', '.join(self.ip_info.dns_servers) or 'Unavailable'}",
            f"Public IPv4: {self.ip_info.public_ipv4 or 'Unavailable'}",
            f"Public IPv6: {self.ip_info.public_ipv6 or 'Unavailable'}",
            f"Saved WiFi profiles: {len(self.profile_names)}",
            f"Nearby networks: {len(self.nearby_networks)}",
            f"Network adapters loaded: {len(self.adapter_inventory)}",
            f"Network drivers loaded: {len(self.driver_inventory)}",
            f"Health score: {str(health_score(self.health_checks)) + '%' if self.health_checks else 'Not run'}",
        ]
        if self.adapter_inventory:
            lines.extend(["", "Adapters:"])
            for row in self.adapter_inventory:
                lines.append(f"- {row.get('name', '')}: {row.get('status', '')}, {row.get('speed', '')}, {row.get('mac', '')}")
        return "\n".join(lines)

    def copy_network_snapshot(self) -> None:
        self.copy_text(self.network_snapshot_text(), "Copied network snapshot.")

    def show_tools(self) -> None:
        self.current_page = "Network Tools"
        body = self.clear_content()
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)
        self.section_title_grid(
            body,
            "Network Tools",
            "Diagnostics for everyday troubleshooting. Each command explains what it does and runs locally on this machine.",
        )
        controls = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        controls.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        controls.grid_columnconfigure(1, weight=1)
        controls_header = tk.Frame(controls, bg=PANEL)
        controls_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        tk.Label(controls_header, text="Network Tools", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(controls_header, text="Run diagnostics, choose quick targets, and save or copy results.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))
        tk.Label(controls, text="Target", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).grid(row=1, column=0, sticky="w", padx=(0, 8))
        self.tool_target = tk.StringVar(value="8.8.8.8")
        target_entry = tk.Entry(controls, textvariable=self.tool_target, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 10))
        target_entry.grid(row=1, column=1, sticky="ew", ipady=8)
        ToolTip(target_entry, "Use an IP address or hostname such as 8.8.8.8, github.com, or your router IP.")
        diagnostics = tk.Frame(controls, bg=PANEL)
        diagnostics.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        diagnostic_buttons = [
            ("Ping", self.run_ping, "Checks whether a target replies and how long each reply takes."),
            ("DNS Lookup", self.run_dns_lookup, "Asks DNS which IP addresses belong to a domain name."),
            ("Traceroute", self.run_traceroute, "Shows the network hops between this machine and the target."),
            ("IP Config", self.run_ipconfig_tool, "Shows detailed local adapter configuration from Windows."),
            ("ARP Table", self.run_arp, "Shows recently discovered local network neighbors and MAC addresses."),
            ("Routes", self.run_routes, "Shows where traffic is sent based on destination network."),
            ("Ports", self.run_ports, "Lists listening and active local network connections."),
        ]
        self.button_grid(diagnostics, diagnostic_buttons, columns=4)

        repair = tk.Frame(controls, bg=PANEL)
        repair.grid(row=3, column=0, columnspan=2, sticky="w", pady=(12, 0))
        tk.Label(repair, text="Repair Center", bg=PANEL, fg=SUBTLE, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
        self.small_button(repair, "Flush DNS", lambda: self.run_repair("Flush DNS", ["ipconfig", "/flushdns"]), "Clears the DNS resolver cache.").pack(side="left", padx=(0, 8))
        self.small_button(repair, "Release IP", lambda: self.run_repair("Release IP", ["ipconfig", "/release"]), "Drops current DHCP leases. This can temporarily disconnect networking.").pack(side="left", padx=(0, 8))
        self.small_button(repair, "Renew IP", lambda: self.run_repair("Renew IP", ["ipconfig", "/renew"]), "Requests a fresh DHCP lease from the router.").pack(side="left", padx=(0, 8))
        self.small_button(repair, "Reset Winsock", lambda: self.run_repair("Reset Winsock", ["netsh", "winsock", "reset"]), "Resets the Windows network socket catalog. Restart may be required.").pack(side="left")

        targets = tk.Frame(controls, bg=PANEL)
        targets.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))
        tk.Label(targets, text="Targets", bg=PANEL, fg=SUBTLE, font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 10))
        self.small_button(targets, "Use Gateway", self.use_gateway_target, "Put the detected default gateway into the target box.").pack(side="left", padx=(0, 8))
        self.small_button(targets, "Use DNS", self.use_dns_target, "Put the first detected DNS server into the target box.").pack(side="left", padx=(0, 8))
        self.small_button(targets, "Use GitHub", lambda: self.set_tool_target("github.com"), "Put github.com into the target box.").pack(side="left")

        output_panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        output_panel.grid(row=2, column=0, sticky="nsew")
        output_panel.grid_columnconfigure(0, weight=1)
        output_panel.grid_rowconfigure(1, weight=1)
        output_top = tk.Frame(output_panel, bg=PANEL)
        output_top.grid(row=0, column=0, sticky="ew")
        output_top.grid_columnconfigure(0, weight=1)
        tk.Label(output_top, text="Output", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        self.small_button(output_top, "Copy Output", self.copy_command_output, "Copy the current command output to the clipboard.").grid(row=0, column=1, padx=(8, 0))
        self.small_button(output_top, "Save Output", self.save_command_output, "Save the current command output as a text file.").grid(row=0, column=2, padx=(8, 0))
        self.small_button(output_top, "Clear", self.clear_command_output, "Clear the output box.").grid(row=0, column=3, padx=(8, 0))
        self.command_output = tk.Text(output_panel, bg=INPUT_BG, fg=TEXT, insertbackground=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        self.command_output.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.write_command_output("Choose a tool above. Hover over any button for a short description.\n\nTraceroute help: each hop is a router or network device on the path to the destination. Low millisecond values are faster. Asterisks usually mean that hop did not reply before the timeout, not always that the route failed.")

    def write_command_output(self, text: str) -> None:
        self.last_command_output = text
        if not self.command_output:
            return
        self.command_output.configure(state="normal")
        self.command_output.delete("1.0", "end")
        self.command_output.insert("1.0", text)
        self.command_output.configure(state="disabled")

    def copy_command_output(self) -> None:
        if not self.last_command_output.strip():
            messagebox.showinfo(APP_NAME, "There is no command output to copy.")
            return
        self.copy_text(self.last_command_output, "Copied command output.")

    def save_command_output(self) -> None:
        if not self.last_command_output.strip():
            messagebox.showinfo(APP_NAME, "There is no command output to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Command Output",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"network_tool_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not path:
            return
        Path(path).write_text(self.last_command_output, encoding="utf-8")
        self.set_status(f"Saved command output: {path}")

    def clear_command_output(self) -> None:
        self.write_command_output("")
        self.set_status("Cleared command output.")

    def run_tool_command(self, label: str, args: list[str], timeout: int = 30) -> None:
        def worker():
            self.schedule_progress(20, "Running")
            code, output = run_command(args, timeout=timeout)
            self.schedule_progress(90, "Output")
            return f"$ {' '.join(args)}\nExit code: {code}\n\n{output or '(no output)'}"

        def done(text):
            self.write_command_output(text)

        self.start_task(f"Running {label}...", worker, done)

    def target(self) -> str:
        value = self.tool_target.get().strip() if hasattr(self, "tool_target") else ""
        return value or "8.8.8.8"

    def set_tool_target(self, value: str) -> None:
        if hasattr(self, "tool_target"):
            self.tool_target.set(value)
            self.set_status(f"Target set to {value}.")

    def use_gateway_target(self) -> None:
        gateway = self.ip_info.gateways[0] if self.ip_info.gateways else ""
        if not gateway:
            messagebox.showinfo(APP_NAME, "No default gateway is loaded yet. Run Full IP Scan or Health Check first.")
            return
        self.set_tool_target(gateway)

    def use_dns_target(self) -> None:
        dns = self.ip_info.dns_servers[0] if self.ip_info.dns_servers else ""
        if not dns:
            messagebox.showinfo(APP_NAME, "No DNS server is loaded yet. Run Full IP Scan or Health Check first.")
            return
        self.set_tool_target(dns)

    def run_ping(self) -> None:
        args = ["ping", "-n", "4", self.target()] if is_windows() else ["ping", "-c", "4", self.target()]
        self.run_tool_command("ping", args, 18)

    def run_dns_lookup(self) -> None:
        self.run_tool_command("DNS lookup", ["nslookup", self.target()], 18)

    def run_traceroute(self) -> None:
        args = ["tracert", "-d", self.target()] if is_windows() else ["traceroute", self.target()]
        self.run_tool_command("traceroute", args, 45)

    def run_ipconfig_tool(self) -> None:
        args = ["ipconfig", "/all"] if is_windows() else ["ifconfig"]
        self.run_tool_command("IP config", args, 18)

    def run_arp(self) -> None:
        args = ["arp", "-a"] if is_windows() else ["arp", "-an"]
        self.run_tool_command("ARP table", args, 18)

    def run_routes(self) -> None:
        args = ["route", "print"] if is_windows() else ["netstat", "-rn"]
        self.run_tool_command("route table", args, 18)

    def run_ports(self) -> None:
        args = ["netstat", "-ano"] if is_windows() else ["netstat", "-an"]
        self.run_tool_command("ports", args, 25)

    def run_repair(self, label: str, args: list[str]) -> None:
        if not is_windows():
            messagebox.showinfo(APP_NAME, "Repair Center commands are Windows-specific.")
            return
        if label in {"Release IP", "Reset Winsock"}:
            confirmed = messagebox.askyesno(
                label,
                f"{label} can temporarily interrupt networking or require a restart.\n\nRun this local Windows command now?",
            )
            if not confirmed:
                return
        self.run_tool_command(label, args, 30)

    def show_reports(self) -> None:
        self.current_page = "Reports"
        body = self.clear_content()
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)
        self.section_title_grid(
            body,
            "Reports",
            "Create clean exports for inventory, troubleshooting notes, or your own records. Password inclusion is controlled in Settings.",
        )
        actions = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=14, pady=12)
        actions.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        self.accent_button(actions, "Export HTML Report", self.export_html_report, "Create a formatted HTML report with dashboard, IP, WiFi, and help context.", CYAN).pack(side="left", padx=(0, 8))
        self.small_button(actions, "Export JSON", self.export_json_report, "Export dashboard, IP, WiFi, nearby network, and health data as JSON.").pack(side="left", padx=(0, 8))
        self.small_button(actions, "Export Profiles CSV", self.export_profiles_csv, "Create a CSV of saved WiFi profile details.").pack(side="left", padx=(0, 8))
        self.small_button(actions, "Copy Summary", self.copy_report_summary, "Copy a short report summary to the clipboard.").pack(side="left", padx=(0, 8))
        self.small_button(actions, "Gather All Profile Details", self.gather_all_profile_details, "Load profile details for every saved network before exporting.").pack(side="left")

        preview_panel = tk.Frame(body, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=12, pady=12)
        preview_panel.grid(row=2, column=0, sticky="nsew")
        preview_panel.grid_columnconfigure(0, weight=1)
        preview_panel.grid_rowconfigure(1, weight=1)
        tk.Label(preview_panel, text="Report Preview", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).grid(row=0, column=0, sticky="w")
        preview = tk.Text(preview_panel, bg=INPUT_BG, fg=TEXT, relief="flat", wrap="word", font=("Consolas", 10))
        preview.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        preview.insert("1.0", self.report_summary())
        preview.configure(state="disabled")

    def report_summary(self) -> str:
        lines = [
            f"{APP_NAME} {APP_VERSION} Report Preview",
            f"Created by {AUTHOR} - {HOMEPAGE}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            f"Current WiFi: {self.interface_info.get('ssid', 'Unavailable')}",
            f"Signal: {self.interface_info.get('signal', 'Unavailable')}",
            f"Saved profiles: {len(self.profile_names)}",
            f"Nearby networks: {len(self.nearby_networks)}",
            f"Strongest nearby: {nearby_summary(self.nearby_networks)['strongest']} ({nearby_summary(self.nearby_networks)['strongest_signal']})",
            f"Primary local IP: {self.ip_info.local_primary or first_ip(self.ip_info) or 'Unavailable'}",
            f"Public IPv4: {self.ip_info.public_ipv4 or 'Unavailable'}",
            f"Gateway: {', '.join(self.ip_info.gateways) or 'Unavailable'}",
            f"DNS: {', '.join(self.ip_info.dns_servers) or 'Unavailable'}",
            f"Health score: {str(health_score(self.health_checks)) + '%' if self.health_checks else 'Not run'}",
            "",
            "Loaded profile details:",
        ]
        if self.profile_details:
            for profile in self.profile_details.values():
                password = profile.password if self.include_passwords.get() else "(hidden by report setting)"
                lines.append(f"- {profile.name}: {profile.authentication}, {profile.encryption}, password: {password}")
        else:
            lines.append("- None loaded yet. Open WiFi Profiles or click Gather All Profile Details.")
        return "\n".join(lines)

    def gather_all_profile_details(self) -> None:
        names = list(self.profile_names)
        if not names:
            messagebox.showinfo(APP_NAME, "No saved WiFi profiles were found.")
            return

        def worker():
            details: dict[str, WifiProfile] = {}
            total = len(names)
            for index, name in enumerate(names, start=1):
                percent = 5 + int((index - 1) / max(1, total) * 85)
                self.schedule_progress(percent, f"{index}/{total}")
                details[name] = get_profile_detail(name)
            self.schedule_progress(95, "Complete")
            return details

        def done(details):
            self.profile_details.update(details)
            self.render_current_page()

        self.start_task("Gathering all saved profile details...", worker, done)

    def export_profiles_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export WiFi Profiles CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"wifi_profiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not path:
            return
        include_passwords = self.include_passwords.get()
        names = list(self.profile_names)

        def worker():
            rows = []
            for name in names:
                profile = self.profile_details.get(name) or get_profile_detail(name)
                self.profile_details[name] = profile
                rows.append(
                    {
                        "name": profile.name,
                        "authentication": profile.authentication,
                        "encryption": profile.encryption,
                        "connection_mode": profile.connection_mode,
                        "password": profile.password if include_passwords else "",
                        "notes": profile.notes,
                    }
                )
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["name", "authentication", "encryption", "connection_mode", "password", "notes"])
                writer.writeheader()
                writer.writerows(rows)
            return path

        def done(saved_path):
            self.set_status(f"Exported CSV: {saved_path}")
            messagebox.showinfo(APP_NAME, f"CSV report saved:\n{saved_path}")

        self.start_task("Exporting WiFi profile CSV...", worker, done)

    def build_report_data(self, include_passwords: bool) -> dict:
        return {
            "app": {
                "name": APP_NAME,
                "version": APP_VERSION,
                "tagline": APP_TAGLINE,
                "author": AUTHOR,
                "homepage": HOMEPAGE,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            },
            "interface": self.interface_info,
            "ip": {
                "hostname": self.ip_info.hostname,
                "local_primary": self.ip_info.local_primary,
                "hostname_ips": self.ip_info.hostname_ips,
                "ipconfig_ips": self.ip_info.ipconfig_ips,
                "powershell_ips": self.ip_info.powershell_ips,
                "gateways": self.ip_info.gateways,
                "dns_servers": self.ip_info.dns_servers,
                "public_ipv4": self.ip_info.public_ipv4,
                "public_ipv4_source": self.ip_info.public_ipv4_source,
                "public_ipv6": self.ip_info.public_ipv6,
                "public_ipv6_source": self.ip_info.public_ipv6_source,
                "adapters": self.ip_info.adapters,
                "errors": self.ip_info.raw_errors,
            },
            "health": {
                "score": health_score(self.health_checks) if self.health_checks else None,
                "status": health_status(health_score(self.health_checks)) if self.health_checks else "Not run",
                "checks": [check.__dict__ for check in self.health_checks],
            },
            "drivers": {
                "network_adapters": self.adapter_inventory,
                "adapter_note": self.adapter_inventory_note,
                "network_driver_inventory": self.driver_inventory,
                "driver_note": self.driver_inventory_note,
            },
            "wifi_profiles": [
                {
                    "name": profile.name,
                    "authentication": profile.authentication,
                    "encryption": profile.encryption,
                    "connection_mode": profile.connection_mode,
                    "password": profile.password if include_passwords else "",
                    "notes": profile.notes,
                }
                for profile in self.profile_details.values()
            ],
            "saved_profile_names": self.profile_names,
            "nearby_summary": nearby_summary(self.nearby_networks),
            "nearby_networks": [net.__dict__ for net in self.nearby_networks],
        }

    def export_json_report(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export JSON Report",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"wifi_vault_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        )
        if not path:
            return
        include_passwords = self.include_passwords.get()

        def worker():
            data = self.build_report_data(include_passwords)
            Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")
            return path

        def done(saved_path):
            self.set_status(f"Exported JSON: {saved_path}")
            messagebox.showinfo(APP_NAME, f"JSON report saved:\n{saved_path}")

        self.start_task("Exporting JSON report...", worker, done)

    def export_html_report(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export HTML Report",
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialfile=f"wifi_vault_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
        )
        if not path:
            return
        include_passwords = self.include_passwords.get()

        def worker():
            content = self.build_html_report(include_passwords)
            Path(path).write_text(content, encoding="utf-8")
            return path

        def done(saved_path):
            self.set_status(f"Exported HTML: {saved_path}")
            messagebox.showinfo(APP_NAME, f"HTML report saved:\n{saved_path}")

        self.start_task("Exporting HTML report...", worker, done)

    def build_html_report(self, include_passwords: bool) -> str:
        profile_rows = []
        for name in self.profile_names:
            profile = self.profile_details.get(name)
            if not profile:
                profile = WifiProfile(name=name, notes="Details not loaded.")
            password = profile.password if include_passwords else ""
            profile_rows.append(
                "<tr>"
                f"<td>{html.escape(profile.name)}</td>"
                f"<td>{html.escape(profile.authentication)}</td>"
                f"<td>{html.escape(profile.encryption)}</td>"
                f"<td>{html.escape(password)}</td>"
                f"<td>{html.escape(profile.notes)}</td>"
                "</tr>"
            )

        nearby_rows = [
            "<tr>"
            f"<td>{html.escape(net.ssid)}</td>"
            f"<td>{html.escape(net.signal)}</td>"
            f"<td>{html.escape(signal_quality(net.signal))}</td>"
            f"<td>{html.escape(guess_band(net.channel, net.radio_type))}</td>"
            f"<td>{html.escape(net.channel)}</td>"
            f"<td>{html.escape(net.authentication)}</td>"
            "</tr>"
            for net in self.nearby_networks
        ]
        health_rows = [
            "<tr>"
            f"<td>{html.escape(check.name)}</td>"
            f"<td>{html.escape(check.status)}</td>"
            f"<td>{html.escape(check.detail)}</td>"
            "</tr>"
            for check in self.health_checks
        ]
        driver_rows = [
            "<tr>"
            f"<td>{html.escape(row.get('device', ''))}</td>"
            f"<td>{html.escape(row.get('manufacturer', ''))}</td>"
            f"<td>{html.escape(row.get('version', ''))}</td>"
            f"<td>{html.escape(row.get('inf', ''))}</td>"
            f"<td>{html.escape(row.get('signed', ''))}</td>"
            "</tr>"
            for row in self.driver_inventory
        ]
        adapter_rows = [
            "<tr>"
            f"<td>{html.escape(row.get('name', ''))}</td>"
            f"<td>{html.escape(row.get('status', ''))}</td>"
            f"<td>{html.escape(row.get('speed', ''))}</td>"
            f"<td>{html.escape(row.get('mac', ''))}</td>"
            f"<td>{html.escape(row.get('media', ''))}</td>"
            "</tr>"
            for row in self.adapter_inventory
        ]

        return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(APP_NAME)} Report</title>
<style>
body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #081018; color: #eaf3ff; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 32px; }}
h1 {{ margin: 0; font-size: 34px; }}
h2 {{ margin-top: 28px; border-bottom: 1px solid #213447; padding-bottom: 8px; }}
.muted {{ color: #8fa6bb; }}
.cards {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 20px; }}
.card {{ background: #101a24; border: 1px solid #213447; padding: 16px; }}
.label {{ color: #8fa6bb; font-size: 12px; text-transform: uppercase; font-weight: 700; }}
.value {{ font-size: 22px; font-weight: 700; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; background: #101a24; }}
th, td {{ border: 1px solid #213447; padding: 9px; text-align: left; vertical-align: top; }}
th {{ background: #132232; }}
a {{ color: #22d3ee; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(APP_NAME)} {html.escape(APP_VERSION)}</h1>
<p class="muted">{html.escape(APP_TAGLINE)} - Created by {html.escape(AUTHOR)} - <a href="{html.escape(HOMEPAGE)}">{html.escape(HOMEPAGE)}</a></p>
<p class="muted">Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
<section class="cards">
<div class="card"><div class="label">Current WiFi</div><div class="value">{html.escape(self.interface_info.get('ssid', 'Unavailable'))}</div><p class="muted">{html.escape(self.interface_info.get('signal', ''))}</p></div>
<div class="card"><div class="label">Primary Local IP</div><div class="value">{html.escape(self.ip_info.local_primary or first_ip(self.ip_info) or 'Unavailable')}</div><p class="muted">Gateway: {html.escape(', '.join(self.ip_info.gateways) or 'Unavailable')}</p></div>
<div class="card"><div class="label">Public IPv4</div><div class="value">{html.escape(self.ip_info.public_ipv4 or 'Unavailable')}</div><p class="muted">{html.escape(self.ip_info.public_ipv4_source)}</p></div>
<div class="card"><div class="label">Health Score</div><div class="value">{html.escape(str(health_score(self.health_checks)) + '%' if self.health_checks else 'Not run')}</div><p class="muted">{html.escape(health_status(health_score(self.health_checks)) if self.health_checks else 'Run Health Check for diagnostics.')}</p></div>
</section>
<h2>Health Check</h2>
<table><thead><tr><th>Check</th><th>Status</th><th>Details</th></tr></thead><tbody>
{''.join(health_rows) or '<tr><td colspan="3">Health Check has not been run.</td></tr>'}
</tbody></table>
<h2>Network Drivers</h2>
<h3>Adapter Status</h3>
<table><thead><tr><th>Adapter</th><th>Status</th><th>Speed</th><th>MAC Address</th><th>Media</th></tr></thead><tbody>
{''.join(adapter_rows) or '<tr><td colspan="5">Network adapter status has not been loaded.</td></tr>'}
</tbody></table>
<h3>Driver Inventory</h3>
<table><thead><tr><th>Device</th><th>Manufacturer</th><th>Version</th><th>INF</th><th>Signed</th></tr></thead><tbody>
{''.join(driver_rows) or '<tr><td colspan="5">Network driver inventory has not been loaded.</td></tr>'}
</tbody></table>
<h2>Saved WiFi Profiles</h2>
<table><thead><tr><th>Name</th><th>Authentication</th><th>Encryption</th><th>Password</th><th>Notes</th></tr></thead><tbody>
{''.join(profile_rows) or '<tr><td colspan="5">No profiles found.</td></tr>'}
</tbody></table>
<h2>Nearby Networks</h2>
<p class="muted">Strongest: {html.escape(str(nearby_summary(self.nearby_networks)['strongest']))} ({html.escape(str(nearby_summary(self.nearby_networks)['strongest_signal']))})</p>
<table><thead><tr><th>SSID</th><th>Signal</th><th>Quality</th><th>Band</th><th>Channel</th><th>Security</th></tr></thead><tbody>
{''.join(nearby_rows) or '<tr><td colspan="6">No nearby networks scanned.</td></tr>'}
</tbody></table>
<h2>IP Detection</h2>
<pre>{html.escape(self.ip_summary())}</pre>
<h2>Feature Guide</h2>
<p>Ping checks reachability and latency. DNS Lookup resolves domain names. Traceroute lists the hops traffic takes to a target. ARP shows local neighbors. Routes show forwarding paths. Ports list local connections. Repair commands flush DNS, renew DHCP leases, or reset Winsock when Windows networking needs cleanup.</p>
</main>
</body>
</html>"""

    def copy_report_summary(self) -> None:
        self.copy_text(self.report_summary(), "Copied report summary.")

    def show_help(self) -> None:
        self.current_page = "Help"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(inner, "Help", "Plain-English descriptions of what every major section and diagnostic tool does.")
        help_items = [
            ("Dashboard", "Shows current WiFi, local IP, inventory state, and the main actions. Quick Refresh is fast; Full Scan loads profiles, nearby networks, IP data, adapters, and drivers."),
            ("WiFi Profiles", "Lists saved Windows WiFi profiles. Selecting a profile loads details such as authentication, encryption, connection mode, and password if Windows returns key content."),
            ("QR Connect", "Builds the standard WiFi QR payload used by many phones. You can copy the payload, copy SSID/password, download payload text, and download a QR PNG when qrcode and Pillow are installed."),
            ("Nearby Networks", "Runs a local WiFi scan and sorts visible networks by signal strength. Includes summary cards, search, security/band filtering, signal quality labels, copy selected details, and CSV export."),
            ("IP Intelligence", "Uses several methods because IP data can fail from one source. Socket route detection finds the address used for internet-bound traffic. Hostname detection asks Python. ipconfig and PowerShell ask Windows adapters directly. Public IP services show what websites see from outside your network."),
            ("Health Check", "Runs a guided diagnostic: local IP, gateway detection, DNS server detection, gateway ping, DNS resolve, internet ping, public IPv4, and public IPv6 context. The result becomes a simple health score."),
            ("Drivers & Folders", "Opens common Windows network tools and folders such as Device Manager, Network Connections, DriverStore, Windows INF, app folder, config folder, Documents, Downloads, and Temp. It also shows adapter status, MAC address, link speed, media type, and signed network driver packages."),
            ("Ping", "Sends small test packets to a target. Replies mean the target can be reached. The time in milliseconds is round-trip latency. Packet loss can point to WiFi, router, ISP, or target issues."),
            ("DNS Lookup", "Resolves a domain name into IP addresses. Use it when a website name fails but raw IP connectivity still works. Bad results can suggest DNS configuration problems."),
            ("Traceroute", "Shows each hop traffic takes toward a destination. A hop is usually a router. High times can identify slow network segments. Asterisks mean a hop did not answer in time, which is common and not automatically a failure."),
            ("IP Config", "Shows Windows adapter settings, including IPv4, IPv6, DHCP, DNS, gateway, MAC addresses, and lease timing. It is the detailed source behind many dashboard values."),
            ("ARP Table", "Lists local network neighbors your machine has recently talked to, pairing IP addresses with MAC addresses. Useful for spotting your router or local devices."),
            ("Routes", "Shows the routing table. It explains where Windows sends traffic for local networks, default internet traffic, VPNs, and special adapter paths."),
            ("Ports", "Lists active and listening network connections. Listening ports are services waiting for inbound connections. Established ports are live connections."),
            ("Repair Center", "Flush DNS clears cached name lookups. Release IP drops a DHCP lease. Renew IP asks for a new lease. Reset Winsock rebuilds Windows socket settings and may require restart."),
            ("Network Tools Output", "Network Tools output can be copied, saved as text, or cleared. Quick target buttons can set the target to your gateway, DNS server, or github.com."),
            ("Status Bar Progress", "The bottom status bar shows task progress with a percentage while the app refreshes data, scans networks, runs health checks, loads adapters/drivers, gathers profiles, or runs commands."),
            ("Reports", "Exports troubleshooting summaries. HTML is easiest to read, CSV is useful for WiFi, nearby network, adapter, and driver inventory, and JSON keeps dashboard/IP/WiFi/health/driver data machine-readable. Password inclusion is controlled in Settings."),
            ("Settings", "Switch the clock between 12-hour and 24-hour time, choose quick refresh on startup, choose whether Full Scan includes public IP lookup, and choose whether reports include loaded passwords."),
            ("About", "Shows version, Rice2k branding, homepage, and program purpose."),
        ]
        for title, text in help_items:
            self.info_panel(inner, title, text, CYAN if title not in {"Repair Center", "Reports"} else YELLOW)

    def show_settings(self) -> None:
        self.current_page = "Settings"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(inner, "Settings", "Preferences are saved to your Windows app data folder and loaded next time the app starts.")

        panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=16, pady=14)
        panel.pack(fill="x")
        tk.Label(panel, text="Clock Format", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        clock_row = tk.Frame(panel, bg=PANEL)
        clock_row.pack(anchor="w", pady=(10, 16))
        self.accent_button(clock_row, "12 Hour", lambda: self.set_clock_format("12"), "Show times like 2:35:08 PM.", CYAN if self.clock_format.get() == "12" else PURPLE).pack(side="left", padx=(0, 8))
        self.accent_button(clock_row, "24 Hour", lambda: self.set_clock_format("24"), "Show times like 14:35:08.", CYAN if self.clock_format.get() == "24" else PURPLE).pack(side="left")

        startup = tk.Checkbutton(
            panel,
            text="Run quick dashboard refresh when app opens",
            variable=self.refresh_on_start,
            bg=PANEL,
            fg=TEXT,
            selectcolor=INPUT_BG,
            activebackground=PANEL,
            activeforeground=TEXT,
            command=self.save_current_settings,
            font=("Segoe UI", 10),
        )
        startup.pack(anchor="w", pady=6)
        ToolTip(startup, "When enabled, startup only checks current WiFi and local IP. Full Scan still runs only when you click it.")

        public = tk.Checkbutton(
            panel,
            text="Include public IPv4/IPv6 lookup during Full Scan",
            variable=self.public_ip_on_refresh,
            bg=PANEL,
            fg=TEXT,
            selectcolor=INPUT_BG,
            activebackground=PANEL,
            activeforeground=TEXT,
            command=self.save_current_settings,
            font=("Segoe UI", 10),
        )
        public.pack(anchor="w", pady=6)
        ToolTip(public, "Public IP lookup contacts internet services and can be slower. Leave off for faster local scans.")

        report_passwords = tk.Checkbutton(
            panel,
            text="Include loaded WiFi passwords in exported reports",
            variable=self.include_passwords,
            bg=PANEL,
            fg=TEXT,
            selectcolor=INPUT_BG,
            activebackground=PANEL,
            activeforeground=TEXT,
            command=self.save_current_settings,
            font=("Segoe UI", 10),
        )
        report_passwords.pack(anchor="w", pady=6)
        ToolTip(report_passwords, "When off, reports leave the password column blank or marked hidden. The app still shows profile details locally after selection.")

        self.info_panel(
            inner,
            "Authorized Use",
            "This utility is intended for computers and networks you own or are authorized to manage. It does not send WiFi passwords anywhere; commands run locally.",
            YELLOW,
        )

    def save_current_settings(self) -> None:
        self.settings["clock_format"] = self.clock_format.get()
        self.settings["refresh_on_start"] = bool(self.refresh_on_start.get())
        self.settings["include_passwords_in_reports"] = bool(self.include_passwords.get())
        self.settings["public_ip_on_refresh"] = bool(self.public_ip_on_refresh.get())
        save_settings(self.settings)
        self.set_status("Settings saved.")

    def show_about(self) -> None:
        self.current_page = "About"
        body = self.clear_content()
        scroll = ScrollFrame(body)
        scroll.grid(row=0, column=0, sticky="nsew")
        inner = scroll.inner
        self.section_title(inner, "About", f"{APP_NAME} {APP_VERSION} - {APP_TAGLINE}")
        panel = tk.Frame(inner, bg=PANEL, highlightbackground=BORDER, highlightthickness=1, padx=20, pady=18)
        panel.pack(fill="x")
        tk.Label(panel, text=APP_NAME, bg=PANEL, fg=TEXT, font=("Segoe UI", 26, "bold")).pack(anchor="w")
        tk.Label(panel, text=APP_TAGLINE, bg=PANEL, fg=CYAN, font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(2, 10))
        tk.Label(panel, text=f"Created by {AUTHOR}", bg=PANEL, fg=TEXT, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        link = tk.Label(panel, text=HOMEPAGE, bg=PANEL, fg=CYAN, cursor="hand2", font=("Segoe UI", 11, "underline"))
        link.pack(anchor="w", pady=(4, 12))
        link.bind("<Button-1>", lambda _event: open_url(HOMEPAGE))
        tk.Label(
            panel,
            text=(
                "WiFi Vault Pro is a Windows-focused desktop utility for local network visibility. "
                "It combines saved WiFi profile review, nearby network scanning, IP detection, diagnostics, repair shortcuts, QR connection payloads, and exportable reports in one polished interface."
            ),
            bg=PANEL,
            fg=MUTED,
            justify="left",
            wraplength=850,
            font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(0, 14))
        self.accent_button(panel, "Open GitHub Homepage", lambda: open_url(HOMEPAGE), "Open GitHub.com/rice2k.", CYAN).pack(anchor="w")

        features = tk.Frame(inner, bg=BG)
        features.pack(fill="x", pady=(14, 0))
        self.info_panel(features, "Feature Set", "Dashboard cards, sidebar navigation, hover tooltips, 12/24-hour clock controls, progress status bar, WiFi profile details, QR payload/image downloads, nearby network filtering/export, multi-method IP detection, Health Check scoring, Drivers & Folders shortcuts, adapter status inventory, network driver inventory, diagnostics output save/copy tools, repair commands, CSV/HTML/JSON reports, and full help text.", GREEN)
        self.info_panel(features, "Privacy", "The app reads local Windows networking information and optional public IP lookup services. It does not upload saved WiFi profile data or report contents.", CYAN)

    def run(self) -> None:
        self.root.mainloop()


def first_ip(info: IpDetection) -> str:
    for source in [info.ipconfig_ips, info.hostname_ips, info.powershell_ips]:
        if source:
            return source[0]
    return ""


def ip_confidence(info: IpDetection) -> int:
    score = 0
    if info.local_primary:
        score += 25
    if info.ipconfig_ips:
        score += 20
    if info.powershell_ips:
        score += 15
    if info.gateways:
        score += 15
    if info.dns_servers:
        score += 10
    if info.public_ipv4:
        score += 15
    return min(100, score)


def health_score(checks: list[ConnectivityCheck]) -> int:
    if not checks:
        return 0
    weights = {"Pass": 1.0, "Warn": 0.45, "Info": 0.75, "Skip": 0.35, "Fail": 0.0}
    scored = [weights.get(check.status, 0.0) for check in checks if check.status != "Info"]
    if not scored:
        scored = [weights.get(check.status, 0.0) for check in checks]
    return int(round((sum(scored) / len(scored)) * 100))


def health_status(score: int) -> str:
    if score >= 85:
        return "Looks healthy."
    if score >= 65:
        return "Mostly healthy, with a few warnings."
    if score >= 40:
        return "Needs attention."
    return "Connectivity problems detected."


def main() -> None:
    app = WifiVaultProApp()
    app.run()


if __name__ == "__main__":
    main()
