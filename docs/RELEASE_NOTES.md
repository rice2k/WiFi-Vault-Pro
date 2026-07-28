# WiFi Vault Pro 4.9 Release Notes

## Highlights

- Full Scan now loads signed network driver inventory in addition to adapter status.
- The app opens quickly by default because heavy scanning is manual.
- Quick Refresh updates current WiFi and local IP only.
- Public IP lookup is off by default for faster local scans.
- Dashboard shortcuts were simplified to the most useful actions.
- Driver and adapter cards now distinguish "not loaded" from "loaded but empty."

## Included Downloads

The GitHub release includes:

- `WiFiVaultPro_Rice2k.exe` - standalone Windows executable.
- `WiFi_Vault_Pro_v4_9_Rice2k_Full_Package.zip` - complete package with EXE, source, scripts, docs, screenshots, tests, and README.
- `WiFi_Vault_Pro_v4_9_Rice2k_Source.zip` - source package with scripts and README.

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
- Real Windows driver inventory command returned driver rows on the test machine.
