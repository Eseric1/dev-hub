#!/usr/bin/env python3
"""
Field Intel Launcher
Double-click to launch field-intel as a system tray app.
Mirrors the file explorer launcher pattern.
"""

import sys, os, subprocess, socket, secrets, threading, time, webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
SERVER   = BASE_DIR / "server.py"

# ── Dependencies ──────────────────────────────────────────────────────────────
def ensure_deps():
    needed = []
    try:
        import pystray
    except ImportError:
        needed.append("pystray")
    try:
        from PIL import Image
    except ImportError:
        needed.append("pillow")

    if not needed:
        return

    import tkinter as tk
    root = tk.Tk()
    root.title("Field Intel — Setup")
    root.geometry("380x100")
    root.configure(bg="#0b0c10")
    root.eval("tk::PlaceWindow . center")

    tk.Label(root, text="Installing dependencies…",
             font=("Consolas", 11), bg="#0b0c10", fg="#cdd6f4").pack(pady=20)

    def do_install():
        for pkg in needed:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg, "--quiet",
                 "--disable-pip-version-check"],
                capture_output=True
            )
        root.destroy()

    threading.Thread(target=do_install, daemon=True).start()
    root.mainloop()

# ── Port ──────────────────────────────────────────────────────────────────────
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_for_port(port, timeout=15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.1)
    return False

# ── Server ────────────────────────────────────────────────────────────────────
def start_server(port, token):
    proc = subprocess.Popen(
        [sys.executable, str(SERVER), str(port), token],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline().strip()
        if line.startswith("READY:"):
            break
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    wait_for_port(port, timeout=10.0)
    return proc

# ── Tray icon ─────────────────────────────────────────────────────────────────
def make_icon():
    from PIL import Image, ImageDraw
    img  = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([2, 2, 62, 62], fill="#10131a", outline="#fbbf79", width=3)
    # Clipboard shape
    draw.rectangle([18, 20, 46, 50], fill="#fbbf79")
    draw.rectangle([24, 16, 40, 24], fill="#fbbf79")
    draw.rectangle([20, 16, 44, 22], fill="#10131a")
    # Lines suggesting text
    for y in [30, 36, 42]:
        draw.line([(22, y), (42, y)], fill="#10131a", width=2)
    return img

# ── Main ──────────────────────────────────────────────────────────────────────
def run_tray(proc, port, token):
    import pystray

    url = f"http://127.0.0.1:{port}/"

    def open_browser(icon=None, item=None):
        subprocess.Popen(
            f'start "" "{url}"', shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

    def quit_app(icon, item):
        proc.terminate()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("📋 Open Field Intel", open_browser, default=True),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Port: {port}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("✕ Quit", quit_app),
    )

    icon = pystray.Icon(
        name="FieldIntel",
        icon=make_icon(),
        title="Field Intel",
        menu=menu,
    )

    def open_when_ready():
        if wait_for_port(port, timeout=15.0):
            open_browser()

    threading.Thread(target=open_when_ready, daemon=True).start()
    icon.run()

def main():
    ensure_deps()

    try:
        import pystray
        from PIL import Image
    except ImportError:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Setup Failed",
            "Could not install required packages.\n"
            "Run: pip install pystray pillow")
        return

    if not SERVER.exists():
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw()
        messagebox.showerror("Missing File",
            f"server.py not found in:\n{BASE_DIR}")
        return

    port  = find_free_port()
    token = secrets.token_urlsafe(32)
    proc  = start_server(port, token)
    run_tray(proc, port, token)

if __name__ == "__main__":
    main()