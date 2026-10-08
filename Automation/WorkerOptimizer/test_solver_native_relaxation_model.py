"""Actual emitted candidate phases against the unchanged dense relax fragment."""

import ast
import copy
from pathlib import Path

from benchmark_native_relaxation import collect_snapshots, equal
from planner_cost_dsl import implicit_score
from solver_native_relaxation_dsl import NATIVE_VARIABLES, candidate_setup, graph, initialize_reset
from test_native_microbenchmark_model import Machine, parser


class ReturnFunction(Exception):
    pass


class NativeMachine(Machine):
    def evaluate(self, form):
        if isinstance(form, list) and form:
            head = str(form[0])
            if head == "return":
                raise ReturnFunction
            if head == "fn":
                try:
                    for item in form[3:]:
                        self.evaluate(item)
                except ReturnFunction:
                    pass
                return
            if head == "switch":
                assert str(form[1]) == "int"
                cases = form[3:]
                regular = [str(item[0]) for item in cases if str(item[0]) != ":Default"]
                assert regular == [":" + str(i) for i in range(len(regular))]
                selected = next((item for item in cases if str(item[0]) == ":" + str(self.evaluate(form[2]))),
                                next((item for item in cases if str(item[0]) == ":Default"), None))
                if selected:
                    for child in selected[1:]:
                        self.evaluate(child)
                return
            if head == "Utilities|Array|Clear":
                self.evaluate(form[1]).clear()
                return
        return super().evaluate(form)


def emitted():
    path = Path(__file__).with_name("generate_solver.py")
    env = {"node": lambda name: "Variables|Default|" + name, "implicit_score": implicit_score}
    names = {"score_index", "negative_score", "dummy_allowed", "relax_cost", "implicit_load_cost",
             "implicit_relax_cost", "relax_choose", "relax_edge", "relax_done"}
    for item in ast.parse(path.read_text(encoding="utf-8")).body:
        include = isinstance(item, ast.FunctionDef) and item.name in {"get", "put", "at", "set_at"}
        if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
            include = item.targets[0].id in names
        if include:
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
    parse, symbol = parser()
    helpers = {key: env[key] for key in ("get", "put", "at", "set_at")}
    text = graph(**helpers, dense_cost=env["relax_cost"], implicit_cost=env["implicit_relax_cost"],
                 relax_done=env["relax_done"])
    forms = dict(native=parse(text), dense=parse(env["relax_edge"]),
                 setup=parse(candidate_setup(env["get"], env["put"])),
                 reset=parse(initialize_reset(env["get"], env["put"])))
    return forms, symbol


def check_structure(forms):
    def visit(node, parent=None, index=0):
        if not isinstance(node, list) or not node:
            return
        if str(node[0]) in ("else", "elif"):
            assert str(parent[0]) in ("if", "elif") and index == len(parent) - 1
        for i, child in enumerate(node):
            visit(child, node, i)
    for source in forms.values():
        visit(source)


def from_snapshot(snapshot, limit):
    before = snapshot["before"]
    state = {name: ([] if array else False if kind == "bool" else 0)
             for name, (kind, array) in NATIVE_VARIABLES.items()}
    state.update(copy.deepcopy(before))
    dummy_columns = [j - 1 for j in before["AllowedColumns"] if j > before["Workers"]]
    state.update(Scores=list(before["ScoreRow"]), RowScoreOffset=-1, Rows=1, Cols=before["Width"],
                 I0=1, ActiveRow=1, DummyCount=0, DummyAllowed=[False], Done=False,
                 NonpositiveV=True, RelaxationBoundEnabled=before["BoundEnabled"],
                 RelaxationLowerBound=before["LowerBound"], SolverState=5,
                 Delta=1e30, J1=0, Cur=0.0, BestColumnFree=False, Cursor=1,
                 StepWorkLimit=limit, NativePlannerTrusted=True, NativeCsrReady=True,
                 NativeFreeValid=True, NativeFreeRow=1,
                 NativeFreeMinimum=before["FreeMinimum"], NativeFreeColumn=before["FreeColumn"],
                 NativeRowOffsets=[0, len(before["AllowedColumns"])],
                 NativeColumns=[j - 1 for j in before["AllowedColumns"]],
                 ImplicitFirstPass=before["PrefixMode"], ImplicitWorkerCount=before["Workers"],
                 ImplicitScores=before["ScoreRow"][:before["Workers"]], ImplicitRowOffset=0,
                 ImplicitMode=3, ImplicitMultiplier=1, ImplicitMinimum=False,
                 ImplicitFixedWorker=-1, ImplicitRealAllowed=True,
                 ImplicitDummyAllowed=bool(dummy_columns),
                 ImplicitDummyStart=min(dummy_columns) if dummy_columns else before["Workers"],
                 ImplicitDummyEnd=max(dummy_columns) + 1 if dummy_columns else before["Workers"],
                 ImplicitFillBonus=0.0, ImplicitCoverageBonus=0.0, ImplicitColumnBonus=0.0)
    return state


def run():
    forms, symbol = emitted()
    check_structure(forms)
    snapshots = collect_snapshots()
    native_hits = 0
    for limit in (1, 3, 64):
        for snapshot in snapshots:
            state = from_snapshot(snapshot, limit)
            machine = NativeMachine([], symbol, state)
            for form in forms["setup"]:
                machine.evaluate(form)
            calls = 0
            while state["SolverState"] == 11:
                for form in forms["native"]:
                    machine.evaluate(form)
                assert 0 < state["LastStepWork"] <= limit
                calls += 1
                assert calls < 10000
            native_hits += state["SolverState"] == 6
            if state["SolverState"] == 5:
                while state["Cursor"] <= state["Width"]:
                    for form in forms["dense"]:
                        machine.evaluate(form)
            for name, value in snapshot["after"].items():
                assert equal(state[name], value), (snapshot["label"], limit, name)
    for changed in ({"NativePlannerTrusted": False}, {"NativeFreeValid": False},
                    {"NativeFreeRow": -1}, {"DummyCount": 1}, {"RelaxationBoundEnabled": False},
                    {"NonpositiveV": False}):
        state = from_snapshot(snapshots[1], 64)
        state.update(changed)
        machine = NativeMachine([], symbol, state)
        for form in forms["setup"]:
            machine.evaluate(form)
        assert state["SolverState"] == 5
    state = from_snapshot(snapshots[1], 64)
    machine = NativeMachine([], symbol, state)
    for form in forms["reset"]:
        machine.evaluate(form)
    assert not state["NativePlannerTrusted"] and not state["NativeCsrReady"] and not state["NativeFreeValid"]
    assert state["NativeColumns"] == state["NativeRowOffsets"] == []
    for phase in range(6):
        state = from_snapshot(snapshots[1], 64)
        state.update(Done=True, SolverState=11, NativePhase=phase)
        before = copy.deepcopy(state)
        machine = NativeMachine([], symbol, state)
        for form in forms["native"]:
            machine.evaluate(form)
        assert state["LastStepWork"] == 0
        assert all(state[name] == value for name, value in before.items())
    state = from_snapshot(snapshots[1], 64)
    state.update(SolverState=11, NativePhase=4, NativeMasked=[1e30] * (state["Width"] + 1))
    machine = NativeMachine([], symbol, state)
    for form in forms["native"]:
        machine.evaluate(form)
    assert state["SolverState"] == 5 and state["Cursor"] == 1 and state["J1"] == 0
    print(f"WO_NATIVE_SOLVER_CANDIDATE_MODEL_PASS snapshots={len(snapshots)} native_completions={native_hits} limits=1,3,64")


if __name__ == "__main__":
    run()
