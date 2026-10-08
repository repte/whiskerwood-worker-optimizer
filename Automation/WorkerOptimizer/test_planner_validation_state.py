"""Compiled per-cell validation state bits, including pre-mask rejection."""

import uuid

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

from test_planner_validation_cache_model import encoded, oracle_cell


PLANNER = unreal.load_class(None, '/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C')
assert PLANNER
FIXTURE_CLASS = None
FIELDS = ('BaseScores WorkerCount FixedConfigured FixedSlots FixedOwners ScanRow ScanWorker '
          'PlanValidationIndex MaxScore PlanDone PlanSucceeded StatsOffset StatsEnd StatsFirstColumn '
          'StatsMaximumColumn StatsFirstScore StatsMaximumScore StatsPrefixScore StatsSecondScore '
          'StatsAllReal StatsUniformScore RowAllReal RowUniformScore RowFirstColumn RowMaximumColumn '
          'RowFirstScore RowMaximumScore RowPrefixScore RowSecondScore').split()
ARRAYS = {name for name in FIELDS if name.startswith('Row') or name in {'BaseScores', 'FixedSlots', 'FixedOwners'}}


def fixture_class():
    global FIXTURE_CLASS
    if FIXTURE_CLASS is None:
        child = BP.create('/Game/WorkerOptimizerEditorTests', 'BP_ValidationState_' + uuid.uuid4().hex, PLANNER)
        graph = BP.add_function_graph(child, 'SeedNegativeZero')
        BP.add_function_param(graph, 'InputZero', 'float', True)
        BP.add_function_param(graph, 'InputIndex', 'int', True)
        BP.compile_blueprint(child)
        matches = [name for name in BP.find_node_types(graph, 'GetBaseScores', [])
                   if name.endswith('|GetBaseScores')]
        preferred = 'Variables|Default|GetBaseScores'
        getter = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
        assert getter is not None, matches
        with toolset_registry.tool_raising_exceptions():
            BP.write_graph_dsl(graph, f'''(fn SeedNegativeZero (InputZero InputIndex)
              (Utilities|Array|SetArrayElem :TargetArray ({getter}) :Index InputIndex
                :Item (* InputZero -1.0)))''')
            BP.compile_blueprint(child, warnings_as_errors=True)
        FIXTURE_CLASS = child.generated_class()
    return FIXTURE_CLASS


def snapshot(planner):
    return {name: list(planner.get_editor_property(name)) if name in ARRAYS else planner.get_editor_property(name)
            for name in FIELDS}


def verify(values, fixed):
    planner = unreal.new_object(fixture_class())
    planner.call_method('StartPlan', args=(values, [0, 1], [True, True], [2, 2], 3, True))
    if fixed:
        assert planner.call_method('RequireFixedSlots', args=([0, -1],))
    planner.set_editor_property('StepWorkLimit', 1)
    for _ in range(1000):
        if planner.get_editor_property('State') == 0:
            break
        assert not planner.get_editor_property('PlanDone'), 'Fixture failed before score validation'
        planner.call_method('AdvancePlan')
    else:
        raise AssertionError('Fixture did not reach score validation')
    # Python array conversion can normalize -0.0; create it in the VM instead.
    negative_indices = [index for index, value in enumerate(values) if encoded(value) == encoded(-0.0)]
    for index in negative_indices:
        planner.call_method('SeedNegativeZero', args=(0.0, index))
    seeded = list(planner.get_editor_property('BaseScores'))
    for index in negative_indices:
        assert encoded(seeded[index]) == encoded(-0.0), ('VM seed lost negative zero', index, seeded[index])
    expected = snapshot(planner)
    cells = 0
    while expected['PlanValidationIndex'] < len(values) and not expected['PlanDone']:
        oracle_cell(expected)
        planner.call_method('AdvancePlan')
        actual = snapshot(planner)
        assert planner.get_editor_property('LastStepWork') == 1
        for name in FIELDS:
            assert encoded(actual[name]) == encoded(expected[name]), (name, values, fixed, cells, actual[name], expected[name])
        cells += 1
    return cells


cells = 0
for values in ([0.0, -0.0, 0.0, -0.0, 0.0, -0.0],
               [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
               [1.0, 3.0, 2.0, 2.0, 3.0, 1.0],
               [0.0, -1.0, -1e20, -0.0, 1e6, 1e6],
               [0.01, 0.0101, 0.01, 1.03, 1.03, 0.0]):
    for fixed in (False, True):
        cells += verify(values, fixed)
for invalid in (float('nan'), float('inf'), -float('inf'), -1.01e20, 1000000.1):
    # Column1 is masked on fixed row0, but raw invalid input must still fail.
    cells += verify([1.0, invalid, 3.0, 4.0, 5.0, 6.0], True)
unreal.log(f'WO_PLANNER_VALIDATION_STATE_TESTS_PASS: {cells} compiled per-cell states, VM-seeded signed zero, all statistic/flag bits, fixed owners and pre-mask invalid rejection')
