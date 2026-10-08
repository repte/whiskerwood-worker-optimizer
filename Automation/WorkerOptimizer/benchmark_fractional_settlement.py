"""Separate paired compiled planner benchmark with genuinely fractional inputs.

This does not alter the six accepted large-settlement fixtures. Both runs use
the same unsaved planner subclass and differ only in the private integer U/V
and MinV flags, set after each initializer and before its first solver action.
"""

import hashlib
import json
import math
from pathlib import Path
import struct
import time
import uuid


PLANNER_PATH = '/Game/Mods/WorkerOptimizer/BP_StaffingPlanner.BP_StaffingPlanner_C'
FIXTURE = None
CONFIGURE = 'ConfigureFractionalBenchmarkFastPaths'
MEMBER_TYPES = {
    'PlanDone': 'bool', 'Done': 'bool', 'State': 'int', 'SolverState': 'int',
    'Cursor': 'int', 'ActiveRow': 'int', 'UsedColumns': 'int[]',
    'IntegerUActive': 'bool', 'IntegerMinActive': 'bool',
    'IntegerUFlushMode': 'int', 'IntegerMinFlushCursor': 'int',
    'IntegerUEnabled': 'bool', 'IntegerMinEnabled': 'bool',
}


def configure_source(node):
    g = lambda name: '(' + node('Get' + name) + ')'
    s = lambda name, value: '(' + node('Set' + name) + ' ' + value + ')'
    return f'''(fn ConfigureFractionalBenchmarkFastPaths (Enabled)
      (if (or {g('PlanDone')} {g('Done')}) (return false))
      (if (or (!= {g('State')} 5) (!= {g('SolverState')} 1)) (return false))
      (if (or (!= {g('Cursor')} 0) (!= {g('ActiveRow')} 1)) (return false))
      (if (!= (Utilities|Array|Length {g('UsedColumns')}) 0) (return false))
      (if (or {g('IntegerUActive')} {g('IntegerMinActive')}) (return false))
      (if (or (!= {g('IntegerUFlushMode')} 0) (!= {g('IntegerMinFlushCursor')} 0)) (return false))
      {s('IntegerUEnabled', 'Enabled')} {s('IntegerMinEnabled', 'Enabled')}
      (return true))'''


def fixture_class(writer=None):
    global FIXTURE
    if FIXTURE is None:
        import unreal
        import toolset_registry
        from editor_toolset.toolsets.blueprint import BlueprintTools as BP
        from editor_toolset.toolsets import blueprint_dsl

        parent = unreal.load_class(None, PLANNER_PATH)
        assert parent is not None, PLANNER_PATH
        bp = BP.create('/Game/WorkerOptimizerEditorTests',
                       'BP_FractionalSettlement_' + uuid.uuid4().hex, parent)
        graph = BP.add_function_graph(bp, CONFIGURE)
        BP.add_function_param(graph, 'Enabled', 'bool', True)
        BP.add_function_param(graph, 'Applied', 'bool', False)
        BP.compile_blueprint(bp)
        library = unreal.BlueprintEditorLibrary
        owners = {}
        current = parent
        while current is not None:
            found = library.get_blueprint_for_class(current)
            values = found if isinstance(found, (tuple, list)) else [found]
            declaring_bp = next((value for value in values if isinstance(value, unreal.Blueprint)), None)
            if declaring_bp is None:
                break
            own_names = set(map(str, library.list_member_variable_names(declaring_bp, False)))
            for name, kind in MEMBER_TYPES.items():
                if name not in own_names or name in owners:
                    continue
                # Verify the live reflected member and its declared type before
                # bypassing the action menu for inherited Blueprint properties.
                unreal.get_default_object(current).get_editor_property(name)
                actual = library.get_member_variable_type(declaring_bp, name)
                assert actual is not None, ('Missing reflected member type', name)
                expected = library.get_basic_type_by_name(unreal.Name(kind.removesuffix('[]')))
                if kind.endswith('[]'):
                    expected = library.get_array_type(expected)
                actual_schema = json.loads(library.pin_type_to_json_schema(actual, current))
                expected_schema = json.loads(library.pin_type_to_json_schema(expected, current))
                assert actual_schema == expected_schema, ('Unexpected member type', name, actual_schema, expected_schema)
                owners[name] = current.get_path_name()
            current = library.get_blueprint_parent_class(declaring_bp)
        assert set(owners) == set(MEMBER_TYPES), ('Missing inherited benchmark members', sorted(set(MEMBER_TYPES) - set(owners)))
        member_nodes, missing_actions = {}, []

        def node(tail):
            operation, name = tail[:3], tail[3:]
            assert operation in ('Get', 'Set') and name in owners, tail
            matches = [value for value in BP.find_node_types(graph, tail, [])
                       if value.startswith('Variables|') and value.lower().endswith('|' + tail.lower())]
            preferred = 'Variables|Default|' + tail
            result = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
            if result is None:
                assert not matches, ('Ambiguous inherited member action', tail, matches)
                result = preferred
                missing_actions.append(tail)
            member_nodes[result] = (operation, name, owners[name])
            return result

        source = configure_source(node)
        with toolset_registry.tool_raising_exceptions():
            if missing_actions:
                editor = unreal.BlueprintGraphEditor.get_graph_editor(graph)

                def create_node(target_graph, type_id, pos, declaring_class=None):
                    member = member_nodes.get(type_id)
                    if member is None or declaring_class is not None:
                        return BP.create_node(target_graph, type_id, pos, declaring_class)
                    assert target_graph == graph
                    operation, name, declaring_path = member
                    create = editor.add_get_member_variable_node if operation == 'Get' else editor.add_set_member_variable_node
                    # Resolve through this Blueprint's skeleton to retain self context.
                    created = create(unreal.Name(name))
                    assert isinstance(created, unreal.EdGraphNode), ('Direct inherited member creation failed', type_id, declaring_path)
                    created.set_node_pos(pos)
                    return created

                # Local callbacks only; neither BlueprintTools nor its caches
                # are patched, and the guard's emitted DSL remains unchanged.
                blueprint_dsl.Transpiler(
                    graph, create_node, BP.connect_pins, BP._get_node_info, BP.set_pin_value,
                    lambda target: BP.find_nodes(target), delete_node_fn=BP.delete_node,
                    find_node_types_fn=lambda value: BP.find_node_types(graph, value),
                ).transpile(source)
                unreal.log('WO_FRACTIONAL_DIRECT_MEMBERS ' + json.dumps(sorted(set(missing_actions))))
            else:
                (writer or BP.write_graph_dsl)(graph, source)
            BP.compile_blueprint(bp, warnings_as_errors=True)
        FIXTURE = bp.generated_class()
    return FIXTURE


def succeeded(value):
    return bool(value[-1] if isinstance(value, (tuple, list)) else value)


def float_bytes(values):
    return b''.join(struct.pack('>d', float(value)) for value in values)


def integer_bytes(values):
    return b''.join(struct.pack('>q', int(value)) for value in values)


def solver_snapshot(planner):
    fields = {}
    for name in ('U', 'V', 'MinV'):
        fields[name] = float_bytes(planner.get_editor_property(name))
    for name in ('P', 'Way', 'Assignment'):
        fields[name] = integer_bytes(planner.get_editor_property(name))
    fields['CurDelta'] = float_bytes([planner.get_editor_property(name) for name in ('Cur', 'Delta')])
    fields['ShapeSelection'] = integer_bytes([
        planner.get_editor_property(name) for name in ('Rows', 'Cols', 'Width', 'J1')])
    return fields


def fixture_data(size):
    assert isinstance(size, int) and size >= 6 and size % 2 == 0
    quality = [0.0] * size
    for row in range(size):
        quality[(row + 17) % size] = float(10000 + row if row % 2 == 0 else row // 2 + 1) + 0.125
    scores = [100.125 if worker == (row + 17) % size else 10.125
              for row in range(size) for worker in range(size)]
    return scores, quality


def run_fixture(size=1500, enabled=False, writer=None, timeout_seconds=300.0):
    import unreal

    scores, quality = fixture_data(size)
    reserve = 3
    priorities = [2] * (size // 2)
    planner = unreal.new_object(fixture_class(writer))
    planner.set_editor_property('StepWorkLimit', 64)
    stages = {}
    compiled_seconds = advance_seconds = 0.0
    calls = work = 0
    hooks, solver_states = [], []

    def timed_call(method, args, stage):
        nonlocal compiled_seconds
        before = time.perf_counter()
        result = planner.call_method(method, args=args)
        elapsed = time.perf_counter() - before
        compiled_seconds += elapsed
        item = stages.setdefault(stage, {'calls': 0, 'seconds': 0.0, 'work': 0, 'max_seconds': 0.0})
        item['calls'] += 1
        item['seconds'] += elapsed
        item['max_seconds'] = max(item['max_seconds'], elapsed)
        return result, elapsed, item

    started = time.perf_counter()
    timed_call('StartPlan', (scores, [r // 2 for r in range(size)],
                            [r % 2 == 0 for r in range(size)], priorities, size, True), 'setup:StartPlan')
    configured, _, _ = timed_call('RequireFixedSlots', ([-1] * size,), 'setup:RequireFixedSlots')
    assert succeeded(configured), 'Unfixed real-pipeline configuration failed'
    configured, _, _ = timed_call('KeepUnassigned', (reserve, size, quality), 'setup:KeepUnassigned')
    assert succeeded(configured), 'Reserve configuration failed'
    in_solver = captured_solver = False
    next_progress = started + 15.0
    while not planner.get_editor_property('PlanDone'):
        state = int(planner.get_editor_property('State'))
        solver_state = int(planner.get_editor_property('SolverState')) if state == 5 else -1
        if state == 5 and not in_solver:
            # BatchBuildPass breaks immediately after State=5; AdvancePlan's
            # state4 arm returns, so this hook precedes every solver action.
            assert not planner.get_editor_property('Done')
            applied, _, _ = timed_call(CONFIGURE, (enabled,), 'setup:IntegerFlags')
            assert succeeded(applied), 'Pass boundary was not an untouched initialized solver'
            assert bool(planner.get_editor_property('IntegerUEnabled')) is enabled
            assert bool(planner.get_editor_property('IntegerMinEnabled')) is enabled
            hooks.append({'pass': len(hooks) + 1, 'solver_state': solver_state,
                          'implicit': bool(planner.get_editor_property('ImplicitFirstPass')),
                          'integer_u_v': enabled, 'integer_minv': enabled})
            in_solver, captured_solver = True, False
        if state == 5 and planner.get_editor_property('Done') and not captured_solver:
            assert planner.get_editor_property('Succeeded'), 'Solver pass failed'
            solver_states.append(solver_snapshot(planner))
            captured_solver = True
        if state != 5:
            in_solver = False
        key = f'planner:{state}/solver:{solver_state}'
        _, elapsed, stage = timed_call('AdvancePlan', (), key)
        units = int(planner.get_editor_property('LastStepWork'))
        assert 0 < units <= 64, (key, units)
        stage['work'] += units
        work += units
        calls += 1
        advance_seconds += elapsed
        now = time.perf_counter()
        if now >= next_progress:
            unreal.log(f'WO_FRACTIONAL_PROGRESS enabled={enabled} workers={size} calls={calls} work={work} state={key} seconds={now-started:.2f}')
            next_progress = now + 15.0
        assert now - started <= timeout_seconds, ('Fractional planner timeout', enabled, key, calls, work)

    assert planner.get_editor_property('PlanSucceeded')
    assert len(hooks) == len(solver_states) >= 2, ('Expected productive and reserve solves', hooks)
    assignment = list(planner.get_editor_property('PlanAssignment'))
    assert len(assignment) == size
    chosen = [worker for worker in assignment if worker >= 0]
    assert len(chosen) == len(set(chosen)) == size - reserve
    assert all(worker < size for worker in chosen)
    assert all(assignment[row] == (row + 17) % size for row in range(size) if assignment[row] >= 0)
    assert all(assignment[row] >= 0 for row in range(0, size, 2))
    counts, score_totals, coverage = [0] * 5, [0.0] * 5, [0] * 5
    for building, tier in enumerate(priorities):
        occupied = [row for row in (2 * building, 2 * building + 1) if assignment[row] >= 0]
        counts[tier] += len(occupied)
        coverage[tier] += bool(occupied)
        score_totals[tier] += sum(scores[row * size + assignment[row]] for row in occupied)
    idle = set(range(size)) - set(chosen)
    builder = float(planner.get_editor_property('BuilderTotal'))
    assert builder == sum(quality[worker] for worker in idle)
    expected_builder = sum(sorted(quality[(row + 17) % size] for row in range(1, size, 2))[-reserve:])
    expected = {'coverage': [0, 0, size // 2, 0, 0], 'counts': [0, 0, size - reserve, 0, 0],
                'quality': [0.0, 0.0, 100.125 * (size - reserve), 0.0, 0.0], 'builder': expected_builder}
    objective = {'coverage': coverage, 'counts': counts, 'quality': score_totals, 'builder': builder}
    assert objective == expected, (objective, expected)
    objective_bits = float_bytes(score_totals + [builder]).hex()
    host_seconds = time.perf_counter() - started
    result = {'label': 'fractional_unique_varied_reserve_integer_on' if enabled else 'fractional_unique_varied_reserve_integer_off',
              'workers': size, 'rows': size, 'buildings': size // 2, 'reserve': reserve,
              'strict': True, 'uniform_priority': True, 'fixed_slots_configured': True,
              'preferred_score': 100.125, 'background_score': 10.125, 'builder_fraction': 0.125,
              'integer_u_v_enabled': enabled, 'integer_minv_enabled': enabled,
              'host_seconds': host_seconds, 'compiled_call_sum_seconds': compiled_seconds,
              'advance_call_sum_seconds': advance_seconds,
              'setup_call_sum_seconds': compiled_seconds - advance_seconds,
              'under_5_seconds_host': host_seconds < 5.0, 'under_5_seconds_compiled': compiled_seconds < 5.0,
              'calls': calls, 'work': work, 'stages': stages, 'pass_hooks': hooks,
              'objective': objective, 'expected_objective': expected, 'objective_float_bits': objective_bits,
              'assignment_sha256': hashlib.sha256(json.dumps(assignment).encode('ascii')).hexdigest(),
              'solver_pass_sha256': [{name: hashlib.sha256(value).hexdigest() for name, value in state.items()}
                                     for state in solver_states]}
    assert all(math.isfinite(result[name]) for name in ('host_seconds', 'compiled_call_sum_seconds'))
    unreal.log('WO_FRACTIONAL_RESULT ' + json.dumps({key: value for key, value in result.items() if key != 'stages'}))
    return result, assignment, solver_states


def run(size=1500, output_path=None, writer=None, candidate_first=False):
    import unreal

    fixture_class(writer)
    runs = {}
    for enabled in ((True, False) if candidate_first else (False, True)):
        runs[enabled] = run_fixture(size, enabled, writer)
    baseline, baseline_assignment, baseline_solver = runs[False]
    candidate, candidate_assignment, candidate_solver = runs[True]
    assert candidate_assignment == baseline_assignment, 'Fractional assignment differs from eager integer-disabled reference'
    for name in ('assignment_sha256', 'objective', 'objective_float_bits'):
        assert candidate[name] == baseline[name], ('Fractional paired output mismatch', name)
    assert len(candidate_solver) == len(baseline_solver)
    for index, (expected, actual) in enumerate(zip(baseline_solver, candidate_solver)):
        assert expected.keys() == actual.keys()
        for name in expected:
            assert actual[name] == expected[name], ('Fractional solver pass bit mismatch', index, name)
    report = {'fixture': 'EXTRA_fractional_unique_varied_reserve', 'accepted_six_fixtures_modified': False,
              'timing_scope': 'Host starts before StartPlan; compiled sum includes StartPlan, RequireFixedSlots, KeepUnassigned, per-pass flag setter and AdvancePlan. Fixture authoring/input construction are excluded.',
              'comparison': 'Current compiled planner, identical native paths; only private integer U/V and MinV flags differ.',
              'candidate_first': candidate_first, 'paired_assignment_objective_and_solver_bits_equal': True,
              'fractional_host_target_met': candidate['under_5_seconds_host'],
              'fractional_compiled_target_met': candidate['under_5_seconds_compiled'],
              'baseline': baseline, 'candidate': candidate}
    destination = Path(output_path) if output_path is not None else Path(
        unreal.Paths.project_saved_dir(), 'WorkerOptimizer-Fractional1500Benchmark.json')
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    unreal.log('WO_FRACTIONAL_BENCHMARK_PASS ' + str(destination))
    if not report['fractional_host_target_met']:
        unreal.log('WO_FRACTIONAL_PERFORMANCE_TARGET_NOT_MET ' + str(candidate['host_seconds']))
    return report


if __name__ == '__main__':
    run()
