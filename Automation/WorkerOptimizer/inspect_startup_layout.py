"""Inspect native readiness and viewport node signatures without changing assets."""
import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

bp = unreal.load_asset('/Game/Mods/WorkerOptimizer/BP_MapLoad')
graph = BP.get_graph(bp, 'PumpUI')
suffixes = ('CurrentInitPhase', 'GetGameMode', 'CastToProjectArcoGameModeBase',
            'GetViewportSize', 'GetViewportScale', 'SlotAsCanvasSlot', 'SetPosition',
            'MakeVector2D', 'BreakVector2D', 'GetLocalSize', 'GetCachedGeometry',
            'GetPlayerScreenWidgetGeometry', 'SetSize', 'SetRenderScale')
for node in BP.find_node_types(graph, '', []):
    if node.rsplit('|', 1)[-1].lower() in {s.lower() for s in suffixes} or any(s in node for s in ('Equal(Enum)', 'Enumto', 'ToString(Byte)', 'Min(Float)', 'Min(Real)', 'GetRealTimeSeconds', 'GetEnumerator')):
        pins = BP.get_node_type_pins(graph, node)
        unreal.log('WO_LAYOUT_NODE ' + node + ' in=' + str([(p.name, p.type_id) for p in pins.input_pins])
                   + ' out=' + str([(p.name, p.type_id) for p in pins.output_pins]))
unreal.log('WO_LAYOUT_INSPECT_PASS')
