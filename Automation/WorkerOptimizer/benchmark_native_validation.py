"""Unsaved Blueprint probe of native double-array validation/statistics.

The timed native path starts with the full flat input and gathers every row in
bounded Blueprint calls. No row preparation is moved outside the measurement.
Native searches, copies and stable sorts are atomic row-sized phase items; their
maximum call latency is reported separately from the primitive-work budget.
"""

import copy
import json
import math
from pathlib import Path
import struct
import sys
import time

sys.path.insert(0, str(Path(__file__).parent))
from planner_validation_dsl import statistics


TYPES = {
    "int": "WorkerCount RowCount StepWorkLimit LastStepWork PlanValidationIndex ScanRow ScanWorker StatsOffset StatsEnd StatsFirstColumn StatsMaximumColumn Stage GatherCursor GatherEnd NativeRows FallbackRows FailureIndex",
    "float": "ValidatedScore MaxScore StatsFirstScore StatsMaximumScore StatsPrefixScore StatsSecondScore NaNNeedle NegativeOne SeedScalar",
    "bool": "PlanDone PlanSucceeded FixedConfigured HasActualFixed StatsAllReal StatsUniformScore",
    "float[]": "BaseScores RowScratch Sorted Prefix RowFirstScore RowMaximumScore RowPrefixScore RowSecondScore",
    "int[]": "FixedSlots FixedOwners RowFirstColumn RowMaximumColumn",
    "bool[]": "RowAllReal RowUniformScore",
}
ROW_FIELDS = (
    ("RowFirstColumn", "StatsFirstColumn"), ("RowMaximumColumn", "StatsMaximumColumn"),
    ("RowFirstScore", "StatsFirstScore"), ("RowMaximumScore", "StatsMaximumScore"),
    ("RowPrefixScore", "StatsPrefixScore"), ("RowSecondScore", "StatsSecondScore"),
    ("RowAllReal", "StatsAllReal"), ("RowUniformScore", "StatsUniformScore"),
)
ORACLE_FIELDS = (
    "WorkerCount FixedConfigured HasActualFixed FixedSlots FixedOwners ScanRow ScanWorker "
    "PlanValidationIndex MaxScore PlanDone PlanSucceeded StatsOffset StatsEnd "
    "StatsFirstColumn StatsMaximumColumn StatsFirstScore StatsMaximumScore "
    "StatsPrefixScore StatsSecondScore StatsAllReal StatsUniformScore "
    "RowAllReal RowUniformScore RowFirstColumn RowMaximumColumn RowFirstScore "
    "RowMaximumScore RowPrefixScore RowSecondScore"
).split()


def sources(sort_node="Utilities|Array|Sort|SortFloatArray",
            find_node="Utilities|Array|FindItem", log_node="Math|Float|Loge"):
    g = lambda name: f"(Variables|Default|Get{name})"
    s = lambda name, value: f"(Variables|Default|Set{name} {value})"
    a = lambda name, index: f'(Utilities|Array|Get(aref) :Array {g(name)} :"Dimension 1" {index})'
    size = lambda name: f"(Utilities|Array|Length {g(name)})"
    sort = lambda name: f'({sort_node} :TargetArray {g(name)} :bStableSort true :SortOrder "Descending")'
    find = lambda name, value: f"({find_node} :TargetArray {g(name)} :ItemToFind {value})"
    last_worker = f'(- {g("WorkerCount")} 1)'
    set_a = lambda name, index, value: f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"
    reset_stats = "\n".join(s(name, "0") for name in ("StatsFirstColumn", "StatsMaximumColumn"))
    reset_stats += "\n" + "\n".join(s(name, "-1e20") for name in
                                   ("StatsFirstScore", "StatsMaximumScore", "StatsPrefixScore", "StatsSecondScore"))
    reset_stats += s("StatsAllReal", "true") + s("StatsUniformScore", "true")
    publish_row = "\n".join(f"(Utilities|Array|Add {g(target)} {g(source)})" for target, source in ROW_FIELDS)
    publish_row += s("StatsOffset", g("StatsEnd"))
    publish_row += s("StatsEnd", f'(+ {g("StatsEnd")} {g("WorkerCount")})') + reset_stats
    finish = s("PlanDone", "true") + s("PlanSucceeded", "true")
    count = s("LastStepWork", "(+ work 1)")
    fail = s("PlanDone", "true") + s("PlanSucceeded", "false") + s("FailureIndex", g("PlanValidationIndex"))
    # This is the existing per-cell validation and statistics order, including
    # configured all-unfixed input as supplied by the real search pipeline.
    cell = f"""
      {s('ValidatedScore', a('BaseScores', g('PlanValidationIndex')))}
      (bind value {g('ValidatedScore')})
      (if (not (and (>= value -1e20) (<= value 1e6))) {fail} (break))
      (if {g('HasActualFixed')}
        {s('ScanRow', f'(/ {g("PlanValidationIndex")} {g("WorkerCount")})')}
        {s('ScanWorker', f'(- {g("PlanValidationIndex")} (* {g("ScanRow")} {g("WorkerCount")}))')}
        (bind fixedWorker {a('FixedSlots', g('ScanRow'))})
        (bind fixedOwner {a('FixedOwners', g('ScanWorker'))})
        (if (or (and (>= fixedWorker 0) (!= fixedWorker {g('ScanWorker')}))
                (and (>= fixedOwner 0) (!= fixedOwner {g('ScanRow')})))
          {set_a('BaseScores', g('PlanValidationIndex'), '-1e20')}
          {s('ValidatedScore', '-1e20')}))
      {statistics(g, s, value='value', column=f'(+ (- {g("PlanValidationIndex")} {g("StatsOffset")}) 1)')}
      {s('PlanValidationIndex', f'(+ {g("PlanValidationIndex")} 1)')}
    """
    stream = f"""
      (for work (range {g('StepWorkLimit')})
        {count}
        (if (>= {g('PlanValidationIndex')} {size('BaseScores')}) {finish} (break))
        {cell}
        (if (== {g('PlanValidationIndex')} {g('StatsEnd')}) {publish_row}))
    """
    fallback = f"""
      {s('FallbackRows', f'(+ {g("FallbackRows")} 1)')}
      {s('Stage', '3')}
    """
    native = f"""
      (switch int {g('Stage')}
        (:0
          (if (> {g('StepWorkLimit')} 0)
            (if (>= {g('GatherCursor')} {size('BaseScores')})
              {s('LastStepWork', '1')} {finish}
              (else
                (bind remaining (- {g('StatsEnd')} {g('GatherCursor')}))
                {s('LastStepWork', f'(select (< {g("StepWorkLimit")} remaining) {g("StepWorkLimit")} remaining)')}
                {s('GatherEnd', f'(+ {g("GatherCursor")} {g("LastStepWork")})')}
                (for index (range {g('GatherCursor')} {g('GatherEnd')})
                  (Utilities|Array|Add {g('RowScratch')} {a('BaseScores', 'index')}))
                {s('GatherCursor', g('GatherEnd'))}
                (if (== {g('GatherCursor')} {g('StatsEnd')}) {s('Stage', '1')})))))
        (:1
          {s('LastStepWork', '1')}
          ; NaNs must be rejected before calling a numeric sort comparator.
          (if (or {g('HasActualFixed')} (>= {find('RowScratch', g('NaNNeedle'))} 0)) {fallback}
            (else
              {s('Sorted', g('RowScratch'))} {sort('Sorted')}
              (if (and (<= {a('Sorted', '0')} 1e6)
                       (>= {a('Sorted', f'(- {g("WorkerCount")} 1)')} 0.0))
                {s('Stage', '2')}
                (else {fallback})))))
        (:2
          {s('LastStepWork', '1')}
          {s('StatsFirstColumn', '1')} {s('StatsFirstScore', a('RowScratch', '0'))}
          {s('StatsMaximumScore', a('Sorted', '0'))}
          {s('StatsMaximumColumn', f'(+ {find("RowScratch", g("StatsMaximumScore"))} 1)')}
          (if (> {g('WorkerCount')} 1) {s('StatsSecondScore', a('Sorted', '1'))})
          {s('StatsAllReal', 'true')}
          {s('StatsUniformScore', f'(== {a("Sorted", "0")} {a("Sorted", last_worker)})')}
          (if (> {g('StatsMaximumColumn')} 1)
            {s('Prefix', g('RowScratch'))}
            (Utilities|Array|Resize {g('Prefix')} (- {g('StatsMaximumColumn')} 1))
            {sort('Prefix')} {s('StatsPrefixScore', a('Prefix', '0'))})
          (if (> {g('StatsMaximumScore')} {g('MaxScore')}) {s('MaxScore', g('StatsMaximumScore'))})
          {s('ValidatedScore', a('RowScratch', f'(- {g("WorkerCount")} 1)'))}
          (if {g('HasActualFixed')}
            {s('ScanRow', f'(/ {g("StatsOffset")} {g("WorkerCount")})')}
            {s('ScanWorker', f'(- {g("WorkerCount")} 1)')})
          {s('PlanValidationIndex', g('GatherCursor'))}
          {publish_row}
          (Utilities|Array|Clear {g('RowScratch')})
          {s('NativeRows', f'(+ {g("NativeRows")} 1)')} {s('Stage', '0')})
        (:3
          (for work (range {g('StepWorkLimit')})
            {count} {cell}
            (if (== {g('PlanValidationIndex')} {g('StatsEnd')})
              {publish_row} (Utilities|Array|Clear {g('RowScratch')})
              {s('Stage', '0')} (break))))
        (:Default {s('LastStepWork', '1')} {fail}))
    """
    clear = "\n".join(f"(Utilities|Array|Clear {g(name)})" for name in
                       ("RowScratch", "Sorted", "Prefix", *(target for target, _ in ROW_FIELDS)))
    reset = f"""
      {clear} {reset_stats}
      {s('PlanValidationIndex', '0')} {s('StatsOffset', '0')} {s('StatsEnd', g('WorkerCount'))}
      {s('ScanRow', '0')} {s('ScanWorker', '0')} {s('Stage', '0')} {s('GatherCursor', '0')} {s('GatherEnd', '0')}
      {s('NativeRows', '0')} {s('FallbackRows', '0')} {s('FailureIndex', '-1')}
      {s('LastStepWork', '0')} {s('MaxScore', '0.0')} {s('ValidatedScore', '0.0')}
      {s('PlanDone', 'false')} {s('PlanSucceeded', 'false')}
      {s('NegativeOne', '-1.0')} {s('NaNNeedle', f'({log_node} :A {g("NegativeOne")})')}
    """
    seed = f"""
      (switch int SeedKind
        (:0 {s('SeedScalar', '(* InputZero -1.0)')}
          {set_a('BaseScores', 'SeedIndex', g('SeedScalar'))})
        (:1 {s('SeedScalar', f'({log_node} :A {g("NegativeOne")})')}
          {set_a('BaseScores', 'SeedIndex', g('SeedScalar'))})
        (:2 {s('SeedScalar', f'(- 0.0 ({log_node} :A InputZero))')}
          {set_a('BaseScores', 'SeedIndex', g('SeedScalar'))})
        (:3 {s('SeedScalar', f'({log_node} :A InputZero)')}
          {set_a('BaseScores', 'SeedIndex', g('SeedScalar'))}))
    """
    return {
        "Reset": f"(fn Reset () {reset})",
        "SeedSpecial": f"(fn SeedSpecial (SeedIndex SeedKind InputZero) {seed})",
        "StreamingStep": f"(fn StreamingStep () {s('LastStepWork', '0')} (if (not {g('PlanDone')}) {stream}))",
        "NativeStep": f"(fn NativeStep () {s('LastStepWork', '0')} (if (not {g('PlanDone')}) {native}))",
    }


def make_fixture():
    import unreal
    import toolset_registry
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
    bp = BP.create("/Game/WorkerOptimizerEditorTests", "BP_NativeValidation_" + str(time.time_ns()),
                   unreal.Object.static_class())
    for kind, names in TYPES.items():
        for name in names.split():
            BP.add_variable(bp, name, kind.removesuffix("[]"),
                            container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
            BP.set_variable_instance_editable(bp, name, True)
    graphs = {name: BP.add_function_graph(bp, name) for name in sources()}
    for name, kind in (("SeedIndex", "int"), ("SeedKind", "int"), ("InputZero", "float")):
        BP.add_function_param(graphs["SeedSpecial"], name, kind, True)
    BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs["NativeStep"], "", [])

    def node(tail):
        matches = [name for name in available if name.lower().endswith("|" + tail.lower())]
        assert len(matches) == 1, (tail, matches)
        return matches[0]

    code = sources(node("SortFloatArray"), node("FindItem"), node("Loge"))
    with toolset_registry.tool_raising_exceptions():
        for name, graph in graphs.items():
            BP.write_graph_dsl(graph, code[name])
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return unreal.new_object(bp.generated_class())


def encoded(value):
    if isinstance(value, float):
        return struct.pack("!d", value).hex()
    if isinstance(value, (list, tuple)):
        return [encoded(item) for item in value]
    return value


def configure(instance, scores, width, rows, limit, configured=True, seeds=()):
    assert len(scores) == width * rows
    for name, value in dict(BaseScores=scores, WorkerCount=width, RowCount=rows,
                            FixedSlots=[-1] * rows, FixedOwners=[-1] * width,
                            FixedConfigured=configured, HasActualFixed=False, StepWorkLimit=limit).items():
        instance.set_editor_property(name, value)
    instance.call_method("Reset")
    assert math.isnan(instance.get_editor_property("NaNNeedle")), "Native Loge(-1) must yield a real NaN needle"
    for index, kind in seeds:
        instance.call_method("SeedSpecial", args=(index, kind, 0.0))
    if seeds:
        actual = list(instance.get_editor_property("BaseScores"))
        for index, kind in seeds:
            if kind == 0:
                assert encoded(actual[index]) == "8000000000000000", "Fixture must preserve VM-generated negative-zero bits"
            elif kind == 1:
                assert math.isnan(actual[index])
            else:
                assert actual[index] == (math.inf if kind == 2 else -math.inf)


def snapshot(instance, include_input=False):
    arrays = {name for kind, names in TYPES.items() if kind.endswith("[]") for name in names.split()}
    names = ORACLE_FIELDS + (["BaseScores"] if include_input else [])
    return {name: list(instance.get_editor_property(name)) if name in arrays
            else instance.get_editor_property(name) for name in names}


def expected_from(before):
    from test_planner_validation_cache_model import oracle_cell
    expected = copy.deepcopy(before)
    configured = expected["FixedConfigured"]
    # Support the original oracle too: actual masking, not API configuration,
    # decides whether an all-unfixed row visits owner checks.
    expected["FixedConfigured"] = expected["HasActualFixed"]
    while not expected["PlanDone"] and expected["PlanValidationIndex"] < len(expected["BaseScores"]):
        oracle_cell(expected)
    if not expected["PlanDone"]:
        expected["PlanDone"], expected["PlanSucceeded"] = True, True
    expected["FixedConfigured"] = configured
    return expected


def assert_state(instance, expected, label, include_input=False):
    actual = snapshot(instance, include_input)
    for name, value in actual.items():
        assert encoded(value) == encoded(expected[name]), (label, name, encoded(value), encoded(expected[name]))
    expected_failure = expected["PlanValidationIndex"] if not expected["PlanSucceeded"] else -1
    assert instance.get_editor_property("FailureIndex") == expected_failure, (label, "FailureIndex")


def measure(instance, method):
    calls = work = 0
    total = maximum = 0.0
    phases = {}
    limit = int(instance.get_editor_property("StepWorkLimit"))
    cells = len(instance.get_editor_property("BaseScores"))
    rows = int(instance.get_editor_property("RowCount"))
    host_start = time.perf_counter()
    while not instance.get_editor_property("PlanDone"):
        phase = str(instance.get_editor_property("Stage")) if method == "NativeStep" else "stream"
        start = time.perf_counter()
        instance.call_method(method)
        elapsed = time.perf_counter() - start
        units = int(instance.get_editor_property("LastStepWork"))
        assert 0 < units <= limit, (method, phase, units, limit)
        calls += 1
        work += units
        total += elapsed
        maximum = max(maximum, elapsed)
        item = phases.setdefault(phase, dict(seconds=0.0, calls=0, work=0, maximum_call_seconds=0.0))
        item["seconds"] += elapsed
        item["calls"] += 1
        item["work"] += units
        item["maximum_call_seconds"] = max(item["maximum_call_seconds"], elapsed)
        assert calls <= 3 * cells + 5 * rows + 10, "Validation probe exceeded its finite bound"
    return dict(compiled_call_sum_seconds=total, host_seconds=time.perf_counter() - host_start,
                maximum_call_seconds=maximum, calls=calls, work=work, phases=phases,
                native_rows=int(instance.get_editor_property("NativeRows")),
                fallback_rows=int(instance.get_editor_property("FallbackRows")))


def verify_cases(instance):
    near = math.nextafter(1.0, 2.0)
    cases = [
        ("empty", [], 0, 0, ()),
        ("zero_workers", [], 0, 2, ()),
        ("singletons", [0.0, 1.0, 1e6], 1, 3, ((0, 0),)),
        ("prefix_ties", [2.0, 2.0, 9.0, 1.0, 9.0, 3.0, 9.0, 9.0, 1.0, 2.0, 2.0, 3.0], 6, 2, ()),
        ("double_precision", [1.0, near, 1.0, near, 1e6, math.nextafter(1e6, 0.0)], 3, 2, ()),
        ("signed_zero_ties", [0.0] * 12, 4, 3, ((0, 0), (2, 0), (5, 0), (7, 0), (8, 0), (9, 0))),
        ("negative_fallback", [-1e20, -1.0, 0.0, 3.0, 0.0, -1.0, 2.0, 2.0], 4, 2, ((2, 0),)),
        ("all_negative", [-1e20, -1.0, -0.1, -1e20], 2, 2, ()),
    ]
    for index in (0, 3, 7, 11):
        for kind, label in ((1, "nan"), (2, "positive_inf"), (3, "negative_inf")):
            cases.append((f"{label}_{index}", [1.0] * 12, 4, 3, ((index, kind),)))
        for value, label in ((math.nextafter(-1e20, -math.inf), "below_bound"),
                             (math.nextafter(1e6, math.inf), "above_bound")):
            values = [1.0] * 12
            values[index] = value
            cases.append((f"{label}_{index}", values, 4, 3, ()))
    checks = []
    for label, scores, width, rows, seeds in cases:
        for configured in (False, True):
            for limit in (1, 3, 64):
                expected = None
                variants = {}
                for method in ("StreamingStep", "NativeStep"):
                    configure(instance, scores, width, rows, limit, configured, seeds)
                    before = snapshot(instance, True)
                    if expected is None:
                        expected = expected_from(before)
                    else:
                        assert encoded(before["BaseScores"]) == encoded(expected_from(before)["BaseScores"])
                    variants[method] = measure(instance, method)
                    assert_state(instance, expected, (label, configured, limit, method), True)
                    # A late call after completion must be inert and report no work.
                    instance.call_method(method)
                    assert instance.get_editor_property("LastStepWork") == 0
                    assert_state(instance, expected, (label, "completed", method), True)
                checks.append(dict(label=label, configured=configured, limit=limit,
                                   succeeded=expected["PlanSucceeded"], variants=variants))
    # Replacing an input after an interrupted gather or native-sort phase must reset all caches.
    for interrupt_after in (1, 2, 3):
        configure(instance, [1.0, 2.0, 3.0, 4.0] * 3, 4, 3, 64)
        for _ in range(interrupt_after):
            instance.call_method("NativeStep")
        configure(instance, [2.0, 1.0, 0.0], 3, 1, 1, seeds=((2, 0),))
        expected = expected_from(snapshot(instance, True))
        measure(instance, "NativeStep")
        assert_state(instance, expected, ("restart", interrupt_after), True)
    return checks


def benchmark_case(instance, workers, mode):
    rows = workers + 3
    scores = [100.0 if mode == "ties" else 1.0] * (workers * workers)
    if mode == "unique":
        for row in range(workers):
            scores[row * workers + row] = 100.0
    quality = [float((worker % 97) + 1) + 0.125 for worker in range(workers)]
    scores.extend(quality * 3)
    result = dict(workers=workers, rows=rows, cells=len(scores), mode=mode,
                  configured_unfixed=True, limit=64, variants={})
    expected = None
    # These are real compiled calls; Python only builds fixtures and checks outcomes.
    for method in ("StreamingStep", "NativeStep"):
        configure(instance, scores, workers, rows, 64)
        if expected is None:
            expected = expected_from(snapshot(instance, True))
        result["variants"][method] = measure(instance, method)
        assert_state(instance, expected, (workers, mode, method))
    native = result["variants"]["NativeStep"]
    assert native["native_rows"] == rows and native["fallback_rows"] == 0
    result["native_vs_streaming_ratio"] = (native["compiled_call_sum_seconds"] /
                                            result["variants"]["StreamingStep"]["compiled_call_sum_seconds"])
    return result


def run(workers=1500):
    import unreal
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-NativeValidationProbe.json")
    report = dict(passed=False, scope="Compiled unsaved Blueprint validation probe, not a full planner benchmark",
                  timed_input="Full flat BaseScores; all Blueprint row gathering, native search/copies/sorts, statistics and publication included",
                  excluded="Fixture generation, Python input marshalling, Reset, compilation and Python correctness oracle",
                  budget="1/3/64 primitive items; native operations are at most one row or row prefix, with call latency measured",
                  phases={"0": "bounded row gathering", "1": "NaN search and stable row sort", "2": "exact row statistics and prefix sort", "3": "legacy cell fallback"},
                  correctness=[], benchmarks=[])
    try:
        instance = make_fixture()
        report["correctness"] = verify_cases(instance)
        unreal.log("WO_NATIVE_VALIDATION_CORRECTNESS_PASS " + str(len(report["correctness"])) + " cases plus interrupted-phase restarts")
        for mode in ("unique", "ties"):
            record = benchmark_case(instance, workers, mode)
            report["benchmarks"].append(record)
            unreal.log("WO_NATIVE_VALIDATION_MEASURE " + json.dumps(record, sort_keys=True))
        report["passed"] = True
        unreal.log("WO_NATIVE_VALIDATION_PROBE_PASS: compiled double-array exact statistics, bounded full-input gathering, negative fallback and VM special-value fixtures")
    finally:
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        unreal.log("WO_NATIVE_VALIDATION_REPORT " + str(output))
    return report


if __name__ == "__main__":
    run()
