"""Private exact integer residual representation for native real columns.

The opt-in is immutable for one initialized solve. Only a complete ordinary scan
can certify the live real prefix, including recertification after a fallback.
Ordinary relaxation and every augmentation receive materialized labels; the
public/default solver never enters this representation.
The optional eighths certificate changes only eligibility, not stored arithmetic.
"""

LIMIT = 2 ** 50
EIGHTHS_LIMIT = 2 ** 48
INTEGER_MINV_TYPES = {
    'bool': 'IntegerMinEnabled IntegerMinActive IntegerMinGathering IntegerMinCertified IntegerMinPhasePrepared IntegerMinCheck IntegerMinRawExact',
    'int': 'IntegerMinPrefix IntegerMinCount IntegerMinDummyCount IntegerMinEpoch IntegerMinLastLive IntegerMinFlushCursor IntegerMinFlushEnd IntegerMinIndex',
    'float': 'IntegerMinOffset IntegerMinRawUpper IntegerMinValue IntegerMinProbe IntegerMinProposedOffset IntegerMinDummyBound IntegerMinProposedDummyBound IntegerMinRawMinimum',
    'int[]': 'IntegerMinBirth',
    'float[]': 'IntegerMinZero',
}
INTEGER_MINV_VARIABLES = {
    name: (kind.removesuffix('[]'), kind.endswith('[]'))
    for kind, names in INTEGER_MINV_TYPES.items() for name in names.split()
}


def reset(get, put):
    return '\n'.join(put(name, 'false' if kind == 'bool' else '0')
                     if not array else f'(Utilities|Array|Clear {get(name)})'
                     for name, (kind, array) in INTEGER_MINV_VARIABLES.items())


def request_flush(get, put):
    return f"(if (== {get('IntegerMinFlushCursor')} 0) {put('IntegerMinFlushCursor', '1')})"


def load_value(get, put, at, index, target='IntegerMinValue'):
    """Imperative scalar decoder: inactive/new objects never read metadata.

    During a bounded flush, indices before FlushCursor are already materialized.
    Used +Inf markers pass through the subtraction and cannot enter the zero arm.
    """
    return f'''
      {put(target, at('MinV', index))}
      (if {get('IntegerMinActive')}
        (if (and (> {index} 0) (<= {index} {get('IntegerMinPrefix')}))
          (if (or (== {get('IntegerMinFlushCursor')} 0) (>= {index} {get('IntegerMinFlushCursor')}))
            {put(target, f'(- {get(target)} {get("IntegerMinOffset")})')}
            (if (== {get(target)} 0.0)
              (if (== {at('IntegerMinBirth', index)} {get('IntegerMinEpoch')})
                {put(target, at('IntegerMinZero', index))}
                (else {put(target, '0.0')}))))))
    '''


def check_value(get, put, floor_node):
    return f'''
      {put('IntegerMinCheck', 'false')}
      (if {get('DyadicEighthsEnabled')}
        (if (and (>= {get('IntegerMinProbe')} {-EIGHTHS_LIMIT}.0) (<= {get('IntegerMinProbe')} {EIGHTHS_LIMIT}.0))
          {put('IntegerMinCheck', f'(== (* {get("IntegerMinProbe")} 8.0) ({floor_node} :A (* {get("IntegerMinProbe")} 8.0)))')})
        (else
          (if (and (>= {get('IntegerMinProbe')} {-LIMIT}.0) (<= {get('IntegerMinProbe')} {LIMIT}.0))
            {put('IntegerMinCheck', f'(== {get("IntegerMinProbe")} ({floor_node} :A {get("IntegerMinProbe")}))')})))
    '''


def begin_scan(get, put):
    """At Cursor1 of a complete ordinary scan; all labels are materialized."""
    return f'''
      (if (and {get('IntegerMinEnabled')} (and (== {get('Cursor')} 1) (not {get('IntegerMinActive')})))
        {put('IntegerMinGathering', 'false')}
        (if (and {get('IntegerUActive')} (and {get('NativeDeadLabels')} {get('NativePlannerTrusted')}))
          (if (and {get('NativeUsedRealOnly')} (and (== {get('DummyCount')} 0) (== {get('Width')} {get('Cols')})))
            (if (and (> {get('ImplicitWorkerCount')} 0)
                     (and (< {get('ImplicitWorkerCount')} {get('Width')})
                          (> {get('FirstFreeColumn')} {get('ImplicitWorkerCount')})))
              {put('IntegerMinPrefix', get('ImplicitWorkerCount'))}
              {put('IntegerMinOffset', '0.0')} {put('IntegerMinEpoch', '0')}
              {put('IntegerMinCount', '0')} {put('IntegerMinRawUpper', '-1e30')}
              {put('IntegerMinDummyCount', '0')} {put('IntegerMinDummyBound', '1e30')}
              {put('IntegerMinCertified', 'true')} {put('IntegerMinRawExact', 'false')}
              {put('IntegerMinGathering', 'true')}
              (Utilities|Array|Resize {get('IntegerMinBirth')} (+ {get('IntegerMinPrefix')} 1))
              (Utilities|Array|Resize {get('IntegerMinZero')} (+ {get('IntegerMinPrefix')} 1))))))
    '''


def observe_scan(get, put, at, set_at, floor_node):
    """After every visited unused cell, including already optimal labels."""
    return f'''
      (if {get('IntegerMinGathering')}
        {put('IntegerMinValue', at('MinV', 'j'))}
        (if (<= j {get('IntegerMinPrefix')})
          {put('IntegerMinCount', f'(+ {get("IntegerMinCount")} 1)')}
          {put('IntegerMinProbe', get('IntegerMinValue'))} {check_value(get, put, floor_node)}
          (if (not {get('IntegerMinCheck')}) {put('IntegerMinCertified', 'false')})
          (if (> {get('IntegerMinValue')} {get('IntegerMinRawUpper')}) {put('IntegerMinRawUpper', get('IntegerMinValue'))})
          {set_at('IntegerMinBirth', 'j', '0')}
          {set_at('IntegerMinZero', 'j', get('IntegerMinValue'))}
          (else
            {put('IntegerMinDummyCount', f'(+ {get("IntegerMinDummyCount")} 1)')}
            (if (< {get('IntegerMinValue')} {get('IntegerMinDummyBound')})
              {put('IntegerMinDummyBound', get('IntegerMinValue'))}))))
    '''


def finish_scan(get, put):
    return f'''
      (if {get('IntegerMinGathering')}
        {put('IntegerMinGathering', 'false')}
        (if (and {get('IntegerMinCertified')}
                 (and (== {get('IntegerMinCount')} (- (+ {get('IntegerMinPrefix')} 1) {get('NativeDeadPrefixUsed')}))
                      (== {get('IntegerMinDummyCount')} (- {get('Width')} {get('IntegerMinPrefix')}))))
          {put('IntegerMinActive', 'true')} {put('IntegerMinRawExact', get('IntegerMinEnabled'))}
          {put('IntegerMinLastLive', get('IntegerMinPrefix'))}))
    '''


def domain_safe(get, offset=None, dummy_bound=None):
    offset = get('IntegerMinOffset') if offset is None else offset
    dummy_bound = get('IntegerMinDummyBound') if dummy_bound is None else dummy_bound
    return f'''(and {get('NativeDeadLabels')}
      (and {get('NativeUsedRealOnly')} (and {get('NativeDummyBoundReady')}
        (and (== {get('NativeDummyBoundRow')} {get('ActiveRow')})
          (and (> {dummy_bound} {get('IntegerMinRawUpper')})
               (> {dummy_bound} (- {get('IntegerMinRawUpper')} {offset})))))))'''


def store_improvement(get, put, at, set_at, floor_node):
    """Set only MinV. Caller must fence Way/cursor/free-cache on flush request."""
    return f'''
      (if (and {get('IntegerMinActive')} (<= j {get('IntegerMinPrefix')}))
        {put('IntegerMinProbe', get('Cur'))} {check_value(get, put, floor_node)}
        (if {get('IntegerMinCheck')}
          {put('IntegerMinProbe', f'(+ {get("Cur")} {get("IntegerMinOffset")})')}
          {check_value(get, put, floor_node)})
        (if {get('IntegerMinCheck')}
          ; Avoid Cur+0 changing a raw negative zero before the first epoch.
          (if (and {get('IntegerMinEnabled')} (== {get('IntegerMinOffset')} 0.0))
            {set_at('MinV', 'j', get('Cur'))}
            (else {set_at('MinV', 'j', get('IntegerMinProbe'))}))
          {set_at('IntegerMinBirth', 'j', get('IntegerMinEpoch'))}
          {set_at('IntegerMinZero', 'j', get('Cur'))}
          (else {request_flush(get, put)}))
        (else {set_at('MinV', 'j', get('Cur'))}))
    '''


def observe_dummy(get, put):
    return f'''
      (if {get('IntegerMinActive')}
        (if (> j {get('IntegerMinPrefix')})
          (if (< {get('Cur')} {get('IntegerMinDummyBound')})
            {put('IntegerMinDummyBound', get('Cur'))})))
    '''


def advance_dispatch(get, put, at, call):
    """Before the U/V coordinator: no pending phase has been projected yet."""
    return f'''
      (if {get('IntegerMinActive')}
        (if (> {get('IntegerMinFlushCursor')} 0) {call('IntegerMinFlush')} (return))
        (if (or (> {get('IntegerUFlushMode')} 0)
                (or (not {get('IntegerUActive')})
                    (or (== {get('SolverState')} 5) (== {get('SolverState')} 7))))
          {request_flush(get, put)} {call('IntegerMinFlush')} (return))
        (if (== {get('SolverState')} 11)
          (if (or (== {get('NativePhase')} 0) (== {get('NativePhase')} 4))
            (if (not {domain_safe(get)})
              {request_flush(get, put)} {call('IntegerMinFlush')} (return))))
        (if (and (== {get('SolverState')} 6) (== {get('Cursor')} 0))
          (if (== {at('P', get('J1'))} 0)
            {request_flush(get, put)} {call('IntegerMinFlush')} (return))
          (if (and (!= {get('Delta')} 0.0) (not {get('IntegerMinPhasePrepared')}))
            {call('IntegerMinPrepare')} (return))))
    '''


def prefix_step(get, put, at, set_at, potential_begin, dummy_begin):
    """Inside the actual deferred nonterminal body, after U/V preparation."""
    return f'''
      (if (and {get('IntegerMinActive')} (== {get('Cursor')} 0))
        {put('PotentialEnd', f'(+ {get("IntegerMinPrefix")} 1)')}
        {potential_begin} {dummy_begin}
        {put('IntegerMinDummyBound', get('IntegerMinProposedDummyBound'))}
        {put('IntegerMinOffset', get('IntegerMinProposedOffset'))}
        {put('IntegerMinEpoch', f'(+ {get("IntegerMinEpoch")} 1)')}
        {put('IntegerMinRawExact', 'false')}
        {set_at('V', '0', f'(- {at("V", "0")} {get("Delta")})')}
        (if (> {get('IntegerMinLastLive')} 0)
          {load_value(get, put, at, get('IntegerMinLastLive'), 'NativeValue')})
        {put('Cursor', get('PotentialEnd'))} {put('LastStepWork', '1')} (return))
    '''


def sources(get, put, at, set_at, floor_node):
    prepare = f'''
(fn IntegerMinPrepare ()
  {put('LastStepWork', '1')}
  (if (or (<= {get('FirstFreeColumn')} {get('IntegerMinPrefix')}) (not {domain_safe(get)}))
    {request_flush(get, put)} (return))
  {put('IntegerMinProbe', get('Delta'))} {check_value(get, put, floor_node)}
  (if (not {get('IntegerMinCheck')}) {request_flush(get, put)} (return))
  {put('IntegerMinProposedOffset', f'(+ {get("IntegerMinOffset")} {get("Delta")})')}
  {put('IntegerMinProbe', get('IntegerMinProposedOffset'))} {check_value(get, put, floor_node)}
  (if (not {get('IntegerMinCheck')}) {request_flush(get, put)} (return))
  {put('IntegerMinProposedDummyBound', f'(- {get("IntegerMinDummyBound")} {get("Delta")})')}
  (if (not {domain_safe(get, get('IntegerMinProposedOffset'), get('IntegerMinProposedDummyBound'))})
    {request_flush(get, put)} (return))
  (for work (range {get('StepWorkLimit')})
    {put('LastStepWork', '(+ work 1)')}
    (if (> {get('IntegerMinLastLive')} 0)
      (if {at('Used', get('IntegerMinLastLive'))}
        {put('IntegerMinLastLive', f'(- {get("IntegerMinLastLive")} 1)')}
        (else {put('IntegerMinPhasePrepared', 'true')} (break)))
      (else {put('IntegerMinPhasePrepared', 'true')} (break)))))
    '''
    flush_finish = f'''
    {put('IntegerMinActive', 'false')} {put('IntegerMinRawExact', 'false')}
    {put('IntegerMinGathering', 'false')}
    {put('IntegerMinOffset', '0.0')} {put('IntegerMinEpoch', '0')}
    {put('IntegerMinFlushCursor', '0')} {put('IntegerMinPhasePrepared', 'false')}
    '''
    flush = f'''
(fn IntegerMinFlush ()
  (if (and {get('IntegerMinEnabled')} (and {get('IntegerMinRawExact')}
    (and {get('IntegerMinActive')} (and (== {get('IntegerMinEpoch')} 0)
      (and (== {get('IntegerMinOffset')} 0.0) (== {get('IntegerMinFlushCursor')} 1))))))
    {put('LastStepWork', '1')}
    {put('IntegerMinFlushEnd', f'(+ {get("IntegerMinPrefix")} 1)')}
    {load_value(get, put, at, get('IntegerMinPrefix'))}
    {flush_finish} (return))
  {put('IntegerMinFlushEnd', f'(select (< (+ {get("IntegerMinFlushCursor")} {get("StepWorkLimit")}) (+ {get("IntegerMinPrefix")} 1)) (+ {get("IntegerMinFlushCursor")} {get("StepWorkLimit")}) (+ {get("IntegerMinPrefix")} 1))')}
  {put('LastStepWork', f'(- {get("IntegerMinFlushEnd")} {get("IntegerMinFlushCursor")})')}
  (for index (range {get('IntegerMinFlushCursor')} {get('IntegerMinFlushEnd')})
    {load_value(get, put, at, 'index')}
    {set_at('MinV', 'index', get('IntegerMinValue'))})
  {put('IntegerMinFlushCursor', get('IntegerMinFlushEnd'))}
  (if (> {get('IntegerMinFlushCursor')} {get('IntegerMinPrefix')})
    {flush_finish}))
    '''
    return {'IntegerMinReset': f'(fn IntegerMinReset () {reset(get, put)})',
            'IntegerMinPrepare': prepare, 'IntegerMinFlush': flush}
