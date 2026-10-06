"""Author the native TreeView projection of the existing priority settings model."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp, add = widget("WBP_PrioritiesView", reset_layout=True)
for name, seconds in (('SearchPulse', 0.15), ('FilterPulse', 0.01)):
    assert unreal.WorkerOptimizerUIAuthoring.create_pulse_animation(bp, name, seconds)
root, _ = add(unreal.VerticalBox, "Contents")
toolbar, _ = add(unreal.WrapBox, "Toolbar", root)
toolbar.set_editor_property("explicit_wrap_size", True)
toolbar.set_editor_property("wrap_size", 920.0)
search_size, _ = add(unreal.SizeBox, "SearchSize", toolbar)
search_size.set_width_override(360)
search, _ = add(unreal.EditableTextBox, "SearchBox", search_size)
input_style(search)
label(add, "Legend", toolbar, size=13)
match_count,_=label(add, "MatchCount", root, size=13)
header, _ = add(unreal.Border,'HeaderSurface',root)
header.set_padding(unreal.Margin(12,8,12,8))
header.set_brush_color(color('head'))
head, _ = add(unreal.HorizontalBox, "Headings", header)
_, slot = label(add, "TypeHeading", head, size=13)
slot.set_size(unreal.SlateChildSize(1.0, unreal.SlateSizeRule.FILL))
priority_heading, _ = add(unreal.SizeBox,'PriorityHeadingSize',head)
priority_heading.set_width_override(540)
label(add,'PriorityHeading',priority_heading,size=13)
effective_heading, _ = add(unreal.SizeBox,'EffectiveHeadingSize',head)
effective_heading.set_width_override(112)
label(add, "EffectiveHeading", effective_heading, size=13)
rule_size,_=add(unreal.SizeBox,'HeaderRule',root)
rule_size.set_height_override(1)
rule,_=add(unreal.Border,'HeaderRulePaint',rule_size)
rule.set_padding(unreal.Margin(0))
rule.set_brush_color(color('line'))
tree, slot = add(unreal.TreeView, "PriorityTree", root)
style_scrollbar(tree)
slot.set_size(unreal.SlateChildSize(1.0, unreal.SlateSizeRule.FILL))
tree.set_editor_property("entry_widget_class", load("WBP_PriorityRow"))
tree.set_editor_property("selection_mode", unreal.SelectionMode.SINGLE)
# Preserve widget GUIDs while restoring sibling order after incremental wrappers.
root.clear_children()
for child in (toolbar,match_count,header,rule_size,tree):
    restored_slot=root.add_child(child)
    if child==tree:
        restored_slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
for name in ("RootItems", "AllItems", "EmptyItems", "BuildChildren"):
    if name not in BP.list_variables(bp):
        BP.add_object_variable(bp, name, unreal.Object.static_class(), container_type=ContainerType.ARRAY)
functions = {
    "HasObject": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "InitializePriorities": ([("Model", load("BP_SettingsModel"))], [("Result", "bool")]),
    "ApplyLayout": ([("Width", "float"), ("Height", "float")], [("Result", "bool")]),
    "CanUseItem": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "WritePriority": ([("Object", unreal.Object.static_class()), ("Value", "int")], [("Result", "bool")]),
    "ExpandItem": ([("Object", unreal.Object.static_class()), ("Expanded", "bool")], [("Result", "bool")]),
    "ToggleExpansion": ([("Object", unreal.Object.static_class()), ("Expanded", "bool")], [("Result", "bool")]),
    "PresentationLabel": ([("Key", "name"), ("Label", "string"), ("Category", "bool")], [("Result", "string")]),
    "HasLocalizedLabel": ([("Label", "string"), ("StringKey", "string")], [("Result", "bool")]),
    "OnSearchPulse": ([], []), "OnFilterPulse": ([], []),
    **{n: ([], [("Result", "bool")]) for n in ("RefreshPriorities", "ShutdownView", "SearchChanged", "CommitSearch", "ContinueFilter", "BindSearchPulse", "BindFilterPulse")},
}
# TreeView's children callback is a native out-array delegate.
existing = {str(x.get_name()) for x in BP.list_graphs(bp)}
if "GetChildren" not in existing:
    graph = BP.add_function_graph(bp, "GetChildren")
    BP.add_object_function_param(graph, "Object", unreal.Object.static_class(), True)
    BP.add_object_function_param(graph, "Children", unreal.Object.static_class(), False, ContainerType.ARRAY)
graphs = declare(bp, {"bool": "Active Updating Narrow RenderedBusy PulsesBound SearchPending", "float": "LayoutWidth", "int": "RenderedRevision RenderedOptions BuildCount MatchTotal", "string": "PendingQuery"}, functions, {"Model": load("BP_SettingsModel")})
graphs["GetChildren"] = BP.get_graph(bp, "GetChildren")
number_text_node = next(n for n in BP.find_node_types(graphs['RefreshPriorities'], '', []) if n.endswith('|ToText(Integer)'))
number_string = lambda value: text_string('(' + number_text_node + ' ' + value + ')')
M = lambda n: prop("BPSettingsModel", g("Model"), n)
S = lambda fn, args="": invoke("BPPrioritySettings", M("Settings"), fn, args)
U = lambda key: S("Text", ':Key "' + key + '"')
I = lambda obj, n: prop("BPUIListItem", obj, n)
SI = lambda obj, n, value: invoke("BPUIListItem", obj, "Set" + n, ":" + n + " " + value)
create = f'(Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self self)'
treecall = lambda fn, args="": f'({native(graphs["RefreshPriorities"], fn, "TreeView")} :self {g("PriorityTree")} {args})'
edit = lambda fn, args="": f'({native(graphs["SearchChanged"], fn, "EditableTextBox")} :self {g("SearchBox")} {args})'
play = lambda field: f'(UserInterface|Animation|PlayAnimation :self self :InAnimation {g(field)} :StartAtTime 0.0 :NumLoopsToPlay 1 :PlayMode "Forward" :PlaybackSpeed 1.0 :bRestoreState false)'
stop = lambda field: f'(UserInterface|Animation|StopAnimation :self self :InAnimation {g(field)})'
valid = '(Utilities|IsValid Object (:"Is Valid" true) (:"Is Not Valid" false))'
code = {}
code['HasObject'] = '(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code["InitializePriorities"] = f'''(fn InitializePriorities (Model)
    (if (not (CallFunction|HasObject :Object Model)) (return false))
    {put('Model','Model')} {put('Active','true')} {put('RenderedRevision','-1')} {put('RenderedOptions','-1')}
    (if (not {g('PulsesBound')}) (CallFunction|BindSearchPulse) (CallFunction|BindFilterPulse) {put('PulsesBound','true')})
    {edit('SetHintText', ':InText ' + text(U('search')))}
    {set_label('TypeHeading', U('building_type'))} {set_label('EffectiveHeading', U('effective'))}
    {set_label('PriorityHeading',U('tab.priorities'))}
    {set_label('Legend', '(Utilities|String|Append :A ' + U('priority.custom') + ' :B (Utilities|String|Append :A " / " :B ' + U('inherit') + '))')}
    (if {M('Filtering')} {visibility('PriorityTree','Hidden')} {play('FilterPulse')} (return true))
    (bind refreshed (CallFunction|RefreshPriorities)) (return refreshed))'''
code["CanUseItem"] = f'''(fn CanUseItem (Object)
    (if (not {g('Active')}) (return false))
    (if (not (CallFunction|HasObject :Object {g('Model')})) (return false))
    (if {M('Filtering')} (return false))
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (if (not (CallFunction|HasObject :Object item)) (return false))
    (if (not (== {I('item','Owner')} self)) (return false))
    (if (or (!= {I('item','Revision')} {g('RenderedRevision')}) (!= {g('RenderedRevision')} {M('SearchRevision')})) (return false))
    (if (not (Utilities|Array|ContainsItem {g('AllItems')} Object)) (return false))
    (bind category (== {I('item','Kind')} "category"))
    (bind keys (select category {M('CategoryKeys')} {M('TypeKeys')}))
    (if (not (Utilities|Array|IsValidIndex keys {I('item','Index')})) (return false))
    (return (== {at('keys',I('item','Index'))} {I('item','Key')})))'''
code["GetChildren"] = f'''(fn GetChildren (Object)
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (if (not (CallFunction|HasObject :Object item)) (return {g('EmptyItems')}))
    (if (not (== {I('item','Owner')} self)) (return {g('EmptyItems')}))
    (return {I('item','Children')}))'''
code['HasLocalizedLabel'] = '''(fn HasLocalizedLabel (Label StringKey)
    (if (== (Utilities|String|Len StringKey) 0) (return false))
    (if (not (Class|LocManager|HasKey :Key StringKey)) (return false))
    (return (Utilities|String|EqualExactly(String) (Class|LocManager|GetWordfromKey :Key StringKey) Label)))'''
code['PresentationLabel'] = f'''(fn PresentationLabel (Key Label Category)
    (if (== (Utilities|String|Len Label) 0) (bind emptyLabel {U('priority.unavailable')}) (return emptyLabel))
    (if (not (Utilities|String|EqualExactly(String) Label (Utilities|String|ToString(Name) Key))) (return Label))
    (if Category
      (if (CallFunction|HasLocalizedLabel :Label Label :StringKey {S('CategoryLabelKey', ':Key Key')}) (return Label))
      (else
        (bind catalog {M('Catalog')})
        (if (CallFunction|HasObject :Object catalog)
          (bind index (Utilities|Array|FindItem {prop('BPDefinitionCatalog', 'catalog', 'Types')} Key))
          (if (Utilities|Array|IsValidIndex {prop('BPDefinitionCatalog', 'catalog', 'StringKeys')} index)
            (if (CallFunction|HasLocalizedLabel :Label Label :StringKey {at(prop('BPDefinitionCatalog', 'catalog', 'StringKeys'), 'index')}) (return Label))))
        (bind observedIndex (Utilities|Array|FindItem {prop('BPPrioritySettings', M('Settings'), 'KnownTypes')} Key))
        (if (Utilities|Array|IsValidIndex {prop('BPPrioritySettings', M('Settings'), 'KnownTypeStringKeys')} observedIndex)
          (if (CallFunction|HasLocalizedLabel :Label Label :StringKey {at(prop('BPPrioritySettings', M('Settings'), 'KnownTypeStringKeys'), 'observedIndex')}) (return Label)))))
    (bind categoryKey (Utilities|String|Append :A "category." :B (Utilities|String|ToLower (Utilities|String|ToString(Name) Key))))
    (if (Utilities|Array|ContainsItem {prop('BPPrioritySettings', M('Settings'), 'TextKeys')} categoryKey)
      (if (Utilities|String|EqualExactly(String) {S('Text', ':Key categoryKey')} Label) (return Label)))
    (bind unavailableLabel {U('priority.unavailable')}) (return unavailableLabel))'''
# A complete model snapshot is published only after its bounded filter commits.
code["RefreshPriorities"] = f'''(fn RefreshPriorities ()
    (if (not {g('Active')}) (return false))
    (if {M('Filtering')} {visibility('PriorityTree','Hidden')} {play('FilterPulse')} (return false))
    (if (and (== {g('RenderedBusy')} {M('Busy')}) (and (== {g('RenderedRevision')} {M('SearchRevision')}) (== {g('RenderedOptions')} {M('OptionRevision')}))) (return true))
    {put('Updating','true')} (Utilities|Array|Clear {g('RootItems')}) (Utilities|Array|Clear {g('AllItems')}) {put('MatchTotal','0')}
    {put('RenderedRevision',M('SearchRevision'))} {put('RenderedOptions',M('OptionRevision'))} {put('RenderedBusy',M('Busy'))}
    (for r (range {length(M('RowIndices'))})
      (if {at(M('RowIsCategory'),'r')}
        (bind c {at(M('RowIndices'),'r')}) (bind category {create})
        {SI('category','Owner','self')} {SI('category','Kind','"category"')}
        {SI('category','Key',at(M('CategoryKeys'),'c'))} {SI('category','Index','c')} {SI('category','Revision',g('RenderedRevision'))}
        (bind categoryLabel (CallFunction|PresentationLabel :Key {at(M('CategoryKeys'),'c')} :Label {at(M('CategoryLabels'),'c')} :Category true))
        {SI('category','Title',text('categoryLabel'))}
        (Utilities|Array|Add {g('RootItems')} category) (Utilities|Array|Add {g('AllItems')} category)
        (Utilities|Array|Clear {g('BuildChildren')})
        (for t (range {length(M('TypeKeys'))})
          (if (and (== {at(M('TypeCategories'),'t')} c) {at(M('TypeMatches'),'t')})
            (bind item {create}) {SI('item','Owner','self')} {SI('item','Kind','"type"')}
            {SI('item','Key',at(M('TypeKeys'),'t'))} {SI('item','Index','t')} {SI('item','Revision',g('RenderedRevision'))}
            (bind typeLabel (CallFunction|PresentationLabel :Key {at(M('TypeKeys'),'t')} :Label {at(M('TypeLabels'),'t')} :Category false))
            {SI('item','Title',text('typeLabel'))}
            (Utilities|Array|Add {g('BuildChildren')} item) (Utilities|Array|Add {g('AllItems')} item)
            {put('MatchTotal',f'(+ {g("MatchTotal")} 1)')}))
        {SI('category','Children',g('BuildChildren'))}
        {SI('category','Count',length(g('BuildChildren')))}))
    {treecall('SetListItems', ':InListItems ' + g('RootItems'))}
    (for object {g('RootItems')}
      (bind item (Utilities|Casting|CastToBP_UIListItem :Object object))
      {treecall('SetItemExpansion', ':Item object :bExpandItem (or (> (Utilities|String|Len ' + M('QueryText') + ') 0) (Utilities|Array|ContainsItem ' + M('ExpandedCategories') + ' ' + I('item','Key') + '))')})
    (bind countLabel {U('priority.types_count')})
    {set_label('MatchCount', '(Utilities|String|Append :A countLabel :B (Utilities|String|Append :A ": " :B (Utilities|String|Append :A ' + number_string(g('MatchTotal')) + ' :B (Utilities|String|Append :A " / " :B ' + number_string(length(M('TypeKeys'))) + '))))')}
    {visibility('PriorityTree','Visible')} {put('Updating','false')} {put('BuildCount',f'(+ {g("BuildCount")} 1)')} (return true))'''
code["WritePriority"] = f'''(fn WritePriority (Object Value)
    (if (or {g('Updating')} (not (CallFunction|CanUseItem :Object Object))) (return false))
    (if (or (< Value -1) (> Value 4)) (return false))
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (bind category (== {I('item','Kind')} "category"))
    (if (and category (< Value 0)) (return false))
    (bind option (select category {S('CategoryOptionId',':Key ' + I('item','Key'))} {S('TypeOptionId',':Key ' + I('item','Key'))}))
    (bind value (select (< Value 0) "WorkerOptimizer.ui.inherit" (Utilities|String|Append :A "WorkerOptimizer.ui.priority." :B (Utilities|String|ToString(Integer) Value))))
    (bind written {invoke('BPSettingsModel',g('Model'),'WriteSetting',':OptionId option :Value value')})
    (CallFunction|RefreshPriorities) (return written))'''
code["ExpandItem"] = f'''(fn ExpandItem (Object Expanded)
    (if (or {g('Updating')} (not (CallFunction|CanUseItem :Object Object))) (return false))
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (if (not (== {I('item','Kind')} "category")) (return false))
    (if (== (Utilities|Array|ContainsItem {M('ExpandedCategories')} {I('item','Key')}) Expanded) (return true))
    (bind changed {invoke('BPSettingsModel',g('Model'),'ToggleCategory',':Category '+I('item','Key'))})
    {visibility('PriorityTree','Hidden')} {play('FilterPulse')} (return changed))'''
code['ToggleExpansion'] = f'''(fn ToggleExpansion (Object Expanded)
    (if (or {g('Updating')} (not (CallFunction|CanUseItem :Object Object))) (return false))
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (if (not (== {I('item','Kind')} "category")) (return false))
    {treecall('SetItemExpansion', ':Item Object :bExpandItem Expanded')}
    (return true))'''
code["SearchChanged"] = f'''(fn SearchChanged ()
    (if (or (not {g('Active')}) {g('Updating')}) (return false))
    {put('PendingQuery',text_string(edit('GetText')))} {put('SearchPending','true')} {play('SearchPulse')} (return true))'''
code["CommitSearch"] = f'''(fn CommitSearch ()
    (if (not {g('Active')}) (return false))
    {put('SearchPending','false')}
    {invoke('BPSettingsModel',g('Model'),'BeginFilter',':Query '+g('PendingQuery'))}
    {visibility('PriorityTree','Hidden')} {play('FilterPulse')} (return true))'''
code["ContinueFilter"] = f'''(fn ContinueFilter ()
    (if (not {g('Active')}) (return false))
    (for work (range 32) (if {M('Filtering')} {invoke('BPSettingsModel',g('Model'),'AdvanceFilter')}))
    (if {M('Filtering')} {play('FilterPulse')} (else (CallFunction|RefreshPriorities))) (return true))'''
code["ApplyLayout"] = f'''(fn ApplyLayout (Width Height)
    {put('LayoutWidth','Width')} {put('Narrow','(< Width 920.0)')}
    ({native(graphs['ApplyLayout'],'SetWidthOverride','SizeBox')} :self {g('SearchSize')} :InWidthOverride (select {g('Narrow')} 280.0 360.0))
    ({native(graphs['ApplyLayout'],'SetWrapSize','WrapBox')} :self {g('Toolbar')} :WrapSize Width)
    ({native(graphs['ApplyLayout'],'SetWidthOverride','SizeBox')} :self {g('PriorityHeadingSize')} :InWidthOverride (select {g('Narrow')} 280.0 540.0))
    (bind entries ({native(graphs['ApplyLayout'],'GetDisplayedEntryWidgets','ListViewBase')} :self {g('PriorityTree')}))
    (for object entries
      (bind row (Utilities|Casting|CastToWBP_PriorityRow :Object object))
      (if (CallFunction|HasObject :Object row)
        {invoke('WBPPriorityRow','row','ApplyLayout',':Width Width')}))
    (return true))'''
code["ShutdownView"] = f'''(fn ShutdownView ()
    {put('Active','false')} {put('SearchPending','false')}
    (if (CallFunction|HasObject :Object {g('Model')})
      {put('PendingQuery',M('QueryText'))}
      {edit('SetText',':InText '+text(g('PendingQuery')))})
    {stop('SearchPulse')} {stop('FilterPulse')} (return true))'''
code['OnSearchPulse'] = f'''(fn OnSearchPulse ()
    (if (and {g('Active')} {g('SearchPending')}) (CallFunction|CommitSearch)) (return))'''
code['OnFilterPulse'] = f'''(fn OnFilterPulse ()
    (if {g('Active')} (if {M('Filtering')} (CallFunction|ContinueFilter))) (return))'''
for name in ('BindSearchPulse', 'BindFilterPulse'):
    code[name] = '(fn '+name+' () (return true))'
emit(bp, graphs, code, {"RenderedRevision": -1, "RenderedOptions": -1, "LayoutWidth": 680.0})


def wire_pulse(field, callback):
    graph = graphs['Bind'+field]
    infos = BP.get_node_infos(BP.find_nodes(graph))
    entry = next(n for n in infos if any(p.name == 'then' for p in n.output_pins))
    result = next(n for n in infos if any(p.name == 'Result' for p in n.input_pins))
    target = BP.create_node(graph, 'Animation|BindtoAnimationFinished', unreal.IntPoint(400, 0), declaring_class=unreal.UserWidget.static_class())
    getter = BP.create_node(graph, g(field)[1:-1], unreal.IntPoint(0, 100))
    target_info, getter_info = BP.get_node_infos([target, getter])
    BP.connect_pins(next(p.pin_id for p in getter_info.output_pins if p.name != 'then'), next(p.pin_id for p in target_info.input_pins if p.name == 'Animation'))
    delegate = BP.create_node(graph, 'EventDispatchers|CreateEvent', unreal.IntPoint(0, 200))
    delegate_info = BP.get_node_infos([delegate])[0]
    BP.connect_pins(next(p.pin_id for p in delegate_info.output_pins if p.name == 'OutputDelegate'), next(p.pin_id for p in target_info.input_pins if p.name == 'Delegate'))
    BP.set_create_event_function(delegate, callback)
    BP.connect_pins(next(p.pin_id for p in entry.output_pins if p.name == 'then'), next(p.pin_id for p in target_info.input_pins if p.name == 'execute'))
    BP.connect_pins(next(p.pin_id for p in target_info.output_pins if p.name == 'then'), next(p.pin_id for p in result.input_pins if p.name == 'execute'))


wire_pulse('SearchPulse', 'OnSearchPulse')
wire_pulse('FilterPulse', 'OnFilterPulse')
events(bp, [("SearchBox", "OnTextChanged", "SearchChanged", unreal.EditableTextBox), ("PriorityTree", "BP_OnItemExpansionChanged", "ExpandItem", unreal.TreeView, {"Item": "Object", "bIsExpanded": "Expanded"})])
bind_children_delegate(bp, "PriorityTree", "GetChildren")
BP.compile_blueprint(bp, warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_PRIORITIES_VIEW_GENERATED")
