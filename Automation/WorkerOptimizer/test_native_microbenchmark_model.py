"""Execute the actual microbenchmark DSL offline before authoring its fixture."""

import ast
import copy
from pathlib import Path

from benchmark_native_relaxation import TYPES, collect_snapshots, equal, sources
from test_solver_relaxation import Relaxation


class BreakLoop(Exception):
    pass


class Machine(Relaxation):
    def evaluate(self, form):
        if isinstance(form, self.symbol) and str(form) in self.bindings:
            return super().evaluate(form)
        if not isinstance(form, list) or not form:
            return super().evaluate(form)
        head = str(form[0])
        if head == "fn":
            for item in form[3:]:
                self.evaluate(item)
            return
        if head == "for":
            for index in range(*(self.evaluate(argument) for argument in form[2][1:])):
                self.bindings[str(form[1])] = index
                try:
                    for item in form[3:]:
                        self.evaluate(item)
                except BreakLoop:
                    break
            return
        if head == "break":
            raise BreakLoop
        if head == "switch":
            assert str(form[1]) == "int"
            assert [str(item[0]) for item in form[3:]] == [":" + str(i) for i in range(len(form) - 3)]
            value = self.evaluate(form[2])
            for item in form[3:]:
                if str(item[0]) == ":" + str(value):
                    for child in item[1:]:
                        self.evaluate(child)
                    break
            return
        if head.startswith("Variables|Default|Set"):
            self.state[head.removeprefix("Variables|Default|Set")] = copy.deepcopy(self.evaluate(form[1]))
            return
        if head == "Utilities|Array|Resize":
            array, size = self.evaluate(form[1]), self.evaluate(form[2])
            del array[size:]
            array.extend([0.0] * max(0, size - len(array)))
            return
        if head == "Utilities|Array|Sort|SortFloatArray":
            self.evaluate(form[2]).sort()
            return
        if head == "Utilities|Array|FindItem":
            array, value = self.evaluate(form[2]), self.evaluate(form[4])
            return array.index(value) if value in array else -1
        if head == "Utilities|Array|Length":
            return len(self.evaluate(form[1]))
        if head == ">":
            return self.evaluate(form[1]) > self.evaluate(form[2])
        return super().evaluate(form)


def parser():
    path = Path(r"D:\WWEngine\Engine\Plugins\Experimental\Toolsets\EditorToolset\Content\Python\editor_toolset\toolsets\blueprint_dsl.py")
    env = {}
    for item in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name in {"Symbol", "_source_line", "tokenize", "parse"}:
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
    return env["parse"], env["Symbol"]


def check_range_arguments():
    parse, symbol = parser()
    for arguments, expected in (("2 5", [2, 3, 4]), ("3", [0, 1, 2]), ("5 5", [])):
        state = {"Values": [-99] * 6, "Count": 0}
        source = f"""(for index (range {arguments})
          (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetValues)
            :Index (Variables|Default|GetCount) :Item index)
          (Variables|Default|SetCount (+ (Variables|Default|GetCount) 1)))"""
        machine = Machine([], symbol, state)
        for form in parse(source):
            machine.evaluate(form)
        assert state["Count"] == len(expected), (arguments, state, expected)
        assert state["Values"] == expected + [-99] * (6 - len(expected)), (arguments, state, expected)


def run():
    check_range_arguments()
    parse, symbol = parser()
    code = {name: parse(source) for name, source in sources().items()}
    snapshots = collect_snapshots()
    for limit in (1, 3, 64):
        for snapshot in snapshots:
            for native in (False, True):
                state = {name: ([] if kind.endswith("[]") else False if kind == "bool" else 0)
                         for kind, names in TYPES.items() for name in names.split()}
                state.update(copy.deepcopy(snapshot["before"]))
                state.update(Cursor=1, Stage=0, Delta=1e30, J1=0, BestColumnFree=False,
                             Cur=0.0, Done=False, StepWorkLimit=limit, CacheFree=native)
                method = "NativeStep" if native else "DenseStep"
                machine = Machine(code[method], symbol, state)
                calls = 0
                while not state["Done"]:
                    for form in code[method]:
                        machine.evaluate(form)
                    assert 0 < state["LastStepWork"] <= limit, (method, state["Stage"], state["LastStepWork"])
                    calls += 1
                    assert calls < 10000, (method, state["Stage"])
                for name, value in snapshot["after"].items():
                    assert equal(state[name], value), (snapshot["label"], method, limit, name)
            after = snapshot["after"]
            if after["BestColumnFree"] or after["Delta"] == 0.0:
                continue
            before = snapshot["before"]
            expected = dict(U=[0.0] * len(before["P"]), V=list(before["V"]), MinV=list(after["MinV"]))
            for j in range(before["Width"] + 1):
                if before["Used"][j]:
                    expected["U"][before["P"][j]] += after["Delta"]
                    expected["V"][j] -= after["Delta"]
                else:
                    expected["MinV"][j] -= after["Delta"]
            for cached in (False, True):
                state.update(copy.deepcopy(before))
                state.update(copy.deepcopy(after))
                state.update(U=[0.0] * len(before["P"]), Cursor=0, Done=False,
                             CacheFree=cached, FreeMinimum=1e30, FreeColumn=0)
                machine = Machine(code["PotentialStep"], symbol, state)
                while not state["Done"]:
                    for form in code["PotentialStep"]:
                        machine.evaluate(form)
                    assert 0 < state["LastStepWork"] <= limit
                assert all(equal(state[name], value) for name, value in expected.items())
                if cached:
                    free = min((j for j in range(1, before["Width"] + 1) if before["P"][j] == 0),
                               key=lambda j: (expected["MinV"][j], j))
                    assert state["FreeColumn"] == free
                    assert equal(state["FreeMinimum"], expected["MinV"][free])
    print(f"WO_NATIVE_MICROBENCH_DSL_MODEL_PASS snapshots={len(snapshots)} limits=1,3,64 variants=2")


if __name__ == "__main__":
    run()
