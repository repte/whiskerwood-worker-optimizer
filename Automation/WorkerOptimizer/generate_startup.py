"""Generate the mod-loader startup actor and native option registration pipeline."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
bp = unreal.load_asset(ROOT + "/BP_Startup")
if bp is None:
    bp = BP.create(ROOT, "BP_Startup", unreal.Actor.static_class())
existing = set(BP.list_variables(bp))
refs = {"Catalog": "BP_DefinitionCatalog", "Settings": "BP_PrioritySettings"}
for name, cls in [(name, load(asset)) for name, asset in refs.items()] + [("Context", unreal.Object.static_class())]:
    if name not in existing:
        BP.add_object_variable(bp, name, cls)
for kind, names in {
    "bool": "Initialized StartupActive StartupDone StartupSucceeded Registering AwaitingRegistration",
    "int": "Cursor RegisteredCount", "name": "FailureCode",
    "int[]": "OptionKinds", "name[]": "OptionKeys SeenCategories", "string[]": "OptionLabelKeys",
}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "Initialize": [("InputContext", unreal.Object.static_class())],
    "BeginStartup": [("InputContext", unreal.Object.static_class())],
    "FailStartup": [("Reason", "name")], "AcceptCatalogStart": [("Started", "bool")],
    "BuildManifest": [], "PrepareRegistration": [], "RecordRegistration": [("Registered", "bool")],
    "ResolveLabel": [("Key", "name"), ("StringKey", "string")], "AdvanceStartup": [], "Pump": [], "Shutdown": [], "StartupStatus": [],
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
        returns_text = name in ("ResolveLabel", "StartupStatus")
        BP.add_function_param(graphs[name], "Label" if returns_text else "Result", "string" if returns_text else "bool", False)
BP.compile_blueprint(bp)


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def prop(ref, name):
    return f"(Class|{refs[ref].replace('_', '')}|Get{name} :self {g(ref)})"


def invoke(ref, name, args=""):
    return f"(Class|{refs[ref].replace('_', '')}|{name} :self {g(ref)} {args})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def count(array):
    return f"(Utilities|Array|Length {array})"


def fail(reason):
    return f'(CallFunction|FailStartup :Reason "{reason}") (return false)'


code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["Initialize"] = f"""(fn Initialize (InputContext)
    (if {g('Initialized')} (return (== InputContext {g('Context')})))
    (if (not (CallFunction|HasObject :Object InputContext)) (return false))
    {put('Context', 'InputContext')}
    {''.join(f'(bind new{name} (Game|ConstructObjectfromClass :Class "{ROOT}/{asset}.{asset}_C" :self self)) {put(name, "new" + name)} (if (not (CallFunction|HasObject :Object {g(name)})) (return false))' for name, asset in refs.items())}
    {put('Initialized', 'true')} (return true))"""
code["FailStartup"] = f"""(fn FailStartup (Reason)
    {put('StartupActive', 'false')} {put('StartupDone', 'true')} {put('StartupSucceeded', 'false')}
    {put('Registering', 'false')} {put('AwaitingRegistration', 'false')} {put('FailureCode', 'Reason')}
    (bind api (Class|ModAPI|GetModAPI))
    (if (CallFunction|HasObject :Object api)
      (Class|ModAPI|LogMessage :self api
        :Msg (Utilities|String|Append :A "Worker Optimizer startup: " :B (Utilities|String|ToString(Name) Reason)) :doPrependDate true))
    (return false))"""
code["BeginStartup"] = f"""(fn BeginStartup (InputContext)
    (bind ready (CallFunction|Initialize :InputContext InputContext))
    (if (not ready) (return false))
    (if {g('StartupActive')} (return true))
    (if {g('StartupDone')} (return {g('StartupSucceeded')}))
    (bind started {invoke('Catalog', 'BeginFromContext', f':Context {g("Context")}')})
    (bind accepted (CallFunction|AcceptCatalogStart :Started started)) (return accepted))"""
code["AcceptCatalogStart"] = f"""(fn AcceptCatalogStart (Started)
    (if (or (not {g('Initialized')}) (or {g('StartupActive')} {g('StartupDone')})) (return false))
    (if (or (not Started) (not {prop('Catalog', 'CatalogActive')})) {fail('catalog_unavailable')})
    {put('StartupActive', 'true')} (return true))"""
code["BuildManifest"] = f"""(fn BuildManifest ()
    (if (or (not {g('StartupActive')}) {g('Registering')}) (return false))
    (if (not {prop('Catalog', 'CatalogDone')}) (return false))
    (if (not {prop('Catalog', 'CatalogSucceeded')}) {fail('invalid_catalog')})
    (bind types {prop('Catalog', 'Types')}) (bind categories {prop('Catalog', 'Categories')})
    (bind strings {prop('Catalog', 'StringKeys')})
    (if (or (!= {count('types')} {count('categories')}) (!= {count('types')} {count('strings')})) {fail('invalid_catalog')})
    {' '.join(f'(Utilities|Array|Clear {g(n)})' for n in ('OptionKinds', 'OptionKeys', 'OptionLabelKeys', 'SeenCategories'))}
    (Utilities|Array|Add {g('OptionKinds')} 0)
    (Utilities|Array|Add {g('OptionKeys')} "None")
    (Utilities|Array|Add {g('OptionLabelKeys')} "")
    (for category categories
      (if (and (!= category "None") (not (Utilities|Array|ContainsItem {g('SeenCategories')} category)))
        (Utilities|Array|Add {g('SeenCategories')} category)
        (Utilities|Array|Add {g('OptionKinds')} 1)
        (Utilities|Array|Add {g('OptionKeys')} category)
        (Utilities|Array|Add {g('OptionLabelKeys')} (Utilities|String|Append :A "toolbar." :B (Utilities|String|ToString(Name) category)))))
    (for i (range {count('types')})
      (Utilities|Array|Add {g('OptionKinds')} 2)
      (Utilities|Array|Add {g('OptionKeys')} {at('types', 'i')})
      (Utilities|Array|Add {g('OptionLabelKeys')} {at('strings', 'i')}))
    {put('Cursor', '0')} {put('Registering', 'true')} (return true))"""
code["StartupStatus"] = f"""(fn StartupStatus ()
    (if (or (not {g('StartupDone')}) (not {g('StartupSucceeded')})) (return ""))
    (return (Utilities|String|Append :A "WorkerOptimizer: startup ready; options="
      :B (Utilities|String|ToString(Integer) {g('RegisteredCount')}))))"""
code["PrepareRegistration"] = f"""(fn PrepareRegistration ()
    (if (or (not {g('StartupActive')}) (or (not {g('Registering')}) {g('AwaitingRegistration')})) (return false))
    (if (>= {g('Cursor')} {count(g('OptionKinds'))})
      {put('StartupActive', 'false')} {put('StartupDone', 'true')} {put('StartupSucceeded', 'true')}
      {put('Registering', 'false')}
      (bind api (Class|ModAPI|GetModAPI))
      (if (CallFunction|HasObject :Object api)
        (Class|ModAPI|LogMessage :self api :Msg (CallFunction|StartupStatus) :doPrependDate true))
      (return true))
    {put('AwaitingRegistration', 'true')} (return true))"""
code["RecordRegistration"] = f"""(fn RecordRegistration (Registered)
    (if (or (not {g('StartupActive')}) (not {g('AwaitingRegistration')})) (return false))
    {put('AwaitingRegistration', 'false')}
    (if (not Registered) {fail('option_registration_failed')})
    {put('RegisteredCount', f'(+ {g("RegisteredCount")} 1)')}
    {put('Cursor', f'(+ {g("Cursor")} 1)')} (return true))"""
code["ResolveLabel"] = f"""(fn ResolveLabel (Key StringKey)
    (bind label {invoke('Settings', 'ResolveLabel', ':Key Key :StringKey StringKey')}) (return label))"""
code["AdvanceStartup"] = f"""(fn AdvanceStartup ()
    (if (not {g('StartupActive')}) (return false))
    (if (not {g('Registering')})
      (if (not {prop('Catalog', 'CatalogDone')}) {invoke('Catalog', 'AdvanceCatalog')} (return true))
      (bind built (CallFunction|BuildManifest)) (return built))
    (bind ready (CallFunction|PrepareRegistration))
    (if (not ready) (return false))
    (if {g('StartupDone')} (return true))
    (bind kind {at(g('OptionKinds'), g('Cursor'))})
    (bind key {at(g('OptionKeys'), g('Cursor'))})
    (bind label (CallFunction|ResolveLabel :Key key :StringKey {at(g('OptionLabelKeys'), g('Cursor'))}))
    (switch int kind
      (:0
        (bind registered {invoke('Settings', 'RegisterGeneral', f':Context {g("Context")}')})
        (bind accepted (CallFunction|RecordRegistration :Registered registered)) (return accepted))
      (:1
        (bind registered {invoke('Settings', 'RegisterCategory', f':Context {g("Context")} :Category key :Label label')})
        (bind accepted (CallFunction|RecordRegistration :Registered registered)) (return accepted))
      (:2
        (bind typeIndex (Utilities|Array|FindItem {prop('Catalog', 'Types')} key))
        (if (< typeIndex 0) {fail('invalid_option_type')})
        (bind registered {invoke('Settings', 'EnsureDefinitionOptions', f':Context {g("Context")} :Type key :Category {at(prop("Catalog", "Categories"), "typeIndex")} :StringKey {at(g("OptionLabelKeys"), g("Cursor"))}')})
        (bind accepted (CallFunction|RecordRegistration :Registered registered)) (return accepted))
      (:Default {fail('invalid_option_kind')})))"""
code["Pump"] = f"""(fn Pump ()
    (for step (range 64)
      (if (not {g('StartupActive')}) (break))
      (CallFunction|AdvanceStartup)) (return true))"""
code["Shutdown"] = f"""(fn Shutdown ()
    (if {g('StartupActive')} (CallFunction|FailStartup :Reason "world_ended")) (return true))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_STARTUP_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.write_graph_dsl(BP.get_graph(bp, "EventGraph"), """
      (event EventBeginPlay () (CallFunction|BeginStartup :InputContext self) (CallFunction|Pump))
      (event EventTick (DeltaSeconds) (CallFunction|Pump))
      (event EventEndPlay (EndPlayReason) (CallFunction|Shutdown))
    """)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    cdo.set_editor_property("hidden", True)
    cdo.get_editor_property("primary_actor_tick").set_editor_property("start_with_tick_enabled", True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Startup.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_STARTUP_GENERATED")
exec(Path(__file__).with_name("test_startup.py").read_text(encoding="utf-8"))
