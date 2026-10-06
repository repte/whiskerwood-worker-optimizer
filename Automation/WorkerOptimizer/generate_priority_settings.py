"""Generate namespaced native settings with runtime building/category inheritance."""

from pathlib import Path
import json
import os

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
MANUAL_ONLY = True
bp = unreal.load_asset(ROOT + "/BP_PrioritySettings")
if bp is None:
    bp = BP.create(ROOT, "BP_PrioritySettings", unreal.Object.static_class())
if "OptionValues" not in BP.list_variables(bp):
    BP.add_variable(bp, "OptionValues", "string", container_type=ContainerType.ARRAY)
for name in ("RegisteredCategories", "RegisteredTypes"):
    if name not in BP.list_variables(bp):
        BP.add_variable(bp, name, "name", container_type=ContainerType.ARRAY)
for kind, names in {"name[]": "KnownCategories KnownTypes KnownTypeCategories FrozenCategories FrozenTypes", "string[]": "KnownTypeStringKeys", "int[]": "FrozenCategoryValues FrozenTypeValues", "bool": "PolicyKeysReady PolicyFrozen FrozenStrict", "int": "FrozenReserve"}.items():
    for name in names.split():
        if name not in BP.list_variables(bp):
            BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
catalog = json.loads(Path(__file__).with_name("translations.json").read_text(encoding="utf-8"))
languages, translations = catalog["languages"], catalog["strings"]
ui_catalog = json.loads(Path(__file__).with_name("ui_translations.json").read_text(encoding="utf-8"))
assert ui_catalog["languages"] == languages
translations.update(ui_catalog["strings"])
# Native setting widgets keep localization keys live when the player changes language.
for key, row in list(translations.items()):
    if key in ("mode", "reserve", "auto_assignment"):
        translations["title." + key] = ["Worker Optimizer: " + value for value in row]
    elif key.startswith("category."):
        translations["title." + key] = ["Worker Optimizer: " + translations["category"][i] + " - " + value for i, value in enumerate(row)]
assert languages == json.loads(Path(__file__).with_name("game_languages.json").read_text(encoding="utf-8"))["languages"]
stride = len(languages)
assert stride == 17
assert all(len(row) == stride and all(isinstance(text, str) and text.strip() for text in row) for row in translations.values())
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
    "ReadOption": ([("Context", obj), ("OptionId", "string"), ("Fallback", "string")], [("Value", "string")]),
    "WriteOption": ([("Context", obj), ("OptionId", "string"), ("Value", "string")], [("Result", "bool")]),
    "BeginPolicyKeys": ([], [("Result", "bool")]),
    "AddPolicyKey": ([("Type", "name"), ("Category", "name")], [("Result", "bool")]),
    "FinishPolicyKeys": ([], [("Result", "bool")]),
    "CapturePolicy": ([("Context", obj)], [("Result", "bool")]),
    "ReleasePolicy": ([], [("Result", "bool")]),
    "ParseAutoMode": ([("Value", "string")], [("Mode", "name")]),
    "ReadAutoMode": ([("Context", obj)], [("Mode", "name")]),
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


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


code["ReadOption"] = f"""(fn ReadOption (Context OptionId Fallback)
    (if (not (CallFunction|HasObject :Object Context)) (return Fallback))
    {api_guard('Fallback')}
    (bind value ({read} :self api :WorldContext Context :optionId OptionId :fallbackValue Fallback))
    (return value))"""
code["BeginPolicyKeys"] = f"""(fn BeginPolicyKeys ()
    (if {arr('PolicyFrozen')} (return false))
    {put('PolicyKeysReady', 'false')}
    (Utilities|Array|Clear {arr('KnownCategories')}) (Utilities|Array|Clear {arr('KnownTypes')})
    (Utilities|Array|Clear {arr('KnownTypeCategories')}) (Utilities|Array|Clear {arr('KnownTypeStringKeys')}) (return true))"""
code["WriteOption"] = """(fn WriteOption (Context OptionId Value)
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    (if (not (Utilities|String|StartsWith :SourceString OptionId :InPrefix "WorkerOptimizer.")) (return false))
    (bind manager (Class|Backbone|GetOptionManager :WorldContext Context))
    (if (not (CallFunction|HasObject :Object manager)) (return false))
    (Class|OptionManager|SetValue :self manager :optionId OptionId :Value Value)
    (bind actual (CallFunction|ReadOption :Context Context :OptionId OptionId :Fallback ""))
    (return (Utilities|String|EqualExactly(String) actual Value)))"""
code["AddPolicyKey"] = f"""(fn AddPolicyKey (Type Category)
    (if (== Type "None") (return false))
    (if (>= (Utilities|Array|Length {arr('KnownTypes')}) 10000)
        (if (not (Utilities|Array|ContainsItem {arr('KnownTypes')} Type)) (return false)))
    (if (and (!= Category "None") (>= (Utilities|Array|Length {arr('KnownCategories')}) 10000))
        (if (not (Utilities|Array|ContainsItem {arr('KnownCategories')} Category)) (return false)))
    (if (not (Utilities|Array|ContainsItem {arr('KnownTypes')} Type))
      (Utilities|Array|Add {arr('KnownTypes')} Type)
      (Utilities|Array|Add {arr('KnownTypeCategories')} Category)
      (Utilities|Array|Add {arr('KnownTypeStringKeys')} (Utilities|String|ToString(Name) Type)))
    (if (!= Category "None") (Utilities|Array|AddUnique {arr('KnownCategories')} Category)) (return true))"""
code["FinishPolicyKeys"] = f"""(fn FinishPolicyKeys () {put('PolicyKeysReady', 'true')} (return true))"""
code["ReleasePolicy"] = f"""(fn ReleasePolicy ()
    {put('PolicyFrozen', 'false')}
    {' '.join(f'(Utilities|Array|Clear {arr(n)})' for n in ('FrozenCategories', 'FrozenTypes', 'FrozenCategoryValues', 'FrozenTypeValues'))}
    (return true))"""
code["CapturePolicy"] = f"""(fn CapturePolicy (Context)
    (if (or {arr('PolicyFrozen')} (not {arr('PolicyKeysReady')})) (return false))
    (if (not (CallFunction|HasObject :Object Context)) (return false))
    (CallFunction|ReleasePolicy)
    {put('FrozenCategories', arr('KnownCategories'))} {put('FrozenTypes', arr('KnownTypes'))}
    (for category {arr('FrozenCategories')}
      (bind value (CallFunction|ReadOption :Context Context :OptionId (CallFunction|CategoryOptionId :Key category) :Fallback "2"))
      (bind (valid priority) (CallFunction|ParsePriority :Value value :AllowInherit false))
      (Utilities|Array|Add {arr('FrozenCategoryValues')} (select valid priority 2)))
    (for type {arr('FrozenTypes')}
      (bind value (CallFunction|ReadOption :Context Context :OptionId (CallFunction|TypeOptionId :Key type) :Fallback "inherit"))
      (bind (valid priority) (CallFunction|ParsePriority :Value value :AllowInherit true))
      (Utilities|Array|Add {arr('FrozenTypeValues')} (select valid priority -1)))
    (bind mode (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.mode" :Fallback "Strict"))
    (bind strict (CallFunction|IsStrictValue :Value mode)) {put('FrozenStrict', 'strict')}
    (bind reserve (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.reserve" :Fallback "1"))
    (bind count (CallFunction|ParseReserve :Value reserve)) {put('FrozenReserve', 'count')}
    {put('PolicyFrozen', 'true')} (return true))"""

exact_locales, prefix_locales = [], []
for i, lang in enumerate(languages):
    alias = lang.replace("-", "_")
    value = item("TextValues", f"(+ (* index {stride}) {i})")
    exact_locales.append(f'(if (or (Utilities|String|EqualExactly(String) normalized "{lang}") (Utilities|String|EqualExactly(String) normalized "{alias}")) (return {value}))')
for lang in sorted(languages, key=len, reverse=True):
    alias = lang.replace("-", "_")
    value = item("TextValues", f"(+ (* index {stride}) {languages.index(lang)})")
    prefix_locales.append(f'(if (or (Utilities|String|StartsWith :SourceString normalized :InPrefix "{lang}-") (Utilities|String|StartsWith :SourceString normalized :InPrefix "{alias}_")) (return {value}))')
code["Localize"] = f"""(fn Localize (Key Language)
    (bind index (Utilities|Array|FindItem {arr('TextKeys')} Key))
    (if (< index 0) (return Key))
    (bind normalized (Utilities|String|ToLower Language))
    {''.join(exact_locales)} {''.join(prefix_locales)}
    (return {item('TextValues', f'(* index {stride})')}))"""
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
legacy_dutch = {"inherit": ["Categorie overnemen"], "priority.0": ["Zeer laag"], "priority.1": ["Laag"], "priority.2": ["Normaal"], "priority.3": ["Hoog"], "priority.4": ["Zeer hoog"]}
code["ParsePriority"] = """(fn ParsePriority (Value AllowInherit)
    """ + "\n".join(
        f'(if (and {"AllowInherit" if value == -1 else "true"} (Utilities|String|EqualExactly(String) Value {literal(label)})) (return true {value}))'
        for key, value in [("inherit", -1)] + [(f"priority.{i}", i) for i in range(5)]
        for label in dict.fromkeys(["inherit" if value == -1 else str(value), "WorkerOptimizer.ui." + key] + translations[key] + legacy_dutch.get(key, []))
    ) + "\n(return false 2))"
code["ResolvePriority"] = """(fn ResolvePriority (CategoryValue TypeValue)
    (bind (typeOK typePriority) (CallFunction|ParsePriority :Value TypeValue :AllowInherit true))
    (if (and typeOK (>= typePriority 0)) (return typePriority))
    (bind (categoryOK categoryPriority) (CallFunction|ParsePriority :Value CategoryValue :AllowInherit false))
    (if categoryOK (return categoryPriority))
    (return 2))"""
code["IsStrictValue"] = "(fn IsStrictValue (Value) " + " ".join(f'(if (Utilities|String|EqualExactly(String) Value {literal(label)}) (return false))' for label in ["Weighted", "WorkerOptimizer.ui.weighted", "Prioriteiten en productiviteit afwegen"] + translations["weighted"]) + " (return true))"
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
    (if {arr('PolicyFrozen')} (return {arr('FrozenReserve')}))
    (bind value (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.reserve" :Fallback "1"))
    (bind count (CallFunction|ParseReserve :Value value)) (return count))"""
auto_modes = ("off", "day_start", "minutes_5", "minutes_10", "minutes_15")
code["ParseAutoMode"] = "(fn ParseAutoMode (Value) " + " ".join(
    f'(if (or (Utilities|String|EqualExactly(String) Value "{mode}") (Utilities|String|EqualExactly(String) Value "WorkerOptimizer.ui.auto.{mode}")) (return "{mode}"))'
    for mode in auto_modes) + ' (return "off"))'
code["ReadAutoMode"] = """(fn ReadAutoMode (Context)
    (bind value (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.auto_assignment" :Fallback "WorkerOptimizer.ui.auto.off"))
    (bind mode (CallFunction|ParseAutoMode :Value value)) (return mode))"""
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
    (if (not reserve) (return false))
    (Utilities|Array|Clear {values})
    {' '.join(f'(Utilities|Array|Add {values} "WorkerOptimizer.ui.auto.{mode}")' for mode in auto_modes)}
    (bind automatic ({register} :self api :WorldContext Context :optionId "WorkerOptimizer.auto_assignment"
      :optionDisplayName "WorkerOptimizer.ui.title.auto_assignment" :Values {values} :DefaultValue "WorkerOptimizer.ui.auto.off" :optionDescription "WorkerOptimizer.ui.auto_assignment_desc"))
    (return automatic))"""
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
    (bind keyReady (CallFunction|AddPolicyKey :Type Type :Category Category))
    (if (not keyReady) (return false))
    (bind metadataIndex (Utilities|Array|FindItem (Variables|Default|GetKnownTypes) Type))
    (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetKnownTypeCategories) :Index metadataIndex :Item Category)
    (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetKnownTypeStringKeys) :Index metadataIndex :Item StringKey)
    (if (and (!= Category "None") (not (Utilities|Array|ContainsItem (Variables|Default|GetRegisteredCategories) Category)))
      (bind categoryLabel (CallFunction|ResolveLabel :Key Category :StringKey (CallFunction|CategoryLabelKey :Key Category)))
      (bind categoryReady (CallFunction|RegisterCategory :Context Context :Category Category :Label categoryLabel))
      (if (not categoryReady) (return false)))
    (if (Utilities|Array|ContainsItem (Variables|Default|GetRegisteredTypes) Type) (return true))
    (bind typeLabel (select (Class|LocManager|HasKey :Key StringKey) StringKey (Utilities|String|ToString(Name) Type)))
    (bind typeReady (CallFunction|RegisterType :Context Context :Type Type :Label typeLabel))
    (return typeReady))"""
code["ReadPriority"] = f"""(fn ReadPriority (Context Category Type)
    (if {arr('PolicyFrozen')}
      (bind typeIndex (Utilities|Array|FindItem {arr('FrozenTypes')} Type))
      (if (>= typeIndex 0)
        (if (>= {item('FrozenTypeValues', 'typeIndex')} 0) (return {item('FrozenTypeValues', 'typeIndex')})))
      (bind categoryIndex (Utilities|Array|FindItem {arr('FrozenCategories')} Category))
      (if (>= categoryIndex 0) (return {item('FrozenCategoryValues', 'categoryIndex')}))
      (return 2))
    (bind categoryKey (CallFunction|CategoryOptionId :Key Category))
    (bind typeKey (CallFunction|TypeOptionId :Key Type))
    (bind categoryValue (CallFunction|ReadOption :Context Context :OptionId categoryKey :Fallback "2"))
    (bind typeValue (CallFunction|ReadOption :Context Context :OptionId typeKey :Fallback "inherit"))
    (bind priority (CallFunction|ResolvePriority :CategoryValue categoryValue :TypeValue typeValue))
    (return priority))"""
code["ReadStrictMode"] = f"""(fn ReadStrictMode (Context)
    (if {arr('PolicyFrozen')} (return {arr('FrozenStrict')}))
    (bind value (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.mode" :Fallback "Strict"))
    (bind strict (CallFunction|IsStrictValue :Value value))
    (return strict))"""
if MANUAL_ONLY:
    # The saved options remain available for a later feature restoration.
    code["ReadPriority"] = "(fn ReadPriority (Context Category Type) (return 2))"
    code["ReadStrictMode"] = "(fn ReadStrictMode (Context) (return true))"
    code["ReadAutoMode"] = "(fn ReadAutoMode (Context) (return \"off\"))"
    code["CapturePolicy"] = f"""(fn CapturePolicy (Context)
        (if (or {arr('PolicyFrozen')} (not {arr('PolicyKeysReady')})) (return false))
        (if (not (CallFunction|HasObject :Object Context)) (return false))
        (CallFunction|ReleasePolicy)
        {put('FrozenCategories', arr('KnownCategories'))} {put('FrozenTypes', arr('KnownTypes'))}
        (for category {arr('FrozenCategories')} (Utilities|Array|Add {arr('FrozenCategoryValues')} 2))
        (for type {arr('FrozenTypes')} (Utilities|Array|Add {arr('FrozenTypeValues')} 2))
        {put('FrozenStrict', 'true')}
        (bind reserve (CallFunction|ReadOption :Context Context :OptionId "WorkerOptimizer.reserve" :Fallback "1"))
        (bind count (CallFunction|ParseReserve :Value reserve)) {put('FrozenReserve', 'count')}
        {put('PolicyFrozen', 'true')} (return true))"""
    code["RegisterGeneral"] = """(fn RegisterGeneral (Context)
        (if (not (CallFunction|HasObject :Object Context)) (return false))
        (bind strings (CallFunction|RegisterStrings :Context Context)) (return strings))"""
    for kind in ("Category", "Type"):
        code["Register" + kind] = f"""(fn Register{kind} (Context {kind} Label)
            (if (not (CallFunction|HasObject :Object Context)) (return false))
            (if (== {kind} "None") (return false))
            {api_guard('false')}
            (Utilities|Array|AddUnique {arr('RegisteredCategories' if kind == 'Category' else 'RegisteredTypes')} {kind})
            (return true))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        if not MANUAL_ONLY and os.environ.get("WO_UI_PRIORITY_ONLY") == "1" and name not in {"WriteOption", "BeginPolicyKeys", "AddPolicyKey", "EnsureDefinitionOptions", "Localize", "ParsePriority", "IsStrictValue"}:
            continue
        unreal.log("WO_PRIORITY_SETTINGS_WRITE " + name)
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
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    defaults = unreal.get_default_object(bp.generated_class())
    defaults.set_editor_property("TextKeys", list(translations))
    defaults.set_editor_property("TextValues", [value for row in translations.values() for value in row])
    defaults.set_editor_property("Languages", languages)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-PrioritySettings.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_PRIORITY_SETTINGS_GENERATED")
if os.environ.get("WO_SKIP_GENERATOR_TESTS") != "1":
    exec(Path(__file__).with_name("test_priority_settings.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_localization.py").read_text(encoding="utf-8"))
