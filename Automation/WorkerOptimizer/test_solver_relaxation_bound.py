"""Compiled cache and bitwise regressions for generalized relaxation bounds."""

import random
import struct
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from planner_test_cost_probe import probe_class, read_scores
from test_planner_fused_matrix import CASES, PLANNER_CLASS, expected_pass


PRODUCTION = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
SOLVER_CLASS = PRODUCTION.generated_class()
REQUIRED = {"RowSecondMinCost", "RelaxationLowerBound", "RelaxationBoundEnabled"}
REFERENCES = {}


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def reference_class(parent):
    key = parent.get_path_name()
    if key in REFERENCES:
        return REFERENCES[key]
    child = BP.create("/Game/WorkerOptimizerEditorTests",
                      "BP_RelaxationBoundReference_" + uuid.uuid4().hex, parent)
    toggle = BP.add_function_graph(child, "SetBoundEnabled")
    BP.add_function_param(toggle, "Enabled", "bool", True)
    force = BP.add_function_graph(child, "PrepareBoundFixture")
    BP.add_function_param(force, "InputLabels", "float", True, ContainerType.ARRAY)
    BP.compile_blueprint(child)

    def node(name):
        matches = [value for value in BP.find_node_types(toggle, name, []) if value.endswith("|" + name)]
        preferred = "Variables|Default|" + name
        assert preferred in matches or len(matches) == 1, (name, matches)
        return preferred if preferred in matches else matches[0]

    def get(name):
        return "(" + node("Get" + name) + ")"

    def put(name, value):
        return "(" + node("Set" + name) + " " + value + ")"

    def set_at(name, index, value):
        return f"(Utilities|Array|SetArrayElem :TargetArray {get(name)} :Index {index} :Item {value})"

    # The previous zero-only shortcut may remain as a compatibility path. A
    # reference scan must disable both certificates, never public-editable flags.
    zero_reset = put("ZeroLabelBound", "false") if "ZeroLabelBound" in BP.list_variables(PRODUCTION) else ""
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(toggle, f"""(fn SetBoundEnabled (Enabled)
          {put('RelaxationBoundEnabled', 'Enabled')} {zero_reset}
          (if Enabled {put('RelaxationLowerBound', '123.0')}))""")
        BP.write_graph_dsl(force, f"""(fn PrepareBoundFixture (InputLabels)
          {put('MinV', 'InputLabels')}
          {set_at('U', '1', '-100.0')} {set_at('P', '0', '2')} {set_at('P', '1', '1')}
          {set_at('Used', '0', 'true')}
          (Utilities|Array|Clear {get('UsedColumns')})
          (Utilities|Array|Add {get('UsedColumns')} 0)
          {put('Width', get('Cols'))} {put('DummyCount', '0')} {put('Succeeded', 'true')}
          {put('ActiveRow', '2')} {put('J0', '1')} {put('Cursor', '0')}
          {put('NonpositiveV', 'true')} {put('SolverState', '4')})""")
        BP.compile_blueprint(child, warnings_as_errors=True)
    REFERENCES[key] = child.generated_class()
    return REFERENCES[key]


def snapshot(solver):
    result = {name: solver.get_editor_property(name) for name in (
        "Done", "Succeeded", "SolverState", "Cursor", "ActiveRow", "J0", "J1", "I0",
        "NonpositiveV", "FirstFreeColumn", "BestColumnFree", "LastStepWork",
    )}
    for name in ("Assignment", "P", "Way", "Used", "UsedColumns", "RowMinColumn"):
        result[name] = tuple(solver.get_editor_property(name))
    for name in ("U", "V", "MinV", "RowMinCost", "RowSecondMinCost"):
        result[name] = bits(solver.get_editor_property(name))
    for name in ("Cur", "Delta", "RowPotential", "RelaxationLowerBound"):
        result[name] = bits([solver.get_editor_property(name)])
    return result


def expected_seconds(scores, rows, columns):
    return [sorted(0.0 - value for value in scores[row * columns:(row + 1) * columns])[1]
            if columns > 1 else 1e20 for row in range(rows)]


def verify_cache(solver, scores, rows, columns):
    actual = list(solver.get_editor_property("RowSecondMinCost"))
    expected = expected_seconds(scores, rows, columns)
    assert bits(actual) == bits(expected), ("second minimum", rows, columns, scores, actual, expected)


def checked_advance(solver, method, limit):
    solver.call_method(method)
    work = int(solver.get_editor_property("LastStepWork"))
    assert 0 < work <= limit, (method, limit, work)
    return work


def initialize(solver, matrix, mask, limit):
    rows, columns = len(matrix), len(matrix[0]) if matrix else 0
    flat = [float(value) for row in matrix for value in row]
    solver.set_editor_property("StepWorkLimit", limit)
    solver.call_method("Initialize", args=(flat, rows, columns))
    solver.call_method("RestrictDummies", args=(mask,))
    assert not solver.get_editor_property("RelaxationBoundEnabled"), "Initialize retained the bound flag"
    assert solver.get_editor_property("RelaxationLowerBound") == 0.0, "Initialize retained the cached bound"
    return flat, rows, columns


def compare_solver(matrix, mask, limit):
    enabled = unreal.new_object(SOLVER_CLASS)
    disabled = unreal.new_object(reference_class(SOLVER_CLASS))
    for solver in (enabled, disabled):
        flat, rows, columns = initialize(solver, matrix, mask, limit)
    bound = rows * columns + rows * (rows + 1) * (3 * (rows + columns) + 10) + 4 * (rows + columns) + 20
    work = hits = 0
    for _ in range(bound + 1):
        if enabled.get_editor_property("Done"):
            break
        if enabled.get_editor_property("SolverState") == 5:
            if enabled.get_editor_property("RelaxationBoundEnabled"):
                assert enabled.get_editor_property("J0") != 0
                assert enabled.get_editor_property("NonpositiveV")
                start = enabled.get_editor_property("Cursor")
                end = min(enabled.get_editor_property("Width") + 1, start + limit)
                threshold = enabled.get_editor_property("RelaxationLowerBound")
                used = enabled.get_editor_property("Used")
                labels = enabled.get_editor_property("MinV")
                hits += sum(not used[j] and labels[j] <= threshold for j in range(start, end))
            disabled.call_method("SetBoundEnabled", args=(False,))
            assert not disabled.get_editor_property("RelaxationBoundEnabled")
        work += checked_advance(enabled, "Advance", limit)
        checked_advance(disabled, "Advance", limit)
        assert snapshot(enabled) == snapshot(disabled), (matrix, mask, limit, work)
        assert work <= bound
    assert enabled.get_editor_property("Done") and disabled.get_editor_property("Done")
    verify_cache(enabled, flat, rows, columns)
    disabled.call_method("SetBoundEnabled", args=(True,))
    initialize(disabled, [[-0.0]], [True], limit)
    while not disabled.get_editor_property("Done"):
        checked_advance(disabled, "Advance", limit)
    verify_cache(disabled, [-0.0], 1, 1)
    return hits


def verify_positive_bound():
    columns = 80
    matrix = [[100.0] + [1.0] * (columns - 1), [0.0] * columns]
    pair = [unreal.new_object(reference_class(SOLVER_CLASS)) for _ in range(2)]
    for solver in pair:
        flat, rows, _ = initialize(solver, matrix, [False, False], 1)
        while solver.get_editor_property("SolverState") == 0:
            checked_advance(solver, "Advance", 1)
        verify_cache(solver, flat, rows, columns)
        solver.call_method("PrepareBoundFixture", args=([0.0] + [99.0] * (columns + rows),))
        checked_advance(solver, "Advance", 1)
        assert solver.get_editor_property("SolverState") == 5
        assert solver.get_editor_property("RelaxationBoundEnabled")
        assert solver.get_editor_property("RowPotential") == -100.0
        assert solver.get_editor_property("RelaxationLowerBound") == 99.0, (
            "Used unique winner did not strengthen the bound from zero to99",
            solver.get_editor_property("RelaxationLowerBound"))
        solver.set_editor_property("StepWorkLimit", 64)
    work = 0
    while pair[0].get_editor_property("SolverState") == 5:
        pair[1].call_method("SetBoundEnabled", args=(False,))
        work += checked_advance(pair[0], "Advance", 64)
        checked_advance(pair[1], "Advance", 64)
        assert snapshot(pair[0]) == snapshot(pair[1]), "Positive-bound scan changed labels/ties"
    assert work == columns + 1, work
    assert pair[0].get_editor_property("J1") == 2
    assert pair[0].get_editor_property("Delta") == 99.0


def start_planner(cls, case, limit):
    planner = unreal.new_object(probe_class(cls))
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=(case["scores"], case["buildings"], case["minimum"],
        case["priorities"], case["workers"], case.get("strict", True)))
    for key, method in (("fixed", "RequireFixedSlots"), ("flexible", "RequireFlexibleMinimum")):
        if key in case:
            assert planner.call_method(method, args=(case[key],))[-1]
    if "reserve" in case:
        assert planner.call_method("KeepUnassigned", args=(case["reserve"], case["workers"], case["quality"]))[-1]
    return planner


def compare_planner(case, limit):
    pair = [start_planner(cls, case, limit) for cls in (PLANNER_CLASS, reference_class(PLANNER_CLASS))]
    passes = implicit_passes = dense_passes = 0
    seen_solver_pass = False
    for _ in range(100000):
        if pair[0].get_editor_property("PlanDone"):
            break
        if pair[0].get_editor_property("State") == 5 and not seen_solver_pass:
            seen_solver_pass = True
            passes += 1
            for planner in pair:
                implicit = planner.get_editor_property("ImplicitFirstPass")
                _, expected = expected_pass(planner, implicit)
                sources = {"implicit" if implicit else "PassScores":
                           read_scores(planner) if implicit else list(planner.get_editor_property("PassScores"))}
                if not implicit:
                    sources["Scores"] = list(planner.get_editor_property("Scores"))
                for source, actual_scores in sources.items():
                    if bits(actual_scores) != bits(expected):
                        differences = [dict(index=index, actual=actual, expected=wanted,
                                            actual_bits=bits([actual])[0].hex(), expected_bits=bits([wanted])[0].hex())
                                       for index, (actual, wanted) in enumerate(zip(actual_scores, expected))
                                       if bits([actual]) != bits([wanted])][:8]
                        diagnostic = dict(source=source, implicit=implicit, tier=planner.get_editor_property("Tier"),
                                          limit=limit, pass_number=passes, actual_length=len(actual_scores),
                                          expected_length=len(expected), first_differences=differences, case=case)
                        unreal.log_error("WO_BOUND_PASS_SCORE_DIAGNOSTIC " + repr(diagnostic))
                        raise AssertionError(diagnostic)
                verify_cache(planner, expected, planner.get_editor_property("SlotCount"),
                             planner.get_editor_property("SolveColumns"))
                if implicit:
                    assert not planner.get_editor_property("RelaxationBoundEnabled")
                    assert planner.get_editor_property("RelaxationLowerBound") == 0.0
            implicit_passes += bool(pair[0].get_editor_property("ImplicitFirstPass"))
            dense_passes += not pair[0].get_editor_property("ImplicitFirstPass")
        if pair[0].get_editor_property("State") != 5:
            seen_solver_pass = False
        pair[1].call_method("SetBoundEnabled", args=(False,))
        for planner in pair:
            checked_advance(planner, "AdvancePlan", limit)
        assert snapshot(pair[0]) == snapshot(pair[1]), ("planner solver state", case, limit, passes)
        for name in ("State", "PlanDone", "PlanSucceeded", "Tier"):
            assert pair[0].get_editor_property(name) == pair[1].get_editor_property(name), (name, case, limit)
    assert passes > 0 and implicit_passes > 0, (passes, implicit_passes)
    for planner in pair:
        assert planner.get_editor_property("PlanDone") and planner.get_editor_property("PlanSucceeded"), case
    for name in ("PlanAssignment", "ExpectedCounts"):
        assert list(pair[0].get_editor_property(name)) == list(pair[1].get_editor_property(name)), (name, case, limit)
    for name in ("ExpectedScores",):
        assert bits(pair[0].get_editor_property(name)) == bits(pair[1].get_editor_property(name)), (name, case, limit)
    assert bits([pair[0].get_editor_property("BuilderTotal")]) == bits([pair[1].get_editor_property("BuilderTotal")])
    return dense_passes


def verify_implicit_reset():
    planner = start_planner(reference_class(PLANNER_CLASS), CASES[0], 1)
    for _ in range(100000):
        if planner.get_editor_property("State") == 4:
            break
        assert not planner.get_editor_property("PlanDone")
        checked_advance(planner, "AdvancePlan", 1)
    else:
        raise AssertionError("Reset fixture did not reach implicit preparation")
    planner.call_method("SetBoundEnabled", args=(True,))
    assert planner.get_editor_property("RelaxationLowerBound") == 123.0
    for _ in range(100000):
        if planner.get_editor_property("State") == 5:
            break
        assert not planner.get_editor_property("PlanDone")
        checked_advance(planner, "AdvancePlan", 1)
    else:
        raise AssertionError("Reset fixture did not initialize implicit solver")
    assert planner.get_editor_property("ImplicitFirstPass")
    assert not planner.get_editor_property("RelaxationBoundEnabled"), "Implicit initializer retained a true certificate"
    assert planner.get_editor_property("RelaxationLowerBound") == 0.0, "Implicit initializer retained a stale numeric bound"


def run():
    missing = REQUIRED.difference(BP.list_variables(PRODUCTION))
    assert not missing, ("Solver lacks the second-minimum relaxation certificate", sorted(missing))
    verify_positive_bound()
    verify_implicit_reset()
    hits = 0
    for limit in (1, 3, 64):
        for matrix, mask in (([], []), ([[]], [True]), ([[7.0]], [False]),
                             ([[-0.0, 0.0], [1.03, 1.03]], [False, False]),
                             ([[100.0, 1.0, 1.0], [0.0, 0.0, 0.0]], [False, False])):
            hits += compare_solver(matrix, mask, limit)
    rng = random.Random(73921)
    values = [-1e20, -0.09, -0.0, 0.0, 0.02, 1.03, 7.0, 99999999999999.92, 200000000000000.06]
    for _ in range(100):
        rows, columns = rng.randrange(1, 7), rng.randrange(0, 7)
        hits += compare_solver([[rng.choice(values) for _ in range(columns)] for _ in range(rows)],
                               [rng.choice((False, True)) for _ in range(rows)], rng.choice((1, 3, 64)))
    dense_passes = 0
    for case in CASES:
        for limit in (1, 3, 64):
            dense_passes += compare_planner(case, limit)
    assert hits > 0 and dense_passes > 0, (hits, dense_passes)
    unreal.log(f"WO_SOLVER_RELAXATION_BOUND_TESTS_PASS: exact bound99 fixture, {hits} certified labels; "
               f"100 random solver comparisons, implicit and {dense_passes} dense planner passes, cache bits/reset/budgets")


if __name__ == "__main__":
    run()
