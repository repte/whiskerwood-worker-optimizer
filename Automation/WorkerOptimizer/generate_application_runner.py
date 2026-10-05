"""Generate serial native action dispatch and exact, bounded result observation."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_ApplicationRunner")
if bp is None:
    bp = BP.create(ROOT, "BP_ApplicationRunner", unreal.Object.static_class())
existing = set(BP.list_variables(bp))
for name, cls in (("Snapshot", load("BP_WorkforceSnapshot")), ("Bridge", load("BP_ActionBridge"))):
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "Active Done Succeeded Waiting",
    "int": "ActionIndex AppliedCount QueuedCount",
    "float": "LastTime Deadline",
    "name": "FailureCode",
    "int[]": "ActionBuildings ActionSlots ActionWorkers",
    "bool[]": "ActionFire",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)

building_cls = unreal.load_class(None, "/Script/ProjectArco.GridActor")
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "FailApplication": [("Reason", "name")],
    "ValidClock": [("Now", "float")],
    "StartApplication": [("InputSnapshot", load("BP_WorkforceSnapshot")), ("InputBridge", load("BP_ActionBridge")),
        ("InputBuildings", "int[]"), ("InputSlots", "int[]"), ("InputWorkers", "int[]"), ("InputFire", "bool[]"), ("Now", "float")],
    "CurrentActionValid": [],
    "PendingStateSafe": [("ReportedWorkplace", building_cls)],
    "RecordDispatch": [("Accepted", "bool"), ("Now", "float")],
    "ObserveAction": [("ReportedWorkplace", building_cls), ("Now", "float")],
    "AdvanceApplication": [("Now", "float")],
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
context = graphs["StartApplication"]


def get(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def action(name):
    return at(get("Action" + name), get("ActionIndex"))


def sg(name, source=None):
    return f"(Class|BPWorkforceSnapshot|Get{name} :self {source or get('Snapshot')})"


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    pins = BP.get_node_type_pins(context, node).output_pins
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in pins)}) ({node} {value}))"


def fail(reason):
    return f'(CallFunction|FailApplication :Reason "{reason}") (return false)'


def present(obj):
    return f"(CallFunction|HasObject :Object {obj})"


code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["FailApplication"] = f"""(fn FailApplication (Reason)
    {put('Active', 'false')} {put('Done', 'true')} {put('Succeeded', 'false')}
    {put('FailureCode', 'Reason')} (return false))"""
code["ValidClock"] = f"""(fn ValidClock (Now)
    (if (not (and (>= Now 0.0) (<= Now 1000000000.0))) (return false))
    (if (< Now {get('LastTime')}) (return false))
    {put('LastTime', 'Now')} (return true))"""
code["StartApplication"] = f"""(fn StartApplication (InputSnapshot InputBridge InputBuildings InputSlots InputWorkers InputFire Now)
    (if (or {get('Active')} {get('Waiting')}) (return false))
    {put('Done', 'false')} {put('Succeeded', 'false')} {put('FailureCode', '"None"')}
    {put('ActionIndex', '0')} {put('AppliedCount', '0')} {put('QueuedCount', '0')} {put('LastTime', '0.0')}
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not {present('InputSnapshot')}) {fail('invalid_plan')})
    (if (not (and {sg('SnapshotValid', 'InputSnapshot')} {sg('CaptureDone', 'InputSnapshot')})) {fail('invalid_plan')})
    (if (not {present('InputBridge')}) {fail('unavailable_bridge')})
    (if (not (Class|BPActionBridge|GetBridgeReady :self InputBridge)) {fail('unavailable_bridge')})
    (bind count (Utilities|Array|Length InputFire))
    (if (> count 20000) {fail('invalid_plan')})
    (if (or (!= count (Utilities|Array|Length InputBuildings))
      (or (!= count (Utilities|Array|Length InputSlots)) (!= count (Utilities|Array|Length InputWorkers)))) {fail('invalid_plan')})
    (for i (range count)
      (if (not (Utilities|Array|IsValidIndex {sg('Buildings', 'InputSnapshot')} {at('InputBuildings', 'i')})) {fail('invalid_plan')})
      (if (not (Utilities|Array|IsValidIndex {sg('Workers', 'InputSnapshot')} {at('InputWorkers', 'i')})) {fail('invalid_plan')})
      {unpack('WorkerAssignment', at(sg('Workforces', 'InputSnapshot'), at('InputBuildings', 'i')), 'wf')}
      (if (not (Utilities|Array|IsValidIndex wf_m_workerSlots {at('InputSlots', 'i')})) {fail('invalid_plan')}))
    {put('Snapshot', 'InputSnapshot')} {put('Bridge', 'InputBridge')}
    {put('ActionBuildings', 'InputBuildings')} {put('ActionSlots', 'InputSlots')}
    {put('ActionWorkers', 'InputWorkers')} {put('ActionFire', 'InputFire')}
    (if (== count 0) {put('Done', 'true')} {put('Succeeded', 'true')} (return true))
    {put('Active', 'true')} (return true))"""
code["CurrentActionValid"] = f"""(fn CurrentActionValid ()
    (if (not {present(get('Snapshot'))}) (return false))
    (if (not (and {sg('SnapshotValid')} {sg('CaptureDone')})) (return false))
    (if (not (Utilities|Array|IsValidIndex {get('ActionFire')} {get('ActionIndex')})) (return false))
    (if (not (Utilities|Array|IsValidIndex {sg('Buildings')} {action('Buildings')})) (return false))
    (if (not (Utilities|Array|IsValidIndex {sg('Workers')} {action('Workers')})) (return false))
    {unpack('WorkerAssignment', at(sg('Workforces'), action('Buildings')), 'wf')}
    (return (Utilities|Array|IsValidIndex wf_m_workerSlots {action('Slots')})))"""
code["PendingStateSafe"] = f"""(fn PendingStateSafe (ReportedWorkplace)
    (if (not (CallFunction|CurrentActionValid)) (return false))
    (bind building {at(sg('Buildings'), action('Buildings'))})
    (bind worker {at(sg('Workers'), action('Workers'))})
    (bind identityOK (Class|BPWorkforceSnapshot|WorkerIdentityUnchanged :self {get('Snapshot')} :Index {action('Workers')}))
    (if (not identityOK) (return false))
    (bind (known workforce) (Class|BPWorkplaceAdapter|ReadWorkplace :self {get('Snapshot')} :Building building))
    (if (not known) (return false))
    {unpack('WorkerAssignment', 'workforce', 'live')}
    (if (not (Utilities|Array|IsValidIndex live_m_workerSlots {action('Slots')})) (return false))
    {unpack('WorkerSlot', at('live_m_workerSlots', action('Slots')), 'liveSlot')}
    {unpack('WorkerAssignment', at(sg('Workforces'), action('Buildings')), 'old')}
    {unpack('WorkerSlot', at('old_m_workerSlots', action('Slots')), 'oldSlot')}
    (bind structureOK (Class|BPWorkforceSnapshot|BuildingMatchesExpected :self {get('Snapshot')} :Index {action('Buildings')} :ChangedSlot {action('Slots')} :ExpectedOccupant liveSlot_Agent))
    (if (not structureOK) (return false))
    (if {action('Fire')}
      (if (and {present('liveSlot_Agent')} (!= liveSlot_Agent oldSlot_Agent)) (return false))
      (if (and {present('ReportedWorkplace')} (!= ReportedWorkplace building)) (return false))
      (else
        (if (and (!= liveSlot_Agent oldSlot_Agent) (!= liveSlot_Agent worker)) (return false))
        (if (and {present('ReportedWorkplace')} (!= ReportedWorkplace building)) (return false))))
    (return true))"""
code["RecordDispatch"] = f"""(fn RecordDispatch (Accepted Now)
    (if (or (not {get('Active')}) {get('Waiting')}) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
    (if (not Accepted) {fail('action_rejected')})
    {put('Waiting', 'true')} {put('Deadline', '(+ Now 10.0)')}
    {put('QueuedCount', f'(+ {get("QueuedCount")} 1)')} (return true))"""
code["ObserveAction"] = f"""(fn ObserveAction (ReportedWorkplace Now)
    (if (not {get('Waiting')}) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not (CallFunction|PendingStateSafe :ReportedWorkplace ReportedWorkplace))
      (if {get('Active')} (CallFunction|FailApplication :Reason "world_changed")) (return false))
    (bind confirmed (Class|BPWorkforceSnapshot|ConfirmAction :self {get('Snapshot')}
      :BuildingIndex {action('Buildings')} :SlotIndex {action('Slots')} :WorkerIndex {action('Workers')}
      :Fire {action('Fire')} :ReportedWorkplace ReportedWorkplace))
    (if confirmed
      {put('Waiting', 'false')} {put('AppliedCount', f'(+ {get("AppliedCount")} 1)')}
      {put('ActionIndex', f'(+ {get("ActionIndex")} 1)')}
      (if (and {get('Active')} (>= {get('ActionIndex')} (Utilities|Array|Length {get('ActionFire')})))
        {put('Done', 'true')} {put('Succeeded', 'true')} {put('Active', 'false')})
      (return true))
    (if (and {get('Active')} (>= Now {get('Deadline')})) (CallFunction|FailApplication :Reason "action_timeout"))
    (return false))"""
code["AdvanceApplication"] = f"""(fn AdvanceApplication (Now)
    (if {get('Waiting')}
      (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
      (bind worker {at(sg('Workers'), action('Workers'))})
      (if (not {present('worker')}) {fail('world_changed')})
      (bind workplace (Class|PrototypeAgent|GetWorkplace :self worker))
      (bind observed (CallFunction|ObserveAction :ReportedWorkplace workplace :Now Now))
      (return observed))
    (if (not {get('Active')}) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
    (if (not {present(get('Bridge'))}) {fail('unavailable_bridge')})
    (bind accepted (Class|BPActionBridge|QueueAction :self {get('Bridge')} :Snapshot {get('Snapshot')}
      :BuildingIndex {action('Buildings')} :SlotIndex {action('Slots')} :WorkerIndex {action('Workers')} :Fire {action('Fire')}))
    (bind recorded (CallFunction|RecordDispatch :Accepted accepted :Now Now))
    (return recorded))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_RUNNER_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ApplicationRunner.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_APPLICATION_RUNNER_GENERATED")
exec(Path(__file__).with_name("test_application_runner.py").read_text(encoding="utf-8"))
