"""Author a bounded projection of native priority categories and settings."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp = unreal.load_asset(ROOT + "/BP_SettingsModel") or BP.create(ROOT, "BP_SettingsModel", unreal.Object.static_class())
functions = {
    "HasObject": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "InitializeModel": ([("Context", unreal.Object.static_class()), ("Settings", load("BP_PrioritySettings")), ("Catalog", load("BP_DefinitionCatalog"))], [("Result", "bool")]),
    "BeginFilter": ([("Query", "string")], [("Result", "bool")]),
    "AdvanceFilter": ([], [("Result", "bool")]),
    "ToggleCategory": ([("Category", "name")], [("Result", "bool")]),
    "ValidateSetting": ([("OptionId", "string"), ("Value", "string")], [("Result", "bool")]),
    "CanWrite": ([("OptionId", "string"), ("Value", "string")], [("Result", "bool")]),
    "WriteSetting": ([("OptionId", "string"), ("Value", "string")], [("Result", "bool")]),
    "TypePriority": ([("Index", "int")], [("Override", "int"), ("Effective", "int")]),
    "CategoryPriority": ([("Index", "int")], [("Value", "int")]),
    "ReadValue": ([("OptionId", "string"), ("Fallback", "string")], [("Value", "string")]),
}
graphs = declare(bp, {"bool": "Initialized Busy Filtering GroupMatched", "int": "Stage Cursor GroupIndex SearchRevision OptionRevision PendingTypeIndex",
    "string": "QueryText PendingLabel", "name": "PendingKey PendingCategory", "name[]": "TypeKeys CategoryKeys ExpandedCategories", "string[]": "TypeLabels CategoryLabels",
    "int[]": "TypeCategories RowIndices CategoryFirst CategoryLast TypeNext", "bool[]": "TypeMatches RowIsCategory"}, functions,
    {"Context": unreal.Object.static_class(), "Settings": load("BP_PrioritySettings"), "Catalog": load("BP_DefinitionCatalog"), "RunController": load("BP_WorkerOptimizer")})
if "OnSettingsPresentationChanged" not in {str(graph.get_name()) for graph in BP.list_event_dispatchers(bp)}:
    BP.add_event_dispatcher(bp, "OnSettingsPresentationChanged")
BP.compile_blueprint(bp)
notification_nodes = list(dict.fromkeys(node for node in BP.find_node_types(graphs["WriteSetting"], "OnSettingsPresentationChanged", [])
                      if node.rsplit("|", 1)[-1].replace(" ", "") == "CallOnSettingsPresentationChanged"))
assert len(notification_nodes) == 1, notification_nodes
notify = f"({notification_nodes[0]} :self self)"
S = lambda fn, args="": invoke("BPPrioritySettings", g("Settings"), fn, args)
C = lambda n: prop("BPDefinitionCatalog", g("Catalog"), n)
arr_add = lambda n, v: f"(Utilities|Array|Add {g(n)} {v})"
ok = '(return true)'
code = {}
code["HasObject"] = '(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code["InitializeModel"] = f'''(fn InitializeModel (Context Settings Catalog)
    (if (not (and (CallFunction|HasObject :Object Context) (and (CallFunction|HasObject :Object Settings) (CallFunction|HasObject :Object Catalog)))) (return false))
    {put('Context','Context')} {put('Settings','Settings')} {put('Catalog','Catalog')} {put('Initialized','true')}
    (bind started (CallFunction|BeginFilter :Query "")) (return started))'''
code["BeginFilter"] = f'''(fn BeginFilter (Query)
    (if (not {g('Initialized')}) (return false))
    {put('QueryText','(Utilities|String|ToLower Query)')} {put('Filtering','true')} {put('Stage','0')} {put('Cursor','0')} {put('GroupIndex','0')}
    {' '.join(f'(Utilities|Array|Clear {g(n)})' for n in ('TypeKeys','CategoryKeys','TypeLabels','CategoryLabels','TypeCategories','TypeMatches','RowIndices','RowIsCategory','CategoryFirst','CategoryLast','TypeNext'))}
    (return true))'''
code["ToggleCategory"] = f'''(fn ToggleCategory (Category)
    (if (Utilities|Array|ContainsItem {g('ExpandedCategories')} Category)
      (Utilities|Array|RemoveItem {g('ExpandedCategories')} Category)
      (else (Utilities|Array|AddUnique {g('ExpandedCategories')} Category)))
    (bind started (CallFunction|BeginFilter :Query {g('QueryText')})) (return started))'''
# The union of the startup catalog and newly observed metadata does not scan the world.
known = prop('BPPrioritySettings',g('Settings'),'KnownTypes')
known_cats = prop('BPPrioritySettings',g('Settings'),'KnownTypeCategories')
known_labels = prop('BPPrioritySettings',g('Settings'),'KnownTypeStringKeys')
code["AdvanceFilter"] = f'''(fn AdvanceFilter ()
    (if (not {g('Filtering')}) (return false))
    (if (== {g('Stage')} 0)
      (if (>= {g('Cursor')} (+ {length(C('Types'))} {length(known)}))
        {put('Stage','1')} {put('Cursor','-1')} {put('GroupIndex','0')} {put('GroupMatched','false')}
        (if (> {length(g('CategoryFirst'))} 0) {put('Cursor',at(g('CategoryFirst'),'0'))}) (return true))
      (bind native (< {g('Cursor')} {length(C('Types'))}))
      (if native
        {put('PendingKey',at(C('Types'),g('Cursor')))}
        {put('PendingCategory',at(C('Categories'),g('Cursor')))}
        {put('PendingLabel',at(C('StringKeys'),g('Cursor')))}
        (else
          (bind index (- {g('Cursor')} {length(C('Types'))}))
          {put('PendingKey',at(known,'index'))} {put('PendingCategory','"None"')} {put('PendingLabel','""')}
          (if (Utilities|Array|IsValidIndex {known_cats} index) {put('PendingCategory',at(known_cats,'index'))})
          (if (Utilities|Array|IsValidIndex {known_labels} index) {put('PendingLabel',at(known_labels,'index'))})))
      (bind key {g('PendingKey')})
      (if (Utilities|Array|ContainsItem {g('TypeKeys')} key) {put('Cursor',f'(+ {g("Cursor")} 1)')} (return true))
      (bind category {g('PendingCategory')})
      (bind categoryKey (select (== category "None") "uncategorized" category))
      (bind labelKey {g('PendingLabel')})
      (bind display {S('ResolveLabel',':Key key :StringKey labelKey')})
      (if (not (Utilities|Array|ContainsItem {g('CategoryKeys')} categoryKey))
        {arr_add('CategoryKeys','categoryKey')}
        {arr_add('CategoryFirst','-1')} {arr_add('CategoryLast','-1')}
        (bind categoryText {S('ResolveLabel',f':Key categoryKey :StringKey {S("CategoryLabelKey",":Key categoryKey")}')})
        {arr_add('CategoryLabels','categoryText')})
      (bind group (Utilities|Array|FindItem {g('CategoryKeys')} categoryKey))
      {put('PendingTypeIndex',length(g('TypeKeys')))} {arr_add('TypeNext','-1')}
      (if (< {at(g('CategoryFirst'),'group')} 0)
        (Utilities|Array|SetArrayElem :TargetArray {g('CategoryFirst')} :Index group :Item {g('PendingTypeIndex')})
        (else (Utilities|Array|SetArrayElem :TargetArray {g('TypeNext')} :Index {at(g('CategoryLast'),'group')} :Item {g('PendingTypeIndex')})))
      (Utilities|Array|SetArrayElem :TargetArray {g('CategoryLast')} :Index group :Item {g('PendingTypeIndex')})
      {arr_add('TypeKeys','key')} {arr_add('TypeLabels','display')} {arr_add('TypeCategories','group')}
      (bind matches (or (== (Utilities|String|Len {g('QueryText')}) 0)
        (or (Utilities|String|Contains :SearchIn (Utilities|String|ToLower display) :Substring {g('QueryText')})
          (or (Utilities|String|Contains :SearchIn (Utilities|String|ToLower (Utilities|String|ToString(Name) key)) :Substring {g('QueryText')})
            (Utilities|String|Contains :SearchIn (Utilities|String|ToLower {at(g('CategoryLabels'),'group')}) :Substring {g('QueryText')})))))
      {arr_add('TypeMatches','matches')} {put('Cursor',f'(+ {g("Cursor")} 1)')} (return true))
    (if (>= {g('GroupIndex')} {length(g('CategoryKeys'))})
      {put('Filtering','false')} {put('SearchRevision',f'(+ {g("SearchRevision")} 1)')} {notify} (return true))
    (if (< {g('Cursor')} 0)
      {put('GroupIndex',f'(+ {g("GroupIndex")} 1)')} {put('GroupMatched','false')}
      (if (Utilities|Array|IsValidIndex {g('CategoryFirst')} {g('GroupIndex')}) {put('Cursor',at(g('CategoryFirst'),g('GroupIndex')))}) (return true))
    (if (and (== {at(g('TypeCategories'),g('Cursor'))} {g('GroupIndex')}) {at(g('TypeMatches'),g('Cursor'))})
      (if (not {g('GroupMatched')}) {arr_add('RowIndices',g('GroupIndex'))} {arr_add('RowIsCategory','true')} {put('GroupMatched','true')})
      (if (or (> (Utilities|String|Len {g('QueryText')}) 0) (Utilities|Array|ContainsItem {g('ExpandedCategories')} {at(g('CategoryKeys'),g('GroupIndex'))}))
        {arr_add('RowIndices',g('Cursor'))} {arr_add('RowIsCategory','false')}))
    {put('Cursor',at(g('TypeNext'),g('Cursor')))} (return true))'''
code["ReadValue"] = f'''(fn ReadValue (OptionId Fallback)
    (bind value {S('ReadOption',f':Context {g("Context")} :OptionId OptionId :Fallback Fallback')}) (return value))'''
code["CategoryPriority"] = f'''(fn CategoryPriority (Index)
    (if (not (Utilities|Array|IsValidIndex {g('CategoryKeys')} Index)) (return 2))
    (if (== {at(g('CategoryKeys'),'Index')} "uncategorized") (return 2))
    (bind id {S('CategoryOptionId',f':Key {at(g("CategoryKeys"),"Index")}')})
    (bind (valid value) {S('ParsePriority',':Value (CallFunction|ReadValue :OptionId id :Fallback "2") :AllowInherit false')})
    (return (select valid value 2)))'''
code["TypePriority"] = f'''(fn TypePriority (Index)
    (if (not (Utilities|Array|IsValidIndex {g('TypeKeys')} Index)) (return -1 2))
    (bind id {S('TypeOptionId',f':Key {at(g("TypeKeys"),"Index")}')})
    (bind (valid value) {S('ParsePriority',':Value (CallFunction|ReadValue :OptionId id :Fallback "inherit") :AllowInherit true')})
    (bind override (select valid value -1))
    (bind category (CallFunction|CategoryPriority :Index {at(g('TypeCategories'),'Index')}))
    (return override (select (>= override 0) override category)))'''
code["ValidateSetting"] = f'''(fn ValidateSetting (OptionId Value)
    (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.reserve")
      (bind count {S('ParseReserve',':Value Value')})
      (return (Utilities|String|EqualExactly(String) Value (Utilities|String|ToString(Integer) count))))
    (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.mode")
      (return (or (Utilities|String|EqualExactly(String) Value "WorkerOptimizer.ui.strict") (Utilities|String|EqualExactly(String) Value "WorkerOptimizer.ui.weighted"))))
    (if (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.auto_assignment")
      {' '.join(f'(if (Utilities|String|EqualExactly(String) Value "WorkerOptimizer.ui.auto.{mode}") (return true))' for mode in ('off','day_start','minutes_5','minutes_10','minutes_15'))}
      (return false))
    (for key {g('CategoryKeys')}
      (if (Utilities|String|EqualExactly(String) OptionId {S('CategoryOptionId',':Key key')})
        (if (== key "uncategorized") (return false))
        (bind (valid priority) {S('ParsePriority',':Value Value :AllowInherit false')}) (return valid)))
    (for key {g('TypeKeys')}
      (if (Utilities|String|EqualExactly(String) OptionId {S('TypeOptionId',':Key key')})
        (bind (valid priority) {S('ParsePriority',':Value Value :AllowInherit true')}) (return valid)))
    (return false))'''
code["CanWrite"] = f'''(fn CanWrite (OptionId Value)
    (if (CallFunction|HasObject :Object {g('RunController')}) {put('Busy',prop('BPWorkerOptimizer',g('RunController'),'RunActive'))})
    (if (not (CallFunction|ValidateSetting :OptionId OptionId :Value Value)) (return false))
    (if {g('Busy')} (return (and (Utilities|String|EqualExactly(String) OptionId "WorkerOptimizer.auto_assignment")
      (Utilities|String|EqualExactly(String) Value "WorkerOptimizer.ui.auto.off")))) (return true))'''
code["WriteSetting"] = f'''(fn WriteSetting (OptionId Value)
    (if (not (CallFunction|CanWrite :OptionId OptionId :Value Value)) (return false))
    (bind written {S('WriteOption',f':Context {g("Context")} :OptionId OptionId :Value Value')})
    (if written {put('OptionRevision',f'(+ {g("OptionRevision")} 1)')} {notify}) (return written))'''
emit(bp, graphs, code)
unreal.log("WO_SETTINGS_MODEL_GENERATED")
