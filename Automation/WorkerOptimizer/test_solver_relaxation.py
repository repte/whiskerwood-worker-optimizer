"""Offline differential check of generated relaxation DSL against eager labels.

Uses the installed engine's pure DSL parser, without importing or running Unreal.
Set WO_BLUEPRINT_DSL_PATH when the engine source is installed elsewhere.
"""

import ast
import copy
import math
import os
import random
import struct
from pathlib import Path


def generated_forms():
    generator = Path(__file__).with_name("generate_solver.py")
    env = {"node": lambda name: "Variables|Default|" + name}
    names = {"score_index", "negative_score", "dummy_allowed", "relax_cost", "relax_choose", "relax_edge"}
    for item in ast.parse(generator.read_text(encoding="utf-8")).body:
        include = isinstance(item, ast.FunctionDef) and item.name in {"get", "put", "at", "set_at"}
        if isinstance(item, ast.Assign) and isinstance(item.targets[0], ast.Name):
            include = item.targets[0].id in names
        if include:
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(generator), "exec"), env)
    parser_path = Path(os.environ.get("WO_BLUEPRINT_DSL_PATH", r"D:\WWEngine\Engine\Plugins\Experimental\Toolsets\EditorToolset\Content\Python\editor_toolset\toolsets\blueprint_dsl.py"))
    parser = {}
    for item in ast.parse(parser_path.read_text(encoding="utf-8")).body:
        if isinstance(item, (ast.FunctionDef, ast.ClassDef)) and item.name in {"Symbol", "_source_line", "tokenize", "parse"}:
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(parser_path), "exec"), parser)
    return parser["parse"](env["relax_edge"]), parser["Symbol"]


class Relaxation:
    def __init__(self, forms, symbol, state):
        self.forms = forms
        self.symbol = symbol
        self.state = state
        self.bindings = {}
        self.reads = {}

    def evaluate(self, form):
        if isinstance(form, self.symbol):
            return self.evaluate(self.bindings[str(form)])
        if not isinstance(form, list):
            return form
        head = str(form[0])
        if head == "bind":
            # DSL bindings alias pins; they do not snapshot their values.
            self.bindings[str(form[1])] = form[2]
            return None
        if head == "if":
            body = form[2:]
            branch = body[-1] if isinstance(body[-1], list) and str(body[-1][0]) in {"elif", "else"} else None
            if self.evaluate(form[1]):
                for statement in body[:-1] if branch is not None else body:
                    self.evaluate(statement)
            elif branch is not None:
                if str(branch[0]) == "elif":
                    self.evaluate(["if", *branch[1:]])
                else:
                    for statement in branch[1:]:
                        self.evaluate(statement)
            return None
        if head.startswith("Variables|Default|Get"):
            return self.state[head.removeprefix("Variables|Default|Get")]
        if head.startswith("Variables|Default|Set"):
            self.state[head.removeprefix("Variables|Default|Set")] = self.evaluate(form[1])
            return None
        if head.startswith("Utilities|Array|Get("):
            name = str(form[2][0]).removeprefix("Variables|Default|Get")
            self.reads[name] = self.reads.get(name, 0) + 1
            return self.evaluate(form[2])[self.evaluate(form[4])]
        if head == "Utilities|Array|SetArrayElem":
            array, index, value = self.evaluate(form[2]), self.evaluate(form[4]), self.evaluate(form[6])
            array[index] = value
            return None
        # Blueprint boolean function inputs are evaluated eagerly.
        args = [self.evaluate(value) for value in form[1:]]
        operators = {
            "+": lambda a, b: a + b,
            # The DSL lowers unary minus to a subtraction node with A set to zero.
            "-": lambda a, b=None: 0 - a if b is None else a - b,
            "*": lambda a, b: a * b,
            "<": lambda a, b: a < b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "and": lambda a, b: a and b,
            "or": lambda a, b: a or b,
            "not": lambda value: not value,
            "select": lambda condition, yes, no: yes if condition else no,
        }
        return operators[head](*args)

    def edge(self):
        self.bindings.clear()
        for form in self.forms:
            self.evaluate(form)


def eager_edge(state):
    j = state["Cursor"]
    if not state["Used"][j]:
        cost = (0.0 - state["Scores"][(state["I0"] - 1) * state["Cols"] + j - 1]
                if j <= state["Cols"] else (0.0 if state["DummyAllowed"][state["I0"] - 1] else 1e29))
        cur = (cost - state["RowPotential"]) - state["V"][j]
        if state["J0"] == 0 or cur < state["MinV"][j]:
            state["MinV"][j] = cur
            state["Way"][j] = state["J0"]
        if (state["MinV"][j] < state["Delta"] or
                (state["MinV"][j] == state["Delta"] and state["P"][j] == 0 and state["P"][state["J1"]] != 0)):
            state["Delta"] = state["MinV"][j]
            state["J1"] = j
    state["Cursor"] += 1


def observable(state):
    bits = lambda value: struct.pack("!d", value)
    return ([bits(value) for value in state["MinV"]], tuple(state["Way"]),
            bits(state["Delta"]), state["J1"], state["Cursor"])


def fixture(width, cols, first=True):
    return {"Cursor": 1, "Cols": cols, "I0": 1, "J0": 0 if first else 1,
            "Cur": 0.0, "Delta": 1e30, "J1": 0, "BestColumnFree": False,
            "RowPotential": 0.0, "RowScoreOffset": -1,
            "Scores": [float(j) for j in range(cols)], "DummyAllowed": [False],
            "Used": [True] + [False] * width, "P": [1] + [0] * width,
            "V": [0.0] * (width + 1), "MinV": [0.0] * (width + 1), "Way": [0] * (width + 1)}


def compare(forms, symbol, initial):
    reference = copy.deepcopy(initial)
    actual = Relaxation(forms, symbol, copy.deepcopy(initial))
    assert reference["P"][0] > 0
    assert all(math.isfinite(value) and -1e20 <= value <= 1e20 for value in reference["Scores"])
    while reference["Cursor"] < len(reference["Used"]):
        eager_edge(reference)
        actual.edge()
        assert observable(actual.state) == observable(reference), (initial, reference, actual.state)
    return actual


def run():
    forms, symbol = generated_forms()
    zero = fixture(1, 1)
    zero["Scores"] = [0.0]
    zero_result = compare(forms, symbol, zero)
    assert struct.pack("!d", zero_result.state["MinV"][1]) == struct.pack("!d", 0.0), (
        "DSL unary negation is zero subtraction, not sign-bit negation", zero_result.state)

    # First relaxation replaces every distance, including stale NaNs, without reading it.
    first = fixture(24, 24)
    first["MinV"] = [math.nan] * 25
    first_result = compare(forms, symbol, first)
    assert first_result.reads.get("MinV", 0) == 0, (
        "First relaxation still reads overwritten MinV labels", first_result.reads)

    # Equal labels retain an occupied best until the first free column, then retain it.
    ties = fixture(7, 7)
    ties["Scores"] = [0.0] * 7
    ties["P"] = [1, 2, 3, 0, 0, 4, 0, 5]
    tie_result = compare(forms, symbol, ties)
    assert tie_result.state["J1"] == 3
    assert tie_result.reads.get("P", 0) == 3, ("Free best column did not suppress later tie reads", tie_result.reads)

    rng = random.Random(20261008)
    scores = [-1e20, -0.09, -0.0, 0.0, 0.1, 1.03, 199999999999999.97, 200000000000000.06, 1e20]
    labels = [-1e29, -200000000000000.06, -0.0, 0.0, 0.1, 1.03, 200000000000000.06, 1e29]
    for case in range(2000):
        width = rng.randint(1, 12)
        cols = rng.randint(0, width)
        rows = rng.randint(1, 6)
        state = fixture(width, cols, first=case % 2 == 0)
        state["I0"] = rng.randint(1, rows)
        state["RowScoreOffset"] = (state["I0"] - 1) * cols - 1
        state["Scores"] = [rng.choice(scores) for _ in range(rows * cols)]
        state["DummyAllowed"] = [bool(rng.randrange(2)) for _ in range(rows)]
        state["RowPotential"] = rng.choice(labels)
        state["P"] = [rows] + [rng.randrange(rows + 1) for _ in range(width)]
        state["V"] = [rng.choice(labels) for _ in range(width + 1)]
        state["MinV"] = [rng.choice(labels) for _ in range(width + 1)]
        if state["J0"]:
            state["Used"] = [True] + [bool(rng.randrange(4) == 0) for _ in range(width)]
            state["Used"][state["J0"]] = True
        compare(forms, symbol, state)
    print("WO_SOLVER_RELAXATION_DIFFERENTIAL_PASS: 2003 scans, bit-exact labels/ties, DSL signed zero, zero stale-label reads")


if __name__ == "__main__":
    run()
