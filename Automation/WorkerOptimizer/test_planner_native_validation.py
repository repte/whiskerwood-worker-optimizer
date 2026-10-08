"""Compiled native-row validation against the independent streaming oracle."""

import copy
import math
import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from benchmark_native_validation import ORACLE_FIELDS, encoded
from test_planner_validation_cache_model import oracle_cell


PLANNER = unreal.load_class(None, '/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C')
FIXTURE = None


def fixture_class():
    global FIXTURE
    if FIXTURE is None:
        bp = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_NativeValidationPlan_' + uuid.uuid4().hex, PLANNER)
        BP.add_variable(bp, 'SeedValue', 'float')
        BP.add_variable(bp, 'SeedNegativeOne', 'float')
        graph = BP.add_function_graph(bp, 'SeedValidationValue')
        for name, kind in (('InputIndex', 'int'), ('InputKind', 'int'), ('InputZero', 'float')):
            BP.add_function_param(graph, name, kind, True)
        BP.compile_blueprint(bp)
        available = BP.find_node_types(graph, '', [])

        def node(tail):
            matches = [value for value in available if value.lower().endswith('|' + tail.lower())]
            preferred = 'Variables|Default|' + tail
            result = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            assert result is not None, (tail, matches)
            return result

        g = lambda name: '(' + node('Get' + name) + ')'
        s = lambda name, value: '(' + node('Set' + name) + ' ' + value + ')'
        write = f'(Utilities|Array|SetArrayElem :TargetArray {g("BaseScores")} :Index InputIndex :Item {g("SeedValue")})'
        log = node('Loge')
        source = f'''(fn SeedValidationValue (InputIndex InputKind InputZero)
          {s('SeedNegativeOne', '-1.0')}
          (switch int InputKind
            (:0 {s('SeedValue', '(* InputZero -1.0)')} {write})
            (:1 {s('SeedValue', f'({log} :A {g("SeedNegativeOne")})')} {write})
            (:2 {s('SeedValue', f'(- 0.0 ({log} :A InputZero))')} {write})
            (:3 {s('SeedValue', f'({log} :A InputZero)')} {write})))'''
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, source)
            BP.compile_blueprint(bp, warnings_as_errors=True)
        FIXTURE = bp.generated_class()
    return FIXTURE


def start(scores, width, rows, pinned=False, seeds=(), planner=None):
    planner = unreal.new_object(fixture_class()) if planner is None else planner
    planner.set_editor_property('StepWorkLimit', 1)
    planner.call_method('StartPlan', args=(scores, list(range(rows)), [True] * rows, [2] * rows, width, True))
    fixed = [0] + [-1] * (rows - 1) if pinned else [-1] * rows
    configured = planner.call_method('RequireFixedSlots', args=(fixed,))
    assert configured[-1] if isinstance(configured, (tuple, list)) else configured
    for _ in range(10000):
        if planner.get_editor_property('State') == 0:
            break
        if planner.get_editor_property('PlanDone'):
            assert (width == 0 or rows == 0) and planner.get_editor_property('PlanSucceeded')
            before = snapshot(planner)
            planner.call_method('AdvancePlan')
            assert planner.get_editor_property('LastStepWork') == 0
            assert all(encoded(snapshot(planner)[name]) == encoded(value) for name, value in before.items())
            break
        assert not planner.get_editor_property('PlanDone'), 'Fixture failed before validation'
        planner.call_method('AdvancePlan')
    else:
        raise AssertionError('Missing validation phase')
    for index, kind in seeds:
        planner.call_method('SeedValidationValue', args=(index, kind, 0.0))
        value = planner.get_editor_property('BaseScores')[index]
        if kind == 0:
            assert encoded(value) == '8000000000000000', 'VM signed-zero fixture lost its sign'
        elif kind == 1:
            assert math.isnan(value)
        else:
            assert value == (math.inf if kind == 2 else -math.inf)
    return planner


def snapshot(planner):
    result = {}
    for name in ORACLE_FIELDS + ['BaseScores', 'ValidatedScore']:
        value = planner.get_editor_property(name)
        result[name] = list(value) if name.startswith('Row') or name in {'BaseScores', 'FixedSlots', 'FixedOwners'} else value
    return result


def verify(planner, budgets):
    expected = snapshot(planner)
    while not expected['PlanDone'] and expected['PlanValidationIndex'] < len(expected['BaseScores']):
        index = expected['PlanValidationIndex']
        oracle_cell(expected)
        expected['ValidatedScore'] = expected['BaseScores'][index]
    certified = []
    for call in range(100000):
        if planner.get_editor_property('State') != 0 or planner.get_editor_property('PlanDone'):
            break
        stage = planner.get_editor_property('NativeValidationStage')
        published = len(planner.get_editor_property('RowFirstScore'))
        limit = budgets[call % len(budgets)]
        planner.set_editor_property('StepWorkLimit', limit)
        planner.call_method('AdvancePlan')
        assert 0 < planner.get_editor_property('LastStepWork') <= limit
        new_rows = len(planner.get_editor_property('RowFirstScore'))
        for row in range(published, new_rows):
            values = expected['BaseScores'][row * expected['WorkerCount']:(row + 1) * expected['WorkerCount']]
            ordered = sorted(values, reverse=True)
            certified.append(stage == 3 and len(values) > 1 and ordered[0] > ordered[1] == ordered[-1])
    else:
        raise AssertionError('Native validation did not complete')
    actual = snapshot(planner)
    for name, value in expected.items():
        assert encoded(actual[name]) == encoded(value), (budgets, name, actual[name], value)
    assert list(planner.get_editor_property('RowSingleMaximum')) == certified
    if not expected['PlanDone']:
        assert planner.get_editor_property('State') == 19, 'Validation must yield before coverage preprocessing'
    return actual


def verify_activation():
    planner = start([1.0] * 240, 80, 3)
    planner.set_editor_property('StepWorkLimit', 64)
    planner.call_method('AdvancePlan')
    assert planner.get_editor_property('PlanValidationIndex') == 0, (
        'Native validation must gather the row before publishing per-cell statistics',
        planner.get_editor_property('PlanValidationIndex'))
    assert planner.get_editor_property('LastStepWork') == 64
    assert planner.get_editor_property('NativeValidationStage') == 1
    assert len(planner.get_editor_property('NativeValidationRow')) == 64
    planner.set_editor_property('StepWorkLimit', 1)
    planner.call_method('AdvancePlan')
    assert planner.get_editor_property('NativeValidationStage') == 1
    assert len(planner.get_editor_property('NativeValidationRow')) == 65
    verify(planner, (3, 1, 64))


def verify_restart_cancel():
    for interrupted, limit in ((1, 3), (1, 64), (2, 64), (3, 64)):
        planner = start([1.0, 9.0, 1.0, 1.0] * 3, 4, 3)
        planner.set_editor_property('StepWorkLimit', limit)
        for _ in range(interrupted):
            planner.call_method('AdvancePlan')
        planner.call_method('FailPlan')
        before = snapshot(planner)
        planner.call_method('AdvancePlan')
        assert planner.get_editor_property('LastStepWork') == 0
        assert all(encoded(snapshot(planner)[name]) == encoded(value) for name, value in before.items())
        start([1.0, 2.0, 3.0, 4.0], 2, 2, planner=planner)
        assert planner.get_editor_property('NativeValidationStage') == 0
        for name in ('NativeValidationRow', 'NativeValidationSorted', 'NativeValidationPrefix'):
            assert not list(planner.get_editor_property(name))
        assert not list(planner.get_editor_property('RowSingleMaximum'))
        verify(planner, (64, 1, 3))

    planner = start([1.0] * 12, 4, 3)
    planner.set_editor_property('StepWorkLimit', 64)
    planner.call_method('AdvancePlan')
    before = snapshot(planner)
    planner.set_editor_property('StepWorkLimit', 0)
    planner.call_method('AdvancePlan')
    assert planner.get_editor_property('PlanDone') and not planner.get_editor_property('PlanSucceeded')
    assert planner.get_editor_property('LastStepWork') == 0
    after = snapshot(planner)
    for name, value in before.items():
        if name not in ('PlanDone', 'PlanSucceeded'):
            assert encoded(after[name]) == encoded(value), ('invalid budget mutated validation', name)


def verify_midrow_activation_guard():
    planner = start([1.0, 2.0, 3.0, 4.0] * 3, 4, 3)
    planner.call_method('AdvancePlan')
    assert planner.get_editor_property('PlanValidationIndex') == 1
    assert planner.get_editor_property('NativeValidationStage') == 0
    verify(planner, (64,))
    assert not any(planner.get_editor_property('RowSingleMaximum'))


def verify_block_boundaries():
    checked = 0
    pool = [0.0, 1.03, math.nextafter(1.0, 2.0), 1e6, 1e6, 999999.9999999999]
    for width in (63, 64, 65, 127, 128, 129):
        for special in (None, 1, 2, 3, 'negative', 'large'):
            values = [pool[index % len(pool)] for index in range(width * 2)]
            seeds = ((0, 0),)
            if isinstance(special, int):
                seeds += ((width - 1, special),)
            elif special == 'negative':
                values[width - 1] = -1e20
            elif special == 'large':
                values[width - 1] = math.nextafter(1e6, math.inf)
            planner = start(values, width, 2, seeds=seeds)
            assert all(planner.get_editor_property(name) == 0 for name in
                       ('NativeValidationBlockCount', 'NativeValidationBlockEnd', 'NativeValidationBlockStart'))
            raw = list(planner.get_editor_property('BaseScores'))
            planner.set_editor_property('StepWorkLimit', 64)
            planner.call_method('AdvancePlan')
            count = min(64, width)
            assert planner.get_editor_property('LastStepWork') == count
            assert encoded(list(planner.get_editor_property('NativeValidationRow'))) == encoded(raw[:count])
            assert planner.get_editor_property('NativeValidationBlockCount') == count // 64
            verify(planner, (1, 3, 64))
            checked += 1
    return checked


verify_activation()
cases = [([], 0, 0, ()), ([], 0, 2, ()), ([1.0, 0.0, 1e6], 1, 3, ((1, 0),)),
         ([2.0, 2.0, 9.0, 1.0, 9.0, 3.0] * 2, 6, 2, ()),
         ([0.0] * 12, 4, 3, ((0, 0), (2, 0), (5, 0), (7, 0))),
         ([0.0, 0.0, 2.0, 1.0] * 3, 4, 3, ((0, 0), (5, 0))),
         ([1.0, -1.0, 0.0, 3.0] * 3, 4, 3, ((2, 0),)),
         ([1.0, math.nextafter(1.0, 2.0), 1.0, 1.0] * 3, 4, 3, ())]
for index in (0, 3, 7, 11):
    for kind in (1, 2, 3):
        cases.append(([1.0] * 12, 4, 3, ((index, kind),)))
    for value in (math.nextafter(-1e20, -math.inf), math.nextafter(1e6, math.inf)):
        values = [1.0] * 12
        values[index] = value
        cases.append((values, 4, 3, ()))
checks = 0
for values, width, rows, seeds in cases:
    for budgets in ((1,), (3,), (64,), (64, 1, 3)):
        verify(start(values, width, rows, seeds=seeds), budgets)
        checks += 1
for budgets in ((1,), (3,), (64,), (64, 1, 3)):
    for seeds in ((), ((1, 1),), ((1, 2),), ((1, 3),)):
        verify(start([1.0] * 12, 4, 3, pinned=True, seeds=seeds), budgets)
        checks += 1
verify_restart_cancel()
verify_midrow_activation_guard()
block_checks = verify_block_boundaries()
unreal.log(f'WO_PLANNER_NATIVE_VALIDATION_TESTS_PASS: {checks} exact end-state cases +{block_checks} block-boundary cases; sticky budgets64/1/3, fixed owners, VM signed-zero/NaN/Inf, bounds/fallback, single-maximum certificates, cancellation/restart')
