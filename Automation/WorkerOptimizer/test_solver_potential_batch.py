"""Compiled per-call equivalence for eager potential-update batching.

The legacy graph below is frozen from Modkit/Saved/WorkerOptimizer-
AdvancePotentials.dsl before the loop optimization. It is compiled only into an
unsaved test child. No current production helper constructs the reference.
"""

import math
import random
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from solver_label_upper_bound_dsl import UPPER_VARIABLES


LEGACY_DSL = r"""
(fn AdvancePotentials ()
  (if (== (Variables|Default|GetDelta) 0.0)
    (Variables|Default|SetLastStepWork 1)
    (if (and (Variables|Default|GetNativePlannerTrusted) (and (== (Variables|Default|GetDummyCount) 0) (== (Variables|Default|GetWidth) (Variables|Default|GetCols))))
      (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0)
        (Variables|Default|SetNativeFreeValid false)
        (Variables|Default|SetNativeMaskReady false)
        )
    )
    (Variables|Default|SetJ0 (Variables|Default|GetJ1)) (Variables|Default|SetSolverState (select (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0) 7 4)) (return))
  (Variables|Default|SetNativeMaskReady false)

  (if (and (< (Variables|Default|GetDelta) 0.0) (> (Utilities|Array|Length (Variables|Default|GetUsedColumns)) 1))
    (Variables|Default|SetNonpositiveV false))

  ; A final augmentation only consumes Way/P; the next row overwrites MinV.
  ; Used columns own distinct matched rows, including the active row at zero.
  (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0)
    (Variables|Default|SetNativeFreeValid false)
    (bind count (Utilities|Array|Length (Variables|Default|GetUsedColumns)))
    (bind remaining (+ (- count (Variables|Default|GetCursor)) 1))
    (Variables|Default|SetLastStepWork (select (< remaining (Variables|Default|GetStepWorkLimit)) remaining (Variables|Default|GetStepWorkLimit)))
    (for work (range (Variables|Default|GetLastStepWork))
      (if (< (Variables|Default|GetCursor) count)
        (bind j (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsedColumns) :"Dimension 1" (Variables|Default|GetCursor)))
        (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetU) :Index (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j) :Item (+ (Utilities|Array|Get(aref) :Array (Variables|Default|GetU) :"Dimension 1" (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j)) (Variables|Default|GetDelta)))
        (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetV) :Index j :Item (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetV) :"Dimension 1" j) (Variables|Default|GetDelta)))
        (Variables|Default|SetCursor (+ (Variables|Default|GetCursor) 1))
        (else (Variables|Default|SetJ0 (Variables|Default|GetJ1)) (Variables|Default|SetSolverState (select (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0) 7 4)))))
    (return))
  (Variables|Default|SetLastStepWork (select (< (+ (- (Variables|Default|GetWidth) (Variables|Default|GetCursor)) 2) (Variables|Default|GetStepWorkLimit)) (+ (- (Variables|Default|GetWidth) (Variables|Default|GetCursor)) 2) (Variables|Default|GetStepWorkLimit)))
  (if (and (Variables|Default|GetNativePlannerTrusted) (and (== (Variables|Default|GetDummyCount) 0) (== (Variables|Default|GetWidth) (Variables|Default|GetCols))))

      (if (== (Variables|Default|GetCursor) 0)
        (Variables|Default|SetNativeFreeValid false) (Variables|Default|SetNativeFreeColumn 0)
        (Variables|Default|SetNativeFreeMinimum 1e30))

    (for work (range (Variables|Default|GetLastStepWork))
      (if (<= (Variables|Default|GetCursor) (Variables|Default|GetWidth))
      (bind j (Variables|Default|GetCursor))
      (if (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsed) :"Dimension 1" j)
        (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetU) :Index (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j) :Item (+ (Utilities|Array|Get(aref) :Array (Variables|Default|GetU) :"Dimension 1" (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j)) (Variables|Default|GetDelta)))
        (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetV) :Index j :Item (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetV) :"Dimension 1" j) (Variables|Default|GetDelta)))
        (else
          (Variables|Default|SetNativeValue (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :"Dimension 1" j) (Variables|Default|GetDelta)))
          (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (Variables|Default|GetNativeValue))

      (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j) 0)
        (if (< (Variables|Default|GetNativeValue) (Variables|Default|GetNativeFreeMinimum))
          (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetNativeValue)) (Variables|Default|SetNativeFreeColumn j)
          (elif (== (Variables|Default|GetNativeValue) (Variables|Default|GetNativeFreeMinimum))
            (if (< j (Variables|Default|GetNativeFreeColumn))
              (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetNativeValue)) (Variables|Default|SetNativeFreeColumn j)))))
    ))
      (Variables|Default|SetCursor (+ (Variables|Default|GetCursor) 1))

        (else
      (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0)
        (Variables|Default|SetNativeFreeValid false)
        (Variables|Default|SetNativeMaskReady false)
        (else
      (Variables|Default|SetNativeFreeRow (Variables|Default|GetActiveRow))
      (Variables|Default|SetNativeFreeValid (> (Variables|Default|GetNativeFreeColumn) 0))
    ))
     (Variables|Default|SetJ0 (Variables|Default|GetJ1)) (Variables|Default|SetSolverState (select (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0) 7 4)))))
    (else
      (for work (range (Variables|Default|GetLastStepWork))
        (if (<= (Variables|Default|GetCursor) (Variables|Default|GetWidth))
  (bind j (Variables|Default|GetCursor))
  (if (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsed) :"Dimension 1" j)
    (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetU) :Index (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j) :Item (+ (Utilities|Array|Get(aref) :Array (Variables|Default|GetU) :"Dimension 1" (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" j)) (Variables|Default|GetDelta)))
    (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetV) :Index j :Item (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetV) :"Dimension 1" j) (Variables|Default|GetDelta)))
    (else (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :"Dimension 1" j) (Variables|Default|GetDelta)))))
  (Variables|Default|SetCursor (+ (Variables|Default|GetCursor) 1))

          (else (Variables|Default|SetJ0 (Variables|Default|GetJ1)) (Variables|Default|SetSolverState (select (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :"Dimension 1" (Variables|Default|GetJ1)) 0) 7 4))))))))
"""


def bits(value):
    return struct.pack("!d", float(value))


def encoded(value):
    if isinstance(value, float):
        return bits(value)
    if isinstance(value, (bool, int, str)):
        return value
    return tuple(encoded(item) for item in value)


def fixture_class():
    asset = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    child = BP.create("/Game/WorkerOptimizerEditorTests",
                      "BP_PotentialBatch_" + str(time.time_ns()), asset.generated_class())
    legacy = BP.add_function_graph(child, "LegacyAdvancePotentials")
    step = BP.add_function_graph(child, "StepLegacy")
    configure = BP.add_function_graph(child, "ConfigurePotentialTest")
    seed = BP.add_function_graph(child, "SeedPotentialTest")
    zeros = BP.add_function_graph(child, "SeedPotentialNegativeZero")
    cursor = BP.add_function_graph(child, "SeedPotentialCursor")
    stop = BP.add_function_graph(child, "StopPotentialTest")
    for name, kind, array in (
            ("Enabled", "bool", False), ("Offsets", "int", True), ("Columns", "int", True)):
        BP.add_function_param(configure, name, kind, True,
                              ContainerType.ARRAY if array else None)
    for name, kind, array in (
            ("Enabled", "bool", False), ("Dummies", "int", False),
            ("PValues", "int", True), ("UsedValues", "bool", True),
            ("Visited", "int", True), ("UValues", "float", True),
            ("VValues", "float", True), ("Labels", "float", True),
            ("InputDelta", "float", False), ("NextColumn", "int", False)):
        BP.add_function_param(seed, name, kind, True,
                              ContainerType.ARRAY if array else None)
    BP.add_function_param(zeros, "InputZero", "float", True)
    BP.add_function_param(zeros, "NegativeDelta", "bool", True)
    BP.add_function_param(cursor, "InputCursor", "int", True)
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(seed, "", [])

    def node(ending):
        matches = [value for value in nodes if value.endswith("|" + ending)]
        preferred = "Variables|Default|" + ending
        if ending in {"LegacyAdvancePotentials", "Advance"}:
            local = "CallFunction|" + ending
            if local in matches:
                return local
        result = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
        assert result, (ending, matches)
        return result

    def get(name):
        return f"({node('Get' + name)})"

    def put(name, value):
        return f"({node('Set' + name)} {value})"

    def set_at(name, index, value):
        return f"(Utilities|Array|SetArrayElem :TargetArray {get(name)} :Index {index} :Item {value})"

    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(legacy, LEGACY_DSL.replace(
            "(fn AdvancePotentials ()", "(fn LegacyAdvancePotentials ()", 1))
        BP.write_graph_dsl(step, f"""(fn StepLegacy ()
          {put('LastStepWork', '0')}
          (if {get('Done')} (return))
          (if (<= {get('StepWorkLimit')} 0)
            {put('Done', 'true')} {put('Succeeded', 'false')} (return))
          (if (== {get('SolverState')} 6)
            ({node('LegacyAdvancePotentials')})
            (else ({node('Advance')}))))""")
        BP.write_graph_dsl(configure, f"""(fn ConfigurePotentialTest (Enabled Offsets Columns)
          {put('NativePlannerTrusted', 'Enabled')} {put('NativeCsrReady', 'Enabled')}
          {put('NativeRowOffsets', 'Offsets')} {put('NativeColumns', 'Columns')})""")
        BP.write_graph_dsl(seed, f"""(fn SeedPotentialTest
            (Enabled Dummies PValues UsedValues Visited UValues VValues Labels InputDelta NextColumn)
          {put('Done', 'false')} {put('Succeeded', 'true')} {put('SolverState', '6')}
          {put('Cursor', '0')} {put('LastStepWork', '91')}
          {put('P', 'PValues')} {put('Used', 'UsedValues')} {put('UsedColumns', 'Visited')}
          {put('U', 'UValues')} {put('V', 'VValues')} {put('MinV', 'Labels')}
          {put('Rows', '(- (Utilities|Array|Length UValues) 1)')}
          {put('Width', '(- (Utilities|Array|Length PValues) 1)')}
          {put('Cols', f'(- {get("Width")} Dummies)')} {put('DummyCount', 'Dummies')}
          {put('NativePlannerTrusted', 'Enabled')}
          {put('NativeFreeValid', 'true')} {put('NativeFreeRow', '17')}
          {put('NativeFreeMinimum', '1e30')} {put('NativeFreeColumn', '0')}
          {put('NativeMaskReady', 'true')} {put('NativeMaskRow', '19')}
          {put('NativeValue', '37.5')} {put('Cur', '-71.25')}
          {put('ActiveRow', get('Rows'))} {put('J0', '0')}
          {put('J1', 'NextColumn')} {put('Delta', 'InputDelta')}
          {put('NonpositiveV', 'true')})""")
        BP.write_graph_dsl(zeros, f"""(fn SeedPotentialNegativeZero (InputZero NegativeDelta)
          {set_at('U', '0', '(* InputZero -1.0)')}
          {set_at('V', '0', '(* InputZero -1.0)')}
          {set_at('MinV', '0', '(* InputZero -1.0)')}
          {set_at('MinV', get('Width'), '(* InputZero -1.0)')}
          (if NegativeDelta {put('Delta', '(* InputZero -1.0)')}))""")
        BP.write_graph_dsl(cursor, f"""(fn SeedPotentialCursor (InputCursor)
          {put('Cursor', 'InputCursor')})""")
        BP.write_graph_dsl(stop, f"(fn StopPotentialTest () {put('Done', 'true')})")
        BP.compile_blueprint(child, warnings_as_errors=True)
    # New loop/certificate scratch fields have no values in the legacy graph.
    # Upper witnesses are separately checked by the production Upper test. The
    # frozen graph cannot maintain these newly declared private cache fields.
    # Every preexisting solver/cache/input field is compared, not only outputs.
    names = sorted(set(BP.list_variables(asset)) - {
        "PotentialEnd", "PotentialFreeFixedColumn", "PotentialLoopEnd", "PotentialDummySkip",
        "NativeDummyBound", "NativeDummyBoundReady", "NativeDummyBoundRow",
        "NativeDummyInitCount", "NativeUsedRealOnly",
    } - set(UPPER_VARIABLES))
    return child.generated_class(), names


def snapshot(obj, names):
    return {name: encoded(obj.get_editor_property(name)) for name in names}


def compare(actual, legacy, names, context):
    left, right = snapshot(actual, names), snapshot(legacy, names)
    differences = {name: (left[name], right[name]) for name in names if left[name] != right[name]}
    assert not differences, (context, differences)
    return left


def advance_pair(actual, legacy, names, limit, context):
    before = int(actual.get_editor_property("SolverState"))
    actual.call_method("Advance")
    legacy.call_method("StepLegacy")
    result = compare(actual, legacy, names, context)
    work = int(actual.get_editor_property("LastStepWork"))
    assert 0 < work <= limit, (context, work, limit)
    if before == 6:
        assert actual.get_editor_property("SolverState") in (4, 6, 7), context
    return result


def seed_pair(cls, names, width, native, terminal, delta, limit, dummies=0):
    rows = width // 2 + 2
    p = [rows] + [j // 2 if j % 2 == 0 else 0 for j in range(1, width + 1)]
    if width == 1 and not terminal:
        p[1] = 1
    next_column = 1 if terminal or width == 1 else 2
    visited = [0] + list(reversed(range(4, width + 1, 4)))
    used = [j in visited for j in range(width + 1)]
    values = [0.0, 0.125, -0.125, 1e14 + 0.02, 1e20, 1e30, 5e-324]
    u = [values[j % len(values)] for j in range(rows + 1)]
    v = [values[(j + 2) % len(values)] for j in range(width + 1)]
    # Repeated equal free minima catch tie handling as well as signed-zero bits.
    labels = [values[j % len(values)] if j % 2 == 0 else 3.0 for j in range(width + 1)]
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    for obj in pair:
        obj.set_editor_property("StepWorkLimit", limit)
        obj.call_method("SeedPotentialTest", args=(
            native, dummies, p, used, visited, u, v, labels, delta, next_column))
        obj.call_method("SeedPotentialNegativeZero", args=(0.0, math.copysign(1.0, delta) < 0 and delta == 0))
        assert bits(obj.get_editor_property("U")[0]) == bits(-0.0)
        assert bits(obj.get_editor_property("V")[0]) == bits(-0.0)
        assert bits(obj.get_editor_property("MinV")[width]) == bits(-0.0)
        if delta == 0 and math.copysign(1.0, delta) < 0:
            assert bits(obj.get_editor_property("Delta")) == bits(-0.0)
    compare(*pair, names, ("seed", width, native, terminal, delta, limit, dummies))
    return pair


def compare_seeded(cls, names):
    cases, calls = 0, 0
    for limit in (1, 3, 64):
        for width in (1, 2, 7, 65):
            for native in (False, True):
                for terminal in (False, True):
                    for delta in (0.0, -0.0, 0.125, -0.125, 1e14, math.nextafter(0.125, 1.0)):
                        actual, legacy = seed_pair(cls, names, width, native, terminal, delta, limit)
                        context = ("seeded", limit, width, native, terminal, delta)
                        expected_work = (1 if delta == 0 else
                                         len(actual.get_editor_property("UsedColumns")) + 1 if terminal else
                                         width + 2)
                        total = 0
                        while actual.get_editor_property("SolverState") == 6:
                            advance_pair(actual, legacy, names, limit, context)
                            total += actual.get_editor_property("LastStepWork")
                            calls += 1
                            assert total <= expected_work, (context, total, expected_work)
                        assert total == expected_work, (context, total, expected_work)
                        assert actual.get_editor_property("SolverState") == (7 if terminal else 4)
                        cases += 1
        # Start on the final cell and on the phase-exit item, including native
        # unavailability through universal dummies and terminal UsedColumns.
        for terminal in (False, True):
            for native, dummies in ((False, 0), (True, 0), (True, 1)):
                for at_exit in (False, True):
                    actual, legacy = seed_pair(cls, names, 7, native, terminal, 0.125, limit, dummies)
                    end = len(actual.get_editor_property("UsedColumns")) if terminal else 8
                    cursor = end if at_exit else end - 1
                    for obj in (actual, legacy):
                        obj.call_method("SeedPotentialCursor", args=(cursor,))
                    total = 0
                    while actual.get_editor_property("SolverState") == 6:
                        advance_pair(actual, legacy, names, limit, ("fence", terminal, native, dummies, cursor))
                        total += actual.get_editor_property("LastStepWork")
                        calls += 1
                    assert total == (1 if at_exit else 2)
                    cases += 1
    return cases, calls


def initialize_pair(pair, matrix, native, mask, limit, names):
    cols = len(matrix[0]) if matrix else 0
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(index for index, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    for obj in pair:
        obj.set_editor_property("StepWorkLimit", limit)
        obj.call_method("Initialize", args=([value for row in matrix for value in row], len(matrix), cols))
        obj.call_method("RestrictDummies", args=(mask,))
        assert not obj.get_editor_property("NativeFreeValid")
        assert not obj.get_editor_property("NativeMaskReady")
        obj.call_method("ConfigurePotentialTest", args=(native, offsets, columns))
    compare(*pair, names, ("initialize", matrix, native, mask, limit))


def compare_lifecycle(cls, names):
    rng = random.Random(902163)
    fixtures = [
        ([], []), ([[]], [True]), ([[0.0]], [False]),
        ([[10.0, 9.0, 0.0], [10.0, 8.0, 0.0], [10.0, 7.0, 0.0]], [False] * 3),
        ([[100000000000000.02, 100000000000000.06, -0.06, 200000000000000.0],
          [100000000000000.0, 200000000000000.1, 199999999999999.9, 199999999999999.9],
          [99999999999999.92, -0.03, 0.0, 100000000000000.06],
          [100000000000000.02, 0.07, 0.1, 0.09]], [False] * 4),
        ([[-1e20, -1.0, 0.0], [-1e20, -1.0, 0.0]], [True, True]),
    ]
    for _ in range(6):
        fixtures.append(([[rng.choice([-1e20, -2.0, 0.0, .125, 7.0]) for _ in range(7)]
                          for _ in range(5)], [False] * 5))
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    comparisons = 0
    for limit in (1, 3, 64):
        for native in (False, True):
            for matrix, mask in fixtures:
                initialize_pair(pair, matrix, native, mask, limit, names)
                work = 0
                while not pair[0].get_editor_property("Done"):
                    advance_pair(*pair, names, limit, ("lifecycle", limit, native, matrix, mask))
                    work += pair[0].get_editor_property("LastStepWork")
                    comparisons += 1
                    assert work < 100000

    for native in (False, True):
        for limit in (1, 3, 64):
            actual, legacy = seed_pair(cls, names, 65, native, False, .125, limit)
            advance_pair(actual, legacy, names, limit, ("pre-cancel", native, limit))
            assert actual.get_editor_property("SolverState") == 6
            for obj in (actual, legacy):
                obj.call_method("StopPotentialTest")
            before = compare(actual, legacy, names, ("cancel", native, limit))
            actual.call_method("Advance")
            legacy.call_method("StepLegacy")
            after = compare(actual, legacy, names, ("cancelled-advance", native, limit))
            assert actual.get_editor_property("LastStepWork") == 0
            assert {key: value for key, value in before.items() if key != "LastStepWork"} == {
                key: value for key, value in after.items() if key != "LastStepWork"}
            initialize_pair((actual, legacy), [[2.0, 1.0], [1.0, 2.0]], native, [False] * 2, limit, names)
            while not actual.get_editor_property("Done"):
                advance_pair(actual, legacy, names, limit, ("restart", native, limit))
            assert list(actual.get_editor_property("Assignment")) == [0, 1]
    return comparisons


def run():
    cls, names = fixture_class()
    cases, calls = compare_seeded(cls, names)
    lifecycle = compare_lifecycle(cls, names)
    unreal.log(f"WO_POTENTIAL_BATCH_TESTS_PASS seeded_cases={cases} phase_calls={calls} "
               f"lifecycle_calls={lifecycle}; bit-exact state/budgets/fences/cancel/reset")


run()
