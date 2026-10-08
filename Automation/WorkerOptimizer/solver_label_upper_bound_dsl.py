"""Conservative maxima for unused labels within one Hungarian augmentation.

Existing native sorts supply the witnesses. Relaxation only decreases labels;
removing a used column shrinks the candidate set; eager subtraction is monotone.
No label arithmetic is reassociated and no root-cell traversal is introduced.
"""


UPPER_VARIABLES = {
    'UpperGlobalReady': ('bool', False), 'UpperPrefixReady': ('bool', False),
    'UpperGlobalBound': ('float', False), 'UpperPrefixBound': ('float', False),
    'UpperRow': ('int', False), 'UpperWidth': ('int', False), 'UpperPrefixWidth': ('int', False),
}


def invalidate(get, put):
    return put('UpperGlobalReady', 'false') + put('UpperPrefixReady', 'false')


def reset(get, put):
    return '\n'.join((invalidate(get, put), put('UpperGlobalBound', '0.0'),
        put('UpperPrefixBound', '0.0'), put('UpperRow', '0'), put('UpperWidth', '0'),
        put('UpperPrefixWidth', '0')))


def begin_row(get, put):
    return '\n'.join((invalidate(get, put), put('UpperRow', get('ActiveRow')),
        put('UpperWidth', get('Width')), put('UpperPrefixWidth', get('ImplicitWorkerCount'))))


def ensure_epoch(get, put):
    return f'''
      (if (or (!= {get('UpperRow')} {get('ActiveRow')})
              (or (!= {get('UpperWidth')} {get('Width')})
                  (!= {get('UpperPrefixWidth')} {get('ImplicitWorkerCount')})))
        {begin_row(get, put)})
    '''


def potential_begin(get, put, enabled=None):
    """Inside the ACTUAL nonterminal potential body, once at Cursor zero.

    Do not call this in an outer prepare/flush wrapper: such a wrapper can leave
    Cursor zero across several calls without executing the potential phase.
    """
    enabled = get('NativeDeadLabels') if enabled is None else enabled
    return f'''
      (if (== {get('Cursor')} 0)
        {ensure_epoch(get, put)}
        (if {enabled}
          (if (!= {get('Delta')} 0.0)
            (if {get('UpperGlobalReady')}
              {put('UpperGlobalBound', f'(- {get("UpperGlobalBound")} {get("Delta")})')})
            (if {get('UpperPrefixReady')}
              {put('UpperPrefixBound', f'(- {get("UpperPrefixBound")} {get("Delta")})')}))
          (else {invalidate(get, put)})))
    '''


def guarded_max(get, put, kind, original_sort, original_read, passing, enabled=None):
    """Return (setup statements, maximum expression) for an existing sort.

    passing(value) must be the existing safe no-improvement predicate, including
    any vacuous all-used-prefix condition. original_read keeps the caller's exact
    index/marker handling. Scratch arrays may remain stale on a certified hit.
    """
    assert kind in ('Global', 'Prefix')
    enabled = get('NativeDeadLabels') if enabled is None else enabled
    bound, ready = 'Upper' + kind + 'Bound', 'Upper' + kind + 'Ready'
    code = f'''
      (if {enabled}
        (if (not (and {get(ready)} {passing(get(bound))}))
          {original_sort}
          (if {get(ready)}
            (if (< {original_read} {get(bound)}) {put(bound, original_read)})
            (else {put(bound, original_read)}))
          {put(ready, 'true')})
        (else {original_sort} {put(bound, original_read)}))
    '''
    # Avoid a pure select between this field and the old array read: Blueprint
    # evaluates both inputs, but a skipped global sort may leave a short prefix
    # scratch array. The disabled branch records the original read explicitly.
    return code, get(bound)
