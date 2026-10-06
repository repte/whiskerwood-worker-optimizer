"""Native virtualized priorities contracts; no persisted preference writes."""
from pathlib import Path
import sys

assert "unreal" in sys.modules or (Path(__file__).resolve().parents[2] / "Content/Mods/WorkerOptimizer/WBP_PrioritiesView.uasset").exists(), "Priorities view has not been authored"
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from ui_authoring import font_points


def run():
    root = "/Game/Mods/WorkerOptimizer/"
    load = lambda n: unreal.load_class(None, root + n + "." + n + "_C")
    fixture = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_PrioritiesInputs', unreal.Object.static_class())
    graph = BP.add_function_graph(fixture, 'Seed')
    BP.add_object_function_param(graph, 'Model', load('BP_SettingsModel'), True)
    BP.add_object_function_param(graph, 'Settings', load('BP_PrioritySettings'), True)
    state = BP.add_function_graph(fixture, 'State')
    BP.add_object_function_param(state, 'Model', load('BP_SettingsModel'), True)
    BP.add_function_param(state, 'Filtering', 'bool', True)
    BP.add_function_param(state, 'Revision', 'int', True)
    query = BP.add_function_graph(fixture,'Query')
    BP.add_object_function_param(query,'Model',load('BP_SettingsModel'),True)
    BP.add_function_param(query,'Value','string',True)
    same_label = BP.add_function_graph(fixture, 'SameLabel')
    BP.add_object_function_param(same_label, 'Model', load('BP_SettingsModel'), True)
    BP.add_object_function_param(same_label, 'Settings', load('BP_PrioritySettings'), True)
    BP.compile_blueprint(fixture)
    source = '(fn Seed (Model Settings) (Class|BPSettingsModel|SetSettings :self Model :Settings Settings) (Class|BPSettingsModel|SetInitialized :self Model :Initialized true) (Class|BPSettingsModel|SetSearchRevision :self Model :SearchRevision 1) '
    for name, values in {'CategoryKeys':['food_process'], 'CategoryLabels':['Food'], 'TypeKeys':['fishery','future_factory'], 'TypeLabels':['Fishery','future_factory'], 'TypeCategories':[0,0], 'TypeMatches':[True,True], 'RowIndices':[0], 'RowIsCategory':[True]}.items():
        array = '(Class|BPSettingsModel|Get'+name+' :self Model)'
        source += '(Utilities|Array|Clear '+array+') '
        for value in values:
            literal = ('true' if value else 'false') if isinstance(value,bool) else ('"'+value+'"' if isinstance(value,str) else str(value))
            source += '(Utilities|Array|Add '+array+' '+literal+') '
    BP.write_graph_dsl(graph, source+')')
    BP.write_graph_dsl(state, '(fn State (Model Filtering Revision) (Class|BPSettingsModel|SetFiltering :self Model :Filtering Filtering) (Class|BPSettingsModel|SetSearchRevision :self Model :SearchRevision Revision))')
    BP.write_graph_dsl(query,'(fn Query (Model Value) (Class|BPSettingsModel|SetQueryText :self Model :QueryText Value))')
    BP.write_graph_dsl(same_label, '''(fn SameLabel (Model Settings)
      (bind index (Utilities|Array|FindItem (Class|BPPrioritySettings|GetTextKeys :self Settings) "category.food_process"))
      (bind languages (Utilities|Array|Length (Class|BPPrioritySettings|GetLanguages :self Settings)))
      (for language (range languages)
        (Utilities|Array|SetArrayElem :TargetArray (Class|BPPrioritySettings|GetTextValues :self Settings) :Index (+ (* index languages) language) :Item "food_process"))
      (Utilities|Array|SetArrayElem :TargetArray (Class|BPSettingsModel|GetCategoryLabels :self Model) :Index 0 :Item "food_process"))''')
    BP.compile_blueprint(fixture, warnings_as_errors=True)
    inputs = unreal.new_object(fixture.generated_class())
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, "/Script/UMG.WidgetBlueprintLibrary"))
    create = lambda n: factory.call_method("Create", args=(world, load(n), None))
    view = create("WBP_PrioritiesView")
    assert not view.call_method('CanUseItem', args=(None,)), 'Uninitialized view must not dereference a model'
    blueprint = unreal.load_asset(root+'WBP_PrioritiesView')
    node_types = [str(info.type_id) for graph in BP.list_graphs(blueprint) for info in BP.get_node_infos(BP.find_nodes(graph))]
    assert not any('Timer' in kind for kind in node_types), 'Presentation pulses must not depend on game-world time'
    assert not any('Event' in kind and 'Tick' in kind for kind in node_types), 'No authored per-frame refresh event'
    for name, seconds in (('SearchPulse',0.15), ('FilterPulse',0.01)):
        animation = view.get_editor_property(name)
        assert animation
        assert abs(animation.get_end_time()-animation.get_start_time()-seconds) < 0.001
    model = unreal.new_object(load("BP_SettingsModel"))
    settings = unreal.new_object(load("BP_PrioritySettings"))
    inputs.call_method('Seed', args=(model,settings))
    assert view.call_method("InitializePriorities", args=(model,))
    tree = view.get_editor_property("PriorityTree")
    assert isinstance(tree, unreal.TreeView)
    assert tree.get_editor_property('selection_mode') != unreal.SelectionMode.NONE, 'Category label clicks require the native row mouse-capture selection path'
    assert view.get_editor_property('PriorityHeading')
    assert view.get_editor_property('HeaderRule').get_editor_property('height_override')==1.0
    roots = list(view.get_editor_property("RootItems"))
    assert len(roots) == 1
    children = list(roots[0].get_editor_property("Children"))
    assert len(children) == 2, "Collapsed categories retain lazy TreeView children"
    assert str(children[0].get_editor_property("Key")) == "fishery"
    assert str(children[1].get_editor_property("Title")) != "future_factory", "Unresolved native labels never expose internal keys"
    assert view.call_method("CanUseItem", args=(children[0],))
    row = create("WBP_PriorityRow")
    assert row.call_method("SetItem", args=(children[0],))
    assert not row.get_editor_property("IsCategory")
    assert row.get_editor_property("RowPriority") == -1
    assert row.get_editor_property("EffectivePriority") == 2
    assert str(row.get_editor_property('Effective').get_text())=='2'
    marker=row.get_editor_property('PriorityStateIcon')
    assert marker.get_visibility()==unreal.SlateVisibility.HIT_TEST_INVISIBLE
    assert marker.get_editor_property('brush').get_editor_property('resource_object')==unreal.load_asset(root+'T_WorkerOptimizerPriorityInherited')
    assert row.get_editor_property('InheritChoiceText').get_editor_property('font').get_editor_property('size')==font_points(15)
    assert row.get_editor_property('CustomChoiceText').get_editor_property('font').get_editor_property('size')==font_points(15)
    assert row.get_editor_property("Stepper").get_visibility() == unreal.SlateVisibility.COLLAPSED
    assert row.get_editor_property('StructureLine').get_visibility()==unreal.SlateVisibility.HIT_TEST_INVISIBLE
    radio_brush=row.get_editor_property('InheritChoice').get_editor_property('widget_style').get_editor_property('checked_image')
    radio_size=radio_brush.get_editor_property('image_size').export_text().replace('.000000','')
    assert radio_size=='(X=16,Y=16)', 'Priority choices use the native themed radio style: '+radio_size
    assert row.call_method('SetItem',args=(roots[0],))
    expander = row.get_editor_property('CategoryExpander')
    assert expander.get_visibility() == unreal.SlateVisibility.VISIBLE, 'Collapsed categories need a visible expansion control'
    assert expander.get_editor_property('is_focusable'), 'Category expansion must support keyboard/gamepad activation'
    assert row.call_method('SetExpansionGlyph', args=(True,))
    assert str(row.get_editor_property('CategoryExpanderText').get_text()) == chr(0x25bc)
    assert row.call_method('SetExpansionGlyph', args=(False,))
    assert str(row.get_editor_property('CategoryExpanderText').get_text()) == chr(0x25b6)
    assert row.get_editor_property('StructureLine').get_visibility()==unreal.SlateVisibility.COLLAPSED
    assert marker.get_visibility()==unreal.SlateVisibility.COLLAPSED
    assert row.call_method('SetItem',args=(children[0],))
    assert expander.get_visibility() == unreal.SlateVisibility.COLLAPSED, 'Leaf rows have no expansion control'
    assert not row.call_method("IncreaseClicked"), "Inherited priorities have no direct numeric edit"
    revision = view.get_editor_property("BuildCount")
    assert view.call_method("RefreshPriorities")
    assert view.get_editor_property("BuildCount") == revision
    inputs.call_method('State', args=(model,True,1))
    assert not view.call_method("CanUseItem", args=(children[0],))
    assert not row.call_method("CanUseRow")
    assert not view.call_method("WritePriority", args=(children[0], 4))
    inputs.call_method('State', args=(model,False,2))
    assert not view.call_method("CanUseItem", args=(children[0],)), "Recycled rows cannot write across filter revisions"
    assert view.call_method("RefreshPriorities")
    assert not view.call_method("CanUseItem", args=(children[0],))
    assert view.call_method("ApplyLayout", args=(919.0, 500.0))
    assert view.get_editor_property("Narrow")
    build_count = view.get_editor_property('BuildCount')
    assert view.call_method("ApplyLayout", args=(920.0, 500.0))
    assert not view.get_editor_property("Narrow")
    assert view.get_editor_property('BuildCount') == build_count, 'Geometry updates never rebuild priority data'
    assert row.call_method('ApplyLayout', args=(920.0,))
    assert row.get_editor_property('PriorityControls').get_editor_property('width_override') == 540.0
    assert row.get_editor_property('EffectiveSize').get_editor_property('width_override') == 88.0
    assert row.get_editor_property('EffectiveIcon').get_editor_property('width_override') == 16.0
    assert row.call_method('ApplyLayout', args=(700.0,))
    assert row.get_editor_property('PriorityControls').slot.get_editor_property('layout_data').offsets.top > 8.0
    inputs.call_method('State',args=(model,True,2))
    assert view.call_method('ShutdownView')
    assert view.call_method('InitializePriorities',args=(model,)), 'Reopening an interrupted filter must resume successfully'
    assert tree.get_visibility()==unreal.SlateVisibility.HIDDEN
    assert view.call_method('ShutdownView')
    assert model.get_editor_property('Filtering'), 'Closing an interrupted filter must not advance domain work'
    inputs.call_method('State',args=(model,False,2))
    assert view.call_method('InitializePriorities',args=(model,))
    inputs.call_method('Query',args=(model,'committed'))
    search=view.get_editor_property('SearchBox')
    search.set_text('pending draft')
    assert view.call_method('SearchChanged')
    assert view.get_editor_property('SearchPending')
    assert view.call_method("ShutdownView")
    assert str(search.get_text())=='committed', 'Closing during debounce must restore the visible committed query'
    assert model.get_editor_property('QueryText')=='committed', 'Closing must not commit or filter a draft query'
    assert not view.get_editor_property('SearchPending')
    assert view.call_method('InitializePriorities',args=(model,))
    assert str(search.get_text())==model.get_editor_property('QueryText'), 'Reopened query and results must agree'
    assert view.call_method('ShutdownView')
    assert not view.call_method("CanUseItem", args=(roots[0],))
    assert not view.call_method("ContinueFilter")
    assert view.call_method('OnSearchPulse') is None
    assert view.call_method('OnFilterPulse') is None
    assert not model.get_editor_property('Filtering'), 'Stopped/closed pulse callbacks must remain inert'
    assert not view.call_method('SearchChanged')
    inputs.call_method('Seed', args=(model, settings))
    inputs.call_method('SameLabel', args=(model, settings))
    assert settings.call_method('ResolveLabel', args=('food_process', 'missing.translation')) == 'food_process'
    assert view.call_method('InitializePriorities', args=(model,))
    category = list(view.get_editor_property('RootItems'))[0]
    assert str(category.get_editor_property('Title')) == 'food_process', 'A confirmed localized name remains valid when its spelling equals the internal key'
    assert row.call_method('SetItem', args=(category,))
    assert unreal.WorkerOptimizerTestSupport.realize_widget_artifact(view)
    assert row.call_method('ExpandClicked'), 'Focusable category control expands the actual native tree item'
    assert 'food_process' in [str(key) for key in model.get_editor_property('ExpandedCategories')], 'Expansion delegates preserve the existing category preference'
    assert view.call_method('ShutdownView')
    assert not row.call_method('ExpandClicked'), 'Recycled/closed rows cannot expand stale tree items'
    unreal.WorkerOptimizerTestSupport.release_widget_artifact()
    unreal.log("WO_PRIORITIES_VIEW_TESTS_PASS: native TreeView/rows, snapshot guards, geometry-only layout, 150/10 ms animations, no game timers/Tick and inert shutdown callbacks")


run()
