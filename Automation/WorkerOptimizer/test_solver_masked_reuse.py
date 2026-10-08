"""Compiled work regression for native mask reuse, with no new-field RED gate."""

import time
import struct

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from test_solver_cached_trace import benchmark_matrices


def fixture_class():
    asset = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_MaskReuse_" + str(time.time_ns()),
                      asset.generated_class())
    configure = BP.add_function_graph(child, "ConfigureMaskTest")
    for name, kind, array in (("Enabled", "bool", False), ("Offsets", "int", True),
                              ("Columns", "int", True)):
        if array:
            BP.add_function_param(configure, name, kind, True, ContainerType.ARRAY)
        else:
            BP.add_function_param(configure, name, kind, True)
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(configure, "", [])

    def put(name, value):
        matches = [node for node in nodes if node.endswith("|Set" + name)]
        preferred = "Variables|Default|Set" + name
        chosen = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
        assert chosen, (name, matches)
        return f"({chosen} {value})"

    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(configure, f"""(fn ConfigureMaskTest (Enabled Offsets Columns)
          {put('NativePlannerTrusted', 'Enabled')} {put('NativeCsrReady', 'Enabled')}
          {put('NativeRowOffsets', 'Offsets')} {put('NativeColumns', 'Columns')})""")
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


def solve(obj, matrix, enabled, limit):
    get = obj.get_editor_property
    rows, cols = len(matrix), len(matrix[0])
    obj.set_editor_property("StepWorkLimit", limit)
    obj.call_method("Initialize", args=([value for row in matrix for value in row], rows, cols))
    obj.call_method("RestrictDummies", args=([False] * rows,))
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, value in enumerate(row) if value != -1e20)
        offsets.append(len(columns))
    obj.call_method("ConfigureMaskTest", args=(enabled, offsets, columns))
    masks, copies, work = 0, 0, 0
    while not get("Done"):
        native, phase = get("SolverState") == 11, get("NativePhase")
        obj.call_method("Advance")
        amount = get("LastStepWork")
        assert 0 < amount <= limit
        masks += amount if native and phase == 3 else 0
        copies += int(native and phase == 2)
        work += amount
        assert work < 1000000
    pack = lambda values: tuple(struct.pack("!d", float(value)) for value in values)
    result = {name: list(get(name)) for name in ("Assignment", "P", "Way")}
    result.update({name: pack(get(name)) for name in ("U", "V", "MinV")})
    result.update(Succeeded=bool(get("Succeeded")), Cur=pack([get("Cur")]))
    return result, masks, copies


cls = fixture_class()
obj = unreal.new_object(cls)
matrix = benchmark_matrices(40)[0]
counts = []
for limit in (1, 3, 64):
    reference, _, _ = solve(obj, matrix, False, limit)
    actual, masks, copies = solve(obj, matrix, True, limit)
    assert actual == reference, (limit, [name for name in actual if actual[name] != reference[name]])
    assert masks <= 16, ("Zero-delta native scans repeatedly rebuilt Used masks", limit, masks, copies)
    assert copies <= 4, ("Zero-delta native scans repeatedly copied labels", limit, copies)
    assert not obj.get_editor_property("NativeMaskReady"), "Terminal matching must invalidate mask reuse"
    obj.call_method("Initialize", args=([1.0], 1, 1))
    assert not obj.get_editor_property("NativeMaskReady")
    counts.append((limit, masks, copies))
unreal.log(f"WO_NATIVE_MASK_REUSE_TESTS_PASS budgets/masks/copies={counts}; bit-exact reference and reset")
