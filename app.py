# -*- coding: utf-8 -*-
"""Gcode Profiler entry point.

Usage:
    GcodeProfiler.exe                       launch GUI
    GcodeProfiler.exe "path\\to\\file.gcode"  launch GUI and open the file
    GcodeProfiler.exe --smoke-test          headless self-check (CI/packaging), exit 0/1
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _smoke_test():
    """Non-interactive startup check: import modules, load schema/registries,
    verify bundled resources. No GUI, no network. Exit 0 on success."""
    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from gcode_profiler import version, schema, exporters, analyzer, nozzle_estimator  # noqa
        from gcode_profiler.resources import resource_path
        # schema must expose the three groups
        assert set(schema.GROUPS) == {"printer", "filament", "process"}
        # exporters registry must be non-empty
        assert exporters.TARGETS
        # icon resource must resolve (best effort)
        ip = resource_path("GCode_Profile_Reverse_Engineer.ico")
        print(f"[smoke-test] version={version.__version__} "
              f"groups={len(schema.GROUPS)} targets={len(exporters.TARGETS)} "
              f"icon={'ok' if ip and os.path.exists(ip) else 'missing'}")
        print("[smoke-test] OK")
        return 0
    except Exception as exc:  # noqa
        import traceback
        sys.stderr.write("[smoke-test] FAILED: %s\n%s\n" % (exc, traceback.format_exc()))
        return 1


def main():
    args = sys.argv[1:]
    if "--smoke-test" in args:
        sys.exit(_smoke_test())
    # first non-flag argument is an optional input file
    open_file = None
    for a in args:
        if not a.startswith("-"):
            open_file = a
            break
    from gcode_profiler.gui import main as gui_main
    gui_main(open_file=open_file)


if __name__ == "__main__":
    main()
