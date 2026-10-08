"""The implicit first pass is bit-equivalent to the independently built dense pass."""

import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from test_planner_fused_matrix import CASES, PLANNER_CLASS, bits, expected_pass
from planner_test_cost_probe import probe_class, read_scores, supports_implicit


REFERENCE_CLASS = None


def reference_class():
    global REFERENCE_CLASS
    if REFERENCE_CLASS is None:
        fixture = BP.create("/Game/WorkerOptimizerEditorTests",
                            "BP_DensePassReference_" + uuid.uuid4().hex, probe_class(PLANNER_CLASS))
        graph = BP.add_function_graph(fixture, "InstallDenseReference")
        BP.add_function_param(graph, "InputScores", "float", True, ContainerType.ARRAY)
        BP.add_function_param(graph, "InputMask", "bool", True, ContainerType.ARRAY)
        BP.compile_blueprint(fixture)

        def node(ending):
            matches = [value for value in BP.find_node_types(graph, ending, [])
                       if value.endswith("|" + ending)]
            preferred = "Variables|Default|" + ending
            if preferred not in matches and "CallFunction|" + ending in matches:
                preferred = "CallFunction|" + ending
            assert preferred in matches or len(matches) == 1, (ending, matches)
            return preferred if preferred in matches else matches[0]

        def get(name):
            return "(" + node("Get" + name) + ")"

        def put(name, value):
            return "(" + node("Set" + name) + " " + value + ")"

        source = f"""(fn InstallDenseReference (InputScores InputMask)
          {put('PassScores', 'InputScores')} {put('AllowedEdges', 'InputMask')}
          ({node('Initialize')} :IncomingScores InputScores :RowCount {get('SlotCount')} :ColumnCount {get('SolveColumns')})
          ({node('RestrictDummies')} :Mask {get('AllowedEmpty')})
          {put('FirstPass', 'false')} {put('State', '5')})"""
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            if supports_implicit(PLANNER_CLASS):
                corrupt = BP.add_function_graph(fixture, "CorruptImplicitInput")
                BP.add_function_param(corrupt, "InputIndex", "int", True)
                BP.compile_blueprint(fixture)
                arrays = ("ImplicitScores", "ImplicitModes", "ImplicitMultipliers",
                          "ImplicitMinimumRows", "ImplicitRealRows", "ImplicitDummyRows",
                          "ImplicitFixedWorkers", "ImplicitDummyStarts", "ImplicitDummyEnds")
                source = "(fn CorruptImplicitInput (InputIndex) " + " ".join(
                    f"(if (== InputIndex {index}) (Utilities|Array|Clear {get(name)}))"
                    for index, name in enumerate(arrays)) + ")"
                BP.write_graph_dsl(corrupt, source)
            BP.compile_blueprint(fixture, warnings_as_errors=True)
        REFERENCE_CLASS = fixture.generated_class()
    return REFERENCE_CLASS


def start(cls, case, limit):
    planner = unreal.new_object(cls)
    planner.set_editor_property("StepWorkLimit", limit)
    planner.call_method("StartPlan", args=(case["scores"], case["buildings"],
        case["minimum"], case["priorities"], case["workers"], case.get("strict", True)))
    if "fixed" in case:
        assert planner.call_method("RequireFixedSlots", args=(case["fixed"],))[-1]
    if "flexible" in case:
        assert planner.call_method("RequireFlexibleMinimum", args=(case["flexible"],))[-1]
    if "reserve" in case:
        assert planner.call_method("KeepUnassigned", args=(
            case["reserve"], case["workers"], case["quality"]))[-1]
    return planner


def reach(planner, predicate, method="AdvancePlan"):
    for _ in range(100000):
        if predicate(planner):
            return
        assert not planner.get_editor_property("PlanDone"), "Planner ended before target phase"
        planner.call_method(method)
        work = planner.get_editor_property("LastStepWork")
        assert 0 < work <= planner.get_editor_property("StepWorkLimit"), work
    raise AssertionError("Planner did not reach target phase")


def verify_case(case, limit, require_implicit=True):
    actual = start(probe_class(PLANNER_CLASS), case, limit)
    reference = start(reference_class(), case, limit)
    for planner in (actual, reference):
        reach(planner, lambda item: item.get_editor_property("State") == 4)
        if "bonuses" in case:
            planner.call_method("SeedTestBonuses", args=tuple(case["bonuses"]))
    mask, scores = expected_pass(reference, True)
    assert expected_pass(actual, True) == (mask, scores)
    reference.call_method("InstallDenseReference", args=(scores, mask))
    reach(actual, lambda item: item.get_editor_property("State") == 5)
    if require_implicit:
        assert not list(actual.get_editor_property("PassScores")), "First pass still materializes the dense score matrix"
        assert not list(actual.get_editor_property("AllowedEdges")), "First pass still materializes the dense edge mask"
        assert actual.get_editor_property("ImplicitFirstPass")
        assert not reference.get_editor_property("ImplicitFirstPass"), "Generic initialization retained implicit mode"
        assert bits(read_scores(actual)) == bits(scores), ("implicit score bits", case, limit)
        if "uncertified_row" in case:
            assert actual.get_editor_property("RowMinColumn")[case["uncertified_row"]] == 0, (
                "Rounding-ambiguous earliest winner must use the exact scan", case, limit)
    for planner in (actual, reference):
        reach(planner, lambda item: item.get_editor_property("Done"), "Advance")
        assert planner.get_editor_property("Succeeded"), case
    for name in ("Assignment", "P"):
        assert list(actual.get_editor_property(name)) == list(reference.get_editor_property(name)), (name, case, limit)
    for name in ("U", "V"):
        assert bits(actual.get_editor_property(name)) == bits(reference.get_editor_property(name)), (name, case, limit)
    for planner in (actual, reference):
        reach(planner, lambda item: item.get_editor_property("PlanDone"))
        assert planner.get_editor_property("PlanSucceeded"), case
    for name in ("PlanAssignment", "ExpectedCounts"):
        assert list(actual.get_editor_property(name)) == list(reference.get_editor_property(name)), (name, case, limit)
    for name in ("ExpectedScores",):
        assert bits(actual.get_editor_property(name)) == bits(reference.get_editor_property(name)), (name, case, limit)
    assert bits([actual.get_editor_property("BuilderTotal")]) == bits([reference.get_editor_property("BuilderTotal")])


def run(require_implicit=True):
    cases = CASES + [
        dict(workers=3, buildings=[0, 0, 1], minimum=[True, False, True], priorities=[2, 2],
             scores=[0.0, 0.01, 0.0101, 1000000., -1e20, 0., 0.0001, 0.0002, 0.0003]),
        dict(workers=4, buildings=[0, 0, 1, 1], minimum=[True, False, True, False], priorities=[2, 2],
             scores=[-0.0] * 16, reserve=1, quality=[0.0, 1.0, 3.0, 2.0]),
    ]
    if require_implicit:
        cases.append(dict(workers=3, buildings=[0, 0, 1], minimum=[True, False, True],
                          priorities=[2, 2], bonuses=[5005001002.0, 5015011004004.0, 6000000000000000.0],
                          uncertified_row=0,
                          scores=[0.0, 0.01, 0.0101, 1000000., -1e20, 0., 0.0001, 0.0002, 0.0003]))
    for case in cases:
        for limit in (1, 3, 64):
            verify_case(case, limit, require_implicit)
    if require_implicit:
        verify_initializer_boundaries()
    unreal.log("WO_PLANNER_IMPLICIT_PASS_TESTS_PASS: dense reference Assignment/P/U/V bits and complete plans, fixed/flexible/reserve/weighted/rounded ties, limits1/3/64")


def verify_initializer_boundaries():
    for index in range(9):
        planner = start(reference_class(), CASES[0], 64)
        reach(planner, lambda item: item.get_editor_property("State") == 5)
        planner.call_method("CorruptImplicitInput", args=(index,))
        planner.call_method("InitializeImplicitFirstPass", args=(
            planner.get_editor_property("SlotCount"), planner.get_editor_property("SolveColumns")))
        assert planner.get_editor_property("Done") and not planner.get_editor_property("Succeeded"), index
        assert not planner.get_editor_property("ImplicitFirstPass"), index
        planner.call_method("Initialize", args=([2.0], 1, 1))
        assert not planner.get_editor_property("ImplicitFirstPass")
        reach(planner, lambda item: item.get_editor_property("Done"), "Advance")
        assert planner.get_editor_property("Succeeded")
        assert list(planner.get_editor_property("Assignment")) == [0]
    for rows, columns in ((-1, 2), (2, -1), (10001, 2), (2, 10001), (2, 2)):
        planner = unreal.new_object(PLANNER_CLASS)
        planner.call_method("InitializeImplicitFirstPass", args=(rows, columns))
        assert planner.get_editor_property("Done") and not planner.get_editor_property("Succeeded"), (rows, columns)


if __name__ == "__main__":
    run()
