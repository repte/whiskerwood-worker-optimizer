"""Verify exact teaching-effect equivalence, independent of production value."""

import unreal


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_JobEligibility.BP_JobEligibility_C")
    rules = unreal.new_object(cls)
    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
    spawned = []
    put = lambda obj, name, value: obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)

    def spawn(name):
        obj = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        spawned.append(obj)
        return obj

    def worker_data(worker, education="Master", guild="farmers", traits="", productivity=100):
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text(f'(education={education},guild="{guild}",traits=({traits}),base_productivity={productivity})')
        assert ch.get_editor_property("base_productivity") == productivity
        put(worker, "m_characteristics", ch)

    try:
        a, b = spawn("Prototype_Agent"), spawn("Prototype_Agent")
        school = spawn("GridActor")
        component = school.call_method("AddComponentByClass", args=(native("School"), False, unreal.Transform(), False))
        wf = component.get_editor_property("m_workers")

        def requirement(value):
            assert wf.import_text(f'(m_workerSlots=((educationRequirement={value},bIsRequiredToRun=True),()))')
            put(component, "m_workers", wf)

        same = lambda left=a, right=b, building=school: rules.call_method("SameTeacherProfile", args=(left, right, building))
        requirement("Master")
        worker_data(a)
        worker_data(b, guild="bakers", traits='"scientist"', productivity=250)
        assert same(), "Education schools may group equal teaching effects despite different production values/guilds"
        assert same(left=a, right=a)
        assert not same(left=None)
        assert not same(building=None)
        worker_data(b, traits='"teacher"')
        assert not same(), "Gifted-teacher multiplier changes the profile"
        worker_data(a, traits='"teacher"')
        assert same()
        worker_data(b, education="Apprentice", traits='"teacher"')
        assert not same(), "An ineligible teacher cannot join a qualified profile"
        worker_data(b, guild="bakers", traits='"teacher"')
        requirement("None")
        assert not same(), "Guild-school student admission depends on teacher guild"
        worker_data(b, traits='"teacher","inquisitive"')
        assert same(), "Inquisitive changes pupil scoring, not teaching"
        worker_data(a, guild="None")
        worker_data(b, guild="None")
        assert same(), "No-guild is a real profile, not a missing-worker sentinel"
        put(wf, "bDisabled", True)
        put(component, "m_workers", wf)
        assert not same(), "Paused schools must not participate"
        unreal.log("WO_TEACHER_PROFILES_TESTS_PASS: native profile equivalence, dynamic education, guild admission, gifted bonus, irrelevant production traits and invalid/paused guards")
    finally:
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
