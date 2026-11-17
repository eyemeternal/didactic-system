"""Local OpenVPN console for Linux desktops running NetworkManager."""
import os
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from queue import Empty, Queue
from tkinter import filedialog, ttk


def nm(*args):
    result = subprocess.run(["nmcli", *args], capture_output=True, text=True,
                            timeout=105, env={**os.environ, "LC_ALL": "C"})
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "NetworkManager request failed")
    return result.stdout.strip()


def profiles():
    found = {}
    rows = nm("-t", "-f", "UUID,TYPE", "connection", "show")
    for row in rows.splitlines():
        uid, kind = row.split(":", 1)
        if kind == "vpn" and nm("-g", "vpn.service-type", "con", "show", uid) == "org.freedesktop.NetworkManager.openvpn":
            name = nm("-g", "connection.id", "con", "show", uid)
            found[f"{name}  ·  {uid}"] = uid
    return found


class Console:
    def __init__(self, root):
        self.root = root
        root.title("OpenVPN / Operations console")
        root.geometry("760x480")
        root.configure(bg="#101c22")
        panel = tk.Frame(root, bg="#101c22", padx=24, pady=20)
        panel.pack(fill="both", expand=True)
        self.state = tk.StringVar(value="Checking NetworkManager…")
        for title, size in [("OPENVPN   /   TUNNEL CONTROL", 19), ("Connection profile", 11)]:
            tk.Label(panel, text=title, bg="#101c22", fg="#9ce4ca",
                     font=("IBM Plex Mono", size)).pack(anchor="w", pady=5)
        self.pick = ttk.Combobox(panel, state="readonly")
        self.pick.pack(fill="x")
        self.pick.bind("<<ComboboxSelected>>", lambda _: self.render())
        tk.Label(panel, textvariable=self.state, bg="#101c22", fg="white").pack(anchor="w", pady=10)
        bar = ttk.Frame(panel)
        bar.pack(anchor="w")
        self.buttons = []
        for title, callback in [("Connect", lambda: self.action("up")), ("Disconnect", lambda: self.action("down")), ("Import .ovpn", self.import_file)]:
            button = ttk.Button(bar, text=title, command=callback)
            button.pack(side="left")
            self.buttons.append(button)
        tk.Label(panel, text="SESSION LOG", bg="#101c22", fg="#9ce4ca").pack(anchor="w", pady=(22, 4))
        self.log = tk.Text(panel, bg="#081318", fg="#bdd9cf", wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self.items, self.active = {}, set()
        self.queue = Queue()
        self.last = None
        self.busy = False
        self.refresh()
        root.after(80, self.receive)
        root.after(3000, self.poll)

    def run(self, job, label):
        if self.busy:
            return
        self.busy = True
        if label:
            self.state.set(label + "…")
        for button in self.buttons:
            button.state(["disabled"])
        def worker():
            try:
                message = job()
                self.queue.put((profiles(), set(nm("-g", "UUID", "con", "show", "--active").splitlines()), message, None))
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                self.queue.put(({}, set(), "", str(error)))
        threading.Thread(target=worker, daemon=True).start()

    def refresh(self):
        self.run(lambda: "", "")

    def receive(self):
        try:
            self.items, self.active, message, error = self.queue.get_nowait()
        except Empty:
            pass
        else:
            self.busy = False
            self.pick.configure(values=list(self.items))
            if self.pick.get() not in self.items:
                self.pick.set(next(iter(self.items), ""))
            self.render()
            if error:
                self.state.set(error)
            entry = message or self.state.get()
            if entry != self.last:
                self.log.configure(state="normal")
                self.log.insert("end", f"{datetime.now():%H:%M:%S}  {entry}\n")
                self.log.see("end")
                self.log.configure(state="disabled")
                self.last = entry
        self.root.after(80, self.receive)


    def poll(self):
        self.refresh()
        self.root.after(3000, self.poll)

    def render(self):
        if self.busy:
            return
        uid = self.items.get(self.pick.get())
        connected = uid in self.active
        self.state.set(("Connected" if connected else "Disconnected") if uid else "Import an OpenVPN profile to begin")
        for button, enabled in zip(self.buttons, (uid and not connected, connected, True)):
            button.state(["!disabled" if enabled else "disabled"])

    def action(self, direction):
        uid = self.items[self.pick.get()]
        self.run(lambda: nm("--wait", "90", "con", direction, "uuid", uid),
                 "Connecting" if direction == "up" else "Disconnecting")

    def import_file(self):
        path = filedialog.askopenfilename(filetypes=[("OpenVPN profiles", "*.ovpn")])
        if path:
            self.run(lambda: nm("con", "import", "type", "openvpn", "file", path), "Importing")


if __name__ == "__main__":
    window = tk.Tk()
    Console(window)
    window.mainloop()
