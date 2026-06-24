#!/usr/bin/env python3
"""
Kiwi Simple - Find File
A tiny, free Windows tool that finds a file by part of its name, fast - then
opens it in File Explorer. Searches any folder or your whole drive, including
the system-adjacent folders a web browser is not allowed to read.

100% local. Nothing is uploaded. Standard library only (no pip installs needed).

Free tool from https://kiwisimple.nz
"""

import os
import sys
import json
import time
import string
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Kiwi Simple - Find File"
BRAND_URL = "https://kiwisimple.nz"
VERSION = "1.2"

# On-brand colours (Kiwi Simple indigo)
INDIGO = "#3949AB"
INDIGO_D = "#283593"
BG = "#E8EAF6"
SCOPEBAR = "#C5CAE9"
RED = "#C62828"
TEXT = "#1a1a1a"
MUTED = "#555555"

CACHE_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "KiwiSimpleFindFile"
)
CACHE_FILE = os.path.join(CACHE_DIR, "index.txt")
META_FILE = os.path.join(CACHE_DIR, "meta.json")

MAX_RESULTS = 2000     # rows shown
COLLECT_CAP = 30000    # matches gathered for sorting before we stop looking


# ----------------------------------------------------------------------------
# Core (no GUI - importable + testable)
# ----------------------------------------------------------------------------
def fixed_drives():
    """Return existing drive roots, e.g. ['C:\\\\', 'D:\\\\']."""
    return [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]


def scan_paths(roots, on_progress=None, should_stop=None):
    """Recursively walk `roots`, returning a list of (path, mtime) tuples.

    On Windows os.scandir already carries stat data, so entry.stat() is free.
    Skips folders we can't read silently. Iterative (no recursion limit).
    """
    out = []
    stack = list(roots)
    count = 0
    while stack:
        if should_stop and should_stop():
            break
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            try:
                                mtime = entry.stat(follow_symlinks=False).st_mtime
                            except OSError:
                                mtime = 0.0
                            out.append((entry.path, mtime))
                            count += 1
                            if on_progress and count % 4000 == 0:
                                on_progress(count)
                    except OSError:
                        pass
        except (PermissionError, OSError):
            pass
    if on_progress:
        on_progress(count)
    return out


def open_in_explorer(path):
    """Open File Explorer with the file selected (the thing a browser can't do)."""
    path = os.path.normpath(path)
    try:
        subprocess.Popen(f'explorer /select,"{path}"')
        return True
    except Exception:
        try:
            subprocess.Popen(["explorer", "/select,", path])
            return True
        except Exception:
            return False


def fmt_date(mtime):
    if not mtime:
        return ""
    try:
        return time.strftime("%d %b %Y  %H:%M", time.localtime(mtime))
    except Exception:
        return ""


def load_cache():
    """Return (items, meta) where items is a list of (path, mtime)."""
    try:
        items = []
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            for line in f.read().splitlines():
                if not line:
                    continue
                if "\t" in line:                     # new format: mtime<TAB>path
                    m, p = line.split("\t", 1)
                    try:
                        items.append((p, float(m)))
                    except ValueError:
                        items.append((p, 0.0))
                else:                                # old format: path only
                    items.append((line, 0.0))
        meta = {}
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as f:
                meta = json.load(f)
        return items, meta
    except (OSError, ValueError):
        return [], None


def save_cache(items, roots):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(f"{int(m)}\t{p}" for p, m in items))
        with open(META_FILE, "w", encoding="utf-8") as f:
            json.dump({"roots": roots, "count": len(items), "when": time.time()}, f)
    except OSError:
        pass


def scope_text(roots):
    if not roots:
        return ""
    if sorted(roots) == sorted(fixed_drives()):
        return "Whole PC (" + ", ".join(roots) + ")"
    return ", ".join(roots)


# ----------------------------------------------------------------------------
# GUI
# ----------------------------------------------------------------------------
class FindFileApp:
    def __init__(self, root):
        self.root = root
        self.index = []          # list of (name_lower, path, mtime)
        self.results = []        # current filtered matches (same shape)
        self.scanning = False
        self.stop_flag = False
        self.last_roots = []
        self.sort_col = None     # 'name' | 'modified' | 'folder' | None
        self.sort_desc = False

        root.title(APP_TITLE)
        root.geometry("900x620")
        root.minsize(660, 460)
        root.configure(bg=BG)

        self._build_ui()
        self._load_existing_cache()

    # --- UI -----------------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        header = tk.Frame(self.root, bg=INDIGO)
        header.pack(fill="x")
        tk.Label(header, text="🔎  Kiwi Simple — Find File", bg=INDIGO, fg="white",
                 font=("Segoe UI", 15, "bold"), pady=12, padx=14).pack(side="left")

        ctrl = tk.Frame(self.root, bg=BG)
        ctrl.pack(fill="x", padx=14, pady=(12, 4))
        self.folder_btn = tk.Button(ctrl, text="📁 Scan a folder…", command=self.scan_folder,
                                    bg=INDIGO, fg="white", relief="flat", padx=12, pady=6,
                                    font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.folder_btn.pack(side="left")
        self.all_btn = tk.Button(ctrl, text="💽 Scan whole PC", command=self.scan_all,
                                 bg=INDIGO, fg="white", relief="flat", padx=12, pady=6,
                                 font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.all_btn.pack(side="left", padx=(8, 0))
        self.rescan_btn = tk.Button(ctrl, text="🔄 Rescan", command=self.rescan,
                                    bg="#9FA8DA", fg=INDIGO_D, relief="flat", padx=12, pady=6,
                                    font=("Segoe UI", 10, "bold"), cursor="hand2", state="disabled")
        self.rescan_btn.pack(side="left", padx=(8, 0))
        self.stop_btn = tk.Button(ctrl, text="⛔ Stop", command=self.stop_scan, bg=RED,
                                  fg="white", relief="flat", padx=12, pady=6,
                                  font=("Segoe UI", 10, "bold"), cursor="hand2", state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))

        self.scope_var = tk.StringVar(
            value="📂  No folder chosen yet — click “Scan a folder…” or “Scan whole PC”.")
        tk.Label(self.root, textvariable=self.scope_var, bg=SCOPEBAR, fg=INDIGO_D,
                 font=("Segoe UI", 10, "bold"), anchor="w", padx=14, pady=9
                 ).pack(fill="x", padx=14, pady=(8, 0))

        sf = tk.Frame(self.root, bg=BG)
        sf.pack(fill="x", padx=14, pady=(10, 2))
        tk.Label(sf, text="Type part of a file name:", bg=BG, fg=MUTED,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(sf, textvariable=self.search_var, font=("Segoe UI", 13),
                                     relief="flat", highlightthickness=2,
                                     highlightbackground="#bbb", highlightcolor=INDIGO)
        self.search_entry.pack(fill="x", ipady=7, pady=(4, 0))
        self.search_entry.bind("<KeyRelease>", self._on_type)
        self._debounce = None
        tk.Label(self.root, text="Double-click a result to open it  ·  click a column heading to sort",
                 bg=BG, fg=MUTED, font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=14)

        rf = tk.Frame(self.root, bg=BG)
        rf.pack(fill="both", expand=True, padx=14, pady=(6, 4))
        cols = ("name", "modified", "folder")
        self.tree = ttk.Treeview(rf, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="File", command=lambda: self.sort_by("name"))
        self.tree.heading("modified", text="Date modified", command=lambda: self.sort_by("modified"))
        self.tree.heading("folder", text="Location", command=lambda: self.sort_by("folder"))
        self.tree.column("name", width=240, anchor="w")
        self.tree.column("modified", width=150, anchor="w")
        self.tree.column("folder", width=440, anchor="w")
        vsb = ttk.Scrollbar(rf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self._open_selected)
        self.tree.bind("<Return>", self._open_selected)
        self.tree.bind("<Button-3>", self._popup_menu)

        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Open in File Explorer", command=self._open_selected)
        self.menu.add_command(label="Copy full path", command=self._copy_selected)

        sb = tk.Frame(self.root, bg=BG)
        sb.pack(fill="x", padx=14, pady=(0, 4))
        self.status = tk.Label(sb, text="Ready.", bg=BG, fg=MUTED, font=("Segoe UI", 9), anchor="w")
        self.status.pack(side="left")

        foot = tk.Frame(self.root, bg="#d7dcf0")
        foot.pack(fill="x")
        link = tk.Label(foot, text="More free tools at kiwisimple.nz", bg="#d7dcf0", fg=INDIGO_D,
                        font=("Segoe UI", 9, "bold"), cursor="hand2", pady=6)
        link.pack()
        link.bind("<Button-1>", lambda e: self._open_url(BRAND_URL))

    # --- button / scope state ----------------------------------------------
    def _set_scanning_ui(self, scanning):
        self.folder_btn.config(state="disabled" if scanning else "normal")
        self.all_btn.config(state="disabled" if scanning else "normal")
        self.stop_btn.config(state="normal" if scanning else "disabled")
        if scanning:
            self.rescan_btn.config(state="disabled")
        else:
            self.rescan_btn.config(state="normal" if self.last_roots else "disabled")

    # --- scanning -----------------------------------------------------------
    def _load_existing_cache(self):
        items, meta = load_cache()
        if items:
            self._set_index(items)
            roots = (meta or {}).get("roots", [])
            self.last_roots = roots
            self.scope_var.set("📂  Searching in:  " + scope_text(roots)
                               + f"   ·   {len(items):,} files (from last scan)")
            self.status.config(text="Type part of a file name to search, or Rescan to refresh.")
            self.rescan_btn.config(state="normal")
            self.search_entry.focus_set()

    def scan_folder(self):
        folder = filedialog.askdirectory(title="Choose a folder to search")
        if folder:
            self._start_scan([os.path.normpath(folder)])

    def scan_all(self):
        drives = fixed_drives()
        if not drives:
            messagebox.showwarning(APP_TITLE, "No drives found.")
            return
        if not messagebox.askokcancel(
            APP_TITLE,
            "Scan your whole PC (" + ", ".join(drives) + ")?\n\n"
            "The first scan can take up to a minute on a big drive. "
            "You can press Stop at any time.",
        ):
            return
        self._start_scan(drives)

    def rescan(self):
        if self.last_roots:
            self._start_scan(self.last_roots)
        else:
            self.scan_all()

    def stop_scan(self):
        if self.scanning:
            self.stop_flag = True
            self.status.config(text="Stopping…")
            self.scope_var.set("⛔  Stopping…")

    def _start_scan(self, roots):
        if self.scanning:
            return
        self.scanning = True
        self.stop_flag = False
        self.last_roots = roots
        self._set_scanning_ui(True)
        self._clear_results()
        self.scope_var.set("📂  Scanning:  " + scope_text(roots) + "  …")
        self.status.config(text="Reading the folder… (press Stop to cancel)")

        def worker():
            t0 = time.time()
            items = scan_paths(
                roots,
                on_progress=lambda c: self._post_status(f"Scanning… {c:,} files found"),
                should_stop=lambda: self.stop_flag,
            )
            stopped = self.stop_flag
            if not stopped:
                save_cache(items, roots)
            self.root.after(0, lambda: self._scan_done(items, time.time() - t0, stopped))

        threading.Thread(target=worker, daemon=True).start()

    def _post_status(self, text):
        self.root.after(0, lambda: self.status.config(text=text))

    def _scan_done(self, items, secs, stopped=False):
        self.scanning = False
        self._set_index(items)
        self._set_scanning_ui(False)
        roots_txt = scope_text(self.last_roots)
        if stopped:
            self.scope_var.set("⛔  Stopped — " + roots_txt
                               + f"   ·   {len(items):,} files found so far (partial)")
            self.status.config(text="Stopped. Pick another folder, or search what was found.")
        else:
            self.scope_var.set("📂  Searching in:  " + roots_txt + f"   ·   {len(items):,} files")
            self.status.config(text=f"Found {len(items):,} files in {secs:0.1f}s. "
                                     f"Type part of a name to search.")
        self.search_entry.focus_set()
        self._do_search()

    def _set_index(self, items):
        self.index = [(os.path.basename(p).lower(), p, m) for p, m in items if p]

    # --- search + sort ------------------------------------------------------
    def _on_type(self, event=None):
        if self._debounce:
            self.root.after_cancel(self._debounce)
        self._debounce = self.root.after(120, self._do_search)

    def _do_search(self):
        self._debounce = None
        q = self.search_var.get().strip().lower()
        self.results = []
        if not self.index:
            self._clear_results()
            return
        if not q:
            self._clear_results()
            self.status.config(text=f"{len(self.index):,} files ready. Type to search.")
            return
        capped = False
        for tup in self.index:                    # (name_lower, path, mtime)
            if q in tup[0]:
                self.results.append(tup)
                if len(self.results) >= COLLECT_CAP:
                    capped = True
                    break
        self._capped = capped
        self._render_results()

    def sort_by(self, col):
        if self.sort_col == col:
            self.sort_desc = not self.sort_desc
        else:
            self.sort_col = col
            self.sort_desc = (col == "modified")  # dates default newest-first
        self._update_headings()
        self._render_results()

    def _update_headings(self):
        arrow = " ▼" if self.sort_desc else " ▲"
        for c, base in (("name", "File"), ("modified", "Date modified"), ("folder", "Location")):
            self.tree.heading(c, text=base + (arrow if c == self.sort_col else ""))

    def _render_results(self):
        self._clear_results()
        rows = self.results
        if self.sort_col:
            keyfn = {
                "name": lambda t: t[0],
                "modified": lambda t: t[2],
                "folder": lambda t: t[1].lower(),
            }[self.sort_col]
            rows = sorted(rows, key=keyfn, reverse=self.sort_desc)
        shown = rows[:MAX_RESULTS]
        for name_lower, path, mtime in shown:
            self.tree.insert("", "end", values=(os.path.basename(path), fmt_date(mtime), path))
        total = len(self.results)
        if getattr(self, "_capped", False):
            self.status.config(text=f"Showing {len(shown):,} of {COLLECT_CAP:,}+ matches — "
                                     f"type a bit more to narrow it down.")
        else:
            more = f" (showing first {MAX_RESULTS:,})" if total > MAX_RESULTS else ""
            self.status.config(text=f"{total:,} match" + ("" if total == 1 else "es") + more)

    def _clear_results(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    # --- actions ------------------------------------------------------------
    def _selected_path(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self.tree.item(sel[0], "values")[2]

    def _open_selected(self, event=None):
        path = self._selected_path()
        if path:
            if not open_in_explorer(path):
                messagebox.showerror(APP_TITLE, "Could not open Explorer for:\n" + path)

    def _copy_selected(self, event=None):
        path = self._selected_path()
        if path:
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.root.update()
            self.status.config(text="Copied: " + path)

    def _popup_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.menu.tk_popup(event.x_root, event.y_root)

    def _open_url(self, url):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass


def main():
    root = tk.Tk()
    FindFileApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
