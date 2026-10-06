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
building_cls = unreal.load_class(None, "/Script/ProjectArco.GridActor")
worker_cls = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
for name, cls in (("Snapshot", load("BP_WorkforceSnapshot")), ("Bridge", load("BP_ActionBridge")),
                  ("PendingBuilding", building_cls), ("PendingWorker", worker_cls)):
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "Active Done Succeeded Waiting ValidationActive PendingReceiptReady PendingFire",
    "int": "ActionIndex AppliedCount QueuedCount ValidationIndex StepWorkLimit LastStepWork ConfirmedFires ConfirmedHires PendingWorkerID PendingSlot",
    "float": "LastTime Deadline",
    "name": "FailureCode",
    "int[]": "ActionBuildings ActionSlots ActionWorkers",
    "bool[]": "ActionFire",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
BP.set_variable_instance_editable(bp, "StepWorkLimit", True)

definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "IsEmptyObject": [("Object", unreal.Object.static_class()), ("Empty", unreal.Object.static_class())],
    "FailApplication": [("Reason", "name")],
    "ValidClock": [("Now", "float")],
    "StartApplication": [("InputSnapshot", load("BP_WorkforceSnapshot")), ("InputBridge", load("BP_ActionBridge")),
        ("InputBuildings", "int[]"), ("InputSlots", "int[]"), ("InputWorkers", "int[]"), ("InputFire", "bool[]"), ("Now", "float")],
    "CurrentActionValid": [],
    "ValidateQueue": [],
    "PendingStateSafe": [("ReportedWorkplace", building_cls)],
    "CapturePendingReceipt": [],
    "PendingEffectObserved": [("ReportedWorkplace", building_cls)],
    "SettleDriftReceipt": [("ReportedWorkplace", building_cls)],
    "RecordDispatch": [("Accepted", "bool"), ("Now", "float")],
    "ObserveAction": [("ReportedWorkplace", building_cls), ("Now", "float")],
    "AdvanceApplication": [("Now", "float")],
    "ResetConfirmedActions": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name in existing_graphs:
        result_kept = False
        for node in BP.find_nodes(graphs[name]):
            kind = node.get_class().get_name()
            if kind == "K2Node_FunctionEntry":
                continue
            if kind == "K2Node_FunctionResult" and not result_kept:
                result_kept = True
                for pin in BP.get_node_infos([node])[0].input_pins:
                    for connected in pin.connected_pins:
                        BP.break_pins(connected, pin.pin_id)
                continue
            BP.delete_node(node)
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
# Empty is deliberately omitted by callers, leaving its object pin at native null.
code["IsEmptyObject"] = """(fn IsEmptyObject (Object Empty) (return (== Object Empty)))"""
code["FailApplication"] = f"""(fn FailApplication (Reason)
    {put('Active', 'false')} {put('Done', 'true')} {put('Succeeded', 'false')}
    {put('ValidationActive', 'false')} {put('Waiting', 'false')} {put('PendingReceiptReady', 'false')}
    {put('FailureCode', 'Reason')} (return false))"""
code["ValidClock"] = f"""(fn ValidClock (Now)
    (if (not (and (>= Now 0.0) (<= Now 1000000000.0))) (return false))
    (if (< Now {get('LastTime')}) (return false))
    {put('LastTime', 'Now')} (return true))"""
code["ResetConfirmedActions"] = f"""(fn ResetConfirmedActions ()
    (if (or {get('Active')} {get('Waiting')}) (return false))
    {put('AppliedCount', '0')} {put('QueuedCount', '0')} {put('ConfirmedFires', '0')} {put('ConfirmedHires', '0')} (return true))"""
code["StartApplication"] = f"""(fn StartApplication (InputSnapshot InputBridge InputBuildings InputSlots InputWorkers InputFire Now)
    (if (or {get('Active')} {get('Waiting')}) (return false))
    (CallFunction|ResetConfirmedActions)
    {put('Done', 'false')} {put('Succeeded', 'false')} {put('FailureCode', '"None"')}
    {put('ActionIndex', '0')} {put('AppliedCount', '0')} {put('QueuedCount', '0')} {put('LastTime', '0.0')}
    {put('ValidationIndex', '0')} {put('ValidationActive', 'false')} {put('LastStepWork', '0')}
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not {present('InputSnapshot')}) {fail('invalid_plan')})
    (if (not (and {sg('SnapshotValid', 'InputSnapshot')} {sg('CaptureDone', 'InputSnapshot')})) {fail('invalid_plan')})
    (if (not {present('InputBridge')}) {fail('unavailable_bridge')})
    (if (not (Class|BPActionBridge|GetBridgeReady :self InputBridge)) {fail('unavailable_bridge')})
    (bind count (Utilities|Array|Length InputFire))
    (if (> count 20000) {fail('invalid_plan')})
    (if (or (!= count (Utilities|Array|Length InputBuildings))
      (or (!= count (Utilities|Array|Length InputSlots)) (!= count (Utilities|Array|Length InputWorkers)))) {fail('invalid_plan')})
    {put('Snapshot', 'InputSnapshot')} {put('Bridge', 'InputBridge')}
    {put('ActionBuildings', 'InputBuildings')} {put('ActionSlots', 'InputSlots')}
    {put('ActionWorkers', 'InputWorkers')} {put('ActionFire', 'InputFire')}
    (if (== count 0) {put('Done', 'true')} {put('Succeeded', 'true')} (return true))
    {put('Active', 'true')} {put('ValidationActive', 'true')} (return true))"""
code["ValidateQueue"] = f"""(fn ValidateQueue ()
    {put('LastStepWork', '0')}
    (if (not (and {get('Active')} {get('ValidationActive')})) (return false))
    (if (<= {get('StepWorkLimit')} 0) {fail('invalid_plan')})
    (for work (range {get('StepWorkLimit')})
      (bind i {get('ValidationIndex')})
      (if (>= i (Utilities|Array|Length {get('ActionFire')}))
        {put('ValidationActive', 'false')} (return true))
      {put('LastStepWork', f'(+ {get("LastStepWork")} 1)')}
      (if (not (Utilities|Array|IsValidIndex {sg('Buildings')} {at(get('ActionBuildings'), 'i')})) {fail('invalid_plan')})
      (if (not (Utilities|Array|IsValidIndex {sg('Workers')} {at(get('ActionWorkers'), 'i')})) {fail('invalid_plan')})
      {unpack('WorkerAssignment', at(sg('Workforces'), at(get('ActionBuildings'), 'i')), 'wf')}
      (if (not (Utilities|Array|IsValidIndex wf_m_workerSlots {at(get('ActionSlots'), 'i')})) {fail('invalid_plan')})
      {put('ValidationIndex', f'(+ {get("ValidationIndex")} 1)')})
    (if (>= {get('ValidationIndex')} (Utilities|Array|Length {get('ActionFire')})) {put('ValidationActive', 'false')})
    (return true))"""
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
code["CapturePendingReceipt"] = f"""(fn CapturePendingReceipt ()
    {put('PendingReceiptReady', 'false')}
    (if (not (CallFunction|CurrentActionValid)) (return false))
    (if (not (Utilities|Array|IsValidIndex {sg('Characteristics')} {action('Workers')})) (return false))
    (if (not (Utilities|Array|IsValidIndex {sg('WorkerWorkplaces')} {action('Workers')})) (return false))
    (bind building {at(sg('Buildings'), action('Buildings'))})
    (bind worker {at(sg('Workers'), action('Workers'))})
    (if (not (and {present('building')} {present('worker')})) (return false))
    {unpack('WorkerAssignment', at(sg('Workforces'), action('Buildings')), 'old')}
    {unpack('WorkerSlot', at('old_m_workerSlots', action('Slots')), 'oldSlot')}
    (if {action('Fire')}
      (if (!= oldSlot_Agent worker) (return false))
      (if (!= {at(sg('WorkerWorkplaces'), action('Workers'))} building) (return false))
      (else
        (if (not (CallFunction|IsEmptyObject :Object oldSlot_Agent)) (return false))
        (if (not (CallFunction|IsEmptyObject :Object {at(sg('WorkerWorkplaces'), action('Workers'))})) (return false))))
    {unpack('AgentCharacteristics', at(sg('Characteristics'), action('Workers')), 'oldWorker')}
    {put('PendingBuilding', 'building')} {put('PendingWorker', 'worker')}
    {put('PendingWorkerID', 'oldWorker_ID')} {put('PendingSlot', action('Slots'))} {put('PendingFire', action('Fire'))}
    {put('PendingReceiptReady', 'true')} (return true))"""
# This receipt only acknowledges an issued action; it never validates a new dispatch or updates the snapshot.
code["PendingEffectObserved"] = f"""(fn PendingEffectObserved (ReportedWorkplace)
    (if (not (and {get('Waiting')} {get('PendingReceiptReady')})) (return false))
    (if (not (CallFunction|CurrentActionValid)) (return false))
    (if (not (and {present(get('PendingBuilding'))} {present(get('PendingWorker'))})) (return false))
    (if (or (!= {at(sg('Buildings'), action('Buildings'))} {get('PendingBuilding')})
      (!= {at(sg('Workers'), action('Workers'))} {get('PendingWorker')})) (return false))
    (if (or (!= {action('Slots')} {get('PendingSlot')}) (!= {action('Fire')} {get('PendingFire')})) (return false))
    {unpack('AgentCharacteristics', f'(Class|PrototypeAgent|GetMCharacteristics :self {get("PendingWorker")})', 'liveWorker')}
    (if (!= liveWorker_ID {get('PendingWorkerID')}) (return false))
    (bind (known workforce) (Class|BPWorkplaceAdapter|ReadWorkplace :self {get('Snapshot')} :Building {get('PendingBuilding')}))
    (if (not known) (return false))
    {unpack('WorkerAssignment', 'workforce', 'live')}
    (if (not (Utilities|Array|IsValidIndex live_m_workerSlots {get('PendingSlot')})) (return false))
    {unpack('WorkerSlot', at('live_m_workerSlots', get('PendingSlot')), 'liveSlot')}
    (if {get('PendingFire')}
      (bind slotEmpty (CallFunction|IsEmptyObject :Object liveSlot_Agent))
      (bind placeEmpty (CallFunction|IsEmptyObject :Object ReportedWorkplace))
      (return (and slotEmpty placeEmpty))
      (else (return (and (== liveSlot_Agent {get('PendingWorker')}) (== ReportedWorkplace {get('PendingBuilding')}))))))"""
code["SettleDriftReceipt"] = f"""(fn SettleDriftReceipt (ReportedWorkplace)
    (bind receipt (CallFunction|PendingEffectObserved :ReportedWorkplace ReportedWorkplace))
    (if (not receipt) (return false))
    (if {get('Active')} (CallFunction|FailApplication :Reason "world_changed"))
    {put('Waiting', 'false')} {put('PendingReceiptReady', 'false')} {put('AppliedCount', f'(+ {get("AppliedCount")} 1)')}
    (if {get('PendingFire')} {put('ConfirmedFires', f'(+ {get("ConfirmedFires")} 1)')}
      (else {put('ConfirmedHires', f'(+ {get("ConfirmedHires")} 1)')}))
    {put('ActionIndex', f'(+ {get("ActionIndex")} 1)')} (return true))"""
code["RecordDispatch"] = f"""(fn RecordDispatch (Accepted Now)
    (if (or {get('ValidationActive')} (or (not {get('Active')}) {get('Waiting')})) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
    (if (not Accepted) {fail('action_rejected')})
    {put('Waiting', 'true')} {put('Deadline', '(+ Now 10.0)')}
    {put('QueuedCount', f'(+ {get("QueuedCount")} 1)')}
    (bind captured (CallFunction|CapturePendingReceipt))
    (if (not captured) {fail('world_changed')}) (return true))"""
code["ObserveAction"] = f"""(fn ObserveAction (ReportedWorkplace Now)
    (if (not {get('Waiting')}) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if (not (CallFunction|PendingStateSafe :ReportedWorkplace ReportedWorkplace))
      (bind settled (CallFunction|SettleDriftReceipt :ReportedWorkplace ReportedWorkplace))
      (if (not settled) (CallFunction|FailApplication :Reason "world_changed")) (return settled))
    (bind confirmed (Class|BPWorkforceSnapshot|ConfirmAction :self {get('Snapshot')}
      :BuildingIndex {action('Buildings')} :SlotIndex {action('Slots')} :WorkerIndex {action('Workers')}
      :Fire {action('Fire')} :ReportedWorkplace ReportedWorkplace))
    (if confirmed
      {put('Waiting', 'false')} {put('PendingReceiptReady', 'false')} {put('AppliedCount', f'(+ {get("AppliedCount")} 1)')}
      (if {action('Fire')} {put('ConfirmedFires', f'(+ {get("ConfirmedFires")} 1)')}
        (else {put('ConfirmedHires', f'(+ {get("ConfirmedHires")} 1)')}))
      {put('ActionIndex', f'(+ {get("ActionIndex")} 1)')}
      (if (and {get('Active')} (>= {get('ActionIndex')} (Utilities|Array|Length {get('ActionFire')})))
        {put('Done', 'true')} {put('Succeeded', 'true')} {put('Active', 'false')})
      (return true))
    (bind settled (CallFunction|SettleDriftReceipt :ReportedWorkplace ReportedWorkplace))
    (if settled (return true))
    (if (and {get('Active')} (>= Now {get('Deadline')})) (CallFunction|FailApplication :Reason "action_timeout"))
    (return false))"""
code["AdvanceApplication"] = f"""(fn AdvanceApplication (Now)
    {put('LastStepWork', '0')}
    (if {get('Waiting')}
      (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
      (bind worker {at(sg('Workers'), action('Workers'))})
      (if (not {present('worker')}) {fail('world_changed')})
      (bind workplace (Class|PrototypeAgent|GetWorkplace :self worker))
      (bind observed (CallFunction|ObserveAction :ReportedWorkplace workplace :Now Now))
      (return observed))
    (if (not {get('Active')}) (return false))
    (if (not (CallFunction|ValidClock :Now Now)) {fail('invalid_clock')})
    (if {get('ValidationActive')} (bind validated (CallFunction|ValidateQueue)) (return validated))
    (if (not (CallFunction|CurrentActionValid)) {fail('world_changed')})
    (if (not {present(get('Bridge'))}) {fail('unavailable_bridge')})
    (bind accepted (Class|BPActionBridge|QueueAction :self {get('Bridge')} :Snapshot {get('Snapshot')}
      :BuildingIndex {action('Buildings')} :SlotIndex {action('Slots')} :WorkerIndex {action('Workers')} :Fire {action('Fire')}))
    (bind recorded (CallFunction|RecordDispatch :Accepted accepted :Now Now))
    (if (not recorded) (return false))
    ; Supported native actions update the slot and employer before returning.
    (bind workplace (Class|PrototypeAgent|GetWorkplace :self {at(sg('Workers'), action('Workers'))}))
    (bind observed (CallFunction|ObserveAction :ReportedWorkplace workplace :Now Now))
    (if {get('Waiting')} (CallFunction|FailApplication :Reason "world_changed"))
    (return observed))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_RUNNER_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    unreal.get_default_object(bp.generated_class()).set_editor_property("StepWorkLimit", 64)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ApplicationRunner.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_APPLICATION_RUNNER_GENERATED")
exec(Path(__file__).with_name("test_application_runner.py").read_text(encoding="utf-8"))
