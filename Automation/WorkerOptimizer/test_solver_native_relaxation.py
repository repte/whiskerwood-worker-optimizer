"""Compiled RED draft for the currently unwired native-relaxation candidate."""

import random
import struct
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType


def bits(value):
    return struct.pack("!d", value)


def probe_class():
    asset = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    required = {"NativePlannerTrusted", "NativeCsrReady", "NativeFreeValid", "NativePhase",
                "NativeRowOffsets", "NativeColumns"}
    assert required <= set(BP.list_variables(asset)), "Native relaxation candidate is not integrated"
    assert "AdvanceNativeRelaxation" in {str(g.get_name()) for g in BP.list_graphs(asset)}
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_NativeSolverTest_" + str(time.time_ns()),
                      asset.generated_class())
    configure = BP.add_function_graph(child, "ConfigureNative")
    BP.add_function_param(configure, "Enabled", "bool", True)
    BP.add_function_param(configure, "Offsets", "int", True, ContainerType.ARRAY)
    BP.add_function_param(configure, "Columns", "int", True, ContainerType.ARRAY)
    stop = BP.add_function_graph(child, "StopNativeTest")
    BP.compile_blueprint(child)
    available = BP.find_node_types(configure, "", [])

    def set_value(name, value):
        endings = [n for n in available if n.endswith("|Set" + name)]
        preferred = "Variables|Default|Set" + name
        chosen = preferred if preferred in endings else endings[0] if len(endings) == 1 else None
        assert chosen, (name, endings)
        return f"({chosen} {value})"

    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(configure, f"""(fn ConfigureNative (Enabled Offsets Columns)
          {set_value('NativePlannerTrusted', 'Enabled')} {set_value('NativeCsrReady', 'Enabled')}
          {set_value('NativeRowOffsets', 'Offsets')} {set_value('NativeColumns', 'Columns')})""")
        BP.write_graph_dsl(stop, f"(fn StopNativeTest () {set_value('Done', 'true')})")
        BP.compile_blueprint(child, warnings_as_errors=True)
    return child.generated_class()


def make_csr(matrix):
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(j for j, score in enumerate(row) if score != -1e20)
        offsets.append(len(columns))
    return offsets, columns


def solve(cls, matrix, enabled, limit, mask=None, reuse=None):
    obj = reuse or unreal.new_object(cls)
    rows, cols = len(matrix), len(matrix[0])
    obj.set_editor_property("StepWorkLimit", limit)
    obj.call_method("Initialize", args=([value for row in matrix for value in row], rows, cols))
    assert not obj.get_editor_property("NativePlannerTrusted")
    assert not obj.get_editor_property("NativeCsrReady")
    assert not obj.get_editor_property("NativeFreeValid")
    obj.call_method("RestrictDummies", args=(mask if mask is not None else [False] * rows,))
    obj.call_method("ConfigureNative", args=(enabled, *make_csr(matrix)))
    work, native, phases = 0, False, set()
    while not obj.get_editor_property("Done"):
        if obj.get_editor_property("SolverState") == 11:
            native = True
            phases.add(int(obj.get_editor_property("NativePhase")))
        obj.call_method("Advance")
        units = int(obj.get_editor_property("LastStepWork"))
        assert 0 < units <= limit
        work += units
        assert work <= 1000000, (rows, cols, work)
    result = {
        "Assignment": list(obj.get_editor_property("Assignment")),
        "Succeeded": bool(obj.get_editor_property("Succeeded")),
        "P": list(obj.get_editor_property("P")), "Way": list(obj.get_editor_property("Way")),
        **{name: [bits(value) for value in obj.get_editor_property(name)] for name in ("U", "V", "MinV")},
        "Cur": bits(obj.get_editor_property("Cur")),
    }
    return obj, result, native, phases


def run():
    cls = probe_class()
    matrices = [
        [[10.0, 9.0, 0.0], [10.0, 8.0, 0.0], [10.0, 7.0, 0.0]],
        [[-1e20, -1.0, 0.0], [-1e20, -1.0, -0.0]],
        [[199999999999999.97, -0.09, 99999999999999.92, 200000000000000.06],
         [-0.05, 200000000000000.06, 200000000000000.1, -0.05],
         [0.02, -0.05, -0.01, -0.06],
         [99999999999999.98, 99999999999999.98, 100000000000000.08, 199999999999999.97]],
        [[100000000000000.02, 100000000000000.06, -0.06, 200000000000000.0],
         [100000000000000.0, 200000000000000.1, 199999999999999.9, 199999999999999.9],
         [99999999999999.92, -0.03, 0.0, 100000000000000.06],
         [100000000000000.02, 0.07, 0.1, 0.09]],
    ]
    rng = random.Random(783901)
    for _ in range(60):
        rows, cols = rng.randint(1, 6), rng.randint(6, 9)
        matrices.append([[rng.choice([-1e20, -1.0, -0.0, 0.0, .125, 1.03, 7.0])
                          for _ in range(cols)] for _ in range(rows)])
    native_hits, phases, reused = 0, set(), None
    for limit in (1, 3, 64):
        for matrix in matrices:
            _, reference, _, _ = solve(cls, matrix, False, limit)
            reused, actual, hit, seen = solve(cls, matrix, True, limit, reuse=reused)
            assert actual == reference, (limit, matrix, [name for name in reference if actual[name] != reference[name]])
            native_hits += hit
            phases.update(seen)
    assert native_hits and phases >= set(range(6)), (native_hits, phases)
    for enabled in (False, True):
        _, result, hit, _ = solve(cls, matrices[0], enabled, 3, mask=[True] * 3)
        assert not hit, "Universal dummy columns must retain the generic path"
        if not enabled:
            reference = result
        else:
            assert result == reference
    # Cancellation is observed before each native phase, not only before solving.
    matrix = matrices[0]
    for phase in range(6):
        reused.call_method("Initialize", args=([v for row in matrix for v in row], 3, 3))
        reused.call_method("RestrictDummies", args=([False] * 3,))
        reused.call_method("ConfigureNative", args=(True, *make_csr(matrix)))
        while not reused.get_editor_property("Done"):
            if reused.get_editor_property("SolverState") == 11 and reused.get_editor_property("NativePhase") == phase:
                break
            reused.call_method("Advance")
        assert not reused.get_editor_property("Done"), ("missing cancellation phase", phase)
        reused.call_method("StopNativeTest")
        before = {name: list(reused.get_editor_property(name)) for name in ("P", "U", "V", "MinV")}
        reused.call_method("Advance")
        assert reused.get_editor_property("LastStepWork") == 0
        assert all(list(reused.get_editor_property(name)) == value for name, value in before.items())
    unreal.log(f"WO_NATIVE_SOLVER_TESTS_PASS comparisons={3*len(matrices)} native_hits={native_hits} phases={sorted(phases)}")


run()
