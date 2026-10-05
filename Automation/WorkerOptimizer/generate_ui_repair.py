"""Regenerate the startup hook and adaptive widget, then run their regressions."""
from pathlib import Path
import runpy
for name in ('generate_lifecycle.py', 'generate_widget.py', 'test_startup_layout.py'):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name='__main__')
