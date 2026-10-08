"""Isolated Used-V deferral; production integer-U defaults remain unchanged."""

import copy

from solver_integer_u_dsl import sources


def prototype_graphs(reference, symbol):
    from test_solver_native_relaxation_model import parser, check_structure
    parse, parsed_symbol = parser()
    names = {name: name.replace('IntegerU', 'IntegerV', 1) for name in
             ('IntegerUPrepareRow', 'IntegerUFlush', 'IntegerUAdvancePotentials', 'IntegerUDeferredPotentials')}

    def convert(value):
        if isinstance(value, list):
            return [convert(item) for item in value]
        return symbol(str(value)) if isinstance(value, parsed_symbol) else value

    def forms(source):
        return convert(parse(source))

    def rename(value):
        if isinstance(value, list):
            return [rename(item) for item in value]
        if isinstance(value, symbol):
            text = str(value)
            if text in names:
                return symbol(names[text])
            prefix = 'Variables|Default|'
            if text.startswith(prefix) and text[len(prefix):] in names:
                return symbol(prefix + names[text[len(prefix):]])
        return value

    result = copy.deepcopy(reference)
    for name, source in sources(defer_v=True).items():
        if name in names:
            result[names[name]] = rename(forms(source))
    guarded = 0

    def omit_v(value):
        nonlocal guarded
        if not isinstance(value, list):
            return value
        name = str(value[0]) if value else ''
        array_v = name == 'Utilities|Array|SetArrayElem' and str(value[2][0]) == 'Variables|Default|GetV'
        ref_v = (name == 'Variables|SetBy-RefVar' and str(value[2][0]) == 'Utilities|Array|Get(aref)'
                 and str(value[2][2][0]) == 'Variables|Default|GetV')
        if array_v or ref_v:
            index = value[4] if array_v else value[2][4]
            assert str(index) == 'j'
            guarded += 1
            return [symbol('if'), [symbol('=='), index, 0], value]
        return [omit_v(item) for item in value]

    deferred = omit_v(copy.deepcopy(reference['IntegerUDeferredPotentials']))
    deferred[0][1] = symbol('IntegerVDeferredPotentials')
    result['IntegerVDeferredPotentials'] = deferred
    assert guarded == 4, ('Exactly four eager V sites retain only V0', guarded)
    result['IntegerVAdvance'] = forms('''(fn IntegerVAdvance ()
      (Variables|Default|SetLastStepWork 0)
      (if (Variables|Default|GetDone) (return))
      (if (<= (Variables|Default|GetStepWorkLimit) 0) (Variables|Default|Advance) (return))
      (if (and (Variables|Default|GetIntegerUEnabled)
          (and (Variables|Default|GetNativePlannerTrusted)
            (and (== (Variables|Default|GetDummyCount) 0)
                 (== (Variables|Default|GetWidth) (Variables|Default|GetCols)))))
        (if (> (Variables|Default|GetIntegerUFlushMode) 0) (Variables|Default|IntegerVFlush) (return))
        (if (and (== (Variables|Default|GetSolverState) 4)
                 (not (Variables|Default|GetIntegerURowPrepared)))
          (Variables|Default|IntegerVPrepareRow) (return))
        (if (== (Variables|Default|GetSolverState) 6) (Variables|Default|IntegerVAdvancePotentials) (return)))
      (Variables|Default|Advance))''')
    check_structure(result)
    return result


def projected_v(state):
    result = list(state['V'])
    if not state.get('IntegerUEnabled') or not state.get('IntegerUActive'):
        return result
    for position, column in enumerate(state.get('UsedColumns', [])):
        if column == 0:
            continue
        prefix, epoch = state['IntegerUTotal'], state['IntegerUEpoch']
        if state.get('IntegerUPhasePrepared') and state.get('IntegerUPhaseNonzero'):
            processed = position < state['Cursor'] if state['IntegerUPhaseTerminal'] else column < state['Cursor']
            if not processed:
                prefix -= state['Delta']
                epoch -= 1
        if state['IntegerUEpochs'][column] != epoch:
            value = result[column] - (prefix - state['IntegerUOffsets'][column])
            result[column] = 0.0 if value == 0.0 else value
    return result


def advance_shadows(before, after, u, v):
    """Independent eager arithmetic from phase/cursor, never observed writes."""
    if before['SolverState'] != 6 or before['IntegerUFlushMode']:
        return
    rejected = after['IntegerUFlushMode'] == 1 and not before['IntegerUPhasePrepared']
    if before['Delta'] == 0.0 or rejected:
        return
    terminal = before['P'][before['J1']] == 0
    columns = (before['UsedColumns'][before['Cursor']:after['Cursor']] if terminal else
               [j for j in range(before['Cursor'], after['Cursor']) if j in before['UsedColumns']])
    for column in columns:
        row = before['P'][column]
        u[row] = u[row] + before['Delta']
        v[column] = v[column] - before['Delta']
