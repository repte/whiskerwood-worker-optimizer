"""Check compiled translations, fallback and language-independent saved policies."""

import unreal
from editor_toolset.toolsets.blueprint import BlueprintTools as BP


def run():
    path = "/Game/Mods/WorkerOptimizer/BP_PrioritySettings"
    bp = unreal.load_asset(path)
    assert "Localize" in {str(g.get_name()) for g in BP.list_graphs(bp)}, "Mod text has no five-language translation path"
    settings = unreal.new_object(unreal.load_class(None, path + ".BP_PrioritySettings_C"))
    call = lambda name, *args: settings.call_method(name, args=args)
    general = BP.read_graph_dsl(BP.get_graph(bp, "RegisterGeneral"))
    assert "WorkerOptimizer.ui.title.mode" in general, "Setting titles must remain language keys, not eagerly translated text"
    assert "WorkerOptimizer.ui.title.reserve" in general
    assert "WorkerOptimizer.ui.title.category." in BP.read_graph_dsl(BP.get_graph(bp, "RegisterCategory"))
    expected = {"en": "Normal", "de": "Normal", "pl": "Normalny", "fr": "Normale", "nl": "Normaal"}
    for lang, normal in expected.items():
        assert call("Localize", "priority.2", lang) == normal
        for level in range(5):
            value = call("Localize", "priority." + str(level), lang)
            assert call("ParsePriority", value, False) == (True, level), (lang, value)
        assert call("ParsePriority", call("Localize", "inherit", lang), True) == (True, -1)
        assert call("IsStrictValue", call("Localize", "strict", lang))
        assert not call("IsStrictValue", call("Localize", "weighted", lang))
        for key in ("reserve", "mode", "category", "type", "optimize", "cancel", "completed", "waiting", "hotkey", "failed", "reserve_desc"):
            value = call("Localize", key, lang)
            assert value and value != key, (lang, key)
        assert call("Localize", "title.reserve", lang) == "Worker Optimizer: " + call("Localize", "reserve", lang)
    assert call("Localize", "priority.2", "xx") == "Normal"
    assert call("Localize", "priority.2", "pl-PL") == "Normalny"
    assert call("Localize", "priority.2", "nl_NL") == "Normaal"
    assert call("Localize", "reserve", "de-AT") == call("Localize", "reserve", "de")
    assert call("Localize", "reserve", "fr_CA") == call("Localize", "reserve", "fr")
    assert call("ParseReserve", "0") == 0
    assert call("ParseReserve", "7") == 7
    assert call("ParseReserve", "100") == 100
    for bad in ("", "-1", "2x", "2.5", "1000000"):
        assert call("ParseReserve", bad) == 1
    assert call("ReadReserve", None) == 1
    unreal.log("WO_LOCALIZATION_TESTS_PASS: five languages, regional and unsupported fallback, multilingual value migration and reserve parsing")


run()
