"""Offline exact first-pass score and conservative row-cache design checks."""

import ast
import math
import os
import random
import struct
from pathlib import Path

from planner_cost_dsl import accumulate_row_statistics, first_pass_row_minimum, first_pass_score
from test_solver_relaxation import Relaxation


def parser():
    path = Path(os.environ.get("WO_BLUEPRINT_DSL_PATH", r"D:\WWEngine\Engine\Plugins\Experimental\Toolsets\EditorToolset\Content\Python\editor_toolset\toolsets\blueprint_dsl.py"))
    env = {}
    for item in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name in {"Symbol", "_source_line", "tokenize", "parse"}:
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
    return env["parse"], env["Symbol"]


def get(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def emitted():
    parse, symbol = parser()
    source = first_pass_score(
        get, put, output="Score", base_output="Base", base=get("IncomingBase"),
        worker=get("Worker"), workers=get("Workers"), mode=get("Mode"),
        multiplier=get("Multiplier"), minimum=get("Minimum"), fixed=get("Fixed"),
        real_allowed=get("RealAllowed"), dummy_allowed=get("DummyAllowed"),
        dummy_start=get("DummyStart"), dummy_end=get("DummyEnd"),
        fill=get("Fill"), coverage=get("Coverage"), column=get("Column"))
    statistics = accumulate_row_statistics(
        get, put, value=get("IncomingBase"), column=get("StatsColumn"),
        first_column="FirstColumn", first_score="FirstScore", maximum_column="MaximumColumn",
        maximum_score="MaximumScore", prefix_score="PrefixScore")
    minimum = first_pass_row_minimum(
        get, put, score_output="MinimumScore", column_output="MinimumColumn", scratch_output="Scratch",
        first_column=get("FirstColumn"), first_score=get("FirstScore"),
        maximum_column=get("MaximumColumn"), maximum_score=get("MaximumScore"), prefix_score=get("PrefixScore"),
        mode=get("Mode"), multiplier=get("Multiplier"), minimum=get("Minimum"), fixed=get("Fixed"),
        real_allowed=get("RealAllowed"), dummy_allowed=get("DummyAllowed"), dummy_start=get("DummyStart"),
        dummy_end=get("DummyEnd"), fill=get("Fill"), coverage=get("Coverage"), column=get("Column"))
    return {"score": parse(source), "statistics": parse(statistics), "minimum": parse(minimum)}, symbol


class CostEvaluator(Relaxation):
    def evaluate(self, form):
        if isinstance(form, list) and str(form[0]) == ">":
            return self.evaluate(form[1]) > self.evaluate(form[2])
        return super().evaluate(form)


def bits(value):
    return struct.pack("!d", value)


def legacy_score(state, worker, base):
    real = worker < state["Workers"]
    allowed = (state["RealAllowed"] and base >= 0.0) if real else (
        state["DummyAllowed"] and state["DummyStart"] <= worker < state["DummyEnd"])
    if not allowed:
        return -1e20
    score = 0.0
    if real:
        if state["Mode"] == 1:
            score = state["Fill"] + base
        elif state["Mode"] == 2:
            score = state["Fill"] + (base * state["Multiplier"])
        elif state["Mode"] == 3:
            score = base
        if state["Minimum"]:
            score = score + state["Coverage"]
    if worker == state["Fixed"]:
        score = score + state["Column"]
    return score


def row_statistics(values):
    """One scalar streaming accumulator; persist its five values once per row."""
    first = maximum_column = 0
    first_score = maximum = prefix_maximum = -1e20
    for column, value in enumerate(values, 1):
        if value >= 0.0:
            if first == 0:
                first, first_score = column, value
            if maximum_column == 0 or value > maximum:
                prefix_maximum = maximum
                maximum, maximum_column = value, column
    return first, first_score, maximum_column, maximum, prefix_maximum


def derived_cache(state, values, columns):
    """Return exact minimum cost and certified first winner, or column zero."""
    first, first_score, maximum_column, maximum, prefix_maximum = row_statistics(values)
    best_score, best_column = -1e20, 1
    if state["RealAllowed"] and first:
        # On a fixed row, masking leaves one eligible real value. Otherwise all
        # real candidates share every term in this monotone transformation.
        transform = lambda value: legacy_score(state, (state["Fixed"] if state["Fixed"] >= 0 else 0), value)
        best_score = transform(maximum)
        if transform(first_score) == best_score:
            best_column = first
        elif maximum_column == first or transform(prefix_maximum) < best_score:
            best_column = maximum_column
        else:
            best_column = 0
    if state["DummyAllowed"] and state["DummyStart"] < min(state["DummyEnd"], columns):
        if 0.0 > best_score:
            best_score, best_column = 0.0, state["DummyStart"] + 1
    return 0.0 - best_score, best_column


def run():
    forms, symbol = emitted()
    rng = random.Random(20261010)
    values = [-1e20, -1.0, -0.0, 0.0, 0.0001, 0.0002, 0.1, 1.03, 1e6]
    uncertain = 0
    cells = 0
    for case in range(5000):
        workers = rng.randint(1, 15)
        columns = workers + rng.randint(0, 8)
        fixed = rng.choice([-1, -1, rng.randrange(workers)])
        row = [rng.choice(values) for _ in range(workers)]
        if fixed >= 0:
            row = [value if col == fixed else -1e20 for col, value in enumerate(row)]
        capacity = rng.choice([2, 1001, 10001])
        max_score = max(0.0, max(row))
        fill = (((max_score * 5.0) + 1.0) * capacity) + 1.0
        coverage = (((fill + (max_score * 5.0)) + 1.0) * capacity) + 1.0
        column = ((((coverage + fill) + (max_score * 5.0)) + 1.0) * capacity) + 1.0
        state = {"Score": 0.0, "Base": 0.0, "IncomingBase": 0.0, "Worker": 0,
                 "Workers": workers, "Mode": rng.randrange(4), "Multiplier": rng.randint(1, 5),
                 "Minimum": bool(rng.randrange(2)), "Fixed": fixed,
                 "RealAllowed": bool(rng.randrange(2)), "DummyAllowed": fixed < 0 and bool(rng.randrange(2)),
                 "DummyStart": rng.randint(workers, columns), "DummyEnd": columns,
                 "Fill": fill, "Coverage": coverage, "Column": column}
        dense = []
        for worker in range(columns):
            state["Worker"] = worker
            state["IncomingBase"] = row[worker] if worker < workers else 0.0
            evaluator = CostEvaluator(forms["score"], symbol, dict(state))
            evaluator.edge()
            expected = legacy_score(state, worker, state["IncomingBase"])
            assert bits(evaluator.state["Score"]) == bits(expected), (case, state, evaluator.state, expected)
            dense.append(0.0 - expected)
            cells += 1
        cost, winner = derived_cache(state, row, columns)
        stats_state = dict(state, FirstColumn=0, FirstScore=-1e20, MaximumColumn=0,
                           MaximumScore=-1e20, PrefixScore=-1e20, MinimumScore=0.0,
                           MinimumColumn=0, Scratch=0.0, StatsColumn=0)
        stats = CostEvaluator(forms["statistics"], symbol, stats_state)
        for index, value in enumerate(row, 1):
            stats_state["StatsColumn"] = index
            stats_state["IncomingBase"] = value
            stats.edge()
        expected_stats = row_statistics(row)
        actual_stats = tuple(stats_state[name] for name in
                             ("FirstColumn", "FirstScore", "MaximumColumn", "MaximumScore", "PrefixScore"))
        assert [bits(value) for value in actual_stats] == [bits(value) for value in expected_stats]
        minimum = CostEvaluator(forms["minimum"], symbol, stats_state)
        minimum.edge()
        assert bits(0.0 - stats_state["MinimumScore"]) == bits(cost), (state, row, stats_state, cost)
        assert stats_state["MinimumColumn"] == winner, (state, row, stats_state, winner)
        expected = min(dense)
        assert bits(cost) == bits(expected), (case, state, row, dense, cost)
        if winner:
            assert winner == dense.index(expected) + 1, (case, state, row, dense, winner)
        else:
            uncertain += 1
        assert math.isfinite(cost)
    # Earlier nonmaximum values can become equal after a large bonus rounds.
    state = {"Workers": 3, "Mode": 1, "Multiplier": 1, "Minimum": True, "Fixed": -1,
             "RealAllowed": True, "DummyAllowed": False, "DummyStart": 3, "DummyEnd": 3,
             "Fill": 5005001002.0, "Coverage": 5015011004004.0, "Column": 0.0}
    row = [0.0, 0.01, 0.0101]
    cost, winner = derived_cache(state, row, 3)
    assert winner == 0, ("Rounded prefix tie must disable first-winner shortcut", winner, cost)
    print(f"WO_PLANNER_IMPLICIT_COST_MODEL_PASS: {cells} exact emitted cells; 5000 exact minima, {uncertain} conservative winners")


if __name__ == "__main__":
    run()
