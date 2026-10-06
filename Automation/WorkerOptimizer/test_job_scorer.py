"""Execute the actual Blueprint productivity scorer, including unclamped inputs."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_JobScorer.BP_JobScorer_C")
    assert cls, "Production job scorer does not exist"
    scorer = unreal.new_object(cls)
    def call(name, *args):
        result = scorer.call_method(name, args=args)
        if name == "NeutralProductivity":
            # Unreal's Python bridge returns non-const array inputs before outputs.
            returned_keys, returned_values, valid, value = result
            assert list(returned_keys) == args[1]
            assert len(returned_values) == len(args[2])
            return valid, value
        return result
    assert not call("ScoreData", 100.0, True, False, False, False, False)[0]
    assert call("Configure", 50.0, -60.0, 10.0, 40.0, 25.0)

    def score(base, match=False, monarch=False, scientist=False, overtime=False, construction=False):
        ok, value = call("ScoreData", base, match, monarch, scientist, overtime, construction)
        assert ok
        return value

    assert score(100) == 100
    assert score(100, match=True) == 150
    assert score(100, monarch=True) == 40
    assert score(100, scientist=True) == 110
    assert score(100, overtime=True) == 140
    assert score(100, construction=True) == 125
    assert score(100, True, True, True, True, True) == 165
    assert score(-150, match=True) == 10, "Floor applies after replacing workplace effects"
    assert score(4, match=True) == 54, "Do not clamp the neutral baseline prematurely"
    keys = ["mod.hunger", "mod.matchingGuildEmployer", "mod.unhappyMonarchist", "mod.trait.scientist", "mod.overtime", "mod.constructionyardWorker", "mod.future_meal"]
    values = [-30.0, 50.0, -60.0, 10.0, 40.0, 25.0, 7.0]
    ok, neutral = call("NeutralProductivity", 100.0, keys, values)
    assert ok and neutral == 77, "Replace all current-job modifiers, preserve unrelated/future modifiers"
    assert score(neutral, match=True) == 127, "No double-counted guild bonus"
    ok, neutral = call("NeutralProductivity", 100.0, ["mod.hunger", "mod.starvation", "mod.injury"], [-30.0, -50.0, -60.0])
    assert ok and neutral == -40
    assert score(neutral, match=True) == 10
    assert score(neutral, match=True, overtime=True) == 50
    assert not call("NeutralProductivity", 100.0, ["one"], [])[0]
    for bad in (float("nan"), float("inf"), -float("inf"), 1e12):
        assert not call("NeutralProductivity", bad, [], [])[0]
        assert not call("NeutralProductivity", 100.0, ["unknown"], [bad])[0]
        assert not call("ScoreData", bad, False, False, False, False, False)[0]
        assert not call("Configure", bad, -60.0, 10.0, 40.0, 25.0)
        assert not call("ScoreData", 100.0, True, False, False, False, False)[0], "Failed configuration must invalidate earlier values"
        assert call("Configure", 50.0, -60.0, 10.0, 40.0, 25.0)
    assert call("Configure", 63.0, -17.0, 22.0, 31.0, 12.0)
    assert score(100, True, True, True, True, True) == 211, "Modifier magnitudes must come from runtime data"
    assert not call("ScoreWorker", None, None, False)[0]
    assert not call("LoadConfig", None), "Native editor stub cannot supply a complete modifier configuration"
    assert not call("ScoreData", 100.0, True, False, False, False, False)[0]
    for gifted, inquisitive, expected in ((False, False, 1.0), (True, False, 3.0),
                                         (False, True, 2.0), (True, True, 6.0)):
        valid, rate = call("SchoolLearningRateData", gifted, inquisitive, 3.0, 2.0)
        assert valid and rate == expected, "School learning multiplies teacher and student effects, without ordinary productivity"
    assert call("SchoolLearningRateData", True, True, 1.25, 1.5) == (True, 1.875)
    for bad in (0.0, -1.0, float("nan"), float("inf"), 1e12):
        assert not call("SchoolLearningRateData", False, False, bad, 2.0)[0]
        assert not call("SchoolLearningRateData", False, False, 3.0, bad)[0]
    assert not call("SchoolLearningRateData", True, True, 1e6, 1e6)[0]
    assert not call("SchoolLearningRate", None, None, None)[0]
    unreal.log("WO_JOB_SCORER_TESTS_PASS: workplace effects replaced, unrelated modifiers retained, native floor, dynamic coefficients, invalid inputs/reuse; native data retrieval not verified in editor")


def frozen_quality():
    bp = unreal.load_asset("/Game/Mods/WorkerOptimizer/BP_JobScorer")
    assert {"BeginQualityCapture", "AdvanceQualityCapture", "ReadFrozenQuality", "ScoreFrozenData"} <= {str(graph.get_name()) for graph in BP.list_graphs(bp)}, "Production frozen-quality capture/scoring interface is missing"
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_JobScorer.BP_JobScorer_C")
    scorer = unreal.new_object(cls)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    def worker(identity):
        value = actors.spawn_actor_from_class(unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent"), unreal.Vector(0, 0, -100000))
        spawned.append(value)
        ch = value.get_editor_property("m_characteristics")
        assert ch.import_text(f"(ID={identity},base_productivity=100)")
        value.set_editor_property("m_characteristics", ch, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        return value
    def begin(values):
        result = scorer.call_method("BeginQualityCapture", args=(values,))
        return result[-1] if isinstance(result, tuple) else result
    def finish():
        for _ in range(100):
            if scorer.get_editor_property("QualityDone"): break
            assert scorer.call_method("AdvanceQualityCapture")
            assert 0 <= scorer.get_editor_property("LastQualityWork") <= 1
        assert scorer.get_editor_property("QualityDone") and scorer.get_editor_property("QualitySucceeded")
    flags = (False, False, False, False, False)
    try:
        first, other = worker(501), worker(502)
        assert scorer.call_method("Configure", args=(50., -60., 10., 40., 25.))
        state = first.get_editor_property("m_state")
        for name, value in (("derived_productivity", 93.), ("derived_speedPercent", 88.), ("derived_carryCapacity", 2.)):
            state.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        first.set_editor_property("m_state", state, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert scorer.call_method("ScoreFrozenData", args=(first, *flags)) == (True, 100.), "Default manual mode retains explicit uncached fallback"
        manual_builder = scorer.call_method("ScoreBuilder", args=(first,))
        assert manual_builder[0] and abs(manual_builder[1] - 128.8) < 0.001
        assert begin([first])
        assert not scorer.call_method("ScoreFrozenData", args=(first, *flags))[0], "Partial quality capture cannot score"
        finish()
        assert scorer.call_method("ReadFrozenQuality", args=(first,)) == (True, 100., 2., 88.)
        assert scorer.call_method("ScoreFrozenData", args=(first, *flags)) == (True, 100.)
        assert scorer.call_method("ScoreFrozenData", args=(first, True, *flags[1:])) == (True, 150.)
        before = scorer.call_method("ScoreBuilder", args=(first,))
        assert before[0] and abs(before[1] - 128.8) < 0.001
        for name, value in (("derived_productivity", 103.), ("derived_speedPercent", 103.), ("derived_carryCapacity", 4.)):
            state.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        first.set_editor_property("m_state", state, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        # Mutable native base is an input-boundary fixture, not permission to ignore hard identity drift.
        ch = first.get_editor_property("m_characteristics")
        ch.set_editor_property("base_productivity", 115., notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        first.set_editor_property("m_characteristics", ch, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
        assert scorer.call_method("ScoreFrozenData", args=(first, *flags)) == (True, 100.), "Matrix scoring must reuse captured neutral, not re-read modifiers/base"
        assert scorer.call_method("ScoreBuilder", args=(first,)) == before, "Reserve and destination scoring share the same frozen quality"
        assert not scorer.call_method("ScoreFrozenData", args=(other, *flags))[0]
        assert not scorer.call_method("ScoreBuilder", args=(other,))[0], "Missing cache actor must never use live fallback"
        assert begin([first])
        finish()
        assert scorer.call_method("ReadFrozenQuality", args=(first,)) == (True, 115., 4., 103.)
        assert scorer.call_method("ScoreFrozenData", args=(first, *flags)) == (True, 115.), "New plan refreshes neutral quality"
        refreshed = scorer.call_method("ScoreBuilder", args=(first,))
        assert refreshed[0] and abs(refreshed[1] - 165.3) < 0.001
        assert begin([None])
        assert not scorer.call_method("AdvanceQualityCapture")
        assert scorer.get_editor_property("QualityDone") and not scorer.get_editor_property("QualitySucceeded")
        assert not scorer.call_method("ScoreBuilder", args=(first,))[0], "Failed new capture invalidates previous cache"
        assert begin([])
        finish()
        assert not scorer.call_method("ScoreFrozenData", args=(first, *flags))[0]
        unreal.log("WO_FROZEN_QUALITY_TESTS_PASS: shared cached neutral/carry/speed, soft drift, bounded capture, refresh, partial/failure/missing actor fail closed; native modifier contents stubbed in editor")
    finally:
        for value in reversed(spawned): actors.destroy_actor(value)

run()
frozen_quality()
