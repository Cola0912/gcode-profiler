# -*- coding: utf-8 -*-
"""Resource and user-data path resolution (source + PyInstaller onefile/onedir)."""
import os
import sys


def resource_path(relative_path):
    """Resolve a bundled read-only resource path, independent of CWD.
    Works in source execution and PyInstaller --onefile/--onedir builds."""
    bases = []
    if hasattr(sys, "_MEIPASS"):
        bases.append(sys._MEIPASS)                     # onefile temp / onedir root
    if getattr(sys, "frozen", False):
        bases.append(os.path.dirname(sys.executable))  # onedir exe dir
    here = os.path.dirname(os.path.abspath(__file__))
    bases.append(os.path.dirname(here))                # project root (source)
    bases.append(here)
    bases.append(os.getcwd())
    for b in bases:
        p = os.path.join(b, relative_path)
        if os.path.exists(p):
            return p
    return None


def user_data_dir():
    """Mutable user-data directory (never inside the install dir)."""
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") \
        or os.path.expanduser("~")
    path = os.path.join(base, "GcodeProfiler")
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path
