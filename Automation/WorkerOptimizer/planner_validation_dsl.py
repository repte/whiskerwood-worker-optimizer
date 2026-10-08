"""Exact short-circuit streaming validation statistics."""


def statistics(get, put, *, value, column):
    return f"""
      (if (< {value} 0.0) {put('StatsAllReal', 'false')}
        (else
          (if {get('StatsUniformScore')}
            (if (!= {value} {get('StatsFirstScore')})
              (if (> {get('StatsFirstColumn')} 0) {put('StatsUniformScore', 'false')})))
          (if (> {value} {get('StatsSecondScore')})
            (if (== {get('StatsFirstColumn')} 0)
              {put('StatsFirstColumn', column)} {put('StatsFirstScore', value)})
            (if (> {value} {get('StatsMaximumScore')})
              {put('StatsPrefixScore', get('StatsMaximumScore'))}
              {put('StatsSecondScore', get('StatsMaximumScore'))}
              {put('StatsMaximumScore', value)} {put('StatsMaximumColumn', column)}
              (if (> {value} {get('MaxScore')}) {put('MaxScore', value)})
              (else {put('StatsSecondScore', value)})))))
    """
