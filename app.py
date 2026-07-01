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
    log_path = os.environ.get("GCODE_PROFILER_SMOKE_LOG")

    def log(step):
        if not log_path:
            return
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(step + "\n")
            fh.flush()

    try:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        log("start")
        from gcode_profiler import version  # noqa
        log("version")
        from gcode_profiler import schema  # noqa
        log("schema")
        from gcode_profiler import exporters  # noqa
        log("exporters")
        from gcode_profiler import analyzer  # noqa
        log("analyzer")
        from gcode_profiler import nozzle_estimator  # noqa
        log("nozzle_estimator")
        from gcode_profiler import canonical  # noqa  (Phase 1 foundation)
        log("canonical")
        from gcode_profiler import pipeline  # noqa  (Phase 2 generic analysis)
        log("pipeline")
        from gcode_profiler import conversion  # noqa  (Phase 4 conversion planning)
        log("conversion")
        from gcode_profiler import parameter_catalogs  # noqa
        log("parameter_catalogs")
        from gcode_profiler import writers  # noqa
        log("writers")
        from gcode_profiler import export_flow  # noqa
        log("export_flow")
        from gcode_profiler import importers  # noqa
        log("importers")
        from gcode_profiler.resources import resource_path
        log("resources")
        # schema must expose the three groups
        assert set(schema.GROUPS) == {"printer", "filament", "process"}
        log("assert_schema")
        assert canonical.SCHEMA_VERSION  # canonical model loads
        log("assert_canonical")
        assert conversion.TARGETS        # conversion registry loads
        log("assert_conversion")
        assert "orca" in parameter_catalogs.list_catalogs()
        log("assert_catalogs")
        assert writers.WRITERS
        log("assert_writers")
        assert export_flow.TARGET_CHOICES
        log("assert_export_flow")
        # exporters registry must be non-empty
        assert exporters.TARGETS
        log("assert_exporters")
        # icon resource must resolve (best effort)
        ip = resource_path("GCode_Profile_Reverse_Engineer.ico")
        log("icon")
        print(f"[smoke-test] version={version.__version__} "
              f"groups={len(schema.GROUPS)} targets={len(export_flow.TARGET_CHOICES)} "
              f"icon={'ok' if ip and os.path.exists(ip) else 'missing'}")
        print("[smoke-test] OK")
        log("ok")
        return 0
    except Exception as exc:  # noqa
        import traceback
        msg = "[smoke-test] FAILED: %s\n%s\n" % (exc, traceback.format_exc())
        log("failed")
        log(str(exc))
        try:
            if sys.stderr:
                sys.stderr.write(msg)
                sys.stderr.flush()
        except Exception:
            pass
        return 1


def main():
    args = sys.argv[1:]
    if "--smoke-test" in args:
        # In the windowed PyInstaller build, imported GUI/runtime modules can
        # leave background state alive. Smoke-test is intentionally headless and
        # must terminate deterministically for installer validation.
        rc = _smoke_test()
        try:
            if sys.stdout:
                sys.stdout.flush()
            if sys.stderr:
                sys.stderr.flush()
        except Exception:
            pass
        os._exit(rc)
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
