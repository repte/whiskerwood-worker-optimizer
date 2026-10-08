"""Compiled exactness/work regression for certified later-pass CSR prefixes."""

import random
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from test_solver_cached_trace import benchmark_matrices
from test_solver_row_order_model import reserve_matrix


def bits(values):
    return tuple(struct.pack("!d", float(value)) for value in values)


def fixture_class():
    parent = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_PrefixSkip_" + str(time.time_ns()),
                      parent.generated_class())
    configure = BP.add_function_graph(child, "ConfigurePrefixTest")
    BP.add_function_param(configure, "Hint", "int", True)
    for name in ("Offsets", "Columns"):
        BP.add_function_param(configure, name, "int", True, ContainerType.ARRAY)
    seed = BP.add_function_graph(child, "SeedPrefixTie")
    stop = BP.add_function_graph(child, "StopPrefixTest")
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(configure, "", [])

    def node(name):
        matches = [value for value in nodes if value.endswith("|" + name)]
        preferred = "Variables|Default|" + name
        assert preferred in matches or len(matches) == 1, (name, matches)
        return preferred if preferred in matches else matches[0]

    def get(name):
        return f"({node('Get' + name)})"

    def put(name, value):
        return f"({node('Set' + name)} {value})"

    def set_at(name, index, value):
        return f"(Utilities|Array|SetArrayElem :TargetArray {get(name)} :Index {index} :Item {value})"

    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(configure, f"""(fn ConfigurePrefixTest (Hint Offsets Columns)
          {put('NativePlannerTrusted', 'true')} {put('NativeCsrReady', 'true')}
          {put('NativeRowOffsets', 'Offsets')} {put('NativeColumns', 'Columns')}
          {put('ImplicitWorkerCount', 'Hint')})""")
        # Python/editor array setters normalize -0. Seed it inside the VM.
        BP.write_graph_dsl(seed, f"""(fn SeedPrefixTie ()
          (for j (range 9)
            {set_at('P', 'j', '0')} {set_at('V', 'j', '0.0')}
            {set_at('Used', 'j', 'false')} {set_at('MinV', 'j', '7.0')}
            {set_at('Way', 'j', '7')})
          {set_at('U', '0', '0.0')} {set_at('U', '1', '0.0')} {set_at('U', '2', '0.0')}
          {set_at('P', '0', '2')} {set_at('P', '1', '1')}
          {set_at('Used', '0', 'true')} {set_at('Used', '1', 'true')}
          (Utilities|Array|Clear {get('UsedColumns')})
          (Utilities|Array|Add {get('UsedColumns')} 0)
          (Utilities|Array|Add {get('UsedColumns')} 1)
          (for j (range 5) {set_at('MinV', 'j', '0.0')})
          {put('NativeFreeMinimum', '0.0')}
          {put('Cur', f'(* {get("NativeFreeMinimum")} -1.0)')}
          {set_at('MinV', '2', get('Cur'))} {set_at('MinV', '4', get('Cur'))}
          {set_at('MinV', '5', '5.0')}
          {put('NativeFreeMinimum', get('Cur'))} {put('NativeFreeColumn', '2')}
          {put('NativeFreeRow', '2')} {put('NativeFreeValid', 'true')}
          {put('NativeMaskReady', 'false')} {put('NativePhase', '0')}
          {put('ActiveRow', '2')} {put('I0', '1')} {put('J0', '1')} {put('J1', '0')}
          {put('RowScoreOffset', '-1')} {put('RowPotential', '0.0')}
          {put('RelaxationBoundEnabled', 'true')} {put('RelaxationLowerBound', '0.0')}
          {put('NonpositiveV', 'true')} {put('Delta', '1e30')}
          {put('BestColumnFree', 'false')} {put('Done', 'false')}
          {put('SolverState', '11')})""")
        BP.write_graph_dsl(stop, f"(fn StopPrefixTest () {put('Done', 'true')})")
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


def csr(matrix):
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, score in enumerate(row) if score != -1e20)
        offsets.append(len(columns))
    return offsets, columns


def snapshot(obj):
    get = obj.get_editor_property
    result = {name: tuple(get(name)) for name in
              ("Assignment", "P", "Way", "Used", "UsedColumns", "RowMinColumn")}
    result.update({name: bits(get(name)) for name in
                   ("U", "V", "MinV", "RowMinCost", "RowSecondMinCost")})
    result.update({name: bits([get(name)]) for name in
                   ("Cur", "Delta", "RowPotential", "RelaxationLowerBound")})
    result.update({name: get(name) for name in
                   ("Done", "Succeeded", "J0", "J1", "I0", "ActiveRow", "BestColumnFree")})
    return result


def initialize(obj, matrix, hint, limit, private_dummies=False):
    obj.set_editor_property("StepWorkLimit", limit)
    obj.call_method("Initialize", args=([value for row in matrix for value in row],
                                        len(matrix), len(matrix[0])))
    assert not obj.get_editor_property("NativePlannerTrusted")
    assert not obj.get_editor_property("NativeCsrReady")
    obj.call_method("RestrictDummies", args=([private_dummies] * len(matrix),))
    obj.call_method("ConfigurePrefixTest", args=(hint, *csr(matrix)))


def advance(obj, limit, native_only=False):
    get = obj.get_editor_property
    work = csr_work = calls = 0
    while not get("Done") and (not native_only or get("SolverState") == 11):
        scan = get("SolverState") == 11 and get("NativePhase") == 1
        obj.call_method("Advance")
        amount = int(get("LastStepWork"))
        assert 0 < amount <= limit, (limit, amount, get("SolverState"))
        work += amount
        csr_work += amount if scan else 0
        calls += 1
        assert work < 1000000, (work, get("SolverState"))
    return snapshot(obj), csr_work, calls


def solve(obj, matrix, hint, limit, private_dummies=False):
    initialize(obj, matrix, hint, limit, private_dummies)
    return advance(obj, limit)


def same(reference, actual, context):
    assert actual == reference, (context, [name for name in reference if reference[name] != actual[name]])


def run():
    cls = fixture_class()
    obj = unreal.new_object(cls)
    gates = []
    # The later tied reserve pass has a full retained real prefix and explicit
    # dummy suffix. Both paths are the production solver; Hint=0 disables only
    # the proposed prefix certificate, not native relaxation or other bounds.
    size = 40
    first, quality, coverage, bonus = benchmark_matrices(size)
    for row in first[:size]:
        row[:size] = [max(row[:size])] * size
    solve(obj, first, 0, 64)
    dual = {name: list(obj.get_editor_property(name.upper())) for name in ("u", "v")}
    matrix, _ = reserve_matrix(first, dual, size, quality, coverage, bonus)
    for limit in (1, 3, 64):
        reference, baseline, _ = solve(obj, matrix, 0, limit)
        actual, optimized, _ = solve(obj, matrix, size, limit)
        same(reference, actual, ("tied reserve", limit))
        assert actual["Succeeded"]
        gates.append(("tied reserve", limit, baseline, optimized, size * (size - 5)))

    # Real labels include both zero signs; a legal dummy outside the skipped
    # prefix must still improve. Its existing label exceeds the prefix bound.
    tie = [[0.0] * 5 + [-1e20] * 3 for _ in range(2)]
    for limit in (1, 3, 64):
        outputs = []
        for hint in (0, 4):
            solve(obj, tie, hint, limit)
            obj.call_method("SeedPrefixTie")
            assert bits(obj.get_editor_property("MinV"))[2] == bits([-0.0])[0]
            actual, work, _ = advance(obj, limit, native_only=True)
            assert obj.get_editor_property("SolverState") == 6
            assert actual["J1"] == 2 and actual["Delta"] == bits([-0.0])
            assert actual["MinV"][5] == bits([0.0])[0] and actual["Way"][5] == 1
            outputs.append((actual, work))
        same(outputs[0][0], outputs[1][0], ("signed zero and dummy suffix", limit))
        gates.append(("signed zero and dummy suffix", limit, outputs[0][1], outputs[1][1], 4))

    # Bounded but semantically stale hints remain safe; incomplete prefixes and
    # out-of-range hints must not authorize skipping. Reuse also checks reset.
    rng = random.Random(20261008)
    values = [-1e20, -1.0, -0.0, 0.0, 0.125, 1.03, 7.0,
              199999999999999.97, 200000000000000.06]
    comparisons = 0
    for limit in (1, 3, 64):
        for _ in range(16):
            rows, cols = rng.randint(1, 5), rng.randint(6, 9)
            matrix = [[rng.choice(values) for _ in range(cols)] for _ in range(rows)]
            reference, _, _ = solve(obj, matrix, 0, limit)
            for hint in (-1, cols + 1, rng.randint(1, cols)):
                actual, _, _ = solve(obj, matrix, hint, limit)
                same(reference, actual, ("fallback/hint", limit, hint, matrix))
                comparisons += 1
        reference, _, _ = solve(obj, tie, 0, limit, private_dummies=True)
        actual, work, _ = solve(obj, tie, 4, limit, private_dummies=True)
        same(reference, actual, ("private dummies", limit))
        assert work == 0

    solve(obj, tie, 4, 3)
    obj.call_method("SeedPrefixTie")
    obj.call_method("StopPrefixTest")
    before = snapshot(obj)
    obj.call_method("Advance")
    same(before, snapshot(obj), "cancel before native prefix")
    assert obj.get_editor_property("LastStepWork") == 0
    unreal.log(f"WO_NATIVE_PREFIX_EXACTNESS_PASS comparisons={comparisons}; signed zero, dummy suffix, reset, budgets, cancel")
    # All behavior checks precede the intentional old-asset work failure.
    for name, limit, baseline, optimized, saved in gates:
        assert baseline - optimized >= saved, (
            "Certified complete CSR prefix still visits unchanged labels", name,
            limit, baseline, optimized, "required saving", saved)
    unreal.log(f"WO_NATIVE_PREFIX_SKIP_TESTS_PASS work={gates}")


run()
