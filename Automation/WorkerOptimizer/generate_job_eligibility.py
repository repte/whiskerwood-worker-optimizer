"""Generate workplace role checks from the inspected native selector rules."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
native = lambda name: unreal.load_class(None, "/Script/ProjectArco." + name)
bp = unreal.load_asset(ROOT + "/BP_JobEligibility")
if bp is None:
    bp = BP.create(ROOT, "BP_JobEligibility", unreal.load_class(None, ROOT + "/BP_WorkplaceAdapter.BP_WorkplaceAdapter_C"))
definitions = {
    "EligibleData": [("Education", "int"), ("Requirement", "int"), ("Student", "bool"), ("TeacherGuild", "name"), ("WorkerGuild", "name")],
    "CanFillSlot": [("Worker", native("Prototype_Agent")), ("Building", native("GridActor")), ("SlotIndex", "int"), ("PlannedTeacher", native("Prototype_Agent"))],
    "LiveCanFillSlot": [("Worker", native("Prototype_Agent")), ("Building", native("GridActor")), ("SlotIndex", "int")],
    "SameTeacherProfile": [("Left", native("Prototype_Agent")), ("Right", native("Prototype_Agent")), ("Building", native("GridActor"))],
}
existing = {str(g.get_name()) for g in BP.list_graphs(bp)}
graphs = {}
for name, params in definitions.items():
    graph = BP.get_graph(bp, name) if name in existing else BP.add_function_graph(bp, name)
    graphs[name] = graph
    if name not in existing:
        for param, kind in params:
            if isinstance(kind, str):
                BP.add_function_param(graph, param, kind, True)
            else:
                BP.add_object_function_param(graph, param, kind, True)
        BP.add_function_param(graph, "Result", "bool", False)
BP.compile_blueprint(bp)
context = graphs["CanFillSlot"]


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    pins = BP.get_node_type_pins(context, node).output_pins
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in pins)}) ({node} {value}))"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


code = {}
code["EligibleData"] = """(fn EligibleData (Education Requirement Student TeacherGuild WorkerGuild)
    (if (or (< Education 0) (> Education 255)) (return false))
    (if (or (< Requirement 0) (> Requirement 255)) (return false))
    (if Student
      (if (and (!= TeacherGuild "None") (== TeacherGuild WorkerGuild)) (return false))
      (if (== Requirement 0) (return true))
      (return (!= (Math|Integer|BitwiseAND Education Requirement) Requirement)))
    (if (== Requirement 128) (return (== (Math|Integer|BitwiseAND Education 3) 1)))
    (if (== Requirement 64) (return (== (Math|Integer|BitwiseAND Education 48) 16)))
    (return (== (Math|Integer|BitwiseAND Education Requirement) Requirement)))"""
def normal(result):
    return f"""(bind {result} (CallFunction|EligibleData :Education education :Requirement requirement :Student false))
    (return {result})"""
code["CanFillSlot"] = f"""(fn CanFillSlot (Worker Building SlotIndex PlannedTeacher)
    (Utilities|IsValid Worker (:"Is Not Valid" (return false))
      (:"Is Valid"
        (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
        (if (not known) (return false))
        {unpack('WorkerAssignment', 'workforce', 'wf')}
        (if wf_bDisabled (return false))
        (if (not (Utilities|Array|IsValidIndex wf_m_workerSlots SlotIndex)) (return false))
        {unpack('WorkerSlot', at('wf_m_workerSlots', 'SlotIndex'), 'slot')}
        {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Worker)', 'ch')}
        (bind education (Math|Conversions|ToInteger(Byte) ch_education))
        (bind requirement (Math|Conversions|ToInteger(Byte) slot_educationRequirement))
        (bind schoolComponent (Actor|GetComponentbyClass :self Building :ComponentClass "/Script/ProjectArco.School"))
        (bind school (Utilities|Casting|CastToSchool :Object schoolComponent)
          (:CastFailed {normal('ordinaryEligible')})
          (:then
            (if (== SlotIndex 0) {normal('teacherEligible')})
            (if (== PlannedTeacher Worker) (return false))
            (Utilities|IsValid PlannedTeacher (:"Is Not Valid" (return false))
              (:"Is Valid"
                {unpack('WorkerSlot', at('wf_m_workerSlots', '0'), 'teacherSlot')}
                {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self PlannedTeacher)', 'teacher')}
                (bind teacherEducation (Math|Conversions|ToInteger(Byte) teacher_education))
                (bind targetEducation (Math|Conversions|ToInteger(Byte) teacherSlot_educationRequirement))
                (bind teacherOK (CallFunction|EligibleData :Education teacherEducation :Requirement targetEducation :Student false))
                (if (not teacherOK) (return false))
                (if (== targetEducation 0)
                  (bind eligible (CallFunction|EligibleData :Education education :Requirement 0 :Student true :TeacherGuild teacher_guild :WorkerGuild ch_guild))
                  (return eligible)
                  (else
                    (bind eligibleEducation (CallFunction|EligibleData :Education education :Requirement targetEducation :Student true))
                    (return eligibleEducation))))))))))"""
code["LiveCanFillSlot"] = f"""(fn LiveCanFillSlot (Worker Building SlotIndex)
    (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
    (if (not known) (return false))
    {unpack('WorkerAssignment', 'workforce', 'wf')}
    (if (not (Utilities|Array|IsValidIndex wf_m_workerSlots SlotIndex)) (return false))
    {unpack('WorkerSlot', at('wf_m_workerSlots', '0'), 'teacherSlot')}
    (bind eligible (CallFunction|CanFillSlot :Worker Worker :Building Building :SlotIndex SlotIndex :PlannedTeacher teacherSlot_Agent))
    (return eligible))"""
code["SameTeacherProfile"] = f"""(fn SameTeacherProfile (Left Right Building)
    (Utilities|IsValid Building (:"Is Not Valid" (return false))
      (:"Is Valid"
        (bind component (Actor|GetComponentbyClass :self Building :ComponentClass "/Script/ProjectArco.School"))
        (Utilities|IsValid component (:"Is Not Valid" (return false))
          (:"Is Valid"
            (bind leftOK (CallFunction|CanFillSlot :Worker Left :Building Building :SlotIndex 0))
            (if (not leftOK) (return false))
            (bind rightOK (CallFunction|CanFillSlot :Worker Right :Building Building :SlotIndex 0))
            (if (not rightOK) (return false))
            {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Left)', 'left')}
            {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Right)', 'right')}
            (if (!= (Utilities|Set|ContainsItem left_traits "teacher") (Utilities|Set|ContainsItem right_traits "teacher")) (return false))
            (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
            (if (not known) (return false))
            {unpack('WorkerAssignment', 'workforce', 'wf')}
            {unpack('WorkerSlot', at('wf_m_workerSlots', '0'), 'teacherSlot')}
            (if (== (Math|Conversions|ToInteger(Byte) teacherSlot_educationRequirement) 0)
              (return (== left_guild right_guild)))
            (return true))))))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_JOB_ELIGIBILITY_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-JobEligibility.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_JOB_ELIGIBILITY_GENERATED")
exec(Path(__file__).with_name("test_job_eligibility.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_teacher_profiles.py").read_text(encoding="utf-8"))
