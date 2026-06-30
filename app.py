# -*- coding: utf-8 -*-
"""exe エントリポイント"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gcode_profiler.gui import main

if __name__ == "__main__":
    main()
