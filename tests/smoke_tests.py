from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import wifi_vault_pro as appmod  # noqa: E402


def pump_until(app: appmod.WifiVaultProApp, predicate, timeout: float = 4.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.root.update()
        if predicate():
            return
        time.sleep(0.03)
    raise AssertionError(f"Timed out waiting for app condition. Status: {app.status_text.get()}")


def install_common_mocks() -> None:
    appmod.messagebox.showerror = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError(args))
    appmod.messagebox.showinfo = lambda *args, **kwargs: None


def test_icon_assets() -> None:
    ico = appmod.resource_path("assets", "wifi_vault_pro.ico")
    png = appmod.resource_path("assets", "wifi_vault_pro.png")
    assert ico.exists() and ico.stat().st_size > 1024
    assert png.exists() and png.stat().st_size > 1024
    assert ico.read_bytes()[:4] == b"\x00\x00\x01\x00"
    assert png.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_ip_parsing() -> None:
    assert appmod.extract_ipv4("2603:6081:2df0:be90:c93b:19e4:4c7a:de12") == ""
    sample = """Windows IP Configuration

Wireless LAN adapter Wi-Fi:
   IPv6 Address. . . . . . . . . . . : 2603:6081:2df0:be90:c93b:19e4:4c7a:de12
   IPv4 Address. . . . . . . . . . . : 192.168.1.185(Preferred)
   Default Gateway . . . . . . . . . : fe80::1%7
                                       192.168.1.1
   DNS Servers . . . . . . . . . . . : 2603:6081:2df0:be90::1
                                       192.168.1.1
"""
    ips, gateways, dns, _adapters = appmod.parse_ipconfig(sample)
    assert ips == ["192.168.1.185"]
    assert gateways == ["192.168.1.1"]
    assert dns == ["192.168.1.1"]


def test_fast_start_no_auto_scan() -> None:
    install_common_mocks()
    calls: list[str] = []
    appmod.load_settings = lambda: {
        "clock_format": "12",
        "refresh_on_start": False,
        "include_passwords_in_reports": False,
        "public_ip_on_refresh": False,
    }
    appmod.get_wifi_interface = lambda: calls.append("interface") or {}
    app = appmod.WifiVaultProApp()
    app.root.withdraw()
    app.root.update()
    try:
        assert calls == []
        assert app.interface_info["state"] == "Not scanned"
    finally:
        app.close()


def test_quick_refresh() -> None:
    install_common_mocks()
    appmod.load_settings = lambda: {
        "clock_format": "12",
        "refresh_on_start": False,
        "include_passwords_in_reports": False,
        "public_ip_on_refresh": False,
    }
    appmod.get_wifi_interface = lambda: {"state": "connected", "ssid": "HomeNet", "signal": "88%"}
    appmod.detect_quick_ips = lambda: appmod.IpDetection(local_primary="192.168.1.185")
    app = appmod.WifiVaultProApp()
    app.root.withdraw()
    try:
        app.refresh_quick()
        pump_until(app, lambda: app.progress_value.get() == 100)
        assert app.ip_loaded is True
        assert app.profiles_loaded is False
        assert app.nearby_loaded is False
    finally:
        app.close()


def test_full_scan_loads_drivers() -> None:
    install_common_mocks()
    seen: list[tuple[str, bool]] = []
    appmod.load_settings = lambda: {
        "clock_format": "12",
        "refresh_on_start": False,
        "include_passwords_in_reports": False,
        "public_ip_on_refresh": False,
    }
    appmod.get_wifi_interface = lambda: {"state": "connected", "ssid": "HomeNet", "signal": "88%"}
    appmod.get_wifi_profiles = lambda: ["HomeNet"]
    appmod.get_nearby_networks = lambda: []
    appmod.detect_ips = lambda include_public=True: seen.append(("ip", include_public)) or appmod.IpDetection(local_primary="192.168.1.185")
    appmod.get_network_adapter_inventory = lambda: ([{"name": "Wi-Fi", "status": "Up", "speed": "866 Mbps", "mac": "AA-BB", "media": "802.11", "index": "7"}], "")
    appmod.get_network_driver_inventory = lambda: ([{"device": "Intel Wi-Fi", "manufacturer": "Intel", "version": "1.2.3", "date": "2026-01-01", "inf": "oem42.inf", "signed": "True"}], "")
    app = appmod.WifiVaultProApp()
    app.root.withdraw()
    try:
        app.refresh_all()
        pump_until(app, lambda: app.progress_value.get() == 100, timeout=5.0)
        assert seen == [("ip", False)]
        assert app.adapters_loaded is True
        assert len(app.adapter_inventory) == 1
        assert app.drivers_loaded is True
        assert len(app.driver_inventory) == 1
    finally:
        app.close()


def test_page_render_smoke() -> None:
    install_common_mocks()
    appmod.load_settings = lambda: {
        "clock_format": "12",
        "refresh_on_start": False,
        "include_passwords_in_reports": False,
        "public_ip_on_refresh": False,
    }
    app = appmod.WifiVaultProApp()
    app.root.withdraw()
    app.profile_names = ["HomeNet"]
    app.profiles_loaded = True
    app.nearby_networks = [appmod.NearbyNetwork(ssid="HomeNet", signal="88%", channel="6", authentication="WPA2-Personal", encryption="CCMP")]
    app.nearby_loaded = True
    app.ip_info = appmod.IpDetection(local_primary="192.168.1.185", gateways=["192.168.1.1"], dns_servers=["192.168.1.1"])
    app.ip_loaded = True
    app.adapter_inventory = [{"name": "Wi-Fi", "status": "Up", "speed": "866 Mbps", "mac": "AA-BB", "media": "802.11", "index": "7"}]
    app.adapters_loaded = True
    app.driver_inventory = [{"device": "Intel Wi-Fi", "manufacturer": "Intel", "version": "1.2.3", "inf": "oem42.inf", "signed": "True"}]
    app.drivers_loaded = True
    try:
        for page in [
            "Dashboard",
            "WiFi Profiles",
            "Nearby Networks",
            "IP Intelligence",
            "Health Check",
            "Drivers & Folders",
            "Network Tools",
            "Reports",
            "Help",
            "Settings",
            "About",
        ]:
            app.navigate(page)
            app.root.update()
    finally:
        app.close()


if __name__ == "__main__":
    test_icon_assets()
    test_ip_parsing()
    test_fast_start_no_auto_scan()
    test_quick_refresh()
    test_full_scan_loads_drivers()
    test_page_render_smoke()
    print("smoke_tests_ok")
