"""Generate the per-world, click-driven optimization/application controller."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_WorkerOptimizer")
if bp is None:
    bp = BP.create(ROOT, "BP_WorkerOptimizer", unreal.Actor.static_class())
refs = {"Snapshot": "BP_WorkforceSnapshot", "Layout": "BP_ProblemLayout", "Matrix": "BP_ScoreMatrix",
        "Planner": "BP_StaffingPlanner", "Search": "BP_PlanSearch", "Scorer": "BP_JobScorer",
        "Settings": "BP_PrioritySettings", "ActionPlan": "BP_ActionPlan", "Runner": "BP_ApplicationRunner",
        "Bridge": "BP_ActionBridge"}
existing = set(BP.list_variables(bp))
for name, cls in list((name, load(cls)) for name, cls in refs.items()) + [("Context", unreal.Object.static_class())]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "Initialized RunActive RunDone RunSucceeded",
    "int": "Phase DecodeIndex AppliedCount QueuedCount RequestedReserve ReserveIndex",
    "float[]": "BuilderQuality",
    "name": "FailureCode",
    "float": "PumpStart PumpNow",
    "int[]": "FinalWorkers",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "Initialize": [("InputContext", unreal.Object.static_class()), ("InputBridge", load("BP_ActionBridge"))],
    "FailRun": [("Reason", "name")], "CompleteRun": [], "BeginRun": [],
    "AcceptConfig": [("Loaded", "bool")], "DecodeAssignment": [], "SyncApplication": [],
    "AdvanceRun": [("Now", "float")], "CancelRun": [], "Shutdown": [], "ReadClock": [], "Pump": [],
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
        BP.add_function_param(graphs[name], "Now" if name == "ReadClock" else "Result", "float" if name == "ReadClock" else "bool", False)
BP.compile_blueprint(bp)


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def prop(ref, name, source=None):
    return f"(Class|{refs[ref].replace('_', '')}|Get{name} :self {source or g(ref)})"


def invoke(ref, name, args=""):
    return f"(Class|{refs[ref].replace('_', '')}|{name} :self {g(ref)} {args})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def count(array):
    return f"(Utilities|Array|Length {array})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def fail(reason):
    return f'(CallFunction|FailRun :Reason "{reason}") (return false)'


def fail_from(ref):
    return f"(CallFunction|FailRun :Reason {prop(ref, 'FailureCode')}) (return false)"


creations = []
for name, asset in refs.items():
    if name == "Bridge":
        continue
    creations.append(f"""(bind new{name} (Game|ConstructObjectfromClass :Class "{ROOT}/{asset}.{asset}_C" :self self))
      {put(name, 'new' + name)}
      (if (not {present(g(name))}) (return false))""")
code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["Initialize"] = f"""(fn Initialize (InputContext InputBridge)
    (if {g('Initialized')} (return (and (== InputContext {g('Context')}) (== InputBridge {g('Bridge')}))))
    (if (not {present('InputContext')}) (return false))
    (if (not {present('InputBridge')}) (return false))
    (if (not {prop('Bridge', 'BridgeReady', 'InputBridge')}) (return false))
    {put('Context', 'InputContext')} {put('Bridge', 'InputBridge')}
    {' '.join(creations)}
    {put('Initialized', 'true')} (return true))"""
code["FailRun"] = f"""(fn FailRun (Reason)
    (bind api (Class|ModAPI|GetModAPI))
    (if {present('api')}
      (Class|ModAPI|LogMessage :self api :Msg (Utilities|String|Append :A "WorkerOptimizer stopped: " :B (Utilities|String|ToString(Name) Reason)) :doPrependDate true))
    {put('RunActive', 'false')} {put('RunDone', 'true')} {put('RunSucceeded', 'false')}
    {put('FailureCode', 'Reason')} (Utilities|Array|Clear {g('FinalWorkers')}) (return false))"""
code["CompleteRun"] = f"""(fn CompleteRun ()
    {put('RunActive', 'false')} {put('RunDone', 'true')} {put('RunSucceeded', 'true')}
    {put('FailureCode', '"None"')} {put('Phase', '7')} (return true))"""
code["BeginRun"] = f"""(fn BeginRun ()
    (if (or (not {g('Initialized')}) {g('RunActive')}) (return false))
    (if (not {present(g('Context'))}) (return false))
    (if (not {present(g('Bridge'))}) (return false))
    (if (not {prop('Bridge', 'BridgeReady')}) (return false))
    (if (or {prop('Runner', 'Active')} {prop('Runner', 'Waiting')}) (return false))
    {put('RunActive', 'true')} {put('RunDone', 'false')} {put('RunSucceeded', 'false')}
    {put('FailureCode', '"None"')} {put('Phase', '0')} {put('AppliedCount', '0')} {put('QueuedCount', '0')}
    {put('ReserveIndex', '0')} (Utilities|Array|Clear {g('BuilderQuality')})
    (Utilities|Array|Clear {g('FinalWorkers')}) (return true))"""
code["AcceptConfig"] = f"""(fn AcceptConfig (Loaded)
    (if (or (not {g('RunActive')}) (!= {g('Phase')} 0)) (return false))
    (if (not Loaded) {fail('configuration_unavailable')})
    (if (not {prop('Scorer', 'Ready')}) {fail('configuration_unavailable')})
    (bind reserve {invoke('Settings', 'ReadReserve', f':Context {g("Context")}')})
    {put('RequestedReserve', 'reserve')}
    {invoke('Snapshot', 'BeginCapture', f':WorldContext {g("Context")}')}
    {put('Phase', '1')} (return true))"""
code["DecodeAssignment"] = f"""(fn DecodeAssignment ()
    (if (!= {count(prop('Search', 'BestAssignment'))} {count(prop('Layout', 'RowBuildings'))}) {fail('invalid_plan')})
    (if (>= {g('DecodeIndex')} {count(prop('Search', 'BestAssignment'))})
      (bind started {invoke('ActionPlan', 'BeginBuild', f':InputSnapshot {g("Snapshot")} :InputWorkers {g("FinalWorkers")}')})
      (if (not started) {fail_from('ActionPlan')})
      {put('Phase', '5')} (return true))
    (bind column {at(prop('Search', 'BestAssignment'), g('DecodeIndex'))})
    (if (or (< column -1) (>= column {count(prop('Layout', 'ColumnWorkers'))})) {fail('invalid_plan')})
    (if (< column 0) (Utilities|Array|Add {g('FinalWorkers')} -1)
      (else (Utilities|Array|Add {g('FinalWorkers')} {at(prop('Layout', 'ColumnWorkers'), 'column')})))
    {put('DecodeIndex', f'(+ {g("DecodeIndex")} 1)')} (return true))"""
code["SyncApplication"] = f"""(fn SyncApplication ()
    (if (!= {g('Phase')} 6) (return false))
    {put('AppliedCount', prop('Runner', 'AppliedCount'))} {put('QueuedCount', prop('Runner', 'QueuedCount'))}
    (if {prop('Runner', 'Done')}
      (if {prop('Runner', 'Succeeded')} (CallFunction|CompleteRun) (return true))
      {fail_from('Runner')}) (return true))"""
code["AdvanceRun"] = f"""(fn AdvanceRun (Now)
    (if (not {g('Initialized')}) (return false))
    (if (not {g('RunActive')})
      (if (== {g('Phase')} 6)
        (if {prop('Runner', 'Waiting')} {invoke('Runner', 'AdvanceApplication', ':Now Now')})
        (CallFunction|SyncApplication)) (return false))
    (switch int {g('Phase')}
      (:0
        (bind loaded {invoke('Scorer', 'LoadConfig', f':Context {g("Context")}')})
        (bind accepted (CallFunction|AcceptConfig :Loaded loaded)) (return accepted))
      (:1
        (if (not {prop('Snapshot', 'CaptureDone')}) {invoke('Snapshot', 'AdvanceCapture')} (return true))
        (if (not {prop('Snapshot', 'SnapshotValid')}) {fail('invalid_snapshot')})
        (bind layoutStarted {invoke('Layout', 'BeginLayout', f':InputSnapshot {g("Snapshot")}')})
        (if (not layoutStarted) {fail_from('Layout')}) {put('Phase', '2')} (return true))
      (:2
        (if (not {prop('Layout', 'LayoutDone')}) {invoke('Layout', 'AdvanceLayout')} (return true))
        (if (not {prop('Layout', 'LayoutSucceeded')}) {fail_from('Layout')})
        (if (< {g('ReserveIndex')} {count(prop('Layout', 'ColumnActors'))})
          (if (< {g('ReserveIndex')} {count(prop('Snapshot', 'Workers'))})
            (bind (valid score) {invoke('Scorer', 'ScoreBuilder', f':Worker {at(prop("Layout", "ColumnActors"), g("ReserveIndex"))}')})
            (if (not valid) {fail('builder_score_unavailable')})
            (Utilities|Array|Add {g('BuilderQuality')} score)
            (else (Utilities|Array|Add {g('BuilderQuality')} 0.0)))
          {put('ReserveIndex', f'(+ {g("ReserveIndex")} 1)')} (return true))
        (bind searchStarted {invoke('Search', 'BeginSearch', f':InputLayout {g("Layout")} :InputMatrix {g("Matrix")} :InputPlanner {g("Planner")} :InputScorer {g("Scorer")} :InputSettings {g("Settings")} :InputContext {g("Context")}')})
        (if (not searchStarted) {fail_from('Search')})
        (bind reserved {invoke('Search', 'ConfigureReserve', f':Requested {g("RequestedReserve")} :Quality {g("BuilderQuality")}')})
        (if (not reserved) {fail('reserve_configuration_failed')})
        {put('Phase', '3')} (return true))
      (:3
        (if (not {prop('Search', 'SearchDone')}) {invoke('Search', 'AdvanceSearch')} (return true))
        (if (not {prop('Search', 'SearchSucceeded')}) {fail_from('Search')})
        (Utilities|Array|Clear {g('FinalWorkers')}) {put('DecodeIndex', '0')} {put('Phase', '4')} (return true))
      (:4 (bind decoded (CallFunction|DecodeAssignment)) (return decoded))
      (:5
        (if (not {prop('ActionPlan', 'BuildDone')}) {invoke('ActionPlan', 'AdvanceBuild')} (return true))
        (if (not {prop('ActionPlan', 'BuildSucceeded')}) {fail_from('ActionPlan')})
        (bind applicationStarted {invoke('Runner', 'StartApplication', f':InputSnapshot {g("Snapshot")} :InputBridge {g("Bridge")} :InputBuildings {prop("ActionPlan", "ActionBuildings")} :InputSlots {prop("ActionPlan", "ActionSlots")} :InputWorkers {prop("ActionPlan", "ActionWorkers")} :InputFire {prop("ActionPlan", "ActionFire")} :Now Now')})
        (if (not applicationStarted) {fail_from('Runner')}) {put('Phase', '6')} (return true))
      (:6
        {invoke('Runner', 'AdvanceApplication', ':Now Now')}
        (bind synced (CallFunction|SyncApplication)) (return synced))
      (:Default {fail('invalid_phase')})))"""
code["CancelRun"] = f"""(fn CancelRun ()
    (if (not {g('RunActive')}) (return false))
    (if (== {g('Phase')} 6)
      {invoke('Runner', 'FailApplication', ':Reason "cancelled"')}
      {put('AppliedCount', prop('Runner', 'AppliedCount'))} {put('QueuedCount', prop('Runner', 'QueuedCount'))}
      (else
        (if {prop('Search', 'SearchActive')} {invoke('Search', 'CancelSearch')})
        {invoke('Layout', 'FailLayout', ':Reason "cancelled"')}
        {invoke('ActionPlan', 'FailBuild', ':Reason "cancelled"')}
        {invoke('Snapshot', 'ResetSnapshot')}))
    (CallFunction|FailRun :Reason "cancelled") (return true))"""
code["Shutdown"] = f"""(fn Shutdown ()
    (if (not {g('Initialized')}) (return false))
    (if {g('RunActive')} (CallFunction|CancelRun))
    {put('Initialized', 'false')} (Variables|Default|SetContext) (Variables|Default|SetBridge) (return true))"""
code["ReadClock"] = """(fn ReadClock ()
    (bind (seconds fraction) (Utilities|Time|GetAccurateRealTime))
    (return (+ seconds fraction)))"""
code["Pump"] = f"""(fn Pump ()
    (if (not {g('Initialized')}) (return false))
    (if (not (or {g('RunActive')} {prop('Runner', 'Waiting')})) (return false))
    (bind start (CallFunction|ReadClock)) {put('PumpStart', 'start')}
    (for step (range 64)
      (bind now (CallFunction|ReadClock)) {put('PumpNow', 'now')}
      (CallFunction|AdvanceRun :Now {g('PumpNow')})
      (if (or (== {g('Phase')} 6) (not {g('RunActive')})) (break))
      (bind after (CallFunction|ReadClock))
      (if (>= (- after {g('PumpStart')}) 0.002) (break))) (return true))"""
event_source = """(event EventTick (DeltaSeconds) (CallFunction|Pump))
    (event EventEndPlay (EndPlayReason) (CallFunction|Shutdown))"""

for name, source in list(code.items()) + [("EventGraph", event_source)]:
    try:
        blueprint_dsl.parse(source)
    except Exception:
        unreal.log_error("WO_CONTROLLER_PARSE " + name + "\n" + source)
        raise
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_CONTROLLER_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.write_graph_dsl(BP.get_graph(bp, "EventGraph"), event_source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    tick = cdo.get_editor_property("primary_actor_tick")
    tick.set_editor_property("start_with_tick_enabled", True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    cdo.set_editor_property("primary_actor_tick", tick, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    cdo.set_editor_property("hidden", True, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Controller.dsl").write_text("\n\n".join(code.values()) + "\n" + event_source, encoding="utf-8")
unreal.log("WO_CONTROLLER_GENERATED")
exec(Path(__file__).with_name("test_controller.py").read_text(encoding="utf-8"))
