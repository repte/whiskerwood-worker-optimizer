"""Author a native compact UMG control and explicit click-only command wiring."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda name: unreal.load_class(None, ROOT + "/" + name + "." + name + "_C")
umg = unreal.get_default_object(unreal.UMGToolSet)
call = lambda name, *args: umg.call_method(name, args=args)
bp = unreal.load_asset(ROOT + "/WBP_WorkerOptimizer") if unreal.EditorAssetLibrary.does_asset_exist(ROOT + "/WBP_WorkerOptimizer") else None
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
    info = existing_widgets.get(name)
    if info:
        assert info.widget.get_class() == kind.static_class() and info.parent == parent, name
    else:
        info = call("AddWidget", bp, kind.static_class(), name, parent, -1)
    assert info.widget, name
    if variable and not info.is_variable:
        call("ToggleWidgetAsVariable", bp, info.widget, True)
    return info.widget, info.slot


def box(slot, x, y, width, height, bottom=False):
    slot.set_anchors(unreal.Anchors(unreal.Vector2D(0, 1 if bottom else 0), unreal.Vector2D(0, 1 if bottom else 0)))
    slot.set_position(unreal.Vector2D(x, y))
    slot.set_size(unreal.Vector2D(width, height))


def icon(parent, path, size):
    obj, slot = add(unreal.Image, parent.get_name() + "Icon", parent)
    texture = unreal.load_asset(path)
    assert texture, path
    obj.set_brush_from_texture(texture, False)
    obj.set_desired_size_override(unreal.Vector2D(size, size))
    obj.set_visibility(unreal.SlateVisibility.HIT_TEST_INVISIBLE)
    slot.set_padding(unreal.Margin(6, 6, 6, 6))
    return obj


def button_style(widget, icon_only=False):
    style = widget.get_editor_property("widget_style")
    if icon_only:
        style.set_editor_property("normal_padding", unreal.Margin(0, 0, 0, 0))
        style.set_editor_property("pressed_padding", unreal.Margin(0, 1, 0, 0))
    for name, level in (("normal", 0.06), ("hovered", 0.13), ("pressed", 0.035)):
        brush = style.get_editor_property(name)
        brush.set_editor_property("tint_color", unreal.SlateColor(unreal.LinearColor(level, level, level, 1)))
        style.set_editor_property(name, brush)
    for name in ("normal_foreground", "hovered_foreground", "pressed_foreground"):
        style.set_editor_property(name, unreal.SlateColor(unreal.LinearColor(1, 1, 1, 1)))
    widget.set_editor_property("widget_style", style)


root, _ = add(unreal.CanvasPanel, "Root")
root.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
controls, slot = add(unreal.CanvasPanel, "Controls", root, True)
box(slot, 180, -170, 372, 144, True)
controls.set_visibility(unreal.SlateVisibility.SELF_HIT_TEST_INVISIBLE)
action, slot = add(unreal.Button, "ActionButton", controls, True)
box(slot, 0, 96, 44, 44)
action.set_editor_property("is_focusable", False)
button_style(action, True)
icon(action, "/Game/Assets/Icons/BoardGameIcons/arrow_clockwise", 28)
settings, slot = add(unreal.Button, "SettingsButton", controls, True)
box(slot, 48, 108, 28, 28)
settings.set_editor_property("is_focusable", False)
button_style(settings, True)
settings.set_tool_tip_text("Worker Optimizer: Hotkey")
icon(settings, "/Game/Assets/Icons/icons8-gear-100", 16)
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
font.set_editor_property("size", 12)
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
key_font.set_editor_property("size", 12)
text_style.set_editor_property("font", key_font)
text_style.set_editor_property("color_and_opacity", unreal.SlateColor(unreal.LinearColor(1, 1, 1, 1)))
selector.set_editor_property("text_style", text_style)
BP.compile_blueprint(bp)

refs = {"Controller": "BP_WorkerOptimizer", "Config": "BP_HotkeyConfig", "Texts": "BP_PrioritySettings"}
existing = set(BP.list_variables(bp))
for name, asset in refs.items():
    if name not in existing:
        BP.add_object_variable(bp, name, load(asset))
for name in ("Initialized", "Closed", "ButtonVisible", "SettingsOpen", "UpdatingKey"):
    if name not in existing:
        BP.add_variable(bp, name, "bool")
for name in ("LayoutWidth", "LayoutHeight", "LayoutX", "LayoutBottom", "LayoutPanelWidth"):
    if name not in existing:
        BP.add_variable(bp, name, "float")
chord = unreal.load_object(None, "/Script/Slate.InputChord")
definitions = {
    "HasObject": [("Object", unreal.Object.static_class())],
    "InitializeUI": [("InputController", load("BP_WorkerOptimizer")), ("InputConfig", load("BP_HotkeyConfig"))],
    "ToggleButton": [], "ToggleSettings": [], "ClickAction": [], "RefreshUI": [], "RefreshSettingsStatus": [],
    "SyncKey": [], "KeyChanged": [("Chord", chord)], "IsCapturing": [], "ShutdownUI": [],
    "UIString": [("Key", "string")],
    "ApplyLayout": [("Width", "float"), ("Height", "float")], "RefreshLayout": [],
}
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
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Text" if name == "UIString" else "Result", "string" if name == "UIString" else "bool", False)
BP.compile_blueprint(bp)

node_types = BP.find_node_types(graphs["InitializeUI"], "", [])
widget_getters = {}
for name in ("Controls", "ActionButton", "SettingsButton", "SettingsPanel", "KeySelector", "HotkeyLabel"):
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
background_node = None
for node in node_types:
    if node.endswith("|SetBackgroundColor"):
        pins = BP.get_node_type_pins(graphs["RefreshUI"], node).input_pins
        if any(p.name == "InBackgroundColor" for p in pins) and any("Button Object" in str(p.type_id) for p in pins):
            background_node = node
            break
assert background_node, "Native button color setter unavailable"


def tooltip(value, widget="ActionButton"):
    return f'(Widget|SetToolTipText :self {g(widget)} :InToolTipText ({text_node} {value}))'


def ui(key):
    return f'(CallFunction|UIString :Key "{key}")'


def tint(red, green, blue, widget="ActionButton"):
    return f'({background_node} :self {g(widget)} :InBackgroundColor ({color_node} :R {red} :G {green} :B {blue} :A 1.0))'


guard = f"(if (or {g('Closed')} (not {g('Initialized')})) (return false))"
code = {}
code["ApplyLayout"] = f"""(fn ApplyLayout (Width Height)
    (if (or (< Width 280.0) (< Height 180.0)) (return false))
    (if (and (== Width {g('LayoutWidth')}) (== Height {g('LayoutHeight')})) (return true))
    {put('LayoutWidth', 'Width')} {put('LayoutHeight', 'Height')}
    {put('LayoutX', '180.0')}
    (if (> {g('LayoutX')} (- Width 100.0)) {put('LayoutX', '(- Width 100.0)')})
    {put('LayoutBottom', '170.0')}
    (if (< Width 1600.0) {put('LayoutBottom', '240.0')})
    (if (> {g('LayoutBottom')} (- Height 12.0)) {put('LayoutBottom', '(- Height 12.0)')})
    {put('LayoutPanelWidth', '372.0')}
    (if (> {g('LayoutPanelWidth')} (- (- Width {g('LayoutX')}) 12.0))
        {put('LayoutPanelWidth', f'(- (- Width {g("LayoutX")}) 12.0)')})
    (Layout|CanvasSlot|SetPosition :self (Slot|SlotasCanvasSlot :Widget {g('Controls')})
        :InPosition (Math|Vector2D|MakeVector2D :X {g('LayoutX')} :Y (- 0.0 {g('LayoutBottom')})))
    (Layout|CanvasSlot|SetSize :self (Slot|SlotasCanvasSlot :Widget {g('Controls')})
        :InSize (Math|Vector2D|MakeVector2D :X {g('LayoutPanelWidth')} :Y 144.0))
    (if (> {g('LayoutPanelWidth')} 360.0) {put('LayoutPanelWidth', '360.0')})
    (Layout|CanvasSlot|SetSize :self (Slot|SlotasCanvasSlot :Widget {g('SettingsPanel')})
        :InSize (Math|Vector2D|MakeVector2D :X {g('LayoutPanelWidth')} :Y 86.0))
    (return true))"""
code["RefreshLayout"] = """(fn RefreshLayout ()
    (bind size (Viewport|GetViewportSize))
    (bind scale (Viewport|GetViewportScale))
    (if (<= scale 0.0) (return false))
    (bind (x y) (Math|Vector2D|BreakVector2D :InVec size))
    (bind applied (CallFunction|ApplyLayout :Width (/ x scale) :Height (/ y scale)))
    (return applied))"""
code["UIString"] = f"""(fn UIString (Key)
    (if (not {present(g('Texts'))}) (return Key))
    (bind translated {invoke('Texts', 'Text', ':Key Key')}) (return translated))"""
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
    (CallFunction|SyncKey) (CallFunction|RefreshUI) (return true))"""
code["ToggleButton"] = f"""(fn ToggleButton () {guard}
    {put('ButtonVisible', f'(not {g("ButtonVisible")})')}
    {put('SettingsOpen', 'false')} {visible('SettingsPanel', 'Collapsed')}
    (if {g('ButtonVisible')} {visible('Controls', 'SelfHitTestInvisible')}
      (else {visible('Controls', 'Collapsed')})) (return true))"""
code["ToggleSettings"] = f"""(fn ToggleSettings () {guard}
    (if (not {g('ButtonVisible')}) (return false))
    {put('SettingsOpen', f'(not {g("SettingsOpen")})')}
    (if {g('SettingsOpen')} {visible('SettingsPanel', 'Visible')} (CallFunction|SyncKey)
      (else {visible('SettingsPanel', 'Collapsed')})) (return true))"""
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
    (if (not {g('SettingsOpen')}) (return false))
    (return (Widget|GetIsSelectingKey :self {g('KeySelector')})))"""
code["ClickAction"] = f"""(fn ClickAction () {guard}
    (if (not {present(g('Controller'))}) (return false))
    (if {prop('RunActive')}
      (bind cancelled {invoke('Controller', 'CancelRun')}) (CallFunction|RefreshUI) (return cancelled))
    (bind started {invoke('Controller', 'BeginRun')}) (CallFunction|RefreshUI) (return started))"""
code["RefreshSettingsStatus"] = f"""(fn RefreshSettingsStatus () {guard}
    (if (not {present(g('Config'))}) (return false))
    {tint(0.75, 0.83, 0.8, 'SettingsButton')}
    {tooltip(ui('hotkey'), 'SettingsButton')}
    (Class|Text|SetText :self {g('HotkeyLabel')} :Text ({text_node} {ui('hotkey')}))
    (bind failure (Class|BPHotkeyConfig|GetFailureCode :self {g('Config')}))
    (if (== failure "invalid_hotkey")
      {tint(1.0, 0.68, 0.17, 'SettingsButton')}
      {tooltip(ui('invalid_hotkey'), 'SettingsButton')} (return true))
    (if (Class|BPHotkeyConfig|GetDirty :self {g('Config')})
      {tint(1.0, 0.35, 0.3, 'SettingsButton')}
      {tooltip(ui('unsaved_hotkey'), 'SettingsButton')} (return true))
    (if (!= failure "None")
      {tint(1.0, 0.68, 0.17, 'SettingsButton')}
      {tooltip(ui('default_hotkey'), 'SettingsButton')})
    (return true))"""
code["RefreshUI"] = f"""(fn RefreshUI () {guard}
    (if (not {present(g('Controller'))}) (return false))
    (CallFunction|RefreshLayout)
    (CallFunction|RefreshSettingsStatus)
    (Widget|SetIsEnabled :self {g('ActionButton')} :bInIsEnabled {prop('Initialized')})
    {tint(0.75, 0.83, 0.8)}
    {tooltip(ui('optimize'))}
    (if {prop('RunActive')}
      {tint(1.0, 0.68, 0.17)}
      {tooltip(ui('cancel'))}
      (return true))
    (bind runner {prop('Runner')})
    (if {present('runner')}
      (if (Class|BPApplicationRunner|GetWaiting :self runner)
        (Widget|SetIsEnabled :self {g('ActionButton')} :bInIsEnabled false)
        {tint(1.0, 0.68, 0.17)} {tooltip(ui('waiting'))} (return true)))
    (if {prop('RunDone')}
      (if {prop('RunSucceeded')}
        {tint(0.3, 0.85, 0.6)}
        {tooltip(ui('completed'))}
        (bind snapshot {prop('Snapshot')})
        (if {present('snapshot')}
          (bind skipped (Utilities|Array|Length (Class|BPWorkforceSnapshot|GetCompatibilityBuildings :self snapshot)))
          (if (> skipped 0)
            {tint(1.0, 0.68, 0.17)}
            {tooltip(f'(Utilities|String|Append :A {ui("skipped")} :B (Utilities|String|ToString(Integer) skipped))')}))
        (else {tint(1.0, 0.35, 0.3)} {tooltip(ui('failed'))}
          (if (== {prop('FailureCode')} "cancelled") {tooltip(ui('cancelled'))})
          (if (== {prop('FailureCode')} "world_changed") {tooltip(ui('world_changed'))}))))
    (return true))"""
code["ShutdownUI"] = f"""(fn ShutdownUI ()
    {put('Closed', 'true')} {put('Initialized', 'false')} {put('SettingsOpen', 'false')} {put('ButtonVisible', 'false')}
    (if {present(g('Controls'))} {visible('Controls', 'Collapsed')})
    (Variables|Default|SetController) (Variables|Default|SetConfig) (Variables|Default|SetTexts) (return true))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_WIDGET_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    event_graph = BP.get_graph(bp, "EventGraph")
    for node in BP.find_nodes(event_graph):
        BP.delete_node(node)
    for widget, event, handler, kind in (
        ("ActionButton", "OnClicked", "ClickAction", unreal.Button),
        ("SettingsButton", "OnClicked", "ToggleSettings", unreal.Button),
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
exec(Path(__file__).with_name("test_widget.py").read_text(encoding="utf-8"))
