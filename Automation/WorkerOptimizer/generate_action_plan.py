"""Compile a complete snapshot assignment into a validated native action queue."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_ActionPlan")
if bp is None:
    bp = BP.create(ROOT, "BP_ActionPlan", unreal.Object.static_class())
existing = set(BP.list_variables(bp))
if "Snapshot" not in existing:
    BP.add_object_variable(bp, "Snapshot", load("BP_WorkforceSnapshot"))
worker_class = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
for name in ("Targets", "SeenOccupants"):
    if name not in existing:
        BP.add_object_variable(bp, name, worker_class, container_type=ContainerType.ARRAY)
for kind, names in {
    "bool": "BuildActive BuildDone BuildSucceeded",
    "int": "Stage BuildingIndex SlotIndex RowIndex",
    "name": "FailureCode",
    "int[]": "FinalWorkers RowBuildings RowSlots OldWorkers SeenTargets BuildingStarts ActionBuildings ActionSlots ActionWorkers",
    "bool[]": "Required BuildingHasAny BuildingHasMovable BuildingMissingRequired ActionFire",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "FailBuild": [("Reason", "name")],
    "BeginBuild": [("InputSnapshot", load("BP_WorkforceSnapshot")), ("InputWorkers", "int[]")],
    "CaptureRow": [],
    "ValidateRow": [],
    "AppendAction": [("Fire", "bool")],
    "AdvanceBuild": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind.removesuffix("[]"), True, ContainerType.ARRAY if kind.endswith("[]") else None)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["BeginBuild"]


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def row(name):
    return at(g(name), g("RowIndex"))


def sg(name, source=None):
    return f"(Class|BPWorkforceSnapshot|Get{name} :self {source or g('Snapshot')})"


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in BP.get_node_type_pins(context, node).output_pins)}) ({node} {value}))"


def add(name, value):
    return f"(Utilities|Array|Add {g(name)} {value})"


def set_item(name, index, value):
    return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def fail(reason):
    return f'(CallFunction|FailBuild :Reason "{reason}") (return false)'


queue_names = "ActionBuildings ActionSlots ActionWorkers ActionFire".split()
arrays = "Targets SeenOccupants FinalWorkers RowBuildings RowSlots OldWorkers SeenTargets BuildingStarts Required BuildingHasAny BuildingHasMovable BuildingMissingRequired".split() + queue_names
clear_queue = " ".join(f"(Utilities|Array|Clear {g(n)})" for n in queue_names)
code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["FailBuild"] = f"""(fn FailBuild (Reason)
    {put('BuildActive', 'false')} {put('BuildDone', 'true')} {put('BuildSucceeded', 'false')}
    {put('FailureCode', 'Reason')} {clear_queue} (return false))"""
code["BeginBuild"] = f"""(fn BeginBuild (InputSnapshot InputWorkers)
    (if {g('BuildActive')} (return false))
    {put('BuildDone', 'false')} {put('BuildSucceeded', 'false')} {put('FailureCode', '"None"')}
    {' '.join(f'(Utilities|Array|Clear {g(n)})' for n in arrays)}
    {put('Stage', '6')} {put('BuildingIndex', '0')} {put('SlotIndex', '0')} {put('RowIndex', '0')}
    (if (not {present('InputSnapshot')}) {fail('invalid_snapshot')})
    (if (not (and {sg('SnapshotValid', 'InputSnapshot')} {sg('CaptureDone', 'InputSnapshot')})) {fail('invalid_snapshot')})
    (if (> (Utilities|Array|Length InputWorkers) 10000) {fail('invalid_shape')})
    {put('Snapshot', 'InputSnapshot')} {put('FinalWorkers', 'InputWorkers')}
    {put('BuildActive', 'true')} (return true))"""
code["CaptureRow"] = f"""(fn CaptureRow ()
    (if (not (Utilities|Array|IsValidIndex {g('FinalWorkers')} {g('RowIndex')})) {fail('invalid_shape')})
    (bind building {at(sg('Buildings'), g('BuildingIndex'))})
    {unpack('WorkerAssignment', at(sg('Workforces'), g('BuildingIndex')), 'wf')}
    {unpack('WorkerSlot', at('wf_m_workerSlots', g('SlotIndex')), 'slot')}
    (bind target {row('FinalWorkers')})
    (if (or (< target -2) (>= target (Utilities|Array|Length {sg('Workers')}))) {fail('invalid_worker')})
    {add('RowBuildings', g('BuildingIndex'))} {add('RowSlots', g('SlotIndex'))} {add('Required', 'slot_bIsRequiredToRun')}
    (if {present('slot_Agent')}
      (if (Utilities|Array|ContainsItem {g('SeenOccupants')} slot_Agent) {fail('duplicate_occupant')})
      {add('SeenOccupants', 'slot_Agent')}
      (bind oldIndex (Utilities|Array|FindItem {sg('Workers')} slot_Agent))
      (if (>= oldIndex 0)
        (if (!= {at(sg('WorkerWorkplaces'), 'oldIndex')} building) {fail('inconsistent_workplace')})
        {add('OldWorkers', 'oldIndex')}
        (if (== target -2) {fail('invalid_preserved_slot')})
        (else
          {add('OldWorkers', '-2')}
          (if (!= target -2) {fail('protected_occupant')})))
      (else
        {add('OldWorkers', '-1')}
        (if (== target -2) {fail('invalid_preserved_slot')})))
    (if (>= target 0)
      {set_item('BuildingHasMovable', g('BuildingIndex'), 'true')}
      (if (Utilities|Array|ContainsItem {g('SeenTargets')} target) {fail('duplicate_target')})
      {add('SeenTargets', 'target')} {add('Targets', at(sg('Workers'), 'target'))}
      (else
        (if (== target -2) {add('Targets', 'slot_Agent')}
          (else (Utilities|Array|Add :TargetArray {g('Targets')})))))
    (if (== target -1)
      (if slot_bIsRequiredToRun {set_item('BuildingMissingRequired', g('BuildingIndex'), 'true')})
      (else {set_item('BuildingHasAny', g('BuildingIndex'), 'true')}))
    (return true))"""
code["ValidateRow"] = f"""(fn ValidateRow ()
    (bind buildingIndex {row('RowBuildings')})
    (if (and {at(g('BuildingHasMovable'), 'buildingIndex')} {at(g('BuildingMissingRequired'), 'buildingIndex')}) {fail('incomplete_crew')})
    (if (== {row('FinalWorkers')} -1) (return true))
    (bind firstRow {at(g('BuildingStarts'), 'buildingIndex')})
    (bind teacher {at(g('Targets'), 'firstRow')})
    (if (== {row('FinalWorkers')} -2)
      (bind schoolComponent (Actor|GetComponentbyClass :self {at(sg('Buildings'), 'buildingIndex')} :ComponentClass "/Script/ProjectArco.School"))
      (if (not {present('schoolComponent')}) (return true))
      (if (== {row('RowSlots')} 0) (return true))
      {unpack('WorkerAssignment', at(sg('Workforces'), 'buildingIndex'), 'oldWorkforce')}
      {unpack('WorkerSlot', at('oldWorkforce_m_workerSlots', '0'), 'oldTeacher')}
      (if (== teacher oldTeacher_Agent) (return true)))
    (bind allowed (Class|BPJobEligibility|CanFillSlot :self {g('Snapshot')} :Worker {row('Targets')}
      :Building {at(sg('Buildings'), 'buildingIndex')} :SlotIndex {row('RowSlots')} :PlannedTeacher teacher))
    (if (not allowed) {fail('ineligible_assignment')})
    (return true))"""
code["AppendAction"] = f"""(fn AppendAction (Fire)
    {add('ActionBuildings', row('RowBuildings'))} {add('ActionSlots', row('RowSlots'))} {add('ActionFire', 'Fire')}
    (if Fire {add('ActionWorkers', row('OldWorkers'))} (else {add('ActionWorkers', row('FinalWorkers'))}))
    (return true))"""
code["AdvanceBuild"] = f"""(fn AdvanceBuild ()
    (if (not {g('BuildActive')}) (return false))
    (if (not {present(g('Snapshot'))}) {fail('invalid_snapshot')})
    (if (not (and {sg('SnapshotValid')} {sg('CaptureDone')})) {fail('invalid_snapshot')})
    (if (== {g('Stage')} 6)
      (if (>= {g('BuildingIndex')} (Utilities|Array|Length {sg('Buildings')}))
        {put('BuildingIndex', '0')} {put('Stage', '0')} (return true))
      {add('BuildingStarts', '-1')} {add('BuildingHasAny', 'false')} {add('BuildingHasMovable', 'false')} {add('BuildingMissingRequired', 'false')}
      {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} (return true))
    (if (== {g('Stage')} 0)
      (if (>= {g('BuildingIndex')} (Utilities|Array|Length {sg('Buildings')}))
        (if (!= {g('RowIndex')} (Utilities|Array|Length {g('FinalWorkers')})) {fail('invalid_shape')})
        {put('Stage', '1')} {put('RowIndex', '0')} (return true))
      (if (== {g('SlotIndex')} 0)
        (bind unchanged (Class|BPWorkforceSnapshot|BuildingUnchanged :self {g('Snapshot')} :Index {g('BuildingIndex')}))
        (if (not unchanged) {fail('world_changed')})
        {set_item('BuildingStarts', g('BuildingIndex'), g('RowIndex'))})
      {unpack('WorkerAssignment', at(sg('Workforces'), g('BuildingIndex')), 'wf')}
      (if (>= {g('SlotIndex')} (Utilities|Array|Length wf_m_workerSlots))
        {put('BuildingIndex', f'(+ {g("BuildingIndex")} 1)')} {put('SlotIndex', '0')} (return true))
      (bind captured (CallFunction|CaptureRow))
      (if (not captured) (return false))
      {put('RowIndex', f'(+ {g("RowIndex")} 1)')} {put('SlotIndex', f'(+ {g("SlotIndex")} 1)')} (return true))
    (if (== {g('Stage')} 1)
      (if (>= {g('RowIndex')} (Utilities|Array|Length {sg('Workers')}))
        {put('Stage', '2')} {put('RowIndex', '0')} (return true))
      (bind workerIndex {g('RowIndex')})
      (bind unchangedWorker (Class|BPWorkforceSnapshot|WorkerUnchanged :self {g('Snapshot')} :Index workerIndex
        :ReportedWorkplace {at(sg('WorkerWorkplaces'), 'workerIndex')}))
      (if (not unchangedWorker) {fail('world_changed')})
      (if {present(at(sg('WorkerWorkplaces'), 'workerIndex'))}
        (if (not (Utilities|Array|ContainsItem {g('SeenOccupants')} {at(sg('Workers'), 'workerIndex')})) {fail('inconsistent_workplace')}))
      {put('RowIndex', f'(+ {g("RowIndex")} 1)')} (return true))
    (if (== {g('Stage')} 2)
      (if (>= {g('RowIndex')} (Utilities|Array|Length {g('FinalWorkers')}))
        {put('Stage', '3')} {put('RowIndex', f'(- (Utilities|Array|Length {g("FinalWorkers")}) 1)')} (return true))
      (bind valid (CallFunction|ValidateRow))
      (if (not valid) (return false))
      {put('RowIndex', f'(+ {g("RowIndex")} 1)')} (return true))
    (if (== {g('Stage')} 3)
      (if (< {g('RowIndex')} 0) {put('Stage', '4')} {put('RowIndex', '0')} (return true))
      (if (and (>= {row('OldWorkers')} 0) (!= {row('OldWorkers')} {row('FinalWorkers')})) (CallFunction|AppendAction :Fire true))
      {put('RowIndex', f'(- {g("RowIndex")} 1)')} (return true))
    (if (>= {g('RowIndex')} (Utilities|Array|Length {g('FinalWorkers')}))
      (if (== {g('Stage')} 4) {put('Stage', '5')} {put('RowIndex', '0')} (return true))
      {put('BuildActive', 'false')} {put('BuildDone', 'true')} {put('BuildSucceeded', 'true')} (return true))
    (if (and (>= {row('FinalWorkers')} 0) (!= {row('OldWorkers')} {row('FinalWorkers')}))
      (if (== {row('Required')} (== {g('Stage')} 4)) (CallFunction|AppendAction :Fire false)))
    {put('RowIndex', f'(+ {g("RowIndex")} 1)')} (return true))"""

for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_ACTION_PLAN_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ActionPlan.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_ACTION_PLAN_GENERATED")
exec(Path(__file__).with_name("test_action_plan.py").read_text(encoding="utf-8"))
