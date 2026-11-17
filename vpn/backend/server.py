"""Serve the local OpenVPN dashboard."""
import hashlib
import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
HOST = "127.0.0.1:8765"
operation = Lock()


def nm(*args, stdin=None):
    result = subprocess.run(["nmcli", *args], capture_output=True, text=True, stdin=stdin,
                            timeout=100, env={**os.environ, "LC_ALL": "C"})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "NetworkManager request failed")
    return result.stdout.strip()


def connect(uid, credentials):
    if not isinstance(credentials, dict):
        raise ValueError("Invalid credential fields")
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    for value in (username, password):
        if not isinstance(value, str) or any(c in value for c in ("\r", "\n", "\0")):
            raise ValueError("Credentials must be single-line text")
    if bool(username) != bool(password):
        raise ValueError("Enter both the VPN username and password")
    args = ("--wait", "90", "con", "up", "uuid", uid)
    if not password:
        return nm(*args)
    nm("con", "modify", "uuid", uid, "vpn.user-name", username)
    with os.fdopen(os.memfd_create("vpn-auth"), "w+b") as secret:
        secret.write(("vpn.secrets.password:" + password + "\n").encode())
        secret.seek(0)
        return nm(*args, "passwd-file", "/proc/self/fd/0", stdin=secret)


def import_files():
    root = FRONTEND.parents[1]
    files = {}
    for folder in (root / "imports", root / "vpn" / "imports", root / "openbook"):
        for path in sorted(folder.glob("*.ovpn")):
            if path.is_file() and not path.is_symlink():
                key = hashlib.sha256(str(path).encode()).hexdigest()
                files[key] = path
    return files


def profiles():
    rows = nm("-t", "-f", "UUID,TYPE", "con", "show").splitlines()
    active = nm("-g", "UUID", "con", "show", "--active").splitlines()
    items = []
    for row in rows:
        uid, kind = row.split(":", 1)
        if kind == "vpn" and nm("-g", "vpn.service-type", "con", "show", uid) == "org.freedesktop.NetworkManager.openvpn":
            items.append(dict(id=uid, name=nm("-g", "connection.id", "con", "show", uid), active=uid in active))
    names = {item["name"] for item in items}
    for key, path in import_files().items():
        if path.stem not in names:
            items.append(dict(id=key, name=path.stem, pending=True, active=False))
    return items


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, body, mime="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get("Host") != HOST:
            return self.reply(403, "Invalid host")
        try:
            if self.path == "/api/profiles":
                return self.reply(200, profiles())
            assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript")}
            if self.path in assets:
                name, mime = assets[self.path]
                return self.reply(200, (FRONTEND / name).read_bytes(), mime)
            self.reply(404, "Unknown route")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.reply(503, str(error))

    def do_POST(self):
        if self.headers.get("Host") != HOST or self.headers.get("Origin") != "http://" + HOST:
            return self.reply(403, "Invalid origin")
        parts = self.path.strip("/").split("/")
        if len(parts) != 4 or parts[:2] != ["api", "profiles"] or parts[3] not in ("connect", "disconnect", "import"):
            return self.reply(404, "Unknown operation")
        if not operation.acquire(blocking=False):
            return self.reply(409, "A connection operation is in progress")
        try:
            uid, action = parts[2:]
            if action == "import":
                path = import_files().get(uid)
                if path is None:
                    return self.reply(404, "Profile file no longer available")
                if any(item["id"] == uid and item.get("pending") for item in profiles()):
                    return self.reply(200, nm("con", "import", "type", "openvpn", "file", str(path)))
                return self.reply(409, "Profile already imported")
            if uid not in {item["id"] for item in profiles() if not item.get("pending")}:
                return self.reply(404, "Unknown OpenVPN profile")
            if action == "connect":
                length = int(self.headers.get("Content-Length", 0))
                if not 0 <= length <= 16384:
                    return self.reply(413, "Credentials are too long")
                credentials = json.loads(self.rfile.read(length)) if length else {}
                return self.reply(200, connect(uid, credentials))
            self.reply(200, nm("--wait", "90", "con", "down", "uuid", uid))
        except ValueError:
            self.reply(400, "Enter both username and password as single-line text, or leave both empty")
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.reply(503, str(error))
        finally:
            operation.release()


if __name__ == "__main__":
    print("Open http://" + HOST, flush=True)
    ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
