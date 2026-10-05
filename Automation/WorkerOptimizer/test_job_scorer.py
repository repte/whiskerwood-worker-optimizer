"""Execute the actual Blueprint productivity scorer, including unclamped inputs."""

import unreal


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


run()
