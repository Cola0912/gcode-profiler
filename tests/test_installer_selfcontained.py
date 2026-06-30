# -*- coding: utf-8 -*-
"""Guard tests: the user installer must be self-contained (no dev tools)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISS = os.path.join(ROOT, "installer", "GcodeProfiler.iss")


def _read():
    with open(ISS, encoding="utf-8") as f:
        return f.read()


def _section(text, name):
    """Return the lines of a [Section] from an .iss file."""
    lines = text.splitlines()
    out, cur = [], None
    for ln in lines:
        m = re.match(r"^\s*\[(\w+)\]\s*$", ln)
        if m:
            cur = m.group(1).lower()
            continue
        if cur == name.lower():
            s = ln.strip()
            if s and not s.startswith(";"):
                out.append(s)
    return out


def test_files_do_not_bundle_dev_tools():
    files = " ".join(_section(_read(), "Files")).lower()
    for forbidden in ("iscc", "innosetup", "inno setup", "python.exe", "pip",
                      "get-pip", "pyinstaller"):
        assert forbidden not in files, f"installer [Files] must not bundle {forbidden}"


def test_run_section_only_launches_app():
    runs = _section(_read(), "Run")
    # the only [Run] entry must be launching the app exe; never pip/python/iscc/curl
    for r in runs:
        low = r.lower()
        assert "{#myappexename}" in low or "{app}\\" in low
        for forbidden in ("pip", "python", "iscc", "curl", "powershell -c",
                          "invoke-webrequest", "msiexec"):
            assert forbidden not in low, f"[Run] must not invoke {forbidden}"


def test_appid_present_and_stable():
    assert "B7E9F2A1-3C4D-4E5F-9A8B-1C2D3E4F5A6B" in _read()


def test_bundles_full_onedir_output():
    files = " ".join(_section(_read(), "Files")).lower()
    assert "sourcedir" in files and "recursesubdirs" in files
