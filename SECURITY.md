# Security And Authorized Use

WiFi Vault Pro is intended for computers and networks you own or are authorized to manage.

The app reads local Windows network information by calling built-in Windows tools such as `netsh`, `ipconfig`, `PowerShell`, `ping`, `tracert`, `arp`, `route`, and `netstat`.

Important notes:

- Saved WiFi password visibility depends on Windows permissions and profile contents.
- Passwords are shown only inside the local app unless the user chooses to copy or export them.
- Reports hide loaded WiFi passwords by default.
- Public IP lookup is off by default and only contacts public IP services when enabled in Settings.
- Repair commands can affect network connectivity and should be used carefully.

Do not use this project to access, reveal, export, or share network credentials from systems or networks where you do not have explicit authorization.

