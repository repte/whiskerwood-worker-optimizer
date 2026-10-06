"""Author a native compact UMG control and explicit click-only command wiring."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl
from ui_authoring import widget as reset_widget, color as token_color, native, control_brush, font_size, nine_slice_brush, image_wrapper_functions, image_wrapper_code, image_wrappers

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
umg = unreal.get_default_object(unreal.UMGToolSet)
call = lambda name, *args: umg.call_method(name, args=args)
bp, unused_add = reset_widget('WBP_WorkerOptimizer', reset_layout=True)
created = bp is None
if bp is None:
    bp = call("CreateWidgetBlueprint", ROOT, "WBP_WorkerOptimizer", unreal.UserWidget.static_class())
assert bp
tree = call("GetWidgets", bp)
if created and tree.widgets:
    assert call("RemoveWidget", bp, next(w.widget for w in tree.widgets if not w.parent))
    tree = call("GetWidgets", bp)
existing_widgets = {str(w.widget_name): w for w in tree.widgets}


def add(kind, name, parent=None, variable=False):
    klass = kind if isinstance(kind, unreal.Class) else kind.static_class()
    info = existing_widgets.get(name)
    if info:
        assert info.widget.get_class() == klass and info.parent == parent, name
    else:
        info = call("AddWidget", bp, klass, name, parent, -1)
    assert info.widget, name
    if variable and not info.is_variable:
        call("ToggleWidgetAsVariable", bp, info.widget, True)
    return info.widget, info.slot


def box(slot, x, y, width, height, bottom=False):
    slot.set_anchors(unreal.Anchors(unreal.Vector2D(0, 1 if bottom else 0), unreal.Vector2D(0, 1 if bottom else 0)))
    slot.set_position(unreal.Vector2D(x, y))
    slot.set_size(unreal.Vector2D(width, height))


def icon(parent, path, size):
    obj, slot = add(unreal.Image, parent.get_name() + "Icon", parent, True)
    texture = unreal.load_asset(path)
    assert texture, path
    obj.set_brush_from_texture(texture, False)
    obj.set_desired_size_override(unreal.Vector2D(size, size))
    obj.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    obj.set_color_and_opacity(token_color('gold'))
    slot.set_padding(unreal.Margin(6, 6, 6, 6))
    slot.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_CENTER)
    slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_CENTER)
    return obj


def button_style(widget, icon_only=False):
    style = widget.get_editor_property("widget_style")
    if icon_only:
        style.set_editor_property("normal_padding", unreal.Margin(0, 0, 0, 0))
        style.set_editor_property("pressed_padding", unreal.Margin(0, 1, 0, 0))
    for name, key, edge in (("normal", 'surface','line2'), ("hovered", 'hover','line3'), ("pressed", 'sunken','goldlo'), ('disabled','dbg','dline')):
        style.set_editor_property(name, control_brush(key,edge))
    for name in ("normal_foreground", "hovered_foreground", "pressed_foreground"):
        style.set_editor_property(name, unreal.SlateColor(unreal.LinearColor(1, 1, 1, 1)))
    if str(widget.get_name()) in ('SettingsButton','LogbookButton'):
        brush = style.get_editor_property('normal')
        brush.set_editor_property('tint_color', unreal.SlateColor(unreal.LinearColor(1,1,1,1)))
        style.set_editor_property('normal',brush)
        widget.set_background_color(token_color('surface'))
    widget.set_editor_property("widget_style", style)


root, _ = add(unreal.CanvasPanel, "Root")
root.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
controls, slot = add(unreal.CanvasPanel, "Controls", root, True)
box(slot, 180, -170, 120, 46, True)
controls.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
action, slot = add(unreal.Button, "ActionButton", controls, True)
box(slot, 0, 0, 40, 40)
action.set_editor_property("is_focusable", True)
button_style(action, True)
icon(action, "/Game/Assets/Icons/BoardGameIcons/arrow_clockwise", 24)
busy, slot = add(unreal.Image, "BusyIndicator", controls, True)
box(slot, 8, 8, 24, 24)
busy_material = unreal.load_asset(ROOT+'/M_WorkerOptimizerBusy')
assert busy_material, 'Generate native UI materials before the HUD'
busy.set_brush_from_material(busy_material)
busy.set_visibility(unreal.SlateVisibility.COLLAPSED)
settings, slot = add(unreal.Button, "SettingsButton", controls, True)
box(slot, 44, 8, 32, 32)
settings.set_editor_property("is_focusable", True)
button_style(settings, True)
settings.set_tool_tip_text("Worker Optimizer: Hotkey")
icon(settings, "/Game/Assets/Icons/icons8-gear-100", 18)
history_button, slot = add(unreal.Button, "LogbookButton", controls, True)
box(slot, 80, 8, 32, 32)
history_button.set_editor_property("is_focusable", True)
button_style(history_button, True)
history_icons = [p for p in unreal.EditorAssetLibrary.list_assets("/Game/Assets/Icons", recursive=True)
                 if any(k in p.rsplit("/",1)[-1].lower() for k in ("book", "list", "scroll", "clipboard"))]
assert history_icons, "Native logbook/list icon unavailable"
icon(history_button, sorted(history_icons)[0], 18)
busy_text, slot = add(unreal.TextBlock, 'BusyText', controls, True)
box(slot,0,-60,260,52)
busy_font=busy_text.get_editor_property('font')
busy_font.set_editor_property('size',15)
busy_text.set_editor_property('font',busy_font)
font_size(busy_text, size=15)
busy_text.set_auto_wrap_text(True)
busy_text.set_color_and_opacity(unreal.SlateColor(token_color('run')))
busy_text.set_visibility(unreal.SlateVisibility.COLLAPSED)
badge, slot = add(unreal.TextBlock, 'OutcomeBadge', controls, True)
box(slot,24,24,16,16)
badge_font=badge.get_editor_property('font')
badge_font.set_editor_property('size',13)
badge.set_editor_property('font',badge_font)
font_size(badge, size=13)
badge.set_visibility(unreal.SlateVisibility.COLLAPSED)
outcome_icon,slot=add(unreal.Image,'OutcomeIcon',controls,True)
box(slot,24,24,16,16)
outcome_texture=unreal.load_asset(ROOT+'/T_WorkerOptimizerStatusCompleted')
assert outcome_texture,'Generate status mask textures before the HUD'
outcome_icon.set_brush_from_texture(outcome_texture,False)
outcome_icon.set_visibility(unreal.SlateVisibility.COLLAPSED)
shadow,slot=add(unreal.Image,'PanelShadow',root,True)
shadow.set_editor_property('brush',nine_slice_brush('T_WorkerOptimizerShadow',64,24/64))
shadow.set_color_and_opacity(unreal.LinearColor(0,0,0,0.45))
shadow.set_visibility(unreal.SlateVisibility.COLLAPSED)
shadow.set_editor_property('render_transform_pivot', unreal.Vector2D(0, 0))
slot.set_z_order(-1)
panel_scale, slot = add(unreal.ScaleBox, "PanelScale", root, True)
panel_scale.set_stretch(unreal.Stretch.USER_SPECIFIED)
panel_scale.set_user_specified_scale(1.0)
box(slot, 0, -428, 620, 520)
panel_scale.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
compact_panel, slot = add(load("WBP_SettingsPanel"), "PanelHost", panel_scale, True)
slot.set_horizontal_alignment(unreal.HorizontalAlignment.H_ALIGN_FILL)
slot.set_vertical_alignment(unreal.VerticalAlignment.V_ALIGN_FILL)
compact_panel.set_visibility(unreal.SlateVisibility.COLLAPSED)
compact_panel.set_editor_property("render_transform_pivot", unreal.Vector2D(0, 0))
panel, slot = add(unreal.Border, "SettingsPanel", controls, True)
box(slot, 0, 0, 360, 86)
panel.set_brush_color(unreal.LinearColor(0.016, 0.022, 0.019, 0.98))
panel.set_padding(unreal.Margin(10, 8, 10, 8))
panel.set_visibility(unreal.SlateVisibility.COLLAPSED)
content, _ = add(unreal.VerticalBox, "SettingsContent", panel)
label, _ = add(unreal.TextBlock, "HotkeyLabel", content, True)
label.set_text("Worker Optimizer: Hotkey")
label.set_auto_wrap_text(True)
font = label.get_editor_property("font")
font.set_editor_property("size", 13)
label.set_editor_property("font", font)
selector, slot = add(unreal.InputKeySelector, "KeySelector", content, True)
selector.set_editor_property("allow_modifier_keys", True)
selector.set_editor_property("allow_gamepad_keys", False)
slot.set_padding(unreal.Margin(0, 6, 0, 0))
selector.set_editor_property("key_selection_text", unreal.Text("..."))
selector.set_editor_property("no_key_specified_text", unreal.Text("Ctrl+Alt+O"))
button_style(selector)
text_style = selector.get_editor_property("text_style")
key_font = text_style.get_editor_property("font")
key_font.set_editor_property("size", 13)
text_style.set_editor_property("font", key_font)
text_style.set_editor_property("color_and_opacity", unreal.SlateColor(unreal.LinearColor(1, 1, 1, 1)))
selector.set_editor_property("text_style", text_style)
unreal.WorkerOptimizerUIAuthoring.create_pulse_animation(bp, 'GeometryPulse', 0.25)
BP.compile_blueprint(bp)

refs = {"Controller": "BP_WorkerOptimizer", "Config": "BP_HotkeyConfig", "Texts": "BP_PrioritySettings", "SettingsModel": "BP_SettingsModel", "History": "BP_Logbook"}
existing = set(BP.list_variables(bp))
for name, asset in refs.items():
    if name not in existing:
        BP.add_object_variable(bp, name, load(asset))
if 'NativeHudWidget' not in existing:
    BP.add_object_variable(bp, 'NativeHudWidget', unreal.Widget.static_class())
for name in ("Initialized", "Closed", "ButtonVisible", "SettingsOpen", "UpdatingKey"):
    if name not in existing:
        BP.add_variable(bp, name, "bool")
for name in ('GeometryWatching','NotificationsBound','LayoutSettling','ShadowVisible'):
    if name not in existing:
        BP.add_variable(bp, name, 'bool')
for name in ("LayoutWidth", "LayoutHeight", "LayoutX", "LayoutBottom", "LayoutPanelWidth", "LayoutPopupScale", "LayoutViewportScale", "LayoutPopupX", "LayoutPopupY", "LayoutPopupWidth", "LayoutPopupHeight", "NativeHudBottom"):
    if name not in existing:
        BP.add_variable(bp, name, "float")
for kind, names in {"int": "UIWriteCount LocalizationVersion CachedActionVersion CachedSettingsVersion ActionState SettingsState SkippedCount CachedActionState CachedSettingsState CachedSkippedCount HUDSettingsStyle HUDLogbookStyle", "bool": "HasActionCache HasSettingsCache ActionEnabled CachedEnabled", "name": "DisplayLanguage LayoutTab"}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind)
chord = unreal.load_object(None, "/Script/Slate.InputChord")
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "InitializeUI": [("InputController", load("BP_WorkerOptimizer")), ("InputConfig", load("BP_HotkeyConfig"))],
    "ToggleButton": [], "ToggleSettings": [], "ClickAction": [], "RefreshUI": [], "RefreshSettingsStatus": [],
    "InitializePanel": [], "OpenLogbook": [],
    "SyncKey": [], "KeyChanged": [("Chord", chord)], "IsCapturing": [], "ShutdownUI": [],
    "UIString": [("Key", "string")], "CompletedTooltip": [],
    "ApplyLayout": [("Width", "float"), ("Height", "float")], "RefreshLayout": [],
    "ApplyViewportLayout": [("PixelWidth", "float"), ("PixelHeight", "float"), ("ViewportScale", "float")],
    "RefreshDisplayState": [], "ApplyActionDisplay": [], "RefreshHudSelection": [],
    "BindController": [], "UnbindController": [], "BindHistory": [], "UnbindHistory": [],
    "BindModel": [], "UnbindModel": [], "BindPanel": [], "UnbindPanel": [],
    "BindPulse": [], "UnbindPulse": [], "UpdateGeometryWatcher": [], "MeasureHud": [], "MeasureCachedHud": [],
    "OnPresentation": [], "OnPanelEvent": [], "OnGeometryPulse": [],
}
definitions.update({name:params for name,(params,_) in image_wrapper_functions().items()})
graphs = {}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if kind == chord:
                BP.add_struct_function_param(graphs[name], param, kind, True)
            elif isinstance(kind, str):
                BP.add_function_param(graphs[name], param, kind, True)
            elif isinstance(kind,unreal.ScriptStruct):
                BP.add_struct_function_param(graphs[name],param,kind,True)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        if name not in ('OnPresentation','OnPanelEvent','OnGeometryPulse','ImageSetTexture','ImageSetColor'):
            is_text = name in ('UIString','CompletedTooltip')
            BP.add_function_param(graphs[name], "Text" if is_text else "Result", "string" if is_text else "bool", False)
BP.compile_blueprint(bp)

node_types = BP.find_node_types(graphs["InitializeUI"], "", [])
widget_getters = {}
for name in ("Controls", "ActionButton", "BusyIndicator", "SettingsButton", "SettingsPanel", "KeySelector", "HotkeyLabel", "PanelHost", "PanelScale", "PanelShadow", "LogbookButton", "BusyText", "OutcomeBadge", "OutcomeIcon", "ActionButtonIcon", "GeometryPulse"):
    matches = [n for n in node_types if n.startswith("Variables|") and n.endswith("|Get" + name)]
    unreal.log("WO_WIDGET_GETTER " + name + " " + str(matches))
    assert len(matches) == 1, (name, matches)
    widget_getters[name] = matches[0]


def g(name):
    return f"({widget_getters.get(name, 'Variables|Default|Get' + name)})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def present(value):
    return f"(CallFunction|HasObject :Object {value})"


def invoke(ref, name, args=""):
    return f"(Class|{refs[ref].replace('_', '')}|{name} :self {g(ref)} {args})"


def prop(name):
    return f"(Class|BPWorkerOptimizer|Get{name} :self {g('Controller')})"


def visible(widget, value):
    return f'(Widget|SetVisibility :self {g(widget)} :InVisibility "{value}")'


text_node = next(n for n in node_types if n.endswith("|ToText(String)"))
color_node = next(n for n in node_types if n.endswith("|MakeLinearColor"))
render_scale_node = next(n for n in node_types if n.endswith("|SetRenderScale"))
render_scale_pin = next(p.name for p in BP.get_node_type_pins(graphs["ApplyLayout"], render_scale_node).input_pins if "Vector2D" in str(p.type_id).replace(" ", ""))
layout_scale_node = native(graphs['ApplyLayout'], 'SetUserSpecifiedScale', 'ScaleBox')
layout_scale_pin = next(p.name for p in BP.get_node_type_pins(graphs['ApplyLayout'], layout_scale_node).input_pins if p.name not in ('self', 'execute', 'Target'))
background_node = None
for node in node_types:
    if node.endswith("|SetBackgroundColor"):
        pins = BP.get_node_type_pins(graphs["RefreshUI"], node).input_pins
        if any(p.name == "InBackgroundColor" for p in pins) and any("Button Object" in str(p.type_id) for p in pins):
            background_node = node
            break
assert background_node, "Native button color setter unavailable"


def tooltip(value, widget="ActionButton"):
    return counted(f'(Widget|SetToolTipText :self {g(widget)} :InToolTipText ({text_node} {value}))')


def ui(key):
    return f'(CallFunction|UIString :Key "{key}")'


def tint(red, green, blue, widget="ActionButton"):
    return ''


def counted(setter):
    return put("UIWriteCount", f"(+ {g('UIWriteCount')} 1)") + " " + setter


guard = f"(if (or {g('Closed')} (not {g('Initialized')})) (return false))"
code = {}
code["ApplyLayout"] = f"""(fn ApplyLayout (Width Height)
    (if (or (< Width 280.0) (< Height 180.0)) (return false))
    (if (and (== Width {g('LayoutWidth')}) (== Height {g('LayoutHeight')})) (return true))
    {put('LayoutWidth','Width')} {put('LayoutHeight','Height')}
    {put('LayoutX','(select (< Width 500.0) 12.0 180.0)')}
    {put('LayoutBottom','(select (< Width 1600.0) 240.0 170.0)')}
    (if (> {g('LayoutBottom')} (- Height 48.0)) {put('LayoutBottom','(- Height 48.0)')})
    (Layout|CanvasSlot|SetPosition :self (Slot|SlotasCanvasSlot :Widget {g('Controls')})
        :InPosition (Math|Vector2D|MakeVector2D :X {g('LayoutX')} :Y (- 0.0 {g('LayoutBottom')})))
    (if (not (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')})) (return true))
    {put('LayoutPopupScale',f'(select (> {g("LayoutViewportScale")} 1.0) {g("LayoutViewportScale")} 1.0)')}
    (bind contentWidth (/ Width {g('LayoutPopupScale')}))
    (bind contentHeight (/ Height {g('LayoutPopupScale')}))
    (bind margin (select (< contentHeight 700.0) 12.0 24.0))
    ({layout_scale_node} :self {g('PanelScale')} :{layout_scale_pin} {g('LayoutPopupScale')})
    ({render_scale_node} :self {g('PanelShadow')} :{render_scale_pin} (Math|Vector2D|MakeVector2D :X {g('LayoutPopupScale')} :Y {g('LayoutPopupScale')}))
    {put('LayoutPopupWidth','(* contentWidth 0.7)')}
    (if (< {g('LayoutPopupWidth')} 680.0) {put('LayoutPopupWidth','680.0')})
    (if (> {g('LayoutPopupWidth')} 1400.0) {put('LayoutPopupWidth','1400.0')})
    (if (> {g('LayoutPopupWidth')} (- contentWidth (* margin 2.0))) {put('LayoutPopupWidth','(- contentWidth (* margin 2.0))')})
    (bind hud (select (> {g('NativeHudBottom')} 0.0) {g('NativeHudBottom')} 48.0))
    {put('LayoutPopupY',f'(+ hud (* margin {g("LayoutPopupScale")}))')}
    {put('LayoutPopupHeight',f'(- (/ (- Height {g("LayoutPopupY")}) {g("LayoutPopupScale")}) margin)')}
    (if (> {g('LayoutPopupHeight')} 1040.0) {put('LayoutPopupHeight','1040.0')})
    {put('LayoutPopupX',f'(- Width (* (+ margin {g("LayoutPopupWidth")}) {g("LayoutPopupScale")}))')}
    (Layout|CanvasSlot|SetSize :self (Slot|SlotasCanvasSlot :Widget {g('PanelScale')})
        :InSize (Math|Vector2D|MakeVector2D :X (* {g('LayoutPopupWidth')} {g('LayoutPopupScale')}) :Y (* {g('LayoutPopupHeight')} {g('LayoutPopupScale')})))
    (Layout|CanvasSlot|SetPosition :self (Slot|SlotasCanvasSlot :Widget {g('PanelScale')})
        :InPosition (Math|Vector2D|MakeVector2D :X {g('LayoutPopupX')} :Y {g('LayoutPopupY')}))
    (Layout|CanvasSlot|SetSize :self (Slot|SlotasCanvasSlot :Widget {g('PanelShadow')})
        :InSize (Math|Vector2D|MakeVector2D :X (+ {g('LayoutPopupWidth')} 48.0) :Y (+ {g('LayoutPopupHeight')} 48.0)))
    (Layout|CanvasSlot|SetPosition :self (Slot|SlotasCanvasSlot :Widget {g('PanelShadow')})
        :InPosition (Math|Vector2D|MakeVector2D :X (- {g('LayoutPopupX')} (* 24.0 {g('LayoutPopupScale')})) :Y (- {g('LayoutPopupY')} (* 16.0 {g('LayoutPopupScale')}))))
    (Class|WBPSettingsPanel|ApplyPanelLayout :self {g('PanelHost')} :Width {g('LayoutPopupWidth')} :Height {g('LayoutPopupHeight')})
    {put('UIWriteCount',f'(+ {g("UIWriteCount")} 1)')} (return true))
"""
code['ApplyViewportLayout'] = f"""(fn ApplyViewportLayout (PixelWidth PixelHeight ViewportScale)
    (if (or (<= ViewportScale 0.0) (or (<= PixelWidth 0.0) (<= PixelHeight 0.0))) (return false))
    (bind correction (select (< ViewportScale 1.0) (/ 1.0 ViewportScale) 1.0))
    (if (!= correction {g('LayoutViewportScale')})
      {put('LayoutViewportScale','correction')} {put('LayoutWidth','-1.0')})
    (bind applied (CallFunction|ApplyLayout :Width (/ PixelWidth ViewportScale) :Height (/ PixelHeight ViewportScale)))
    (return applied))"""
code["RefreshLayout"] = """(fn RefreshLayout ()
    (bind size (Viewport|GetViewportSize))
    (bind scale (Viewport|GetViewportScale))
    (if (<= scale 0.0) (return false))
    (bind (x y) (Math|Vector2D|BreakVector2D :InVec size))
    (bind applied (CallFunction|ApplyViewportLayout :PixelWidth x :PixelHeight y :ViewportScale scale))
    (return applied))"""
code["UIString"] = f"""(fn UIString (Key)
    (if (not {present(g('Texts'))}) (return Key))
    (bind translated {invoke('Texts', 'Text', ':Key Key')}) (return translated))"""
date_node = next(n for n in node_types if 'DateTime' in n and any(p.name == 'InTimeZone' for p in BP.get_node_type_pins(graphs['CompletedTooltip'],n).input_pins))
integer_text_node = next(n for n in node_types if n.endswith('|ToText(Integer)'))
code['CompletedTooltip']=f'''(fn CompletedTooltip ()
    (bind report {prop('CompletedReport')})
    (if (not {present('report')}) (bind fallback {ui('completed')}) (return fallback))
    (bind timestamp (Utilities|String|ToString(Text) ({date_node} :InDateTime (Class|BPRunReport|GetEndedAt :self report) :InDateStyle "Short" :InTimeStyle "Short")))
    (bind result (Utilities|String|Append :A {ui('completed')} :B (Utilities|String|Append :A " | " :B timestamp)))
    (if (Class|BPRunReport|GetCountsKnown :self report)
      (bind count (Utilities|String|ToString(Text) ({integer_text_node} :Value (Class|BPRunReport|GetConfirmedChanges :self report))))
      (bind detail (Utilities|String|Append :A result :B (Utilities|String|Append :A " | " :B (Utilities|String|Append :A {ui('history.changes')} :B (Utilities|String|Append :A ": " :B count)))))
      (return detail))
    (return result))'''
code["HasObject"] = """(fn HasObject (Object)
    (Utilities|IsValid Object (:"Is Valid" (return true)) (:"Is Not Valid" (return false))))"""
code["InitializeUI"] = f"""(fn InitializeUI (InputController InputConfig)
    (if {g('Closed')} (return false))
    (if {g('Initialized')} (return (and (== InputController {g('Controller')}) (== InputConfig {g('Config')}))))
    (if (or (not {present('InputController')}) (not {present('InputConfig')})) (return false))
    (if (or (not {present(g('ActionButton'))}) (not {present(g('KeySelector'))})) (return false))
    {put('Controller', 'InputController')} {put('Config', 'InputConfig')}
    (bind texts (Game|ConstructObjectfromClass :Class "{ROOT}/BP_PrioritySettings.BP_PrioritySettings_C" :self self))
    {put('Texts', 'texts')}
    {put('Initialized', 'true')} {put('ButtonVisible', 'true')} {put('SettingsOpen', 'false')}
    {visible('Controls', 'SelfHitTestInvisible')} {visible('SettingsPanel', 'Collapsed')}
    {put('History',prop('Logbook'))}
    (CallFunction|BindController) (CallFunction|BindPanel) (CallFunction|BindPulse)
    (if {present(g('History'))} (CallFunction|BindHistory))
    {put('NotificationsBound','true')}
    (CallFunction|SyncKey) (CallFunction|RefreshUI) (return true))"""
code["ToggleButton"] = f"""(fn ToggleButton () {guard}
    {put('ButtonVisible', f'(not {g("ButtonVisible")})')}
    {put('SettingsOpen', 'false')} {visible('SettingsPanel', 'Collapsed')}
    (Class|WBPSettingsPanel|ClosePanel :self {g('PanelHost')})
    (if {g('ButtonVisible')} {visible('Controls', 'SelfHitTestInvisible')}
      (else {visible('Controls', 'Collapsed')})) (return true))"""
code["ToggleSettings"] = f"""(fn ToggleSettings () {guard}
    (if (not {g('ButtonVisible')}) (return false))
    (if (and (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')}) (== (Class|WBPSettingsPanel|GetActiveTab :self {g('PanelHost')}) "general"))
      (Class|WBPSettingsPanel|ClosePanel :self {g('PanelHost')}) {put('SettingsOpen','false')} (return true))
    (if (not (CallFunction|InitializePanel)) (return false))
    (bind opened (Class|WBPSettingsPanel|OpenTab :self {g('PanelHost')} :Tab "general"))
    {put('SettingsOpen','opened')} (CallFunction|RefreshLayout) (return opened))"""
code["InitializePanel"] = f"""(fn InitializePanel ()
    (if (!= {g('History')} {prop('Logbook')})
      (if {present(g('History'))} (CallFunction|UnbindHistory))
      {put('History',prop('Logbook'))}
      (if {present(g('History'))} (CallFunction|BindHistory)))
    (if (Class|WBPSettingsPanel|GetInitialized :self {g('PanelHost')}) (return true))
    (if (not {present(prop('Settings'))}) (return false))
    (if (not {present(prop('PolicyCatalog'))}) (return false))
    (if (not {present(prop('Logbook'))}) (return false))
    (bind model (Game|ConstructObjectfromClass :Class "{ROOT}/BP_SettingsModel.BP_SettingsModel_C" :self self))
    {put('SettingsModel','model')}
    (bind initialized (Class|BPSettingsModel|InitializeModel :self model :Context {prop('Context')} :Settings {prop('Settings')} :Catalog {prop('PolicyCatalog')}))
    (if (not initialized) (return false))
    (bind ready (Class|WBPSettingsPanel|InitializePanel :self {g('PanelHost')} :Controller {g('Controller')} :Model model :Hotkey {g('Config')} :Logbook {prop('Logbook')}))
    (if ready (CallFunction|BindModel))
    (return ready))"""
code["OpenLogbook"] = f"""(fn OpenLogbook () {guard}
    (if (not {g('ButtonVisible')}) (return false))
    (if (not (CallFunction|InitializePanel)) (return false))
    (bind opened (Class|WBPSettingsPanel|OpenTab :self {g('PanelHost')} :Tab "logbook"))
    {put('SettingsOpen','opened')} (CallFunction|RefreshLayout) (return opened))"""
code["SyncKey"] = f"""(fn SyncKey () {guard}
    {put('UpdatingKey', 'true')}
    (Widget|SetSelectedKey :self {g('KeySelector')} :InSelectedKey {invoke('Config', 'ExportChord')})
    {put('UpdatingKey', 'false')} (return true))"""
code["KeyChanged"] = f"""(fn KeyChanged (Chord) {guard}
    (if {g('UpdatingKey')} (return false))
    (bind applied {invoke('Config', 'ApplyChord', ':Chord Chord')})
    (if (not applied) (CallFunction|SyncKey) (CallFunction|RefreshUI) (return false))
    (bind saved {invoke('Config', 'SaveSettings', ':Slot "WorkerOptimizer_UI_v1"')})
    (CallFunction|RefreshUI) (return saved))"""
code["IsCapturing"] = f"""(fn IsCapturing () {guard}
    (bind capturing (Class|WBPSettingsPanel|IsCapturing :self {g('PanelHost')})) (return capturing))"""
code["ClickAction"] = f"""(fn ClickAction () {guard}
    (if (not {present(g('Controller'))}) (return false))
    (CallFunction|RefreshDisplayState)
    (if (not {g('ActionEnabled')}) (CallFunction|ApplyActionDisplay) (return false))
    (bind started {invoke('Controller', 'BeginRun')}) (CallFunction|RefreshUI) (return started))"""
code["RefreshSettingsStatus"] = f"""(fn RefreshSettingsStatus () {guard}
    (if (not {present(g('Config'))}) (return false))
    (if (and {g('HasSettingsCache')} (and (== {g('SettingsState')} {g('CachedSettingsState')}) (== {g('LocalizationVersion')} {g('CachedSettingsVersion')}))) (return true))
    (if (or (not {g('HasSettingsCache')}) (!= {g('LocalizationVersion')} {g('CachedSettingsVersion')}))
      {counted(f'(Class|Text|SetText :self {g("HotkeyLabel")} :Text ({text_node} {ui("hotkey")}))')})
    (if (or (not {g('HasSettingsCache')}) (!= {g('LocalizationVersion')} {g('CachedSettingsVersion')}))
      {tooltip(ui('tab.logbook'),'LogbookButton')})
    {put('HasSettingsCache', 'true')} {put('CachedSettingsState', g('SettingsState'))} {put('CachedSettingsVersion', g('LocalizationVersion'))}
    (switch int {g('SettingsState')}
      (:0 {tint(0.75, 0.83, 0.8, 'SettingsButton')} {tooltip(ui('tab.general'), 'SettingsButton')} (return true))
      (:1 {tint(1.0, 0.68, 0.17, 'SettingsButton')} {tooltip(ui('invalid_hotkey'), 'SettingsButton')} (return true))
      (:2 {tint(1.0, 0.35, 0.3, 'SettingsButton')} {tooltip(ui('unsaved_hotkey'), 'SettingsButton')} (return true))
      (:3 {tint(1.0, 0.68, 0.17, 'SettingsButton')} {tooltip(ui('default_hotkey'), 'SettingsButton')} (return true))))"""
code["RefreshDisplayState"] = f"""(fn RefreshDisplayState ()
    (bind manager (Class|Backbone|GetLocManager))
    (if {present('manager')}
      (bind language (Class|LocManager|GetActiveLanguage :self manager))
      (if (!= language {g('DisplayLanguage')}) {put('DisplayLanguage', 'language')} {put('LocalizationVersion', f'(+ {g("LocalizationVersion")} 1)')}
        {put('LayoutWidth','-1.0')} {put('LayoutSettling','true')}))
    {put('SettingsState', '0')}
    (bind failure (Class|BPHotkeyConfig|GetFailureCode :self {g('Config')}))
    (if (!= failure "None") {put('SettingsState', '3')})
    (if (Class|BPHotkeyConfig|GetDirty :self {g('Config')}) {put('SettingsState', '2')})
    (if (== failure "invalid_hotkey") {put('SettingsState', '1')})
    {put('ActionState', '0')} {put('SkippedCount', '0')} {put('ActionEnabled', prop('Initialized'))}
    (bind settings {prop('Settings')})
    (if {present('settings')}
      (if (not (Class|BPPrioritySettings|GetPolicyKeysReady :self settings)) {put('ActionEnabled', 'false')}))
    (if (not {g('ActionEnabled')}) {put('ActionState','8')})
    (if {prop('RunActive')}
      {put('ActionEnabled', 'false')} {put('ActionState', '1')} (return true))
    (bind runner {prop('Runner')})
    (if {present('runner')}
      (if (Class|BPApplicationRunner|GetWaiting :self runner)
        {put('ActionEnabled', 'false')} {put('ActionState', '2')} (return true)))
    (if {prop('ReportPending')}
      {put('ActionEnabled', 'false')} {put('ActionState', '2')} (return true))
    (if {prop('RunDone')}
      {put('ActionState','7')}
      (if {prop('RunSucceeded')} {put('ActionState','3')})
      (if (== {prop('FailureCode')} "cancelled") {put('ActionState','6')})
      {' '.join(f'(if (== '+prop('FailureCode')+f' "{reason}") '+put('ActionState','5')+')' for reason in ('invalid_plan','invalid_snapshot','invalid_phase','configuration_unavailable','builder_score_unavailable','reserve_configuration_failed','observation_unavailable'))}
      (bind report {prop('CompletedReport')})
      (if (and {present('report')} {prop('RunSucceeded')})
        (for reason (Class|BPRunReport|GetGroupReasons :self report)
          (if (not (or (== reason "preserved_paused") (== reason "preserved_unsupported")))
            {put('ActionState','4')} {put('SkippedCount',f'(+ {g("SkippedCount")} 1)')}))))
    (return true))"""
code["ApplyActionDisplay"] = f"""(fn ApplyActionDisplay ()
    (if (and {g('HasActionCache')} (and (== {g('ActionState')} {g('CachedActionState')}) (and (== {g('ActionEnabled')} {g('CachedEnabled')}) (and (== {g('SkippedCount')} {g('CachedSkippedCount')}) (== {g('LocalizationVersion')} {g('CachedActionVersion')}))))) (return true))
    (if (or (not {g('HasActionCache')}) (!= {g('ActionEnabled')} {g('CachedEnabled')}))
      {counted(f'(Widget|SetIsEnabled :self {g("ActionButton")} :bInIsEnabled {g("ActionEnabled")})')})
    {put('CachedEnabled', g('ActionEnabled'))}
    (if (and {g('HasActionCache')} (and (== {g('ActionState')} {g('CachedActionState')}) (and (== {g('SkippedCount')} {g('CachedSkippedCount')}) (== {g('LocalizationVersion')} {g('CachedActionVersion')})))) (return true))
    (if (or (not {g('HasActionCache')}) (or (!= {g('ActionState')} {g('CachedActionState')}) (!= {g('LocalizationVersion')} {g('CachedActionVersion')})))
      (if (or (== {g('ActionState')} 1) (== {g('ActionState')} 2))
        {counted(visible('BusyIndicator', 'HitTestInvisible'))}
        {visible('BusyText','HitTestInvisible')} {visible('ActionButtonIcon','Hidden')} {visible('OutcomeIcon','Collapsed')}
        (Class|Text|SetText :self {g('BusyText')} :Text ({text_node} {ui('ui.working')}))
        (else {counted(visible('BusyIndicator', 'Collapsed'))} {visible('BusyText','Collapsed')} {visible('ActionButtonIcon','HitTestInvisible')}
          (if (and (> {g('ActionState')} 2) (< {g('ActionState')} 8)) {visible('OutcomeIcon','HitTestInvisible')}
            (else {visible('OutcomeIcon','Collapsed')})))))
    {put('HasActionCache', 'true')} {put('CachedActionState', g('ActionState'))}
    {put('CachedSkippedCount', g('SkippedCount'))} {put('CachedActionVersion', g('LocalizationVersion'))}
    (switch int {g('ActionState')}
      (:0 {tint(0.75, 0.83, 0.8)} {tooltip(ui('optimize'))} (return true))
      (:1 {tint(1.0, 0.68, 0.17)} {tooltip(ui('busy'))} (return true))
      (:2 {tint(1.0, 0.68, 0.17)} {tooltip(ui('waiting'))} (return true))
      (:3 {tint(0.3, 0.85, 0.6)} {tooltip('(CallFunction|CompletedTooltip)')} (return true))
      (:4 {tint(1.0, 0.68, 0.17)} {tooltip(ui('history.problems'))} (return true))
      (:5 {tint(1.0, 0.35, 0.3)} {tooltip(ui('failed'))} (return true))
      (:6 {tint(1.0, 0.35, 0.3)} {tooltip(ui('cancelled'))} (return true))
      (:7 {tint(1.0, 0.35, 0.3)} {tooltip(ui('history.problems'))} (return true))
      (:8 {tooltip(ui('ui.initializing'))} (return true))))"""
def hud_tint(widget, key):
    c=token_color(key)
    return counted(f'({background_node} :self {g(widget)} :InBackgroundColor ({color_node} :R {c.r} :G {c.g} :B {c.b} :A 1.0))')
code['RefreshHudSelection']=f'''(fn RefreshHudSelection ()
    (bind opened (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')}))
    (if (!= opened {g('ShadowVisible')})
      {put('ShadowVisible','opened')}
      (if opened {counted(visible('PanelShadow','HitTestInvisible'))}
        (else {counted(visible('PanelShadow','Collapsed'))})))
    (bind tab (Class|WBPSettingsPanel|GetActiveTab :self {g('PanelHost')}))
    (bind settingsStyle (select (> {g('SettingsState')} 0) (select (== {g('SettingsState')} 2) 3 2) (select (and opened (!= tab "logbook")) 1 0)))
    (bind logbookStyle (select (and opened (== tab "logbook")) 1 0))
    (if (!= settingsStyle {g('HUDSettingsStyle')})
      {put('HUDSettingsStyle','settingsStyle')}
      (switch int settingsStyle
        (:0 {hud_tint('SettingsButton','surface')}) (:1 {hud_tint('SettingsButton','sel')})
        (:2 {hud_tint('SettingsButton','warnbg')}) (:3 {hud_tint('SettingsButton','errbg')})))
    (if (!= logbookStyle {g('HUDLogbookStyle')})
      {put('HUDLogbookStyle','logbookStyle')}
      (if (== logbookStyle 1) {hud_tint('LogbookButton','sel')} (else {hud_tint('LogbookButton','surface')})))
    (return true))'''
code["RefreshUI"] = f"""(fn RefreshUI () {guard}
    (if (not {present(g('Controller'))}) (return false))
    (CallFunction|RefreshDisplayState) (CallFunction|RefreshLayout)
    (CallFunction|RefreshSettingsStatus) (CallFunction|RefreshHudSelection) (CallFunction|ApplyActionDisplay)
    (if (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')})
      (Class|WBPSettingsPanel|RefreshPanel :self {g('PanelHost')}))
    {put('SettingsOpen',f'(Class|WBPSettingsPanel|GetPanelOpen :self {g("PanelHost")})')}
    (CallFunction|UpdateGeometryWatcher)
    (return true))"""
code["ShutdownUI"] = f"""(fn ShutdownUI ()
    {put('Closed', 'true')} {put('Initialized', 'false')} {put('SettingsOpen', 'false')} {put('ButtonVisible', 'false')}
    {put('GeometryWatching','false')}
    {put('ShadowVisible','false')} {visible('PanelShadow','Collapsed')}
    (CallFunction|UnbindPulse)
    (UserInterface|Animation|StopAnimation :self self :InAnimation {g('GeometryPulse')})
    (if {g('NotificationsBound')}
      (if {present(g('Controller'))} (CallFunction|UnbindController))
      (if {present(g('History'))} (CallFunction|UnbindHistory))
      (if {present(g('SettingsModel'))} (CallFunction|UnbindModel))
      (CallFunction|UnbindPanel))
    {put('NotificationsBound','false')}
    (if {present(g('Controls'))} {visible('Controls', 'Collapsed')})
    (Class|WBPSettingsPanel|ClosePanel :self {g('PanelHost')})
    (Variables|Default|SetController) (Variables|Default|SetConfig) (Variables|Default|SetTexts) (return true))"""
play_pulse=f'(UserInterface|Animation|PlayAnimation :self self :InAnimation {g("GeometryPulse")} :NumLoopsToPlay 1 :PlaybackSpeed 1.0 :StartAtTime 0.0)'
code['OnPresentation']='(fn OnPresentation () (CallFunction|RefreshUI))'
code['OnPanelEvent']=f'''(fn OnPanelEvent ()
    (if {g('Closed')} (return))
    (if (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')})
      {put('LayoutWidth','-1.0')} {put('LayoutSettling','true')} (CallFunction|MeasureHud))
    (CallFunction|RefreshUI))'''
code['OnGeometryPulse']=f'''(fn OnGeometryPulse ()
    (if (or {g('Closed')} (not {g('GeometryWatching')})) (return))
    (if (not (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')}))
      {put('GeometryWatching','false')} (return))
    (if {g('LayoutSettling')} {put('LayoutWidth','-1.0')} {put('LayoutSettling','false')})
    (CallFunction|MeasureCachedHud) (CallFunction|RefreshLayout) {play_pulse})'''
code['UpdateGeometryWatcher']=f'''(fn UpdateGeometryWatcher ()
    (bind opened (Class|WBPSettingsPanel|GetPanelOpen :self {g('PanelHost')}))
    (if opened (if (not {g('GeometryWatching')}) {put('GeometryWatching','true')} {play_pulse})
      (else (if {g('GeometryWatching')} {put('GeometryWatching','false')}
        (UserInterface|Animation|StopAnimation :self self :InAnimation {g('GeometryPulse')}))))
    (return true))'''
code['MeasureHud']=f'''(fn MeasureHud ()
    (Variables|Default|SetNativeHudWidget) {put('NativeHudBottom','0.0')}
    (bind widgets (Widget|GetAllWidgetsOfClass :WidgetClass "/Script/ProjectArco.PlayHud" :TopLevelOnly false))
    (for widget widgets
      (bind hud (Utilities|Casting|CastToPlayHud :Object widget))
      (bind toolbar (Class|PlayHud|GetMToolbar :self hud))
      (if {present('toolbar')}
        {put('NativeHudWidget','toolbar')} (break)))
    (CallFunction|MeasureCachedHud) (return true))'''
code['MeasureCachedHud']=f'''(fn MeasureCachedHud ()
    (if {present(g('NativeHudWidget'))}
        (bind geometry (Widget|GetCachedGeometry :self {g('NativeHudWidget')}))
        (bind size (UserInterface|Geometry|GetLocalSize :Geometry geometry))
        (bind (width height) (Math|Vector2D|BreakVector2D :InVec size))
        (bind (pixel viewport) (UserInterface|Geometry|LocaltoViewport :Geometry geometry :LocalCoordinate size))
        (bind (x bottom) (Math|Vector2D|BreakVector2D :InVec viewport))
        (if (and (> height 0.0) (and (< height 200.0) (and (> bottom 0.0) (< bottom 200.0))))
          (if (!= bottom {g('NativeHudBottom')}) {put('NativeHudBottom','bottom')} {put('LayoutWidth','-1.0')}))
      (else (if (> {g('NativeHudBottom')} 0.0) {put('NativeHudBottom','0.0')} {put('LayoutWidth','-1.0')})))
    (return true))'''
binding_specs=[('Controller','Controller',load('BP_WorkerOptimizer'),'OnControllerPresentationChanged','OnPresentation'),
               ('History','History',load('BP_Logbook'),'OnHistoryPresentationChanged','OnPresentation'),
               ('Model','SettingsModel',load('BP_SettingsModel'),'OnSettingsPresentationChanged','OnPresentation'),
               ('Panel','PanelHost',load('WBP_SettingsPanel'),'OnPanelChanged','OnPanelEvent')]
for prefix,_,_,_,_ in binding_specs:
    for action_name in ('Bind','Unbind'):
        code[action_name+prefix]=f'(fn {action_name+prefix} () (return true))'
code['BindPulse']='(fn BindPulse () (return true))'
code['UnbindPulse']='(fn UnbindPulse () (return true))'

badge_color_node=native(graphs['ApplyActionDisplay'],'SetColorAndOpacity','TextBlock')
badge_color_pin=next(p.name for p in BP.get_node_type_pins(graphs['ApplyActionDisplay'],badge_color_node).input_pins if p.name in ('InColorAndOpacity','ColorAndOpacity'))
slate_color_nodes=[n for n in node_types if n.endswith('|MakeSlateColor')]
assert len(slate_color_nodes)==1, [n for n in node_types if 'SlateColor' in n]
slate_color_node=slate_color_nodes[0]
badge_updates=[]
for state,key,symbol,texture in ((3,'ok','\u2713','Completed'),(4,'warn','\u25b3','Problems'),(5,'err','\u2bc3','Error'),(6,'abort','\u2298','Aborted'),(7,'warn','\u25b3','Problems')):
    c=token_color(key)
    badge_updates.append(f'''(if (== {g('ActionState')} {state})
      (Class|Text|SetText :self {g('OutcomeBadge')} :Text ({text_node} "{symbol}"))
      (CallFunction|ImageSetTexture :Target {g('OutcomeIcon')} :Texture "{ROOT}/T_WorkerOptimizerStatus{texture}.T_WorkerOptimizerStatus{texture}")
      (CallFunction|ImageSetColor :Target {g('OutcomeIcon')} :Color ({color_node} :R {c.r} :G {c.g} :B {c.b} :A 1.0))
      ({badge_color_node} :self {g('OutcomeBadge')} :{badge_color_pin} ({slate_color_node} :SpecifiedColor ({color_node} :R {c.r} :G {c.g} :B {c.b} :A 1.0))))''')
code['ApplyActionDisplay']=code['ApplyActionDisplay'].replace("    (switch int ", '    '+' '.join(badge_updates)+'\n    (switch int ')
code.update(image_wrapper_code())

def wire_delegate(function, field, owner, dispatcher, callback, unbind=False, animation=False):
    graph=graphs[function]
    infos=BP.get_node_infos(BP.find_nodes(graph))
    entry=next(n for n in infos if any(p.name=='then' for p in n.output_pins))
    result=next(n for n in infos if any(p.name=='Result' for p in n.input_pins))
    kind=('Animation|UnbindfromAnimationFinished' if unbind else 'Animation|BindtoAnimationFinished') if animation else 'Default|'+('UnbindEventfrom' if unbind else 'BindEventto')+dispatcher
    target=BP.create_node(graph,kind,unreal.IntPoint(400,0))
    get=BP.create_node(graph,g(field)[1:-1],unreal.IntPoint(0,100))
    target_info,get_info=BP.get_node_infos([target,get])
    BP.connect_pins(next(p.pin_id for p in get_info.output_pins if p.name!='then'),next(p.pin_id for p in target_info.input_pins if p.name==('Animation' if animation else 'self')))
    delegate=BP.create_node(graph,'EventDispatchers|CreateEvent',unreal.IntPoint(0,200))
    delegate_info=BP.get_node_infos([delegate])[0]
    BP.connect_pins(next(p.pin_id for p in delegate_info.output_pins if p.name=='OutputDelegate'),next(p.pin_id for p in target_info.input_pins if p.name=='Delegate'))
    BP.set_create_event_function(delegate,callback)
    BP.connect_pins(next(p.pin_id for p in entry.output_pins if p.name=='then'),next(p.pin_id for p in target_info.input_pins if p.name=='execute'))
    BP.connect_pins(next(p.pin_id for p in target_info.output_pins if p.name=='then'),next(p.pin_id for p in result.input_pins if p.name=='execute'))
for function, source in code.items():
    try:
        blueprint_dsl.parse(source)
    except RuntimeError:
        unreal.log_error('WO_HUD_PARSE '+function+' '+source)
        raise
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_WIDGET_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    image_wrappers(bp)
    for prefix,field,owner,dispatcher,callback in binding_specs:
        for removing in (False,True):
            wire_delegate(('Unbind' if removing else 'Bind')+prefix,field,owner,dispatcher,callback,removing)
    for removing in (False,True):
        wire_delegate(('Unbind' if removing else 'Bind')+'Pulse','GeometryPulse',unreal.UserWidget.static_class(),'', 'OnGeometryPulse',removing,True)
    event_graph = BP.get_graph(bp, "EventGraph")
    for node in BP.find_nodes(event_graph):
        BP.delete_node(node)
    for widget, event, handler, kind in (
        ("ActionButton", "OnClicked", "ClickAction", unreal.Button),
        ("SettingsButton", "OnClicked", "ToggleSettings", unreal.Button),
        ("LogbookButton", "OnClicked", "OpenLogbook", unreal.Button),
        ("KeySelector", "OnKeySelected", "KeyChanged", unreal.InputKeySelector),
    ):
        old = set(str(n.get_path_name()) for n in BP.find_nodes(event_graph))
        assert call("BindToEventProperty", bp, event, widget, kind.static_class())
        nodes = [n for n in BP.find_nodes(event_graph) if str(n.get_path_name()) not in old]
        assert len(nodes) == 1, (widget, nodes)
        event_info = BP.get_node_infos(nodes)[0]
        target = BP.create_node(event_graph, "CallFunction|" + handler, unreal.IntPoint(400, 0))
        target_info = BP.get_node_infos([target])[0]
        unreal.log("WO_WIDGET_EVENT " + widget + " " + str([(p.name, p.type_id) for p in event_info.output_pins]))
        BP.connect_pins(next(p.pin_id for p in event_info.output_pins if p.name == "then"),
                        next(p.pin_id for p in target_info.input_pins if p.name == "execute"))
        if handler == "KeyChanged":
            BP.connect_pins(next(p.pin_id for p in event_info.output_pins if p.name == "SelectedKey"),
                            next(p.pin_id for p in target_info.input_pins if p.name == "Chord"))
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Widget.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_WIDGET_GENERATED")
