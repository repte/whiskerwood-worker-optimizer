"""Native UMG assertions for the supplied redesign, not a simulated UI."""
import unreal
from ui_authoring import font_points
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    root = '/Game/Mods/WorkerOptimizer/'
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    factory = unreal.get_default_object(unreal.load_class(None, '/Script/UMG.WidgetBlueprintLibrary'))
    klass = unreal.load_class(None, root + 'WBP_SettingsPanel.WBP_SettingsPanel_C')
    panel = factory.call_method('Create', args=(world, klass, None))
    assert panel.get_editor_property('GeneralTab').get_editor_property('is_focusable'), 'Redesign tabs must support keyboard/gamepad focus'
    assert panel.get_editor_property('Views').get_class() == unreal.WidgetSwitcher.static_class()
    assert panel.get_editor_property('PrioritiesHost').get_class().get_name() == 'WBP_PrioritiesView_C'
    for width, height in ((1280.0, 720.0), (1920.0, 1080.0), (2560.0, 1080.0)):
        assert panel.call_method('ApplyPanelLayout', args=(width, height))
        assert panel.get_editor_property('LayoutWidth') == width
    assert not panel.get_editor_property('PanelOpen')
    assert panel.call_method('ClosePanel')
    tools = unreal.get_default_object(unreal.UMGToolSet)
    for asset,names in (('WBP_SettingsPanel',('ContentScroll',)),('WBP_PrioritiesView',('PriorityTree',)),('WBP_LogbookView',('RunRows','DetailRows'))):
        entries=tools.call_method('GetWidgets',args=(unreal.load_asset(root+asset),)).widgets
        for entry in entries:
            if str(entry.widget_name) in names:
                field='widget_bar_style' if isinstance(entry.widget,unreal.ScrollBox) else 'scroll_bar_style'
                assert entry.widget.get_editor_property(field).get_editor_property('thickness') == 6.0
    for name in ('WBP_SettingsPanel','WBP_PrioritiesView','WBP_PriorityRow','WBP_LogbookView','WBP_HistoryRow','WBP_HistoryDetailRow'):
        blueprint = unreal.load_asset(root+name)
        for entry in tools.call_method('GetWidgets',args=(blueprint,)).widgets:
            widget = entry.widget
            if isinstance(widget,unreal.TextBlock):
                assert widget.get_editor_property('font').get_editor_property('size') >= font_points(13), (name,widget.get_name())
                assert widget.get_editor_property('auto_wrap_text'), (name,widget.get_name())
        for graph in BP.list_graphs(blueprint):
            nodes = BP.get_node_infos(BP.find_nodes(graph))
            assert not any('EventTick' in node.type_id.replace(' ','') for node in nodes), name
        assert unreal.WorkerOptimizerTestSupport.has_only_event_bindings(blueprint), name
    unreal.log('WO_UI_DESIGN_CONTRACT_PASS')


run()
