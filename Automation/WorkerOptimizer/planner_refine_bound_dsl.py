"""Exact real-prefix singleton bound for first implicit refinement.

For every non-winning real column, cost >= the second explicit row cost and
V[column] <= max_real_v. Correctly ordered finite subtraction is monotone, so
(second_cost - U) - max_real_v is a lower bound on its reduced cost. A strict
bound above the existing tight-edge tolerance proves it cannot be retained.
"""


def max_real_v_start(get, put):
    return f"""
      {put('RefineMaxVCursor', '0')}
      {put('RefineMaxRealV', '0.0')}
      {put('RefineMaxVReady', f'(or (not {get("ImplicitFirstPass")}) (== {get("WorkerCount")} 0))')}
    """


def max_real_v_step(get, put, at):
    value = at('V', f'(+ {get("RefineMaxVCursor")} 1)')
    return f"""
      (if (== {get('RefineMaxVCursor')} 0) {put('RefineMaxRealV', value)}
        (elif (> {value} {get('RefineMaxRealV')}) {put('RefineMaxRealV', value)}))
      {put('RefineMaxVCursor', f'(+ {get("RefineMaxVCursor")} 1)')}
      (if (== {get('RefineMaxVCursor')} {get('WorkerCount')}) {put('RefineMaxVReady', 'true')})
    """


def singleton_real_range(get, put, at):
    return f"""
      (if (and {get('ImplicitRealAllowed')} {get('RefineMaxVReady')})
        {put('RefineWinner', at('RowMinColumn', get('ScanRow')))}
        (if (and (> {get('RefineWinner')} 0) (<= {get('RefineWinner')} {get('WorkerCount')}))
          (if (> (- (- {at('RowSecondMinCost', get('ScanRow'))} {get('RefineRowPotential')}) {get('RefineMaxRealV')}) 0.00001)
            {put('ScanWorker', f'(- {get("RefineWinner")} 1)')}
            {put('RefineRangeEnd', get('RefineWinner'))})))
    """
