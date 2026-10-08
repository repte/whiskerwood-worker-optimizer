"""Run complete emitted solver lifecycles without Unreal or production assets."""

import ast
import copy
from pathlib import Path
import random

from benchmark_native_relaxation import equal
from test_solver_native_relaxation_model import NativeMachine, parser, check_structure


def emitted(path):
    def node(name):
        if name == "SortFloatArray":
            return "Utilities|Array|Sort|SortFloatArray"
        if name == "FindItem":
            return "Utilities|Array|FindItem"
        return "Variables|Default|" + name

    env = {"node": node}
    active = False
    for item in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(item, ast.ImportFrom) and item.module in {
                "planner_cost_dsl", "solver_relaxation_bound_dsl", "solver_native_relaxation_dsl", "solver_integer_u_dsl",
                "solver_integer_minv_dsl"}:
            helper_path = path.with_name(item.module + ".py")
            if helper_path.exists():
                helper = {}
                exec(compile(helper_path.read_text(encoding="utf-8"), str(helper_path), "exec"), helper)
                for alias in item.names:
                    env[alias.asname or alias.name] = helper[alias.name]
            else:
                exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
        if isinstance(item, ast.FunctionDef) and item.name == "get":
            active = True
        if active and isinstance(item, (ast.FunctionDef, ast.Assign)):
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
    parse, symbol = parser()
    graphs = {}
    for name, source in env.items():
        if isinstance(source, str) and source.lstrip().startswith("(fn "):
            forms = parse(source)
            graphs[str(forms[0][1])] = forms
    check_structure(graphs)
    return graphs, symbol


class SolverMachine(NativeMachine):
    def __init__(self, graphs, symbol, limit):
        super().__init__([], symbol, {"StepWorkLimit": limit})
        self.graphs = graphs
        self.params = {}

    def invoke(self, name, args=()):
        prior_bindings, prior_params = self.bindings, self.params
        self.bindings = {}
        self.params = dict(zip(map(str, self.graphs[name][0][2]), args))
        try:
            for form in self.graphs[name]:
                self.evaluate(form)
        finally:
            self.bindings, self.params = prior_bindings, prior_params

    def evaluate(self, form):
        if isinstance(form, self.symbol) and str(form) in self.params:
            return self.params[str(form)]
        if isinstance(form, list) and form:
            head = str(form[0])
            prefix = "Variables|Default|"
            if head.startswith(prefix) and head[len(prefix):] in self.graphs:
                self.invoke(head[len(prefix):], [self.evaluate(item) for item in form[1:]])
                return
            if head.startswith(prefix + "Get"):
                return self.state.get(head[len(prefix + "Get"):], 0)
            if head == "Variables|SetBy-RefVar":
                assert str(form[1]) == ":Target" and str(form[3]) == ":Value"
                target = form[2]
                assert str(target[0]) == "Utilities|Array|Get(aref)"
                assert str(target[1]) == ":Array" and str(target[3]) == ":Dimension 1"
                array, index = self.evaluate(target[2]), self.evaluate(target[4])
                assert isinstance(index, int) and 0 <= index < len(array)
                value = self.evaluate(form[4])
                assert not isinstance(value, (list, dict))
                array[index] = value
                return
            if head == "Utilities|Array|Clear":
                name = str(form[1][0]).removeprefix(prefix + "Get")
                self.state[name] = []
                return
            if head == "Utilities|Array|Add":
                array = self.evaluate(form[1])
                array.append(self.evaluate(form[2]))
                return len(array) - 1
            if head == "/":
                a, b = self.evaluate(form[1]), self.evaluate(form[2])
                return a // b if isinstance(a, int) and isinstance(b, int) else a / b
        return super().evaluate(form)


def solve(graphs, symbol, matrix, limit, enabled=False, dummy=False):
    machine = SolverMachine(graphs, symbol, limit)
    rows, cols = len(matrix), len(matrix[0])
    machine.invoke("Initialize", [[value for row in matrix for value in row], rows, cols])
    machine.invoke("RestrictDummies", [[dummy] * rows])
    if enabled:
        offsets, columns = [0], []
        for row in matrix:
            columns.extend(j for j, score in enumerate(row) if score != -1e20)
            offsets.append(len(columns))
        machine.state.update(NativePlannerTrusted=True, NativeCsrReady=True,
                             NativeColumns=columns, NativeRowOffsets=offsets)
    native, work = 0, 0
    while not machine.state["Done"]:
        native += machine.state["SolverState"] == 11
        machine.invoke("Advance")
        actual = machine.state["LastStepWork"]
        assert 0 < actual <= limit
        work += actual
        assert work < 1000000
    return machine.state, native


def solve_implicit(graphs, symbol, matrix, workers, limit, enabled):
    machine = SolverMachine(graphs, symbol, limit)
    rows, cols = len(matrix), len(matrix[0])
    starts, ends, allowed = [], [], []
    for row in matrix:
        legal = [j for j in range(workers, cols) if row[j] >= 0.0]
        assert not legal or legal == list(range(legal[0], legal[-1] + 1))
        starts.append(legal[0] if legal else workers)
        ends.append(legal[-1] + 1 if legal else workers)
        allowed.append(bool(legal))
    machine.state.update(ImplicitWorkerCount=workers,
        ImplicitScores=[value for row in matrix for value in row[:workers]],
        ImplicitModes=[3] * rows, ImplicitMultipliers=[1] * rows, ImplicitMinimumRows=[False] * rows,
        ImplicitRealRows=[True] * rows, ImplicitDummyRows=allowed, ImplicitFixedWorkers=[-1] * rows,
        ImplicitDummyStarts=starts, ImplicitDummyEnds=ends,
        ImplicitFillBonus=0.0, ImplicitCoverageBonus=0.0, ImplicitColumnBonus=0.0)
    machine.invoke("InitializeImplicitFirstPass", [rows, cols])
    costs = [[0.0 - value for value in row] for row in matrix]
    machine.state.update(RowMinCost=[min(row) for row in costs],
        RowMinColumn=[row.index(min(row)) + 1 for row in costs],
        RowSecondMinCost=[sorted(row)[1] if len(row) > 1 else 1e20 for row in costs],
        NativePlannerTrusted=enabled, NativeCsrReady=False)
    native, work = 0, 0
    while not machine.state["Done"]:
        native += machine.state["SolverState"] == 11
        machine.invoke("Advance")
        actual = machine.state["LastStepWork"]
        assert 0 < actual <= limit
        work += actual
        assert work < 1000000
    return machine.state, native


def run():
    graphs, symbol = emitted(Path(__file__).with_name("generate_solver.py"))
    baseline_path = Path(r"D:\TD\WoodMod\DeploymentCandidates\performance-1000\Round4\generate_solver.py")
    baseline, baseline_symbol = emitted(baseline_path)
    r6, r6_symbol = emitted(Path(r"D:\TD\WoodMod\DeploymentCandidates\performance-1000\Round6SourceBeforeCache\generate_solver.py"))
    matrices = [[[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]]]
    compiled_test = ast.parse(Path(__file__).with_name("test_solver_native_relaxation.py").read_text(encoding="utf-8"))
    run_fn = next(item for item in compiled_test.body if isinstance(item, ast.FunctionDef) and item.name == "run")
    examples = next(item for item in run_fn.body if isinstance(item, ast.Assign)
                    and isinstance(item.targets[0], ast.Name) and item.targets[0].id == "matrices")
    matrices.extend(ast.literal_eval(examples.value))
    rng = random.Random(187237)
    for _ in range(80):
        rows, cols = rng.randint(1, 7), rng.randint(1, 9)
        matrices.append([[rng.choice([-1e20, -0.09, -0.0, 0.0, .1, 1.03, 7., 1e14+.06])
                          for _ in range(cols)] for _ in range(rows)])
    names = ("Assignment", "Succeeded", "P", "Way", "U", "V", "MinV", "Cur")
    cases, native_calls, r6_cases = 0, 0, 0
    for limit in (1, 3, 64):
        for dummy in (False, True):
            for matrix in matrices:
                expected, _ = solve(baseline, baseline_symbol, matrix, limit, dummy=dummy)
                prior, _ = solve(r6, r6_symbol, matrix, limit, True, dummy)
                for name in names:
                    assert equal(prior.get(name, 0), expected.get(name, 0)), ("R6", limit, dummy, matrix, name)
                r6_cases += 1
                for enabled in (False, True):
                    actual, native = solve(graphs, symbol, matrix, limit, enabled, dummy)
                    for name in names:
                        assert equal(actual.get(name, 0), expected.get(name, 0)), (limit, dummy, enabled, matrix, name)
                    if dummy or not enabled:
                        assert native == 0
                    cases += 1
                    native_calls += native
    from test_solver_cached_trace import benchmark_matrices
    for limit in (1, 3, 64):
        for size in (6, 12, 24):
            matrix = benchmark_matrices(size)[0]
            expected, _ = solve_implicit(baseline, baseline_symbol, matrix, size, limit, False)
            prior, _ = solve_implicit(r6, r6_symbol, matrix, size, limit, True)
            for name in names:
                assert equal(prior.get(name, 0), expected.get(name, 0)), ("R6 implicit", size, limit, name)
            r6_cases += 1
            for enabled in (False, True):
                actual, native = solve_implicit(graphs, symbol, matrix, size, limit, enabled)
                for name in names:
                    assert equal(actual.get(name, 0), expected.get(name, 0)), ("implicit", size, limit, enabled, name)
                native_calls += native
                cases += 1
    assert native_calls
    changed = [name for name in graphs if graphs[name] != r6.get(name)]
    print(f"WO_NATIVE_SOLVER_LIFECYCLE_MODEL_PASS comparisons={cases} r6_references={r6_cases} "
          f"native_phase_calls={native_calls} graphs={len(graphs)} changed_vs_r6={changed}")


if __name__ == "__main__":
    run()
