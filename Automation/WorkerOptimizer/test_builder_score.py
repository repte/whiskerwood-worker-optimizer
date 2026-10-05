"""Builder tie preference must use neutral productivity, carry and movement."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP

path = "/Game/Mods/WorkerOptimizer/BP_JobScorer"
bp = unreal.load_asset(path)
assert "BuilderPreference" in {str(g.get_name()) for g in BP.list_graphs(bp)}, "No builder suitability tie-breaker"
scorer = unreal.new_object(unreal.load_class(None, path + ".BP_JobScorer_C"))
call = lambda *args: scorer.call_method("BuilderPreference", args=args)
assert call(100., 2., 100.) == (True, 130.)
assert call(100., 3., 100.)[1] > call(100., 2., 100.)[1]
assert call(120., 2., 100.)[1] > call(100., 2., 100.)[1]
assert call(100., 2., 110.)[1] > call(100., 2., 100.)[1]
assert call(-20., 0., 0.) == (True, 10.)
for value in (float("nan"), float("inf"), 1e12):
    assert not call(value, 2., 100.)[0]
    assert not call(100., value, 100.)[0]
    assert not call(100., 2., value)[0]
assert not scorer.call_method("ScoreBuilder", args=(None,))[0]
unreal.log("WO_BUILDER_SCORE_TESTS_PASS: monotonic neutral productivity/carry/speed preference and invalid input rejection")
