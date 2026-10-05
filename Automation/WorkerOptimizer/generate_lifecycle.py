"""Generate native load-finished binding and per-world session ownership."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
api_class = unreal.load_class(None, "/Script/SystemCore.ModAPI")
bp = unreal.load_asset(ROOT + "/BP_MapLoad")
if bp is None:
    bp = BP.create(ROOT, "BP_MapLoad", unreal.Actor.static_class())
refs = {"Controller": "BP_WorkerOptimizer", "Bridge": "BP_ActionBridge", "ActionView": "WBP_ActionContext", "UI": "WBP_WorkerOptimizer", "Hotkey": "BP_HotkeyConfig"}
existing = set(BP.list_variables(bp))
for name, cls in [(name, load(asset)) for name, asset in refs.items()] + [("API", api_class)]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {"bool": "Primary Bound Loaded Ready ShuttingDown", "name": "FailureCode"}.items():
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
    "PumpUI": [],
}
void_functions = {"BindLoading", "UnbindLoading", "OnLoaded"}
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
        if name not in void_functions:
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
    {put('API', 'InputAPI')} (CallFunction|BindLoading) {put('Bound', 'true')}
    {trace('bound')} (return true))"""
code["BindLoading"] = f"""(fn BindLoading ()
    (EventDispatchers|BindEventtoOnLoadingFinished :self {g('API')}))"""
code["UnbindLoading"] = f"""(fn UnbindLoading ()
    (EventDispatchers|UnbindEventfromOnLoadingFinished :self {g('API')}))"""
code["OnLoaded"] = f"""(fn OnLoaded ()
    (if {present(g('API'))} {trace('loading_finished')})
    (if (or {g('ShuttingDown')} (or (not {g('Bound')}) (not {g('Primary')}))) (return))
    (if {g('Loaded')} (return))
    {put('Loaded', 'true')}
    (CallFunction|CreateSession))"""
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
    ({add_viewport} :self widget :ZOrder 30)
    {trace('ui_added')} (return true))"""
code["PumpUI"] = f"""(fn PumpUI ()
    (if (or {g('ShuttingDown')} (not {g('Ready')})) (return false))
    (if (or (not {present(g('UI'))}) (not {present(g('Hotkey'))})) (return false))
    {invoke('UI', 'RefreshUI')}
    (bind capturing {invoke('UI', 'IsCapturing')})
    (if capturing (return true))
    (bind player (Game|GetPlayerController :PlayerIndex 0))
    (bind pressed {invoke('Hotkey', 'PollKey', ':Player player')})
    (if pressed {invoke('UI', 'ToggleButton')}) (return true))"""
code["ReleaseSession"] = f"""(fn ReleaseSession ()
    {put('Ready', 'false')}
    (if {present(g('UI'))} {invoke('UI', 'ShutdownUI')} (Widget|RemovefromParent :self {g('UI')}))
    (Variables|Default|SetUI) (Variables|Default|SetHotkey)
    (if {present(g('Controller'))}
      (if (== (Actor|GetOwner :self {g('Controller')}) self)
        {invoke('Controller', 'Shutdown')} (Actor|DestroyActor :self {g('Controller')})))
    (if {present(g('Bridge'))}
      (if (== (Actor|GetOwner :self {g('Bridge')}) self) (Actor|DestroyActor :self {g('Bridge')})))
    (if {present(g('ActionView'))} (Widget|RemovefromParent :self {g('ActionView')}))
    (Variables|Default|SetController) (Variables|Default|SetBridge) (Variables|Default|SetActionView)
    (return true))"""
code["Shutdown"] = f"""(fn Shutdown ()
    (if {g('ShuttingDown')} (return true))
    {put('ShuttingDown', 'true')}
    (if (and {g('Bound')} {present(g('API'))}) (CallFunction|UnbindLoading))
    {put('Bound', 'false')} {put('Primary', 'false')}
    (CallFunction|ReleaseSession) (Variables|Default|SetAPI) (return true))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        if name in ("BindLoading", "UnbindLoading"):
            continue
        unreal.log("WO_LIFECYCLE_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    # Both delegates reference the same void function; never unbind all listeners.
    for function, node_type in (("BindLoading", "EventDispatchers|BindEventtoOnLoadingFinished"),
                                ("UnbindLoading", "EventDispatchers|UnbindEventfromOnLoadingFinished")):
        graph = graphs[function]
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
        BP.set_create_event_function(create, "OnLoaded")
    BP.write_graph_dsl(BP.get_graph(bp, "EventGraph"), """
      (event EventBeginPlay () (CallFunction|BeginLifecycle))
      (event EventTick (DeltaSeconds) (CallFunction|PumpUI))
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
