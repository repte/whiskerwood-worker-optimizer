"""Read-only editor inspection of the game's worker-assignment protocol."""

import unreal


assets = [
    "/Game/UI/SpatialWorkerAssignmentWIdget",
    "/Game/UI/SpatialWorkerSlot",
    "/Game/UI/WorkerSlot_CircleDesign",
    "/Game/UI/DebugUI_Components/WorkerAssignmentPanel_BP",
    "/Game/UI/WhiskerDetails/ClearAssignment_WhiskerSelectionRow",
    "/Game/UI/WhiskerDetails/GenericAgentSelector",
    "/Game/UI/WhiskerDetails/BP_CondensedWhiskerSummary_ListViewEntry",
]

for path in assets:
    asset = unreal.load_class(None, path + "." + path.rsplit("/", 1)[1] + "_C")
    if asset is None:
        raise RuntimeError("Could not load " + path)
    unreal.log("WO_INSPECT_LOADED " + path)

unreal.SystemLibrary.execute_console_command(None, "DISASMSCRIPT Worker")
unreal.SystemLibrary.execute_console_command(None, "DISASMSCRIPT ClearAssignment")
unreal.SystemLibrary.execute_console_command(None, "DISASMSCRIPT GenericAgentSelector")
unreal.SystemLibrary.execute_console_command(None, "DISASMSCRIPT CondensedWhisker")
unreal.log("WO_INSPECT_COMPLETE")
