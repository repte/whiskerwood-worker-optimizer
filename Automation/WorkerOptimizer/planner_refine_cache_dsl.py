"""Exact constant-real-row certificate for pass-local refinement reuse."""

from planner_cost_dsl import allowed_score


def constant_real_score(get, put, at, *, mode=None, multiplier=None, minimum=None, fill=None, coverage=None, column=None):
    """Mode1/2 uniformity is numeric: positive Fill removes signed-zero ambiguity."""
    mode = get('BuildMode') if mode is None else mode
    return f"""
      {put('RefineConstantReal', '(== ' + mode + ' 0)')}
      (if (and (>= {mode} 1) (<= {mode} 2))
        (if {at('RowUniformScore', get('ScanRow'))} {put('RefineConstantReal', 'true')}))
      (if {get('RefineConstantReal')}
        {allowed_score(get, put, output='RefineConstantScore',
          base=at('RowFirstScore', get('ScanRow')), mode=mode,
          multiplier=get('BuildMultiplier') if multiplier is None else multiplier,
          minimum=get('BuildMinimum') if minimum is None else minimum,
          required='false', fill=get('FillBonus') if fill is None else fill,
          coverage=get('CoverageBonus') if coverage is None else coverage,
          column=get('ColumnBonus') if column is None else column)})
    """
