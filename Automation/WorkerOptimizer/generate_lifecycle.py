"""Generate native load-finished binding and per-world session ownership."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
MANUAL_ONLY = True
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
api_class = unreal.load_class(None, "/Script/SystemCore.ModAPI")
bp = unreal.load_asset(ROOT + "/BP_MapLoad")
if bp is None:
    bp = BP.create(ROOT, "BP_MapLoad", unreal.Actor.static_class())
refs = {"Controller": "BP_WorkerOptimizer", "Bridge": "BP_ActionBridge", "ActionView": "WBP_ActionContext", "UI": "WBP_WorkerOptimizer", "Hotkey": "BP_HotkeyConfig", "Logbook": "BP_Logbook"}
existing = set(BP.list_variables(bp))
for name, cls in [(name, load(asset)) for name, asset in refs.items()] + [("API", api_class)]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {"bool": "Primary Bound Loaded Ready ShuttingDown HasPerformancePrevious", "name": "FailureCode", "float": "NextStartupCheck NextHistoryCheck PerformancePreviousFraction PerformanceUIFraction", "int": "PerformancePreviousSeconds PerformanceUISeconds PerformanceUIPhase"}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())], "OwnsWorld": [], "ClaimWorld": [],
    "FailSession": [("Reason", "name")], "BeginLifecycle": [], "AttachAPI": [("InputAPI", api_class)],
    "BindLoading": [], "UnbindLoading": [], "OnLoaded": [], "CreateSession": [],
    "InstallSession": [("InputController", load("BP_WorkerOptimizer")), ("InputBridge", load("BP_ActionBridge")), ("InputView", load("WBP_ActionContext"))],
    "ReleaseSession": [], "Shutdown": [],
    "CreateUI": [], "InstallUI": [("InputWidget", load("WBP_WorkerOptimizer")), ("InputConfig", load("BP_HotkeyConfig"))],
    "PumpUI": [], "SyncGameplayVisibility": [],
    "HudAllowsDisplay": [("InputHud", unreal.load_class(None, "/Script/ProjectArco.PlayHud")),
                         ("InputController", unreal.load_class(None, "/Script/ProjectArco.PlayerController_Play"))],
    "ObserveReadiness": [("WorldReady", "bool"), ("PlayerReady", "bool")],
    "PumpLifecycle": [],
    "MeasureUI": [],
    "BindDay": [], "UnbindDay": [], "OnDayStart": [("day", "int")],
    "ReadCalendar": [], "PollAutomatic": [],
    "PumpHistory": [],
}
void_functions = {"BindLoading", "UnbindLoading", "OnLoaded", "BindDay", "UnbindDay", "OnDayStart"}
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
        if name == "ReadCalendar":
            for param, kind in (("Valid", "bool"), ("Year", "int"), ("Day", "int")):
                BP.add_function_param(graphs[name], param, kind, False)
        elif name not in void_functions:
            BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
node_types = BP.find_node_types(graphs["ClaimWorld"], "", [])
make_transform = next(n for n in node_types if n.endswith("|MakeTransform"))
add_viewport = next(n for n in node_types if n.rsplit("|", 1)[-1].lower() == "addtoviewport")
for suffix in ("OwnsWorld", "RemovefromParent"):
    for node in node_types:
        if node.endswith("|" + suffix):
            pins = BP.get_node_type_pins(graphs["ClaimWorld"], node)
            unreal.log("WO_LIFECYCLE_MEMBER " + node + " " + str([(p.name, p.type_id) for p in pins.input_pins]))


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def invoke(ref, name, args="", source=None):
    return f"(Class|{refs[ref].replace('_', '')}|{name} :self {source or g(ref)} {args})"


def fail(reason):
    return f'(CallFunction|FailSession :Reason "{reason}") (return false)'


def factory_fail(reason):
    return f"(CallFunction|ReleaseSession) {fail(reason)}"


def trace(stage, api=None):
    return (f'(Class|ModAPI|LogMessage :self {api or g("API")} '
            f':Msg "WorkerOptimizer lifecycle: {stage}" :doPrependDate true)')


def unpack(struct, value, prefix):
    kind = "Utilities|Struct|Break" + struct
    names = [prefix + str(pin.name) for pin in BP.get_node_type_pins(graphs["HudAllowsDisplay"], kind).output_pins]
    return f"(bind ({' '.join(names)}) ({kind} {value}))"


code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["OwnsWorld"] = f"""(fn OwnsWorld () (return (and {g('Primary')} (not {g('ShuttingDown')}))))"""
code["FailSession"] = f"""(fn FailSession (Reason)
    {put('FailureCode', 'Reason')}
    (if {present(g('API'))}
      (Class|ModAPI|LogMessage :self {g('API')}
        :Msg (Utilities|String|Append :A "Worker Optimizer map load: " :B (Utilities|String|ToString(Name) Reason)) :doPrependDate true))
    (return false))"""
code["ClaimWorld"] = f"""(fn ClaimWorld ()
    (if {g('ShuttingDown')} (return false))
    (if {g('Primary')} (return true))
    (bind peers (Actor|GetAllActorsOfClass :ActorClass "{ROOT}/BP_MapLoad.BP_MapLoad_C"))
    (for peer peers
      (if (!= peer self)
        (bind typed (Utilities|Casting|CastToBP_MapLoad :Object peer)
          (:then
            (if (CallFunction|OwnsWorld :self typed)
              {fail('duplicate_instance')})))))
    {put('Primary', 'true')} (return true))"""
code["BeginLifecycle"] = f"""(fn BeginLifecycle ()
    (bind api (Class|ModAPI|GetModAPI))
    (if {present('api')} {trace('begin', 'api')})
    (bind attached (CallFunction|AttachAPI :InputAPI api)) (return attached))"""
code["AttachAPI"] = f"""(fn AttachAPI (InputAPI)
    (if {g('ShuttingDown')} (return false))
    (if {g('Bound')} (return (== InputAPI {g('API')})))
    (bind claimed (CallFunction|ClaimWorld)) (if (not claimed) (return false))
    (if (not {present('InputAPI')}) {fail('mod_api_unavailable')})
    {put('API', 'InputAPI')} (CallFunction|BindLoading) (CallFunction|BindDay) {put('Bound', 'true')}
    {trace('bound')} (return true))"""
code["BindLoading"] = f"""(fn BindLoading ()
    (EventDispatchers|BindEventtoOnLoadingFinished :self {g('API')}))"""
code["UnbindLoading"] = f"""(fn UnbindLoading ()
    (EventDispatchers|UnbindEventfromOnLoadingFinished :self {g('API')}))"""
code["BindDay"] = f"""(fn BindDay () (EventDispatchers|BindEventtoOnDayStart :self {g('API')}))"""
code["UnbindDay"] = f"""(fn UnbindDay () (EventDispatchers|UnbindEventfromOnDayStart :self {g('API')}))"""
code["ReadCalendar"] = f"""(fn ReadCalendar ()
    (bind (valid systems) (Class|ArcoSystems|GetArcoSys))
    (if (or (not valid) (not {present('systems')})) (return false -1 -1))
    (bind clock (Class|ArcoSystems|GetMWorldTime :self systems))
    (if (not {present('clock')}) (return false -1 -1))
    (return true (Class|WorldTime|GetMYear :self clock) (Class|WorldTime|GetMDay :self clock)))"""
code["OnDayStart"] = f"""(fn OnDayStart (day)
    (if (or {g('ShuttingDown')} (or (not {g('Ready')}) (not {present(g('Controller'))}))) (return))
    (bind (valid year currentDay) (CallFunction|ReadCalendar))
    (if (not valid) (return))
    (bind scheduler (Class|BPWorkerOptimizer|GetAutoAssignment :self {g('Controller')}))
    (if (not {present('scheduler')}) (return))
    (Class|BPAutoAssignment|ObserveDay :self scheduler :Year year :Day day))"""
code["PollAutomatic"] = f"""(fn PollAutomatic ()
    (if (or {g('ShuttingDown')} (or (not {g('Ready')}) (not {present(g('Controller'))}))) (return false))
    (bind scheduler (Class|BPWorkerOptimizer|GetAutoAssignment :self {g('Controller')}))
    (bind settings (Class|BPWorkerOptimizer|GetSettings :self {g('Controller')}))
    (if (or (not {present('scheduler')}) (not {present('settings')})) (return false))
    (bind mode (Class|BPPrioritySettings|ReadAutoMode :self settings :Context self))
    (bind now (Class|BPWorkerOptimizer|ReadSchedulingClock :self {g('Controller')}))
    (if (== mode "off")
      (Class|BPAutoAssignment|Configure :self scheduler :Mode mode :NowSeconds now :Year -1 :Day -1)
      (return false))
    (bind (valid year day) (CallFunction|ReadCalendar))
    (if (not valid) (return false))
    (Class|BPAutoAssignment|Configure :self scheduler :Mode mode :NowSeconds now :Year year :Day day)
    (bind runner (Class|BPWorkerOptimizer|GetRunner :self {g('Controller')}))
    (bind busy (or (Class|BPWorkerOptimizer|GetRunActive :self {g('Controller')})
      (or (Class|BPApplicationRunner|GetActive :self runner) (Class|BPApplicationRunner|GetWaiting :self runner))))
    (bind ready (and (Class|BPWorkerOptimizer|GetInitialized :self {g('Controller')}) (Class|BPPrioritySettings|GetPolicyKeysReady :self settings)))
    (bind due (Class|BPAutoAssignment|Poll :self scheduler :NowSeconds now :Paused (Game|IsGamePaused) :Ready ready :Busy busy))
    (if (not due) (return false))
    (bind accepted (Class|BPWorkerOptimizer|BeginTriggeredRun :self {g('Controller')} :Trigger mode)) (return accepted))"""
code["OnLoaded"] = f"""(fn OnLoaded ()
    (if {present(g('API'))} {trace('loading_finished')})
    (if (or {g('ShuttingDown')} (or (not {g('Bound')}) (not {g('Primary')}))) (return))
    (if {g('Loaded')} (return))
    {put('Loaded', 'true')}
    (CallFunction|CreateSession))"""
code["ObserveReadiness"] = f"""(fn ObserveReadiness (WorldReady PlayerReady)
    (if (or {g('ShuttingDown')} (or (not {g('Bound')}) (not {g('Primary')}))) (return false))
    (if (or (not WorldReady) (not PlayerReady)) (return false))
    (if (not {g('Loaded')}) {trace('world_ready')} {put('Loaded', 'true')})
    (return true))"""
# New colonies and late-bound mods do not necessarily receive the save-load event.
# Use the game's explicit init phase; never infer readiness from elapsed time.
code["PumpLifecycle"] = f"""(fn PumpLifecycle ()
    (if {g('ShuttingDown')} (return false))
    (if {g('Ready')}
      (CallFunction|PumpHistory)
      (CallFunction|PollAutomatic)
      (if (and {present(g('Controller'))} (Class|BPWorkerOptimizer|GetMeasurePerformance :self {g('Controller')}))
        (bind measured (CallFunction|MeasureUI)) (return measured))
      {put('HasPerformancePrevious', 'false')}
      (bind pumped (CallFunction|PumpUI)) (return pumped))
    (bind now (Utilities|Time|GetRealTimeSeconds))
    (if (< now {g('NextStartupCheck')}) (return false))
    {put('NextStartupCheck', '(+ now 0.5)')}
    (if (not {g('Bound')}) (CallFunction|BeginLifecycle))
    (if (or (not {g('Bound')}) (not {g('Primary')})) (return false))
    (bind mode (Utilities|Casting|CastToProjectArcoGameModeBase :Object (Game|GetGameMode))
      (:then
        (bind phase (Class|ProjectArcoGameModeBase|CurrentInitPhase :self mode))
        (bind observed (CallFunction|ObserveReadiness :WorldReady (Utilities|Enum|Equal(Enum) :A phase)
            :PlayerReady {present('(Game|GetPlayerController :PlayerIndex 0)')}))
        (if observed (bind installed (CallFunction|CreateSession)) (return installed))
        (return false))
      (:CastFailed (return false))))"""
code["PumpHistory"] = f"""(fn PumpHistory ()
    (if (or {g('ShuttingDown')} (not {present(g('Logbook'))})) (return false))
    (bind now (Utilities|Time|GetRealTimeSeconds))
    (if (>= now {g('NextHistoryCheck')})
      {put('NextHistoryCheck','(+ now 0.5)')}
      (bind (valid identity) {invoke('Logbook','ResolveIdentity',':Context self')})
      (if (not (Utilities|String|EqualExactly(String) identity (Class|BPLogbook|GetActiveIdentity :self {g('Logbook')})))
        {invoke('Logbook','BeginLoad',':Identity identity')}))
    (if (and (Class|BPLogbook|GetReady :self {g('Logbook')}) (not (Class|BPLogbook|GetDirty :self {g('Logbook')}))) (return false))
    (if (and (== (Utilities|String|Len (Class|BPLogbook|GetActiveIdentity :self {g('Logbook')})) 0)
      (not (Class|BPLogbook|GetDirty :self {g('Logbook')}))) (return false))
    (bind (startSeconds startFraction) (Class|BPWorkerOptimizer|ReadClockParts :self {g('Controller')}))
    (bind metrics (Class|BPWorkerOptimizer|GetMetrics :self {g('Controller')}))
    (for unit (range 64)
      {invoke('Logbook','AdvanceStorage')}
      (if (and (Class|BPLogbook|GetInFlight :self {g('Logbook')})
        (== (Utilities|Array|Length (Class|BPLogbook|GetPendingReports :self {g('Logbook')})) 0)) (break))
      (if (and (Class|BPLogbook|GetReady :self {g('Logbook')}) (not (Class|BPLogbook|GetDirty :self {g('Logbook')}))) (break))
      (bind (endSeconds endFraction) (Class|BPWorkerOptimizer|ReadClockParts :self {g('Controller')}))
      (bind elapsed (Class|BPPerformanceMetrics|ElapsedSeconds :self metrics :StartSeconds startSeconds :StartFraction startFraction :EndSeconds endSeconds :EndFraction endFraction))
      (if (>= elapsed 0.002) (break)))
    (return true))"""
code["InstallSession"] = f"""(fn InstallSession (InputController InputBridge InputView)
    (if (or {g('ShuttingDown')} (or (not {g('Loaded')}) (not {g('Primary')}))) (return false))
    (if {g('Ready')} (return (and (== InputController {g('Controller')}) (and (== InputBridge {g('Bridge')}) (== InputView {g('ActionView')})))))
    (if (or (not {present('InputController')}) (or (not {present('InputBridge')}) (not {present('InputView')}))) (return false))
    (if (or (!= (Actor|GetOwner :self InputController) self) (!= (Actor|GetOwner :self InputBridge) self)) (return false))
    {' '.join(f'(if (and {present(g(ref))} (!= {g(ref)} {param})) (return false))' for ref, param in [('Controller', 'InputController'), ('Bridge', 'InputBridge'), ('ActionView', 'InputView')])}
    (bind bridgeReady {invoke('Bridge', 'InitializeBridge', ':Widget InputView', 'InputBridge')})
    (if (not bridgeReady) {fail('bridge_initialization_failed')})
    (bind controllerReady {invoke('Controller', 'Initialize', ':InputContext self :InputBridge InputBridge', 'InputController')})
    (if (not controllerReady) {fail('controller_initialization_failed')})
    {put('Controller', 'InputController')} {put('Bridge', 'InputBridge')} {put('ActionView', 'InputView')}
    (bind history (Game|ConstructObjectfromClass :Class "{ROOT}/BP_Logbook.BP_Logbook_C" :self self))
    {put('Logbook','history')}
    (Class|BPWorkerOptimizer|SetLogbook :self InputController :Logbook history)
    (bind (identityValid identity) {invoke('Logbook','ResolveIdentity',':Context self')})
    {invoke('Logbook','BeginLoad',':Identity identity')}
    {put('Ready', 'true')} {put('FailureCode', '"None"')} (return true))"""
code["CreateSession"] = f"""(fn CreateSession ()
    (if (or {g('ShuttingDown')} (or (not {g('Loaded')}) (not {g('Primary')}))) (return false))
    (if {g('Ready')} (bind uiReady (CallFunction|CreateUI)) (return uiReady))
    {trace('create_session')}
    (bind player (Game|GetPlayerController :PlayerIndex 0))
    (if (not {present('player')}) {fail('player_unavailable')})
    (bind view (UserInterface|CreateWidget :Class "{ROOT}/WBP_ActionContext.WBP_ActionContext_C" :OwningPlayer player))
    {put('ActionView', 'view')}
    (if (not {present(g('ActionView'))}) {factory_fail('context_creation_failed')})
    (bind bridge (Game|SpawnActorfromClass :Class "{ROOT}/BP_ActionBridge.BP_ActionBridge_C" :Owner self
      :SpawnTransform ({make_transform}) :CollisionHandlingOverride "AlwaysSpawn"))
    {put('Bridge', 'bridge')}
    (if (not {present(g('Bridge'))}) {factory_fail('bridge_creation_failed')})
    (bind controller (Game|SpawnActorfromClass :Class "{ROOT}/BP_WorkerOptimizer.BP_WorkerOptimizer_C" :Owner self
      :SpawnTransform ({make_transform}) :CollisionHandlingOverride "AlwaysSpawn"))
    {put('Controller', 'controller')}
    (if (not {present(g('Controller'))}) {factory_fail('controller_creation_failed')})
    (bind installed (CallFunction|InstallSession :InputController {g('Controller')} :InputBridge {g('Bridge')} :InputView {g('ActionView')}))
    (if (not installed) (CallFunction|ReleaseSession) (return false))
    {trace('session_ready')}
    (bind uiReady (CallFunction|CreateUI))
    (if (not uiReady) (CallFunction|ReleaseSession) (return false)) (return true))"""
code["InstallUI"] = f"""(fn InstallUI (InputWidget InputConfig)
    (if (or {g('ShuttingDown')} (not {g('Ready')})) (return false))
    (if (or (not {present('InputWidget')}) (not {present('InputConfig')})) (return false))
    (if {present(g('UI'))} (return (and (== InputWidget {g('UI')}) (== InputConfig {g('Hotkey')}))))
    (bind initialized {invoke('UI', 'InitializeUI', f':InputController {g("Controller")} :InputConfig InputConfig', 'InputWidget')})
    (if (not initialized) {fail('ui_initialization_failed')})
    {put('UI', 'InputWidget')} {put('Hotkey', 'InputConfig')} (return true))"""
code["CreateUI"] = f"""(fn CreateUI ()
    (if (or {g('ShuttingDown')} (not {g('Ready')})) (return false))
    (if {present(g('UI'))} (return true))
    (bind player (Game|GetPlayerController :PlayerIndex 0))
    (if (not {present('player')}) {fail('player_unavailable')})
    (bind preferences (Game|ConstructObjectfromClass :Class "{ROOT}/BP_HotkeyConfig.BP_HotkeyConfig_C" :self self))
    (if (not {present('preferences')}) {fail('hotkey_creation_failed')})
    {invoke('Hotkey', 'LoadSettings', ':Slot "WorkerOptimizer_UI_v1"', 'preferences')}
    (bind widget (UserInterface|CreateWidget :Class "{ROOT}/WBP_WorkerOptimizer.WBP_WorkerOptimizer_C" :OwningPlayer player))
    (if (not {present('widget')}) {fail('widget_creation_failed')})
    (bind installed (CallFunction|InstallUI :InputWidget widget :InputConfig preferences))
    (if (not installed) (Widget|RemovefromParent :self widget) (return false))
    (CallFunction|SyncGameplayVisibility)
    ({add_viewport} :self widget :ZOrder 30)
    {trace('ui_added')} (return true))"""
code["HudAllowsDisplay"] = f"""(fn HudAllowsDisplay (InputHud InputController)
    (if (or (not {present('InputHud')}) (not {present('InputController')})) (return false))
    (if (not (Class|PlayHud|GetMUiHasFadedIn :self InputHud)) (return false))
    {unpack('ArcoPlayerState', '(Class|PlayerControllerPlay|GetMState :self InputController)', 'p_')}
    (if (or {present('p_activeArcoView')} (or (not p_m_showHud) (or p_m_dev_hideAllHud p_m_showReplayMenu))) (return false))
    {unpack('HudState', '(Class|PlayHud|GetMHudState :self InputHud)', 'h_')}
    (if h_showSaving (return false))
    {unpack('VisibilityToggles', 'h_sectionVisibilities', 'v_')}
    (return v_showHudRoot))"""
hide_ui = invoke('UI', 'ApplyGameplayVisibility', ':Visible false')
code["SyncGameplayVisibility"] = f"""(fn SyncGameplayVisibility ()
    (if (not {present(g('UI'))}) (return false))
    (if (or {g('ShuttingDown')} (not {g('Ready')})) {hide_ui} (return false))
    (bind mode (Utilities|Casting|CastToProjectArcoGameModeBase :Object (Game|GetGameMode))
      (:then
        (bind phase (Class|ProjectArcoGameModeBase|CurrentInitPhase :self mode))
        (if (not (Utilities|Enum|Equal(Enum) :A phase)) {hide_ui} (return false))
        (bind (found systems) (Class|ArcoSystems|GetArcoSys))
        (if (or (not found) (not {present('systems')})) {hide_ui} (return false))
        (if (not (Class|ArcoSystems|IsLive :self systems)) {hide_ui} (return false))
        (bind player (Utilities|Casting|CastToPlayerController_Play :Object (Game|GetPlayerController :PlayerIndex 0))
          (:then
            (bind visible (CallFunction|HudAllowsDisplay
              :InputHud (Class|PlayerControllerPlay|GetMPlayHud :self player) :InputController player))
            {invoke('UI', 'ApplyGameplayVisibility', ':Visible visible')}
            (return visible))
          (:CastFailed {hide_ui} (return false))))
      (:CastFailed {hide_ui} (return false))))"""
code["PumpUI"] = f"""(fn PumpUI ()
    (bind visible (CallFunction|SyncGameplayVisibility))
    (if (not visible) (return false))
    (if (or {g('ShuttingDown')} (not {g('Ready')})) (return false))
    (if (or (not {present(g('UI'))}) (not {present(g('Hotkey'))})) (return false))
    (bind capturing {invoke('UI', 'IsCapturing')})
    (if capturing (return true))
    (bind player (Game|GetPlayerController :PlayerIndex 0))
    (bind pressed {invoke('Hotkey', 'PollKey', ':Player player')})
    (if pressed {invoke('UI', 'ToggleButton')}) (return true))"""
code["MeasureUI"] = f"""(fn MeasureUI ()
    (if (not {present(g('Controller'))}) (return false))
    (if (not (Class|BPWorkerOptimizer|GetMeasurePerformance :self {g('Controller')})) (return false))
    (bind metrics (Class|BPWorkerOptimizer|GetMetrics :self {g('Controller')}))
    (if (not {present('metrics')}) (return false))
    (bind (startSeconds startFraction) (Class|BPWorkerOptimizer|ReadClockParts :self {g('Controller')}))
    {put('PerformanceUISeconds', 'startSeconds')} {put('PerformanceUIFraction', 'startFraction')}
    {put('PerformanceUIPhase', f'(select (Class|BPWorkerOptimizer|GetRunActive :self {g("Controller")}) 11 10)')}
    (bind pumped (CallFunction|PumpUI))
    (bind (endSeconds endFraction) (Class|BPWorkerOptimizer|ReadClockParts :self {g('Controller')}))
    (bind uiSeconds (Class|BPPerformanceMetrics|ElapsedSeconds :self metrics
      :StartSeconds {g('PerformanceUISeconds')} :StartFraction {g('PerformanceUIFraction')}
      :EndSeconds endSeconds :EndFraction endFraction))
    (Class|BPPerformanceMetrics|RecordSample :self metrics :Phase {g('PerformanceUIPhase')} :Seconds uiSeconds)
    (if {g('HasPerformancePrevious')}
      (bind frameSeconds (Class|BPPerformanceMetrics|ElapsedSeconds :self metrics
        :StartSeconds {g('PerformancePreviousSeconds')} :StartFraction {g('PerformancePreviousFraction')}
        :EndSeconds {g('PerformanceUISeconds')} :EndFraction {g('PerformanceUIFraction')}))
      (Class|BPPerformanceMetrics|RecordSample :self metrics :Phase 9 :Seconds frameSeconds))
    {put('PerformancePreviousSeconds', g('PerformanceUISeconds'))}
    {put('PerformancePreviousFraction', g('PerformanceUIFraction'))} {put('HasPerformancePrevious', 'true')}
    (return pumped))"""
code["ReleaseSession"] = f"""(fn ReleaseSession ()
    {put('Ready', 'false')} {put('HasPerformancePrevious', 'false')}
    (if {present(g('UI'))} {invoke('UI', 'ShutdownUI')} (Widget|RemovefromParent :self {g('UI')}))
    (Variables|Default|SetUI) (Variables|Default|SetHotkey)
    (if {present(g('Controller'))}
      (if (== (Actor|GetOwner :self {g('Controller')}) self)
        {invoke('Controller', 'Shutdown')}))
    (if {present(g('Logbook'))}
      (bind flushed {invoke('Logbook','CloseStorage')})
      (if (and (not flushed) {present(g('API'))})
        (Class|ModAPI|LogMessage :self {g('API')} :Msg "Worker Optimizer history: history_unflushed" :doPrependDate true)))
    (if {present(g('Controller'))}
      (if (== (Actor|GetOwner :self {g('Controller')}) self) (Actor|DestroyActor :self {g('Controller')})))
    (if {present(g('Bridge'))}
      (if (== (Actor|GetOwner :self {g('Bridge')}) self) (Actor|DestroyActor :self {g('Bridge')})))
    (if {present(g('ActionView'))} (Widget|RemovefromParent :self {g('ActionView')}))
    (Variables|Default|SetController) (Variables|Default|SetBridge) (Variables|Default|SetActionView)
    (return true))"""
code["Shutdown"] = f"""(fn Shutdown ()
    (if {g('ShuttingDown')} (return true))
    {put('ShuttingDown', 'true')}
    (if (and {g('Bound')} {present(g('API'))}) (CallFunction|UnbindLoading) (CallFunction|UnbindDay))
    {put('Bound', 'false')} {put('Primary', 'false')}
    (CallFunction|ReleaseSession) (Variables|Default|SetAPI) (return true))"""
if MANUAL_ONLY:
    code["AttachAPI"] = code["AttachAPI"].replace(" (CallFunction|BindDay)", "")
    code["OnDayStart"] = "(fn OnDayStart (day) (return))"
    code["PollAutomatic"] = "(fn PollAutomatic () (return false))"
    code["PumpLifecycle"] = code["PumpLifecycle"].replace("(CallFunction|PollAutomatic)", "")
    code["PumpUI"] = f"""(fn PumpUI ()
        (CallFunction|SyncGameplayVisibility)
        (if (or {g('ShuttingDown')} (not {g('Ready')})) (return false))
        (bind available {present(g('UI'))}) (return available))"""


def clear_generated_body(graph):
    # Preserve signatures while discarding the old parameter-connected body.
    result_kept = False
    for node in BP.find_nodes(graph):
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


for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        if name in ("BindLoading", "UnbindLoading", "BindDay", "UnbindDay"):
            continue
        unreal.log("WO_LIFECYCLE_WRITE " + name)
        clear_generated_body(graphs[name])
        BP.write_graph_dsl(graphs[name], source)
        if name in ("PumpLifecycle", "SyncGameplayVisibility"):
            # The DSL caches wildcard pin types. Set the enum constant only after
            # connecting the typed phase input, rather than wiring a string literal.
            comparisons = [n for n in BP.get_node_infos(BP.find_nodes(graphs[name]))
                           if n.type_id == "Utilities|Enum|Equal(Enum)"]
            assert len(comparisons) == 1
            BP.set_pin_value(next(p.pin_id for p in comparisons[0].input_pins if p.name == "B"), "DONE")
    # Both delegates reference the same void function; never unbind all listeners.
    for function, node_type in (("BindLoading", "EventDispatchers|BindEventtoOnLoadingFinished"),
                                ("UnbindLoading", "EventDispatchers|UnbindEventfromOnLoadingFinished"),
                                ("BindDay", "EventDispatchers|BindEventtoOnDayStart"),
                                ("UnbindDay", "EventDispatchers|UnbindEventfromOnDayStart")):
        graph = graphs[function]
        clear_generated_body(graph)
        # The regular writer compiles immediately. Wire the required delegate first.
        blueprint_dsl.Transpiler(
            graph, BP.create_node, BP.connect_pins, BP._get_node_info,
            BP.set_pin_value, lambda g: BP.find_nodes(g),
            delete_node_fn=BP.delete_node,
            find_node_types_fn=lambda f: BP.find_node_types(graph, f),
        ).transpile(code[function])
        targets = [n for n in BP.get_node_infos(BP.find_nodes(graph)) if any(p.name == "Delegate" for p in n.input_pins)]
        assert len(targets) == 1, (function, [n.type_id for n in targets])
        target = targets[0]
        create = BP.create_node(graph, "EventDispatchers|CreateEvent", unreal.IntPoint(0, 200))
        info = BP.get_node_infos([create])[0]
        BP.connect_pins(next(p.pin_id for p in info.output_pins if p.name == "OutputDelegate"),
                        next(p.pin_id for p in target.input_pins if p.name == "Delegate"))
        BP.set_create_event_function(create, "OnDayStart" if function in ("BindDay", "UnbindDay") else "OnLoaded")
    BP.write_graph_dsl(BP.get_graph(bp, "EventGraph"), """
      (event EventBeginPlay () (CallFunction|BeginLifecycle))
      (event EventTick (DeltaSeconds) (CallFunction|PumpLifecycle))
      (event EventEndPlay (EndPlayReason) (CallFunction|Shutdown))
    """)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property("hidden", True)
    tick = cdo.get_editor_property("primary_actor_tick")
    tick.set_editor_property("start_with_tick_enabled", True)
    tick.set_editor_property("tick_even_when_paused", True)
    cdo.set_editor_property("primary_actor_tick", tick, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Lifecycle.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_LIFECYCLE_GENERATED")
exec(Path(__file__).with_name("test_lifecycle.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_ui_lifecycle.py").read_text(encoding="utf-8"))
