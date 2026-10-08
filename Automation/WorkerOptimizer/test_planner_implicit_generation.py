"""Offline checks of the actual emitted planner preparation/refinement graphs."""

import ast
import copy
import random
from pathlib import Path

import planner_cost_dsl
import planner_refine_bound_dsl
import planner_refine_cache_dsl
import planner_refine_reconstruct_dsl
from planner_validation_dsl import statistics as validation_statistics
from test_planner_implicit_cost_model import CostEvaluator, bits, legacy_score, parser, row_statistics


def generated(path=None):
    path = Path(__file__).with_name("generate_planner.py") if path is None else Path(path)
    env = dict(vars(planner_cost_dsl))
    env.update(vars(planner_refine_bound_dsl))
    env.update(vars(planner_refine_cache_dsl))
    env.update(vars(planner_refine_reconstruct_dsl))
    env['validation_statistics'] = validation_statistics
    env["node"] = lambda name: "Variables|Default|" + name
    started = False
    for item in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(item, ast.FunctionDef) and item.name == "g":
            started = True
        if started:
            if isinstance(item, ast.For):
                break
            exec(compile(ast.Module(body=[item], type_ignores=[]), str(path), "exec"), env)
    return env


def check_structure(form, loop=False):
    if not isinstance(form, list) or not form:
        return
    head = str(form[0])
    assert not (loop and head == "return"), "Void return inside a loop does not break the Blueprint macro"
    for index, child in enumerate(form):
        if isinstance(child, list) and child and str(child[0]) in {"elif", "else"}:
            assert head in {"if", "elif"} and index == len(form) - 1, (head, child)
        check_structure(child, loop or head == "for")


class PlannerEvaluator(CostEvaluator):
    def __init__(self, forms, symbol, state):
        super().__init__(forms, symbol, state)
        self.writes = {}
        self.cell_writes = {}
        self.divisions = 0

    def evaluate(self, form):
        if isinstance(form, list) and form:
            head = str(form[0])
            if head.startswith('Variables|Default|Set'):
                name = head.removeprefix('Variables|Default|Set')
                value = self.evaluate(form[1])
                self.state[name] = list(value) if isinstance(value, list) else value
                return None
            if head.startswith('Variables|Default|Get'):
                name = head.removeprefix('Variables|Default|Get')
                if name not in self.state:
                    for kind, names in planner_refine_reconstruct_dsl.RECONSTRUCTION_VARIABLES.items():
                        if name in names.split():
                            self.state[name] = [] if kind.endswith('[]') else False if kind == 'bool' else 0
                    if name in planner_cost_dsl.IMPLICIT_VARIABLES:
                        kind, array = planner_cost_dsl.IMPLICIT_VARIABLES[name]
                        self.state[name] = [] if array else False if kind == 'bool' else 0
                    if name == 'SentinelRow':
                        self.state[name] = []
            if head == "Utilities|Array|SetArrayElem":
                name = str(form[2][0]).removeprefix("Variables|Default|Get")
                array, index, value = self.evaluate(form[2]), self.evaluate(form[4]), self.evaluate(form[6])
                self.writes[name] = self.writes.get(name, 0) + 1
                key = (name, index)
                self.cell_writes[key] = self.cell_writes.get(key, 0) + 1
                array[index] = value
                return None
            if head == "Utilities|Array|Length":
                return len(self.evaluate(form[1]))
            if head == "Utilities|Array|Add":
                self.evaluate(form[1]).append(self.evaluate(form[2]))
                return None
            if head == "Utilities|Array|AppendArray":
                self.evaluate(form[1]).extend(self.evaluate(form[2]))
                return None
            if head == "Utilities|Array|Clear":
                self.evaluate(form[1]).clear()
                return None
            if head == "Utilities|Array|Resize":
                array, size = self.evaluate(form[1]), self.evaluate(form[2])
                del array[size:]
                array.extend([0] * (size - len(array)))
                return None
            if head == "/":
                self.divisions += 1
                return self.evaluate(form[1]) // self.evaluate(form[2])
        return super().evaluate(form)


def check_native_handoff(env, parse, symbol):
    class Initializer(PlannerEvaluator):
        def evaluate(self, form):
            if isinstance(form, list) and form:
                head = str(form[0])
                if head in {"Variables|Default|Initialize", "Variables|Default|InitializeImplicitFirstPass"}:
                    self.state.update(NativePlannerTrusted=False, NativeCsrReady=False,
                                      NativeRowOffsets=[], NativeColumns=[])
                    return None
                if head == "Variables|Default|RestrictDummies":
                    return None
            return super().evaluate(form)

    for first, ready in ((True, False), (False, True), (False, False)):
        state = dict(FirstPass=first, RetainedReady=ready, SlotCount=2, SolveColumns=3,
                     PassScores=[0.0] * 6, AllowedEmpty=[False] * 2,
                     PassRowMinCost=[-2.0, -3.0], PassRowSecondMinCost=[0.0, -1.0],
                     PassRowMinColumn=[1, 2], RetainedRowOffsets=[0, 2, 3], RetainedColumns=[0, 1, 1],
                     NativePlannerTrusted=True, NativeCsrReady=True, NativeRowOffsets=[99], NativeColumns=[99])
        Initializer(parse(env["initialize_pass"]), symbol, state).edge()
        assert state["State"] == 5 and not state["FirstPass"] and state["NativePlannerTrusted"]
        assert state["NativeCsrReady"] == (not first and ready)
        assert state["NativeRowOffsets"] == ([0, 2, 3] if not first and ready else [])
        assert state["NativeColumns"] == ([0, 1, 1] if not first and ready else [])
        for parent, planner in (("RowMinCost", "PassRowMinCost"), ("RowSecondMinCost", "PassRowSecondMinCost"),
                                ("RowMinColumn", "PassRowMinColumn")):
            assert state[parent] == state[planner]


def run():
    env = generated()
    parse, symbol = parser()
    for source in env["code"].values():
        for form in parse(source):
            check_structure(form)
    check_native_handoff(env, parse, symbol)
    validate = parse("(bind n (Variables|Default|GetPlanValidationIndex))" + env["validation_cell"]("(return)"))
    build = parse(env["build_implicit_row"])
    rng = random.Random(20261011)
    cells = 0
    for case in range(300):
        workers, rows = rng.randint(1, 10), rng.randint(1, 8)
        dummy_count = rng.randint(0, 4)
        columns = workers + rows * dummy_count
        values = [-1e20, -0.0, 0.0, 0.0001, 0.01, 0.0101, 1.03, 1e6]
        base = [rng.choice(values) for _ in range(rows * workers)]
        fixed = [-1] * rows
        for row in range(min(rows, workers)):
            if case % 7 == 0:
                fixed[row] = row
                for worker in range(workers):
                    if worker != row:
                        base[row * workers + worker] = -1e20
        state = dict(BaseScores=base, PlanValidationIndex=0, WorkerCount=workers,
                     FixedConfigured=False, MaxScore=0.0, StatsOffset=0, StatsEnd=workers,
                     StatsFirstColumn=0, StatsMaximumColumn=0, StatsFirstScore=-1e20,
                     StatsMaximumScore=-1e20, StatsPrefixScore=-1e20, StatsSecondScore=-1e20,
                     StatsAllReal=True, StatsUniformScore=True,
                     RowFirstColumn=[], RowMaximumColumn=[], RowFirstScore=[],
                     RowMaximumScore=[], RowPrefixScore=[], RowSecondScore=[])
        evaluator = PlannerEvaluator(validate, symbol, state)
        for _ in base:
            evaluator.edge()
        assert len(state["RowSecondScore"]) == rows, "Validation must stream second raw maxima without rescanning"
        for row in range(rows):
            actual = tuple(state[name][row] for name in
                           ("RowFirstColumn", "RowFirstScore", "RowMaximumColumn", "RowMaximumScore", "RowPrefixScore"))
            expected = row_statistics(base[row * workers:(row + 1) * workers])
            assert [bits(value) for value in actual] == [bits(value) for value in expected]
            eligible = sorted((value for value in base[row * workers:(row + 1) * workers] if value >= 0.0), reverse=True)
            assert state["RowSecondScore"][row] == (eligible[1] if len(eligible) > 1 else -1e20)
            assert state['RowAllReal'][row] == (len(eligible) == workers)
            assert state['RowUniformScore'][row] == (not eligible or all(value == eligible[0] for value in eligible))
        capacity = rows + 1
        fill = (((state["MaxScore"] * 5.0) + 1.0) * capacity) + 1.0
        coverage = (((fill + (state["MaxScore"] * 5.0)) + 1.0) * capacity) + 1.0
        column = ((((coverage + fill) + (state["MaxScore"] * 5.0)) + 1.0) * capacity) + 1.0
        state.update(SlotCount=rows, SolveColumns=columns, MatrixCells=rows * columns,
                     ScanRow=0, ScanWorker=0, BuildIndex=0, SlotBuildings=list(range(rows)),
                     FixedSlots=fixed, Accepted=[bool(rng.randrange(2)) for _ in range(rows)],
                     Minimum=[bool(rng.randrange(2)) for _ in range(rows)],
                     Priorities=[rng.randint(-1, 4) for _ in range(rows)], Tier=rng.randint(-1, 4),
                     StrictMode=bool(rng.randrange(2)), PassRowMinCost=[0.0] * rows,
                     PassRowMinColumn=[0] * rows, PassRowSecondMinCost=[0.0] * rows,
                     FillBonus=fill, CoverageBonus=coverage,
                     ColumnBonus=column, BuildingDummyStart=[workers + row * dummy_count for row in range(rows)],
                     BuildingDummyEnd=[workers + (row + 1) * dummy_count for row in range(rows)])
        for name, (_, array) in planner_cost_dsl.IMPLICIT_VARIABLES.items():
            state[name] = [0] * rows if array else 0
        state.update(ImplicitWorkerCount=workers, ImplicitScores=base, ImplicitFillBonus=fill,
                     ImplicitCoverageBonus=coverage, ImplicitColumnBonus=column, ImplicitFirstPass=True)
        evaluator.forms = build
        for _ in range(rows):
            evaluator.edge()
        assert state["BuildIndex"] == rows and state["ScanRow"] == rows
        dense = []
        masks = []
        for row in range(rows):
            priority = state["Priorities"][row]
            mode = (2 if not state["StrictMode"] else int(priority == state["Tier"])) if priority >= 0 and state["Tier"] >= 0 else int(priority < 0 and state["Tier"] < 0) * 3
            reference = dict(Workers=workers, Mode=mode, Multiplier=priority + 1,
                             Minimum=state["Minimum"][row], Fixed=fixed[row],
                             RealAllowed=state["Accepted"][row] or fixed[row] >= 0,
                             DummyAllowed=fixed[row] < 0 and not (state["Minimum"][row] and state["Accepted"][row]),
                             DummyStart=state["BuildingDummyStart"][row], DummyEnd=state["BuildingDummyEnd"][row],
                             Fill=fill, Coverage=coverage, Column=column)
            scores = [legacy_score(reference, worker, base[row * workers + worker] if worker < workers else 0.0)
                      for worker in range(columns)]
            costs = [0.0 - score for score in scores]
            assert bits(state["PassRowMinCost"][row]) == bits(min(costs)), (case, row, state)
            assert bits(state["PassRowSecondMinCost"][row]) == bits(sorted(costs)[1] if columns > 1 else 1e20), (case, row, state)
            cached = state["PassRowMinColumn"][row]
            assert cached == 0 or cached == costs.index(min(costs)) + 1
            dense.extend(scores)
            masks.extend(score >= 0.0 for score in scores)
        state.update(BuildIndex=0, RetainedColumns=[], RetainedRowOffsets=[], PassScores=[], AllowedEdges=[],
                     State=6, RefineInitialized=False, RetainedReady=False,
                     RowMinColumn=list(state["PassRowMinColumn"]),
                     RowSecondMinCost=list(state["PassRowSecondMinCost"]),
                     U=[rng.choice([-0.0, 0.0, coverage, -coverage]) for _ in range(rows + 1)],
                     V=[rng.choice([-0.0, 0.0, 0.1, -0.1]) for _ in range(columns + 1)])
        dense_seed = copy.deepcopy(state)
        evaluator.forms = parse(env["refine_item"])
        evaluator.writes.clear()
        evaluator.cell_writes.clear()
        evaluator.reads.clear()
        evaluator.divisions = 0
        expected_mask = []
        expected_columns = []
        expected_offsets = []
        for index, score in enumerate(dense):
            row, worker = divmod(index, columns)
            if worker == 0:
                expected_offsets.append(len(expected_columns))
            reduced = ((0.0 - score) - state["U"][row + 1]) - state["V"][worker + 1]
            allowed = masks[index] and -0.00001 <= reduced <= 0.00001
            expected_mask.append(allowed)
            if allowed:
                expected_columns.append(worker)
            cells += 1
        while state["State"] == 6:
            evaluator.edge()
        assert state["PassScores"] == [], "First implicit refinement must defer dense score materialization"
        expected_offsets.append(len(expected_columns))
        assert state["AllowedEdges"] == expected_mask
        assert state["RetainedColumns"] == expected_columns
        assert state["RetainedRowOffsets"] == expected_offsets
        assert evaluator.writes.get("PassScores", 0) == 0
        assert evaluator.writes.get("AllowedEdges", 0) == 0, 'Reconstruction publishes only at finish'
        assert (evaluator.divisions, evaluator.reads.get("U", 0), state["ScanRow"], state["ScanWorker"]) == (0, rows, rows, 0), (
            "Refinement must advance cursors and cache U once per row", case, rows,
            evaluator.divisions, evaluator.reads.get("U", 0), state["ScanRow"], state["ScanWorker"])
        # Later passes keep their existing mask guard and write only exclusions.
        dense_seed.update(ImplicitFirstPass=False, PassScores=list(dense), AllowedEdges=list(masks))
        later = PlannerEvaluator(parse(env["refine_item"]), symbol, dense_seed)
        while dense_seed["State"] == 6:
            later.edge()
        for name in ("AllowedEdges", "RetainedColumns", "RetainedRowOffsets"):
            assert dense_seed[name] == state[name], (case, name, dense_seed[name], state[name])
        assert [bits(value) for value in dense_seed["PassScores"]] == [bits(value if allowed else -1e20) for value, allowed in zip(dense, expected_mask)]
        excluded = sum(old and not new for old, new in zip(masks, expected_mask))
        assert later.writes.get("PassScores", 0) == later.writes.get("AllowedEdges", 0) == excluded
        assert later.reads.get("V", 0) == sum(masks), "Initially forbidden dense edges must retain their guard"
        assert (later.divisions, later.reads.get("U", 0), dense_seed["ScanRow"], dense_seed["ScanWorker"]) == (0, rows, rows, 0)
        for candidate in (state, dense_seed):
            assert candidate["PassRowSecondMinCost"] == [1e20] * rows
        # Later passes must maintain both minima while scoring only CSR edges.
        state.update(ScanRow=0, ScanWorker=0, BuildIndex=0, BuildBaseOffset=0,
                     BuildRowOffset=0, RetainedCursor=0, RetainedEnd=0,
                     FirstPass=False, TemplatesReady=False, BuildRowReady=False,
                     SentinelRow=[], TemplatePlainRow=[], TemplateMinimumRow=[],
                     TemplatePlainCost=1e20, TemplatePlainSecond=1e20, TemplatePlainColumn=1,
                     TemplateMinimumCost=1e20, TemplateMinimumSecond=1e20, TemplateMinimumColumn=1,
                     RequiredWorker=[bool(rng.randrange(2)) for _ in range(columns)])
        next_scores = []
        for index, allowed in enumerate(expected_mask):
            row, worker = divmod(index, columns)
            priority = state["Priorities"][row]
            mode = (2 if not state["StrictMode"] else int(priority == state["Tier"])) if priority >= 0 and state["Tier"] >= 0 else int(priority < 0 and state["Tier"] < 0) * 3
            score = -1e20
            if allowed:
                score = 0.0
                if worker < workers:
                    raw = base[row * workers + worker]
                    if mode == 1:
                        score = fill + raw
                    elif mode == 2:
                        score = fill + (raw * (priority + 1))
                    elif mode == 3:
                        score = raw
                    if state["Minimum"][row]:
                        score = score + coverage
                if state["RequiredWorker"][worker]:
                    score = score + column
            next_scores.append(score)
        evaluator.forms = parse(env["build_item"])
        sparse_items = 0
        while not state["TemplatesReady"] or state["ScanRow"] < rows:
            evaluator.edge()
            sparse_items += 1
        assert sparse_items <= columns + 1 + rows + len(expected_columns)
        assert [bits(value) for value in state["PassScores"]] == [bits(value) for value in next_scores]
        for row in range(rows):
            costs = [0.0 - value for value in next_scores[row * columns:(row + 1) * columns]]
            assert bits(state["PassRowMinCost"][row]) == bits(min(costs))
            assert bits(state["PassRowSecondMinCost"][row]) == bits(sorted(costs)[1] if columns > 1 else 1e20)
    print(f"WO_PLANNER_IMPLICIT_GENERATION_PASS: {len(env['code'])} structured graphs, 300 matrices, {cells} refined cells")


if __name__ == "__main__":
    run()
