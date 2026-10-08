"""Exact full-real cache and native-row reconstruction fragments."""

RECONSTRUCTION_VARIABLES = {
    'bool': 'RefineReconstruct RefineFullReal RefineConstantReal RefineSingleton RefineCacheHit RefineCacheEligible RefinePlainCacheReady RefineMinimumCacheReady StatsAllReal StatsUniformScore',
    'int': 'RefineStage RefineOldStart RefineOldEnd',
    'float': 'RefineConstantScore RefinePlainCacheScore RefineMinimumCacheScore RefinePlainCacheU RefineMinimumCacheU',
    'bool[]': 'RowAllReal RowUniformScore RefineFalseRow RefineRowMask RefineOutputMask RefinePlainCacheMask RefineMinimumCacheMask',
    'float[]': 'RefineRowScores RefineOutputScores RefinePlainCacheScores RefineMinimumCacheScores',
    'int[]': 'RefineRealColumns RefineOutputColumns RefineOutputOffsets RefinePlainCacheColumns RefineMinimumCacheColumns',
}


def start_reconstruction(get, put):
    cleared = ('RefineOutputMask', 'RefineOutputScores', 'RefineOutputColumns', 'RefineOutputOffsets',
               'RefineFalseRow', 'RefineRowScores')
    return '\n'.join(f'(Utilities|Array|Clear {get(name)})' for name in cleared) + f"""
      (Utilities|Array|Resize {get('RefineFalseRow')} {get('SolveColumns')})
      {put('RefinePlainCacheReady', 'false')}
      {put('RefineMinimumCacheReady', 'false')}
    """


def start_payload(get, put):
    return f"""
      {put('RefineRowMask', get('RefineFalseRow'))}
      (if (not {get('ImplicitFirstPass')}) {put('RefineRowScores', get('SentinelRow'))})
      (Utilities|Array|Clear {get('RefineRealColumns')})
    """


def full_real_certificate(get, put, at):
    last_real = f"(- (+ {get('RefineOldStart')} {get('WorkerCount')}) 1)"
    full_prefix = f"(== {at('RetainedColumns', last_real)} (- {get('WorkerCount')} 1))"
    return f"""
      {put('RefineFullReal', 'false')}
      (if (> {get('WorkerCount')} 1)
        (if {get('ImplicitFirstPass')}
          {put('RefineFullReal', f"(and {at('RowAllReal', get('ScanRow'))} (and {get('ImplicitRealAllowed')} (< {get('ImplicitFixedWorker')} 0)))")}
          (elif {get('RetainedReady')}
            (if (>= (- {get('RefineOldEnd')} {get('RefineOldStart')}) {get('WorkerCount')})
              {put('RefineFullReal', full_prefix)}))))
    """


def cache_lookup(get, put):
    def branch(prefix):
        return f"""
          (if (and {get(prefix + 'Ready')}
                (and (== {get(prefix + 'Score')} {get('RefineConstantScore')})
                     (== {get(prefix + 'U')} {get('RefineRowPotential')})))
            {put('RefineCacheHit', 'true')}
            {put('RefineRowMask', get(prefix + 'Mask'))}
            {put('RefineRowScores', get(prefix + 'Scores'))}
            {put('RefineRealColumns', get(prefix + 'Columns'))})
        """
    return f"""
      {put('RefineCacheHit', 'false')}
      {put('RefineCacheEligible', f"(and {get('RefineFullReal')} (and {get('RefineConstantReal')} (not {get('RefineSingleton')})))")}
      (if {get('RefineCacheEligible')}
        (if {get('BuildMinimum')}
          {branch('RefineMinimumCache')}
          (else {branch('RefinePlainCache')})))
    """


def cache_store(get, put):
    def branch(prefix):
        return "\n".join(put(prefix + target, get(source)) for target, source in (
            ('Score', 'RefineConstantScore'), ('U', 'RefineRowPotential'),
            ('Mask', 'RefineRowMask'), ('Scores', 'RefineRowScores'),
            ('Columns', 'RefineRealColumns'))) + put(prefix + 'Ready', 'true')
    return f"""
      (if (and {get('RefineCacheEligible')} (not {get('RefineCacheHit')}))
        (if {get('BuildMinimum')}
          {branch('RefineMinimumCache')}
          (else {branch('RefinePlainCache')})))
    """


def append_row(get):
    return f"""
      (Utilities|Array|Add {get('RefineOutputOffsets')} (Utilities|Array|Length {get('RefineOutputColumns')}))
      (Utilities|Array|AppendArray {get('RefineOutputMask')} {get('RefineRowMask')})
      (if (not {get('ImplicitFirstPass')})
        (Utilities|Array|AppendArray {get('RefineOutputScores')} {get('RefineRowScores')}))
      (Utilities|Array|AppendArray {get('RefineOutputColumns')} {get('RefineRealColumns')})
    """


def retain_dummy(get, set_at):
    index = f"(+ (* {get('ScanRow')} {get('SolveColumns')}) {get('ScanWorker')})"
    return f"""
      {set_at('RefineOutputMask', index, 'true')}
      (if (not {get('ImplicitFirstPass')})
        {set_at('RefineOutputScores', index, get('EdgeScore'))})
      (Utilities|Array|Add {get('RefineOutputColumns')} {get('ScanWorker')})
    """


def finish_reconstruction(get, put):
    return f"""
      (Utilities|Array|Add {get('RefineOutputOffsets')} (Utilities|Array|Length {get('RefineOutputColumns')}))
      {put('AllowedEdges', get('RefineOutputMask'))}
      {put('PassScores', get('RefineOutputScores'))}
      {put('RetainedColumns', get('RefineOutputColumns'))}
      {put('RetainedRowOffsets', get('RefineOutputOffsets'))}
      {put('RetainedReady', 'true')}
    """
