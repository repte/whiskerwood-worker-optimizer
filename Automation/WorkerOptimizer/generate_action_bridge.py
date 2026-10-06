"""Generate a guarded native action transport, without runtime helper classes.

The transport enforces live slot-lock and school eligibility before dispatch.
This asset alone is not a complete assignment application workflow.
"""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
snapshot_cls = unreal.load_class(None, ROOT + "/BP_WorkforceSnapshot.BP_WorkforceSnapshot_C")
assert snapshot_cls
bp = unreal.load_asset(ROOT + "/BP_ActionBridge")
if bp is None:
    bp = BP.create(ROOT, "BP_ActionBridge", native("SelectTool"))
view = unreal.load_asset(ROOT + "/WBP_ActionContext") if unreal.EditorAssetLibrary.does_asset_exist(ROOT + "/WBP_ActionContext") else None
if view is None:
    view = unreal.get_default_object(unreal.UMGToolSet).call_method(
        "CreateWidgetBlueprint", args=(ROOT, "WBP_ActionContext", native("ArcoView")))
assert view
existing = set(BP.list_variables(bp))
for name, kind in (("QueuedActions", "int"), ("BridgeReady", "bool")):
    if name not in existing:
        BP.add_variable(bp, name, kind)
if "RejectionGuard" not in existing:
    BP.add_variable(bp, "RejectionGuard", "name")
if "ActionContext" not in existing:
    BP.add_object_variable(bp, "ActionContext", native("ArcoView"))

params = [("Snapshot", snapshot_cls), ("BuildingIndex", "int"), ("SlotIndex", "int"), ("WorkerIndex", "int"), ("Fire", "bool")]
definitions = {
    "InitializeBridge": [("Widget", native("ArcoView"))],
    "ValidateAction": params + [("ReportedWorkplace", native("GridActor"))],
    "QueueAction": params,
    "RejectAction": [("Guard", "name")],
}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
graphs = {}
for name, arguments in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in arguments:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
name = "RequiredCrewPresent"
graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
if name not in existing_graphs:
    BP.add_struct_function_param(graphs[name], "Workforce", unreal.load_object(None, "/Script/ProjectArco.WorkerAssignment"), True)
    BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["QueueAction"]
nodes = BP.find_node_types(context, "", [])


def node(suffix):
    found = [n for n in nodes if n.endswith(suffix)]
    assert len(found) == 1, (suffix, found)
    return found[0]


def g(name):
    return f"(Variables|Default|Get{name})"


def sg(name):
    return f"(Class|BPWorkforceSnapshot|Get{name} :self Snapshot)"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def unpack(struct, value, prefix):
    ident = "Utilities|Struct|Break" + struct
    pins = BP.get_node_type_pins(context, ident).output_pins
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in pins)}) ({ident} {value}))"


valid = "Utilities|IsValid"
get_detail = node("|GetMActiveDetailWidget")
set_detail = node("|SetMActiveDetailWidget")
set_context = "Class|ArcoWidgetBase|SetContext"
validate_call = "CallFunction|ValidateAction :Snapshot Snapshot :BuildingIndex BuildingIndex :SlotIndex SlotIndex :WorkerIndex WorkerIndex :Fire Fire"
code = {}
def reject(guard):
    return f'(CallFunction|RejectAction :Guard "bridge.{guard}") (return false)'

code["RejectAction"] = f'''(fn RejectAction (Guard)
    (if (== {g('RejectionGuard')} "None") (Variables|Default|SetRejectionGuard Guard))
    (return false))'''
code["RequiredCrewPresent"] = f"""(fn RequiredCrewPresent (Workforce)
    {unpack('WorkerAssignment', 'Workforce', 'wf')}
    (for workerSlot wf_m_workerSlots
      {unpack('WorkerSlot', 'workerSlot', 's')}
      (if s_bIsRequiredToRun
        ({valid} s_Agent (:"Is Not Valid" (return false)))))
    (return true))"""
code["InitializeBridge"] = f"""(fn InitializeBridge (Widget)
    (Variables|Default|SetBridgeReady false)
    (Actor|Tick|SetActorTickEnabled :self self :bEnabled false)
    ({valid} Widget
      (:"Is Valid"
        (Variables|Default|SetActionContext Widget)
        ({set_detail} :m_activeDetailWidget Widget)
        (Variables|Default|SetQueuedActions 0)
        (Variables|Default|SetBridgeReady true)
        (return true))
      (:"Is Not Valid" (return false))))"""
code["ValidateAction"] = f"""(fn ValidateAction (Snapshot BuildingIndex SlotIndex WorkerIndex Fire ReportedWorkplace)
    (Variables|Default|SetRejectionGuard "None")
    ({valid} Snapshot
      (:"Is Not Valid" {reject('snapshot_unavailable')})
      (:"Is Valid"
        (if (not (and {sg('SnapshotValid')} {sg('CaptureDone')})) {reject('snapshot_incomplete')})
        (if (not (Utilities|Array|IsValidIndex {sg('Buildings')} BuildingIndex)) {reject('building_index')})
        (if (not (Utilities|Array|IsValidIndex {sg('Workers')} WorkerIndex)) {reject('worker_index')})
        (bind building {at(sg('Buildings'), 'BuildingIndex')})
        (bind worker {at(sg('Workers'), 'WorkerIndex')})
        (bind buildingOK (Class|BPWorkforceSnapshot|BuildingUnchanged :self Snapshot :Index BuildingIndex))
        (if (not buildingOK) {reject('building_changed')})
        (bind workerOK (Class|BPWorkforceSnapshot|WorkerUnchanged :self Snapshot :Index WorkerIndex :ReportedWorkplace ReportedWorkplace))
        (if (not workerOK) {reject('worker_changed')})
        (bind (known workforce) (Class|BPWorkplaceAdapter|ReadWorkplace :self Snapshot :Building building))
        (if (not known) {reject('workplace_unavailable')})
        {unpack('WorkerAssignment', 'workforce', 'wf')}
        (if wf_bDisabled {reject('disabled')})
        (if (not (Utilities|Array|IsValidIndex wf_m_workerSlots SlotIndex)) {reject('slot_index')})
        {unpack('WorkerSlot', at('wf_m_workerSlots', 'SlotIndex'), 'slot')}
        {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self worker)', 'ch')}
        (if (< ch_ID 0) {reject('worker_id')})
        (if Fire
          (if (not (and (== ReportedWorkplace building) (== slot_Agent worker))) {reject('fire_occupancy')})
          (return true)
          (else
            (bind roleEligible (Class|BPJobEligibility|LiveCanFillSlot :self Snapshot :Worker worker :Building building :SlotIndex SlotIndex))
            (if (not roleEligible) {reject('hire_role_eligibility')})
            (if (not slot_bIsRequiredToRun)
              (bind crewPresent (CallFunction|RequiredCrewPresent :Workforce workforce))
              (if (not crewPresent) {reject('optional_before_required')}))
            ({valid} ReportedWorkplace (:"Is Valid" {reject('worker_not_free')})
              (:"Is Not Valid"
                ({valid} slot_Agent (:"Is Valid" {reject('slot_occupied')}) (:"Is Not Valid" (return true))))))))))"""
code["QueueAction"] = f"""(fn QueueAction (Snapshot BuildingIndex SlotIndex WorkerIndex Fire)
    (Variables|Default|SetRejectionGuard "None")
    (if (not {g('BridgeReady')}) {reject('not_ready')})
    ({valid} {g('ActionContext')} (:"Is Not Valid" {reject('context_unavailable')})
      (:"Is Valid"
        (if (!= ({get_detail}) {g('ActionContext')}) {reject('context_changed')})
        ({valid} Snapshot (:"Is Not Valid" {reject('snapshot_unavailable')})
          (:"Is Valid"
            (if (not (Utilities|Array|IsValidIndex {sg('Workers')} WorkerIndex)) {reject('worker_index')})
            (bind worker {at(sg('Workers'), 'WorkerIndex')})
            ({valid} worker (:"Is Not Valid" {reject('worker_unavailable')})
              (:"Is Valid"
                (bind workplace (Class|PrototypeAgent|GetWorkplace :self worker))
                (bind allowed ({validate_call} :ReportedWorkplace workplace))
                (if (not allowed) (return false))
                (bind building {at(sg('Buildings'), 'BuildingIndex')})
                (bind (definition definitionFound) (Class|GridActor|GetGridActorDefinition :self building))
                (if (not definitionFound) {reject('definition_unavailable')})
                {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self worker)', 'ch')}
                ({set_context} :self {g('ActionContext')} :Context building)
                (if Fire
                  (WorkerOptimizerNativeBridge|ReceiveHudAction :self self :HudAction
                    (Utilities|Struct|MakeHudAction :action "fireSpecificWorker" :paramInt ch_ID))
                  (else
                    (WorkerOptimizerNativeBridge|ReceiveHudAction :self self :HudAction
                      (Utilities|Struct|MakeHudAction :action "hireWorkerForSlot" :paramInt ch_ID :paramFloat SlotIndex))))
                (Variables|Default|SetQueuedActions (+ {g('QueuedActions')} 1))
                (return true))))))))"""
for name, source in code.items():
    unreal.log("WO_ACTION_BRIDGE_PARSE " + name)
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_ACTION_BRIDGE_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    BP.compile_blueprint(view, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    tick = cdo.get_editor_property("primary_actor_tick")
    tick.set_editor_property("start_with_tick_enabled", False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    cdo.set_editor_property("primary_actor_tick", tick, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    cdo.set_editor_property("hidden", True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    unreal.log("WO_BRIDGE_CDO_TICK " + str(cdo.get_editor_property("primary_actor_tick").get_editor_property("start_with_tick_enabled")))
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    assert unreal.EditorAssetLibrary.save_loaded_asset(view)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-ActionBridge.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_ACTION_BRIDGE_GENERATED: native references and structural safety gates; controller eligibility and in-game validation still required")
exec(Path(__file__).with_name("test_action_bridge.py").read_text(encoding="utf-8"))
