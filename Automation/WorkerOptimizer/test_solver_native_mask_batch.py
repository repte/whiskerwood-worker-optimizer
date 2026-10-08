"""Per-call native-mask loop equivalence with a frozen full legacy graph.

LEGACY_DSL was emitted before the stable-end loop change. It is compiled only
into an unsaved child; all production phases except phase 3 remain shared.
The offline RED also measures actual emitted cursor-property writes.
"""

LEGACY_DSL = "(fn AdvanceNativeRelaxation () (Variables|Default|SetLastStepWork 0) (if (Variables|Default|GetDone) (return)) (switch int (Variables|Default|GetNativePhase) (:0 (Variables|Default|SetNativeMaxScratch (Variables|Default|GetMinV)) (Utilities|Array|Resize (Variables|Default|GetNativeMaxScratch) (+ (Variables|Default|GetWidth) 1)) (Utilities|Array|Sort|SortFloatArray :TargetArray (Variables|Default|GetNativeMaxScratch) :bStableSort false) (if (<= (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeMaxScratch) :\"Dimension 1\" (Variables|Default|GetWidth)) (- 1e+20 (Variables|Default|GetRowPotential))) (Variables|Default|SetNativePhase 1) (if (Variables|Default|GetImplicitFirstPass) (if (> (Variables|Default|GetImplicitWorkerCount) 0) (Variables|Default|SetNativeMaxScratch (Variables|Default|GetMinV)) (Utilities|Array|Resize (Variables|Default|GetNativeMaxScratch) (+ (Variables|Default|GetImplicitWorkerCount) 1)) (Utilities|Array|Sort|SortFloatArray :TargetArray (Variables|Default|GetNativeMaxScratch) :bStableSort false) (if (> (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeMaxScratch) :\"Dimension 1\" (Variables|Default|GetImplicitWorkerCount)) (Variables|Default|GetRelaxationLowerBound)) (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false)))) (if (== (Variables|Default|GetSolverState) 11) (if (Variables|Default|GetImplicitFirstPass) (Variables|Default|SetNativeCursor (Variables|Default|GetImplicitDummyStart)) (Variables|Default|SetNativeEnd (Variables|Default|GetImplicitDummyStart)) (if (Variables|Default|GetImplicitDummyAllowed) (Variables|Default|SetNativeEnd (Variables|Default|GetImplicitDummyEnd))) (else (if (== (Utilities|Array|Length (Variables|Default|GetNativeRowOffsets)) (+ (Variables|Default|GetRows) 1)) (Variables|Default|SetNativeCursor (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeRowOffsets) :\"Dimension 1\" (- (Variables|Default|GetI0) 1))) (Variables|Default|SetNativeEnd (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeRowOffsets) :\"Dimension 1\" (Variables|Default|GetI0))) (if (or (< (Variables|Default|GetNativeCursor) 0) (or (< (Variables|Default|GetNativeEnd) (Variables|Default|GetNativeCursor)) (> (Variables|Default|GetNativeEnd) (Utilities|Array|Length (Variables|Default|GetNativeColumns))))) (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false) (else (if (and (Variables|Default|GetNativeCsrReady) (and (Variables|Default|GetNonpositiveV) (Variables|Default|GetRelaxationBoundEnabled))) (bind hint (Variables|Default|GetImplicitWorkerCount)) (if (and (> hint 0) (<= hint (Variables|Default|GetCols))) (if (>= (- (Variables|Default|GetNativeEnd) (Variables|Default|GetNativeCursor)) hint) (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeColumns) :\"Dimension 1\" (- (+ (Variables|Default|GetNativeCursor) hint) 1)) (- hint 1)) (Variables|Default|SetNativeMaxScratch (Variables|Default|GetMinV)) (Utilities|Array|Resize (Variables|Default|GetNativeMaxScratch) (+ hint 1)) (Utilities|Array|Sort|SortFloatArray :TargetArray (Variables|Default|GetNativeMaxScratch) :bStableSort false) (if (<= (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeMaxScratch) :\"Dimension 1\" hint) (Variables|Default|GetRelaxationLowerBound)) (Variables|Default|SetNativeCursor (+ (Variables|Default|GetNativeCursor) hint))))))))) (else (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false))))) (if (Variables|Default|GetNativeMaskReady) (if (and (== (Variables|Default|GetNativeMaskRow) (Variables|Default|GetActiveRow)) (== (Utilities|Array|Length (Variables|Default|GetNativeMasked)) (+ (Variables|Default|GetWidth) 1))) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetNativeMasked) :Index (Variables|Default|GetJ0) :Item 1e+30) (else (Variables|Default|SetNativeMaskReady false))))) (else (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false))) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))) (:1 (if (Variables|Default|GetImplicitFirstPass) (for work (range (Variables|Default|GetStepWorkLimit)) (if (>= (Variables|Default|GetNativeCursor) (Variables|Default|GetNativeEnd)) (break)) (Variables|Default|SetNativeColumn (+ (Variables|Default|GetNativeCursor) 1)) (if (or (< (Variables|Default|GetNativeColumn) 1) (> (Variables|Default|GetNativeColumn) (Variables|Default|GetCols))) (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)) (break)) (bind j (Variables|Default|GetNativeColumn)) (if (not (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsed) :\"Dimension 1\" j)) (if (<= j (Variables|Default|GetCols)) (Variables|Default|SetCur -1e+20) (if (< (- j 1) (Variables|Default|GetImplicitWorkerCount)) (if (Variables|Default|GetImplicitRealAllowed) (Variables|Default|SetImplicitBaseValue (Utilities|Array|Get(aref) :Array (Variables|Default|GetImplicitScores) :\"Dimension 1\" (+ (Variables|Default|GetImplicitRowOffset) (- j 1)))) (if (>= (Variables|Default|GetImplicitBaseValue) 0.0) (Variables|Default|SetCur 0.0) (if (== (Variables|Default|GetImplicitMode) 1) (Variables|Default|SetCur (+ (Variables|Default|GetImplicitFillBonus) (Variables|Default|GetImplicitBaseValue))) (elif (== (Variables|Default|GetImplicitMode) 2) (Variables|Default|SetCur (+ (Variables|Default|GetImplicitFillBonus) (* (Variables|Default|GetImplicitBaseValue) (Variables|Default|GetImplicitMultiplier)))) (elif (== (Variables|Default|GetImplicitMode) 3) (Variables|Default|SetCur (Variables|Default|GetImplicitBaseValue))))) (if (Variables|Default|GetImplicitMinimum) (Variables|Default|SetCur (+ (Variables|Default|GetCur) (Variables|Default|GetImplicitCoverageBonus)))) (if (== (- j 1) (Variables|Default|GetImplicitFixedWorker)) (Variables|Default|SetCur (+ (Variables|Default|GetCur) (Variables|Default|GetImplicitColumnBonus)))))) (else (if (and (Variables|Default|GetImplicitDummyAllowed) (and (>= (- j 1) (Variables|Default|GetImplicitDummyStart)) (< (- j 1) (Variables|Default|GetImplicitDummyEnd)))) (Variables|Default|SetCur 0.0)))) (Variables|Default|SetCur (- (Variables|Default|GetCur))) (else (Variables|Default|SetCur (select (Utilities|Array|Get(aref) :Array (Variables|Default|GetDummyAllowed) :\"Dimension 1\" (- (Variables|Default|GetI0) 1)) 0.0 1e+29)))) (Variables|Default|SetCur (- (- (Variables|Default|GetCur) (Variables|Default|GetRowPotential)) (Utilities|Array|Get(aref) :Array (Variables|Default|GetV) :\"Dimension 1\" j))) (if (== (Variables|Default|GetJ0) 0) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (Variables|Default|GetCur)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetWay) :Index j :Item (Variables|Default|GetJ0)) (elif (< (Variables|Default|GetCur) (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (Variables|Default|GetCur)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetWay) :Index j :Item (Variables|Default|GetJ0)) (else (Variables|Default|SetCur (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j))))) (if (Variables|Default|GetNativeMaskReady) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetNativeMasked) :Index j :Item (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j))) (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :\"Dimension 1\" j) 0) (if (< (Variables|Default|GetCur) (Variables|Default|GetNativeFreeMinimum)) (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetCur)) (Variables|Default|SetNativeFreeColumn j) (elif (== (Variables|Default|GetCur) (Variables|Default|GetNativeFreeMinimum)) (if (< j (Variables|Default|GetNativeFreeColumn)) (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetCur)) (Variables|Default|SetNativeFreeColumn j)))))) (Variables|Default|SetNativeCursor (+ (Variables|Default|GetNativeCursor) 1)) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))) (else (for work (range (Variables|Default|GetStepWorkLimit)) (if (>= (Variables|Default|GetNativeCursor) (Variables|Default|GetNativeEnd)) (break)) (Variables|Default|SetNativeColumn (+ (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeColumns) :\"Dimension 1\" (Variables|Default|GetNativeCursor)) 1)) (if (or (< (Variables|Default|GetNativeColumn) 1) (> (Variables|Default|GetNativeColumn) (Variables|Default|GetCols))) (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)) (break)) (bind j (Variables|Default|GetNativeColumn)) (if (not (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsed) :\"Dimension 1\" j)) (if (<= j (Variables|Default|GetCols)) (Variables|Default|SetCur (- (Utilities|Array|Get(aref) :Array (Variables|Default|GetScores) :\"Dimension 1\" (+ (Variables|Default|GetRowScoreOffset) j)))) (else (Variables|Default|SetCur (select (Utilities|Array|Get(aref) :Array (Variables|Default|GetDummyAllowed) :\"Dimension 1\" (- (Variables|Default|GetI0) 1)) 0.0 1e+29)))) (Variables|Default|SetCur (- (- (Variables|Default|GetCur) (Variables|Default|GetRowPotential)) (Utilities|Array|Get(aref) :Array (Variables|Default|GetV) :\"Dimension 1\" j))) (if (== (Variables|Default|GetJ0) 0) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (Variables|Default|GetCur)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetWay) :Index j :Item (Variables|Default|GetJ0)) (elif (< (Variables|Default|GetCur) (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetMinV) :Index j :Item (Variables|Default|GetCur)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetWay) :Index j :Item (Variables|Default|GetJ0)) (else (Variables|Default|SetCur (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j))))) (if (Variables|Default|GetNativeMaskReady) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetNativeMasked) :Index j :Item (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" j))) (if (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :\"Dimension 1\" j) 0) (if (< (Variables|Default|GetCur) (Variables|Default|GetNativeFreeMinimum)) (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetCur)) (Variables|Default|SetNativeFreeColumn j) (elif (== (Variables|Default|GetCur) (Variables|Default|GetNativeFreeMinimum)) (if (< j (Variables|Default|GetNativeFreeColumn)) (Variables|Default|SetNativeFreeMinimum (Variables|Default|GetCur)) (Variables|Default|SetNativeFreeColumn j)))))) (Variables|Default|SetNativeCursor (+ (Variables|Default|GetNativeCursor) 1)) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))))) (if (== (Variables|Default|GetSolverState) 11) (if (>= (Variables|Default|GetNativeCursor) (Variables|Default|GetNativeEnd)) (Variables|Default|SetNativePhase (select (Variables|Default|GetNativeMaskReady) 4 2)))) (if (== (Variables|Default|GetLastStepWork) 0) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)))) (:2 (Variables|Default|SetNativeMasked (Variables|Default|GetMinV)) (Utilities|Array|Resize (Variables|Default|GetNativeMasked) (+ (Variables|Default|GetWidth) 1)) (Variables|Default|SetNativeCursor 0) (Variables|Default|SetNativePhase 3) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))) (:3 (for work (range (Variables|Default|GetStepWorkLimit)) (if (>= (Variables|Default|GetNativeCursor) (Utilities|Array|Length (Variables|Default|GetUsedColumns))) (break)) (Utilities|Array|SetArrayElem :TargetArray (Variables|Default|GetNativeMasked) :Index (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsedColumns) :\"Dimension 1\" (Variables|Default|GetNativeCursor)) :Item 1e+30) (Variables|Default|SetNativeCursor (+ (Variables|Default|GetNativeCursor) 1)) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))) (if (>= (Variables|Default|GetNativeCursor) (Utilities|Array|Length (Variables|Default|GetUsedColumns))) (Variables|Default|SetNativePhase 4)) (if (== (Variables|Default|GetLastStepWork) 0) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)))) (:4 (Variables|Default|SetNativeSorted (Variables|Default|GetNativeMasked)) (Utilities|Array|Sort|SortFloatArray :TargetArray (Variables|Default|GetNativeSorted) :bStableSort false) (Variables|Default|SetNativeMinimum (Utilities|Array|Get(aref) :Array (Variables|Default|GetNativeSorted) :\"Dimension 1\" 0)) (if (< (Variables|Default|GetNativeMinimum) 1e+30) (if (== (Variables|Default|GetNativeFreeMinimum) (Variables|Default|GetNativeMinimum)) (Variables|Default|SetJ1 (Variables|Default|GetNativeFreeColumn)) (else (Variables|Default|SetJ1 (Utilities|Array|FindItem :TargetArray (Variables|Default|GetNativeMasked) :ItemToFind (Variables|Default|GetNativeMinimum))))) (if (and (> (Variables|Default|GetJ1) 0) (<= (Variables|Default|GetJ1) (Variables|Default|GetWidth))) (Variables|Default|SetDelta (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" (Variables|Default|GetJ1))) (Variables|Default|SetBestColumnFree (== (Utilities|Array|Get(aref) :Array (Variables|Default|GetP) :\"Dimension 1\" (Variables|Default|GetJ1)) 0)) (Variables|Default|SetNativeCursor (Variables|Default|GetWidth)) (Variables|Default|SetNativePhase 5) (else (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false))) (else (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false))) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1))) (:5 (for work (range (Variables|Default|GetStepWorkLimit)) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)) (if (< (Variables|Default|GetNativeCursor) 1) (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false) (break)) (if (not (Utilities|Array|Get(aref) :Array (Variables|Default|GetUsed) :\"Dimension 1\" (Variables|Default|GetNativeCursor))) (Variables|Default|SetCur (Utilities|Array|Get(aref) :Array (Variables|Default|GetMinV) :\"Dimension 1\" (Variables|Default|GetNativeCursor))) (Variables|Default|SetNativeMaskRow (Variables|Default|GetActiveRow)) (Variables|Default|SetNativeMaskReady true) (Variables|Default|SetNativeFreeRow (Variables|Default|GetActiveRow)) (Variables|Default|SetNativeFreeValid (> (Variables|Default|GetNativeFreeColumn) 0)) (Variables|Default|SetCursor 0) (Variables|Default|SetSolverState 6) (break)) (Variables|Default|SetNativeCursor (- (Variables|Default|GetNativeCursor) 1)))) (:Default (Variables|Default|SetDelta 1e+30) (Variables|Default|SetJ1 0) (Variables|Default|SetBestColumnFree false) (Variables|Default|SetCursor 1) (Variables|Default|SetSolverState 5) (Variables|Default|SetNativePhase 0) (Variables|Default|SetNativeMaskReady false) (Variables|Default|SetLastStepWork (+ (Variables|Default|GetLastStepWork) 1)))))"

import ast
import copy
import json
import struct
import sys
import time
from pathlib import Path

from solver_label_upper_bound_dsl import UPPER_VARIABLES


NEW_PRIVATE_FIELDS = {"NativeMaskEnd"} | set(UPPER_VARIABLES)


def encoded(value):
    if isinstance(value, float):
        return struct.pack("!d", value)
    if isinstance(value, (bool, int, str)):
        return value
    return tuple(encoded(item) for item in value)


def fixture_class():
    import unreal
    import toolset_registry
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
    asset = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_AssignmentSolver")
    child = BP.create("/Game/WorkerOptimizerEditorTests",
                      "BP_NativeMaskBatch_" + str(time.time_ns()), asset.generated_class())
    graphs = {name: BP.add_function_graph(child, name) for name in (
        "LegacyAdvanceNativeRelaxation", "StepMaskLegacy", "SeedMaskTest",
        "SeedMaskZero", "ConfigureMaskCsr", "StopMaskTest")}
    for name, params in {
        "SeedMaskTest": (("InputCursor", "int", False), ("Columns", "int", True),
                         ("Values", "float", True), ("InputDone", "bool", False)),
        "SeedMaskZero": (("InputZero", "float", False), ("Index", "int", False)),
        "ConfigureMaskCsr": (("Offsets", "int", True), ("Columns", "int", True)),
        "StopMaskTest": (),
    }.items():
        for param, kind, array in params:
            BP.add_function_param(graphs[name], param, kind, True,
                                  ContainerType.ARRAY if array else None)
    BP.compile_blueprint(child)
    nodes = BP.find_node_types(graphs["SeedMaskTest"], "", [])

    def node(tail):
        matches = [value for value in nodes if value.endswith("|" + tail)]
        preferred = "Variables|Default|" + tail
        result = preferred if preferred in matches else matches[0] if len(matches) == 1 else None
        assert result, (tail, matches)
        return result

    get = lambda name: "(" + node("Get" + name) + ")"
    put = lambda name, value: "(" + node("Set" + name) + " " + value + ")"
    sources = {
        "LegacyAdvanceNativeRelaxation": LEGACY_DSL.replace(
            "(fn AdvanceNativeRelaxation ()", "(fn LegacyAdvanceNativeRelaxation ()", 1).replace(
            "Utilities|Array|Sort|SortFloatArray", node("SortFloatArray")).replace(
            "Utilities|Array|FindItem", node("FindItem")),
        "StepMaskLegacy": f"""(fn StepMaskLegacy ()
          {put('LastStepWork', '0')} (if {get('Done')} (return))
          (if (<= {get('StepWorkLimit')} 0)
            {put('Done', 'true')} {put('Succeeded', 'false')} (return))
          (if (== {get('SolverState')} 11)
            ({node('LegacyAdvanceNativeRelaxation')}) (return))
          ({node('Advance')}))""",
        "SeedMaskTest": f"""(fn SeedMaskTest (InputCursor Columns Values InputDone)
          {put('NativeCursor', 'InputCursor')} {put('UsedColumns', 'Columns')}
          {put('NativeMasked', 'Values')} {put('Done', 'InputDone')}
          {put('NativePhase', '3')} {put('SolverState', '11')}
          {put('NativeEnd', '777')} {put('LastStepWork', '99')})""",
        "SeedMaskZero": f"""(fn SeedMaskZero (InputZero Index)
          (Utilities|Array|SetArrayElem :TargetArray {get('NativeMasked')}
            :Index Index :Item (* InputZero -1.0)))""",
        "ConfigureMaskCsr": f"""(fn ConfigureMaskCsr (Offsets Columns)
          {put('NativePlannerTrusted', 'true')} {put('NativeCsrReady', 'true')}
          {put('NativeRowOffsets', 'Offsets')} {put('NativeColumns', 'Columns')})""",
        "StopMaskTest": f"""(fn StopMaskTest () {put('Done', 'true')})""",
    }
    with toolset_registry.tool_raising_exceptions():
        for name, source in sources.items():
            BP.write_graph_dsl(graphs[name], source)
        BP.compile_blueprint(child, warnings_as_errors=True)
    # The frozen graph predates Upper witnesses; their private scratch fields
    # have a dedicated differential test. Keep every old native/mask field.
    return child.generated_class(), sorted(set(BP.list_variables(asset)) - NEW_PRIVATE_FIELDS)


def compare(pair, names, context):
    for name in names:
        a, b = (obj.get_editor_property(name) for obj in pair)
        assert encoded(a) == encoded(b), (context, name, a, b)


def initialize(pair, matrix, limit):
    cols = len(matrix[0]) if matrix else 0
    offsets, columns = [0], []
    for row in matrix:
        columns.extend(index for index, score in enumerate(row) if score != -1e20)
        offsets.append(len(columns))
    for obj in pair:
        obj.set_editor_property("StepWorkLimit", limit)
        obj.call_method("Initialize", args=([value for row in matrix for value in row], len(matrix), cols))
        obj.call_method("RestrictDummies", args=([False] * len(matrix),))
        obj.call_method("ConfigureMaskCsr", args=(offsets, columns))


def step(pair, names, limit, context):
    stopped = pair[0].get_editor_property("Done")
    pair[0].call_method("Advance")
    pair[1].call_method("StepMaskLegacy")
    compare(pair, names, context)
    work = int(pair[0].get_editor_property("LastStepWork"))
    assert work == 0 if stopped else 0 < work <= limit, (context, work)
    return work


def compiled_run():
    import unreal
    cls, names = fixture_class()
    pair = [unreal.new_object(cls), unreal.new_object(cls)]
    cases = calls = native_calls = 0
    for limit in (1, 3, 64):
        for count in (0, 1, 2, 3, 4, 63, 64, 65, 129):
            columns = list(reversed(range(0, count * 2, 2)))
            values = [float(index) + .125 for index in range(count * 2 + 3)]
            for start in sorted({0, max(0, count - 1), count, count + 1}):
                for stopped in (False, True):
                    initialize(pair, [[1.0]], limit)
                    for obj in pair:
                        obj.call_method("SeedMaskTest", args=(start, columns, values, stopped))
                        obj.call_method("SeedMaskZero", args=(0.0, len(values) - 1))
                        assert encoded(obj.get_editor_property("NativeMasked")[-1]) == encoded(-0.0)
                    compare(pair, names, ("seed", limit, count, start, stopped))
                    before = list(pair[0].get_editor_property("NativeMasked"))
                    total = step(pair, names, limit, ("mask", limit, count, start, stopped))
                    calls += 1
                    if not stopped:
                        while pair[0].get_editor_property("NativePhase") == 3:
                            total += step(pair, names, limit, ("mask continuation", count, start))
                            calls += 1
                        assert total == max(1, count - start), (limit, count, start, total)
                        assert pair[0].get_editor_property("NativeCursor") == max(start, count)
                        assert pair[0].get_editor_property("NativePhase") == 4
                        expected = before[:]
                        for column in columns[start:]:
                            expected[column] = 1e30
                        assert encoded(pair[0].get_editor_property("NativeMasked")) == encoded(expected)
                    cases += 1
        # Natural full lifecycles compare every field at every public call fence.
        matrices = [
            [[10., 9., 0.], [10., 8., 0.], [10., 7., 0.]],
            [[5., 5., 5., 0.]] * 4,
            [[4., -1e20, 3., 0.], [4., 3., -1e20, 0.], [4., 3., 3., 0.]],
            [[1e14+.06, 1e14+.02, 0.], [1e14+.06, 1e14+.02, 0.]],
            [[0., -0.0, 0.], [0., 0., -0.0]],
            [],
        ]
        from test_solver_cached_trace import benchmark_matrices
        matrices.append(benchmark_matrices(12)[0])
        for matrix in matrices:
            initialize(pair, matrix, limit)
            compare(pair, names, ("initialize", limit, matrix))
            work = 0
            while not pair[0].get_editor_property("Done"):
                native_calls += pair[0].get_editor_property("SolverState") == 11
                work += step(pair, names, limit, ("lifecycle", limit, len(matrix), calls))
                calls += 1
                assert work < 200000
            cases += 1
        # Stop between chunks, prove no work, then restart the same objects.
        initialize(pair, [[1.0]], limit)
        values, columns = [0.] * 140, list(range(130))
        for obj in pair:
            obj.call_method("SeedMaskTest", args=(0, columns, values, False))
        step(pair, names, limit, ("pre-cancel", limit))
        for obj in pair:
            obj.call_method("StopMaskTest")
        before = {name: encoded(pair[0].get_editor_property(name)) for name in names if name != "LastStepWork"}
        step(pair, names, limit, ("cancel", limit))
        after = {name: encoded(pair[0].get_editor_property(name)) for name in names if name != "LastStepWork"}
        assert before == after
        initialize(pair, [[2., 1.], [1., 2.]], limit)
        while not pair[0].get_editor_property("Done"):
            step(pair, names, limit, ("restart", limit))
        cases += 1
    assert native_calls > 0
    unreal.log(f"WO_NATIVE_MASK_BATCH_TESTS_PASS cases={cases} calls={calls} native_calls={native_calls}")


def offline_run():
    from test_solver_native_relaxation_model import emitted, NativeMachine, parser, check_structure
    current, old_symbol = emitted()
    parse, symbol = parser()
    # One parser instance owns both Symbol classes for the interpreter.
    def emit(form):
        if isinstance(form, list):
            return "(" + " ".join(emit(item) for item in form) + ")"
        if isinstance(form, old_symbol):
            return ':' + json.dumps(str(form)[1:]) if str(form).startswith(':') and ' ' in str(form) else str(form)
        return json.dumps(form)
    current["native"] = parse(emit(current["native"][0]))
    legacy = parse(LEGACY_DSL)
    check_structure({"current": current["native"], "legacy": legacy})

    class Meter(NativeMachine):
        def __init__(self, forms, state):
            super().__init__(forms, symbol, state)
            self.writes = {}

        def evaluate(self, form):
            if isinstance(form, list) and form and str(form[0]).startswith("Variables|Default|Set"):
                name = str(form[0]).removeprefix("Variables|Default|Set")
                self.writes[name] = self.writes.get(name, 0) + 1
            return super().evaluate(form)

    cases = 0
    maximum_cursor_writes = 0
    for limit in (1, 3, 64):
        for count in (0, 1, 2, 3, 4, 63, 64, 65, 129):
            for start in sorted({0, max(0, count - 1), count, count + 1}):
                for stopped in (False, True):
                    state = dict(Done=stopped, StepWorkLimit=limit, LastStepWork=99,
                                 NativePhase=3, NativeCursor=start, NativeEnd=777,
                                 UsedColumns=list(reversed(range(0, count * 2, 2))),
                                 NativeMasked=[0., -0., .125] * (count + 1))
                    a = Meter(current["native"], copy.deepcopy(state))
                    b = Meter(legacy, copy.deepcopy(state))
                    while True:
                        for machine in (a, b):
                            machine.writes.clear()
                            for form in machine.forms:
                                try:
                                    machine.evaluate(form)
                                except Exception as error:
                                    raise AssertionError((limit, count, start, stopped,
                                                          "current" if machine is a else "legacy", machine.state)) from error
                        actual = {key: encoded(value) for key, value in a.state.items() if key not in NEW_PRIVATE_FIELDS}
                        expected = {key: encoded(value) for key, value in b.state.items() if key not in NEW_PRIVATE_FIELDS}
                        assert actual == expected, (limit, count, start, stopped, actual, expected)
                        maximum_cursor_writes = max(maximum_cursor_writes, a.writes.get("NativeCursor", 0))
                        if stopped or a.state["NativePhase"] != 3:
                            break
                    cases += 1
    assert maximum_cursor_writes <= 1, (
        "Mask batch must commit NativeCursor once per call, not once per used column", maximum_cursor_writes)
    print("WO_NATIVE_MASK_BATCH_MODEL_PASS", cases, "max_cursor_writes", maximum_cursor_writes)


if __name__ == "__main__":
    offline_run() if "--offline" in sys.argv else compiled_run()
