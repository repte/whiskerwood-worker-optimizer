"""Unsaved Blueprint prototype: +Inf VM probe, then exact solver lifecycles.

This is not a production integration test. It derives one native graph and a
test-only step wrapper from the current generator, leaving the parent untouched.
Run only after the saved parent and generator have the same source revision.
"""

import math
from pathlib import Path
import random
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType

from solver_used_label_marker_prototype import MARKER_VARIABLES, prototype_graphs, render
from test_solver_native_lifecycle_model import emitted


def bits(value):
    return struct.pack("!d", float(value))


def fixture_class(production=False):
    parent = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_UsedLabelMarker_" + str(time.time_ns()),
                      parent.generated_class())
    for name, (kind, array) in MARKER_VARIABLES.items():
        BP.add_variable(child, name, kind, container_type=ContainerType.ARRAY if array else None)
    names = ("MarkerAdvance", "MarkerAdvanceNativeRelaxation", "ConfigureMarker", "SeedMarkerInfinity",
             "SeedMarkerNegativeZero", "StopMarker", "InitializeMarkerImplicit")
    graphs = {name: BP.add_function_graph(child, name) for name in names}
    params = {
        "ConfigureMarker": [("Enabled", "bool", False), ("Prefix", "int", False),
                            ("Offsets", "int", True), ("Columns", "int", True)],
        "SeedMarkerInfinity": [("Zero", "float", False)],
        "SeedMarkerNegativeZero": [("Index", "int", False), ("Zero", "float", False)],
        "InitializeMarkerImplicit": [("Values", "float", True), ("Workers", "int", False),
            ("R", "int", False), ("C", "int", False), ("Starts", "int", True),
            ("Ends", "int", True), ("Allowed", "bool", True), ("Minima", "float", True),
            ("Seconds", "float", True), ("Winners", "int", True)],
    }
    for name, items in params.items():
        for param, kind, array in items:
            BP.add_function_param(graphs[name], param, kind, True, ContainerType.ARRAY if array else None)
    with toolset_registry.tool_raising_exceptions():
        BP.compile_blueprint(child)
    available = BP.find_node_types(graphs["MarkerAdvance"], "", [])

    def node(ending):
        matches = [value for value in available if value.endswith("|" + ending)]
        for preferred in ("Variables|Default|" + ending, "CallFunction|" + ending):
            if preferred in matches:
                return preferred
        assert len(matches) == 1, (ending, matches)
        return matches[0]

    def g(name):
        return f"({node('Get' + name)})"

    def s(name, value):
        return f"({node('Set' + name)} {value})"

    def at(name, index, value):
        return f"(Utilities|Array|SetArrayElem :TargetArray {g(name)} :Index {index} :Item {value})"

    base, symbol = emitted(Path(__file__).with_name("generate_solver.py"))
    prototype = None if production else prototype_graphs(base, symbol)

    def resolve(value):
        if isinstance(value, list):
            return [resolve(item) for item in value]
        if isinstance(value, symbol) and str(value).startswith("Variables|Default|"):
            return symbol(node(str(value).rsplit("|", 1)[1]))
        return value

    row_arrays = {"ImplicitModes": "3", "ImplicitMultipliers": "1", "ImplicitMinimumRows": "false",
                  "ImplicitRealRows": "true", "ImplicitFixedWorkers": "-1"}
    with toolset_registry.tool_raising_exceptions():
        for name in ("MarkerAdvance", "MarkerAdvanceNativeRelaxation"):
            if production:
                target = name.removeprefix("Marker")
                BP.write_graph_dsl(graphs[name], f"(fn {name} () ({node(target)}))")
            else:
                BP.write_graph_dsl(graphs[name], render(resolve(prototype[name]), symbol))
        BP.write_graph_dsl(graphs["ConfigureMarker"], f"""(fn ConfigureMarker (Enabled Prefix Offsets Columns)
          {s('NativePlannerTrusted', 'true')} {s('NativeCsrReady', f'(not {g("ImplicitFirstPass")})')}
          {s('NativeRowOffsets', 'Offsets')} {s('NativeColumns', 'Columns')}
          {s('ImplicitWorkerCount', 'Prefix')} {s('MarkerEnabled', 'Enabled')}
          {s('MarkerRow', '-1')} {s('MarkerSeenUsed', '0')} {s('MarkerPrefixUsed', '0')}
          {s('MarkerMarks', '0')}
          {f'(if Enabled ({node("EnableNativeDeadLabels")}))' if production else ''})""")
        BP.write_graph_dsl(graphs["SeedMarkerInfinity"], f"""(fn SeedMarkerInfinity (Zero)
          {s('MarkerInfinity', f'(- 0.0 ({node("Loge")} :A Zero))')}
          (Utilities|Array|Clear {g('MarkerProbeValues')})
          (Utilities|Array|Add {g('MarkerProbeValues')} {g('MarkerInfinity')})
          (Utilities|Array|Add {g('MarkerProbeValues')} (* Zero -1.0))
          (Utilities|Array|Add {g('MarkerProbeValues')} 1.0)
          (Utilities|Array|Add {g('MarkerProbeValues')} {g('MarkerInfinity')})
          (Utilities|Array|Add {g('MarkerProbeValues')} -3.0)
          (Utilities|Array|Add {g('MarkerProbeValues')} Zero)
          {s('MarkerProbeSorted', g('MarkerProbeValues'))}
          ({node('SortFloatArray')} :TargetArray {g('MarkerProbeSorted')} :bStableSort true)
          {s('MarkerProbeFound', f'({node("FindItem")} :TargetArray {g("MarkerProbeValues")} :ItemToFind {g("MarkerInfinity")})')})""")
        BP.write_graph_dsl(graphs["SeedMarkerNegativeZero"], f"""(fn SeedMarkerNegativeZero (Index Zero)
          (if {g('ImplicitFirstPass')} {at('ImplicitScores', 'Index', '(* Zero -1.0)')}
            (else {at('Scores', 'Index', '(* Zero -1.0)')})))""")
        BP.write_graph_dsl(graphs["StopMarker"], f"(fn StopMarker () {s('Done', 'true')})")
        BP.write_graph_dsl(graphs["InitializeMarkerImplicit"], f"""
          (fn InitializeMarkerImplicit (Values Workers R C Starts Ends Allowed Minima Seconds Winners)
            {s('ImplicitWorkerCount', 'Workers')} {s('ImplicitScores', 'Values')}
            {s('ImplicitDummyStarts', 'Starts')} {s('ImplicitDummyEnds', 'Ends')}
            {s('ImplicitDummyRows', 'Allowed')}
            {s('ImplicitFillBonus', '0.0')} {s('ImplicitCoverageBonus', '0.0')} {s('ImplicitColumnBonus', '0.0')}
            {' '.join(f'(Utilities|Array|Clear {g(name)})' for name in row_arrays)}
            (for r (range R)
              {' '.join(f'(Utilities|Array|Add {g(name)} {value})' for name, value in row_arrays.items())})
            ({node('InitializeImplicitFirstPass')} :RowCount R :ColumnCount C)
            {s('RowMinCost', 'Minima')} {s('RowSecondMinCost', 'Seconds')} {s('RowMinColumn', 'Winners')})""")
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


def create_instance(cls):
    obj = unreal.new_object(cls)
    obj.call_method("SeedMarkerInfinity", args=(0.0,))
    infinity = obj.get_editor_property("MarkerInfinity")
    assert math.isinf(infinity) and infinity > 0, ("VM did not produce positive infinity", infinity)
    assert obj.get_editor_property("MarkerProbeFound") == 0
    original = list(obj.get_editor_property("MarkerProbeValues"))
    ordered = list(obj.get_editor_property("MarkerProbeSorted"))
    assert bits(original[1]) == bits(-0.0), "VM negative-zero seed lost its sign"
    assert [bits(value) for value in ordered] == [bits(value) for value in (-3.0, -0.0, 0.0, 1.0, math.inf, math.inf)]
    return obj


def initialize(obj, matrix, enabled, limit, prefix, dummy=False, implicit=False):
    rows, cols = len(matrix), len(matrix[0])
    obj.set_editor_property("StepWorkLimit", limit)
    if implicit:
        starts, ends, allowed = [], [], []
        for row in matrix:
            legal = [j for j in range(prefix, cols) if row[j] >= 0.0]
            assert not legal or legal == list(range(legal[0], legal[-1] + 1))
            starts.append(legal[0] if legal else prefix)
            ends.append(legal[-1] + 1 if legal else prefix)
            allowed.append(bool(legal))
        costs = [[0.0 - value for value in row] for row in matrix]
        obj.call_method("InitializeMarkerImplicit", args=(
            [v for row in matrix for v in row[:prefix]], prefix, rows, cols, starts, ends, allowed,
            [min(row) for row in costs], [sorted(row)[1] if cols > 1 else 1e20 for row in costs],
            [row.index(min(row)) + 1 for row in costs]))
    else:
        obj.call_method("Initialize", args=([v for row in matrix for v in row], rows, cols))
        obj.call_method("RestrictDummies", args=([dummy] * rows,))
    assert not obj.get_editor_property("NativePlannerTrusted")
    seed_values = [v for row in matrix for v in (row[:prefix] if implicit else row)]
    for i, value in enumerate(seed_values):
        if bits(value) == bits(-0.0):
            obj.call_method("SeedMarkerNegativeZero", args=(i, 0.0))
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    obj.call_method("ConfigureMarker", args=(enabled, prefix, offsets, columns))


def result(obj):
    return {"Assignment": list(obj.get_editor_property("Assignment")),
            "Succeeded": bool(obj.get_editor_property("Succeeded")),
            "P": list(obj.get_editor_property("P")), "Way": list(obj.get_editor_property("Way")),
            "U": [bits(v) for v in obj.get_editor_property("U")],
            "V": [bits(v) for v in obj.get_editor_property("V")],
            "Cur": bits(obj.get_editor_property("Cur"))}


def solve(obj, matrix, enabled, limit, prefix, dummy=False, implicit=False):
    initialize(obj, matrix, enabled, limit, prefix, dummy, implicit)
    work = mask_calls = 0
    trace, phases, label_epoch = [], set(), 0
    while not obj.get_editor_property("Done"):
        before = int(obj.get_editor_property("SolverState"))
        row, j0 = int(obj.get_editor_property("ActiveRow")), int(obj.get_editor_property("J0"))
        if before == 11:
            phase = int(obj.get_editor_property("NativePhase"))
            phases.add(phase)
            mask_calls += phase == 3
        obj.call_method("MarkerAdvance" if enabled else "Advance")
        units = int(obj.get_editor_property("LastStepWork"))
        assert 0 < units <= limit, (units, limit)
        work += units
        assert work < 1000000
        if before != 6 and obj.get_editor_property("SolverState") == 6:
            if before == 5 and j0 == 0:
                label_epoch = row
            active = int(obj.get_editor_property("ActiveRow"))
            live = []
            if label_epoch == active:
                labels, used = list(obj.get_editor_property("MinV")), list(obj.get_editor_property("Used"))
                for j in range(int(obj.get_editor_property("Width")) + 1):
                    if not used[j]:
                        assert math.isfinite(labels[j]), ("nonfinite live label", j, labels[j])
                        live.append((j, bits(labels[j])))
            trace.append((active, int(obj.get_editor_property("I0")), int(obj.get_editor_property("J0")),
                          int(obj.get_editor_property("J1")), bits(obj.get_editor_property("Delta")), live))
    return result(obj), trace, work, mask_calls, phases


def run():
    cls = fixture_class()
    reference, candidate = create_instance(cls), create_instance(cls)
    unreal.log("WO_USED_LABEL_INFINITY_VM_PASS store/copy/stable-sort/find and signed zero")
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
        [[math.nan, 0.0]], [[math.inf, 0.0]], [[-math.inf, 0.0]],
        [[-0.0, 0.0, 0.0], [0.0, -0.0, 0.0]],
        [[199999999999999.97, -.09, 99999999999999.92, 200000000000000.06],
         [-.05, 200000000000000.06, 200000000000000.1, -.05],
         [.02, -.05, -.01, -.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]]]
    rng = random.Random(817521)
    for _ in range(40):
        rows, cols = rng.randint(1, 6), rng.randint(1, 9)
        matrices.append([[rng.choice([-1e20, -.09, -0.0, 0.0, .125, 1.03, 7., 1e14+.06])
                          for _ in range(cols)] for _ in range(rows)])
    comparisons = removed_masks = markers = old_work = new_work = 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for number, matrix in enumerate(matrices):
                prefix = (0, 1, len(matrix[0]), len(matrix[0]) + 1)[number % 4]
                expected = solve(reference, matrix, False, limit, prefix, dummy)
                actual = solve(candidate, matrix, True, limit, prefix, dummy)
                assert expected[:2] == actual[:2], (limit, dummy, number, "state or selection trace")
                assert actual[3] == 0
                if dummy:
                    assert candidate.get_editor_property("MarkerMarks") == 0
                comparisons += 1
                removed_masks += expected[3]
                markers += int(candidate.get_editor_property("MarkerMarks"))
                old_work += expected[2]
                new_work += actual[2]
    from test_solver_cached_trace import benchmark_matrices
    from test_solver_used_label_marker_model import reserve_matrix
    reserve_work = []
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix, quality, coverage, column_bonus = benchmark_matrices(size)
            expected = solve(reference, matrix, False, limit, size, implicit=True)
            actual = solve(candidate, matrix, True, limit, size, implicit=True)
            assert expected[:2] == actual[:2], ("implicit", size, limit)
            assert actual[3] == 0
            comparisons += 1
            removed_masks += expected[3]
            markers += int(candidate.get_editor_property("MarkerMarks"))
            old_work += expected[2]
            new_work += actual[2]
            later = reserve_matrix(matrix, list(reference.get_editor_property('U')),
                                   list(reference.get_editor_property('V')), size, quality, coverage, column_bonus)
            expected = solve(reference, later, False, limit, size)
            actual = solve(candidate, later, True, limit, size)
            assert expected[:2] == actual[:2], ("reserve", size, limit)
            assert actual[3] == 0, ("reserve work", size, limit, expected[2], actual[2])
            reserve_work.append((size, limit, expected[2], actual[2]))
            comparisons += 1
            removed_masks += expected[3]
            markers += int(candidate.get_editor_property("MarkerMarks"))
    cancellations = 0
    for phase in (0, 1, 4, 5):
        initialize(candidate, matrices[0], True, 1, 2)
        while not candidate.get_editor_property("Done"):
            if candidate.get_editor_property("SolverState") == 11 and candidate.get_editor_property("NativePhase") == phase:
                break
            candidate.call_method("MarkerAdvance")
        assert not candidate.get_editor_property("Done"), ("missing cancellation phase", phase)
        candidate.call_method("StopMarker")
        before = result(candidate), [bits(v) for v in candidate.get_editor_property("MinV")], candidate.get_editor_property("MarkerMarks")
        candidate.call_method("MarkerAdvance")
        after = result(candidate), [bits(v) for v in candidate.get_editor_property("MinV")], candidate.get_editor_property("MarkerMarks")
        assert after == before and candidate.get_editor_property("LastStepWork") == 0
        cancellations += 1
    assert removed_masks > 0 and markers > 0, (removed_masks, markers)
    assert any(new < old for _, _, old, new in reserve_work), reserve_work
    unreal.log(f"WO_USED_LABEL_MARKER_PROTOTYPE_PASS comparisons={comparisons} marker_writes={markers} "
               f"removed_mask_calls={removed_masks} random_and_first_work={old_work}->{new_work} "
               f"cancellations={cancellations} reserve_work={reserve_work}")


if __name__ == "__main__":
    run()
