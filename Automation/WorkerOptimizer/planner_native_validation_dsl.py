"""Exact row-sized native validation with bounded flat-input gathering."""


NATIVE_VALIDATION_VARIABLES = {
    'int': 'NativeValidationStage NativeValidationCursor NativeValidationEnd NativeValidationBlockCount NativeValidationBlockEnd NativeValidationBlockStart',
    'float': 'NativeValidationNegativeOne NativeValidationNaN',
    'float[]': 'NativeValidationRow NativeValidationSorted NativeValidationPrefix',
    'bool[]': 'RowSingleMaximum',
}


def reset_native_validation(g, s, node):
    return '\n'.join((
        *(s(name, '0') for name in ('NativeValidationStage', 'NativeValidationCursor', 'NativeValidationEnd',
                                   'NativeValidationBlockCount', 'NativeValidationBlockEnd', 'NativeValidationBlockStart')),
        *(f'(Utilities|Array|Clear {g(name)})' for name in
          ('NativeValidationRow', 'NativeValidationSorted', 'NativeValidationPrefix', 'RowSingleMaximum')),
        s('NativeValidationNegativeOne', '-1.0'),
        s('NativeValidationNaN', f'({node("Loge")} :A {g("NativeValidationNegativeOne")})'),
    ))


def publish_statistics(g, s, single_maximum='false'):
    fields = (('RowFirstColumn', 'StatsFirstColumn'), ('RowMaximumColumn', 'StatsMaximumColumn'),
              ('RowFirstScore', 'StatsFirstScore'), ('RowMaximumScore', 'StatsMaximumScore'),
              ('RowPrefixScore', 'StatsPrefixScore'), ('RowSecondScore', 'StatsSecondScore'),
              ('RowAllReal', 'StatsAllReal'), ('RowUniformScore', 'StatsUniformScore'))
    return '\n'.join((
        *(f'(Utilities|Array|Add {g(target)} {g(source)})' for target, source in fields),
        f'(Utilities|Array|Add {g("RowSingleMaximum")} {single_maximum})',
        s('StatsAllReal', 'true'), s('StatsUniformScore', 'true'),
        s('StatsOffset', g('StatsEnd')), s('StatsEnd', f'(+ {g("StatsEnd")} {g("WorkerCount")})'),
        s('StatsFirstColumn', '0'), s('StatsMaximumColumn', '0'),
        *(s(name, '-1e20') for name in
          ('StatsFirstScore', 'StatsMaximumScore', 'StatsPrefixScore', 'StatsSecondScore')),
    ))


def activate_native_validation(g, s, length):
    return f'''
      (if (== {g('NativeValidationStage')} 0)
        (if (and (> {g('StepWorkLimit')} 1) (not {g('HasActualFixed')}))
          (if (and (> {g('WorkerCount')} 0)
                   (and (== {g('PlanValidationIndex')} {g('StatsOffset')})
                        (< {g('PlanValidationIndex')} {length('BaseScores')})))
            {s('NativeValidationCursor', g('PlanValidationIndex'))}
            (Utilities|Array|Clear {g('NativeValidationRow')})
            {s('NativeValidationStage', '1')})))
    '''


def native_validation(g, s, a, node, validation_cell, validation_finish):
    find = lambda name, value: f'({node("FindItem")} :TargetArray {g(name)} :ItemToFind {value})'
    sort = lambda name: f'({node("SortFloatArray")} :TargetArray {g(name)} :bStableSort true :SortOrder "Descending")'
    last = f'(- {g("WorkerCount")} 1)'
    single = f'''(and (> {g('WorkerCount')} 1)
      (and (> {g('StatsMaximumScore')} {g('StatsSecondScore')})
           (== {g('StatsSecondScore')} {a('NativeValidationSorted', last)})))'''
    next_row = f'''
      (Utilities|Array|Clear {g('NativeValidationRow')})
      {s('NativeValidationCursor', g('PlanValidationIndex'))}
      {s('NativeValidationStage', '1')}
    '''
    elements = []
    for index in range(64):
        offset = g('NativeValidationBlockStart') if index == 0 else f'(+ {g("NativeValidationBlockStart")} {index})'
        elements.append(f':"[{index}]" {a("BaseScores", offset)}')
    block_elements = ' '.join(elements)
    return f'''
      (switch int {g('NativeValidationStage')}
        (:0 {s('LastStepWork', '1')} ({node('FailPlan')}))
        (:1
          (if (>= {g('NativeValidationCursor')} (Utilities|Array|Length {g('BaseScores')}))
            {s('LastStepWork', '1')} {s('NativeValidationStage', '0')} {validation_finish}
            (else
              (bind remaining (- {g('StatsEnd')} {g('NativeValidationCursor')}))
              {s('LastStepWork', f'(select (< {g("StepWorkLimit")} remaining) {g("StepWorkLimit")} remaining)')}
              {s('NativeValidationEnd', f'(+ {g("NativeValidationCursor")} {g("LastStepWork")})')}
              {s('NativeValidationBlockCount', f'(/ {g("LastStepWork")} 64)')}
              {s('NativeValidationBlockEnd', f'(+ {g("NativeValidationCursor")} (* {g("NativeValidationBlockCount")} 64))')}
              (if (== {g('LastStepWork')} 64)
                {s('NativeValidationBlockStart', g('NativeValidationCursor'))}
                (Utilities|Array|AppendArray :TargetArray {g('NativeValidationRow')}
                  :SourceArray ({node('MakeArray')} {block_elements}))
                (else
                  (for part (range {g('NativeValidationBlockCount')})
                    {s('NativeValidationBlockStart', f'(+ {g("NativeValidationCursor")} (* part 64))')}
                    (Utilities|Array|AppendArray :TargetArray {g('NativeValidationRow')}
                      :SourceArray ({node('MakeArray')} {block_elements})))
                  (for index (range {g('NativeValidationBlockEnd')} {g('NativeValidationEnd')})
                    (Utilities|Array|Add {g('NativeValidationRow')} {a('BaseScores', 'index')}))))
              {s('NativeValidationCursor', g('NativeValidationEnd'))}
              (if (== {g('NativeValidationCursor')} {g('StatsEnd')}) {s('NativeValidationStage', '2')}))))
        (:2
          {s('LastStepWork', '1')}
          ; Numeric sorting is only valid after the native NaN search succeeds.
          (if (>= {find('NativeValidationRow', g('NativeValidationNaN'))} 0)
            {s('NativeValidationStage', '4')}
            (else
              {s('NativeValidationSorted', g('NativeValidationRow'))} {sort('NativeValidationSorted')}
              (if (and (<= {a('NativeValidationSorted', '0')} 1e6)
                       (>= {a('NativeValidationSorted', last)} 0.0))
                {s('NativeValidationStage', '3')}
                (else {s('NativeValidationStage', '4')})))))
        (:3
          {s('LastStepWork', '1')}
          {s('StatsFirstColumn', '1')} {s('StatsFirstScore', a('NativeValidationRow', '0'))}
          {s('StatsMaximumScore', a('NativeValidationSorted', '0'))}
          {s('StatsMaximumColumn', f'(+ {find("NativeValidationRow", g("StatsMaximumScore"))} 1)')}
          (if (> {g('WorkerCount')} 1) {s('StatsSecondScore', a('NativeValidationSorted', '1'))})
          {s('StatsAllReal', 'true')}
          {s('StatsUniformScore', f'(== {a("NativeValidationSorted", "0")} {a("NativeValidationSorted", last)})')}
          (if (> {g('StatsMaximumColumn')} 1)
            {s('NativeValidationPrefix', g('NativeValidationRow'))}
            (Utilities|Array|Resize {g('NativeValidationPrefix')} (- {g('StatsMaximumColumn')} 1))
            {sort('NativeValidationPrefix')} {s('StatsPrefixScore', a('NativeValidationPrefix', '0'))})
          (if (> {g('StatsMaximumScore')} {g('MaxScore')}) {s('MaxScore', g('StatsMaximumScore'))})
          {s('ValidatedScore', a('NativeValidationRow', last))}
          {s('PlanValidationIndex', g('NativeValidationCursor'))}
          {publish_statistics(g, s, single)}
          {next_row})
        (:4
          (for work (range {g('StepWorkLimit')})
            {s('LastStepWork', '(+ work 1)')}
            (bind n {g('PlanValidationIndex')})
            {validation_cell('(break)')}
            (if (== {g('PlanValidationIndex')} {g('StatsOffset')}) {next_row} (break))))
        (:Default {s('LastStepWork', '1')} ({node('FailPlan')})))
    '''
