"""Generate namespaced native settings with runtime building/category inheritance."""

from pathlib import Path
import json

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_PrioritySettings")
if bp is None:
    bp = BP.create(ROOT, "BP_PrioritySettings", unreal.Object.static_class())
if "OptionValues" not in BP.list_variables(bp):
    BP.add_variable(bp, "OptionValues", "string", container_type=ContainerType.ARRAY)
for name in ("RegisteredCategories", "RegisteredTypes"):
    if name not in BP.list_variables(bp):
        BP.add_variable(bp, name, "name", container_type=ContainerType.ARRAY)
catalog = json.loads(Path(__file__).with_name("translations.json").read_text(encoding="utf-8"))
languages, translations = catalog["languages"], catalog["strings"]
# Native setting widgets keep localization keys live when the player changes language.
for key, row in list(translations.items()):
    if key in ("mode", "reserve"):
        translations["title." + key] = ["Worker Optimizer: " + value for value in row]
    elif key.startswith("category."):
        translations["title." + key] = ["Worker Optimizer: " + translations["category"][i] + " - " + value for i, value in enumerate(row)]
assert languages == ["en", "de", "pl", "fr", "nl"]
assert all(len(row) == 5 and all(isinstance(text, str) and text for text in row) for row in translations.values())
for name in ("TextKeys", "TextValues", "Languages"):
    if name not in BP.list_variables(bp):
        BP.add_variable(bp, name, "string", container_type=ContainerType.ARRAY)
if "TranslationMap" not in BP.list_variables(bp):
    kind = unreal.BlueprintEditorLibrary.get_map_type(unreal.BlueprintEditorLibrary.get_basic_type_by_name("name"), unreal.BlueprintEditorLibrary.get_basic_type_by_name("string"))
    assert unreal.BlueprintEditorLibrary.add_member_variable(bp, "TranslationMap", kind)

obj = unreal.Object.static_class()
definitions = {
    "HasObject": ([("Object", obj)], [("Result", "bool")]),
    "ParsePriority": ([("Value", "string"), ("AllowInherit", "bool")], [("Valid", "bool"), ("Priority", "int")]),
    "ResolvePriority": ([("CategoryValue", "string"), ("TypeValue", "string")], [("Priority", "int")]),
    "IsStrictValue": ([("Value", "string")], [("Strict", "bool")]),
    "CategoryOptionId": ([("Key", "name")], [("OptionId", "string")]),
    "TypeOptionId": ([("Key", "name")], [("OptionId", "string")]),
    "CategoryLabelKey": ([("Key", "name")], [("LabelKey", "string")]),
    "ResolveLabel": ([("Key", "name"), ("StringKey", "string")], [("Label", "string")]),
    "EnsureDefinitionOptions": ([("Context", obj), ("Type", "name"), ("Category", "name"), ("StringKey", "string")], [("Result", "bool")]),
    "PrepareValues": ([("IncludeInherit", "bool")], [("Result", "bool")]),
    "RegisterGeneral": ([("Context", obj)], [("Result", "bool")]),
    "RegisterCategory": ([("Context", obj), ("Category", "name"), ("Label", "string")], [("Result", "bool")]),
    "RegisterType": ([("Context", obj), ("Type", "name"), ("Label", "string")], [("Result", "bool")]),
    "ReadPriority": ([("Context", obj), ("Category", "name"), ("Type", "name")], [("Priority", "int")]),
    "ReadStrictMode": ([("Context", obj)], [("Strict", "bool")]),
    "Localize": ([("Key", "string"), ("Language", "string")], [("Text", "string")]),
    "Text": ([("Key", "string")], [("Text", "string")]),
    "RegisterStrings": ([("Context", obj)], [("Result", "bool")]),
    "MigrateOption": ([("Context", obj), ("OptionId", "string"), ("Mode", "bool"), ("AllowInherit", "bool")], [("Result", "bool")]),
    "ParseReserve": ([("Value", "string")], [("Count", "int")]),
    "ReadReserve": ([("Context", obj)], [("Count", "int")]),
}
graphs = {}
existing = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, (inputs, outputs) in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing else BP.add_function_graph(bp, name)
    if name not in existing:
        for param, kind in inputs:
            if isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        for param, kind in outputs:
            BP.add_function_param(graphs[name], param, kind, False)
BP.compile_blueprint(bp)
nodes = BP.find_node_types(graphs["RegisterGeneral"], "", [])


def node(name):
    found = [n for n in nodes if n.endswith("|" + name)]
    assert len(found) == 1, (name, found)
    return found[0]


def concat(a, b):
    return f"(Utilities|String|Append :A {a} :B {b})"


values = "(Variables|Default|GetOptionValues)"
register = node("RegisterModOptions")
read = node("ReadModOptionValue")
get_api = "Class|ModAPI|GetModAPI"


def api_guard(fallback):
    return f"""(bind api ({get_api} :WorldContext Context))
      (if (not (CallFunction|HasObject :Object api)) (return {fallback}))"""


code = {}
def arr(name):
    return f"(Variables|Default|Get{name})"

def item(name, index):
    return f'(Utilities|Array|Get(acopy) :Array {arr(name)} :"Dimension 1" {index})'

def text(key):
    return f'(CallFunction|Text :Key "{key}")'

def literal(value):
    return json.dumps(value, ensure_ascii=False)

code["Localize"] = f"""(fn Localize (Key Language)
    (bind index (Utilities|Array|FindItem {arr('TextKeys')} Key))
    (if (< index 0) (return Key))
    (bind normalized (Utilities|String|ToLower Language))
    {''.join(f'(if (or (Utilities|String|EqualExactly(String) normalized "{lang}") (or (Utilities|String|StartsWith :SourceString normalized :InPrefix "{lang}-") (Utilities|String|StartsWith :SourceString normalized :InPrefix "{lang}_"))) (return {item("TextValues", f"(+ (* index 5) {i})")}))' for i, lang in enumerate(languages))}
    (return {item('TextValues', '(* index 5)')}))"""
code["Text"] = """(fn Text (Key)
    (bind manager (Class|Backbone|GetLocManager :WorldContext self))
    (if (CallFunction|HasObject :Object manager)
      (bind language (Utilities|String|ToString(Name) (Class|LocManager|GetActiveLanguage :self manager)))
      (bind translated (CallFunction|Localize :Key Key :Language language)) (return translated))
    (bind fallback (CallFunction|Localize :Key Key :Language "en")) (return fallback))"""
code["RegisterStrings"] = f"""(fn RegisterStrings (Context)
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    {api_guard('false')}
    (bind available (Class|ModAPI|ListLanguageIds :self api :WorldContext Context))
    (for language available
      (Utilities|Map|Clear {arr('TranslationMap')})
      (for i (range (Utilities|Array|Length {arr('TextKeys')}))
        (bind key {item('TextKeys', 'i')})
        (bind translated (CallFunction|Localize :Key key :Language (Utilities|String|ToString(Name) language)))
        (Utilities|Map|Add {arr('TranslationMap')} ({node('StringToName')} (Utilities|String|Append :A "WorkerOptimizer.ui." :B key)) translated))
      (bind added (Class|ModAPI|AddNewStrings :self api :WorldContext Context :langId language :idStringPairs {arr('TranslationMap')}))
      (if (not added) (return false)))
    (return true))"""
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["ParsePriority"] = """(fn ParsePriority (Value AllowInherit)
    """ + "\n".join(
        f'(if (and {"AllowInherit" if value == -1 else "true"} (Utilities|String|EqualExactly(String) Value {literal(label)})) (return true {value}))'
        for key, value in [("inherit", -1)] + [(f"priority.{i}", i) for i in range(5)]
        for label in dict.fromkeys(["inherit" if value == -1 else str(value), "WorkerOptimizer.ui." + key] + translations[key])
    ) + "\n(return false 2))"
code["ResolvePriority"] = """(fn ResolvePriority (CategoryValue TypeValue)
    (bind (typeOK typePriority) (CallFunction|ParsePriority :Value TypeValue :AllowInherit true))
    (if (and typeOK (>= typePriority 0)) (return typePriority))
    (bind (categoryOK categoryPriority) (CallFunction|ParsePriority :Value CategoryValue :AllowInherit false))
    (if categoryOK (return categoryPriority))
    (return 2))"""
code["IsStrictValue"] = "(fn IsStrictValue (Value) " + " ".join(f'(if (Utilities|String|EqualExactly(String) Value {literal(label)}) (return false))' for label in ["Weighted", "WorkerOptimizer.ui.weighted"] + translations["weighted"]) + " (return true))"
code["CategoryLabelKey"] = """(fn CategoryLabelKey (Key)
    (return (Utilities|String|Append :A "toolbar." :B (Utilities|String|ToString(Name) Key))))"""
code["ResolveLabel"] = """(fn ResolveLabel (Key StringKey)
    (if (not (Utilities|String|EqualExactly(String) StringKey ""))
      (if (Class|LocManager|HasKey :Key StringKey)
        (bind translated (Class|LocManager|GetWordfromKey :Key StringKey))
        (if (not (Utilities|String|EqualExactly(String) translated "")) (return translated))))
    (bind categoryKey (Utilities|String|Append :A "category." :B (Utilities|String|ToLower (Utilities|String|ToString(Name) Key))))
    (if (Utilities|Array|ContainsItem (Variables|Default|GetTextKeys) categoryKey)
      (bind category (CallFunction|Text :Key categoryKey)) (return category))
    (return (Utilities|String|ToString(Name) Key)))"""
for kind in ("Category", "Type"):
    # IDs use engine names. Display labels never participate in persistence keys.
    code[kind + "OptionId"] = f"""(fn {kind}OptionId (Key)
      (bind nameString ({node('ToString(Name)')} Key))
      (return {concat('"WorkerOptimizer.' + kind.lower() + '."', 'nameString')}))"""
code["PrepareValues"] = f"""(fn PrepareValues (IncludeInherit)
    (Utilities|Array|Clear {values})
    (if IncludeInherit (Utilities|Array|Add {values} "WorkerOptimizer.ui.inherit"))
    {' '.join(f'(Utilities|Array|Add {values} "WorkerOptimizer.ui.priority.{i}")' for i in range(5))}
    (return true))"""
code["MigrateOption"] = f"""(fn MigrateOption (Context OptionId Mode AllowInherit)
    {api_guard('false')}
    (bind value ({read} :self api :WorldContext Context :optionId OptionId :fallbackValue ""))
    (if (Utilities|String|EqualExactly(String) value "") (return true))
    (if (Utilities|String|StartsWith :SourceString value :InPrefix "WorkerOptimizer.ui.") (return true))
    (bind manager (Class|Backbone|GetOptionManager :WorldContext Context))
    (if (not (CallFunction|HasObject :Object manager)) (return false))
    (if Mode
      (bind strict (CallFunction|IsStrictValue :Value value))
      (Class|OptionManager|SetValue :self manager :optionId OptionId :Value (select strict "WorkerOptimizer.ui.strict" "WorkerOptimizer.ui.weighted"))
      (return true))
    (bind (valid priority) (CallFunction|ParsePriority :Value value :AllowInherit AllowInherit))
    (if (not valid) (return true))
    (if (< priority 0) (Class|OptionManager|SetValue :self manager :optionId OptionId :Value "WorkerOptimizer.ui.inherit") (return true))
    (Class|OptionManager|SetValue :self manager :optionId OptionId :Value (Utilities|String|Append :A "WorkerOptimizer.ui.priority." :B (Utilities|String|ToString(Integer) priority)))
    (return true))"""
code["ParseReserve"] = """(fn ParseReserve (Value)
    (for number (range 101)
      (if (Utilities|String|EqualExactly(String) Value (Utilities|String|ToString(Integer) number)) (return number)))
    (return 1))"""
code["ReadReserve"] = f"""(fn ReadReserve (Context)
    (if (not (CallFunction|HasObject :Object Context)) (return 1))
    {api_guard('1')}
    (bind value ({read} :self api :WorldContext Context :optionId "WorkerOptimizer.reserve" :fallbackValue "1"))
    (bind count (CallFunction|ParseReserve :Value value)) (return count))"""
code["RegisterGeneral"] = f"""(fn RegisterGeneral (Context)
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    {api_guard('false')}
    (bind strings (CallFunction|RegisterStrings :Context Context))
    (if (not strings) (return false))
    (CallFunction|MigrateOption :Context Context :OptionId "WorkerOptimizer.mode" :Mode true :AllowInherit false)
    (Utilities|Array|Clear {values})
    (Utilities|Array|Add {values} "WorkerOptimizer.ui.strict") (Utilities|Array|Add {values} "WorkerOptimizer.ui.weighted")
    (bind registered ({register} :self api :WorldContext Context :optionId "WorkerOptimizer.mode"
      :optionDisplayName "WorkerOptimizer.ui.title.mode" :Values {values} :DefaultValue "WorkerOptimizer.ui.strict" :optionDescription "WorkerOptimizer.ui.mode_desc"))
    (if (not registered) (return false))
    (Utilities|Array|Clear {values})
    (for i (range 101) (Utilities|Array|Add {values} (Utilities|String|ToString(Integer) i)))
    (bind reserve ({register} :self api :WorldContext Context :optionId "WorkerOptimizer.reserve"
      :optionDisplayName "WorkerOptimizer.ui.title.reserve" :Values {values} :DefaultValue "1" :optionDescription "WorkerOptimizer.ui.reserve_desc"))
    (return reserve))"""
for kind in ("Category", "Type"):
    param = kind
    title = 'Label'
    if kind == 'Category':
        title = '(select (Utilities|Array|ContainsItem (Variables|Default|GetTextKeys) (Utilities|String|Append :A "title.category." :B (Utilities|String|ToLower (Utilities|String|ToString(Name) Category)))) (Utilities|String|Append :A "WorkerOptimizer.ui.title.category." :B (Utilities|String|ToLower (Utilities|String|ToString(Name) Category))) Label)'
    code["Register" + kind] = f"""(fn Register{kind} (Context {param} Label)
      (if (not (CallFunction|HasObject :Object Context)) (return false))
      (if (== {param} "None") (return false))
      {api_guard('false')}
      (CallFunction|PrepareValues :IncludeInherit {'true' if kind == 'Type' else 'false'})
      (bind key (CallFunction|{kind}OptionId :Key {param}))
      (CallFunction|MigrateOption :Context Context :OptionId key :Mode false :AllowInherit {'true' if kind == 'Type' else 'false'})
      (bind label {title})
      (bind registered ({register} :self api :WorldContext Context :optionId key :optionDisplayName label
        :Values {values} :DefaultValue "WorkerOptimizer.ui.{'inherit' if kind == 'Type' else 'priority.2'}" :optionDescription "WorkerOptimizer.ui.{kind.lower()}_desc"))
      (if registered (Utilities|Array|AddUnique (Variables|Default|GetRegistered{'Categories' if kind == 'Category' else 'Types'}) {param}))
      (return registered))"""
code["EnsureDefinitionOptions"] = """(fn EnsureDefinitionOptions (Context Type Category StringKey)
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    (if (== Type "None") (return false))
    (if (and (!= Category "None") (not (Utilities|Array|ContainsItem (Variables|Default|GetRegisteredCategories) Category)))
      (bind categoryLabel (CallFunction|ResolveLabel :Key Category :StringKey (CallFunction|CategoryLabelKey :Key Category)))
      (bind categoryReady (CallFunction|RegisterCategory :Context Context :Category Category :Label categoryLabel))
      (if (not categoryReady) (return false)))
    (if (Utilities|Array|ContainsItem (Variables|Default|GetRegisteredTypes) Type) (return true))
    (bind typeLabel (select (Class|LocManager|HasKey :Key StringKey) StringKey (Utilities|String|ToString(Name) Type)))
    (bind typeReady (CallFunction|RegisterType :Context Context :Type Type :Label typeLabel))
    (return typeReady))"""
code["ReadPriority"] = f"""(fn ReadPriority (Context Category Type)
    (if (not (CallFunction|HasObject :Object Context)) (return 2))
    {api_guard('2')}
    (bind categoryKey (CallFunction|CategoryOptionId :Key Category))
    (bind typeKey (CallFunction|TypeOptionId :Key Type))
    (bind categoryValue ({read} :self api :WorldContext Context :optionId categoryKey :fallbackValue "2"))
    (bind typeValue ({read} :self api :WorldContext Context :optionId typeKey :fallbackValue "inherit"))
    (bind priority (CallFunction|ResolvePriority :CategoryValue categoryValue :TypeValue typeValue))
    (return priority))"""
code["ReadStrictMode"] = f"""(fn ReadStrictMode (Context)
    (if (not (CallFunction|HasObject :Object Context)) (return true))
    {api_guard('true')}
    (bind value ({read} :self api :WorldContext Context :optionId "WorkerOptimizer.mode" :fallbackValue "Strict"))
    (bind strict (CallFunction|IsStrictValue :Value value))
    (return strict))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_PRIORITY_SETTINGS_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    defaults = unreal.get_default_object(bp.generated_class())
    defaults.set_editor_property("TextKeys", list(translations))
    defaults.set_editor_property("TextValues", [value for row in translations.values() for value in row])
    defaults.set_editor_property("Languages", languages)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-PrioritySettings.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_PRIORITY_SETTINGS_GENERATED")
exec(Path(__file__).with_name("test_priority_settings.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_localization.py").read_text(encoding="utf-8"))
