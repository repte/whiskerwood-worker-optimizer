"""Regenerate only the assignment recovery controller and affected status views."""
from pathlib import Path
import runpy

import unreal

for name in ("generate_controller.py", "generate_logbook_view.py", "generate_widget.py", "test_assignment_hotfix.py"):
    runpy.run_path(str(Path(__file__).with_name(name)), run_name="__main__")
unreal.log("WO_ASSIGNMENT_HOTFIX_GENERATED")
