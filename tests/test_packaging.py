# -*- coding: utf-8 -*-
import re

from gcode_profiler import version
from gcode_profiler.resources import resource_path, user_data_dir


def test_version_is_semver():
    assert re.match(r"^\d+\.\d+\.\d+(-[\w.]+)?$", version.__version__)


def test_resource_path_resolves_icon():
    assert resource_path("GCode_Profile_Reverse_Engineer.ico") is not None


def test_user_data_dir_outside_cwd():
    d = user_data_dir()
    assert "GcodeProfiler" in d


def test_iss_appid_stable():
    import os
    iss = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "installer", "GcodeProfiler.iss")
    with open(iss, encoding="utf-8") as f:
        text = f.read()
    assert "B7E9F2A1-3C4D-4E5F-9A8B-1C2D3E4F5A6B" in text  # stable AppId present


def test_smoke_mode_importable():
    import app
    assert app._smoke_test() == 0
