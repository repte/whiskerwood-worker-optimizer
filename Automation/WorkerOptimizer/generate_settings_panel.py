"""Native settings shell; settings writes remain owned by the existing model."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
from ui_authoring import *

bp,add=widget('WBP_SettingsPanel',reset=True)
frame,_=add(unreal.Border,'PanelRoot')
frame.set_editor_property('background',nine_slice_brush('T_WorkerOptimizerFrame',16,6/16))
frame.set_brush_color(color('panel'))
frame.set_padding(unreal.Margin(0))
root,_=add(unreal.VerticalBox,'PanelContents',frame)
header_size,_=add(unreal.SizeBox,'HeaderSize',root)
header_size.set_height_override(96)
header_canvas,_=add(unreal.CanvasPanel,'HeaderCanvas',header_size)
header_background,slot=add(unreal.Border,'HeaderBackground',header_canvas)
header_background.set_brush_color(color('head'))
header_background.set_padding(unreal.Margin(0))
slot.set_anchors(unreal.Anchors(unreal.Vector2D(0,0),unreal.Vector2D(1,1)))
slot.set_offsets(unreal.Margin(0))
slot.set_z_order(-1)
title_size,_=add(unreal.SizeBox,'TitleSize',header_canvas)
title_size.slot.set_auto_size(True)
title_size.set_height_override(52)
title_bar,_=add(unreal.HorizontalBox,'TitleBar',title_size)
emblem,emblem_slot=add(unreal.Image,'TitleEmblem',title_bar)
emblem_texture=unreal.load_asset('/Game/Assets/Icons/BoardGameIcons/arrow_clockwise')
assert emblem_texture
emblem.set_brush_from_texture(emblem_texture,False)
emblem.set_desired_size_override(unreal.Vector2D(24,24))
emblem.set_color_and_opacity(GOLD)
emblem.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
emblem_slot.set_padding(unreal.Margin(24,0,8,0))
emblem_slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
title,slot=label(add,'PanelTitle',title_bar,'Worker Optimizer',20)
slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
slot.set_padding(unreal.Margin(0,8,12,8))
slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
close_size,_=add(unreal.SizeBox,'CloseSize',title_bar)
close_size.set_width_override(44)
button(add,'Close',close_size,'\u00d7')
tabs_size,_=add(unreal.SizeBox,'TabsSize',header_canvas)
tabs_size.slot.set_auto_size(True)
tabs_size.slot.set_position(unreal.Vector2D(0,52))
tabs_size.set_height_override(44)
tabs,_=add(unreal.HorizontalBox,'Tabs',tabs_size)
for name in ('GeneralTab','PrioritiesTab','LogbookTab'):
    control,slot=add(unreal.Button,name,tabs)
    control.set_editor_property('is_focusable',True)
    style=button_style(control.get_editor_property('widget_style'))
    empty=unreal.SlateBrush()
    empty.set_editor_property('draw_as',unreal.SlateBrushDrawType.NO_DRAW_TYPE)
    style.set_editor_property('normal',empty)
    style.set_editor_property('hovered',control_brush('hover','hover',width=0))
    style.set_editor_property('pressed',control_brush('sunken','sunken',width=0))
    style.set_editor_property('normal_padding',unreal.Margin(12,0,12,0))
    style.set_editor_property('pressed_padding',unreal.Margin(12,0,12,0))
    control.set_editor_property('widget_style',style)
    slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.AUTOMATIC))
    content,_=add(unreal.VerticalBox,name+'Content',control)
    tab_text,text_slot=label(add,name+'Text',content)
    text_slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
    text_slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
    underline_size,_=add(unreal.SizeBox,name+'UnderlineSize',content)
    underline_size.set_height_override(2)
    underline,_=add(unreal.Border,name+'Underline',underline_size)
    underline.set_padding(unreal.Margin(0))
    underline.set_brush_color(GOLD)
    underline.set_visibility(unreal.SlateVisibility.HIDDEN)
views,slot=add(unreal.WidgetSwitcher,'Views',root)
slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
scroll,_=add(unreal.ScrollBox,'ContentScroll',views)
style_scrollbar(scroll)
body_size,_=add(unreal.SizeBox,'GeneralBodySize',scroll)
body_size.set_max_desired_width(980)
general,_=add(unreal.VerticalBox,'General',body_size)

def band(name,label_name):
    border,_=add(unreal.Border,name+'Band',general)
    border.set_brush_color(SURFACE)
    border.set_padding(unreal.Margin(24,20,24,20))
    wrap,_=add(unreal.WrapBox,name+'Wrap',border)
    wrap.set_editor_property('explicit_wrap_size',True)
    wrap.set_editor_property('inner_slot_padding',unreal.Vector2D(0,12))
    left,_=add(unreal.SizeBox,name+'LabelSize',wrap)
    left.set_width_override(300)
    label(add,label_name,left,size=16)
    right,_=add(unreal.SizeBox,name+'ControlSize',wrap)
    right.set_width_override(632)
    controls,_=add(unreal.VerticalBox,name+'Controls',right)
    rule_size,rule_slot=add(unreal.SizeBox,name+'RuleSize',general)
    rule_size.set_height_override(1)
    rule_slot.set_padding(unreal.Margin(24,0,24,0))
    rule,_=add(unreal.Border,name+'Rule',rule_size)
    rule.set_padding(unreal.Margin(0))
    rule.set_brush_color(color('line'))
    return controls

reserve_controls=band('Reserve','ReserveLabel')
stepper_size,_=add(unreal.SizeBox,'ReserveStepperSize',reserve_controls)
stepper_size.set_width_override(120)
stepper_size.set_height_override(32)
stepper,_=add(unreal.HorizontalBox,'ReserveStepper',stepper_size)
for name,width in [('ReserveMinus',32),('ReserveInput',48),('ReservePlus',32)]:
    size,slot=add(unreal.SizeBox,name+'Size',stepper)
    size.set_width_override(width)
    size.set_height_override(32)
    if name!='ReservePlus':slot.set_padding(unreal.Margin(0,0,4,0))
    if name=='ReserveInput':
        reserve,_=add(unreal.EditableTextBox,name,size)
        input_style(reserve)
        style=reserve.get_editor_property('widget_style')
        text_style=style.get_editor_property('text_style')
        font_size(text_style,size=15)
        style.set_editor_property('text_style',text_style)
        style.set_editor_property('padding',unreal.Margin(4,2,4,2))
        reserve.set_editor_property('widget_style',style)
        reserve.set_editor_property('justification',unreal.TextJustify.CENTER)
    else:
        control,_=button(add,name,size,'\u2212' if name=='ReserveMinus' else '+')
        style=control.get_editor_property('widget_style')
        style.set_editor_property('normal_padding',unreal.Margin(0))
        style.set_editor_property('pressed_padding',unreal.Margin(0))
        control.set_editor_property('widget_style',style)
reserve_help,_=label(add,'ReserveHelp',reserve_controls,size=13)
reserve_help.set_color_and_opacity(unreal.SlateColor(color('text3')))
mode_controls=band('Mode','ModeLabel')
def choice_surface(name,parent,bottom=0):
    surface,slot=add(unreal.Border,name+'Surface',parent)
    surface.set_brush(control_brush('panel','line2'))
    surface.set_brush_color(unreal.LinearColor(1,1,1,1))
    surface.set_padding(unreal.Margin(4,4,4,4))
    if bottom:
        slot.set_padding(unreal.Margin(0,0,0,bottom))
    return surface
for name in ('StrictChoice','WeightedChoice'):
    choice,_=add(unreal.CheckBox,name,choice_surface(name,mode_controls,8))
    input_style(choice)
    label(add,name+'Text',choice,size=15)
mode_help,_=label(add,'ModeHelp',mode_controls,size=13)
mode_help.set_color_and_opacity(unreal.SlateColor(color('text3')))
auto_controls=band('Auto','AutoLabel')
chips,_=add(unreal.WrapBox,'AutoChips',auto_controls)
chips.set_editor_property('inner_slot_padding',unreal.Vector2D(8,8))
AUTO=[('AutoOff','off'),('AutoDay','day_start'),('Auto5','minutes_5'),('Auto10','minutes_10'),('Auto15','minutes_15')]
for name,_ in AUTO:
    choice,_=add(unreal.CheckBox,name,choice_surface(name,chips))
    input_style(choice)
    label(add,name+'Text',choice,size=15)
auto_help,_=label(add,'AutoHelp',auto_controls,size=13)
auto_help.set_color_and_opacity(unreal.SlateColor(color('text3')))
hotkey_controls=band('Hotkey','HotkeyLabel')
selector,_=add(unreal.InputKeySelector,'KeySelector',hotkey_controls)
selector.set_allow_modifier_keys(True)
selector.set_allow_gamepad_keys(False)
input_style(selector)
key_text_style=selector.get_editor_property('text_style')
font_size(key_text_style,size=15)
selector.set_editor_property('text_style',key_text_style)
selector.set_editor_property('no_key_specified_text',unreal.Text('\u2014'))
label(add,'HotkeyState',hotkey_controls,size=13)
add(load('WBP_PrioritiesView'),'PrioritiesHost',views)
add(load('WBP_LogbookView'),'HistoryHost',views)

# Reparenting during incremental authoring keeps widget IDs, but not sibling order.
templates={str(item.widget_name):item.widget for item in unreal.get_default_object(unreal.UMGToolSet).call_method('GetWidgets',args=(bp,)).widgets}
title_bar.clear_children()
for name in ('TitleEmblem','PanelTitle','CloseSize'):
    slot=title_bar.add_child(templates[name])
    slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
    if name=='TitleEmblem':slot.set_padding(unreal.Margin(24,0,8,0))
    if name=='PanelTitle':
        slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
        slot.set_padding(unreal.Margin(0,8,12,8))
general.clear_children()
for name in ('Reserve','Mode','Auto','Hotkey'):
    general.add_child(templates[name+'Band'])
    slot=general.add_child(templates[name+'RuleSize'])
    slot.set_padding(unreal.Margin(24,0,24,0))
mode_controls.clear_children()
for name in ('StrictChoiceSurface','WeightedChoiceSurface','ModeHelp'):
    slot=mode_controls.add_child(templates[name])
    if name!='ModeHelp':slot.set_padding(unreal.Margin(0,0,0,8))

if 'OnPanelChanged' not in {str(graph.get_name()) for graph in BP.list_event_dispatchers(bp)}:
    BP.add_event_dispatcher(bp,'OnPanelChanged')
functions={
 'HasObject':([('Object',unreal.Object.static_class())],[('Result','bool')]),
 'InitializePanel':([(n,load(cls)) for n,cls in [('Controller','BP_WorkerOptimizer'),('Model','BP_SettingsModel'),('Hotkey','BP_HotkeyConfig'),('Logbook','BP_Logbook')]],[('Result','bool')]),
 'OpenTab':([('Tab','name')],[('Result','bool')]),
 'ApplyPanelLayout':([('Width','float'),('Height','float')],[('Result','bool')]),
 'WriteOption':([('OptionId','string'),('Value','string')],[('Result','bool')]),
 'ChangeReserve':([('Delta','int')],[('Result','bool')]),
 'DesiredWidth':([('Widget',unreal.Widget.static_class())],[('Value','float')]),
 'KeyChanged':([('Chord',unreal.load_object(None,'/Script/Slate.InputChord'))],[('Result','bool')]),
 **{n:([],[('Result','bool')]) for n in ('ClosePanel','RefreshPanel','RefreshGeneral','RebuildLabels','SyncKey','IsCapturing','GeneralClicked','PrioritiesClicked','LogbookClicked','ReserveChanged','ReserveDecrement','ReserveIncrement','StrictChanged','WeightedChanged','ModeChanged','AutoChanged','BuildRows','SearchChanged','PreviousPage','NextPage')},
 **{name+'Changed':([],[('Result','bool')]) for name,_ in AUTO}}
brush_struct=unreal.load_object(None,'/Script/SlateCore.SlateBrush')
for name in ('SelectedChoiceBrush','NormalChoiceBrush'):
    if name not in BP.list_variables(bp):BP.add_struct_variable(bp,name,brush_struct)
graphs=declare(bp,{'bool':'Initialized PanelOpen Updating Narrow HasGeneralCache HasReserveCache CachedBusy CompactHeader','name':'ActiveTab','float':'LayoutWidth LayoutHeight HeaderHeight',
 'string':'DisplayLanguage CachedMode CachedReserve CachedAuto HotkeySlot CachedHotkeyState','string[]':'AutoValues ModeValues'},functions,
 {'Controller':load('BP_WorkerOptimizer'),'Model':load('BP_SettingsModel'),'Hotkey':load('BP_HotkeyConfig'),'Logbook':load('BP_Logbook')})
M=lambda n:prop('BPSettingsModel',g('Model'),n)
S=lambda fn,args='':invoke('BPPrioritySettings',M('Settings'),fn,args)
U=lambda key:S('Text',':Key "'+key+'"')
read=lambda key,fallback:invoke('BPSettingsModel',g('Model'),'ReadValue',':OptionId "'+key+'" :Fallback "'+fallback+'"')
edit=lambda fn,args='':f'({native(graphs["RefreshGeneral"],fn,"EditableTextBox")} :self {g("ReserveInput")} {args})'
check=lambda name,condition:f'({native(graphs["RefreshGeneral"],"SetIsChecked","CheckBox")} :self {g(name)} :InIsChecked {condition})'
enable=lambda name,condition:f'(Widget|SetIsEnabled :self {g(name)} :bInIsEnabled {condition})'
button_color=native(graphs['OpenTab'],'SetBackgroundColor','Button')
make_color=next(n for n in BP.find_node_types(graphs['OpenTab'],'',[]) if n.endswith('|MakeLinearColor'))
surface_brush_node=native(graphs['RefreshGeneral'],'SetBrush','Border')
surface_brush_pins={p.name for p in BP.get_node_type_pins(graphs['RefreshGeneral'],surface_brush_node).input_pins}
surface_brush_arg=next(name for name in ('Brush','InBrush') if name in surface_brush_pins)
def selected_surface(name,condition):
    return f'({surface_brush_node} :self {g(name+"Surface")} :{surface_brush_arg} (select {condition} {g("SelectedChoiceBrush")} {g("NormalChoiceBrush")}))'
def tint(key):
    c=color(key)
    return f'({make_color} :R {c.r} :G {c.g} :B {c.b} :A 1.0)'
code={}
code['HasObject']='(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code['InitializePanel']=f'''(fn InitializePanel (Controller Model Hotkey Logbook)
 (if (not (and (CallFunction|HasObject :Object Controller) (and (CallFunction|HasObject :Object Model) (and (CallFunction|HasObject :Object Hotkey) (CallFunction|HasObject :Object Logbook))))) (return false))
 {put('Controller','Controller')} {put('Model','Model')} {put('Hotkey','Hotkey')} {put('Logbook','Logbook')}
 (Class|BPSettingsModel|SetRunController :self Model :RunController Controller)
 {put('Initialized','true')} {put('HasReserveCache','false')}
 {invoke('WBPLogbookView',g('HistoryHost'),'InitializeHistory',':Logbook Logbook :Texts '+M('Settings'))}
 (CallFunction|RebuildLabels) (CallFunction|SyncKey) (CallFunction|ClosePanel) (return true))'''
code['OpenTab']=f'''(fn OpenTab (Tab)
 (if (not (or (== Tab "general") (or (== Tab "priorities") (== Tab "logbook")))) (return false))
 (if (and {g('PanelOpen')} (== Tab {g('ActiveTab')})) (return true))
 {invoke('WBPPrioritiesView',g('PrioritiesHost'),'ShutdownView')}
 {put('ActiveTab','Tab')} {put('PanelOpen','true')}
 (Widget|SetVisibility :self self :InVisibility "Visible")
 ({native(graphs['OpenTab'],'SetActiveWidgetIndex','WidgetSwitcher')} :self {g('Views')} :Index (select (== Tab "general") 0 (select (== Tab "priorities") 1 2)))
 {' '.join(f'({button_color} :self {g(name)} :InBackgroundColor (select (== Tab "{key}") {tint("sel")} {tint("surface")}))' for key,name in [('general','GeneralTab'),('priorities','PrioritiesTab'),('logbook','LogbookTab')])}
 {' '.join(f'(if (== Tab "{key}") (Widget|SetVisibility :self {g(name+"Underline")} :InVisibility "HitTestInvisible") (else (Widget|SetVisibility :self {g(name+"Underline")} :InVisibility "Hidden")))' for key,name in [('general','GeneralTab'),('priorities','PrioritiesTab'),('logbook','LogbookTab')])}
 (if (and {g('Initialized')} (== Tab "priorities")) {invoke('WBPPrioritiesView',g('PrioritiesHost'),'InitializePriorities',':Model '+g('Model'))})
 (CallFunction|RefreshPanel) (Default|CallOnPanelChanged :self self) (return true))'''
code['ClosePanel']=f'''(fn ClosePanel () {put('PanelOpen','false')}
 {invoke('WBPPrioritiesView',g('PrioritiesHost'),'ShutdownView')}
 (Widget|SetVisibility :self self :InVisibility "Collapsed") (Default|CallOnPanelChanged :self self) (return true))'''
for fn,tab in [('GeneralClicked','general'),('PrioritiesClicked','priorities'),('LogbookClicked','logbook')]:
    code[fn]=f'(fn {fn} () (bind opened (CallFunction|OpenTab :Tab "{tab}")) (return opened))'
labels=[('GeneralTabText','tab.general'),('PrioritiesTabText','tab.priorities'),('LogbookTabText','tab.logbook'),('ReserveLabel','reserve'),('ReserveHelp','reserve_desc'),('ModeLabel','mode'),('ModeHelp','mode_desc'),('StrictChoiceText','strict'),('WeightedChoiceText','weighted'),('AutoLabel','auto_assignment'),('AutoHelp','auto_assignment_desc'),('HotkeyLabel','hotkey')]+[(name+'Text','auto.'+value) for name,value in AUTO]
code['RebuildLabels']=f'''(fn RebuildLabels () {put('Updating','true')}
 {' '.join(set_label(name,U(key)) for name,key in labels)}
 {' '.join(f'(Widget|SetToolTipText :self {g(name)} :InToolTipText {text(U("reserve_desc"))})' for name in ('ReserveMinus','ReservePlus','ReserveInput'))}
 (Widget|SetToolTipText :self {g('KeySelector')} :InToolTipText {text(U('hotkey'))})
 {put('HasGeneralCache','false')} {put('Updating','false')} (return true))'''
code['RefreshGeneral']=f'''(fn RefreshGeneral ()
 (if (not {g('Initialized')}) (return false)) {put('Updating','true')}
 (bind mode {read('WorkerOptimizer.mode','WorkerOptimizer.ui.strict')})
 (bind reserve {read('WorkerOptimizer.reserve','1')})
 (bind auto {read('WorkerOptimizer.auto_assignment','WorkerOptimizer.ui.auto.off')})
 {check('StrictChoice',S('IsStrictValue',':Value mode'))} {check('WeightedChoice','(not '+S('IsStrictValue',':Value mode')+')')}
 {selected_surface('StrictChoice',S('IsStrictValue',':Value mode'))} {selected_surface('WeightedChoice','(not '+S('IsStrictValue',':Value mode')+')')}
 (if (or (not {g('HasReserveCache')}) (not (Utilities|String|EqualExactly(String) reserve {g('CachedReserve')})))
   {edit('SetText',':InText '+text('(Utilities|String|ToString(Integer) '+S('ParseReserve',':Value reserve')+')'))} {put('HasReserveCache','true')})
 (bind autoKey {S('ParseAutoMode',':Value auto')})
 {' '.join(check(name,'(== autoKey "'+value+'")') for name,value in AUTO)}
 {' '.join(selected_surface(name,'(== autoKey "'+value+'")') for name,value in AUTO)}
 {' '.join(enable(name,'(not '+M('Busy')+')') for name in ('StrictChoice','WeightedChoice','ReserveInput','ReserveMinus','ReservePlus'))}
 {' '.join(f'(Widget|SetToolTipText :self {g(name)} :InToolTipText {text("(select "+M("Busy")+" "+U("busy")+" "+U(key)+")")})' for name,key in [('StrictChoice','mode_desc'),('WeightedChoice','mode_desc'),('ReserveInput','reserve_desc'),('ReserveMinus','reserve_desc'),('ReservePlus','reserve_desc')])}
 {' '.join(enable(name,'true' if value=='off' else '(not '+M('Busy')+')') for name,value in AUTO)}
 (bind failure {prop('BPHotkeyConfig',g('Hotkey'),'FailureCode')})
 (bind dirty {prop('BPHotkeyConfig',g('Hotkey'),'Dirty')})
 (bind keyState (select dirty "unsaved_hotkey" (select (== failure "None") "" (select (== failure "invalid_hotkey") "invalid_hotkey" "default_hotkey"))))
 (if (Utilities|String|EqualExactly(String) keyState "") {set_label('HotkeyState','""')} (else {set_label('HotkeyState',S('Text',':Key keyState'))}))
 {put('CachedMode','mode')} {put('CachedReserve','reserve')} {put('CachedAuto','auto')} {put('CachedBusy',M('Busy'))}
 {put('HasGeneralCache','true')} {put('Updating','false')} (return true))'''
code['RefreshPanel']=f'''(fn RefreshPanel ()
 (if (or (not {g('Initialized')}) (not {g('PanelOpen')})) (return false))
 (Class|BPSettingsModel|SetBusy :self {g('Model')} :Busy {prop('BPWorkerOptimizer',g('Controller'),'RunActive')})
 (bind manager (Class|Backbone|GetLocManager))
 (if (CallFunction|HasObject :Object manager) (bind language (Class|LocManager|GetActiveLanguage :self manager))
   (if (not (Utilities|String|EqualExactly(String) language {g('DisplayLanguage')}))
     {put('DisplayLanguage','language')} (CallFunction|RebuildLabels)
     {invoke('BPSettingsModel',g('Model'),'BeginFilter',':Query '+M('QueryText'))}
     (if (== {g('ActiveTab')} "priorities")
       {invoke('WBPPrioritiesView',g('PrioritiesHost'),'InitializePriorities',':Model '+g('Model'))})))
 (if (== {g('ActiveTab')} "general") (CallFunction|RefreshGeneral))
 (if (== {g('ActiveTab')} "priorities") {invoke('WBPPrioritiesView',g('PrioritiesHost'),'RefreshPriorities')})
 (if (== {g('ActiveTab')} "logbook") {invoke('WBPLogbookView',g('HistoryHost'),'RefreshHistory')}) (return true))'''
code['WriteOption']=f'''(fn WriteOption (OptionId Value)
 (if (or {g('Updating')} (not {g('Initialized')})) (return false))
 (Class|BPSettingsModel|SetBusy :self {g('Model')} :Busy {prop('BPWorkerOptimizer',g('Controller'),'RunActive')})
 (bind written {invoke('BPSettingsModel',g('Model'),'WriteSetting',':OptionId OptionId :Value Value')})
 (CallFunction|RefreshGeneral) (return written))'''
for fn,value in [('StrictChanged','strict'),('WeightedChanged','weighted')]:
    code[fn]=f'(fn {fn} () (bind written (CallFunction|WriteOption :OptionId "WorkerOptimizer.mode" :Value "WorkerOptimizer.ui.{value}")) (return written))'
for name,value in AUTO:
    code[name+'Changed']=f'(fn {name}Changed () (bind written (CallFunction|WriteOption :OptionId "WorkerOptimizer.auto_assignment" :Value "WorkerOptimizer.ui.auto.{value}")) (return written))'
code['ReserveChanged']=f'''(fn ReserveChanged ()
 (bind value {text_string(edit('GetText'))})
 {put('HasReserveCache','false')}
 (bind written (CallFunction|WriteOption :OptionId "WorkerOptimizer.reserve" :Value value)) (return written))'''
code['ChangeReserve']=f'''(fn ChangeReserve (Delta)
 (if (not {g('Initialized')}) (return false))
 (bind value {S('ParseReserve',':Value '+read('WorkerOptimizer.reserve','1'))})
 (bind target (+ value Delta))
 (if (or (< target 0) (> target 100)) (return false))
 (bind written (CallFunction|WriteOption :OptionId "WorkerOptimizer.reserve" :Value (Utilities|String|ToString(Integer) target))) (return written))'''
for fn,delta in [('ReserveDecrement',-1),('ReserveIncrement',1)]:code[fn]=f'(fn {fn} () (bind written (CallFunction|ChangeReserve :Delta {delta})) (return written))'
code['SyncKey']=f'''(fn SyncKey () {put('Updating','true')}
 (Widget|SetSelectedKey :self {g('KeySelector')} :InSelectedKey {invoke('BPHotkeyConfig',g('Hotkey'),'ExportChord')}) {put('Updating','false')} (return true))'''
code['KeyChanged']=f'''(fn KeyChanged (Chord) (if {g('Updating')} (return false))
 (bind applied {invoke('BPHotkeyConfig',g('Hotkey'),'ApplyChord',':Chord Chord')})
 (if (not applied) (CallFunction|SyncKey) (CallFunction|RefreshGeneral) (return false))
 (bind saved {invoke('BPHotkeyConfig',g('Hotkey'),'SaveSettings',':Slot '+g('HotkeySlot'))})
 (CallFunction|RefreshGeneral) (return saved))'''
code['IsCapturing']=f'''(fn IsCapturing () (if (not {g('PanelOpen')}) (return false))
 (return (Widget|GetIsSelectingKey :self {g('KeySelector')})))'''
for fn in ('ModeChanged','AutoChanged','BuildRows','SearchChanged','PreviousPage','NextPage'):
    code[fn]=f'(fn {fn} () (return false))'
def size_call(name,value):return f'({native(graphs["ApplyPanelLayout"],"SetWidthOverride","SizeBox")} :self {g(name)} :InWidthOverride {value})'
def height_call(name,value):return f'({native(graphs["ApplyPanelLayout"],"SetHeightOverride","SizeBox")} :self {g(name)} :InHeightOverride {value})'
canvas_slot=native(graphs['ApplyPanelLayout'],'SlotAsCanvasSlot')
set_position=native(graphs['ApplyPanelLayout'],'SetPosition','CanvasPanelSlot')
def position(name,x,y):return f'({set_position} :self ({canvas_slot} :Widget {g(name)}) :InPosition (Math|Vector2D|MakeVector2D :X {x} :Y {y}))'
code['DesiredWidth']=f'''(fn DesiredWidth (Widget)
 (bind (x y) (Math|Vector2D|BreakVector2D ({native(graphs['DesiredWidth'],'GetDesiredSize')} :self Widget))) (return x))'''
wrap_node=native(graphs['ApplyPanelLayout'],'SetWrapSize','WrapBox')
text_wrap_node=native(graphs['ApplyPanelLayout'],'SetWrapTextAt')
text_wrap_pins={p.name for p in BP.get_node_type_pins(graphs['ApplyPanelLayout'],text_wrap_node).input_pins}
text_wrap_arg=next(name for name in ('WrapTextAt','InWrapTextAt') if name in text_wrap_pins)
prepass_node=native(graphs['ApplyPanelLayout'],'ForceLayoutPrepass')
code['ApplyPanelLayout']=f'''(fn ApplyPanelLayout (Width Height)
 {put('LayoutWidth','Width')} {put('LayoutHeight','Height')} {put('Narrow','(< (- Width 48.0) 920.0)')}
 (bind titleWidth (CallFunction|DesiredWidth :Widget {g('PanelTitle')}))
 (bind generalWidth (CallFunction|DesiredWidth :Widget {g('GeneralTabText')}))
 (bind prioritiesWidth (CallFunction|DesiredWidth :Widget {g('PrioritiesTabText')}))
 (bind logbookWidth (CallFunction|DesiredWidth :Widget {g('LogbookTabText')}))
 (bind textWidth (+ 32.0 (+ (+ titleWidth generalWidth) (+ prioritiesWidth logbookWidth))))
 {put('CompactHeader','(and (< Height 560.0) (and (> titleWidth 0.0) (and (> generalWidth 0.0) (and (> prioritiesWidth 0.0) (and (> logbookWidth 0.0) (<= (+ textWidth 164.0) Width))))))')}
 {put('HeaderHeight','(select '+g('CompactHeader')+' 52.0 96.0)')}
 {height_call('HeaderSize',g('HeaderHeight'))} {size_call('TitleSize','Width')}
 (bind tabsX (select {g('CompactHeader')} (+ titleWidth 68.0) 0.0))
 {position('TabsSize','tabsX','(select '+g('CompactHeader')+' 0.0 52.0)')}
 {size_call('TabsSize','(select '+g('CompactHeader')+' (- (- Width tabsX) 44.0) Width)')}
 {height_call('TabsSize','(select '+g('CompactHeader')+' 52.0 44.0)')}
 (bind usable (select (> Width 48.0) (- Width 48.0) 0.0))
 (bind scrollUsable (select (> usable 6.0) (- usable 6.0) 0.0))
 (bind body (select (> scrollUsable 932.0) 932.0 scrollUsable))
 {size_call('GeneralBodySize','(+ body 48.0)')}
 (bind controlWidth (select {g('Narrow')} body (- body 300.0)))
 {' '.join(f'({wrap_node} :self {g(name+"Wrap")} :WrapSize body) '+size_call(name+'LabelSize','(select '+g('Narrow')+' body 300.0)')+' '+size_call(name+'ControlSize','(select '+g('Narrow')+' body (- body 300.0))') for name in ('Reserve','Mode','Auto','Hotkey'))}
 {' '.join(f'({text_wrap_node} :self {g(name)} :{text_wrap_arg} controlWidth)' for name in ('ReserveHelp','ModeHelp','AutoHelp','HotkeyState'))}
 ({prepass_node} :self self)
 {invoke('WBPPrioritiesView',g('PrioritiesHost'),'ApplyLayout',':Width usable :Height (- Height '+g('HeaderHeight')+')')}
 {invoke('WBPLogbookView',g('HistoryHost'),'ApplyLayout',':Width usable :Height (- Height '+g('HeaderHeight')+')')}
 (return true))'''
emit(bp,graphs,code,{'SelectedChoiceBrush':control_brush('sel','gold'),'NormalChoiceBrush':control_brush('panel','line2'),'HotkeySlot':'WorkerOptimizer_UI_v1','ModeValues':['WorkerOptimizer.ui.strict','WorkerOptimizer.ui.weighted'],'AutoValues':['WorkerOptimizer.ui.auto.'+value for _,value in AUTO]})
events(bp,[(name,'OnClicked',fn,unreal.Button) for name,fn in [('GeneralTab','GeneralClicked'),('PrioritiesTab','PrioritiesClicked'),('LogbookTab','LogbookClicked'),('Close','ClosePanel'),('ReserveMinus','ReserveDecrement'),('ReservePlus','ReserveIncrement')]]+
 [(name,'OnCheckStateChanged',fn,unreal.CheckBox) for name,fn in [('StrictChoice','StrictChanged'),('WeightedChoice','WeightedChanged')]+[(name,name+'Changed') for name,_ in AUTO]]+
 [('ReserveInput','OnTextCommitted','ReserveChanged',unreal.EditableTextBox),('KeySelector','OnKeySelected','KeyChanged',unreal.InputKeySelector,{'SelectedKey':'Chord'})])
unreal.log('WO_SETTINGS_PANEL_GENERATED')
