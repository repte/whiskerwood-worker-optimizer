"""Author an explicitly opened, immutable last-50 run history view."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp, add = widget("WBP_LogbookView", reset_layout=True)
root, _ = add(unreal.VerticalBox, "HistoryRoot")
bar_size,_=add(unreal.SizeBox,'FilterBarSize',root)
bar_size.set_height_override(52)
bar, _ = add(unreal.HorizontalBox, "FilterBar", bar_size)
all_filter, _ = button(add, "AllFilter", bar, "All")
problems_filter,_=button(add, "ProblemsFilter", bar, "Problems")
for control,selected in [(all_filter,True),(problems_filter,False)]:
    style=control.get_editor_property('widget_style')
    brush_tint(style,'normal',unreal.LinearColor(1,1,1,1))
    control.set_editor_property('widget_style',style)
    control.set_background_color(color('sel' if selected else 'surface'))
label(add, "StorageState", bar,size=13)
next(w.widget for w in unreal.get_default_object(unreal.UMGToolSet).call_method('GetWidgets',args=(bp,)).widgets if str(w.widget_name) == 'StorageState').set_color_and_opacity(unreal.SlateColor(MUTED))
content, _ = add(unreal.CanvasPanel, "HistoryContent", root)
content.slot.set_size(unreal.SlateChildSize(1.0, unreal.SlateSizeRule.FILL))
size, _ = add(unreal.SizeBox, "ListSize", content)
size.slot.set_auto_size(True)
list_body,_=add(unreal.VerticalBox,'RunListBody',size)
header_size,_=add(unreal.SizeBox,'RunHeaderSize',list_body)
header_size.set_min_desired_height(32)
header_background,_=add(unreal.Border,'RunHeaderBackground',header_size)
header_background.set_brush_color(color('head'))
header_background.set_padding(unreal.Margin(12,4,22,4))
header,_=add(unreal.HorizontalBox,'RunHeader',header_background)
for name,width in [('ResultHeader',160),('TimestampHeader',140),('TriggerHeader',None),('ChangesHeader',84)]:
    if width:
        cell,_=add(unreal.SizeBox,name+'Cell',header)
        cell.set_width_override(width)
        value,_=label(add,name,cell,size=13)
    else:
        value,slot=label(add,name,header,size=13)
        slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
    if name=='ChangesHeader':value.set_editor_property('justification',unreal.TextJustify.RIGHT)
scroll, slot = add(unreal.ListView, "RunRows", list_body)
style_scrollbar(scroll)
slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
scroll.set_editor_property('entry_widget_class', load('WBP_HistoryRow'))
label(add, "EmptyState", root)
separator_size,_=add(unreal.SizeBox,'HistorySeparatorSize',content)
separator_size.slot.set_auto_size(True)
separator_size.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
separator,_=add(unreal.Border,'HistorySeparator',separator_size)
separator.set_padding(unreal.Margin(0))
separator.set_brush_color(color('line'))
detail_size, _ = add(unreal.SizeBox, "DetailSize", content)
detail_size.slot.set_auto_size(True)
detail_scroll, _ = add(unreal.ListView, "DetailRows", detail_size)
style_scrollbar(detail_scroll)
detail_scroll.set_editor_property('entry_widget_class', load('WBP_HistoryDetailRow'))
functions = {
    "HasObject": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "InitializeHistory": ([("Logbook", load("BP_Logbook")), ("Texts", load("BP_PrioritySettings"))], [("Result", "bool")]),
    "RefreshHistory": ([], [("Result", "bool")]),
    "ApplyLayout": ([("Width", "float"), ("Height", "float")], [("Result", "bool")]),
    "ShutdownView": ([], [("Result", "bool")]),
    "AddDetail": ([("Title", "string"), ("Detail", "string"), ("Kind", "name"), ("Index", "int")], [("Result", "bool")]),
    "BuildMetrics": ([], [("Result", "bool")]),
    "TypeLabel": ([("Type", "name")], [("Value", "string")]),
    "RenderRows": ([], [("Result", "bool")]),
    "StatusFor": ([("Index", "int")], [("Value", "name")]),
    "StatusLabel": ([("Index", "int")], [("Value", "string")]),
    "RunClicked": ([("Item", unreal.Object.static_class())], [("Result", "bool")]),
    "DetailClicked": ([("Item", unreal.Object.static_class())], [("Result", "bool")]),
    "OnRunClicked": ([("Item", unreal.Object.static_class())], []),
    "RunSelectionChanged": ([("Item", unreal.Object.static_class()), ("bIsSelected","bool")], [("Result","bool")]),
    "OnRunSelectionChanged": ([("Item", unreal.Object.static_class()), ("bIsSelected","bool")], []),
    "OnDetailClicked": ([("Item", unreal.Object.static_class())], []),
    "ClearView": ([], [("Result", "bool")]),
    "StoreAvailable": ([], [("Result", "bool")]),
    "CanReadStore": ([], [("Result", "bool")]),
    "SetProblemsOnly": ([("Enabled", "bool")], [("Result", "bool")]),
    "SelectRun": ([("RunId", "string")], [("Result", "bool")]),
    "SelectVisible": ([("Index", "int")], [("Result", "bool")]),
    "ExpandGroup": ([("GroupIndex", "int")], [("Result", "bool")]),
    "RefreshDetailPage": ([], [("Result", "bool")]),
    "BuildDetails": ([], [("Result", "bool")]),
    "SummaryText": ([("Index", "int")], [("Value", "string")]),
    "Timestamp": ([("Index", "int")], [("Value", "string")]),
    "ReasonLabel": ([("Reason", "string")], [("Value", "string")]),
    "ReadNumber": ([("Field", "name"), ("Index", "int")], [("Value", "int")]),
    "ReadKnown": ([("Field", "name"), ("Index", "int")], [("Value", "bool")]),
    "ReadText": ([("Field", "name"), ("Index", "int")], [("Value", "string")]),
    "KnownNumber": ([("Field", "name"), ("Known", "name"), ("Index", "int")], [("Value", "string")]),
    **{n: ([], [("Result", "bool")]) for n in ("ShowAll", "ShowProblems", "GroupChanged", "PreviousPage", "NextPage")},
}
object_array_variable(bp, 'RunItems', unreal.Object.static_class())
object_array_variable(bp, 'DetailItems', unreal.Object.static_class())
object_array_variable(bp, 'MetricChildren', unreal.Object.static_class())
graphs = declare(bp, {"bool": "Initialized ProblemsOnly HasCache HasStatusCache Updating WaitingForStore", "int": "CachedRevision ViewBuildCount SelectedRunIndex SelectedGroup DetailPage DetailTotal DetailVisibleCount DetailStart",
    "string": "SelectedRunId CachedIdentity DisplayLanguage CachedStatus Scratch", "int[]": "VisibleRuns"}, functions,
    {"Logbook": load("BP_Logbook"), "Texts": load("BP_PrioritySettings"), "Store": load("BP_LogbookStore")})
L = lambda n: prop("BPLogbook",g("Logbook"),n)
S = lambda n: prop("BPLogbookStore",g("Store"),n)
T = lambda expr: invoke("BPPrioritySettings",g("Texts"),"Text",":Key "+expr)
U = lambda key: T('"'+key+'"')
cat = lambda a,b: f'(Utilities|String|Append :A {a} :B {b})'
number_text_node = next(n for n in BP.find_node_types(graphs['KnownNumber'], '', []) if n.endswith('|ToText(Integer)'))
string = lambda x: text_string(f'({number_text_node} :Value {x})')
newline = '"\n"'
read = lambda f,i=None: f'(CallFunction|ReadNumber :Field "{f}" :Index {i or g("SelectedRunIndex")})'
readtext = lambda f,i=None: f'(CallFunction|ReadText :Field "{f}" :Index {i or g("SelectedRunIndex")})'
list_call = lambda fn, name, args='': f'({native(graphs["RefreshHistory"], fn, "ListView")} :self {g(name)} {args})'
item_prop = lambda n, item='item': prop('BPUIListItem', item, n)
item_put = lambda n, value, item='item': invoke('BPUIListItem', item, 'Set'+n, ':'+n+' '+value)
button_color = next(n for n in BP.find_node_types(graphs['SetProblemsOnly'],'SetBackgroundColor',[]) if any(p.name == 'InBackgroundColor' for p in BP.get_node_type_pins(graphs['SetProblemsOnly'],n).input_pins) and any('Button Object' in str(p.type_id) for p in BP.get_node_type_pins(graphs['SetProblemsOnly'],n).input_pins))
make_color = next(n for n in BP.find_node_types(graphs['SetProblemsOnly'],'',[]) if n.endswith('|MakeLinearColor'))
code = {}
code["HasObject"] = '(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code['StoreAvailable'] = f'''(fn StoreAvailable ()
    (if (not {g('Initialized')}) (return false))
    (if (not {L('Ready')}) (return false))
    (if (not (Utilities|Array|IsValidIndex {L('Stores')} {L('ActiveWorkspace')})) (return false))
    (if (and (> {L('Stage')} 0) (== {L('WorkWorkspace')} {L('ActiveWorkspace')})) (return false))
    (return true))'''
code['CanReadStore'] = f'''(fn CanReadStore ()
    (if (not (CallFunction|StoreAvailable)) (return false))
    (if (or (not {g('HasCache')}) (!= {g('CachedRevision')} {L('HistoryRevision')})) (return false))
    (return (and (== {g('Store')} {at(L('Stores'),L('ActiveWorkspace'))})
      (Utilities|String|EqualExactly(String) {g('CachedIdentity')} {L('ActiveIdentity')}))))'''
code["InitializeHistory"] = f'''(fn InitializeHistory (Logbook Texts)
    (if (not (and (CallFunction|HasObject :Object Logbook) (CallFunction|HasObject :Object Texts))) (return false))
    {put('Logbook','Logbook')} {put('Texts','Texts')} {put('Initialized','true')} {put('HasCache','false')}
    {put('SelectedRunId','""')} {put('SelectedRunIndex','-1')} {put('SelectedGroup','-1')}
    (bind refreshed (CallFunction|RefreshHistory)) (return refreshed))'''
numbers = "Reserve ConfirmedChanges ConfirmedFires ConfirmedHires ActiveSupportedBuildings PausedBuildings UnsupportedBuildings ConfirmedMinimumCrews FreeEligibleResidents StartedYear StartedMonth StartedDay StartedHour StartedMinute StartedSecond StartedMillisecond GroupReasonsOffsets GroupReasonsLengths GroupTypesOffsets GroupCountsOffsets GroupStartsOffsets GroupIdCountsOffsets AffectedBuildingIdsOffsets AffectedBuildingIdsLengths"
for fn, fields, default in (("ReadNumber", numbers.split(), "0"), ("ReadKnown", "CountsKnown StaffingKnown WorkersKnown ReserveKnown ReserveSatisfied StrictMode ConfirmationWindowKnown".split(), "false")):
    code[fn] = f'(fn {fn} (Field Index) ' + ' '.join(f'(if (== Field "{n}") (if (Utilities|Array|IsValidIndex {S(n)} Index) (return {at(S(n),"Index")})) (return {default}))' for n in fields) + f' (return {default}))'
code['ReadText'] = '(fn ReadText (Field Index) '+ ' '.join(f'(if (== Field "{n}") (if (Utilities|Array|IsValidIndex {S(n)} Index) (return '+(at(S(n),'Index') if n in ('RunId','SaveIdentity') else f'(Utilities|String|ToString(Name) {at(S(n),"Index")})')+')) (return ""))' for n in ('RunId','SaveIdentity','Trigger','Outcome','Failure'))+' (return ""))'
code['KnownNumber'] = f'''(fn KnownNumber (Field Known Index)
    (if (not (CallFunction|ReadKnown :Field Known :Index Index)) (bind unknown {U('history.unavailable')}) (return unknown))
    (bind count (CallFunction|ReadNumber :Field Field :Index Index)) (return {string('count')}))'''
code['ReasonLabel'] = f'''(fn ReasonLabel (Reason)
    (bind key {cat('"reason."','Reason')}) (bind translated {T('key')})
    (if (Utilities|String|EqualExactly(String) key translated) (bind missing {U('history.unavailable')}) (return missing))
    (return translated))'''
# The native text conversion consumes UTC DateTime and uses the local timezone.
date_candidates = [n for n in BP.find_node_types(graphs['Timestamp'], '', []) if 'DateTime' in n and any(p.name == 'InTimeZone' for p in BP.get_node_type_pins(graphs['Timestamp'],n).input_pins)]
assert len(date_candidates) == 1, date_candidates
date_node = date_candidates[0]
date_arg = "InDateTime"
def date_style_args(node, *styles):
    pins = {p.name for p in BP.get_node_type_pins(graphs['Timestamp'], node).input_pins}
    args = []
    for style in styles:
        pin = next((name for name in ('In'+style, style) if name in pins), None)
        assert pin is not None, (node, style, sorted(pins))
        args.append(f':{pin} "Short"')
    return ' '.join(args)

date_styles = date_style_args(date_node, 'DateStyle', 'TimeStyle')
date = '(Math|DateTime|MakeDateTime '+' '.join(':'+n+' '+read('Started'+n,'Index') for n in ('Year','Month','Day','Hour','Minute','Second','Millisecond'))+')'
timestamp_nodes = BP.find_node_types(graphs['Timestamp'], '', [])
def timezone_formatter(style, excluded):
    for node in timestamp_nodes:
        if not node.rsplit('|',1)[-1].replace(' ','').startswith(('AsDate(', 'AsTime(', 'ToText(Date)', 'ToText(Time)')):
            continue
        pins = {p.name for p in BP.get_node_type_pins(graphs['Timestamp'],node).input_pins}
        if {'InDateTime','InTimeZone'}.issubset(pins) and any(p in pins for p in ('In'+style,style)) and not any(p in pins for p in ('In'+excluded,excluded)):
            return node
    return None
date_only = timezone_formatter('DateStyle','TimeStyle')
time_only = timezone_formatter('TimeStyle','DateStyle')
unreal.log('WO_HISTORY_DATE_NODES '+str((date_only,time_only)))
relative_date = ''
if date_only and time_only:
    subtract_day = next(n for n in timestamp_nodes if n.rsplit('|',1)[-1].replace(' ','') == 'DateTime-Timespan')
    # Stored timestamps are UTC. Native Now is local wall time; formatting its
    # calendar date in UTC prevents a second timezone shift. Subtracting a day
    # from wall time handles 23/25-hour daylight-saving days correctly.
    date_key = text_string(f'({date_only} :InDateTime {date})')
    today_key = text_string(f'({date_only} :InDateTime localNow :InTimeZone "UTC")')
    yesterday_key = text_string(f'({date_only} :InDateTime ({subtract_day} :A localNow :B (Math|Timespan|MakeTimespan :Days 1)) :InTimeZone "UTC")')
    local_time = text_string(f'({time_only} :InDateTime {date} {date_style_args(time_only, "TimeStyle")})')
    relative_date = f'''(bind localNow (Math|DateTime|Now))
      (bind dateKey {date_key})
      (if (Utilities|String|EqualExactly(String) dateKey {today_key})
        (bind relative {cat(U('history.today'),cat('", "',local_time))}) (return relative))
      (if (Utilities|String|EqualExactly(String) dateKey {yesterday_key})
        (bind relative {cat(U('history.yesterday'),cat('", "',local_time))}) (return relative))'''
code['Timestamp'] = f'''(fn Timestamp (Index)
    (if (or (< {read('StartedYear','Index')} 1) (> {read('StartedYear','Index')} 9999)) (bind unknown {U('history.unavailable')}) (return unknown))
    (if (or (< {read('StartedMonth','Index')} 1) (> {read('StartedMonth','Index')} 12)) (bind unknown {U('history.unavailable')}) (return unknown))
    (if (or (< {read('StartedDay','Index')} 1) (> {read('StartedDay','Index')} 31)) (bind unknown {U('history.unavailable')}) (return unknown))
    {relative_date}
    (bind formatted {text_string(f'({date_node} :{date_arg} {date} {date_styles})')}) (return formatted))'''
code['SummaryText'] = f'''(fn SummaryText (Index)
    (bind outcome (CallFunction|StatusLabel :Index Index))
    (bind trigger {T(cat('"trigger."',readtext('Trigger','Index')))})
    (bind timestamp (CallFunction|Timestamp :Index Index))
    (bind changes (CallFunction|KnownNumber :Field "ConfirmedChanges" :Known "ConfirmationWindowKnown" :Index Index))
    (return {cat(cat(cat('timestamp',cat('" | "','trigger')),cat('" | "','outcome')),cat('" | "','changes'))}))'''
code['SetProblemsOnly'] = f'''(fn SetProblemsOnly (Enabled)
    (if (== Enabled {g('ProblemsOnly')}) (return true))
    {' '.join(f'({button_color} :self {g(name)} :InBackgroundColor ({make_color} :R (select {condition} {color("sel").r} {color("surface").r}) :G (select {condition} {color("sel").g} {color("surface").g}) :B (select {condition} {color("sel").b} {color("surface").b}) :A 1.0))' for name,condition in [('AllFilter','(not Enabled)'),('ProblemsFilter','Enabled')])}
    {put('ProblemsOnly','Enabled')} {put('HasCache','false')} (bind refreshed (CallFunction|RefreshHistory)) (return refreshed))'''
code['ShowAll'] = '(fn ShowAll () (bind changed (CallFunction|SetProblemsOnly :Enabled false)) (return changed))'
code['ShowProblems'] = '(fn ShowProblems () (bind changed (CallFunction|SetProblemsOnly :Enabled true)) (return changed))'
code['ClearView'] = f'''(fn ClearView ()
    (Utilities|Array|Clear {g('VisibleRuns')}) {put('SelectedRunIndex','-1')}
    (Utilities|Array|Clear {g('RunItems')}) (Utilities|Array|Clear {g('DetailItems')})
    (Utilities|Array|Clear {g('MetricChildren')})
    {list_call('ClearListItems','RunRows')} {list_call('ClearListItems','DetailRows')}
    {set_label('EmptyState','""')} {put('HasCache','false')} (return true))'''
code['ShutdownView'] = f'''(fn ShutdownView () (CallFunction|ClearView)
    {put('SelectedRunId','""')} {put('Initialized','false')} {put('HasStatusCache','false')} (return true))'''
code['StatusFor'] = f'''(fn StatusFor (Index)
    (bind outcome {readtext('Outcome','Index')})
    (if (Utilities|String|EqualExactly(String) outcome "completed")
      (for offset (range {read('GroupReasonsLengths','Index')})
        (bind reason (Utilities|String|ToString(Name) {at(S('GroupReasons'), '(+ '+read('GroupReasonsOffsets','Index')+' offset)')}))
        (if (not (or (Utilities|String|EqualExactly(String) reason "preserved_paused") (Utilities|String|EqualExactly(String) reason "preserved_unsupported"))) (return "problems")))
      (return "completed"))
    (if (or (Utilities|String|EqualExactly(String) outcome "aborted") (Utilities|String|EqualExactly(String) outcome "cancelled")) (return "aborted"))
    (bind failure {readtext('Failure','Index')})
    {' '.join(f'(if (Utilities|String|EqualExactly(String) failure "{reason}") (return "error"))' for reason in ('invalid_plan','invalid_snapshot','invalid_phase','configuration_unavailable','builder_score_unavailable','reserve_configuration_failed','observation_unavailable'))}
    (return "problems"))'''
code['StatusLabel']=f'''(fn StatusLabel (Index)
    (bind status (CallFunction|StatusFor :Index Index))
    (if (== status "problems") (bind label {U('history.problems')}) (return label))
    (if (== status "error") (bind label {U('history.failed')}) (return label))
    (if (== status "aborted") (bind label {U('history.cancelled')}) (return label))
    (bind label {U('history.completed')}) (return label))'''
code['RenderRows'] = f'''(fn RenderRows ()
    (Utilities|Array|Clear {g('RunItems')})
    (for offset (range {length(g('VisibleRuns'))})
      (bind index {at(g('VisibleRuns'),'offset')})
      (bind item (Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self self))
      {item_put('Owner','self')} {item_put('RunId',readtext('RunId','index'))}
      {item_put('Revision',g('CachedRevision'))} {item_put('Index','index')}
      {item_put('Kind','"run"')} {item_put('Status','(CallFunction|StatusFor :Index index)')}
      {item_put('Title',text('(CallFunction|StatusLabel :Index index)'))}
      {item_put('Subtitle',text('(CallFunction|Timestamp :Index index)'))}
      {item_put('Detail',text(T(cat('"trigger."',readtext('Trigger','index')))))}
      {item_put('Count',read('ConfirmedChanges','index'))} {item_put('Known','(CallFunction|ReadKnown :Field "ConfirmationWindowKnown" :Index index)')}
      (Utilities|Array|Add {g('RunItems')} item))
    {list_call('SetListItems','RunRows',':InListItems '+g('RunItems'))} (return true))'''
code['RefreshHistory'] = f'''(fn RefreshHistory ()
    (if (not {g('Initialized')}) (return false))
    (bind manager (Class|Backbone|GetLocManager))
    (if (CallFunction|HasObject :Object manager)
      (bind language (Class|LocManager|GetActiveLanguage :self manager))
      (if (not (Utilities|String|EqualExactly(String) language {g('DisplayLanguage')})) {put('DisplayLanguage','language')} {put('HasCache','false')} {put('HasStatusCache','false')}))
    (bind status (Utilities|String|ToString(Name) {L('PersistenceStatus')}))
    (if (or (not {g('HasStatusCache')}) (not (Utilities|String|EqualExactly(String) status {g('CachedStatus')})))
      {set_label('StorageState',T(cat('"storage."','status')))} {put('CachedStatus','status')} {put('HasStatusCache','true')})
    (if (not {L('Ready')})
      (if (not {g('WaitingForStore')}) (CallFunction|ClearView) {put('WaitingForStore','true')}) (return false))
    {put('WaitingForStore','false')}
    (if (not (CallFunction|StoreAvailable)) (return false))
    {put('Store',at(L('Stores'),L('ActiveWorkspace')))}
    (if (not (CallFunction|HasObject :Object {g('Store')})) (return false))
    (if (and {g('HasCache')} (and (== {L('HistoryRevision')} {g('CachedRevision')}) (Utilities|String|EqualExactly(String) {L('ActiveIdentity')} {g('CachedIdentity')}))) (return true))
    (if (not (Utilities|String|EqualExactly(String) {L('ActiveIdentity')} {g('CachedIdentity')}))
      {put('SelectedRunId','""')} {put('SelectedRunIndex','-1')})
    {put('CachedIdentity',L('ActiveIdentity'))} {put('CachedRevision',L('HistoryRevision'))}
    {put('HasCache','true')} {put('ViewBuildCount',f'(+ {g("ViewBuildCount")} 1)')}
    (Utilities|Array|Clear {g('VisibleRuns')})
    (for offset (range 50)
      (bind index (- (- {length(S('RunId'))} 1) offset))
      (if (>= index 0)
        (if (or (not {g('ProblemsOnly')}) (or (not (Utilities|String|EqualExactly(String) {readtext('Outcome','index')} "completed")) (> {read('GroupReasonsLengths','index')} 0)))
          (Utilities|Array|Add {g('VisibleRuns')} index))))
    {set_label('AllFilterText',U('history.all'))} {set_label('ProblemsFilterText',U('history.problems'))}
    {' '.join(set_label(name,U(key)) for name,key in [('ResultHeader','history.result'),('TimestampHeader','history.time'),('TriggerHeader','history.trigger'),('ChangesHeader','history.changes')])}
    {set_label('EmptyState',U('history.empty'))}
    (if (== {length(g('VisibleRuns'))} 0) {visibility('EmptyState','Visible')} (else {visibility('EmptyState','Collapsed')}))
    (CallFunction|RenderRows)
    (if (> (Utilities|String|Len {g('SelectedRunId')}) 0) (CallFunction|SelectRun :RunId {g('SelectedRunId')})
      (else (Utilities|Array|Clear {g('DetailItems')}) {list_call('ClearListItems','DetailRows')}))
    (return true))'''
code['SelectVisible'] = f'''(fn SelectVisible (Index)
    (if (not (CallFunction|CanReadStore)) (return false))
    (if (not (Utilities|Array|IsValidIndex {g('VisibleRuns')} Index)) (return false))
    (bind chosen (CallFunction|SelectRun :RunId {at(S('RunId'),at(g('VisibleRuns'),'Index'))})) (return chosen))'''
code['SelectRun'] = f'''(fn SelectRun (RunId)
    (if (not (CallFunction|CanReadStore)) (return false))
    {put('SelectedRunIndex',f'(Utilities|Array|FindItem {S("RunId")} RunId)')}
    (bind visibleIndex (Utilities|Array|FindItem {g('VisibleRuns')} {g('SelectedRunIndex')}))
    (if (or (< {g('SelectedRunIndex')} 0) (< visibleIndex 0))
      {put('SelectedRunId','""')} {put('SelectedRunIndex','-1')}
      {put('Updating','true')} {list_call('ClearSelection','RunRows')} {put('Updating','false')}
      (Utilities|Array|Clear {g('DetailItems')}) {list_call('ClearListItems','DetailRows')} (return false))
    {put('SelectedRunId','RunId')} {put('SelectedGroup','-1')} {put('DetailPage','0')} {put('DetailTotal','0')} {put('DetailVisibleCount','0')}
    {put('Updating','true')} {list_call('SetSelectedItem','RunRows',':Item '+at(g('RunItems'),'visibleIndex'))} {put('Updating','false')}
    (bind built (CallFunction|BuildDetails)) (return built))'''
details = [('history.changes','ConfirmedChanges','ConfirmationWindowKnown'),('history.hires','ConfirmedHires','ConfirmationWindowKnown'),('history.fires','ConfirmedFires','ConfirmationWindowKnown'),('history.active','ActiveSupportedBuildings','CountsKnown'),('history.paused','PausedBuildings','CountsKnown'),('history.unsupported','UnsupportedBuildings','CountsKnown'),('history.minimum','ConfirmedMinimumCrews','StaffingKnown'),('history.free','FreeEligibleResidents','WorkersKnown'),('history.reserve','Reserve','ReserveKnown')]
detail_lines = []
for k, field, known in details[3:]:
    value = f'(CallFunction|KnownNumber :Field "{field}" :Known "{known}" :Index {g("SelectedRunIndex")})'
    detail_lines.append(f'(CallFunction|AddDetail :Title {U(k)} :Detail {value} :Kind (select (CallFunction|ReadKnown :Field "{known}" :Index {g("SelectedRunIndex")}) "aggregate" "unavailable") :Index -1)')
metric_children=[]
for metric_index,(key,field,known) in enumerate(details[:3]):
    child='metricChild'+str(metric_index)
    metric_children.append(f'''(bind {child} (Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self self))
      {item_put('Title',text(U(key)),child)}
      {item_put('Known',f'(CallFunction|ReadKnown :Field "{known}" :Index {g("SelectedRunIndex")})',child)}
      {item_put('Kind','(select '+prop('BPUIListItem',child,'Known')+' "metric" "unavailable")',child)}
      {item_put('Detail',text(f'(CallFunction|KnownNumber :Field "{field}" :Known "{known}" :Index {g("SelectedRunIndex")})'),child)}
      (Utilities|Array|Add {g('MetricChildren')} {child})''')
code['BuildMetrics']=f'''(fn BuildMetrics ()
    (if (not (CallFunction|CanReadStore)) (return false))
    (Utilities|Array|Clear {g('MetricChildren')}) {' '.join(metric_children)}
    (bind item (Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self self))
    {item_put('Owner','self')} {item_put('RunId',g('SelectedRunId'))} {item_put('Revision',g('CachedRevision'))}
    {item_put('Kind','"metrics"')} {item_put('Children',g('MetricChildren'))}
    (Utilities|Array|Add {g('DetailItems')} item) (return true))'''
types=prop('BPPrioritySettings',g('Texts'),'KnownTypes')
type_keys=prop('BPPrioritySettings',g('Texts'),'KnownTypeStringKeys')
code['TypeLabel']=f'''(fn TypeLabel (Type)
    (bind index (Utilities|Array|FindItem {types} Type))
    (if (not (Utilities|Array|IsValidIndex {type_keys} index)) (bind label {U('history.unavailable')}) (return label))
    (bind key {at(type_keys,'index')})
    (bind label {invoke('BPPrioritySettings',g('Texts'),'ResolveLabel',':Key Type :StringKey key')})
    (if (or (Utilities|String|EqualExactly(String) label (Utilities|String|ToString(Name) Type)) (Utilities|String|EqualExactly(String) label key))
      (bind missing {U('history.unavailable')}) (return missing)) (return label))'''
code['AddDetail'] = f'''(fn AddDetail (Title Detail Kind Index)
    (bind item (Game|ConstructObjectfromClass :Class "{ROOT}/BP_UIListItem.BP_UIListItem_C" :self self))
    {item_put('Owner','self')} {item_put('RunId',g('SelectedRunId'))} {item_put('Revision',g('CachedRevision'))}
    {item_put('Title',text('Title'))} {item_put('Detail',text('Detail'))}
    {item_put('Kind','Kind')} {item_put('Index','Index')}
    (if (== Kind "header") {item_put('Status','(CallFunction|StatusFor :Index '+g('SelectedRunIndex')+')')})
    (Utilities|Array|Add {g('DetailItems')} item) (return true))'''
code['BuildDetails'] = f'''(fn BuildDetails ()
    (if (not (CallFunction|CanReadStore)) (return false))
    (Utilities|Array|Clear {g('DetailItems')})
    (bind timestamp (CallFunction|Timestamp :Index {g('SelectedRunIndex')}))
    (bind trigger {T(cat('"trigger."',readtext('Trigger')))})
    (CallFunction|AddDetail :Title (CallFunction|StatusLabel :Index {g('SelectedRunIndex')}) :Detail {cat('timestamp',cat('" · "','trigger'))} :Kind "header" :Index -1)
    (CallFunction|BuildMetrics)
    (bind failure {readtext('Failure')})
    (if (and (> (Utilities|String|Len failure) 0) (not (Utilities|String|EqualExactly(String) failure "None")))
      (CallFunction|AddDetail :Title (CallFunction|ReasonLabel :Reason failure) :Detail "" :Kind "reason" :Index -1))
    (CallFunction|AddDetail :Title {U('history.groups')} :Detail "" :Kind "section" :Index -1)
    (for offset (range {read('GroupReasonsLengths')})
      (bind index (+ {read('GroupReasonsOffsets')} offset))
      (bind reason (Utilities|String|ToString(Name) {at(S('GroupReasons'),'index')}))
      (bind countIndex (+ {read('GroupCountsOffsets')} offset))
      (bind count {string(at(S('GroupCounts'),'countIndex'))})
      (bind typeIndex (+ {read('GroupTypesOffsets')} offset))
      (bind type {at(S('GroupTypes'),'typeIndex')})
      (bind label (CallFunction|TypeLabel :Type type))
      (bind groupDetail (select (== type "None") count {cat('label',cat('" · "','count'))}))
      (CallFunction|AddDetail :Title (CallFunction|ReasonLabel :Reason reason) :Detail groupDetail :Kind "group" :Index offset))
    {' '.join(detail_lines)}
    {' '.join(f'(CallFunction|AddDetail :Title {U(key)} :Detail {U("history.unavailable")} :Kind "unavailable" :Index -1)' for key in ('history.residents','history.professions','history.assignments','history.per_building'))}
    {list_call('SetListItems','DetailRows',':InListItems '+g('DetailItems'))}
    (return true))'''
group_start = at(S('GroupStarts'), '(+ ' + read('GroupStartsOffsets') + ' GroupIndex)')
code['ExpandGroup'] = f'''(fn ExpandGroup (GroupIndex)
    (if (not (CallFunction|CanReadStore)) (return false))
    (if (or (< GroupIndex 0) (>= GroupIndex {read('GroupReasonsLengths')})) (return false))
    {put('SelectedGroup','GroupIndex')} {put('DetailPage','0')}
    {put('DetailTotal',at(S('GroupIdCounts'),f'(+ {read("GroupIdCountsOffsets")} GroupIndex)'))}
    {put('DetailStart','(+ ' + read('AffectedBuildingIdsOffsets') + ' ' + group_start + ')')}
    (bind refreshed (CallFunction|RefreshDetailPage)) (return refreshed))'''
# Preserve bounded legacy page-reader entry points, but never expose IDs or guessed
# current-settlement names as historical building/person information.
code['RefreshDetailPage'] = f'''(fn RefreshDetailPage ()
    (if (not (CallFunction|CanReadStore)) (return false))
    {put('DetailVisibleCount','0')}
    (for offset (range 25)
      (bind local (+ (* {g('DetailPage')} 25) offset))
      (if (< local {g('DetailTotal')}) {put('DetailVisibleCount',f'(+ {g("DetailVisibleCount")} 1)')}))
    (CallFunction|BuildDetails)
    (if (>= {g('SelectedGroup')} 0)
      (CallFunction|AddDetail :Title {U('history.per_building')} :Detail {U('history.unavailable')} :Kind "unavailable" :Index -1)
      {list_call('SetListItems','DetailRows',':InListItems '+g('DetailItems'))})
    (return true))'''
code['PreviousPage'] = f'''(fn PreviousPage () (if (not (CallFunction|CanReadStore)) (return false)) (if (<= {g('DetailPage')} 0) (return false)) {put('DetailPage',f'(- {g("DetailPage")} 1)')} (bind changed (CallFunction|RefreshDetailPage)) (return changed))'''
code['NextPage'] = f'''(fn NextPage () (if (not (CallFunction|CanReadStore)) (return false)) (if (>= (* (+ {g('DetailPage')} 1) 25) {g('DetailTotal')}) (return false)) {put('DetailPage',f'(+ {g("DetailPage")} 1)')} (bind changed (CallFunction|RefreshDetailPage)) (return changed))'''
code['GroupChanged'] = '(fn GroupChanged () (return false))'
for fn, action in [('RunClicked',f'(CallFunction|SelectRun :RunId {item_prop("RunId")})'),
                   ('DetailClicked',f'(CallFunction|ExpandGroup :GroupIndex {item_prop("Index")})')]:
    code[fn] = f'''(fn {fn} (Item)
      (if (not (CallFunction|CanReadStore)) (return false))
      (bind item (Utilities|Casting|CastToBP_UIListItem :Object Item) (:then
        (if (!= {item_prop('Revision')} {g('CachedRevision')}) (return false))
        (if (!= {item_prop('Owner')} self) (return false))
        {'(if (!= '+item_prop('Kind')+' "group") (return false))' if fn == 'DetailClicked' else ''}
        {'(if (not (Utilities|String|EqualExactly(String) '+item_prop('RunId')+' '+g('SelectedRunId')+')) (return false))' if fn == 'DetailClicked' else ''}
        (bind changed {action}) (return changed))
        (:CastFailed (return false))))'''
def size_call(method, name, value):
    return f'({native(graphs["ApplyLayout"], method, "SizeBox")} :self {g(name)} :In'+method.removeprefix('Set')+' '+value+')'
slot_node = native(graphs['ApplyLayout'],'SlotAsCanvasSlot')
position = native(graphs['ApplyLayout'],'SetPosition','CanvasPanelSlot')
vector = '(Math|Vector2D|MakeVector2D :X {x} :Y {y})'
def move(name, x, y):
    return f'({position} :self ({slot_node} :Widget {g(name)}) :InPosition '+vector.format(x=x,y=y)+')'
code['ApplyLayout'] = f'''(fn ApplyLayout (Width Height)
    (bind available (select (> Height 52.0) (- Height 52.0) 0.0))
    (if (>= Width 920.0)
      (bind requested (* Width 0.46))
      (bind left (select (< requested 560.0) 560.0 (select (> requested 680.0) 680.0 requested)))
      {size_call('SetWidthOverride','ListSize','left')} {size_call('SetHeightOverride','ListSize','available')}
      {size_call('SetWidthOverride','HistorySeparatorSize','1.0')} {size_call('SetHeightOverride','HistorySeparatorSize','available')}
      {move('HistorySeparatorSize','left','0.0')}
      {size_call('SetWidthOverride','DetailSize','(- (- Width left) 1.0)')} {size_call('SetHeightOverride','DetailSize','available')}
      {move('DetailSize','(+ left 1.0)','0.0')}
      (else
        {size_call('SetWidthOverride','ListSize','Width')} {size_call('SetHeightOverride','ListSize','192.0')}
        {size_call('SetWidthOverride','HistorySeparatorSize','Width')} {size_call('SetHeightOverride','HistorySeparatorSize','1.0')}
        {move('HistorySeparatorSize','0.0','192.0')}
        {size_call('SetWidthOverride','DetailSize','Width')} {size_call('SetHeightOverride','DetailSize','(select (> available 193.0) (- available 193.0) 0.0)')}
        {move('DetailSize','0.0','193.0')}))
    (return true))'''
code['OnRunClicked'] = '(fn OnRunClicked (Item) (CallFunction|RunClicked :Item Item) (return))'
code['RunSelectionChanged'] = f'''(fn RunSelectionChanged (Item bIsSelected)
    (if (or {g('Updating')} (not bIsSelected)) (return false))
    (if (not (CallFunction|HasObject :Object Item)) (return false))
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Item) (:then
      (if (Utilities|String|EqualExactly(String) {item_prop('RunId')} {g('SelectedRunId')}) (return false))
      (bind changed (CallFunction|RunClicked :Item Item)) (return changed))
      (:CastFailed (return false))))'''
code['OnRunSelectionChanged'] = '(fn OnRunSelectionChanged (Item bIsSelected) (CallFunction|RunSelectionChanged :Item Item :bIsSelected bIsSelected) (return))'
code['OnDetailClicked'] = '(fn OnDetailClicked (Item) (CallFunction|DetailClicked :Item Item) (return))'
emit(bp, graphs, code)
events(bp, [("AllFilter","OnClicked","ShowAll",unreal.Button),
            ("ProblemsFilter","OnClicked","ShowProblems",unreal.Button),
            ('RunRows','BP_OnItemClicked','OnRunClicked',unreal.ListView,{'Item':'Item'}),
            ('RunRows','BP_OnItemSelectionChanged','OnRunSelectionChanged',unreal.ListView,{'Item':'Item','bIsSelected':'bIsSelected'}),
            ('DetailRows','BP_OnItemClicked','OnDetailClicked',unreal.ListView,{'Item':'Item'})])
BP.compile_blueprint(bp,warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_LOGBOOK_VIEW_GENERATED")
