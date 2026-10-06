"""Author a recyclable native TreeView row with stable-key guarded writes."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from ui_authoring import *

bp, add = widget("WBP_PriorityRow", reset_layout=True)
ensure_list_entry(bp)
frame, _ = add(unreal.Border, "RowFrame")
frame.set_padding(unreal.Margin(0))
frame.set_brush_color(color('panel'))
row_size, _ = add(unreal.SizeBox, "RowSize", frame)
row_size.set_height_override(64)
root, _ = add(unreal.CanvasPanel, "Contents", row_size)
line, slot = add(unreal.Border,'StructureLine',root)
line.set_padding(unreal.Margin(0))
line.set_brush_color(color('line'))
slot.set_anchors(unreal.Anchors(unreal.Vector2D(0,0),unreal.Vector2D(0,1)))
slot.set_position(unreal.Vector2D(27,0))
slot.set_size(unreal.Vector2D(1,0))
line.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
title_size, _ = add(unreal.SizeBox, "TitleSize", root)
title_size.slot.set_auto_size(True)
label(add, "Title", title_size)
expander_size, _ = add(unreal.SizeBox, 'CategoryExpanderSize', root)
expander_size.slot.set_auto_size(True)
expander_size.set_width_override(24)
expander_size.set_height_override(24)
# Triangles are rendered through the same game font as the row title.
expander, _ = button(add, 'CategoryExpander', expander_size, '\u25b6')
expander_style = expander.get_editor_property('widget_style')
expander_style.set_editor_property('normal_padding', unreal.Margin(0))
expander_style.set_editor_property('pressed_padding', unreal.Margin(0))
expander.set_editor_property('widget_style', expander_style)
expander.get_content().slot.set_padding(unreal.Margin(0))
expander.get_content().set_editor_property('justification', unreal.TextJustify.CENTER)
effective_size, _ = add(unreal.SizeBox, "EffectiveSize", root)
effective_size.slot.set_auto_size(True)
effective_size.set_width_override(112)
label(add, "Effective", effective_size, size=17)
icon_size,_=add(unreal.SizeBox,'EffectiveIcon',root)
icon_size.slot.set_auto_size(True)
icon_size.set_width_override(16)
icon_size.set_height_override(16)
state_icon,_=add(unreal.Image,'PriorityStateIcon',icon_size)
state_texture=unreal.load_asset(ROOT+'/T_WorkerOptimizerPriorityInherited')
assert state_texture,'Generate priority marker masks before rows'
state_icon.set_brush_from_texture(state_texture,False)
state_icon.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
controls_size, _ = add(unreal.SizeBox, "PriorityControls", root)
controls_size.slot.set_auto_size(True)
controls, _ = add(unreal.WrapBox, "Controls", controls_size)
controls.set_editor_property("explicit_wrap_size", True)
controls.set_editor_property("inner_slot_padding", unreal.Vector2D(6, 4))
choices, _ = add(unreal.WrapBox, "Choices", controls)
choices.set_editor_property("explicit_wrap_size", True)
choices.set_editor_property("inner_slot_padding", unreal.Vector2D(6, 4))
for name in ("InheritChoice", "CustomChoice"):
    surface, slot = add(unreal.Border,name+'Surface',choices)
    surface.set_padding(unreal.Margin(0))
    segment_brush=control_brush('sunken','line2')
    segment_brush.set_editor_property('tint_color',unreal.SlateColor(unreal.LinearColor(1,1,1,1)))
    surface.set_editor_property('background',segment_brush)
    surface.set_brush_color(color('sunken'))
    slot.set_padding(unreal.Margin(0,4,6,4))
    check, _ = add(unreal.CheckBox, name, surface)
    input_style(check)
    check.set_editor_property("is_focusable", True)
    label(add, name + "Text", check, size=15)
stepper, _ = add(unreal.HorizontalBox, "Stepper", controls)
for name, value in (("Decrease", "-"), ("Increase", "+")):
    if name == "Increase":
        size, slot = add(unreal.SizeBox, "ValueSize", stepper)
        size.set_width_override(48)
        number, _ = label(add, "Value", size)
        number.set_editor_property('justification', unreal.TextJustify.CENTER)
        slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
    button_size, _ = add(unreal.SizeBox, name + 'Size', stepper)
    button_size.set_width_override(32)
    button_size.set_height_override(32)
    b, _ = button(add, name, button_size, value)
    b.set_editor_property("is_focusable", True)
functions = {
    "ApplyLayout": ([("Width", "float")], [("Result", "bool")]),
    "HasObject": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "SetItem": ([("Object", unreal.Object.static_class())], [("Result", "bool")]),
    "SetExpansionGlyph": ([("Expanded", "bool")], [("Result", "bool")]),
    "Write": ([("Value", "int")], [("Result", "bool")]),
    **{name: ([], [("Result", "bool")]) for name in ("RefreshRow", "CanUseRow", "ExpandClicked", "InheritChanged", "CustomChanged", "DecreaseClicked", "IncreaseClicked")},
    **image_wrapper_functions(),
}
graphs = declare(bp, {"bool": "Updating IsCategory", "int": "RowPriority EffectivePriority"}, functions,
                 {"Item": load("BP_UIListItem"), "Owner": load("WBP_PrioritiesView"), "Model": load("BP_SettingsModel")})
I = lambda n: prop("BPUIListItem", g("Item"), n)
M = lambda n: prop("BPSettingsModel", g("Model"), n)
S = lambda fn, args="": invoke("BPPrioritySettings", M("Settings"), fn, args)
U = lambda key: S("Text", ':Key "' + key + '"')
owner = lambda fn, args="": invoke("WBPPrioritiesView", g("Owner"), fn, args)
check = lambda name, state: f'({native(graphs["RefreshRow"], "SetIsChecked", "CheckBox")} :self {g(name)} :InIsChecked {state})'
brush_color_node=native(graphs['RefreshRow'],'SetBrushColor','Border')
make_color_node=next(n for n in BP.find_node_types(graphs['RefreshRow'],'',[]) if n.endswith('|MakeLinearColor'))
def tint_surface(name,key):
    c=color(key)
    return f'({brush_color_node} :self {g(name)} :InBrushColor ({make_color_node} :R {c.r} :G {c.g} :B {c.b} :A 1.0))'
effective_display = '(Utilities|String|ToString(Integer) '+g('EffectivePriority')+')'
expander_display = '(select Expanded "' + chr(0x25bc) + '" "' + chr(0x25b6) + '")'
def marker_tint(key):
    c=color(key)
    return f'(CallFunction|ImageSetColor :Target {g("PriorityStateIcon")} :Color ({make_color_node} :R {c.r} :G {c.g} :B {c.b} :A 1.0))'
code = {}
code['HasObject'] = '(fn HasObject (Object) (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))'
code["SetItem"] = f'''(fn SetItem (Object)
    {put('Updating','true')}
    (bind item (Utilities|Casting|CastToBP_UIListItem :Object Object))
    (if (not (CallFunction|HasObject :Object item)) {visibility('RowFrame','Collapsed')} {put('Updating','false')} (return false))
    {put('Item','item')}
    (bind owner (Utilities|Casting|CastToWBP_PrioritiesView :Object {I('Owner')}))
    (if (not (CallFunction|HasObject :Object owner)) {visibility('RowFrame','Collapsed')} {put('Updating','false')} (return false))
    {put('Owner','owner')} {put('Model',prop('WBPPrioritiesView','owner','Model'))}
    {put('IsCategory',f'(== {I("Kind")} "category")')}
    (Class|Text|SetText :self {g('Title')} :Text {I('Title')})
    {set_label('InheritChoiceText',U('inherit'))} {set_label('CustomChoiceText',U('priority.custom'))}
    {visibility('RowFrame','SelfHitTestInvisible')}
    {put('Updating','false')} (bind refreshed (CallFunction|RefreshRow)) (return refreshed))'''
code["CanUseRow"] = f'''(fn CanUseRow ()
    (if (not (CallFunction|HasObject :Object {g('Item')})) (return false))
    (if (not (CallFunction|HasObject :Object {g('Owner')})) (return false))
    (bind allowed {owner('CanUseItem',':Object '+g('Item'))}) (return allowed))'''
code["RefreshRow"] = f'''(fn RefreshRow ()
    (if (not (CallFunction|CanUseRow)) (Widget|SetIsEnabled :self {g('Controls')} :bInIsEnabled false) (return false))
    {put('Updating','true')}
    (if {g('IsCategory')}
      {visibility('CategoryExpanderSize','SelfHitTestInvisible')} {visibility('CategoryExpander','Visible')}
      (bind expanded ({native(graphs['RefreshRow'], 'IsListItemExpanded')}))
      (CallFunction|SetExpansionGlyph :Expanded expanded)
      (else {visibility('CategoryExpanderSize','Collapsed')} {visibility('CategoryExpander','Collapsed')}))
    (if {g('IsCategory')} {tint_surface('RowFrame','cat')} {visibility('StructureLine','Collapsed')}
      (else {tint_surface('RowFrame','panel')} {visibility('StructureLine','HitTestInvisible')}))
    (if {g('IsCategory')}
      (bind categoryPriority {invoke('BPSettingsModel',g('Model'),'CategoryPriority',':Index '+I('Index'))})
      {put('RowPriority','categoryPriority')}
      {put('EffectivePriority',g('RowPriority'))} {visibility('Choices','Collapsed')}
      (else (bind (override effective) {invoke('BPSettingsModel',g('Model'),'TypePriority',':Index '+I('Index'))})
        {put('RowPriority','override')} {put('EffectivePriority','effective')} {visibility('Choices','Visible')}))
    {check('InheritChoice',f'(< {g("RowPriority")} 0)')} {check('CustomChoice',f'(>= {g("RowPriority")} 0)')}
    (if (< {g('RowPriority')} 0) {tint_surface('InheritChoiceSurface','sel')} {tint_surface('CustomChoiceSurface','sunken')}
      (else {tint_surface('InheritChoiceSurface','sunken')} {tint_surface('CustomChoiceSurface','sel')}))
    (if (or {g('IsCategory')} (>= {g('RowPriority')} 0)) {visibility('Stepper','Visible')} (else {visibility('Stepper','Collapsed')}))
    {set_label('Value','(Utilities|String|ToString(Integer) '+g('RowPriority')+')')}
    (bind priorityLabel {S('Text', ':Key (Utilities|String|Append :A "priority." :B (Utilities|String|ToString(Integer) '+g('EffectivePriority')+'))')})
    {set_label('Effective',effective_display)}
    (if {g('IsCategory')} {visibility('PriorityStateIcon','Collapsed')}
      (else {visibility('PriorityStateIcon','HitTestInvisible')}
        (if (< {g('RowPriority')} 0)
          (CallFunction|ImageSetTexture :Target {g('PriorityStateIcon')} :Texture "{ROOT}/T_WorkerOptimizerPriorityInherited.T_WorkerOptimizerPriorityInherited") {marker_tint('text2')}
          (else (CallFunction|ImageSetTexture :Target {g('PriorityStateIcon')} :Texture "{ROOT}/T_WorkerOptimizerPriorityOwn.T_WorkerOptimizerPriorityOwn") {marker_tint('gold')}))))
    (bind effectiveLabel {U('effective')})
    (Widget|SetToolTipText :self {g('Effective')} :InToolTipText {text('(Utilities|String|Append :A effectiveLabel :B (Utilities|String|Append :A ": " :B priorityLabel))')})
    (bind enabled (and (not {M('Busy')}) (not (and {g('IsCategory')} (== {I('Key')} "uncategorized")))))
    (Widget|SetIsEnabled :self {g('Controls')} :bInIsEnabled enabled)
    (Widget|SetIsEnabled :self {g('Decrease')} :bInIsEnabled (and enabled (> {g('RowPriority')} 0)))
    (Widget|SetIsEnabled :self {g('Increase')} :bInIsEnabled (and enabled (< {g('RowPriority')} 4)))
    {put('Updating','false')}
    (CallFunction|ApplyLayout :Width {prop('WBPPrioritiesView',g('Owner'),'LayoutWidth')}) (return true))'''
code['ExpandClicked'] = f'''(fn ExpandClicked ()
    (if (or {g('Updating')} (not (CallFunction|CanUseRow))) (return false))
    (if (not {g('IsCategory')}) (return false))
    (bind expanded ({native(graphs['ExpandClicked'], 'IsListItemExpanded')}))
    (bind changed {owner('ToggleExpansion', ':Object '+g('Item')+' :Expanded (not expanded)')}) (return changed))'''
code['SetExpansionGlyph'] = f'''(fn SetExpansionGlyph (Expanded)
    (if (not (CallFunction|CanUseRow)) (return false))
    (if (not {g('IsCategory')}) (return false))
    {set_label('CategoryExpanderText', expander_display)} (return true))'''
code["Write"] = f'''(fn Write (Value)
    (if (or {g('Updating')} (not (CallFunction|CanUseRow))) (return false))
    (bind written {owner('WritePriority',':Object '+g('Item')+' :Value Value')})
    (CallFunction|RefreshRow) (return written))'''
code["InheritChanged"] = f'''(fn InheritChanged ()
    (if {g('Updating')} (return false))
    (if {g('IsCategory')} (return false))
    (bind written (CallFunction|Write :Value -1)) (return written))'''
code["CustomChanged"] = f'''(fn CustomChanged ()
    (if {g('Updating')} (return false))
    (if {g('IsCategory')} (return false))
    (bind written (CallFunction|Write :Value {g('EffectivePriority')})) (return written))'''
code["DecreaseClicked"] = f'''(fn DecreaseClicked ()
    (if (<= {g('RowPriority')} 0) (return false))
    (bind written (CallFunction|Write :Value (- {g('RowPriority')} 1))) (return written))'''
code["IncreaseClicked"] = f'''(fn IncreaseClicked ()
    (if (or (< {g('RowPriority')} 0) (>= {g('RowPriority')} 4)) (return false))
    (bind written (CallFunction|Write :Value (+ {g('RowPriority')} 1))) (return written))'''


def set_scalar(method, owner, name, value):
    node = native(graphs['ApplyLayout'], method, owner)
    pins = BP.get_node_type_pins(graphs['ApplyLayout'], node).input_pins
    argument = next(p.name for p in pins if p.name not in ('self', 'execute', 'Target'))
    return f'({node} :self {g(name)} :{argument} {value})'


slot_node = native(graphs['ApplyLayout'], 'SlotAsCanvasSlot')
position_node = native(graphs['ApplyLayout'], 'SetPosition', 'CanvasPanelSlot')
desired_node = native(graphs['ApplyLayout'], 'GetDesiredSize', 'Widget')
prepass_node = native(graphs['ApplyLayout'], 'ForceLayoutPrepass', 'Widget')


def move(name, x, y):
    return f'({position_node} :self ({slot_node} :Widget {g(name)}) :InPosition (Math|Vector2D|MakeVector2D :X {x} :Y {y}))'


code['ApplyLayout'] = f'''(fn ApplyLayout (Width)
    (bind outer (select (> Width 0.0) Width 680.0))
    (bind width (- outer 24.0))
    (bind wide (>= outer 920.0))
    (bind titleWidth (- (select wide (- width 676.0) (- width 124.0)) 32.0))
    (bind controlsWidth (select wide 540.0 (- width 32.0)))
    {set_scalar('SetWidthOverride','SizeBox','TitleSize','titleWidth')}
    {set_scalar('SetWidthOverride','SizeBox','PriorityControls','controlsWidth')}
    {set_scalar('SetWidthOverride','SizeBox','EffectiveSize',f'(select {g("IsCategory")} 112.0 88.0)')}
    {set_scalar('SetWrapTextAt','TextBlock','Title','titleWidth')}
    {set_scalar('SetWrapTextAt','TextBlock','Effective','112.0')}
    {set_scalar('SetWrapTextAt','TextBlock','InheritChoiceText','190.0')}
    {set_scalar('SetWrapTextAt','TextBlock','CustomChoiceText','170.0')}
    {set_scalar('SetWrapSize','WrapBox','Controls','controlsWidth')}
    {set_scalar('SetWrapSize','WrapBox','Choices','(- controlsWidth 126.0)')}
    ({prepass_node} :self self)
    (bind (titleX titleHeight) (Math|Vector2D|BreakVector2D ({desired_node} :self {g('TitleSize')})))
    (bind (effectiveX effectiveHeight) (Math|Vector2D|BreakVector2D ({desired_node} :self {g('EffectiveSize')})))
    (bind (controlsX controlsHeight) (Math|Vector2D|BreakVector2D ({desired_node} :self {g('PriorityControls')})))
    (bind headHeight (select (> titleHeight effectiveHeight) titleHeight effectiveHeight))
    {move('TitleSize','44.0','8.0')}
    {move('CategoryExpanderSize','12.0','8.0')}
    {move('EffectiveIcon','(+ 12.0 (- width 112.0))','8.0')}
    {move('EffectiveSize',f'(+ (+ 12.0 (- width 112.0)) (select {g("IsCategory")} 0.0 24.0))','8.0')}
    (if wide
      {move('PriorityControls','(+ titleWidth 56.0)','8.0')}
      {set_scalar('SetHeightOverride','SizeBox','RowSize','(+ 16.0 (select (> controlsHeight headHeight) controlsHeight headHeight))')}
      (else
        {move('PriorityControls','44.0','(+ headHeight 12.0)')}
        {set_scalar('SetHeightOverride','SizeBox','RowSize','(+ 20.0 (+ headHeight controlsHeight))')}))
    (return true))'''
code.update(image_wrapper_code())
emit(bp, graphs, code)
image_wrappers(bp)
events(bp, [("CategoryExpander", "OnClicked", "ExpandClicked", unreal.Button), ("InheritChoice", "OnCheckStateChanged", "InheritChanged", unreal.CheckBox), ("CustomChoice", "OnCheckStateChanged", "CustomChanged", unreal.CheckBox), ("Decrease", "OnClicked", "DecreaseClicked", unreal.Button), ("Increase", "OnClicked", "IncreaseClicked", unreal.Button)])
list_entry_event(bp)
graph = BP.get_graph(bp, 'EventGraph')
expansion_event = BP.add_event(bp, 'BP_OnItemExpansionChanged')
expansion_call = BP.create_node(graph, 'CallFunction|SetExpansionGlyph', unreal.IntPoint(400, 300))
source, target = BP.get_node_infos([expansion_event, expansion_call])
BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name == 'then'), next(p.pin_id for p in target.input_pins if p.name == 'execute'))
BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name == 'bIsExpanded'), next(p.pin_id for p in target.input_pins if p.name == 'Expanded'))
BP.compile_blueprint(bp, warnings_as_errors=True)
assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_PRIORITY_ROW_GENERATED")
