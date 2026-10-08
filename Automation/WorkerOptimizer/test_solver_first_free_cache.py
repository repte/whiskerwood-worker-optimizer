"""Compiled per-batch reference for the earliest-free potential certificate."""

import ast
from pathlib import Path
import time

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def legacy_helpers():
    path = Path(__file__).with_name("test_solver_potential_batch.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Reuse its frozen independent reference without executing its test runner.
    tree.body = [item for item in tree.body if not (
        isinstance(item, ast.Expr) and isinstance(item.value, ast.Call)
        and isinstance(item.value.func, ast.Name) and item.value.func.id == "run")]
    env = {"__file__": str(path)}
    exec(compile(tree, str(path), "exec"), env)
    return env


def fixture_class(legacy):
    parent, names = legacy["fixture_class"]()
    child = BP.create("/Game/WorkerOptimizerEditorTests", "BP_FirstFreeCache_" + str(time.time_ns()), parent)
    graph = BP.add_function_graph(child, "SeedFreeCache")
    for name, kind in (("First", "int"), ("Winner", "int"), ("Minimum", "float"),
                       ("Valid", "bool"), ("SameRow", "bool"), ("NegativeZero", "bool")):
        BP.add_function_param(graph, name, kind, True)
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(graph, "", [])

    def node(ending):
        matches = [name for name in nodes if name.endswith("|" + ending)]
        preferred = "Variables|Default|" + ending
        assert preferred in matches or len(matches) == 1, (ending, matches)
        return preferred if preferred in matches else matches[0]

    get = lambda name: f"({node('Get' + name)})"
    put = lambda name, value: f"({node('Set' + name)} {value})"
    source = f"""(fn SeedFreeCache (First Winner Minimum Valid SameRow NegativeZero)
      {put('FirstFreeColumn', 'First')} {put('NativeFreeColumn', 'Winner')}
      {put('NativeFreeMinimum', 'Minimum')} {put('NativeFreeValid', 'Valid')}
      {put('NativeFreeRow', f'(select SameRow {get("ActiveRow")} (+ {get("ActiveRow")} 1))')}
      (if NegativeZero
        {put('NativeFreeMinimum', '(* Minimum -1.0)')}
        (Utilities|Array|SetArrayElem :TargetArray {get('MinV')} :Index First :Item {get('NativeFreeMinimum')})))"""
    with toolset_registry.tool_raising_exceptions():
        BP.write_graph_dsl(graph, source)
        BP.compile_blueprint(child, warnings_as_errors=True)
    source_fields = BP.list_variables(unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver"))
    return child.generated_class(), [name for name in names if name != "PotentialFreeFixedColumn"], source_fields


def seed(cls, width, first, variant, native, delta, limit):
    free = list(range(first, width + 1))
    occupied = [column for column in range(1, width + 1) if column not in free]
    if first == 1:
        occupied = list(range(2, width + 1, 2))
        free = [column for column in range(1, width + 1) if column not in occupied]
    rows = len(occupied) + 1
    p = [rows] + [0] * width
    for row, column in enumerate(occupied, 1):
        p[column] = row
    next_column = occupied[0]
    visited = [0] + [column for column in occupied if column != next_column and column % 3 == 0]
    used = [column in visited for column in range(width + 1)]
    labels = [1e14 + column * 0.125 if column in occupied else 0.125 for column in range(width + 1)]
    if variant == "later_minimum":
        labels[free[-1]] = -0.125
    if variant == "negative_zero":
        for column in free:
            labels[column] = 0.0
    winner = min(free, key=labels.__getitem__)
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    for obj in pair:
        obj.set_editor_property("StepWorkLimit", limit)
        obj.call_method("SeedPotentialTest", args=(native, 0, p, used, visited,
                        [0.125 * row for row in range(rows + 1)],
                        [-0.125 * column for column in range(width + 1)], labels, delta, next_column))
        obj.call_method("SeedFreeCache", args=(first, winner, labels[winner],
                        variant != "invalid", variant != "wrong_row", variant == "negative_zero"))
    return pair, native and delta != 0.0 and winner == first and variant not in ("invalid", "wrong_row")


def run():
    legacy = legacy_helpers()
    cls, names, all_names = fixture_class(legacy)
    present = "PotentialFreeFixedColumn" in all_names
    comparisons = phases = activated = 0
    for limit in (1, 3, 64):
        for width, first in ((9, 1), (65, 17), (65, 65)):
            for variant in ("valid", "later_minimum", "invalid", "wrong_row", "negative_zero"):
                for native in (False, True):
                    for delta in (0.0, 0.125, -1e14, -5e-324):
                        pair, expected = seed(cls, width, first, variant, native, delta, limit)
                        context = (limit, width, first, variant, native, delta)
                        legacy["compare"](*pair, names, ("seed", context))
                        total = 0
                        while pair[0].get_editor_property("SolverState") == 6:
                            legacy["advance_pair"](*pair, names, limit, context)
                            work = pair[0].get_editor_property("LastStepWork")
                            total += work
                            assert total <= width + 2
                            comparisons += 1
                            if total == work and present:
                                certificate = pair[0].get_editor_property("PotentialFreeFixedColumn")
                                assert bool(certificate) == expected, (context, certificate, expected)
                                activated += bool(certificate)
                        assert total == (1 if delta == 0.0 else width + 2)
                        phases += 1
    unreal.log(f"WO_FIRST_FREE_CACHE_EXACTNESS_PASS phases={phases} calls={comparisons}")
    assert present and activated > 0, "Earliest-free potential certificate is not integrated"
    # Covers generic/private-dummy fallback, cancellation and object reuse.
    seeded = legacy["compare_seeded"](cls, names)
    lifecycle = legacy["compare_lifecycle"](cls, names)
    unreal.log(f"WO_FIRST_FREE_CACHE_TESTS_PASS activated={activated} legacy_seeded={seeded} lifecycle={lifecycle}")


run()
