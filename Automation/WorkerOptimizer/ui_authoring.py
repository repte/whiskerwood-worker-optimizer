"""Small shared native Blueprint/UMG authoring primitives for compact panels."""
from pathlib import Path
import json
import re
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
load = lambda n: unreal.load_class(None, ROOT + "/" + n + "." + n + "_C")
GETTERS = {}
g = lambda n: f"({GETTERS.get(n, 'Variables|Default|Get' + n)})"
put = lambda n, v: f"(Variables|Default|Set{n} {v})"
at = lambda a, i: f'(Utilities|Array|Get(acopy) :Array {a} :"Dimension 1" {i})'
length = lambda a: f"(Utilities|Array|Length {a})"
invoke = lambda cls, obj, fn, args="": f"(Class|{cls.replace('_', '')}|{fn} :self {obj} {args})"
prop = lambda cls, obj, n: invoke(cls, obj, "Get" + n)
TEXT_NODE = "Utilities|Text|ToText(String)"
text = lambda value: f"({TEXT_NODE} {value})"
TEXT_STRING_NODE = "Utilities|String|ToString(Text)"
text_string = lambda value: f"({TEXT_STRING_NODE} {value})"


def declare(bp, variables, functions, objects=None):
    existing = set(BP.list_variables(bp))
    for kind, names in variables.items():
        for name in names.split():
            if name not in existing:
                BP.add_variable(bp, name, kind.removesuffix("[]"), container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
    for name, cls in (objects or {}).items():
        if name not in existing:
            BP.add_object_variable(bp, name, cls)
    existing_graphs = {str(v.get_name()) for v in BP.list_graphs(bp)}
    graphs = {}
    for name, (inputs, outputs) in functions.items():
        graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
        if name in existing_graphs:
            continue
        for is_input, params in ((True, inputs), (False, outputs)):
            for param, kind in params:
                if isinstance(kind, str):
                    BP.add_function_param(graphs[name], param, kind, is_input)
                elif isinstance(kind, unreal.ScriptStruct):
                    BP.add_struct_function_param(graphs[name], param, kind, is_input)
                else:
                    BP.add_object_function_param(graphs[name], param, kind, is_input)
    BP.compile_blueprint(bp)
    global TEXT_NODE, TEXT_STRING_NODE
    GETTERS.clear()
    nodes = BP.find_node_types(next(iter(graphs.values())), "", [])
    for candidate in nodes:
        if candidate.endswith("|ToText(String)"):
            TEXT_NODE = candidate
        if candidate.endswith("|ToString(Text)"):
            TEXT_STRING_NODE = candidate
        if candidate.startswith("Variables|") and "|Get" in candidate:
            GETTERS[candidate.rsplit("|Get", 1)[1]] = candidate
    return graphs


def emit(bp, graphs, code, defaults=None):
    for source in code.values():
        blueprint_dsl.parse(source)
    with toolset_registry.tool_raising_exceptions():
        for name, source in code.items():
            unreal.log("WO_UI_WRITE " + bp.get_name() + "." + name)
            BP.write_graph_dsl(graphs[name], source)
        BP.compile_blueprint(bp, warnings_as_errors=True)
        cdo = unreal.get_default_object(bp.generated_class())
        for name, value in (defaults or {}).items():
            cdo.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), bp.get_name() + ".dsl").write_text("\n\n".join(code.values()), encoding="utf-8")


def widget(name, reset=False, reset_layout=False):
    tools = unreal.get_default_object(unreal.UMGToolSet)
    call = lambda fn, *args: tools.call_method(fn, args=args)
    path = ROOT + "/" + name
    bp = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
    if bp is None:
        bp = call("CreateWidgetBlueprint", ROOT, name, unreal.UserWidget.static_class())
        assert bp, name
        tree = call("GetWidgets", bp)
        for item in tree.widgets:
            if not item.parent:
                call("RemoveWidget", bp, item.widget)
    if reset:
        for graph in list(BP.list_graphs(bp)):
            if str(graph.get_name()) != 'EventGraph':
                BP.remove_function_graph(bp, str(graph.get_name()))
            else:
                for node in BP.find_nodes(graph):
                    BP.delete_node(node)
        # Flush same-class reflected functions before reusing their names.
        # Otherwise the editor can mistake removed functions for inherited ones.
        BP.compile_blueprint(bp)
    if reset_layout and not reset:
        for graph in BP.list_graphs(bp):
            for node in BP.find_nodes(graph):
                if node.get_class().get_name() not in ('K2Node_FunctionEntry', 'K2Node_FunctionResult'):
                    BP.delete_node(node)
    if reset or reset_layout:
        # Keep existing function signatures during layout-only regeneration so
        # dependent widgets never observe a temporarily missing interface.
        for item in call('GetWidgets', bp).widgets:
            if not item.parent:
                call('RemoveWidget', bp, item.widget)
    entries = {str(w.widget_name): w for w in call("GetWidgets", bp).widgets}

    def add(kind, key, parent=None, variable=True):
        klass = kind if isinstance(kind, unreal.Class) else kind.static_class()
        item = entries.get(key)
        if isinstance(parent, unreal.ContentWidget):
            current = parent.get_content()
            if current and (not item or current != item.widget):
                parent.clear_children()
        item = item or call("AddWidget", bp, klass, key, parent, -1)
        assert item.widget, key
        entries[key] = item
        if parent and item.widget.get_parent() != parent:
            item.widget.remove_from_parent()
            parent.add_child(item.widget)
        if variable and not item.is_variable:
            call("ToggleWidgetAsVariable", bp, item.widget, True)
        return item.widget, item.widget.slot
    return bp, add


TOKENS = json.loads(Path(__file__).with_name('ui_tokens.json').read_text(encoding='utf-8-sig'))


def color(name):
    value = TOKENS['farben'].get(name, {}).get('hex') or TOKENS['statusflaechen'].get(name) or TOKENS['weitere_farben'][name]
    values = [int(value[i:i+2], 16) / 255.0 for i in (1, 3, 5)]
    # Slate consumes linear colors; designer hex colors are sRGB.
    values = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in values]
    return unreal.LinearColor(*values, 1.0)


INK, MUTED, GOLD, SURFACE, FIELD = [color(k) for k in ('text', 'text2', 'gold', 'panel', 'surface')]


def brush_tint(style, field, color):
    brush = style.get_editor_property(field)
    brush.set_editor_property('tint_color', unreal.SlateColor(color))
    style.set_editor_property(field, brush)


def font_points(slate_units):
    # FSlateFontInfo.Size is in points; Slate renders fonts at 96 DPI.
    return float(slate_units) * 72.0 / 96.0


def font_size(owner, field='font', size=15):
    # Keep the existing composite font and its multilingual fallback chain.
    font = owner.get_editor_property(field)
    font.set_editor_property('size', font_points(size))
    font.set_editor_property('typeface_font_name','Semi Bold' if size >= 16 else 'Regular')
    game_font = unreal.load_asset('/Game/Assets/Fonts/Poppins/Poppins')
    if game_font:
        font.set_editor_property('font_object', game_font)
    owner.set_editor_property(field, font)


def control_brush(fill, outline='line2', radius=4, width=1):
    brush = unreal.SlateBrush()
    brush.set_editor_property('draw_as', unreal.SlateBrushDrawType.ROUNDED_BOX)
    brush.set_editor_property('tint_color', unreal.SlateColor(color(fill)))
    edge = brush.get_editor_property('outline_settings')
    edge.set_editor_property('rounding_type', unreal.SlateBrushRoundingType.FIXED_RADIUS)
    edge.set_editor_property('corner_radii', unreal.Vector4(radius,radius,radius,radius))
    edge.set_editor_property('color', unreal.SlateColor(color(outline)))
    edge.set_editor_property('width', width)
    brush.set_editor_property('outline_settings', edge)
    return brush


def style_scrollbar(widget):
    is_scrollbox = isinstance(widget, unreal.ScrollBox)
    assert is_scrollbox or isinstance(widget, unreal.ListView), widget
    field = 'widget_bar_style' if is_scrollbox else 'scroll_bar_style'
    style = widget.get_editor_property(field)
    transparent = unreal.SlateBrush()
    transparent.set_editor_property('draw_as', unreal.SlateBrushDrawType.NO_DRAW_TYPE)
    if is_scrollbox:
        # Invisible SImage track slots still contribute their brush's desired size.
        image_size = transparent.get_editor_property('image_size')
        assert image_size.import_text('(X=0,Y=0)')
        transparent.set_editor_property('image_size', image_size)
    for name in ('horizontal_background_image','vertical_background_image',
                 'horizontal_top_slot_image','vertical_top_slot_image',
                 'horizontal_bottom_slot_image','vertical_bottom_slot_image'):
        style.set_editor_property(name, transparent)
    for name, token in (('normal_thumb_image','line2'),
                        ('hovered_thumb_image','line3'),('dragged_thumb_image','line3')):
        thumb = control_brush(token, token, radius=3, width=0)
        image_size = thumb.get_editor_property('image_size')
        assert image_size.import_text('(X=6,Y=6)')
        thumb.set_editor_property('image_size', image_size)
        style.set_editor_property(name, thumb)
    style.set_editor_property('thickness', 6.0)
    widget.set_editor_property(field, style)
    widget.set_editor_property('scrollbar_padding' if is_scrollbox else 'scroll_bar_padding', unreal.Margin(0))
    if is_scrollbox:
        widget.set_editor_property('scrollbar_thickness', unreal.Vector2D(6,6))


def nine_slice_brush(name, size, margin):
    texture = unreal.load_asset(ROOT + '/' + name)
    assert isinstance(texture, unreal.Texture2D), 'Generate native UI frame assets first: ' + name
    brush = unreal.SlateBrush()
    brush.set_editor_property('resource_object', texture)
    brush.set_editor_property('draw_as', unreal.SlateBrushDrawType.BOX)
    brush.set_editor_property('margin', unreal.Margin(margin, margin, margin, margin))
    image_size=brush.get_editor_property('image_size')
    assert image_size.import_text(f'(X={size},Y={size})')
    brush.set_editor_property('image_size',image_size)
    brush.set_editor_property('tint_color', unreal.SlateColor(unreal.LinearColor(1,1,1,1)))
    return brush


def button_style(style):
    for field, fill, edge in [('normal','surface','line2'),('hovered','hover','line3'),('pressed','sunken','goldlo'),('disabled','dbg','dline')]:
        style.set_editor_property(field, control_brush(fill,edge))
    for field in ('normal_foreground','hovered_foreground','pressed_foreground','disabled_foreground'):
        style.set_editor_property(field, unreal.SlateColor(INK if field != 'disabled_foreground' else color('dtext')))
    style.set_editor_property('normal_padding', unreal.Margin(12,4,12,4))
    style.set_editor_property('pressed_padding', unreal.Margin(12,4,12,4))
    return style


def input_style(widget):
    if isinstance(widget, unreal.ComboBoxString):
        font_size(widget)
        widget.set_editor_property('foreground_color', unreal.SlateColor(INK))
        widget.set_editor_property('content_padding', unreal.Margin(10,7,10,7))
        widget.set_editor_property('max_list_height', 240.0)
        style = widget.get_editor_property('widget_style')
        combo = style.get_editor_property('combo_button_style')
        combo.set_editor_property('button_style', button_style(combo.get_editor_property('button_style')))
        brush_tint(combo, 'down_arrow_image', INK)
        brush_tint(combo, 'menu_border_brush', SURFACE)
        style.set_editor_property('combo_button_style', combo)
        widget.set_editor_property('widget_style', style)
        rows = widget.get_editor_property('item_style')
        for field in ('even_row_background_brush','odd_row_background_brush'):
            brush_tint(rows, field, FIELD)
        for field in ('active_brush','active_hovered_brush','inactive_brush','inactive_hovered_brush','even_row_background_hovered_brush','odd_row_background_hovered_brush'):
            brush_tint(rows, field, GOLD)
        rows.set_editor_property('text_color', unreal.SlateColor(INK))
        rows.set_editor_property('selected_text_color', unreal.SlateColor(INK))
        widget.set_editor_property('item_style', rows)
    elif isinstance(widget, unreal.SpinBox):
        font_size(widget)
        widget.set_editor_property('foreground_color', unreal.SlateColor(INK))
        style = widget.get_editor_property('widget_style')
        for field in ('background_brush','active_background_brush','hovered_background_brush','inactive_fill_brush'):
            brush_tint(style, field, FIELD)
        for field in ('active_fill_brush','hovered_fill_brush'):
            brush_tint(style, field, GOLD)
        style.set_editor_property('text_padding', unreal.Margin(10,7,10,7))
        widget.set_editor_property('widget_style', style)
    elif isinstance(widget, unreal.InputKeySelector):
        widget.set_editor_property('widget_style', button_style(widget.get_editor_property('widget_style')))
        style = widget.get_editor_property('text_style')
        font_size(style)
        style.set_editor_property('color_and_opacity', unreal.SlateColor(INK))
        widget.set_editor_property('text_style', style)
        widget.set_editor_property('key_selection_text', unreal.Text('...'))
    elif isinstance(widget, unreal.EditableTextBox):
        style = widget.get_editor_property('widget_style')
        text_style = style.get_editor_property('text_style')
        font_size(text_style)
        text_style.set_editor_property('color_and_opacity', unreal.SlateColor(INK))
        style.set_editor_property('text_style', text_style)
        for field,edge in [('background_image_normal','line2'),('background_image_hovered','line3'),('background_image_focused','focus'),('background_image_read_only','dline')]:
            style.set_editor_property(field,control_brush('sunken',edge,width=2 if edge=='focus' else 1))
        style.set_editor_property('foreground_color', unreal.SlateColor(INK))
        style.set_editor_property('padding', unreal.Margin(10,7,10,7))
        widget.set_editor_property('widget_style', style)
    elif isinstance(widget, unreal.CheckBox):
        style = widget.get_editor_property('widget_style')
        for field in ('unchecked_image','unchecked_hovered_image','unchecked_pressed_image','checked_image','checked_hovered_image','checked_pressed_image'):
            checked = not field.startswith('unchecked')
            brush = control_brush('gold' if checked else 'sunken','gold' if checked else 'text2',radius=8)
            image_size=brush.get_editor_property('image_size')
            assert image_size.import_text('(X=16,Y=16)')
            brush.set_editor_property('image_size',image_size)
            style.set_editor_property(field,brush)
        style.set_editor_property('padding',unreal.Margin(8,4,8,4))
        widget.set_editor_property('widget_style', style)
        widget.set_editor_property('is_focusable', True)


def label(add, name, parent, value="", size=15):
    result, slot = add(unreal.TextBlock, name, parent)
    result.set_text(value)
    result.set_auto_wrap_text(True)
    font = result.get_editor_property("font")
    font.set_editor_property("size", font_points(max(13, size)))
    font.set_editor_property('typeface_font_name','Semi Bold' if size >= 16 else 'Regular')
    game_font = unreal.load_asset('/Game/Assets/Fonts/Poppins/Poppins')
    if game_font:
        font.set_editor_property('font_object', game_font)
    result.set_editor_property("font", font)
    result.set_color_and_opacity(unreal.SlateColor(INK))
    return result, slot


def button(add, name, parent, value):
    result, slot = add(unreal.Button, name, parent)
    result.set_editor_property("is_focusable", True)
    result.set_editor_property('widget_style', button_style(result.get_editor_property('widget_style')))
    label(add, name + "Text", result, value)
    return result, slot


def bind(bp, graph, widget_name, event, fn, kind, params=None):
    old = {str(n.get_path_name()) for n in BP.find_nodes(graph)}
    tools = unreal.get_default_object(unreal.UMGToolSet)
    assert tools.call_method("BindToEventProperty", args=(bp, event, widget_name, kind.static_class()))
    nodes = [n for n in BP.find_nodes(graph) if str(n.get_path_name()) not in old]
    assert len(nodes) == 1, (widget_name, nodes)
    event_info = BP.get_node_infos(nodes)[0]
    call = BP.create_node(graph, "CallFunction|" + fn, unreal.IntPoint(400, 0))
    call_info = BP.get_node_infos([call])[0]
    for source, target in {"then": "execute", **(params or {})}.items():
        BP.connect_pins(next(p.pin_id for p in event_info.output_pins if p.name == source),
                        next(p.pin_id for p in call_info.input_pins if p.name == target))


def events(bp, bindings):
    graph = BP.get_graph(bp, "EventGraph")
    for node in BP.find_nodes(graph):
        BP.delete_node(node)
    for args in bindings:
        bind(bp, graph, *args)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)


def native(graph, method, owner=None):
    candidates = list(dict.fromkeys(n for n in BP.find_node_types(graph, '', []) if n.rsplit("|", 1)[-1].split("(",1)[0].replace(" ", "").lower() == method.replace(" ", "").lower()))
    original = list(candidates)
    if owner and len(candidates) > 1:
        alias = {"EditableTextBox":"TextBox", "TextBlock":"Text"}.get(owner,owner).lower()
        candidates = [n for n in candidates if any(re.sub("[^a-z0-9]", "", str(p.type_id).lower()) == alias + "objectreference"
                      for p in BP.get_node_type_pins(graph, n).input_pins if p.name in ("self", "Target"))]
        functions = [n for n in candidates if not n.startswith("Class|")]
        candidates = functions or candidates
    if len(candidates) != 1:
        for n in BP.find_node_types(graph,method,[]):
            unreal.log("WO_UI_NATIVE " + n + " " + str([(p.name,str(p.type_id)) for p in BP.get_node_type_pins(graph,n).input_pins]))
    assert len(candidates) == 1, (method, owner, candidates, original)
    return candidates[0]


def combo_wrappers(bp):
    """Disambiguate UComboBoxString/Key's identical native menu IDs explicitly."""
    existing = {str(x.get_name()) for x in BP.list_graphs(bp)}
    for method, args, result in (("ClearOptions", [], None), ("AddOption", [("Option","string")], None),
                                 ("SetSelectedIndex", [("Index","int")], None), ("GetSelectedIndex", [], "int")):
        name = "Combo" + method
        graph = BP.get_graph(bp,name) if name in existing else BP.add_function_graph(bp,name)
        if name not in existing:
            BP.add_object_function_param(graph,"Target",unreal.ComboBoxString.static_class(),True)
            for param,kind in args: BP.add_function_param(graph,param,kind,True)
            if result: BP.add_function_param(graph,"Value",result,False)
        BP.write_graph_dsl(graph, '(fn '+name+' (Target '+ ' '.join(p for p,_ in args)+') (return '+('0' if result else '')+'))')
        infos = BP.get_node_infos(BP.find_nodes(graph))
        entry = next(n for n in infos if any(p.name == 'Target' for p in n.output_pins))
        result_node = next((n for n in infos if any(p.name == 'Value' for p in n.input_pins)),None)
        candidates = BP.find_node_types(graph,method,[])
        kind = next(n for n in candidates if n.startswith('ComboBox|') and n.rsplit('|',1)[-1].split('(',1)[0] == method)
        call = BP.create_node(graph,kind,unreal.IntPoint(300,0),declaring_class=unreal.ComboBoxString.static_class())
        info = BP.get_node_infos([call])[0]
        input_pins = {p.name:p.pin_id for p in info.input_pins}
        output_pins = {p.name:p.pin_id for p in info.output_pins}
        entry_pins = {p.name:p.pin_id for p in entry.output_pins}
        BP.connect_pins(entry_pins['Target'],input_pins['self'])
        for param,_ in args: BP.connect_pins(entry_pins[param],input_pins[param])
        if 'execute' in input_pins: BP.connect_pins(entry_pins['then'],input_pins['execute'])
        if result_node:
            outputs = {p.name:p.pin_id for p in result_node.input_pins}
            BP.connect_pins(output_pins['ReturnValue'],outputs['Value'])
            if 'then' in output_pins: BP.connect_pins(output_pins['then'],outputs['execute'])
    BP.compile_blueprint(bp,warnings_as_errors=True)


def image_wrapper_functions():
    return {
        'ImageSetTexture':([('Target',unreal.Image.static_class()),('Texture',unreal.Texture2D.static_class())],[]),
        'ImageSetColor':([('Target',unreal.Image.static_class()),('Color',unreal.load_object(None,'/Script/CoreUObject.LinearColor'))],[]),
    }


def image_wrapper_code():
    return {'ImageSetTexture':'(fn ImageSetTexture (Target Texture) (return))',
            'ImageSetColor':'(fn ImageSetColor (Target Color) (return))'}


def image_wrappers(bp):
    """Wire already-declared stubs after all other graph bodies compile successfully."""
    for name,method,param,native_param in (('ImageSetTexture','SetBrushFromTexture','Texture','Texture'),
                                         ('ImageSetColor','SetColorAndOpacity','Color','InColorAndOpacity')):
        graph=BP.get_graph(bp,name)
        for node in BP.find_nodes(graph):
            if node.get_class().get_name() not in ('K2Node_FunctionEntry','K2Node_FunctionResult'):
                BP.delete_node(node)
        infos=BP.get_node_infos(BP.find_nodes(graph))
        entry=next(info for info in infos if any(pin.name=='Target' for pin in info.output_pins))
        entry_pins={pin.name:pin.pin_id for pin in entry.output_pins}
        kind=native(graph,method,'Image')
        call=BP.create_node(graph,kind,unreal.IntPoint(300,0),declaring_class=unreal.Image.static_class())
        info=BP.get_node_infos([call])[0]
        inputs={pin.name:pin.pin_id for pin in info.input_pins}
        outputs={pin.name:pin.pin_id for pin in info.output_pins}
        if name == 'ImageSetColor' and native_param not in inputs:
            # BlueprintSetter metadata exposes the property pin on this build.
            native_param = next(key for key in ('ColorAndOpacity', 'InColor') if key in inputs)
        BP.connect_pins(entry_pins['Target'],inputs['self'])
        BP.connect_pins(entry_pins[param],inputs[native_param])
        BP.connect_pins(entry_pins['then'],inputs['execute'])
        if 'bMatchSize' in inputs:
            BP.set_pin_value(inputs['bMatchSize'],'false')
        result=next((item for item in infos if any(pin.name=='execute' for pin in item.input_pins)),None)
        if result:
            BP.connect_pins(outputs['then'],next(pin.pin_id for pin in result.input_pins if pin.name=='execute'))
    BP.compile_blueprint(bp,warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)


def visibility(name, value):
    return f'(Widget|SetVisibility :self {g(name)} :InVisibility "{value}")'


def set_label(name, value):
    return f'(Class|Text|SetText :self {g(name)} :Text {text(value)})'


def object_array_param(graph, name, klass, is_input):
    return BP.add_object_function_param(graph, name, klass, is_input, container_type=ContainerType.ARRAY)


def object_array_variable(bp, name, klass):
    if name not in BP.list_variables(bp):
        BP.add_object_variable(bp, name, klass, container_type=ContainerType.ARRAY)


def ensure_list_entry(bp):
    assert unreal.WorkerOptimizerTestSupport.implement_list_entry(bp)
    BP.compile_blueprint(bp)


def bind_widget_function(bp, widget_name, property_name, function_name):
    assert unreal.WorkerOptimizerTestSupport.bind_widget_function(bp, widget_name, property_name, function_name)


def bind_children_delegate(bp, widget_name, function_name):
    bind_widget_function(bp, widget_name, 'BP_OnGetItemChildren', function_name)


def list_entry_event(bp, fn='SetItem'):
    graph = BP.get_graph(bp, 'EventGraph')
    event = BP.add_event(bp, 'OnListItemObjectSet')
    call = BP.create_node(graph, 'CallFunction|' + fn, unreal.IntPoint(400, 0))
    source, target = BP.get_node_infos([event, call])
    BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name == 'then'), next(p.pin_id for p in target.input_pins if p.name == 'execute'))
    BP.connect_pins(next(p.pin_id for p in source.output_pins if p.name == 'ListItemObject'), next(p.pin_id for p in target.input_pins if p.name in ('Object', 'Item')))
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
