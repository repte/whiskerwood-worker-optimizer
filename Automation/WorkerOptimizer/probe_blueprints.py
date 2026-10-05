"""Read editor node schemas for the asset generator; saves no game assets."""

import json
from pathlib import Path

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = BP.create("/Game/Mods/WorkerOptimizer", "BP_NodeProbe", unreal.Object.static_class())
solver = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_AssignmentSolver.BP_AssignmentSolver_C")
if solver:
    BP.add_object_variable(bp, "Solver", solver)
graph = BP.add_function_graph(bp, "Probe")
schemas = {}
for query in ("WorkerAssignment", "WorkerSlot", "AgentState", "AgentCharacteristics", "GetIsPlayerOwned", "GetHealth", "GetID", "GetMState", "GetMCharacteristics", "GetWorkplace", "GetPrefabInfo", "GetGridActorDefinition", "Array", "WorkplaceAdapter"):
    for node_id in BP.find_node_types(graph, query, []):
        if query == "Utilities|Array" and node_id.rsplit("|", 1)[-1] not in (
            "Get(acopy)", "Get(aref)", "SetArrayElem", "Resize", "Clear", "Add", "Length"
        ):
            continue
        try:
            info = BP.get_node_type_pins(graph, node_id)
            schemas[node_id] = {
                direction: [{"name": p.name, "type": p.type_id, "value": p.value} for p in getattr(info, direction)]
                for direction in ("input_pins", "output_pins")
            }
        except Exception as exc:
            schemas[node_id] = {"error": str(exc)}
Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-node-schemas.json").write_text(
    json.dumps(schemas, indent=2, default=str), encoding="utf-8"
)
unreal.log("WO_NODE_PROBE_COMPLETE")
