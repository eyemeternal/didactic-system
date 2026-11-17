# didactic-system

## OpenVPN console

Run `python3 vpn_console.py` in your Linux desktop session. The console uses
Tk, nmcli, NetworkManager, and its OpenVPN plugin. Import a trusted .ovpn file
or select an existing OpenVPN connection, then choose Connect. NetworkManager
handles the tunnel and uses your desktop secret agent for credentials.
Disconnect ends the selected tunnel. Closing the console leaves its connection
under NetworkManager control.

## Web dashboard

Run `python3 vpn/backend/server.py` and open <http://127.0.0.1:8765>.
The local Python backend serves the browser frontend in `vpn/frontend`.
Use a Linux desktop with NetworkManager, nmcli and its OpenVPN plugin.
To add a profile run `nmcli connection import type openvpn file /path/to/profile.ovpn`.

The profile selector also discovers .ovpn files in `imports/`, `vpn/imports/`,
and `openbook/`. Choose a file and click **Import profile**, then **Connect**.
