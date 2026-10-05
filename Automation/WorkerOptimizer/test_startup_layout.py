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
try:
    for width, height in ((5120,1440), (3440,1440), (2560,1080), (1920,1080), (1280,720), (800,600)):
        for dpi in (0.75, 1.0, 1.25, 1.5, 2.0):
            w, h = width / dpi, height / dpi
            assert widget.call_method('ApplyLayout', args=(w, h))
            slot = widget.get_editor_property('Controls').slot
            pos = slot.get_position()
            size = slot.get_size()
            assert pos.x >= 160, (width, height, dpi, 'left HUD overlap', pos)
            assert pos.x + size.x <= w - 8, (width, height, dpi, 'right clipping', pos, size)
            assert h + pos.y >= 8 and pos.y + size.y <= -8, (width, height, dpi, 'vertical clipping', pos, size)
            if w < 1600:
                assert pos.y + 140 <= -100, 'Compact viewports must clear the bottom toolbar'
    assert not widget.call_method('ApplyLayout', args=(0.0,0.0)), 'Minimized viewport must not destroy layout'
finally:
    widget.remove_from_parent()
unreal.log('WO_STARTUP_LAYOUT_TESTS_PASS: no-event readiness, guards, idempotence, 30 viewport/DPI layouts')
