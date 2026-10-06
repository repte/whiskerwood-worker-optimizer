"""Author optional, fixed-memory performance metrics for the packaged Blueprint."""

from pathlib import Path
import runpy

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
bp = unreal.load_asset(ROOT + "/BP_PerformanceMetrics")
if bp is None:
    bp = BP.create(ROOT, "BP_PerformanceMetrics", unreal.Object.static_class())
PHASES = 12
BOUNDS = [0.0, 0.00005, 0.0001, 0.0002, 0.0005, 0.001, 0.002, 0.004,
          0.008, 0.016667, 0.033334, 0.05, 0.1, 0.25, 1.0, 1e300]
existing = set(BP.list_variables(bp))
for kind, names in {"int[]": "Histogram Counts", "int": "Cumulative", "float[]": "Bounds Maxima", "string": "Summary"}.items():
    for name in names.split():
        if name not in existing:
            BP.add_variable(bp, name, kind.removesuffix("[]"),
                            container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
definitions = {
    "ResetMetrics": ([], "bool"),
    "RecordSample": ([("Phase", "int"), ("Seconds", "float")], "bool"),
    "PercentileUpperBound": ([("Phase", "int"), ("Percentile", "float")], "float"),
    "ElapsedSeconds": ([("StartSeconds", "int"), ("StartFraction", "float"),
                        ("EndSeconds", "int"), ("EndFraction", "float")], "float"),
    "BuildSummary": ([], "string"),
}
graphs = {}
existing_graphs = {str(graph.get_name()) for graph in BP.list_graphs(bp)}
for name, (params, result) in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            BP.add_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Result", result, False)
BP.compile_blueprint(bp)


def g(name):
    return f"(Variables|Default|Get{name})"


def at(name, index):
    return f'(Utilities|Array|Get(acopy) :Array {g(name)} :"Dimension 1" {index})'


def set_at(name, index, value):
    return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"


def append(*values):
    result = values[0]
    for value in values[1:]:
        result = f"(Utilities|String|Append :A {result} :B {value})"
    return result


code = {}
code["ResetMetrics"] = f"""(fn ResetMetrics ()
    (Utilities|Array|Clear {g('Histogram')}) (Utilities|Array|Resize {g('Histogram')} {PHASES * len(BOUNDS)})
    (Utilities|Array|Clear {g('Counts')}) (Utilities|Array|Resize {g('Counts')} {PHASES})
    (Utilities|Array|Clear {g('Maxima')}) (Utilities|Array|Resize {g('Maxima')} {PHASES})
    (return true))"""
code["RecordSample"] = f"""(fn RecordSample (Phase Seconds)
    (if (or (< Phase 0) (>= Phase {PHASES})) (return false))
    (if (not (and (>= Seconds 0.0) (<= Seconds 1.7976931348623157e308))) (return false))
    (if (>= {at('Counts', 'Phase')} 2147483647) (return false))
    (for bucket (range {len(BOUNDS)})
      (if (or (<= Seconds {at('Bounds', 'bucket')}) (== bucket {len(BOUNDS)-1}))
        (bind index (+ (* Phase {len(BOUNDS)}) bucket))
        {set_at('Histogram', 'index', f'(+ {at("Histogram", "index")} 1)')}
        {set_at('Counts', 'Phase', f'(+ {at("Counts", "Phase")} 1)')}
        (if (> Seconds {at('Maxima', 'Phase')}) {set_at('Maxima', 'Phase', 'Seconds')})
        (return true))) (return false))"""
code["PercentileUpperBound"] = f"""(fn PercentileUpperBound (Phase Percentile)
    (if (or (< Phase 0) (>= Phase {PHASES})) (return -1.0))
    (if (not (and (>= Percentile 0.0) (<= Percentile 100.0))) (return -1.0))
    (bind count {at('Counts', 'Phase')}) (if (== count 0) (return 0.0))
    (bind target (* (Math|Conversions|ToFloat(Integer) count) (/ Percentile 100.0)))
    (Variables|Default|SetCumulative 0)
    (for bucket (range {len(BOUNDS)})
      (Variables|Default|SetCumulative (+ {g('Cumulative')} {at('Histogram', f'(+ (* Phase {len(BOUNDS)}) bucket)')}))
      (if (and (> {g('Cumulative')} 0) (>= (Math|Conversions|ToFloat(Integer) {g('Cumulative')}) target))
        (if (== bucket {len(BOUNDS)-1}) (return {at('Maxima', 'Phase')}))
        (return {at('Bounds', 'bucket')}))) (return {at('Maxima', 'Phase')}))"""
code["ElapsedSeconds"] = """(fn ElapsedSeconds (StartSeconds StartFraction EndSeconds EndFraction)
    (return (+ (Math|Conversions|ToFloat(Integer) (- EndSeconds StartSeconds)) (- EndFraction StartFraction))))"""
row = append('" phase="', '(Utilities|String|ToString(Integer) phase)', '" count="',
             f'(Utilities|String|ToString(Integer) {at("Counts", "phase")})', '" p95_s<="',
             '(Utilities|String|ToString(Float) (CallFunction|PercentileUpperBound :Phase phase :Percentile 95.0))',
             '" p99_s<="', '(Utilities|String|ToString(Float) (CallFunction|PercentileUpperBound :Phase phase :Percentile 99.0))',
             '" max_s="', f'(Utilities|String|ToString(Float) {at("Maxima", "phase")})')
code["BuildSummary"] = f"""(fn BuildSummary ()
    (Variables|Default|SetSummary "WorkerOptimizer development timing (histogram upper bounds):")
    (for phase (range {PHASES})
      (Variables|Default|SetSummary (Utilities|String|Append :A {g('Summary')} :B {row})))
    (return {g('Summary')}))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    cdo = unreal.get_default_object(bp.generated_class())
    for name, value in (("Bounds", BOUNDS), ("Histogram", [0] * (PHASES * len(BOUNDS))),
                        ("Counts", [0] * PHASES), ("Maxima", [0.0] * PHASES)):
        cdo.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-Performance.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_PERFORMANCE_GENERATED")
# Controller wiring is authored next; run the metrics-only checks here.
tests = runpy.run_path(str(Path(__file__).with_name("test_performance.py")))
for name in ("test_histogram_bounds", "test_reset_metrics", "test_acceptance_boundaries", "test_long_uptime_elapsed"):
    tests[name]()
unreal.log("WO_PERFORMANCE_METRICS_TESTS_PASS")
