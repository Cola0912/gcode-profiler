# Third-Party Licenses

Gcode Profiler is licensed under Apache-2.0. It depends on and/or bundles the
following third-party components at runtime. Each remains under its own license
and is **not** relicensed under Apache-2.0.

| Component | Version | License | Source / Homepage | Bundled |
|---|---|---|---|---|
| PySide6 (Qt for Python) | 6.x | LGPL-3.0 / Qt commercial | https://www.qt.io/qt-for-python | Yes (in app build) |
| Qt | 6.x | LGPL-3.0 / Qt commercial | https://www.qt.io | Yes (via PySide6) |
| Python standard library | 3.12 | PSF License | https://www.python.org | Runtime (via PyInstaller bootloader) |

Build-time only (not distributed in the application):

| Component | Version | License | Source |
|---|---|---|---|
| PyInstaller | 6.x | GPL-2.0 with bootloader exception | https://pyinstaller.org |
| pytest | (latest) | MIT | https://pytest.org |
| Inno Setup | 6.x | Inno Setup License (free) | https://jrsoftware.org/isinfo.php |

## LGPL compliance note (PySide6 / Qt)

The application is distributed under Apache-2.0 while dynamically linking the
LGPL-licensed Qt libraries (via PySide6). To remain LGPL-compliant when
redistributing binaries, the Qt/PySide6 shared libraries must be replaceable by
the user. The PyInstaller `--onedir` build keeps these as separate shared
libraries in the application directory, which preserves that ability.

> Verify and update this table against the actually bundled versions before any
> public release. Versions above are placeholders pending a build-time audit
> (`pip show PySide6 pyinstaller`).
