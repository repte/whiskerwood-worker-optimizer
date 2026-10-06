"""Generate the opt-in, real-time session scheduling state machine."""
from pathlib import Path
import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_AutoAssignment")
if bp is None:
    bp = BP.create(ROOT, "BP_AutoAssignment", unreal.Object.static_class())
# The authoring library's real primitive is a double-precision Blueprint pin.
for kind, names in {"name": "Mode", "bool": "Pending Running HasClock HasDay", "real": "LastNow NextDeadline Interval", "int": "LastYear LastDay"}.items():
    for name in names.split():
        if name not in BP.list_variables(bp):
            BP.add_variable(bp, name, kind)
definitions = {
    "ValidClock": [("NowSeconds", "real")],
    "Configure": [("Mode", "name"), ("NowSeconds", "real"), ("Year", "int"), ("Day", "int")],
    "ObserveDay": [("Year", "int"), ("Day", "int")],
    "Poll": [("NowSeconds", "real"), ("Paused", "bool"), ("Ready", "bool"), ("Busy", "bool")],
    "OnRunStarted": [("NowSeconds", "real")], "OnRunEnded": [("NowSeconds", "real")], "ResetSession": [],
}
graphs = {}
existing = {str(graph.get_name()) for graph in BP.list_graphs(bp)}
for name, params in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing else BP.add_function_graph(bp, name)
    if name not in existing:
        for param, kind in params:
            BP.add_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", "bool", False)
BP.compile_blueprint(bp)
g = lambda name: f"(Variables|Default|Get{name})"
put = lambda name, value: f"(Variables|Default|Set{name} {value})"
code = {}
code["ValidClock"] = "(fn ValidClock (NowSeconds) (return (and (>= NowSeconds 0.0) (<= NowSeconds 1000000000000.0))))"
code["ResetSession"] = f"""(fn ResetSession ()
    {put('Mode', '"off"')} {put('Pending', 'false')} {put('Running', 'false')}
    {put('HasClock', 'false')} {put('HasDay', 'false')} {put('Interval', '0.0')}
    {put('LastNow', '0.0')} {put('NextDeadline', '0.0')}
    {put('LastYear', '0')} {put('LastDay', '0')} (return true))"""
code["Configure"] = f"""(fn Configure (Mode NowSeconds Year Day)
    (if (not (CallFunction|ValidClock :NowSeconds NowSeconds)) (CallFunction|ResetSession) (return false))
    (if (not (or (== Mode "off") (or (== Mode "day_start") (or (== Mode "minutes_5") (or (== Mode "minutes_10") (== Mode "minutes_15"))))))
      (CallFunction|ResetSession) (return false))
    (if (and (== Mode {g('Mode')}) {g('HasClock')}) (return true))
    {put('Mode', 'Mode')} {put('Pending', 'false')} {put('HasClock', 'true')} {put('LastNow', 'NowSeconds')}
    {put('Interval', '0.0')}
    (if (== Mode "minutes_5") {put('Interval', '300.0')})
    (if (== Mode "minutes_10") {put('Interval', '600.0')})
    (if (== Mode "minutes_15") {put('Interval', '900.0')})
    {put('NextDeadline', f'(+ NowSeconds {g("Interval")})')}
    {put('HasDay', '(and (>= Year 0) (>= Day 0))')} {put('LastYear', 'Year')} {put('LastDay', 'Day')}
    (return true))"""
code["ObserveDay"] = f"""(fn ObserveDay (Year Day)
    (if (or (< Year 0) (< Day 0)) (return false))
    (if (and {g('HasDay')} (and (== Year {g('LastYear')}) (== Day {g('LastDay')}))) (return false))
    (bind observed {g('HasDay')})
    {put('HasDay', 'true')} {put('LastYear', 'Year')} {put('LastDay', 'Day')}
    (if (or (not observed) (!= {g('Mode')} "day_start")) (return false))
    {put('Pending', 'true')} (return true))"""
code["Poll"] = f"""(fn Poll (NowSeconds Paused Ready Busy)
    (if (not (CallFunction|ValidClock :NowSeconds NowSeconds))
      {put('HasClock', 'false')} {put('Pending', 'false')} (return false))
    (if (or (not {g('HasClock')}) (< NowSeconds {g('LastNow')}))
      {put('HasClock', 'true')} {put('Pending', 'false')} {put('LastNow', 'NowSeconds')}
      {put('NextDeadline', f'(+ NowSeconds {g("Interval")})')} (return false))
    {put('LastNow', 'NowSeconds')}
    (if (== {g('Mode')} "off") {put('Pending', 'false')} (return false))
    (if (and (not {g('Running')}) (and (> {g('Interval')} 0.0) (>= NowSeconds {g('NextDeadline')})))
      {put('Pending', 'true')})
    (return (and {g('Pending')} (and (not {g('Running')}) (and (not Paused) (and Ready (not Busy)))))))"""
code["OnRunStarted"] = f"""(fn OnRunStarted (NowSeconds)
    (if (or {g('Running')} (not (CallFunction|ValidClock :NowSeconds NowSeconds))) (return false))
    {put('Running', 'true')} {put('Pending', 'false')} {put('HasClock', 'true')} {put('LastNow', 'NowSeconds')}
    (return true))"""
code["OnRunEnded"] = f"""(fn OnRunEnded (NowSeconds)
    {put('Running', 'false')} {put('Pending', 'false')}
    (if (not (CallFunction|ValidClock :NowSeconds NowSeconds)) {put('HasClock', 'false')} (return false))
    {put('HasClock', 'true')} {put('LastNow', 'NowSeconds')} {put('NextDeadline', f'(+ NowSeconds {g("Interval")})')}
    (return true))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    unreal.get_default_object(bp.generated_class()).set_editor_property("Mode", "off")
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
unreal.log("WO_AUTO_ASSIGNMENT_GENERATED")
exec(Path(__file__).with_name("test_auto_assignment.py").read_text(encoding="utf-8"))
