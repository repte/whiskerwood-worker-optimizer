"""Generate runtime-data-driven productivity scores for hypothetical workplaces."""

from pathlib import Path

import unreal
import toolset_registry
from editor_toolset.toolsets.blueprint import BlueprintTools as BP, ContainerType
from editor_toolset.toolsets import blueprint_dsl

ROOT = "/Game/Mods/WorkerOptimizer"
parent = unreal.load_class(None, ROOT + "/BP_WorkplaceAdapter.BP_WorkplaceAdapter_C")
bp = unreal.load_asset(ROOT + "/BP_JobScorer")
if bp is None:
    bp = BP.create(ROOT, "BP_JobScorer", parent)
coefficients = ("GuildBonus", "IndustrialPenalty", "ScientistBonus", "OvertimeBonus", "ConstructionBonus")
keys = ("mod.matchingGuildEmployer", "mod.unhappyMonarchist", "mod.trait.scientist", "mod.overtime", "mod.constructionyardWorker")
existing = set(BP.list_variables(bp))
for name, kind, array in [(n, "float", False) for n in coefficients] + [
    ("Ready", "bool", False), ("Accumulator", "float", False),
    ("BuilderCarry", "float", False), ("BuilderSpeed", "float", False),
    ("ScratchKeys", "name", True), ("ScratchValues", "float", True),
]:
    if name not in existing:
        BP.add_variable(bp, name, kind, container_type=ContainerType.ARRAY if array else None)
worker_cls = unreal.load_class(None, "/Script/ProjectArco.Prototype_Agent")
building_cls = unreal.load_class(None, "/Script/ProjectArco.GridActor")
definitions = {
    "ObjectPresent": ([("Object", unreal.Object.static_class())], False),
    "FiniteScore": ([('Value', 'float')], False),
    "Configure": ([(n, 'float') for n in coefficients], False),
    "LoadConfig": ([("Context", unreal.Object.static_class())], False),
    "IsWorkplaceModifier": ([("Key", "name")], False),
    "NeutralProductivity": ([("Base", "float"), ("Keys", "name[]"), ("Values", "float[]")], True),
    "ScoreData": ([("Neutral", "float")] + [(n, 'bool') for n in ("MatchGuild", "MonarchistIndustrial", "ScientistResearch", "Overtime", "Construction")], True),
    "ScoreWorker": ([("Worker", worker_cls), ("Building", building_cls), ("Overtime", "bool")], True),
    "BuilderPreference": ([("Productivity", "float"), ("Carry", "float"), ("Speed", "float")], True),
    "ScoreBuilder": ([("Worker", worker_cls)], True),
    "SchoolLearningRateData": ([("TeacherGifted", "bool"), ("StudentInquisitive", "bool"),
        ("GiftedMultiplier", "float"), ("InquisitiveMultiplier", "float")], True),
    "SchoolLearningRate": ([("Teacher", worker_cls), ("Student", worker_cls), ("Building", building_cls)], True),
}
existing_graphs = {str(g.get_name()) for g in BP.list_graphs(bp)}
graphs = {}
for name, (params, scored) in definitions.items():
    graphs[name] = BP.get_graph(bp, name) if name in existing_graphs else BP.add_function_graph(bp, name)
    if name not in existing_graphs:
        for param, kind in params:
            if isinstance(kind, str):
                array = kind.endswith("[]")
                BP.add_function_param(graphs[name], param, kind.removesuffix("[]"), True, ContainerType.ARRAY if array else None)
            else:
                BP.add_object_function_param(graphs[name], param, kind, True)
        BP.add_function_param(graphs[name], "Valid" if scored else "Result", "bool", False)
        if scored:
            BP.add_function_param(graphs[name], "Value", "float", False)
BP.compile_blueprint(bp)
context = graphs["ScoreWorker"]
nodes = BP.find_node_types(context, "", [])


def find(suffix):
    matches = [n for n in nodes if n.endswith("|" + suffix)]
    assert len(matches) == 1, (suffix, matches)
    return matches[0]


def get(name):
    return f"(Variables|Default|Get{name})"


def put(name, value):
    return f"(Variables|Default|Set{name} {value})"


def at(array, index):
    return f'(Utilities|Array|Get(acopy) :Array {array} :"Dimension 1" {index})'


def unpack(struct, value, prefix):
    node = "Utilities|Struct|Break" + struct
    pins = BP.get_node_type_pins(context, node).output_pins
    return f"(bind ({' '.join(prefix + '_' + str(p.name) for p in pins)}) ({node} {value}))"


def sum_effect(condition, coefficient):
    addition = f"(+ {get('Accumulator')} {get(coefficient)})"
    return f"(if {condition} {put('Accumulator', addition)})"


modifier_node = find("GetAgentModifier")
productivity_node = find("GetProductivityModifiers")
system_tune_node = find("GetSystemTune")
set_contains = "Utilities|Set|ContainsItem"
get_component = find("GetComponentbyClass")
code = {}
code["ObjectPresent"] = """(fn ObjectPresent (Object)
    (Utilities|IsValid Object (:"Is Not Valid" (return false)) (:"Is Valid" (return true))))"""
code["FiniteScore"] = """(fn FiniteScore (Value)
    (return (and (>= Value -1000000.0) (<= Value 1000000.0))))"""
code["Configure"] = f"""(fn Configure ({' '.join(coefficients)})
    {put('Ready', 'false')}
    {' '.join(f'(if (not (CallFunction|FiniteScore :Value {n})) (return false))' for n in coefficients)}
    {' '.join(put(n, n) for n in coefficients)}
    {put('Ready', 'true')} (return true))"""
loads = []
for i, key in enumerate(keys):
    loads.append(f"""(bind (m{i} found{i}) ({modifier_node} :Context Context :Key "{key}"))
      (if (not found{i}) (return false))
      {unpack('AgentModifier', 'm' + str(i), 'm' + str(i))}""")
code["LoadConfig"] = f"""(fn LoadConfig (Context)
    {put('Ready', 'false')}
    (Utilities|IsValid Context (:"Is Not Valid" (return false))
      (:"Is Valid"
        {' '.join(loads)}
        (bind configured (CallFunction|Configure {' '.join(':' + n + ' m' + str(i) + '_productivityMod' for i,n in enumerate(coefficients))}))
        (return configured))))"""
code["IsWorkplaceModifier"] = f"""(fn IsWorkplaceModifier (Key)
    {' '.join(f'(if (== Key "{key}") (return true))' for key in keys)}
    (return false))"""
code["NeutralProductivity"] = f"""(fn NeutralProductivity (Base Keys Values)
    (if (not (CallFunction|FiniteScore :Value Base)) (return false 0.0))
    (if (!= (Utilities|Array|Length Keys) (Utilities|Array|Length Values)) (return false 0.0))
    (if (> (Utilities|Array|Length Keys) 10000) (return false 0.0))
    {put('Accumulator', 'Base')}
    (for i (range (Utilities|Array|Length Keys))
      (bind value {at('Values', 'i')})
      (if (not (CallFunction|FiniteScore :Value value)) (return false 0.0))
      (bind isJob (CallFunction|IsWorkplaceModifier :Key {at('Keys', 'i')}))
      (if (not isJob) {put('Accumulator', f'(+ {get("Accumulator")} value)')}))
    (if (not (CallFunction|FiniteScore :Value {get('Accumulator')})) (return false 0.0))
    (return true {get('Accumulator')}))"""
code["ScoreData"] = f"""(fn ScoreData (Neutral MatchGuild MonarchistIndustrial ScientistResearch Overtime Construction)
    (if (not {get('Ready')}) (return false 0.0))
    (if (not (CallFunction|FiniteScore :Value Neutral)) (return false 0.0))
    {put('Accumulator', 'Neutral')}
    {' '.join(sum_effect(c, n) for c,n in zip(('MatchGuild', 'MonarchistIndustrial', 'ScientistResearch', 'Overtime', 'Construction'), coefficients))}
    (if (not (CallFunction|FiniteScore :Value {get('Accumulator')})) (return false 0.0))
    (if (< {get('Accumulator')} 10.0) (return true 10.0))
    (return true {get('Accumulator')}))"""
code["ScoreWorker"] = f"""(fn ScoreWorker (Worker Building Overtime)
    (if (not {get('Ready')}) (return false 0.0))
    (Utilities|IsValid Worker (:"Is Not Valid" (return false 0.0))
      (:"Is Valid"
        (Utilities|IsValid Building (:"Is Not Valid" (return false 0.0))
          (:"Is Valid"
            (bind (definition found) (Class|GridActor|GetGridActorDefinition :self Building))
            (if (not found) (return false 0.0))
            (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
            (if (not known) (return false 0.0))
            {unpack('WorkerAssignment', 'workforce', 'wf')}
            (if (or wf_bDisabled (!= wf_bOvertime Overtime)) (return false 0.0))
            {unpack('GridActorDefinitionMasterSyncFormat', 'definition', 'd')}
            {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Worker)', 'ch')}
            (bind modifiers ({productivity_node} :Agent Worker))
            (Utilities|Array|Clear {get('ScratchKeys')})
            (Utilities|Array|Clear {get('ScratchValues')})
            (for pair modifiers
              {unpack('ModifierPair', 'pair', 'p')}
              {unpack('AgentModifier', 'p_mod', 'm')}
              (Utilities|Array|Add {get('ScratchKeys')} p_Key)
              (Utilities|Array|Add {get('ScratchValues')} m_productivityMod))
            (bind (baseOK neutral) (CallFunction|NeutralProductivity :Base ch_base_productivity :Keys {get('ScratchKeys')} :Values {get('ScratchValues')}))
            (if (not baseOK) (return false 0.0))
            (bind research ({get_component} :self Building :ComponentClass "/Script/ProjectArco.ResearchLab"))
            (bind yard ({get_component} :self Building :ComponentClass "/Script/ProjectArco.ConstructionYard"))
            (bind hasResearch (CallFunction|ObjectPresent :Object research))
            (bind hasYard (CallFunction|ObjectPresent :Object yard))
            (bind (scoreOK score) (CallFunction|ScoreData :Neutral neutral
              :MatchGuild (== ch_guild d_guildSpecialty)
              :MonarchistIndustrial (and d_industrialLabor ({set_contains} ch_traits "monarchist"))
              :ScientistResearch (and hasResearch ({set_contains} ch_traits "scientist"))
              :Overtime Overtime :Construction hasYard))
            (return scoreOK score))))))"""
code["BuilderPreference"] = f"""(fn BuilderPreference (Productivity Carry Speed)
    (if (not (and (CallFunction|FiniteScore :Value Productivity) (and (CallFunction|FiniteScore :Value Carry) (CallFunction|FiniteScore :Value Speed)))) (return false 0.0))
    ; A tie preference, not a prediction of construction time or route length.
    (bind value (+ (+ (select (> Productivity 10.0) Productivity 10.0) (* (select (> Carry 0.0) Carry 0.0) 10.0)) (* (select (> Speed 0.0) Speed 0.0) 0.1)))
    (if (not (CallFunction|FiniteScore :Value value)) (return false 0.0))
    (return true value))"""
code["ScoreBuilder"] = f"""(fn ScoreBuilder (Worker)
    (if (not (CallFunction|ObjectPresent :Object Worker)) (return false 0.0))
    {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Worker)', 'ch')}
    {unpack('AgentState', '(Class|PrototypeAgent|GetMState :self Worker)', 'state')}
    {put('BuilderCarry', 'state_derived_carryCapacity')} {put('BuilderSpeed', 'state_derived_speedPercent')}
    (bind modifiers (Class|AgentDetails|GetAgentModifiers :Agent Worker :hideMinorMods false))
    (Utilities|Array|Clear {get('ScratchKeys')}) (Utilities|Array|Clear {get('ScratchValues')})
    (for pair modifiers
      {unpack('ModifierPair', 'pair', 'p')}
      {unpack('AgentModifier', 'p_mod', 'm')}
      (Utilities|Array|Add {get('ScratchKeys')} p_Key)
      (Utilities|Array|Add {get('ScratchValues')} m_productivityMod)
      (bind isJob (CallFunction|IsWorkplaceModifier :Key p_Key))
      (if isJob {put('BuilderCarry', f'(- {get("BuilderCarry")} m_carryMod)')} {put('BuilderSpeed', f'(- {get("BuilderSpeed")} m_speedMod)')}))
    (bind (ok neutral) (CallFunction|NeutralProductivity :Base ch_base_productivity :Keys {get('ScratchKeys')} :Values {get('ScratchValues')}))
    (if (not ok) (return false 0.0))
    (bind (valid score) (CallFunction|BuilderPreference :Productivity neutral :Carry {get('BuilderCarry')} :Speed {get('BuilderSpeed')}))
    (return valid score))"""
code["SchoolLearningRateData"] = f"""(fn SchoolLearningRateData (TeacherGifted StudentInquisitive GiftedMultiplier InquisitiveMultiplier)
    (if (not (and (> GiftedMultiplier 0.0) (<= GiftedMultiplier 1000000.0))) (return false 0.0))
    (if (not (and (> InquisitiveMultiplier 0.0) (<= InquisitiveMultiplier 1000000.0))) (return false 0.0))
    {put('Accumulator', '1.0')}
    (if TeacherGifted {put('Accumulator', 'GiftedMultiplier')})
    (if StudentInquisitive {put('Accumulator', f'(* {get("Accumulator")} InquisitiveMultiplier)')})
    (if (not (CallFunction|FiniteScore :Value {get('Accumulator')})) (return false 0.0))
    (return true {get('Accumulator')}))"""
code["SchoolLearningRate"] = f"""(fn SchoolLearningRate (Teacher Student Building)
    (if (not (CallFunction|ObjectPresent :Object Teacher)) (return false 0.0))
    (if (not (CallFunction|ObjectPresent :Object Student)) (return false 0.0))
    (if (== Teacher Student) (return false 0.0))
    (if (not (CallFunction|ObjectPresent :Object Building)) (return false 0.0))
    (bind school ({get_component} :self Building :ComponentClass "/Script/ProjectArco.School"))
    (if (not (CallFunction|ObjectPresent :Object school)) (return false 0.0))
    (bind (known workforce) (CallFunction|ReadWorkplace :Building Building))
    (if (not known) (return false 0.0))
    {unpack('WorkerAssignment', 'workforce', 'wf')}
    (if wf_bDisabled (return false 0.0))
    {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Teacher)', 'teacher')}
    {unpack('AgentCharacteristics', '(Class|PrototypeAgent|GetMCharacteristics :self Student)', 'student')}
    (bind gifted ({system_tune_node} :Context Building :Key "educationGiftedBonus"))
    (bind inquisitive ({system_tune_node} :Context Building :Key "educationInquisitiveBonus"))
    (bind (rateOK rate) (CallFunction|SchoolLearningRateData
      :TeacherGifted ({set_contains} teacher_traits "teacher")
      :StudentInquisitive ({set_contains} student_traits "inquisitive")
      :GiftedMultiplier gifted :InquisitiveMultiplier inquisitive))
    (return rateOK rate))"""
for source in code.values():
    blueprint_dsl.parse(source)
with toolset_registry.tool_raising_exceptions():
    for name, source in code.items():
        unreal.log("WO_JOB_SCORER_WRITE " + name)
        BP.write_graph_dsl(graphs[name], source)
    BP.compile_blueprint(bp, warnings_as_errors=True)
    assert unreal.EditorAssetLibrary.save_loaded_asset(bp)
    Path(unreal.Paths.project_saved_dir(), "WorkerOptimizer-JobScorer.dsl").write_text("\n\n".join(code.values()), encoding="utf-8")
unreal.log("WO_JOB_SCORER_GENERATED")
exec(Path(__file__).with_name("test_job_scorer.py").read_text(encoding="utf-8"))
exec(Path(__file__).with_name("test_builder_score.py").read_text(encoding="utf-8"))
