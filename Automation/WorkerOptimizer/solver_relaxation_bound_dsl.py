"""Inline exact lower-bound relaxation certificate for Hungarian scans.

The second minimum is an order statistic of explicit column costs, counting
equal minima separately. Nonpositive V makes cost minus U a reduced-cost lower
bound under the existing floating-point operation order.
"""


def bound_setup(get, put, at):
    """Cache a lower reduced-cost bound for all currently unvisited columns."""
    row = f'(- {get("I0")} 1)'
    minimum_column = at("RowMinColumn", row)
    dummy_cost = f'(select {at("DummyAllowed", row)} 0.0 1e29)'
    return f"""
      {put('RelaxationBoundEnabled', 'false')}
      (if (and (!= {get('J0')} 0) {get('NonpositiveV')})
        {put('RelaxationLowerBound', at('RowMinCost', row))}
        (if (and (> {minimum_column} 0) (<= {minimum_column} {get('Cols')}))
          (if {at('Used', minimum_column)}
            {put('RelaxationLowerBound', at('RowSecondMinCost', row))}))
        (if (> {get('DummyCount')} 0)
          (if (< {dummy_cost} {get('RelaxationLowerBound')})
            {put('RelaxationLowerBound', dummy_cost)}))
        {put('RelaxationLowerBound', f'(- {get("RelaxationLowerBound")} {get("RowPotential")})')}
        {put('RelaxationBoundEnabled', 'true')})
    """


def bounded_edge(get, put, at, relax_cost, relax_choose):
    """Replace only strictly non-improving cost reads; keep original tie logic."""
    return f"""
      (bind j {get('Cursor')})
      (if (not {at('Used', 'j')})
        (if (<= {at('MinV', 'j')} {get('RelaxationLowerBound')})
          {put('Cur', at('MinV', 'j'))}
          (else {relax_cost}))
        {relax_choose})
      {put('Cursor', f'(+ {get("Cursor")} 1)')}
    """
