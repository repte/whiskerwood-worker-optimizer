"""Exact full-real CSR templates for a certified single raw-score maximum.

The validator proves every other raw value is numerically equal. Positive fill
and multiplier make their mode1/2 transformed scores bit-identical, including
raw signed zeros. Each pass keeps its first plain/minimum background template;
a different key falls back rather than repeatedly rebuilding a cache.
"""

from planner_cost_dsl import allowed_score


SINGLE_MAXIMUM_VARIABLES = {
    "bool": "SingleTemplateBuilding SingleTemplateHandled SinglePlainReady SingleMinimumReady",
    "int": "SingleTemplateCursor SingleTemplateColumn SinglePlainColumn SingleMinimumColumn SingleHighColumn",
    "float": "SingleBackground SingleTemplateCost SingleTemplateSecond SinglePlainKey SinglePlainCost SinglePlainSecond SingleMinimumKey SingleMinimumCost SingleMinimumSecond SingleCost",
    "float[]": "SingleTemplateRow SinglePlainRow SingleMinimumRow",
}


def single_maximum_reset(g, s):
    return f"""
    {s('SingleTemplateBuilding', 'false')} {s('SingleTemplateHandled', 'false')}
    {s('SinglePlainReady', 'false')} {s('SingleMinimumReady', 'false')}
    """


def _score(g, s, a, base, required):
    return allowed_score(
        g, s, output='EdgeScore', base=base, mode=g('BuildMode'),
        multiplier=g('BuildMultiplier'), minimum=g('BuildMinimum'),
        required=required, fill=g('FillBonus'), coverage=g('CoverageBonus'),
        column=g('ColumnBonus'), real='true')


def _apply(g, s, a, set_a):
    return f"""
    (Utilities|Array|AppendArray {g('PassScores')} {g('SingleTemplateRow')})
    {s('SingleHighColumn', a('RowMaximumColumn', g('ScanRow')))}
    {_score(g, s, a, a('RowMaximumScore', g('ScanRow')), a('RequiredWorker', f'(- {g("SingleHighColumn")} 1)'))}
    {set_a('PassScores', f'(- (+ {g("BuildRowOffset")} {g("SingleHighColumn")}) 1)', g('EdgeScore'))}
    {s('SingleCost', f'(- {g("EdgeScore")})')}
    ; Lowering one entry never needs a third order statistic.
    (if (< {g('SingleCost')} {g('SingleTemplateCost')})
      (if (!= {g('SingleHighColumn')} {g('SingleTemplateColumn')})
        {s('SingleTemplateSecond', g('SingleTemplateCost'))})
      {s('SingleTemplateCost', g('SingleCost'))}
      {s('SingleTemplateColumn', g('SingleHighColumn'))}
      (elif (!= {g('SingleHighColumn')} {g('SingleTemplateColumn')})
        (if (< {g('SingleCost')} {g('SingleTemplateSecond')})
          {s('SingleTemplateSecond', g('SingleCost'))})
        (if (and (== {g('SingleCost')} {g('SingleTemplateCost')}) (< {g('SingleHighColumn')} {g('SingleTemplateColumn')}))
          {s('SingleTemplateColumn', g('SingleHighColumn'))})))
    {set_a('PassRowMinCost', g('ScanRow'), g('SingleTemplateCost'))}
    {set_a('PassRowSecondMinCost', g('ScanRow'), g('SingleTemplateSecond'))}
    {set_a('PassRowMinColumn', g('ScanRow'), g('SingleTemplateColumn'))}
    {s('RetainedCursor', f'(+ {g("RetainedCursor")} {g("WorkerCount")})')}
    {s('SingleTemplateBuilding', 'false')}
    """


def _cache_get(g, s, a, set_a, prefix):
    return f"""
    {s('SingleTemplateRow', g(prefix + 'Row'))}
    {s('SingleTemplateCost', g(prefix + 'Cost'))}
    {s('SingleTemplateSecond', g(prefix + 'Second'))}
    {s('SingleTemplateColumn', g(prefix + 'Column'))}
    {s('SingleTemplateHandled', 'true')}
    {_apply(g, s, a, set_a)}
    """


def _cache_start(g, s):
    return f"""
    {s('SingleTemplateRow', g('SentinelRow'))}
    {s('SingleTemplateCost', '1e20')} {s('SingleTemplateSecond', '1e20')}
    {s('SingleTemplateColumn', '1')} {s('SingleTemplateCursor', '0')}
    {s('SingleTemplateHandled', 'true')} {s('SingleTemplateBuilding', 'true')}
    """


def _choose_cache(g, s, a, set_a, prefix):
    return f"""
    (if {g(prefix + 'Ready')}
      (if (== {g('SingleBackground')} {g(prefix + 'Key')})
        {_cache_get(g, s, a, set_a, prefix)})
      (else {_cache_start(g, s)}))
    """


def single_maximum_begin(g, s, a, set_a):
    """After row setup/CSR bounds; handled rows append here or during cell()."""
    return f"""
    {s('SingleTemplateHandled', 'false')} {s('SingleTemplateBuilding', 'false')}
    (if (and (or (== {g('BuildMode')} 1) (== {g('BuildMode')} 2)) (>= {g('WorkerCount')} 2))
      (if (and (> {g('FillBonus')} 0.0) (> {g('BuildMultiplier')} 0))
        (if {a('RowSingleMaximum', g('ScanRow'))}
          (if (and (> {a('RowMaximumColumn', g('ScanRow'))} 0) (<= {a('RowMaximumColumn', g('ScanRow'))} {g('WorkerCount')}))
            (if (>= (- {g('RetainedEnd')} {g('RetainedCursor')}) {g('WorkerCount')})
              (if (== {a('RetainedColumns', f'(- (+ {g("RetainedCursor")} {g("WorkerCount")}) 1)')} (- {g('WorkerCount')} 1))
                {_score(g, s, a, a('RowSecondScore', g('ScanRow')), 'false')}
                {s('SingleBackground', g('EdgeScore'))}
                (if {g('BuildMinimum')}
                  {_choose_cache(g, s, a, set_a, 'SingleMinimum')}
                  (else {_choose_cache(g, s, a, set_a, 'SinglePlain')}))))))))
    """


def _cache_store(g, s, prefix):
    return f"""
    {s(prefix + 'Key', g('SingleBackground'))}
    {s(prefix + 'Row', g('SingleTemplateRow'))}
    {s(prefix + 'Cost', g('SingleTemplateCost'))}
    {s(prefix + 'Second', g('SingleTemplateSecond'))}
    {s(prefix + 'Column', g('SingleTemplateColumn'))}
    {s(prefix + 'Ready', 'true')}
    """


def single_maximum_cell(g, s, a, set_a):
    """One real column per budgeted item; existing suffix processing is untouched."""
    return f"""
    {s('EdgeScore', g('SingleBackground'))}
    (if {a('RequiredWorker', g('SingleTemplateCursor'))}
      {s('EdgeScore', f'(+ {g("EdgeScore")} {g("ColumnBonus")})')})
    {set_a('SingleTemplateRow', g('SingleTemplateCursor'), g('EdgeScore'))}
    {s('SingleCost', f'(- {g("EdgeScore")})')}
    (if (< {g('SingleCost')} {g('SingleTemplateCost')})
      {s('SingleTemplateSecond', g('SingleTemplateCost'))}
      {s('SingleTemplateCost', g('SingleCost'))}
      {s('SingleTemplateColumn', f'(+ {g("SingleTemplateCursor")} 1)')}
      (elif (< {g('SingleCost')} {g('SingleTemplateSecond')})
        {s('SingleTemplateSecond', g('SingleCost'))}))
    {s('SingleTemplateCursor', f'(+ {g("SingleTemplateCursor")} 1)')}
    (if (>= {g('SingleTemplateCursor')} {g('WorkerCount')})
      ; Store before either the exception or later dummy patches mutate output.
      (if {g('BuildMinimum')}
        {_cache_store(g, s, 'SingleMinimum')}
        (else {_cache_store(g, s, 'SinglePlain')}))
      {_apply(g, s, a, set_a)})
    """
