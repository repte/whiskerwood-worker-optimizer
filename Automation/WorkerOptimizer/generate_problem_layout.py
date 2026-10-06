"""Compile live snapshot slots and protected incumbents into planner coordinates."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
snapshot_class = unreal.load_class(None, ROOT + "/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C")
worker_class = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
bp = unreal.load_asset(ROOT + "/BP_ProblemLayout")
if bp is None:
    bp = BP.create(ROOT, "BP_ProblemLayout", unreal.Object.static_class())
existing = set(BP.list_variables(bp))
if "Snapshot" not in existing:
    BP.add_object_variable(bp, "Snapshot", snapshot_class)
for name in ("ColumnActors", "SeenOccupants"):
    if name not in existing:
        BP.add_object_variable(bp, name, worker_class, container_type=ContainerType.ARRAY)
for kind, names in {
    "bool": "LayoutActive LayoutDone LayoutSucceeded AnyRequired HasFixed ColumnsReady HasProtectedOptional",
    "int": "BuildingIndex SlotIndex WorkerIndex MinimumFallbackRow ProtectionRow",
    "name": "FailureCode",
    "int[]": "RowBuildings RowSlots Incumbents FixedSlots ColumnWorkers BuildingStarts",
    "bool[]": "Minimum SchoolBuildings FlexibleMinimumBuildings",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "FailLayout": [("Reason", "name")],
    "BeginLayout": [("InputSnapshot", snapshot_class)],
    "CaptureLayoutRow": [],
    "AdvanceLayout": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["CaptureLayoutRow"]


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def sg(name, source=None):
    return f"(Class|BPWorkforceSnapshot|Get{name} :self {source or g('Snapshot')})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def count(array):
    return f"(Utilities|Array|Length {array})"


def add(name, value):
    return f"(Utilities|Array|Add {g(name)} {value})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in BP.get_node_type_pins(context, node).output_pins)}) ({node} {value}))"


def fail(reason):
    return f'(CallFunction|FailLayout :Reason "{reason}") (return false)'


arrays = "RowBuildings RowSlots Incumbents FixedSlots ColumnWorkers BuildingStarts Minimum SchoolBuildings FlexibleMinimumBuildings ColumnActors SeenOccupants".split()
clear = " ".join(f"(Utilities|Array|Clear {g(name)})" for name in arrays)
shape_checks = []
for primary, companions in (("Buildings", ("Workforces", "PrefabKeys", "BuildingIds")),
                            ("Workers", ("WorkerWorkplaces", "Characteristics", "States", "WorkerIds"))):
    for other in companions:
        shape_checks.append(f"(if (!= {count(sg(primary, 'InputSnapshot'))} {count(sg(other, 'InputSnapshot'))}) {fail('invalid_shape')})")

code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["FailLayout"] = f"""(fn FailLayout (Reason)
    {put('LayoutActive', 'false')} {put('LayoutDone', 'true')} {put('LayoutSucceeded', 'false')}
    {put('FailureCode', 'Reason')} {clear} (return false))"""
code["BeginLayout"] = f"""(fn BeginLayout (InputSnapshot)
    (if {g('LayoutActive')} (return false))
    {clear} {put('LayoutDone', 'false')} {put('LayoutSucceeded', 'false')}
    {put('FailureCode', '"None"')} {put('BuildingIndex', '0')} {put('SlotIndex', '0')} {put('WorkerIndex', '0')}
    {put('ColumnsReady', 'false')} {put('HasProtectedOptional', 'false')} {put('ProtectionRow', '0')}
    (if (not {present('InputSnapshot')}) {fail('invalid_snapshot')})
    (if (not (and {sg('SnapshotValid', 'InputSnapshot')} {sg('CaptureDone', 'InputSnapshot')})) {fail('invalid_snapshot')})
    (if (or (> {count(sg('Buildings', 'InputSnapshot'))} 10000) (> {count(sg('Workers', 'InputSnapshot'))} 10000)) {fail('too_large')})
    {' '.join(shape_checks)}
    {put('Snapshot', 'InputSnapshot')} {put('ColumnActors', sg('Workers'))}
    {put('LayoutActive', 'true')} (return true))"""
code["CaptureLayoutRow"] = f"""(fn CaptureLayoutRow ()
    (if (>= {count(g('RowBuildings'))} 10000) {fail('too_large')})
    {unpack('WorkerAssignment', at(sg('Workforces'), g('BuildingIndex')), 'wf')}
    {unpack('WorkerSlot', at('wf_m_workerSlots', g('SlotIndex')), 'slot')}
    {add('RowBuildings', g('BuildingIndex'))} {add('RowSlots', g('SlotIndex'))}
    {add('Minimum', 'slot_bIsRequiredToRun')}
    (if slot_bIsRequiredToRun {put('AnyRequired', 'true')})
    (if (not {present('slot_Agent')})
      {add('Incumbents', '-1')} {add('FixedSlots', '-1')} (return true))
    (if (Utilities|Array|ContainsItem {g('SeenOccupants')} slot_Agent) {fail('duplicate_occupant')})
    {add('SeenOccupants', 'slot_Agent')}
    (bind oldIndex (Utilities|Array|FindItem {sg('Workers')} slot_Agent))
    (if (>= oldIndex 0)
      (if (!= {at(sg('WorkerWorkplaces'), 'oldIndex')} {at(sg('Buildings'), g('BuildingIndex'))}) {fail('inconsistent_workplace')})
      {add('Incumbents', 'oldIndex')} {add('FixedSlots', '-1')} (return true))
    (if (>= {count(g('ColumnActors'))} 10000) {fail('too_large')})
    {add('FixedSlots', count(g('ColumnActors')))}
    {add('Incumbents', '-2')} {add('ColumnWorkers', '-2')} {add('ColumnActors', 'slot_Agent')}
    (if (not slot_bIsRequiredToRun) {put('HasProtectedOptional', 'true')})
    (if (and (not {g('HasFixed')}) (not {at(g('SchoolBuildings'), g('BuildingIndex'))}))
      {put('MinimumFallbackRow', f'(- {count(g("RowBuildings"))} 1)')})
    {put('HasFixed', 'true')} (return true))"""
# Native required-slot fires also clear optional slots. Protect their unavailable
# incumbents by pinning occupied required slots, at most one layout row per step.
code["AdvanceLayout"] = f"""(fn AdvanceLayout ()
    (if (not {g('LayoutActive')}) (return false))
    (if (not {present(g('Snapshot'))}) {fail('invalid_snapshot')})
    (if (not (and {sg('SnapshotValid')} {sg('CaptureDone')})) {fail('invalid_snapshot')})
    (if (not {g('ColumnsReady')})
      (if (< {g('WorkerIndex')} {count(sg('Workers'))})
        {add('ColumnWorkers', g('WorkerIndex'))} {put('WorkerIndex', f'(+ {g("WorkerIndex")} 1)')}
        (else {put('ColumnsReady', 'true')} {put('WorkerIndex', '0')})) (return true))
    (if (< {g('BuildingIndex')} {count(sg('Buildings'))})
      (if (== {g('SlotIndex')} 0)
        (bind unchanged (Class|BPWorkforceSnapshot|BuildingUnchanged :self {g('Snapshot')} :Index {g('BuildingIndex')}))
        (if (not unchanged) {fail('world_changed')})
        {add('BuildingStarts', count(g('RowBuildings')))}
        {put('MinimumFallbackRow', count(g('RowBuildings')))} {put('AnyRequired', 'false')} {put('HasFixed', 'false')}
        {put('ProtectionRow', count(g('RowBuildings')))} {put('HasProtectedOptional', 'false')}
        (bind school (Actor|GetComponentbyClass :self {at(sg('Buildings'), g('BuildingIndex'))} :ComponentClass "/Script/ProjectArco.School"))
        {add('SchoolBuildings', present('school'))} {add('FlexibleMinimumBuildings', 'false')})
      {unpack('WorkerAssignment', at(sg('Workforces'), g('BuildingIndex')), 'wf')}
      (if (>= {g('SlotIndex')} {count('wf_m_workerSlots')})
        (if (and {g('HasProtectedOptional')} (< {g('ProtectionRow')} {count(g('RowBuildings'))}))
          (bind incumbent {at(g('Incumbents'), g('ProtectionRow'))})
          (if (and {at(g('Minimum'), g('ProtectionRow'))} (>= incumbent 0))
            (Utilities|Array|SetArrayElem :TargetArray {g('FixedSlots')} :Index {g('ProtectionRow')} :Item incumbent))
          {put('ProtectionRow', f'(+ {g("ProtectionRow")} 1)')} (return true))
        (if (and (not {g('AnyRequired')}) (> {count('wf_m_workerSlots')} 0))
          (if {at(g('SchoolBuildings'), g('BuildingIndex'))}
            (Utilities|Array|SetArrayElem :TargetArray {g('Minimum')} :Index {g('MinimumFallbackRow')} :Item true)
            (else (Utilities|Array|SetArrayElem :TargetArray {g('FlexibleMinimumBuildings')} :Index {g('BuildingIndex')} :Item true))))
        {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} {put('SlotIndex', '0')} (return true))
      (bind captured (CallFunction|CaptureLayoutRow))
      (if (not captured) (return false))
      {put('SlotIndex', f'(+ {g("SlotIndex")} 1)')} (return true))
    (if (< {g('WorkerIndex')} {count(sg('Workers'))})
      (bind unchangedWorker (Class|BPWorkforceSnapshot|WorkerUnchanged :self {g('Snapshot')} :Index {g('WorkerIndex')}
        :ReportedWorkplace {at(sg('WorkerWorkplaces'), g('WorkerIndex'))}))
      (if (not unchangedWorker) {fail('world_changed')})
      (if {present(at(sg('WorkerWorkplaces'), g('WorkerIndex')))}
        (if (not (Utilities|Array|ContainsItem {g('SeenOccupants')} {at(sg('Workers'), g('WorkerIndex'))})) {fail('inconsistent_workplace')}))
      {put('WorkerIndex', f'(+ {g("WorkerIndex")} 1)')} (return true))
    {put('LayoutActive', 'false')} {put('LayoutDone', 'true')} {put('LayoutSucceeded', 'true')} (return true))"""

for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        # Rewritten bodies must not retain old parameter-linked nodes.
        result_kept = False
        for old_node in BP.find_nodes(graphs[name]):
            kind = old_node.get_class().get_name()
            if kind == "K2Node_FunctionEntry":
                continue
            if kind == "K2Node_FunctionResult" and not result_kept:
                result_kept = True
                for pin in BP.get_node_infos([old_node])[0].input_pins:
                    for connected in pin.connected_pins:
                        BP.break_pins(connected, pin.pin_id)
                continue
            BP.delete_node(old_node)
        unreal.log("WO_PROBLEM_LAYOUT_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ProblemLayout.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_PROBLEM_LAYOUT_GENERATED")
exec(Path(__file__).with_name("test_action_plan.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_native_fire_dependencies.py").read_text(encoding="utf-8"))
