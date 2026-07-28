# File Guide

| Path | Purpose |
| --- | --- |
| `wifi_vault_pro.py` | Main Tkinter desktop application. Contains the UI, WiFi profile reader, nearby scanner, IP detection, health checks, network tools, reports, QR payload tools, and Windows shortcut helpers. |
| `run_app.bat` | Starts the app from source with Python on Windows. |
| `install_requirements.bat` | Installs optional dependencies for QR images and executable builds. |
| `build_exe.bat` | Builds a standalone Windows `.exe` with PyInstaller. |
| `requirements.txt` | Optional package list: QR support, Pillow, and PyInstaller. |
| `assets/wifi_vault_pro.ico` | Custom Windows icon used by the app window, helper dialogs, taskbar, and built `.exe`. |
| `assets/wifi_vault_pro.png` | PNG preview/fallback version of the app icon. |
| `tests/smoke_tests.py` | Lightweight regression checks for parsers, fast startup, Quick Refresh, Full Scan driver loading, and page rendering. |
| `docs/screenshots/` | GitHub README screenshots generated with safe demo data. |
| `docs/RELEASE_NOTES.md` | Release details for the latest packaged build. |
| `SECURITY.md` | Authorized-use and privacy notes. |
| `LICENSE` | MIT license for the project. |

## Main App Sections

| Section | What It Does |
| --- | --- |
| Dashboard | Fast overview with current WiFi, local IP, public IP when scanned, profile/nearby counts, gateway/DNS, and main actions. |
| WiFi Profiles | Shows saved Windows WiFi profiles and selected profile details. Creates QR payloads and QR PNG downloads when optional QR support is installed. |
| Nearby Networks | Scans visible WiFi networks and filters by security or band. |
| IP Intelligence | Combines socket route, hostname, `ipconfig`, PowerShell, gateway, DNS, public IPv4, and public IPv6 checks. |
| Health Check | Runs practical local connectivity checks and produces a health score. |
| Drivers & Folders | Opens Windows network tools/folders and shows adapter plus signed driver inventory. |
| Network Tools | Runs Ping, DNS Lookup, Traceroute, IP Config, ARP, Routes, Ports, and repair commands. |
| Reports | Exports HTML, JSON, and CSV files for troubleshooting or inventory records. |
| Settings | Controls 12/24 hour clock, startup Quick Refresh, public IP lookup, and password inclusion in reports. |
