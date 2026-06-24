# Kiwi Simple — Find File

A tiny, free Windows app that **finds a file by part of its name, fast** — then opens it
in File Explorer. It searches any folder or your **whole PC**, including the
system-adjacent folders a web browser is not allowed to read.

**100% private** — it runs entirely on your own machine. Nothing is uploaded.

---

## Download & run (for everyone — no coding needed)

1. Go to the **[latest release](../../releases/latest)** and download **`KiwiSimpleFindFile.exe`**.
2. **Double-click** it. No install, no Python, no setup.
3. If Windows shows *"Windows protected your PC"*, click **More info → Run anyway**.
   (That warning appears for every small app that isn't from a big company — it's safe;
   it's our free tool and the source code is right here in this folder.)
4. Click **Scan a folder…** or **Scan whole PC**, type part of a file name, and
   **double-click** a result to open it in Explorer.

The first whole-PC scan can take up to a minute; after that it's saved, so searches are
instant.

---

## Run the source directly (if you have Python)

```bash
python find_file.py
```

No third-party packages required — it uses only the Python standard library (Tkinter).
Tested on Python 3.12, Windows.

---

## Why does this exist?

Web pages aren't allowed to search your computer's files — browsers block it for security.
So we made a small desktop app that can do what a website can't. It's the desktop companion
to **[kiwisimple.nz](https://kiwisimple.nz)**.

## Build the .exe yourself

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name KiwiSimpleFindFile find_file.py
# output: dist/KiwiSimpleFindFile.exe
```

---

Free tool from **[kiwisimple.nz](https://kiwisimple.nz)** • Made in New Zealand
