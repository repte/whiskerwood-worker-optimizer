"""Recycled native list entry: only immutable projected run data is displayed."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp, add = widget('WBP_HistoryRow', reset=True)
ensure_list_entry(bp)
root, _ = add(unreal.Border, 'RowSurface')
root.set_brush_color(color('panel'))
root.set_padding(unreal.Margin(12, 8, 12, 8))
box, _ = add(unreal.HorizontalBox, 'RowBody', root)
icon_cell,_=add(unreal.SizeBox,'StatusIconCell',box)
icon_cell.set_width_override(24)
icon_size,icon_slot=add(unreal.SizeBox,'StatusIconSize',icon_cell)
icon_size.set_width_override(16)
icon_size.set_height_override(16)
status_icon,_=add(unreal.Image,'StatusIcon',icon_size)
texture=unreal.load_asset(ROOT+'/T_WorkerOptimizerStatusCompleted')
assert texture,'Generate status mask textures before history rows'
status_icon.set_brush_from_texture(texture,False)
status_icon.set_desired_size_override(unreal.Vector2D(16,16))
status_icon.set_visibility(unreal.SlateVisibility.COLLAPSED)
icon_slot.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_CENTER)
icon_slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
ordered=[icon_cell]
flex=None
for name, size in [('StatusText',15),('TitleText',15),('SubtitleText',13),('DetailText',13),('CountText',15)]:
    width = {'StatusText':24,'TitleText':136,'SubtitleText':140,'CountText':84}.get(name)
    if width:
        container, slot = add(unreal.SizeBox,name+'Cell',box)
        container.set_width_override(width)
        cell, text_slot = label(add,name,container,size=size)
        if name in ('TitleText','SubtitleText'):
            text_slot.set_padding(unreal.Margin(0,0,8,0))
            cell.set_editor_property('wrap_text_at',width-8)
            cell.set_editor_property('wrapping_policy',unreal.TextWrappingPolicy.ALLOW_PER_CHARACTER_WRAPPING)
        if name=='StatusText':
            container.set_visibility(unreal.SlateVisibility.COLLAPSED)
        ordered.append(container)
    else:
        cell, slot = label(add,name,box,size=size)
        slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
        ordered.append(cell)
        flex=cell
    if name == 'CountText':
        cell.set_editor_property('justification',unreal.TextJustify.RIGHT)
box.clear_children()
for child in ordered:
    slot=box.add_child(child)
    slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
    if child==flex:
        slot.set_size(unreal.SlateChildSize(1.0,unreal.SlateSizeRule.FILL))
graphs = declare(bp, {'string':'RunId', 'name':'Status', 'int':'Revision','bool':'Selected'},
    {'SetItem': ([('Object',unreal.Object.static_class())],[('Result','bool')]),
     'ClearRow': ([],[('Result','bool')]),
     'SelectionChanged':([('IsSelected','bool')],[('Result','bool')]),**image_wrapper_functions()})
P = lambda n: prop('BPUIListItem','item',n)
color_node = native(graphs['SetItem'],'SetColorAndOpacity','Text')
color_pins = {p.name for p in BP.get_node_type_pins(graphs['SetItem'], color_node).input_pins}
color_arg = next(name for name in ('ColorAndOpacity', 'InColorAndOpacity') if name in color_pins)
make = next(n for n in BP.find_node_types(graphs['SetItem'],'',[]) if n.endswith('|MakeLinearColor'))
make_slate = next(n for n in BP.find_node_types(graphs['SetItem'],'',[]) if n.endswith('|MakeSlateColor'))
slate_color_arg = next(p.name for p in BP.get_node_type_pins(graphs['SetItem'],make_slate).input_pins if p.name == 'SpecifiedColor')
def text_tint(c):
    return f'({make_slate} :{slate_color_arg} ({make} :R {c.r} :G {c.g} :B {c.b} :A 1.0))'
colors = {'completed':color('ok'),'problems':color('warn'),
          'error':color('err'),'aborted':color('abort')}
neutral = color('run')
brush_node=native(graphs['SetItem'],'SetBrushColor','Border')
brush_pins={p.name for p in BP.get_node_type_pins(graphs['SetItem'],brush_node).input_pins}
brush_arg=next(name for name in ('BrushColor','InBrushColor') if name in brush_pins)
selected_node=native(graphs['SetItem'],'IsListItemSelected')
selected_pin=next(p.name for p in BP.get_node_type_pins(graphs['SetItem'],selected_node).input_pins if p.name in ('UserListEntry','Target','self'))
def row_tint(key):
    c=color(key)
    return f'({make} :R {c.r} :G {c.g} :B {c.b} :A 1.0)'
# Shapes complement localized outcome text; no status depends on hue alone.
shapes = {'completed':'\u2713','problems':'\u25b3','error':'\u2bc3','aborted':'\u2298'}
status_code = []
icon_names={'completed':'Completed','problems':'Problems','error':'Error','aborted':'Aborted'}
number_text_node = next(n for n in BP.find_node_types(graphs['SetItem'], '', []) if n.endswith('|ToText(Integer)'))
count_text = '(select '+P('Known')+' '+text_string(f'({number_text_node} :Value {P("Count")})')+' "\u2014")'
for status, rgb in colors.items():
    status_code.append(f'''(if (== {g('Status')} "{status}")
      {set_label('StatusText','"'+shapes[status]+'"')}
      (CallFunction|ImageSetTexture :Target {g('StatusIcon')} :Texture "{ROOT}/T_WorkerOptimizerStatus{icon_names[status]}.T_WorkerOptimizerStatus{icon_names[status]}")
      (CallFunction|ImageSetColor :Target {g('StatusIcon')} :Color ({make} :R {rgb.r} :G {rgb.g} :B {rgb.b} :A 1.0))
      {visibility('StatusIcon','HitTestInvisible')}
      ({color_node} :self {g('TitleText')} :{color_arg} {text_tint(rgb)})
      ({color_node} :self {g('StatusText')} :{color_arg} {text_tint(rgb)}))''')
code = {'ClearRow':f'''(fn ClearRow ()
    {put('RunId','""')} {put('Revision','-1')} {put('Status','"None"')}
    {put('Selected','false')}
    {visibility('StatusIcon','Collapsed')}
    ({brush_node} :self {g('RowSurface')} :{brush_arg} {row_tint('panel')})
    {' '.join(set_label(n,'""') for n in ('StatusText','TitleText','SubtitleText','DetailText','CountText'))}
    ({color_node} :self {g('StatusText')} :{color_arg} {text_tint(neutral)})
    ({color_node} :self {g('TitleText')} :{color_arg} {text_tint(INK)})
    (return true))''',
    'SetItem':f'''(fn SetItem (Object)
    (CallFunction|ClearRow)
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object) (:then
      {put('RunId',P('RunId'))} {put('Revision',P('Revision'))} {put('Status',P('Status'))}
      {' '.join(f'(Class|Text|SetText :self {g(n)} :Text {P(field)})' for n,field in [('TitleText','Title'),('SubtitleText','Subtitle'),('DetailText','Detail')])}
      {set_label('CountText',count_text)}
      {' '.join(status_code)}
      (CallFunction|SelectionChanged :IsSelected ({selected_node} :{selected_pin} self)) (return true))
      (:CastFailed (return false))))''',
    'SelectionChanged':f'''(fn SelectionChanged (IsSelected)
      {put('Selected','IsSelected')}
      ({brush_node} :self {g('RowSurface')} :{brush_arg} (select IsSelected {row_tint('sel')} {row_tint('panel')})) (return true))'''}
code.update(image_wrapper_code())
emit(bp,graphs,code)
image_wrappers(bp)
list_entry_event(bp, 'SetItem')
event=BP.add_event(bp,'BP_OnItemSelectionChanged')
graph=BP.get_graph(bp,'EventGraph')
call=BP.create_node(graph,'CallFunction|SelectionChanged',unreal.IntPoint(400,300))
source,target=BP.get_node_infos([event,call])
BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name=='then'),next(p.pin_id for p in target.input_pins if p.name=='execute'))
BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name in ('bIsSelected','IsSelected')),next(p.pin_id for p in target.input_pins if p.name=='IsSelected'))
BP.compile_blueprint(bp,warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log('WO_HISTORY_ROW_GENERATED')
