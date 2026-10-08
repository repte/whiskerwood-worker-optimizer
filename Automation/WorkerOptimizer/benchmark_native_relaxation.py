"""Unsaved editor Blueprint probe, never modifies production assets.

Native array copy/sort is one atomic phase item. This measures its maximum call
latency explicitly; a 64-item limit alone does not establish a frame-time bound.
"""

import json
from pathlib import Path
import struct
import time


TYPES = {
    "int": "Width Workers Cursor Index J0 J1 FreeColumn Stage StepWorkLimit LastStepWork",
    "float": "RowPotential LowerBound ForbiddenBound Delta Cur FreeMinimum MinimumValue ScratchValue",
    "bool": "BoundEnabled PrefixMode Done BestColumnFree CacheFree",
    "float[]": "ScoreRow U V MinV MaxScratch Masked Sorted",
    "int[]": "P Way UsedColumns AllowedColumns",
    "bool[]": "Used",
}


def sources(sort_node="Utilities|Array|Sort|SortFloatArray", find_node="Utilities|Array|FindItem"):
    def g(name):
        return f"(Variables|Default|Get{name})"

    def s(name, value):
        return f"(Variables|Default|Set{name} {value})"

    def a(name, index):
        return f'(Utilities|Array|Get(aref) :Array {g(name)} :"Dimension 1" {index})'

    def set_a(name, index, value):
        return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"

    def length(name):
        return f"(Utilities|Array|Length {g(name)})"

    def sort(name):
        return f"({sort_node} :TargetArray {g(name)} :bStableSort false)"

    def resize(name):
        return f"(Utilities|Array|Resize {g(name)} (+ {g('Width')} 1))"

    count = s("LastStepWork", f"(+ {g('LastStepWork')} 1)")
    increment = s("Cursor", f"(+ {g('Cursor')} 1)")
    choose = f"""
      (if (< {g('Cur')} {g('Delta')})
        {s('Delta', g('Cur'))} {s('J1', g('Index'))}
        {s('BestColumnFree', f'(== {a("P", g("Index"))} 0)')}
        (elif (== {g('Cur')} {g('Delta')})
          (if (not {g('BestColumnFree')})
            (if (== {a('P', g('Index'))} 0)
              {s('Delta', g('Cur'))} {s('J1', g('Index'))} {s('BestColumnFree', 'true')}))))
    """
    changed_free = f"""
      (if (== {a('P', g('Index'))} 0)
        (if (or (< {g('Cur')} {g('FreeMinimum')})
                 (and (== {g('Cur')} {g('FreeMinimum')}) (< {g('Index')} {g('FreeColumn')})))
          {s('FreeMinimum', g('Cur'))} {s('FreeColumn', g('Index'))}))
    """
    row_score = a("ScoreRow", f"(- {g('Index')} 1)")
    update = f"""
      {s('Cur', f'(- (- (- {row_score}) {g("RowPotential")}) {a("V", g("Index"))})')}
      (if (or (== {g('J0')} 0) (< {g('Cur')} {a('MinV', g('Index'))}))
        {set_a('MinV', g('Index'), g('Cur'))} {set_a('Way', g('Index'), g('J0'))}
        (if {g('CacheFree')} {changed_free})
        (else {s('Cur', a('MinV', g('Index')))}))
    """
    relax = f"""
      (if (not {a('Used', g('Index'))})
        (if {g('BoundEnabled')}
          (if (<= {a('MinV', g('Index'))} {g('LowerBound')})
            {s('Cur', a('MinV', g('Index')))} (else {update}))
          (else {update}))
        {choose})
    """
    # Each loop explicitly breaks; a void Blueprint return is not a loop break.
    dense = f"""
      (for work (range {g('StepWorkLimit')})
        (if (> {g('Cursor')} {g('Width')}) {s('Done', 'true')} (break))
        {s('Index', g('Cursor'))} {relax} {increment} {count})
      (if (> {g('Cursor')} {g('Width')}) {s('Done', 'true')})
    """
    native = f"""
      (switch int {g('Stage')}
        (:0
          {s('MaxScratch', g('MinV'))} {resize('MaxScratch')} {sort('MaxScratch')}
          {s('Stage', '6')}
          (if {g('BoundEnabled')}
            (if (<= {a('MaxScratch', g('Width'))} {g('ForbiddenBound')})
              {s('Stage', '1')} {s('Cursor', '0')}
              (if {g('PrefixMode')}
                {s('MaxScratch', g('MinV'))}
                (Utilities|Array|Resize {g('MaxScratch')} (+ {g('Workers')} 1))
                {sort('MaxScratch')}
                (if (> {a('MaxScratch', g('Workers'))} {g('LowerBound')})
                  {s('Stage', '6')} {s('Cursor', '1')}))))
          {count})
        (:1
          (for work (range {g('StepWorkLimit')})
            (if (>= {g('Cursor')} {length('AllowedColumns')}) (break))
            {s('Index', a('AllowedColumns', g('Cursor')))}
            (if (not {a('Used', g('Index'))}) {update})
            {increment} {count})
          (if (>= {g('Cursor')} {length('AllowedColumns')})
            {s('Stage', '2')} {s('Cursor', '0')})
          (if (== {g('LastStepWork')} 0) {count}))
        (:2
          {s('Masked', g('MinV'))} {resize('Masked')}
          {s('Stage', '3')} {s('Cursor', '0')} {count})
        (:3
          (for work (range {g('StepWorkLimit')})
            (if (>= {g('Cursor')} {length('UsedColumns')}) (break))
            {set_a('Masked', a('UsedColumns', g('Cursor')), '1e30')}
            {increment} {count})
          (if (>= {g('Cursor')} {length('UsedColumns')}) {s('Stage', '4')})
          (if (== {g('LastStepWork')} 0) {count}))
        (:4
          {s('Sorted', g('Masked'))} {sort('Sorted')}
          {s('MinimumValue', a('Sorted', '0'))}
          (if (== {g('FreeMinimum')} {g('MinimumValue')})
            {s('J1', g('FreeColumn'))}
            (else {s('J1', f'({find_node} :TargetArray {g("Masked")} :ItemToFind {g("MinimumValue")})')}))
          {s('Delta', a('MinV', g('J1')))}
          {s('BestColumnFree', f'(== {a("P", g("J1"))} 0)')}
          {s('Cursor', g('Width'))} {s('Stage', '5')} {count})
        (:5
          (for work (range {g('StepWorkLimit')})
            {count}
            (if (not {a('Used', g('Cursor'))})
              {s('Cur', a('MinV', g('Cursor')))} {s('Done', 'true')} (break))
            {s('Cursor', f'(- {g("Cursor")} 1)')}))
        (:6 {dense}))
    """
    potential = f"""
      (for work (range {g('StepWorkLimit')})
        (if (> {g('Cursor')} {g('Width')}) {s('Done', 'true')} (break))
        (if {a('Used', g('Cursor'))}
          {set_a('U', a('P', g('Cursor')), f'(+ {a("U", a("P", g("Cursor")))} {g("Delta")})')}
          {set_a('V', g('Cursor'), f'(- {a("V", g("Cursor"))} {g("Delta")})')}
          (else
            {s('ScratchValue', f'(- {a("MinV", g("Cursor"))} {g("Delta")})')}
            {set_a('MinV', g('Cursor'), g('ScratchValue'))}
            (if {g('CacheFree')}
              (if (== {a('P', g('Cursor'))} 0)
                (if (< {g('ScratchValue')} {g('FreeMinimum')})
                  {s('FreeMinimum', g('ScratchValue'))} {s('FreeColumn', g('Cursor'))})))))
        {increment} {count})
      (if (> {g('Cursor')} {g('Width')}) {s('Done', 'true')})
    """
    # Editor property assignment normalizes signed zero inside Python arrays.
    # Seed those bits in the VM so the fixture actually exercises the tie case.
    seed_zero = f"""
      {s('ScratchValue', f'(* {g("FreeMinimum")} -1.0)')}
      {set_a('MinV', '1', g('ScratchValue'))}
      {set_a('MinV', '3', g('ScratchValue'))}
      {set_a('MinV', '4', g('ScratchValue'))}
    """
    return {name: f"(fn {name} () {s('LastStepWork', '0')} {body})"
            for name, body in (("DenseStep", dense), ("NativeStep", native),
                               ("PotentialStep", potential), ("SeedSignedZero", seed_zero))}


def collect_snapshots():
    from test_solver_cached_trace import benchmark_matrices, solve
    from test_solver_row_order_model import reserve_matrix
    selected = {}
    pass_name = "first"

    def capture(row, potential, v, p, used, used_columns, minv, lower, j0, first_free, way):
        if j0 == 0:
            return None
        width, workers = len(row), 1000
        prefix = pass_name == "first"
        allowed = [j for j in range(1, width + 1) if row[j - 1] >= 0.0 and (not prefix or j > workers)]
        free = min((j for j in range(1, width + 1) if p[j] == 0), key=lambda j: (minv[j], j))
        eligible = lower is not None and max(minv) <= 1e20 - potential
        if prefix:
            eligible = eligible and max(minv[:workers + 1]) <= lower
        bucket = (pass_name, eligible, len(used_columns).bit_length())
        if bucket in selected:
            return None
        before = dict(ScoreRow=list(row), RowPotential=potential, V=list(v), P=list(p),
                      Used=list(used), UsedColumns=list(used_columns), MinV=list(minv), Way=list(way),
                      Width=width, Workers=workers, J0=j0, LowerBound=lower or 0.0,
                      BoundEnabled=lower is not None, ForbiddenBound=1e20 - potential,
                      PrefixMode=prefix, AllowedColumns=allowed, FreeMinimum=minv[free], FreeColumn=free)

        def finish(delta, j1, best_free, cur, actual_minv, actual_way):
            selected[bucket] = dict(label=str(bucket), eligible=eligible, before=before,
                                    after=dict(Delta=delta, J1=j1, BestColumnFree=best_free, Cur=cur,
                                               MinV=list(actual_minv), Way=list(actual_way)))
        return finish

    matrix, quality, coverage, bonus = benchmark_matrices(1000)
    first = solve(matrix, False, scan_probe=capture)
    matrix, _ = reserve_matrix(matrix, first, 1000, quality, coverage, bonus)
    pass_name = "reserve"
    solve(matrix, False, scan_probe=capture)
    snapshots = list(selected.values())
    snapshots.append(dict(label="signed_zero_free_tie", eligible=True, before=dict(
        ScoreRow=[-1e20, 0.0, 0.0, 0.0], RowPotential=0.0, V=[0.0] * 5,
        P=[1, 2, 0, 3, 0], Used=[True, True, False, False, False], UsedColumns=[0, 1],
        MinV=[0.0, -0.0, 0.0, -0.0, -0.0], Way=[0, 0, 7, 8, 9], Width=4,
        Workers=4, J0=1, LowerBound=0.0, BoundEnabled=True, ForbiddenBound=1e20,
        PrefixMode=False, AllowedColumns=[2, 3, 4], FreeMinimum=0.0, FreeColumn=2),
        after=dict(Delta=0.0, J1=2, BestColumnFree=True, Cur=-0.0,
                   MinV=[0.0, -0.0, 0.0, -0.0, -0.0], Way=[0, 0, 7, 8, 9])))
    return snapshots


def make_fixture():
    import unreal
    import toolset_registry
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
    bp = BP.create("/Game/WorkerOptimizerEditorTests", "BP_NativeRelaxation_" + str(time.time_ns()),
                   unreal.Object.static_class())
    for kind, names in TYPES.items():
        for name in names.split():
            BP.add_variable(bp, name, kind.removesuffix("[]"),
                            container_type=ContainerType.ARRAY if kind.endswith("[]") else None)
            BP.set_variable_instance_editable(bp, name, True)
    graphs = {name: BP.add_function_graph(bp, name) for name in sources()}
    BP.compile_blueprint(bp)
    available = BP.find_node_types(graphs["NativeStep"], "", [])

    def node(tail):
        matches = [value for value in available if value.lower().endswith("|" + tail.lower())]
        assert len(matches) == 1, (tail, matches)
        return matches[0]

    code = sources(node("SortFloatArray"), node("FindItem"))
    with toolset_registry.tool_raising_exceptions():
        for name, graph in graphs.items():
            BP.write_graph_dsl(graph, code[name])
        BP.compile_blueprint(bp, warnings_as_errors=True)
    return unreal.new_object(bp.generated_class())


def equal(actual, expected):
    if isinstance(expected, float):
        return struct.pack("!d", actual) == struct.pack("!d", expected)
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(equal(a, b) for a, b in zip(actual, expected))
    return actual == expected


def reset(instance, snapshot, native, limit=64):
    for name, value in snapshot["before"].items():
        instance.set_editor_property(name, value)
    if snapshot["label"] == "signed_zero_free_tie":
        instance.call_method("SeedSignedZero")
    for name, value in snapshot["before"].items():
        actual = instance.get_editor_property(name)
        assert equal(actual, value), ("Fixture input roundtrip", snapshot["label"], name, actual, value)
    for name, value in dict(Cursor=1, Stage=0, Delta=1e30, J1=0, BestColumnFree=False,
                            Cur=0.0, Done=False, StepWorkLimit=limit, CacheFree=native).items():
        instance.set_editor_property(name, value)


def measure(instance, method):
    elapsed = maximum = 0.0
    calls = work = 0
    phases = {}
    while not instance.get_editor_property("Done"):
        phase = str(instance.get_editor_property("Stage")) if method == "NativeStep" else method
        start = time.perf_counter()
        instance.call_method(method)
        seconds = time.perf_counter() - start
        units = int(instance.get_editor_property("LastStepWork"))
        assert 0 < units <= instance.get_editor_property("StepWorkLimit"), (method, phase, units)
        elapsed += seconds
        maximum = max(maximum, seconds)
        calls += 1
        work += units
        item = phases.setdefault(phase, dict(seconds=0.0, maximum=0.0, calls=0))
        item["seconds"] += seconds
        item["maximum"] = max(item["maximum"], seconds)
        item["calls"] += 1
        assert calls < 10000
    return dict(seconds=elapsed, maximum_call_seconds=maximum, calls=calls, work=work, phases=phases)


def run():
    import unreal
    output = Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-NativeRelaxationProbe.json")
    report = dict(scope="Compiled unsaved Blueprint microbenchmark, not full planner or gameplay timing",
                  budget="64 cell items; native copies/sorts are atomic phase items, latency measured",
                  snapshots=[], potential_overhead=[], passed=False)
    try:
        snapshots = collect_snapshots()
        instance = make_fixture()
        for snapshot in snapshots:
            record = dict(label=snapshot["label"], eligible=snapshot["eligible"], variants={})
            for native in (False, True):
                reset(instance, snapshot, native)
                method = "NativeStep" if native else "DenseStep"
                result = measure(instance, method)
                mismatches = []
                for name, expected in snapshot["after"].items():
                    actual = instance.get_editor_property(name)
                    if not equal(actual, expected):
                        if isinstance(expected, list):
                            detail = [(index, float(a).hex(), float(b).hex())
                                      for index, (a, b) in enumerate(zip(actual, expected))
                                      if not equal(a, b)][:8]
                        else:
                            detail = (float(actual).hex(), float(expected).hex())
                        mismatches.append((name, detail))
                assert not mismatches, (snapshot["label"], method, mismatches)
                record["variants"][method] = result
            report["snapshots"].append(record)
            after = snapshot["after"]
            if not after["BestColumnFree"] and after["Delta"] != 0.0:
                variants, expected = {}, None
                for cached in (False, True):
                    reset(instance, snapshot, cached)
                    for name, value in after.items():
                        instance.set_editor_property(name, value)
                    for name, value in dict(Cursor=0, Done=False, U=[0.0] * len(snapshot["before"]["P"]),
                                            FreeMinimum=1e30, FreeColumn=0).items():
                        instance.set_editor_property(name, value)
                    variants[str(cached)] = measure(instance, "PotentialStep")
                    actual = {name: list(instance.get_editor_property(name)) for name in ("U", "V", "MinV")}
                    if expected is None:
                        expected = actual
                    else:
                        assert all(equal(actual[name], expected[name]) for name in actual)
                        p = snapshot["before"]["P"]
                        free = min((j for j in range(1, snapshot["before"]["Width"] + 1) if p[j] == 0),
                                   key=lambda j: (actual["MinV"][j], j))
                        assert instance.get_editor_property("FreeColumn") == free
                        assert equal(instance.get_editor_property("FreeMinimum"), actual["MinV"][free])
                report["potential_overhead"].append(dict(label=snapshot["label"], variants=variants))
        report["passed"] = True
        unreal.log("WO_NATIVE_RELAXATION_MICROBENCH_PASS " + json.dumps(report, sort_keys=True))
    finally:
        output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        unreal.log("WO_NATIVE_RELAXATION_REPORT " + str(output))
    return report


if __name__ == "__main__":
    run()
