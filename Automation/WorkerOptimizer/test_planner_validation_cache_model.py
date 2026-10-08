"""Offline validation-cache differential test; no runtime/editor imports."""

import copy
import random
import sys

from test_planner_implicit_cost_model import bits, parser
from test_planner_implicit_generation import PlannerEvaluator, generated


class ValidationReturn(Exception):
    pass


class ValidationEvaluator(PlannerEvaluator):
    def evaluate(self, form):
        if isinstance(form, list) and form:
            head = str(form[0])
            if head == "Variables|Default|FailPlan":
                self.state["PlanDone"] = True
                self.state["PlanSucceeded"] = False
                return None
            if head == "return":
                raise ValidationReturn()
        return super().evaluate(form)

    def edge(self):
        try:
            super().edge()
        except ValidationReturn:
            pass


def initial(rng, workers, rows, case):
    pool = [-1e20, -1.0, -0.0, 0.0, 0.0001, 0.01, 0.0101, 1.0, 100.0, 1e6]
    scores = [rng.choice(pool) for _ in range(workers * rows)]
    fixed, owners = [-1] * rows, [-1] * workers
    for row in range(min(rows, workers)):
        if rng.randrange(4) == 0:
            fixed[row], owners[row] = row, row
    if case % 7 == 0:
        scores[rng.randrange(len(scores))] = rng.choice([float("nan"), float("inf"), -float("inf"), -1.01e20, 1000000.1])
    return dict(BaseScores=scores, WorkerCount=workers, FixedConfigured=bool(case % 3),
                FixedSlots=fixed, FixedOwners=owners, ScanRow=0, ScanWorker=0,
                PlanValidationIndex=0, MaxScore=0.0, PlanDone=False, PlanSucceeded=False,
                StatsOffset=0, StatsEnd=workers, StatsFirstColumn=0, StatsMaximumColumn=0,
                StatsFirstScore=-1e20, StatsMaximumScore=-1e20, StatsPrefixScore=-1e20,
                StatsSecondScore=-1e20, StatsAllReal=True, StatsUniformScore=True,
                RowAllReal=[], RowUniformScore=[], RowFirstColumn=[], RowMaximumColumn=[],
                RowFirstScore=[], RowMaximumScore=[], RowPrefixScore=[], RowSecondScore=[])


def oracle_cell(state):
    index = state["PlanValidationIndex"]
    value = state["BaseScores"][index]
    if not (-1e20 <= value <= 1e6):
        state["PlanDone"], state["PlanSucceeded"] = True, False
        return
    if state["FixedConfigured"]:
        row, worker = divmod(index, state["WorkerCount"])
        state["ScanRow"], state["ScanWorker"] = row, worker
        fixed, owner = state["FixedSlots"][row], state["FixedOwners"][worker]
        if (fixed >= 0 and fixed != worker) or (owner >= 0 and owner != row):
            state["BaseScores"][index] = value = -1e20
    if value > state["MaxScore"]:
        state["MaxScore"] = value
    if value < 0.0:
        state['StatsAllReal'] = False
    elif state['StatsFirstColumn'] and value != state['StatsFirstScore']:
        state['StatsUniformScore'] = False
    if value >= 0.0:
        column = index - state["StatsOffset"] + 1
        if state["StatsFirstColumn"] == 0:
            state["StatsFirstColumn"], state["StatsFirstScore"] = column, value
        if value > state["StatsMaximumScore"]:
            state["StatsPrefixScore"] = state["StatsMaximumScore"]
            state["StatsSecondScore"] = state["StatsMaximumScore"]
            state["StatsMaximumScore"], state["StatsMaximumColumn"] = value, column
        elif value > state["StatsSecondScore"]:
            state["StatsSecondScore"] = value
    state["PlanValidationIndex"] = index + 1
    if index + 1 == state["StatsEnd"]:
        for target, source in (("RowFirstColumn", "StatsFirstColumn"), ("RowMaximumColumn", "StatsMaximumColumn"),
                               ("RowFirstScore", "StatsFirstScore"), ("RowMaximumScore", "StatsMaximumScore"),
                               ("RowPrefixScore", "StatsPrefixScore"), ("RowSecondScore", "StatsSecondScore"),
                               ('RowAllReal', 'StatsAllReal'), ('RowUniformScore', 'StatsUniformScore')):
            state[target].append(state[source])
        state["StatsOffset"] = state["StatsEnd"]
        state["StatsEnd"] += state["WorkerCount"]
        state["StatsFirstColumn"] = state["StatsMaximumColumn"] = 0
        state['StatsAllReal'] = state['StatsUniformScore'] = True
        for name in ("StatsFirstScore", "StatsMaximumScore", "StatsPrefixScore", "StatsSecondScore"):
            state[name] = -1e20


def encoded(value):
    if isinstance(value, list):
        return [encoded(item) for item in value]
    return bits(value) if isinstance(value, float) else value


def run(design=False):
    env = generated()
    source = env["validation_cell"]("(return)")
    if design:
        load = env["a"]("BaseScores", "n")
        old = "(bind value " + load + ")"
        assert old in source, "Design replacement is only for the uncached baseline"
        source = source.replace(old, env["s"]("ValidatedScore", load) + " (bind value " + env["g"]("ValidatedScore") + ")", 1)
        mask = env["set_a"]("BaseScores", "n", "-1e20")
        assert mask in source
        source = source.replace(mask, mask + " " + env["s"]("ValidatedScore", "-1e20"), 1)
    parse, symbol = parser()
    forms = parse("(bind n (Variables|Default|GetPlanValidationIndex))" + source)
    rng = random.Random(20261015)
    cells, reads, rejected = 0, 0, 0
    for case in range(1000):
        workers, rows = rng.randint(1, 20), rng.randint(1, 12)
        expected = initial(rng, workers, rows, case)
        actual = ValidationEvaluator(forms, symbol, copy.deepcopy(expected))
        for _ in expected["BaseScores"]:
            oracle_cell(expected)
            actual.edge()
            cells += 1
            for name, value in expected.items():
                assert encoded(actual.state[name]) == encoded(value), (case, name, actual.state[name], value)
            if expected["PlanDone"]:
                rejected += 1
                break
        reads += actual.reads.get("BaseScores", 0)
    assert rejected > 100
    print(f"WO_VALIDATION_CACHE_EQUIVALENCE_PASS: {cells} cells, {rejected} rejected inputs, {reads} modeled source reads")
    assert reads == cells, "Cache each source score once; update the cache when fixed masking replaces it"
    print("WO_VALIDATION_CACHE_MODEL_PASS: exact state bits and one source read per cell")


if __name__ == "__main__":
    run(design="--design" in sys.argv)
