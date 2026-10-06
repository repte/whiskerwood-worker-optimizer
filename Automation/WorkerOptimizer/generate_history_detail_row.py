"""Native recycled detail entry; projections never read live settlement state."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp, add = widget('WBP_HistoryDetailRow', reset=True)
ensure_list_entry(bp)
root, _ = add(unreal.Border,'RowSurface')
root.set_brush_color(color('panel'))
root.set_padding(unreal.Margin(24,12,24,12))
box, _ = add(unreal.VerticalBox,'RowBody',root)
title,_=label(add,'TitleText',box,size=16)
detail,_=label(add,'DetailText',box,size=15)
metrics,_=add(unreal.WrapBox,'Metrics',box)
metrics.set_editor_property('inner_slot_padding',unreal.Vector2D(16,8))
metrics.set_visibility(unreal.SlateVisibility.COLLAPSED)
for index in range(3):
    cell,_=add(unreal.SizeBox,'MetricCell'+str(index),metrics)
    cell.set_width_override(160)
    cell.set_min_desired_height(56)
    body,_=add(unreal.VerticalBox,'MetricBody'+str(index),cell)
    label(add,'MetricValue'+str(index),body,size=22)
    metric_label,_=label(add,'MetricLabel'+str(index),body,size=13)
    metric_label.set_color_and_opacity(unreal.SlateColor(MUTED))
aggregate,_=add(unreal.HorizontalBox,'AggregateLine',box)
aggregate.set_visibility(unreal.SlateVisibility.COLLAPSED)
_,slot=label(add,'AggregateTitle',aggregate,size=15)
slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
aggregate_value,_=label(add,'AggregateValue',aggregate,size=15)
aggregate_value.set_editor_property('justification',unreal.TextJustify.RIGHT)
font_struct=unreal.load_object(None,'/Script/SlateCore.SlateFontInfo')
fonts={}
for name,size in [('SectionFont',16),('BodyFont',15),('CaptionFont',13),('MetricFont',22)]:
    if name not in BP.list_variables(bp):BP.add_struct_variable(bp,name,font_struct)
    font=unreal.SlateFontInfo()
    font.import_text(title.get_editor_property('font').export_text())
    font.set_editor_property('size',font_points(size))
    font.set_editor_property('typeface_font_name','Semi Bold' if size >= 16 else 'Regular')
    fonts[name]=font
graphs = declare(bp,{'name':'Kind','int':'Index Revision','string':'RunId'},
    {'SetItem':([('Object',unreal.Object.static_class())],[('Result','bool')]),
     'ClearRow':([],[('Result','bool')]),
     'HasObject':([('Object',unreal.Object.static_class())],[('Result','bool')])})
P = lambda n: prop('BPUIListItem','item',n)
font_node=native(graphs['SetItem'],'SetFont','Text')
font_pins={p.name for p in BP.get_node_type_pins(graphs['SetItem'],font_node).input_pins}
font_arg=next(name for name in ('Font','InFontInfo') if name in font_pins)
brush_node=native(graphs['SetItem'],'SetBrushColor','Border')
brush_pins={p.name for p in BP.get_node_type_pins(graphs['SetItem'],brush_node).input_pins}
brush_arg=next(name for name in ('BrushColor','InBrushColor') if name in brush_pins)
color_node=native(graphs['SetItem'],'SetColorAndOpacity','Text')
color_pins={p.name for p in BP.get_node_type_pins(graphs['SetItem'],color_node).input_pins}
color_arg=next(name for name in ('ColorAndOpacity','InColorAndOpacity') if name in color_pins)
make=next(n for n in BP.find_node_types(graphs['SetItem'],'',[]) if n.endswith('|MakeLinearColor'))
make_slate=next(n for n in BP.find_node_types(graphs['SetItem'],'',[]) if n.endswith('|MakeSlateColor'))
slate_color_arg=next(p.name for p in BP.get_node_type_pins(graphs['SetItem'],make_slate).input_pins if p.name == 'SpecifiedColor')
def tint(key):
    c=color(key)
    return f'({make} :R {c.r} :G {c.g} :B {c.b} :A 1.0)'
def font(name,role):return f'({font_node} :self {g(name)} :{font_arg} {g(role)})'
def ink(name,key):return f'({color_node} :self {g(name)} :{color_arg} ({make_slate} :{slate_color_arg} {tint(key)}))'
metric_code=[]
for index in range(3):
    child='child'+str(index)
    child_prop=lambda name:prop('BPUIListItem',child,name)
    metric_code.append(f'''(if (Utilities|Array|IsValidIndex {P('Children')} {index})
      (bind {child} (Utilities|Casting|CastToBP_UIListItem :Object {at(P('Children'),str(index))}))
      (if (CallFunction|HasObject :Object {child})
        (Class|Text|SetText :self {g('MetricValue'+str(index))} :Text {child_prop('Detail')})
        (Class|Text|SetText :self {g('MetricLabel'+str(index))} :Text {child_prop('Title')})
        (if (not {child_prop('Known')}) {font('MetricValue'+str(index),'CaptionFont')} {ink('MetricValue'+str(index),'text2')})
        {visibility('MetricCell'+str(index),'Visible')}))''')
header_status=[]
for status,key in [('completed','ok'),('problems','warn'),('error','err'),('aborted','abort')]:
    header_status.append(f'(if (== {P("Status")} "{status}") {ink("TitleText",key)})')
code = {'HasObject':'(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))',
    'ClearRow':f'''(fn ClearRow ()
    {put('Kind','"None"')} {put('Index','-1')} {put('Revision','-1')} {put('RunId','""')}
    {set_label('TitleText','""')} {set_label('DetailText','""')}
    {font('TitleText','SectionFont')} {font('DetailText','BodyFont')}
    {ink('TitleText','text')} {ink('DetailText','text')}
    ({brush_node} :self {g('RowSurface')} :{brush_arg} {tint('panel')})
    {visibility('TitleText','Visible')} {visibility('DetailText','Visible')}
    {visibility('Metrics','Collapsed')} {visibility('AggregateLine','Collapsed')}
    {set_label('AggregateTitle','""')} {set_label('AggregateValue','""')}
    {' '.join(visibility('MetricCell'+str(index),'Collapsed')+' '+set_label('MetricValue'+str(index),'""')+' '+set_label('MetricLabel'+str(index),'""')+' '+font('MetricValue'+str(index),'MetricFont')+' '+ink('MetricValue'+str(index),'text') for index in range(3))}
    (return true))''',
    'SetItem':f'''(fn SetItem (Object)
    (CallFunction|ClearRow)
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object) (:then
      {put('Kind',P('Kind'))} {put('Index',P('Index'))}
      {put('RunId',P('RunId'))} {put('Revision',P('Revision'))}
      (if (== {g('Kind')} "metric") {font('TitleText','CaptionFont')} {font('DetailText','MetricFont')} {ink('TitleText','text2')})
      (if (or (== {g('Kind')} "header") (== {g('Kind')} "section"))
        ({brush_node} :self {g('RowSurface')} :{brush_arg} {tint('head')}))
      (if (or (== {g('Kind')} "group") (== {g('Kind')} "reason")) {font('TitleText','BodyFont')})
      (if (== {g('Kind')} "unavailable") {font('TitleText','BodyFont')} {font('DetailText','CaptionFont')} {ink('DetailText','text2')})
      (Class|Text|SetText :self {g('TitleText')} :Text {P('Title')})
      (Class|Text|SetText :self {g('DetailText')} :Text {P('Detail')})
      (if (== {g('Kind')} "header") {' '.join(header_status)})
      (if (== {g('Kind')} "metrics")
        {visibility('TitleText','Collapsed')} {visibility('DetailText','Collapsed')} {visibility('Metrics','Visible')}
        {' '.join(metric_code)})
      (if (== {g('Kind')} "aggregate")
        {visibility('TitleText','Collapsed')} {visibility('DetailText','Collapsed')} {visibility('AggregateLine','Visible')}
        (Class|Text|SetText :self {g('AggregateTitle')} :Text {P('Title')})
        (Class|Text|SetText :self {g('AggregateValue')} :Text {P('Detail')}))
      (if (== (Utilities|String|Len {text_string(P('Detail'))}) 0) {visibility('DetailText','Collapsed')}) (return true))
      (:CastFailed (return false))))'''}
emit(bp,graphs,code,fonts)
list_entry_event(bp,'SetItem')
unreal.log('WO_HISTORY_DETAIL_ROW_GENERATED')
