"""Generate one guarded, read-only adapter from reflected workplace components."""

import json
from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_WorkplaceAdapter")
if bp is None:
    bp = BP.create(ROOT, "BP_WorkplaceAdapter", unreal.Object.static_class())
graphs = {str(g.get_name()): g for g in BP.list_graphs(bp)}
if "ReadWorkplace" in graphs:
    graph = graphs["ReadWorkplace"]
else:
    graph = BP.add_function_graph(bp, "ReadWorkplace")
    BP.add_object_function_param(graph, "Building", unreal.load_class(None, "/Script/ProjectArco.GridActor"), True)
    BP.add_function_param(graph, "Known", "bool", False)
    BP.add_struct_function_param(graph, "Workforce", unreal.load_object(None, "/Script/ProjectArco.WorkerAssignment"), False)
workforce_struct = unreal.load_object(None, "/Script/ProjectArco.WorkerAssignment")
if "ReadComponent" in graphs:
    component_graph = graphs["ReadComponent"]
else:
    component_graph = BP.add_function_graph(bp, "ReadComponent")
    BP.add_object_function_param(component_graph, "component", unreal.ActorComponent.static_class(), True)
    BP.add_function_param(component_graph, "Known", "bool", False)
    BP.add_struct_function_param(component_graph, "Workforce", workforce_struct, False)
existing_variables = BP.list_variables(bp)
if "FoundCount" not in existing_variables:
    BP.add_variable(bp, "FoundCount", "int")
if "FoundWorkforce" not in existing_variables:
    BP.add_struct_variable(bp, "FoundWorkforce", workforce_struct)
with toolset_registry.tool_raising_exceptions():
    BP.compile_blueprint(bp)
    types = BP.find_node_types(graph, "", [])
    component_nodes = []
    for node_id in sorted(types):
        parts = node_id.split("|")
        if len(parts) != 3 or parts[0] != "Class" or parts[2] != "GetMWorkers":
            continue
        cls_path = "/Script/ProjectArco." + parts[1]
        cls = unreal.load_class(None, cls_path)
        if cls and unreal.MathLibrary.class_is_child_of(cls, unreal.ActorComponent.static_class()):
            component_nodes.append((cls_path, parts[1], node_id))
    assert component_nodes, "No readable workplace components discovered"
    component_query = next(n for n in types if n.lower() == "actor|getcomponentsbyinterface")
    all_components = next(n for n in types if n.lower() == "actor|getcomponentsbyclass")
    query_info = BP.get_node_type_pins(graph, component_query)
    assert "Interface" in [p.name for p in query_info.input_pins]
    chain = "(return false)"
    for cls_path, cls_name, getter in reversed(component_nodes):
        cast = next(n for n in types if n.lower() == "utilities|casting|castto" + cls_name.lower())
        chain = f"""
        (bind typed ({cast} :Object component)
          (:then (return true ({getter} :self typed)))
          (:CastFailed {chain}))
        """
    BP.write_graph_dsl(component_graph, f"(fn ReadComponent (component) {chain})")
    # In 0.7.209.0 ResourceBuilding (including GranaryResourceBuilding) exposes
    # legacy m_workers but its native AgentEnterable assignment getter returns null.
    # Keep ReadComponent intact so occupants remain protected by the snapshot.
    code = f"""
    (fn ReadWorkplace (Building)
      (Utilities|IsValid :InputObject Building
        (:"Is Valid"
          (bind unsupported ({all_components} :self Building :ComponentClass "/Script/ProjectArco.ResourceBuilding"))
          (if (> (Utilities|Array|Length unsupported) 0) (return false))
          (Variables|Default|SetFoundCount 0)
          (bind components ({all_components} :self Building :ComponentClass "/Script/Engine.ActorComponent"))
          (for component components
            (bind (known workforce) (CallFunction|ReadComponent :component component))
            (if known
              (Variables|Default|SetFoundCount (+ (Variables|Default|GetFoundCount) 1))
              (Variables|Default|SetFoundWorkforce workforce)))
          (if (!= (Variables|Default|GetFoundCount) 1) (return false))
          (bind nativeWorkplaces ({component_query} :self Building :Interface "/Script/ProjectArco.AgentEnterable"))
          (if (> (Utilities|Array|Length nativeWorkplaces) (Variables|Default|GetFoundCount)) (return false))
          (return true (Variables|Default|GetFoundWorkforce)))
        (:"Is Not Valid" (return false))))
    """
    BP.write_graph_dsl(graph, code)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Workplace.dsl").write_text(code, encoding="utf-8")
    Path(unreal.Paths.project_dir(), "Docs/WorkerOptimizer/WORKPLACE-COMPATIBILITY.json").write_text(
        json.dumps({
            "game_version": "0.7.209.0",
            "component_classes": [p for p, _, _ in component_nodes],
            "non_assignable_component_families": {
                "/Script/ProjectArco.ResourceBuilding": "Native AgentEnterable assignment getter returns null; readable occupants are protected."
            },
        }, indent=2), encoding="utf-8"
    )
unreal.log(f"WO_WORKPLACE_GENERATED: {len(component_nodes)} reflected component types, no building list")
exec(Path(__file__).with_name("test_workplace.py").read_text(encoding="utf-8"))
