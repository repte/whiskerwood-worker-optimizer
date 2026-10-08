"""Compiled and emitted per-call proof for certified inert dummy suffixes.

The reference is the independently frozen legacy potential graph. New fields
are optional during the old-asset RED run; exactness is checked before the
activation assertion. No production assets are written by this fixture.
"""

import ast
import copy
import math
from pathlib import Path
import struct
import sys
import time

from solver_label_upper_bound_dsl import UPPER_VARIABLES


NEW_FIELDS = {
    "NativeDummyBound", "NativeDummyBoundReady", "NativeDummyBoundRow",
    "NativeDummyInitCount", "NativeUsedRealOnly", "PotentialDummySkip", "PotentialLoopEnd",
}
IGNORED = NEW_FIELDS | {"PotentialEnd", "PotentialFreeFixedColumn"} | set(UPPER_VARIABLES)
THRESHOLD = float(2 ** 66)


def encoded(value):
    if isinstance(value, float):
        return struct.pack("!d", value)
    if isinstance(value, (bool, int, str)):
        return value
    return tuple(encoded(item) for item in value)


def cases():
    for limit in (1, 3, 64):
        for workers, dummies in ((4, 1), (6, 65)):
            for variant in ("valid", "not_ready", "wrong_row", "incomplete", "used_dummy", "cache_invalid", "generic"):
                for bound, delta in (
                    (THRESHOLD, .125), (THRESHOLD, math.nextafter(4096., 0.)),
                    (THRESHOLD, 4096.), (math.nextafter(THRESHOLD, 0.), 4096.),
                    (1e20, -1.), (1e20, 1e14), (1e20, 0.)):
                    if variant == "used_dummy" and dummies == 1:
                        continue
                    yield limit, workers, dummies, variant, bound, delta


def state_for(case):
    limit, workers, dummies, variant, bound, delta = case
    width, rows = workers + dummies, workers + 2
    p = [rows] + list(range(1, workers + 1)) + [0] * dummies
    visited = [0, 2]
    if variant == "used_dummy":
        p[workers + 1] = workers + 1
        visited.append(workers + 1)
    first = next(j for j in range(1, width + 1) if p[j] == 0)
    labels = [-0.0] + [float(j) / 8 for j in range(1, workers + 1)]
    labels.extend(bound + (j % 3) * math.ulp(bound) for j in range(dummies))
    labels[first] = bound
    ready, same_row = variant != "not_ready", variant != "wrong_row"
    state = dict(StepWorkLimit=limit, P=p, Used=[j in visited for j in range(width + 1)],
                 UsedColumns=visited, U=[.125 * j for j in range(rows + 1)],
                 V=[-.125 * j for j in range(width + 1)], MinV=labels,
                 Rows=rows, Width=width, Cols=width, DummyCount=0,
                 ActiveRow=rows, J0=0, J1=1, Delta=delta, Cursor=0,
                 Done=False, Succeeded=False, SolverState=6, LastStepWork=91,
                 NonpositiveV=True, Cur=-71.25, NativeValue=37.5,
                 NativePlannerTrusted=variant != "generic", ImplicitWorkerCount=workers,
                 NativeFreeValid=variant != "cache_invalid", NativeFreeRow=rows,
                 NativeFreeColumn=first, NativeFreeMinimum=bound, FirstFreeColumn=first,
                 NativeMaskReady=True, NativeMaskRow=rows,
                 NativeDummyBound=bound, NativeDummyBoundReady=ready,
                 NativeDummyBoundRow=rows if same_row else rows + 1,
                 NativeDummyInitCount=dummies - (variant == "incomplete"),
                 NativeUsedRealOnly=variant != "used_dummy", PotentialDummySkip=False)
    eligible = (variant == "valid" and bound >= THRESHOLD and 0.0 < delta < 4096.)
    return state, eligible


def legacy_namespace():
    path = Path(__file__).with_name("test_solver_potential_batch.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [item for item in tree.body if not (
        isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
        and isinstance(item.value.func, ast.Name) and item.value.func.id == "run")]
    env = {"__file__": str(path)}
    exec(compile(tree, str(path), "exec"), env)
    return env


def fixture_class(legacy):
    import unreal
    import toolset_registry
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    parent, names = legacy["fixture_class"]()
    fields = set(BP.list_variables(unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")))
    present = NEW_FIELDS <= fields
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_DummySuffix_" + str(time.time_ns()), parent)
    graph = BP.add_function_graph(child, "SeedSuffixCertificate")
    params = (("Workers", "int"), ("Ready", "bool"), ("SameRow", "bool"), ("Bound", "float"),
              ("Witnesses", "int"), ("UsedReal", "bool"), ("First", "int"), ("CacheValid", "bool"))
    for name, kind in params:
        BP.add_function_param(graph, name, kind, True)
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(graph, "", [])

    def node(tail):
        options = [name for name in nodes if name.endswith("|" + tail)]
        preferred = "Variables|Default|" + tail
        assert preferred in options or len(options) == 1, (tail, options)
        return preferred if preferred in options else options[0]

    get = lambda name: f"({node('Get' + name)})"
    put = lambda name, value: f"({node('Set' + name)} {value})"
    extra = ""
    if present:
        extra = "\n".join((put("NativeDummyBound", "Bound"), put("NativeDummyBoundReady", "Ready"),
            put("NativeDummyBoundRow", f'(select SameRow {get("ActiveRow")} (+ {get("ActiveRow")} 1))'),
            put("NativeDummyInitCount", "Witnesses"), put("NativeUsedRealOnly", "UsedReal"),
            put("PotentialDummySkip", "false")))
    source = f"""(fn SeedSuffixCertificate ({' '.join(name for name, _ in params)})
      {put('ImplicitWorkerCount', 'Workers')} {put('FirstFreeColumn', 'First')}
      {put('NativeFreeColumn', 'First')} {put('NativeFreeMinimum', 'Bound')}
      {put('NativeFreeValid', 'CacheValid')} {put('NativeFreeRow', get('ActiveRow'))}
      {extra})"""
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graph, source)
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class(), [name for name in names if name not in IGNORED], present


def seed_compiled(cls, state):
    import unreal
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    for obj in pair:
        obj.set_editor_property("StepWorkLimit", state["StepWorkLimit"])
        obj.call_method("SeedPotentialTest", args=(state["NativePlannerTrusted"], 0,
            state["P"], state["Used"], state["UsedColumns"], state["U"], state["V"],
            state["MinV"], state["Delta"], state["J1"]))
        obj.call_method("SeedSuffixCertificate", args=(state["ImplicitWorkerCount"],
            state["NativeDummyBoundReady"], state["NativeDummyBoundRow"] == state["ActiveRow"],
            state["NativeDummyBound"], state["NativeDummyInitCount"], state["NativeUsedRealOnly"],
            state["FirstFreeColumn"], state["NativeFreeValid"]))
    return pair


def lifecycle_matrix():
    return [
        [100., 1., 1., 1., 0., -1e20],
        [1., 100., 1., 1., -1e20, -1e20],
        [1., 1., 100., 1., -1e20, 0.],
        [1., 1., 1., 100., -1e20, -1e20],
        [3., 7., 5., 9., -1e20, -1e20],
        [6., 8., 4., 2., -1e20, -1e20],
    ]


def check_witness(state, workers):
    if state("NativeDummyBoundReady") and state("NativeDummyBoundRow") == state("ActiveRow"):
        width = state("Width")
        assert state("NativeDummyInitCount") == width - workers
        assert state("NativeDummyBound") <= min(state("MinV")[workers + 1:width + 1])
        return 1
    return 0


def compiled_lifecycle(cls, names, legacy):
    import unreal
    matrix, workers = lifecycle_matrix(), 4
    witnessed = partial = 0
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    for limit in (1, 3, 64):
        legacy["initialize_pair"](pair, matrix, True, [False] * len(matrix), limit, names)
        for obj in pair:
            obj.call_method("SeedSuffixCertificate", args=(workers, False, True, 1e30, 0, True, 1, False))
        steps = 0
        while not pair[0].get_editor_property("Done"):
            legacy["advance_pair"](*pair, names, limit, ("suffix lifecycle", limit, steps))
            state = pair[0].get_editor_property
            count = state("NativeDummyInitCount")
            if 0 < count < state("Width") - workers:
                assert not state("NativeDummyBoundReady"), "Partial suffix witnesses cannot publish a bound"
                partial += 1
            witnessed += check_witness(state, workers)
            steps += 1
            assert steps < 20000
        # Start the same objects again and stop during a partially witnessed row.
        legacy["initialize_pair"](pair, matrix, True, [False] * len(matrix), 1, names)
        for obj in pair:
            assert not obj.get_editor_property("NativeDummyBoundReady")
            assert obj.get_editor_property("NativeDummyInitCount") == 0
            obj.call_method("SeedSuffixCertificate", args=(workers, False, True, 1e30, 0, True, 1, False))
        for step in range(20000):
            legacy["advance_pair"](*pair, names, 1, ("partial cancellation", step))
            if pair[0].get_editor_property("NativeDummyInitCount") == 1:
                break
        else:
            raise AssertionError("Fixture never reached partial suffix initialization")
        for obj in pair:
            obj.call_method("StopPotentialTest")
        pair[0].call_method("Advance")
        pair[1].call_method("StepLegacy")
        legacy["compare"](*pair, names, ("cancelled partial suffix", limit))
        assert pair[0].get_editor_property("LastStepWork") == 0
        for obj in pair:
            assert not obj.get_editor_property("NativeDummyBoundReady")
            obj.call_method("Initialize", args=([1.0], 1, 1))
            assert not obj.get_editor_property("NativeDummyBoundReady")
            assert obj.get_editor_property("NativeDummyInitCount") == 0
            assert not obj.get_editor_property("PotentialDummySkip")
    assert witnessed > 0 and partial > 0, (witnessed, partial)
    return witnessed, partial


def compiled_run():
    import unreal
    legacy = legacy_namespace()
    cls, names, present = fixture_class(legacy)
    phases = calls = activations = 0
    for case in cases():
        state, expected = state_for(case)
        pair = seed_compiled(cls, state)
        legacy["compare"](*pair, names, ("suffix seed", case))
        total = 0
        while pair[0].get_editor_property("SolverState") == 6:
            legacy["advance_pair"](*pair, names, case[0], ("suffix", case))
            work = pair[0].get_editor_property("LastStepWork")
            total += work
            assert total <= state["Width"] + 2
            if present and total == work:
                actual = bool(pair[0].get_editor_property("PotentialDummySkip"))
                assert actual == expected, (case, actual, expected)
                activations += actual
            calls += 1
        assert total == (1 if state["Delta"] == 0.0 else state["Width"] + 2)
        if present:
            # A ready current-row bound is adjusted once, never once per chunk.
            valid = (state["NativeDummyBoundReady"] and
                     state["NativeDummyBoundRow"] == state["ActiveRow"] and
                     state["NativeDummyInitCount"] == case[2] and state["NativePlannerTrusted"])
            expected_bound = state["NativeDummyBound"]
            if valid and state["Delta"] > 0.0:
                expected_bound -= state["Delta"]
            assert encoded(pair[0].get_editor_property("NativeDummyBound")) == encoded(expected_bound), case
        phases += 1
    unreal.log(f"WO_DUMMY_SUFFIX_EXACTNESS_PASS phases={phases} calls={calls}")
    assert present and activations > 0, "Certified inert explicit-dummy suffix is not integrated"
    witnessed, partial = compiled_lifecycle(cls, names, legacy)
    # Existing fixture covers cancellation, exact phase exits and object reuse.
    legacy["compare_lifecycle"](cls, names)
    for obj in pair:
        obj.call_method("Initialize", args=([1.0], 1, 1))
        assert not obj.get_editor_property("NativeDummyBoundReady")
        assert obj.get_editor_property("NativeDummyInitCount") == 0
        assert not obj.get_editor_property("PotentialDummySkip")
    unreal.log(f"WO_DUMMY_SUFFIX_BOUND_TESTS_PASS activations={activations} phases={phases} calls={calls} "
               f"witnessed={witnessed} partial={partial}")


def offline_run():
    from test_solver_native_lifecycle_model import emitted, SolverMachine
    from test_native_microbenchmark_model import parser
    graphs, symbol = emitted(Path(__file__).with_name("generate_solver.py"))
    tree = ast.parse(Path(__file__).with_name("test_solver_potential_batch.py").read_text(encoding="utf-8"))
    frozen = next(ast.literal_eval(item.value) for item in tree.body if isinstance(item, ast.Assign)
                  and isinstance(item.targets[0], ast.Name) and item.targets[0].id == "LEGACY_DSL")
    parse, old_symbol = parser()

    def convert(form):
        if isinstance(form, list):
            return [convert(value) for value in form]
        return symbol(str(form)) if isinstance(form, old_symbol) else form

    old_graphs = copy.deepcopy(graphs)
    old_graphs["AdvancePotentials"] = convert(parse(frozen))

    class Counted(SolverMachine):
        def __init__(self, source, limit):
            super().__init__(source, symbol, limit)
            self.label_writes = 0

        def evaluate(self, form):
            if (isinstance(form, list) and form and str(form[0]) == "Utilities|Array|SetArrayElem"
                    and str(form[2][0]) == "Variables|Default|GetMinV"):
                self.label_writes += 1
            if (isinstance(form, list) and form and str(form[0]) == "Variables|SetBy-RefVar"
                    and str(form[2][2][0]) == "Variables|Default|GetMinV"):
                self.label_writes += 1
            return super().evaluate(form)

    phases = calls = skipped = 0
    failures = []
    for case in cases():
        state, expected = state_for(case)
        pair = [Counted(graphs, case[0]), Counted(old_graphs, case[0])]
        for machine in pair:
            machine.state = copy.deepcopy(state)
        total = 0
        while pair[0].state["SolverState"] == 6:
            for machine in pair:
                machine.invoke("Advance")
            names = (pair[0].state.keys() | pair[1].state.keys()) - IGNORED
            for name in names:
                assert encoded(pair[0].state.get(name, 0)) == encoded(pair[1].state.get(name, 0)), (case, name)
            assert 0 < pair[0].state["LastStepWork"] <= case[0]
            total += pair[0].state["LastStepWork"]
            if total == pair[0].state["LastStepWork"]:
                assert bool(pair[0].state["PotentialDummySkip"]) == expected, case
            calls += 1
        valid = (state["NativeDummyBoundReady"] and
                 state["NativeDummyBoundRow"] == state["ActiveRow"] and
                 state["NativeDummyInitCount"] == case[2] and state["NativePlannerTrusted"])
        expected_bound = state["NativeDummyBound"]
        if valid and state["Delta"] > 0.0:
            expected_bound -= state["Delta"]
        assert encoded(pair[0].state["NativeDummyBound"]) == encoded(expected_bound), case
        saved = pair[1].label_writes - pair[0].label_writes
        if saved != (case[2] if expected else 0):
            failures.append((case, saved, case[2] if expected else 0))
        skipped += saved
        phases += 1
    assert not failures, ("Certified dummy suffix still writes unchanged labels", failures[:3])
    witnessed = partial = lifecycle_saved = 0
    matrix, workers = lifecycle_matrix(), 4
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, score in enumerate(row) if score != -1e20)
        offsets.append(len(columns))
    for limit in (1, 3, 64):
        pair = [Counted(graphs, limit), Counted(old_graphs, limit)]
        for machine in pair:
            machine.invoke("Initialize", [[x for row in matrix for x in row], len(matrix), len(matrix[0])])
            machine.invoke("RestrictDummies", [[False] * len(matrix)])
            machine.state.update(NativePlannerTrusted=True, NativeCsrReady=True,
                NativeRowOffsets=offsets[:], NativeColumns=columns[:], ImplicitWorkerCount=workers)
        steps = 0
        while not pair[0].state["Done"]:
            for machine in pair:
                machine.invoke("Advance")
            names = (pair[0].state.keys() | pair[1].state.keys()) - IGNORED
            for name in names:
                assert encoded(pair[0].state.get(name, 0)) == encoded(pair[1].state.get(name, 0)), (limit, steps, name)
            state = lambda name: pair[0].state.get(name, 0)
            count = state("NativeDummyInitCount")
            if 0 < count < state("Width") - workers:
                assert not state("NativeDummyBoundReady")
                partial += 1
            witnessed += check_witness(state, workers)
            steps += 1
            assert steps < 20000
        lifecycle_saved += pair[1].label_writes - pair[0].label_writes
        pair[0].invoke("Initialize", [[1.0], 1, 1])
        assert not pair[0].state["NativeDummyBoundReady"]
        assert pair[0].state["NativeDummyInitCount"] == 0
        assert not pair[0].state["PotentialDummySkip"]
    assert witnessed > 0 and partial > 0 and lifecycle_saved > 0, (witnessed, partial, lifecycle_saved)
    print("WO_DUMMY_SUFFIX_BOUND_MODEL_PASS", phases, "phases", calls, "calls", skipped,
          "seeded writes avoided; lifecycle", lifecycle_saved, "writes avoided", witnessed, "ready", partial, "partial")


if __name__ == "__main__":
    offline_run() if "--offline" in sys.argv else compiled_run()
