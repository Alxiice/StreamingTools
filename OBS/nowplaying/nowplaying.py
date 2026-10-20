"""
Now Playing overlay manager for OBS.

Run:  python nowplaying.py
Then add an OBS Browser Source with the URL shown in the window.
Needs only Python 3 (tkinter is included with the standard installer).
"""
import json
import os
import queue
import threading
import tkinter as tk
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tkinter import filedialog, ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "nowplaying_config.json")
DEFAULT_TEMPLATE = os.path.join(APP_DIR, "nowplaying_template.html")
DEFAULTS = {"title_file": "", "viewer_file": "", "port": 8000, "show_debug": False,
            "width": 1000, "opacity": 100, "dark": False,
            "template_file": "", "gui_dark": True}

config = dict(DEFAULTS)
log_queue = queue.Queue()
last_seen = {}


def log(msg):
    log_queue.put("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))


def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config.update(json.load(f))
        log("Config loaded from " + CONFIG_PATH)
    except FileNotFoundError:
        log("No saved config yet - set your files and press Save.")
    except Exception as e:
        log("Could not read config: %s" % e)


def save_config():
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


# ----------------------------------------------------------------- server


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, key, label):
        path = config.get(key + "_file", "")
        err_key = key + "_err"
        if not path:
            self._send(404, "not set")
            if last_seen.get(err_key) != "unset":
                last_seen[err_key] = "unset"
                log("%s file is not set." % label)
            return
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                text = f.read().strip()
        except OSError as e:
            self._send(404, "unreadable")
            if last_seen.get(err_key) != str(e):
                last_seen[err_key] = str(e)
                log("Cannot read %s file: %s" % (label.lower(), e))
            return
        last_seen[err_key] = None
        self._send(200, text)
        if last_seen.get(key) != text:
            last_seen[key] = text
            log("%s: %s" % (label, text if text else "(empty)"))

    def _serve_template(self):
        tpl = config.get("template_file") or DEFAULT_TEMPLATE
        try:
            with open(tpl, "r", encoding="utf-8-sig") as f:
                html = f.read()
        except OSError as e:
            self._send(500, "Template not found or unreadable: %s\n%s" % (tpl, e))
            if last_seen.get("tpl_err") != tpl:
                last_seen["tpl_err"] = tpl
                log("Cannot read template: %s" % e)
            return
        last_seen["tpl_err"] = None
        self._send(200, html, "text/html; charset=utf-8")
        if last_seen.get("tpl") != tpl:
            last_seen["tpl"] = tpl
            log("Template loaded: " + tpl)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", "/nowplaying.html"):
            self._serve_template()
        elif path == "/config.json":
            self._send(200, json.dumps({"show_debug": bool(config["show_debug"]),
                                        "width": config["width"],
                                        "opacity": config["opacity"],
                                        "dark": bool(config["dark"])}),
                       "application/json")
        elif path == "/song":
            self._serve_file("title", "Song")
        elif path == "/requester":
            self._serve_file("viewer", "Requested by")
        else:
            self._send(404, "not found")

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/log":
            n = int(self.headers.get("Content-Length", 0) or 0)
            msg = self.rfile.read(n).decode("utf-8", "replace")
            log("Overlay: " + msg)
            self._send(200, "ok")
        else:
            self._send(404, "not found")

    def log_message(self, *args):
        pass


class Server:
    def __init__(self):
        self.httpd = None

    @property
    def running(self):
        return self.httpd is not None

    def start(self, port):
        try:
            self.httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        except OSError as e:
            self.httpd = None
            log("Could not start server on port %d: %s" % (port, e))
            return False
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        log("Server started on http://localhost:%d/" % port)
        return True

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
            log("Server stopped.")


# -------------------------------------------------------------------- GUI
class App:
    def __init__(self, root):
        self.root = root
        self.server = Server()
        self.style = ttk.Style()
        self.default_theme = self.style.theme_use()
        self.default_bg = root.cget("bg")
        root.title("Now Playing for OBS - v6")
        root.geometry("760x720")
        root.minsize(640, 600)

        self.title_var = tk.StringVar(value=config["title_file"])
        self.viewer_var = tk.StringVar(value=config["viewer_file"])
        self.template_var = tk.StringVar(value=config["template_file"] or DEFAULT_TEMPLATE)
        self.port_var = tk.StringVar(value=str(config["port"]))
        self.debug_var = tk.BooleanVar(value=bool(config["show_debug"]))
        self.width_var = tk.StringVar(value=str(config["width"]))
        self.opacity_var = tk.DoubleVar(value=config["opacity"])
        self.opacity_text = tk.StringVar(value="%d%%" % config["opacity"])
        self.dark_var = tk.BooleanVar(value=bool(config["dark"]))
        self.gui_dark_var = tk.BooleanVar(value=bool(config["gui_dark"]))
        self.url_var = tk.StringVar()
        self.status_var = tk.StringVar()

        main = ttk.Frame(root, padding=14)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(11, weight=1)

        self._file_row(main, 0, "Song title file", self.title_var)
        self._file_row(main, 1, "Viewer name file", self.viewer_var)

        self._file_row(main, 2, "HTML template", self.template_var,
                       [("HTML files", "*.html *.htm"), ("All files", "*.*")])

        ttk.Label(main, text="Port").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Spinbox(main, from_=1024, to=65535, width=8,
                    textvariable=self.port_var).grid(row=3, column=1, sticky="w", pady=6)

        ttk.Label(main, text="Box width (px)").grid(row=4, column=0, sticky="w", pady=6)
        wsp = ttk.Spinbox(main, from_=300, to=3000, increment=50, width=8,
                          textvariable=self.width_var, command=self.on_appearance)
        wsp.grid(row=4, column=1, sticky="w", pady=6)
        wsp.bind("<Return>", lambda e: self.on_appearance())
        wsp.bind("<FocusOut>", lambda e: self.on_appearance())

        ttk.Label(main, text="Box opacity").grid(row=5, column=0, sticky="w", pady=6)
        orow = ttk.Frame(main)
        orow.grid(row=5, column=1, sticky="ew", padx=8)
        scale = ttk.Scale(orow, from_=0, to=100, variable=self.opacity_var,
                          command=lambda v: self.opacity_text.set("%d%%" % float(v)))
        scale.pack(side="left", fill="x", expand=True)
        scale.bind("<ButtonRelease-1>", lambda e: self.on_appearance())
        ttk.Label(orow, textvariable=self.opacity_text, width=5).pack(side="left", padx=(8, 0))

        ttk.Checkbutton(
            main, text="Plain dark box in the overlay (no blurred cover)",
            variable=self.dark_var, command=self.on_appearance,
        ).grid(row=6, column=0, columnspan=3, sticky="w")

        ttk.Checkbutton(
            main, text="Show debug box in the OBS overlay",
            variable=self.debug_var, command=self.on_save,
        ).grid(row=7, column=0, columnspan=3, sticky="w", pady=(8, 8))

        ttk.Label(main, text="OBS Browser Source URL").grid(row=8, column=0, sticky="w")
        url = ttk.Entry(main, textvariable=self.url_var, state="readonly")
        url.grid(row=8, column=1, sticky="ew", padx=8)
        ttk.Button(main, text="Copy", command=self.copy_url).grid(row=8, column=2)

        bar = ttk.Frame(main)
        bar.grid(row=9, column=0, columnspan=3, sticky="ew", pady=12)
        ttk.Button(bar, text="Save config", command=self.on_save).pack(side="left")
        self.toggle_btn = ttk.Button(bar, text="Stop server", command=self.toggle_server)
        self.toggle_btn.pack(side="left", padx=8)
        ttk.Label(bar, textvariable=self.status_var).pack(side="left", padx=8)
        ttk.Checkbutton(bar, text="Dark interface", variable=self.gui_dark_var,
                        command=self.on_theme).pack(side="right")

        head = ttk.Frame(main)
        head.grid(row=10, column=0, columnspan=3, sticky="ew")
        ttk.Label(head, text="Logs").pack(side="left")
        ttk.Button(head, text="Clear", command=self.clear_logs).pack(side="right")

        box = ttk.Frame(main)
        box.grid(row=11, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        self.logbox = tk.Text(box, height=10, state="disabled", wrap="word",
                              font=("Consolas", 10))
        sb = ttk.Scrollbar(box, command=self.logbox.yview)
        self.logbox.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.logbox.pack(side="left", fill="both", expand=True)

        self.apply_theme()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.apply_config(restart=False)
        self.server.start(config["port"])
        self.refresh_status()
        self.drain_logs()

    def _file_row(self, parent, row, label, var, types=None):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(parent, text="Browse...",
                   command=lambda: self.browse(var, types)).grid(row=row, column=2)

    def browse(self, var, types=None):
        path = filedialog.askopenfilename(
            title="Choose a file",
            filetypes=types or [("Text files", "*.txt"), ("All files", "*.*")])
        if path:
            var.set(os.path.normpath(path))

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.url_var.get())
        log("OBS URL copied to clipboard.")

    def apply_config(self, restart=True):
        try:
            port = int(self.port_var.get())
            if not 1024 <= port <= 65535:
                raise ValueError
        except ValueError:
            log("Port must be a number between 1024 and 65535.")
            self.port_var.set(str(config["port"]))
            port = config["port"]
        try:
            width = max(300, min(3000, int(float(self.width_var.get()))))
        except ValueError:
            width = config["width"]
        self.width_var.set(str(width))
        old_port = config["port"]
        config.update(
            title_file=self.title_var.get().strip().strip('"'),
            viewer_file=self.viewer_var.get().strip().strip('"'),
            template_file=self.template_var.get().strip().strip('"'),
            port=port,
            show_debug=self.debug_var.get(),
            width=width,
            opacity=int(round(self.opacity_var.get())),
            dark=self.dark_var.get(),
            gui_dark=self.gui_dark_var.get(),
        )
        self.url_var.set("http://localhost:%d/" % port)
        if restart and port != old_port and self.server.running:
            self.server.stop()
            self.server.start(port)

    def on_theme(self):
        self.apply_theme()
        self.on_save(quiet=True)

    def apply_theme(self):
        st = self.style
        if self.gui_dark_var.get():
            bg, fg, field = "#1e1e1e", "#e6e6e6", "#2d2d30"
            btn, btn_hi, border, accent = "#3a3a3d", "#4a4a4e", "#3c3c3c", "#0e639c"
            st.theme_use("clam")
            st.configure(".", background=bg, foreground=fg, fieldbackground=field,
                         bordercolor=border, lightcolor=bg, darkcolor=bg,
                         troughcolor=field, focuscolor=bg, insertcolor=fg)
            st.configure("TButton", background=btn, foreground=fg, padding=6)
            st.map("TButton", background=[("active", btn_hi), ("pressed", btn_hi)])
            st.configure("TCheckbutton", background=bg, foreground=fg)
            st.map("TCheckbutton", background=[("active", bg)],
                   indicatorbackground=[("selected", accent), ("!selected", field)],
                   indicatorforeground=[("selected", "#ffffff"), ("!selected", field)])
            st.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg)
            st.map("TEntry", fieldbackground=[("readonly", field)])
            st.configure("TSpinbox", fieldbackground=field, foreground=fg,
                         arrowcolor=fg, background=btn, insertcolor=fg)
            st.configure("TScrollbar", background=btn, troughcolor=bg,
                         arrowcolor=fg, bordercolor=bg)
            st.map("TScrollbar", background=[("active", btn_hi)])
            st.configure("Horizontal.TScale", background=bg, troughcolor=field)
            self.root.configure(bg=bg)
            self.logbox.configure(bg="#151515", fg=fg, insertbackground=fg,
                                  selectbackground=accent, highlightthickness=1,
                                  highlightbackground=border, highlightcolor=border)
        else:
            st.theme_use(self.default_theme)
            self.root.configure(bg=self.default_bg)
            self.logbox.configure(bg="white", fg="black", insertbackground="black",
                                  selectbackground="#3399ff", highlightthickness=1,
                                  highlightbackground="#999999", highlightcolor="#999999")

    def on_appearance(self):
        self.on_save(quiet=True)

    def on_save(self, quiet=False):
        self.apply_config()
        try:
            save_config()
            if not quiet:
                log("Config saved.")
        except OSError as e:
            log("Could not save config: %s" % e)
        self.refresh_status()

    def toggle_server(self):
        if self.server.running:
            self.server.stop()
        else:
            self.apply_config(restart=False)
            self.server.start(config["port"])
        self.refresh_status()

    def refresh_status(self):
        if self.server.running:
            self.status_var.set("Server running")
            self.toggle_btn.configure(text="Stop server")
        else:
            self.status_var.set("Server stopped")
            self.toggle_btn.configure(text="Start server")

    def clear_logs(self):
        self.logbox.configure(state="disabled")
        self.logbox.configure(state="normal")
        self.logbox.delete("1.0", "end")
        self.logbox.configure(state="disabled")

    def drain_logs(self):
        lines = []
        while True:
            try:
                lines.append(log_queue.get_nowait())
            except queue.Empty:
                break
        if lines:
            self.logbox.configure(state="normal")
            self.logbox.insert("end", "\n".join(lines) + "\n")
            extra = int(self.logbox.index("end-1c").split(".")[0]) - 1000
            if extra > 0:
                self.logbox.delete("1.0", "%d.0" % (extra + 1))
            self.logbox.see("end")
            self.logbox.configure(state="disabled")
        self.root.after(250, self.drain_logs)

    def on_close(self):
        self.server.stop()
        self.root.destroy()


if __name__ == "__main__":
    log("Running " + os.path.abspath(__file__) + " (v6)")
    load_config()
    root = tk.Tk()
    App(root)
    root.mainloop()
