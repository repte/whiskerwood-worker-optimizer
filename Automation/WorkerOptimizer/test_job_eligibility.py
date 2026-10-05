"""Production role checks, including school admission and special education filters."""

import unreal


def put(obj, name, value):
    obj.set_editor_property(name, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_JobEligibility.BP_JobEligibility_C")
    assert cls, "Production job eligibility does not exist"
    rules = unreal.new_object(cls)

    def eligible(education, required, student=False, teacher="None", guild="None"):
        return rules.call_method("EligibleData", args=(education, required, student, teacher, guild))

    assert eligible(0, 0)
    assert eligible(3, 1) and not eligible(1, 3)
    assert eligible(7, 5) and not eligible(3, 5)
    assert eligible(1, 128) and not eligible(3, 128), "ApprenticeOnly is not an ordinary mask"
    assert eligible(16, 64) and not eligible(48, 64), "SailorOnly excludes officers"
    assert eligible(0, 4, True) and not eligible(4, 4, True), "Students must not already have the target education"
    assert eligible(1, 3, True) and not eligible(3, 3, True)
    assert not eligible(0, 0, True, "bakers", "bakers")
    assert eligible(0, 0, True, "bakers", "farmers")
    assert eligible(0, 0, True, "None", "None")
    assert eligible(0, 0, False, "bakers", "bakers"), "Teacher guild exclusion is student-only"
    for education in range(64):
        for required in (*range(64), 64, 128):
            expected = ((education & 3) == 1 if required == 128 else
                        (education & 48) == 16 if required == 64 else
                        (education & required) == required)
            assert eligible(education, required) == expected, (education, required)
            expected_student = required == 0 or (education & required) != required
            assert eligible(education, required, True) == expected_student
    for education, required in ((-1, 0), (256, 0), (0, -1), (0, 256)):
        assert not eligible(education, required)

    actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawned = []
    native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)

    def spawn(name):
        obj = actors.spawn_actor_from_class(native(name), unreal.Vector(0, 0, -100000))
        assert obj
        spawned.append(obj)
        return obj

    def traits(worker, education, guild):
        ch = worker.get_editor_property("m_characteristics")
        assert ch.import_text(f'(education={education},guild="{guild}")')
        put(worker, "m_characteristics", ch)

    try:
        worker = spawn("Prototype_Agent")
        teacher = spawn("Prototype_Agent")
        building = spawn("GridActor")
        industry = building.call_method("AddComponentByClass", args=(native("Industry"), False, unreal.Transform(), False))
        workforce = industry.get_editor_property("m_workers")
        assert workforce.import_text("(m_workerSlots=((educationRequirement=Master,bIsRequiredToRun=True),()))")
        put(industry, "m_workers", workforce)
        can = lambda target=building, slot=0, tutor=None, candidate=worker: rules.call_method("CanFillSlot", args=(candidate, target, slot, tutor))
        traits(worker, "Apprentice", "farmers")
        assert not can()
        traits(worker, "Master", "farmers")
        assert can()
        assert can(slot=1)
        assert not can(slot=-1) and not can(slot=2)
        assert not can(target=None) and not can(candidate=None)
        put(workforce, "bDisabled", True)
        put(industry, "m_workers", workforce)
        assert not can(), "Paused building must remain untouched"

        school_building = spawn("GridActor")
        school = school_building.call_method("AddComponentByClass", args=(native("School"), False, unreal.Transform(), False))
        sw = school.get_editor_property("m_workers")
        assert sw.import_text("(m_workerSlots=((educationRequirement=Educated,bIsRequiredToRun=True),()))")
        put(school, "m_workers", sw)
        traits(worker, "None", "farmers")
        traits(teacher, "Educated", "bakers")
        assert not can(school_building, 0)
        assert can(school_building, 0, candidate=teacher)
        assert can(school_building, 1, teacher)
        assert not can(school_building, 1), "Student placement requires a planned teacher"
        assert not can(school_building, 1, worker), "One worker cannot be teacher and student"
        traits(worker, "Educated", "farmers")
        assert not can(school_building, 1, teacher)
        traits(worker, "None", "farmers")
        traits(teacher, "None", "bakers")
        assert not can(school_building, 1, teacher), "Planned teacher must meet the teacher role"

        assert sw.import_text("(m_workerSlots=((educationRequirement=None,bIsRequiredToRun=True),()))")
        put(school, "m_workers", sw)
        assert can(school_building, 1, teacher)
        traits(worker, "None", "bakers")
        assert not can(school_building, 1, teacher), "Guild students must learn a different guild"
        traits(worker, "None", "farmers")
        assert can(school_building, 1, teacher)
        assert rules.call_method("LiveCanFillSlot", args=(worker, school_building, 1)) is False
        slots = list(sw.get_editor_property("m_workerSlots"))
        put(slots[0], "Agent", teacher)
        put(sw, "m_workerSlots", slots)
        put(school, "m_workers", sw)
        assert rules.call_method("LiveCanFillSlot", args=(worker, school_building, 1))
        assert not rules.call_method("LiveCanFillSlot", args=(teacher, school_building, 1))
        unreal.log("WO_JOB_ELIGIBILITY_TESTS_PASS: 8448 education/admission cases, special filters, dynamic slots, pause, planned/live teachers, guild exclusions; native game application not exercised")
    finally:
        for obj in reversed(spawned):
            actors.destroy_actor(obj)


run()
