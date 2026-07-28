# WiFi Vault Pro 4.10 Release Notes

## Highlights

- Added a custom WiFi Vault Pro Windows icon so the app no longer uses the default Tk feather icon.
- The custom icon is applied to the main app window, QR helper window, taskbar, and PyInstaller-built `.exe`.
- The icon assets are included in the source and full package downloads.
- Full Scan now loads signed network driver inventory in addition to adapter status.
- The app opens quickly by default because heavy scanning is manual.
- Quick Refresh updates current WiFi and local IP only.
- Public IP lookup is off by default for faster local scans.
- Dashboard shortcuts were simplified to the most useful actions.
- Driver and adapter cards now distinguish "not loaded" from "loaded but empty."

## Included Downloads

The GitHub release includes:

- `WiFiVaultPro_Rice2k.exe` - standalone Windows executable.
- `WiFi_Vault_Pro_v4_10_Rice2k_Full_Package.zip` - complete package with EXE, source, scripts, docs, screenshots, tests, icon assets, and README.
- `WiFi_Vault_Pro_v4_10_Rice2k_Source.zip` - source package with scripts, icon assets, and README.

## Validation

- Python syntax compile check.
- Parser regression checks.
- Fast startup test.
- Quick Refresh test.
- Full Scan driver-loading regression test.
- Empty adapter/driver result rendering.
- All-page Tkinter render smoke test.
- PyInstaller one-file EXE build.
- EXE launch smoke test.
- Custom icon asset loading.
- Real Windows driver inventory command returned driver rows on the test machine.
