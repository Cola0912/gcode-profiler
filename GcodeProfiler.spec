# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Gcode Profiler.

Drives both build modes from one spec via the GP_ONEFILE environment variable:
  GP_ONEFILE=1  -> portable single-file exe
  (unset)       -> --onedir application directory (used by the installer)

Windows executable metadata is generated from gcode_profiler/version.py so the
version is never hard-coded here.
"""
import os

block_cipher = None
ROOT = os.path.abspath(os.getcwd())

# --- canonical version ---
_ver_ns = {}
with open(os.path.join(ROOT, "gcode_profiler", "version.py"), encoding="utf-8") as _f:
    exec(_f.read(), _ver_ns)
APP_VERSION = _ver_ns["__version__"]
APP_NAME = _ver_ns.get("APP_NAME", "Gcode Profiler")
APP_PUBLISHER = _ver_ns.get("APP_PUBLISHER", "Shusei Aida")
_vt = tuple(int(p) for p in (APP_VERSION.split("-")[0].split(".") + ["0", "0", "0", "0"])[:4])

ICON = os.path.join(ROOT, "GCode_Profile_Reverse_Engineer.ico")

# --- Windows VERSIONINFO file (generated from canonical version) ---
version_info = f"""
VSVersionInfo(
  ffi=FixedFileInfo(filevers={_vt}, prodvers={_vt}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', '{APP_PUBLISHER}'),
      StringStruct('FileDescription', '{APP_NAME}'),
      StringStruct('FileVersion', '{APP_VERSION}'),
      StringStruct('InternalName', 'GcodeProfiler'),
      StringStruct('LegalCopyright', 'Copyright 2026 {APP_PUBLISHER}'),
      StringStruct('OriginalFilename', 'GcodeProfiler.exe'),
      StringStruct('ProductName', '{APP_NAME}'),
      StringStruct('ProductVersion', '{APP_VERSION}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""
_VI_PATH = os.path.join(ROOT, "build_version_info.txt")
with open(_VI_PATH, "w", encoding="utf-8") as _f:
    _f.write(version_info)

datas = [
    (ICON, "."),
    (os.path.join(ROOT, "LICENSE"), "."),
    (os.path.join(ROOT, "NOTICE"), "."),
    (os.path.join(ROOT, "THIRD_PARTY_LICENSES.md"), "."),
]

_catalog_root = os.path.join(ROOT, "parameter_catalogs")
if os.path.isdir(_catalog_root):
    for _dir, _dirs, _files in os.walk(_catalog_root):
        for _name in _files:
            _src = os.path.join(_dir, _name)
            _rel_dir = os.path.relpath(_dir, ROOT)
            datas.append((_src, _rel_dir))

a = Analysis(
    ["app.py"],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=["gcode_profiler"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "pytest", "numpy", "PySide6.QtWebEngineCore"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

ONEFILE = bool(os.environ.get("GP_ONEFILE"))

if ONEFILE:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
        name="GcodeProfiler", debug=False, bootloader_ignore_signals=False,
        strip=False, upx=False, runtime_tmpdir=None, console=False,
        icon=ICON, version=_VI_PATH,
    )
else:
    exe = EXE(
        pyz, a.scripts, [], exclude_binaries=True,
        name="GcodeProfiler", debug=False, bootloader_ignore_signals=False,
        strip=False, upx=False, console=False, icon=ICON, version=_VI_PATH,
    )
    coll = COLLECT(
        exe, a.binaries, a.zipfiles, a.datas, strip=False, upx=False,
        name="GcodeProfiler",
    )
