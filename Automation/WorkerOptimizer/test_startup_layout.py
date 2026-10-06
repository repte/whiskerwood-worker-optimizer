"""Regression: missed load events and DPI-aware compact control placement."""
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

root = '/Game/Mods/WorkerOptimizer/'
load = lambda name: unreal.load_class(None, root + name + '.' + name + '_C')
bp = unreal.load_asset(root + 'BP_MapLoad')
graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
assert 'ObserveReadiness' in graphs, 'A completed new game must start without the load delegate'
poll = BP.read_graph_dsl(BP.get_graph(bp, 'PumpLifecycle'))
assert 'CurrentInitPhase' in poll and 'DONE' in poll, 'Fallback must use the completed native init phase'
assert 'PumpLifecycle' in BP.read_graph_dsl(BP.get_graph(bp, 'EventGraph'))
actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
session = actors.spawn_actor_from_class(load('BP_MapLoad'), unreal.Vector(0, 0, -100000))
api = unreal.new_object(unreal.load_class(None, '/Script/SystemCore.ModAPI'))
try:
    assert not session.call_method('ObserveReadiness', args=(True, True))
    assert not session.call_method('PumpLifecycle'), 'Editor/menu world must not initialize gameplay UI'
    assert session.call_method('AttachAPI', args=(api,))
    for ready in ((False, False), (False, True), (True, False)):
        assert not session.call_method('ObserveReadiness', args=ready)
        assert not session.get_editor_property('Loaded'), 'Must not initialize during loading or without a player'
    assert session.call_method('ObserveReadiness', args=(True, True))
    assert session.get_editor_property('Loaded'), 'Missed delegate must not leave UI waiting forever'
    assert session.call_method('ObserveReadiness', args=(True, True)), 'Readiness must be idempotent'
    assert not session.get_editor_property('Controller'), 'Observation does not optimize or create duplicate sessions'
    session.call_method('Shutdown')
    assert not session.call_method('ObserveReadiness', args=(True, True))
finally:
    session.call_method('Shutdown')
    actors.destroy_actor(session)

widget_bp = unreal.load_asset(root + 'WBP_WorkerOptimizer')
assert 'ApplyLayout' in {str(g.get_name()) for g in BP.list_graphs(widget_bp)}, 'Controls must adapt to viewport and DPI changes'
world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
factory = unreal.get_default_object(unreal.load_class(None, '/Script/UMG.WidgetBlueprintLibrary'))
widget = factory.call_method('Create', args=(world, load('WBP_WorkerOptimizer'), None))


def assert_popup_scale(panel, panel_scale, expected):
    assert panel_scale.get_editor_property('stretch') == unreal.Stretch.USER_SPECIFIED
    assert abs(panel_scale.get_editor_property('user_specified_scale') - expected) < 0.001, 'Popup correction must participate in Slate layout'
    transform = panel.get_editor_property('render_transform')
    scale = transform.get_editor_property('scale')
    assert abs(scale.x - 1) < 0.0001 and abs(scale.y - 1) < 0.0001, 'Render scaling would magnify undersized text glyphs'
    assert transform.get_editor_property('translation') == unreal.Vector2D(0, 0)
    assert transform.get_editor_property('shear') == unreal.Vector2D(0, 0)
    assert abs(transform.get_editor_property('angle')) < 0.0001


try:
    panel = widget.get_editor_property('PanelHost')
    panel_scale = widget.get_editor_property('PanelScale')
    assert isinstance(panel_scale, unreal.ScaleBox)
    assert panel.get_parent() == panel_scale
    assert panel.slot.get_editor_property('horizontal_alignment') == unreal.HorizontalAlignment.H_ALIGN_FILL
    assert panel.slot.get_editor_property('vertical_alignment') == unreal.VerticalAlignment.V_ALIGN_FILL
    closed_size=panel_scale.slot.get_size()
    closed_position=panel_scale.slot.get_position()
    assert widget.call_method('ApplyLayout',args=(1400.0,900.0))
    assert panel_scale.slot.get_size()==closed_size and panel_scale.slot.get_position()==closed_position, 'Closed panel geometry must remain untouched'
    for width, height in ((5120,1440), (3440,1440), (2560,1080), (1920,1080), (1280,720), (800,600)):
        for dpi in (0.75, 1.0, 1.25, 1.5, 2.0):
            w, h = width / dpi, height / dpi
            assert panel.call_method('OpenTab',args=('general',))
            assert widget.call_method('ApplyLayout', args=(w, h))
            slot = widget.get_editor_property('Controls').slot
            pos = slot.get_position()
            size = slot.get_size()
            popup_pos = panel_scale.slot.get_position()
            popup_size = panel_scale.slot.get_size()
            popup_x = popup_pos.x
            popup_y = popup_pos.y
            assert_popup_scale(panel, panel_scale, 1.0)
            assert popup_x >= 8 and popup_y >= 8, (width, height, dpi, 'popup above/left viewport', popup_x, popup_y)
            assert popup_x + popup_size.x <= w - 8, (width, height, dpi, 'popup right clipping')
            assert popup_y + popup_size.y <= h - 8, (width, height, dpi, 'popup bottom clipping')
            margin = 12 if h < 700 else 24
            assert abs(popup_size.x - min(max(w * 0.7, 680), 1400, w - margin * 2)) < 0.01
            assert popup_size.y <= 1040
            assert abs(popup_x + popup_size.x - (w - margin)) < 0.01, 'Window must remain right aligned'
            for tab in ('general', 'priorities', 'logbook'):
                assert panel.call_method('OpenTab', args=(tab,)), (width, height, dpi, tab)
                assert str(panel.get_editor_property('ActiveTab')) == tab
                assert widget.call_method('ApplyLayout', args=(w, h))
                assert panel_scale.slot.get_size().y <= h - 16
            panel.call_method('ClosePanel')
            assert pos.x >= (160 if w >= 500 else 12), (width, height, dpi, 'left HUD overlap', pos)
            assert pos.x + size.x <= w - 8, (width, height, dpi, 'right clipping', pos, size)
            assert h + pos.y >= 8 and pos.y + size.y <= -8, (width, height, dpi, 'vertical clipping', pos, size)
            if w < 1600:
                assert pos.y + size.y <= -100, 'Compact viewports must clear the bottom toolbar'
    assert not widget.call_method('ApplyLayout', args=(0.0,0.0)), 'Minimized viewport must not destroy layout'
    for width, height, dpi in ((3202,1390,0.7), (2061,907,0.45), (1280,720,0.7), (800,600,0.45), (1920,1080,1.0), (1280,720,1.25)):
        assert panel.call_method('OpenTab', args=('logbook',))
        assert widget.call_method('ApplyViewportLayout', args=(float(width),float(height),dpi))
        scale = float(panel_scale.get_editor_property('user_specified_scale'))
        assert_popup_scale(panel, panel_scale, max(1.0, 1.0 / dpi))
        size = panel_scale.slot.get_size()
        pos = panel_scale.slot.get_position()
        assert abs(scale * dpi - max(1.0,dpi)) < 0.001, 'Game DPI must never shrink minimum text below 100%'
        effective_width = width / max(1.0,dpi)
        effective_height = height / max(1.0,dpi)
        margin = 12 if effective_height < 700 else 24
        assert abs(size.x / scale-min(max(effective_width*0.7,680),1400,effective_width-margin*2)) < 0.01
        assert pos.x + size.x <= width/dpi-8
        assert pos.y + size.y <= height/dpi-8
        assert pos.y >= widget.get_editor_property('NativeHudBottom') + margin*scale
        shadow = widget.get_editor_property('PanelShadow')
        shadow_scale = shadow.get_editor_property('render_transform').get_editor_property('scale')
        assert abs(shadow_scale.x-scale) < 0.001 and abs(shadow_scale.y-scale) < 0.001
        assert shadow.get_editor_property('render_transform_pivot') == unreal.Vector2D(0,0)
        writes = widget.get_editor_property('UIWriteCount')
        assert widget.call_method('ApplyViewportLayout',args=(float(width),float(height),dpi))
        assert widget.get_editor_property('UIWriteCount') == writes, 'Unchanged DPI/viewport must not reflow'
    # Same logical geometry can have different physical DPI: the watcher must still relayout.
    assert widget.call_method('ApplyViewportLayout',args=(1600.0,900.0,1.0))
    assert widget.call_method('ApplyViewportLayout',args=(800.0,450.0,0.5))
    assert_popup_scale(panel, panel_scale, 2.0)
finally:
    widget.remove_from_parent()
unreal.log('WO_STARTUP_LAYOUT_TESTS_PASS: no-event readiness, guards, idempotence, 30 viewport/DPI layouts')
