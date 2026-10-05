"""Generate incremental runtime discovery of building option metadata."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_DefinitionCatalog")
if bp is None:
    bp = BP.create(ROOT, "BP_DefinitionCatalog", unreal.Object.static_class())
existing = set(BP.list_variables(bp))
if "SourceTable" not in existing:
    BP.add_object_variable(bp, "SourceTable", unreal.DataTable.static_class())
for kind, names in {"bool": "CatalogActive CatalogDone CatalogSucceeded", "int": "Cursor",
                    "name[]": "SourceNames Types Categories", "string[]": "StringKeys"}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
row_struct = unreal.load_object(None, "/Script/ProjectArco.GridActorDefinition_MasterSyncFormat")
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "ResetCatalog": [],
    "FailCatalog": [],
    "BeginTable": [("Table", unreal.DataTable.static_class())],
    "BeginFromContext": [("Context", unreal.Object.static_class())],
    "AddDefinition": [("TypeKey", "name"), ("Definition", row_struct), ("LiveWorkplace", "bool")],
    "AdvanceCatalog": [],
}
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            elif kind == row_struct:
                BP.add_struct_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
get_path = next(n for n in BP.find_node_types(graphs["BeginTable"], "", []) if n.endswith("|GetObjectPathString"))


def g(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def at(name, index):
    return f'(Utilities|Array|Get(acopy) :Array {g(name)} :"Dimension 1" {index})'


def unpack(value):
    node = "Utilities|Struct|BreakGridActorDefinitionMasterSyncFormat"
    pins = BP.get_node_type_pins(graphs["AddDefinition"], node).output_pins
    return f"(bind ({' '.join('d_' + str(p.name) for p in pins)}) ({node} {value}))"


code = {}
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["ResetCatalog"] = f"""(fn ResetCatalog ()
    {put('CatalogActive', 'false')} {put('CatalogDone', 'true')} {put('CatalogSucceeded', 'false')}
    {put('Cursor', '0')}
    {' '.join(f'(Utilities|Array|Clear {g(n)})' for n in ('SourceNames', 'Types', 'Categories', 'StringKeys'))}
    (return true))"""
code["FailCatalog"] = """(fn FailCatalog () (CallFunction|ResetCatalog) (return false))"""
code["BeginTable"] = f"""(fn BeginTable (Table)
    (CallFunction|ResetCatalog)
    (if (not (CallFunction|HasObject :Object Table)) (return false))
    (bind schema (DataTable|GetDataTableRowStruct :Table Table))
    (if (not (CallFunction|HasObject :Object schema)) (return false))
    (bind schemaPath ({get_path} :Object schema))
    (if (not (Utilities|String|EqualExactly(String) schemaPath "/Script/ProjectArco.GridActorDefinition_MasterSyncFormat")) (return false))
    {put('SourceTable', 'Table')}
    (bind names (DataTable|GetDataTableRowNames :Table Table))
    (if (> (Utilities|Array|Length names) 10000) (return false))
    {put('SourceNames', 'names')} {put('CatalogActive', 'true')} {put('CatalogDone', 'false')}
    (return true))"""
code["BeginFromContext"] = f"""(fn BeginFromContext (Context)
    (CallFunction|ResetCatalog)
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    (bind instance (Game|GetGameInstance :WorldContextObject Context))
    (bind game (Utilities|Casting|CastToArcoGameInstance :Object instance)
      (:CastFailed (return false))
      (:then
        (bind table (Class|ArcoGameInstance|GetMGridActorLookup :self game))
        (bind started (CallFunction|BeginTable :Table table)) (return started))))"""
code["AddDefinition"] = f"""(fn AddDefinition (TypeKey Definition LiveWorkplace)
    (if (== TypeKey "None") (return false))
    (if (Utilities|Array|ContainsItem {g('Types')} TypeKey) (return true))
    {unpack('Definition')}
    (if (and (not LiveWorkplace) (or (<= d_maxAgents_contextual 0) (> d_asHouseTier 0))) (return true))
    (Utilities|Array|Add {g('Types')} TypeKey)
    (Utilities|Array|Add {g('Categories')} d_toolbarGroup)
    (Utilities|Array|Add {g('StringKeys')} d_stringKey)
    (return true))"""
code["AdvanceCatalog"] = f"""(fn AdvanceCatalog ()
    (if (not {g('CatalogActive')}) (return false))
    (if (not (CallFunction|HasObject :Object {g('SourceTable')})) (CallFunction|FailCatalog) (return false))
    (if (>= {g('Cursor')} (Utilities|Array|Length {g('SourceNames')}))
      {put('CatalogActive', 'false')} {put('CatalogDone', 'true')} {put('CatalogSucceeded', 'true')} (return true))
    (bind key {at('SourceNames', g('Cursor'))})
    (bind definition (Utilities|GetDataTableRow :DataTable {g('SourceTable')} :RowName key)
      (:RowNotFound (CallFunction|FailCatalog) (return false))
      (:then
        (bind added (CallFunction|AddDefinition :TypeKey key :Definition definition :LiveWorkplace false))
        (if (not added) (CallFunction|FailCatalog) (return false))
        {put('Cursor', f'(+ {g("Cursor")} 1)')} (return true))))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_DEFINITION_CATALOG_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-DefinitionCatalog.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_DEFINITION_CATALOG_GENERATED")
exec(Path(__file__).with_name("test_definition_catalog.py").read_text(encoding="utf-8"))
