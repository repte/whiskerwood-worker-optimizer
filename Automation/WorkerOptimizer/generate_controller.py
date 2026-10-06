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
        "Bridge": "BP_ActionBridge", "Metrics": "BP_PerformanceMetrics", "PolicyCatalog": "BP_DefinitionCatalog", "AutoAssignment": "BP_AutoAssignment",
        "CurrentReport": "BP_RunReport", "CompletedReport": "BP_RunReport", "Logbook": "BP_Logbook"}
existing = set(BP.list_variables(bp))
for name, cls in list((name, load(cls)) for name, cls in refs.items()) + [("Context", unreal.Object.static_class())]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "Initialized RunActive RunDone RunSucceeded MeasurePerformance ReportPending ReportPublished LateEndPending",
    "int": "Phase DecodeIndex AppliedCount QueuedCount RequestedReserve ReserveIndex PumpStartSeconds StepStartSeconds SamplePhase PolicyKeyIndex CompletedRecordCount ReplanCount PriorAppliedCount PriorQueuedCount PriorFires PriorHires",
    "float[]": "BuilderQuality",
    "name": "FailureCode RunTrigger TerminalOutcome",
    "string": "LastFailureDiagnostic",
    "float": "PumpStart PumpNow PumpStartFraction StepStartFraction",
    "int[]": "FinalWorkers",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
BP.set_variable_instance_editable(bp, "MeasurePerformance", True)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "Initialize": [("InputContext", unreal.Object.static_class()), ("InputBridge", load("BP_ActionBridge"))],
    "FailRun": [("Reason", "name")], "CompleteRun": [], "BeginRun": [],
    "HandleFailure": [("Reason", "name")], "FailureRecoverable": [("Reason", "name")], "RestartPlan": [],
    "BuildFailureDiagnostic": [("Reason", "name")],
    "AcceptConfig": [("Loaded", "bool")], "DecodeAssignment": [], "SyncApplication": [],
    "AdvanceRun": [("Now", "float")], "CancelRun": [], "Shutdown": [], "ReadClock": [], "Pump": [],
    "ReadClockParts": [], "ResetPerformanceMetrics": [], "FlushPerformanceSummary": [],
    "PreparePolicyKeys": [],
    "BeginTriggeredRun": [("Trigger", "name")],
    "ReadSchedulingClock": [], "ComposeSchedulingClock": [("Seconds", "int"), ("Fraction", "real")],
    "AdvanceTerminalReport": [], "ReadSaveIdentity": [], "PublishTerminalReport": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
if "DumpStaffingProbe" in existing_graphs:
    BP.remove_function_graph(bp, "DumpStaffingProbe")
    existing_graphs.remove("DumpStaffingProbe")
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        if name == "ReadClockParts":
            BP.add_function_param(graphs[name], "Seconds", "int", False)
            BP.add_function_param(graphs[name], "Fraction", "float", False)
        elif name in ("ReadSchedulingClock", "ComposeSchedulingClock"):
            BP.add_function_param(graphs[name], "NowSeconds", "real", False)
        elif name in ("ReadSaveIdentity", "BuildFailureDiagnostic"):
            BP.add_function_param(graphs[name], "Identity" if name == "ReadSaveIdentity" else "Message", "string", False)
        else:
            BP.add_function_param(graphs[name], "Now" if name == "ReadClock" else "Result", "float" if name == "ReadClock" else "bool", False)
    elif name in ("ReadSchedulingClock", "ComposeSchedulingClock"):
        outputs = [pin for node in BP.get_node_infos(BP.find_nodes(graphs[name])) for pin in node.input_pins if pin.name == "NowSeconds"]
        assert len(outputs) == 1
        if "double" not in str(BP._resolve_pin(outputs[0].pin_id).get_pin_type_display_string()).lower():
            BP.remove_function_param(graphs[name], "NowSeconds", False)
            BP.add_function_param(graphs[name], "NowSeconds", "real", False)
BP.compile_blueprint(bp)

if "OnControllerPresentationChanged" not in {str(graph.get_name()) for graph in BP.list_event_dispatchers(bp)}:
    BP.add_event_dispatcher(bp, "OnControllerPresentationChanged")
BP.compile_blueprint(bp)
notification_nodes = list(dict.fromkeys(node for node in BP.find_node_types(graphs["BeginTriggeredRun"], "OnControllerPresentationChanged", [])
                      if node.rsplit("|", 1)[-1].replace(" ", "") == "CallOnControllerPresentationChanged"))
assert len(notification_nodes) == 1, notification_nodes
notify = f"({notification_nodes[0]} :self self)"


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
    return f'(CallFunction|HandleFailure :Reason "{reason}") (return false)'


def fail_from(ref):
    return f"(CallFunction|HandleFailure :Reason {prop(ref, 'FailureCode')}) (return false)"


creations = []
for name, asset in refs.items():
    if name in ("Bridge", "CurrentReport", "CompletedReport", "Logbook"):
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
    {invoke('Settings', 'BeginPolicyKeys')}
    {put('PolicyKeyIndex', '0')}
    {invoke('PolicyCatalog', 'BeginFromContext', f':Context {g("Context")}')}
    {put('Initialized', 'true')} (return true))"""
code["PreparePolicyKeys"] = f"""(fn PreparePolicyKeys ()
    (if (not {g('Initialized')}) (return false))
    (if {prop('Settings', 'PolicyKeysReady')} (return true))
    (if (not {prop('PolicyCatalog', 'CatalogDone')}) {invoke('PolicyCatalog', 'AdvanceCatalog')} (return false))
    (if (not {prop('PolicyCatalog', 'CatalogSucceeded')}) (return false))
    (if (>= {g('PolicyKeyIndex')} {count(prop('PolicyCatalog', 'Types'))})
      (bind ready {invoke('Settings', 'FinishPolicyKeys')}) (if ready {notify}) (return ready))
    (bind added {invoke('Settings', 'AddPolicyKey', f':Type {at(prop("PolicyCatalog", "Types"), g("PolicyKeyIndex"))} :Category {at(prop("PolicyCatalog", "Categories"), g("PolicyKeyIndex"))}')})
    (if (not added) (return false))
    {put('PolicyKeyIndex', f'(+ {g("PolicyKeyIndex")} 1)')} (return false))"""
def concat(*values):
    result = values[0]
    for value in values[1:]: result = f'(Utilities|String|Append :A {result} :B {value})'
    return result

integer = lambda value: f'(Utilities|String|ToString(Integer) {value})'
evidence = concat(g('LastFailureDiagnostic'), '" phase="', integer(g('Phase')), '" guard="', '(Utilities|String|ToString(Name) guard)',
                  '" index="', integer(prop('Snapshot', 'ValidationIndex')), '" captured="', prop('Snapshot', 'ValidationCaptured'),
                  '" live="', prop('Snapshot', 'ValidationLive'))
counts = concat(g('LastFailureDiagnostic'), '" queued="', integer(prop('Runner', 'QueuedCount')), '" confirmed="', integer(prop('Runner', 'AppliedCount')),
                '" fires="', integer(prop('Runner', 'ConfirmedFires')), '" hires="', integer(prop('Runner', 'ConfirmedHires')),
                '" action="', integer(prop('Runner', 'ActionIndex')))
code["BuildFailureDiagnostic"] = f'''(fn BuildFailureDiagnostic (Reason)
    {put('LastFailureDiagnostic', '(Utilities|String|Append :A "WorkerOptimizer stopped: " :B (Utilities|String|ToString(Name) Reason))')}
    (if (not (or (== Reason "world_changed") (== Reason "action_rejected"))) (return {g('LastFailureDiagnostic')}))
    (if {present(g('Snapshot'))}
      (bind guard {prop('Snapshot', 'ValidationGuard')})
      (if (== guard "None") {put('LastFailureDiagnostic', concat(g('LastFailureDiagnostic'), '" phase="', integer(g('Phase')), '" guard=phase_component_unattributed"'))}
        (else {put('LastFailureDiagnostic', evidence)}))
      (else {put('LastFailureDiagnostic', concat(g('LastFailureDiagnostic'), '" phase="', integer(g('Phase')), '" guard=snapshot_unavailable"'))}))
    (if {present(g('Runner'))} {put('LastFailureDiagnostic', counts)})
    (if (and (== Reason "action_rejected") {present(g('Bridge'))})
      {put('LastFailureDiagnostic', concat(g('LastFailureDiagnostic'), '" bridge="', '(Utilities|String|ToString(Name) (Class|BPActionBridge|GetRejectionGuard :self (Variables|Default|GetBridge)))'))})
    (return {g('LastFailureDiagnostic')}))'''
recoverable_bridge_guards = ("building_changed", "worker_changed", "disabled", "hire_role_eligibility",
                            "fire_occupancy", "worker_not_free", "slot_occupied", "optional_before_required")
bridge_drift = "false"
for guard in recoverable_bridge_guards:
    bridge_drift = f'(or (== guard "{guard}") {bridge_drift})'
code["FailureRecoverable"] = f"""(fn FailureRecoverable (Reason)
    (if (== Reason "world_changed") (return true))
    (if (and (== Reason "action_rejected") {present(g('Bridge'))})
      (bind guard (Class|BPActionBridge|GetRejectionGuard :self {g('Bridge')}))
      (return {bridge_drift}))
    (return false))"""
code["HandleFailure"] = f"""(fn HandleFailure (Reason)
    (bind recoverable (CallFunction|FailureRecoverable :Reason Reason))
    (if (and recoverable (and {g('RunActive')} (< {g('ReplanCount')} 2)))
      (if {prop('Runner', 'Waiting')} (return true))
      (bind restarted (CallFunction|RestartPlan)) (if restarted (return true)))
    (CallFunction|FailRun :Reason Reason) (return false))"""
code["RestartPlan"] = f"""(fn RestartPlan ()
    (if (or (not {g('RunActive')}) (or (>= {g('ReplanCount')} 2) {prop('Runner', 'Waiting')})) (return false))
    (if (not {prop('Settings', 'PolicyFrozen')}) (return false))
    (if {prop('Runner', 'Active')} {invoke('Runner', 'FailApplication', ':Reason "world_changed"')})
    (if {prop('Scorer', 'QualityActive')} {invoke('Scorer', 'FailQualityCapture')})
    {put('ReplanCount', f'(+ {g("ReplanCount")} 1)')}
    {put('AppliedCount', prop('Runner', 'AppliedCount'))} {put('QueuedCount', prop('Runner', 'QueuedCount'))}
    {put('FailureCode', '"None"')} {put('ReserveIndex', '0')} {put('DecodeIndex', '0')}
    (Utilities|Array|Clear {g('BuilderQuality')}) (Utilities|Array|Clear {g('FinalWorkers')})
    (Class|BPProblemLayout|SetLayoutDone :self {g('Layout')} :LayoutDone false)
    (Class|BPProblemLayout|SetLayoutSucceeded :self {g('Layout')} :LayoutSucceeded false)
    {invoke('Snapshot', 'BeginCapture', f':WorldContext {g("Context")}')}
    {put('Phase', '1')} (return true))"""
code["FailRun"] = f"""(fn FailRun (Reason)
    (if (and {g('RunDone')} (not {g('RunActive')})) (return false))
    {invoke('Settings', 'ReleasePolicy')}
    (if (not {prop('Runner', 'Waiting')}) {invoke('AutoAssignment', 'OnRunEnded', ':NowSeconds (CallFunction|ReadSchedulingClock)')})
    {put('LateEndPending', prop('Runner', 'Waiting'))}
    (if (not {g('RunDone')})
      {put('TerminalOutcome', '(select (== Reason "cancelled") "cancelled" "failed")')} {put('FailureCode', 'Reason')})
    {put('RunActive', 'false')} {put('RunDone', 'true')} {put('RunSucceeded', 'false')}
    (bind message (CallFunction|BuildFailureDiagnostic :Reason Reason)) {put('LastFailureDiagnostic', 'message')}
    (bind api (Class|ModAPI|GetModAPI))
    (if {present('api')}
      (Class|ModAPI|LogMessage :self api :Msg message :doPrependDate true))
    (Utilities|Array|Clear {g('FinalWorkers')}) (CallFunction|AdvanceTerminalReport) {notify} (return false))"""
code["CompleteRun"] = f"""(fn CompleteRun ()
    {invoke('Settings', 'ReleasePolicy')}
    {invoke('AutoAssignment', 'OnRunEnded', ':NowSeconds (CallFunction|ReadSchedulingClock)')}
    {put('RunActive', 'false')} {put('RunDone', 'true')} {put('RunSucceeded', 'true')}
    {put('FailureCode', '"None"')} {put('TerminalOutcome', '"completed"')} {put('Phase', '7')}
    (CallFunction|AdvanceTerminalReport) {notify} (return true))"""
code["ReadSaveIdentity"] = """(fn ReadSaveIdentity ()
    (bind (valid systems) (Class|ArcoSystems|GetArcoSys))
    (if (not valid) (return ""))
    (if (not (CallFunction|HasObject :Object systems)) (return ""))
    (return (Class|ArcoSystems|GetMAssociatedSave :self systems)))"""
code["AdvanceTerminalReport"] = f"""(fn AdvanceTerminalReport ()
    (if (or (not {g('ReportPending')}) (or (not {g('RunDone')}) {g('RunActive')})) (return false))
    (if (or {prop('Runner', 'Waiting')} {prop('Runner', 'Active')}) (return false))
    (if (not {prop('CurrentReport', 'FinishStarted')})
      (bind accepted {invoke('CurrentReport', 'BeginFinish', f':Outcome {g("TerminalOutcome")} :Failure {g("FailureCode")} :Snapshot {g("Snapshot")} :Layout {g("Layout")} :Runner {g("Runner")}')})
      (if (not accepted) (return false)))
    {invoke('CurrentReport', 'AdvanceReport')}
    (if {prop('CurrentReport', 'ReportDone')} (CallFunction|PublishTerminalReport)) (return true))"""
code["PublishTerminalReport"] = f"""(fn PublishTerminalReport ()
    (if (or (not {g('ReportPending')}) {g('ReportPublished')}) (return false))
    (if (not {prop('CurrentReport', 'ReportDone')}) (return false))
    {put('CompletedReport', g('CurrentReport'))} {put('ReportPending', 'false')} {put('ReportPublished', 'true')}
    (if {present(g('Logbook'))} {invoke('Logbook', 'AppendReport', f':Report {g("CompletedReport")}')})
    {put('CompletedRecordCount', f'(+ {g("CompletedRecordCount")} 1)')} {notify} (return true))"""
code["BeginRun"] = """(fn BeginRun () (bind accepted (CallFunction|BeginTriggeredRun :Trigger "manual")) (return accepted))"""
code["BeginTriggeredRun"] = f"""(fn BeginTriggeredRun (Trigger)
    (if (not (or (== Trigger "manual") (or (== Trigger "day_start") (or (== Trigger "minutes_5") (or (== Trigger "minutes_10") (== Trigger "minutes_15")))))) (return false))
    (if (or (not {g('Initialized')}) (or {g('RunActive')} {g('ReportPending')})) (return false))
    (if (not {present(g('Context'))}) (return false))
    (if (not {present(g('Bridge'))}) (return false))
    (if (not {prop('Bridge', 'BridgeReady')}) (return false))
    (if (or {prop('Runner', 'Active')} {prop('Runner', 'Waiting')}) (return false))
    (if (not {prop('Settings', 'PolicyKeysReady')}) (return false))
    (bind captured {invoke('Settings', 'CapturePolicy', f':Context {g("Context")}')})
    (if (not captured) {invoke('Settings', 'ReleasePolicy')} (return false))
    (bind report (Game|ConstructObjectfromClass :Class "{ROOT}/BP_RunReport.BP_RunReport_C" :self self))
    (if (not {present('report')}) {invoke('Settings', 'ReleasePolicy')} (return false))
    {put('CurrentReport', 'report')}
    (bind reportStarted {invoke('CurrentReport', 'BeginReport', f':RunId (Guid|ToString(Guid) (Guid|NewGuid)) :Trigger Trigger :SaveIdentity (CallFunction|ReadSaveIdentity) :StartedAt (Math|DateTime|UTCNow) :Reserve {prop("Settings", "FrozenReserve")}')})
    (if (not reportStarted) {invoke('Settings', 'ReleasePolicy')} (return false))
    (bind configuration {invoke('CurrentReport', 'CaptureConfiguration', f':Settings {g("Settings")}')})
    (if (not configuration) {invoke('Settings', 'ReleasePolicy')} (return false))
    {invoke('Runner', 'ResetConfirmedActions')}
    (if {prop('Scorer', 'QualityActive')} {invoke('Scorer', 'FailQualityCapture')})
    {invoke('Snapshot', 'ResetSnapshot')} (Class|BPWorkforceSnapshot|SetSnapshotValid :self {g('Snapshot')} :SnapshotValid false)
    {put('LastFailureDiagnostic', '""')}
    (Class|BPProblemLayout|SetLayoutDone :self {g('Layout')} :LayoutDone false)
    (Class|BPProblemLayout|SetLayoutSucceeded :self {g('Layout')} :LayoutSucceeded false)
    {put('ReportPending', 'true')} {put('ReportPublished', 'false')}
    {invoke('AutoAssignment', 'OnRunStarted', ':NowSeconds (CallFunction|ReadSchedulingClock)')}
    {put('RunTrigger', 'Trigger')}
    {put('RunActive', 'true')} {put('RunDone', 'false')} {put('RunSucceeded', 'false')}
    {put('FailureCode', '"None"')} {put('Phase', '0')} {put('AppliedCount', '0')} {put('QueuedCount', '0')}
    {put('ReplanCount', '0')}
    {put('ReserveIndex', '0')} (Utilities|Array|Clear {g('BuilderQuality')})
    (Utilities|Array|Clear {g('FinalWorkers')}) {notify} (return true))"""
code["AcceptConfig"] = f"""(fn AcceptConfig (Loaded)
    (if (or (not {g('RunActive')}) (!= {g('Phase')} 0)) (return false))
    (if (not Loaded) {fail('configuration_unavailable')})
    (if (not {prop('Scorer', 'Ready')}) {fail('configuration_unavailable')})
    (if (not {prop('Settings', 'PolicyFrozen')}) {fail('configuration_unavailable')})
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
    (if (and {g('RunDone')} (not {g('RunActive')})) (return true))
    (if {prop('Runner', 'Done')}
      (if {prop('Runner', 'Succeeded')} (CallFunction|CompleteRun) (return true))
      {fail_from('Runner')}) (return true))"""
code["AdvanceRun"] = f"""(fn AdvanceRun (Now)
    (if (not {g('Initialized')}) (return false))
    (if (not {g('RunActive')})
      (if (== {g('Phase')} 6)
        (if {prop('Runner', 'Waiting')} {invoke('Runner', 'AdvanceApplication', ':Now Now')})
        (CallFunction|SyncApplication)
        (if (and {g('LateEndPending')} (not {prop('Runner', 'Waiting')}))
          {invoke('AutoAssignment', 'OnRunEnded', ':NowSeconds (CallFunction|ReadSchedulingClock)')} {put('LateEndPending', 'false')} {notify}))
      (CallFunction|AdvanceTerminalReport) (return false))
    (switch int {g('Phase')}
      (:0
        (bind loaded {invoke('Scorer', 'LoadConfig', f':Context {g("Context")}')})
        (bind accepted (CallFunction|AcceptConfig :Loaded loaded)) (return accepted))
      (:1
        (if (not {prop('Snapshot', 'CaptureDone')}) {invoke('Snapshot', 'AdvanceCapture')} (return true))
        (if (not {prop('Snapshot', 'SnapshotValid')}) {fail('invalid_snapshot')})
        (bind qualityStarted {invoke('Scorer', 'BeginQualityCapture', f':InputWorkers {prop("Snapshot", "Workers")}')})
        (if (not qualityStarted) {fail('builder_score_unavailable')})
        (bind layoutStarted {invoke('Layout', 'BeginLayout', f':InputSnapshot {g("Snapshot")}')})
        (if (not layoutStarted) {fail_from('Layout')}) {put('Phase', '2')} (return true))
      (:2
        (if (not {prop('Layout', 'LayoutDone')}) {invoke('Layout', 'AdvanceLayout')} (return true))
        (if (not {prop('Layout', 'LayoutSucceeded')}) {fail_from('Layout')})
        (if (not {prop('Scorer', 'QualityDone')}) {invoke('Scorer', 'AdvanceQualityCapture')} (return true))
        (if (not {prop('Scorer', 'QualitySucceeded')}) {fail('builder_score_unavailable')})
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
        {put('PriorAppliedCount', prop('Runner', 'AppliedCount'))} {put('PriorQueuedCount', prop('Runner', 'QueuedCount'))}
        {put('PriorFires', prop('Runner', 'ConfirmedFires'))} {put('PriorHires', prop('Runner', 'ConfirmedHires'))}
        (bind applicationStarted {invoke('Runner', 'StartApplication', f':InputSnapshot {g("Snapshot")} :InputBridge {g("Bridge")} :InputBuildings {prop("ActionPlan", "ActionBuildings")} :InputSlots {prop("ActionPlan", "ActionSlots")} :InputWorkers {prop("ActionPlan", "ActionWorkers")} :InputFire {prop("ActionPlan", "ActionFire")} :Now Now')})
        (Class|BPApplicationRunner|SetAppliedCount :self {g('Runner')} :AppliedCount (+ {g('PriorAppliedCount')} {prop('Runner', 'AppliedCount')}))
        (Class|BPApplicationRunner|SetQueuedCount :self {g('Runner')} :QueuedCount (+ {g('PriorQueuedCount')} {prop('Runner', 'QueuedCount')}))
        (Class|BPApplicationRunner|SetConfirmedFires :self {g('Runner')} :ConfirmedFires (+ {g('PriorFires')} {prop('Runner', 'ConfirmedFires')}))
        (Class|BPApplicationRunner|SetConfirmedHires :self {g('Runner')} :ConfirmedHires (+ {g('PriorHires')} {prop('Runner', 'ConfirmedHires')}))
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
        (if (not {prop('Layout', 'LayoutDone')}) {invoke('Layout', 'FailLayout', ':Reason "cancelled"')})
        {invoke('ActionPlan', 'FailBuild', ':Reason "cancelled"')}
        (if (not {prop('Snapshot', 'CaptureDone')})
          {invoke('Snapshot', 'ResetSnapshot')} (Class|BPWorkforceSnapshot|SetSnapshotValid :self {g('Snapshot')} :SnapshotValid false))))
    (CallFunction|FailRun :Reason "cancelled") (return true))"""
code["Shutdown"] = f"""(fn Shutdown ()
    (if (not {g('Initialized')}) (return false))
    (if {g('RunActive')} (CallFunction|CancelRun))
    (if {g('ReportPending')}
      (bind closed {invoke('CurrentReport', 'CloseUnavailable', f':Outcome (select (== {g("TerminalOutcome")} "completed") "failed" {g("TerminalOutcome")}) :Failure (select (== {g("TerminalOutcome")} "completed") "observation_unavailable" {g("FailureCode")}) :Runner {g("Runner")}')})
      (if closed (CallFunction|PublishTerminalReport)))
    (if {present(g('Settings'))} {invoke('Settings', 'ReleasePolicy')})
    (if {present(g('AutoAssignment'))} {invoke('AutoAssignment', 'ResetSession')})
    {put('Initialized', 'false')} (Variables|Default|SetContext) (Variables|Default|SetBridge) (return true))"""
code["ReadClock"] = """(fn ReadClock ()
    (bind (seconds fraction) (Utilities|Time|GetAccurateRealTime))
    (return (+ seconds fraction)))"""
code["ReadClockParts"] = """(fn ReadClockParts ()
    (bind (seconds fraction) (Utilities|Time|GetAccurateRealTime))
    (return seconds fraction))"""
code["ComposeSchedulingClock"] = """(fn ComposeSchedulingClock (Seconds Fraction)
    (bind integral (Math|Conversions|ToFloat(Integer) Seconds))
    (return (+ integral Fraction)))"""
code["ReadSchedulingClock"] = """(fn ReadSchedulingClock ()
    (bind (seconds fraction) (CallFunction|ReadClockParts))
    (bind now (CallFunction|ComposeSchedulingClock :Seconds seconds :Fraction fraction)) (return now))"""
code["ResetPerformanceMetrics"] = f"""(fn ResetPerformanceMetrics ()
    (if (or (not {g('MeasurePerformance')}) (not {present(g('Metrics'))})) (return false))
    (if (or {g('RunActive')} (or {prop('Runner', 'Waiting')} {g('ReportPending')})) (return false))
    (bind reset {invoke('Metrics', 'ResetMetrics')}) (return reset))"""
code["FlushPerformanceSummary"] = f"""(fn FlushPerformanceSummary ()
    (if (or (not {g('MeasurePerformance')}) (not {present(g('Metrics'))})) (return false))
    (if (or {g('RunActive')} (or {prop('Runner', 'Waiting')} {g('ReportPending')})) (return false))
    {put('MeasurePerformance', 'false')}
    (bind api (Class|ModAPI|GetModAPI)) (if (not {present('api')}) (return false))
    (bind summary {invoke('Metrics', 'BuildSummary')})
    (Class|ModAPI|LogMessage :self api :Msg summary :doPrependDate true) (return true))"""
code["Pump"] = f"""(fn Pump ()
    (if (not {g('Initialized')}) (return false))
    (if (not {prop('Settings', 'PolicyKeysReady')})
      (bind prepared (CallFunction|PreparePolicyKeys)) (return prepared))
    (if (not (or {g('RunActive')} (or {prop('Runner', 'Waiting')} {g('ReportPending')}))) (return false))
    (bind (startSeconds startFraction) (CallFunction|ReadClockParts))
    {put('PumpStartSeconds', 'startSeconds')} {put('PumpStartFraction', 'startFraction')}
    (for step (range 64)
      (bind (nowSeconds nowFraction) (CallFunction|ReadClockParts))
      {put('PumpNow', '(+ (Math|Conversions|ToFloat(Integer) nowSeconds) nowFraction)')}
      (if {g('MeasurePerformance')}
        {put('StepStartSeconds', 'nowSeconds')} {put('StepStartFraction', 'nowFraction')}
        {put('SamplePhase', f'(select (and {g("ReportPending")} (and (not {g("RunActive")}) (not {prop("Runner", "Waiting")}))) 7 {g("Phase")})')})
      (CallFunction|AdvanceRun :Now {g('PumpNow')})
      (bind (afterSeconds afterFraction) (CallFunction|ReadClockParts))
      (if {g('MeasurePerformance')}
        (bind stepElapsed {invoke('Metrics', 'ElapsedSeconds', f':StartSeconds {g("StepStartSeconds")} :StartFraction {g("StepStartFraction")} :EndSeconds afterSeconds :EndFraction afterFraction')})
        {invoke('Metrics', 'RecordSample', f':Phase {g("SamplePhase")} :Seconds stepElapsed')})
      (if (or (and (== {g('Phase')} 6) (or {g('RunActive')} {prop('Runner', 'Waiting')}))
          (not (or {g('RunActive')} {g('ReportPending')}))) (break))
      (bind elapsed {invoke('Metrics', 'ElapsedSeconds', f':StartSeconds {g("PumpStartSeconds")} :StartFraction {g("PumpStartFraction")} :EndSeconds afterSeconds :EndFraction afterFraction')})
      (if (>= elapsed 0.002) (break)))
    (if {g('MeasurePerformance')}
      (bind (endSeconds endFraction) (CallFunction|ReadClockParts))
      (bind pumpElapsed {invoke('Metrics', 'ElapsedSeconds', f':StartSeconds {g("PumpStartSeconds")} :StartFraction {g("PumpStartFraction")} :EndSeconds endSeconds :EndFraction endFraction')})
      {invoke('Metrics', 'RecordSample', ':Phase 8 :Seconds pumpElapsed')}) (return true))"""
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
    cdo.set_editor_property("MeasurePerformance", False, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Controller.dsl").write_text("\n\n".join(code.values()) + "\n" + event_source, encoding="utf-8")
unreal.log("WO_CONTROLLER_GENERATED")
exec(Path(__file__).with_name("test_controller.py").read_text(encoding="utf-8"))
