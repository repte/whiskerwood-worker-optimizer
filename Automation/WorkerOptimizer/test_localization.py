"""Catalog completeness and compiled localization; not linguistic/render acceptance."""
import json
import re
import sys
from collections import Counter
from pathlib import Path
from string import Formatter

LANGUAGES = ["en", "fr", "de", "it", "es", "ru", "ja", "zh", "ko", "tr", "pt", "pl", "ua", "cs", "hu", "zh-tw", "es-mx"]

def parameters(text):
    braces = [name for _, name, _, _ in Formatter().parse(text) if name is not None]
    printf = re.findall(r"(?<!%)%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[sdif]", text)
    return Counter(braces + printf)

def check_catalog():
    folder = Path(__file__).parent
    catalog = json.loads((folder / "translations.json").read_text(encoding="utf-8"))
    assert catalog["languages"] == LANGUAGES, "Catalog must expose exactly the native17 language IDs"
    evidence = json.loads((folder / "game_languages.json").read_text(encoding="utf-8"))
    assert evidence["languages"] == LANGUAGES and evidence["game_version"] == "0.7.209.0"
    ui = json.loads((folder / "ui_translations.json").read_text(encoding="utf-8"))
    assert ui["languages"] == LANGUAGES
    assert not set(catalog["strings"]) & set(ui["strings"]), "Duplicate authored UI keys"
    rows = dict(catalog["strings"], **ui["strings"])
    assert "reason.observation_unavailable" in rows, "Shutdown observation reason must be localized"
    for key, row in rows.items():
        assert len(row) == 17 and all(isinstance(cell, str) and cell.strip() for cell in row), key
        assert all(parameters(cell) == parameters(row[0]) for cell in row), (key, "interpolation")
        if row[0].endswith(" "): assert all(cell.endswith(" ") for cell in row), (key, "prefix spacing")
    for key, row in list(rows.items()):
        if key in ("mode", "reserve", "auto_assignment"):
            rows["title." + key] = ["Worker Optimizer: " + cell for cell in row]
        elif key.startswith("category."):
            rows["title." + key] = ["Worker Optimizer: " + rows["category"][i] + " - " + cell for i, cell in enumerate(row)]
    return rows

def run():
    rows = check_catalog()
    import unreal
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP
    path = "/Game/Mods/WorkerOptimizer/BP_PrioritySettings"
    bp = unreal.load_asset(path)
    cls = unreal.load_class(None, path + ".BP_PrioritySettings_C")
    defaults = unreal.get_default_object(cls)
    assert list(defaults.get_editor_property("Languages")) == LANGUAGES
    assert list(defaults.get_editor_property("TextKeys")) == list(rows)
    assert list(defaults.get_editor_property("TextValues")) == [cell for row in rows.values() for cell in row]
    settings = unreal.new_object(cls)
    call = lambda name, *args: settings.call_method(name, args=args)
    for i, lang in enumerate(LANGUAGES):
        assert call("Localize", "reason.observation_unavailable", lang) == rows["reason.observation_unavailable"][i]
    preserved = {name: list(settings.get_editor_property(name)) for name in ("KnownCategories", "KnownTypes", "FrozenCategories", "FrozenTypes", "FrozenCategoryValues", "FrozenTypeValues")}
    for key, row in rows.items():
        for i, lang in enumerate(LANGUAGES):
            assert call("Localize", key, lang) == row[i], (key, lang)
        for lang in ("zh-TW", "zh_TW", "zh-tw-extra", "es-MX", "es_MX", "es-mx-extra"):
            native = "zh-tw" if lang.lower().startswith("zh") else "es-mx"
            assert call("Localize", key, lang) == row[LANGUAGES.index(native)], (key, lang)
        for lang in ("xx", "nl_NL"):
            assert call("Localize", key, lang) == row[0]
    for lang in LANGUAGES:
        for level in range(5):
            assert call("ParsePriority", call("Localize", "priority." + str(level), lang), False) == (True, level)
        assert call("ParsePriority", call("Localize", "inherit", lang), True) == (True, -1)
        assert call("IsStrictValue", call("Localize", "strict", lang))
        assert not call("IsStrictValue", call("Localize", "weighted", lang))
    for level, alias in enumerate(("Zeer laag", "Laag", "Normaal", "Hoog", "Zeer hoog")):
        assert call("ParsePriority", alias, False) == (True, level)
        assert call("ParsePriority", str(level), False) == (True, level)
        assert call("ParsePriority", "WorkerOptimizer.ui.priority." + str(level), False) == (True, level)
    assert call("ParsePriority", "Categorie overnemen", True) == (True, -1)
    assert call("IsStrictValue", "Prioriteiten strikt volgen")
    assert not call("IsStrictValue", "Prioriteiten en productiviteit afwegen")
    for mode in ("off", "day_start", "minutes_5", "minutes_10", "minutes_15"):
        assert str(call("ParseAutoMode", mode)) == mode
        assert str(call("ParseAutoMode", "WorkerOptimizer.ui.auto." + mode)) == mode
    assert call("Localize", "reserve", "de-AT") == call("Localize", "reserve", "de")
    assert call("Localize", "reserve", "fr_CA") == call("Localize", "reserve", "fr")
    for name, value in preserved.items(): assert list(settings.get_editor_property(name)) == value
    general = BP.read_graph_dsl(BP.get_graph(bp, "RegisterGeneral"))
    assert "RegisterStrings" in general, "The manual icon still needs registered localization"
    for function in ("RegisterGeneral", "RegisterCategory", "RegisterType"):
        graph = BP.read_graph_dsl(BP.get_graph(bp, function))
        assert "RegisterModOptions" not in graph, "Dormant settings must not expose native options"
        assert "MigrateOption" not in graph, "Dormant settings must not rewrite saved options"
    assert "ListLanguageIds" in BP.read_graph_dsl(BP.get_graph(bp, "RegisterStrings")), "Registration must use native IDs"
    for number in (0, 7, 100): assert call("ParseReserve", str(number)) == number
    for bad in ("", "-1", "2x", "2.5", "1000000"): assert call("ParseReserve", bad) == 1
    assert call("ReadReserve", None) == 1
    unreal.log("WO_LOCALIZATION_TESTS_PASS: native17 catalog, every authored/derived cell, regional exact/prefix precedence, interpolation, Dutch migration, stable IDs, dormant options and nonmutating reads")

if "--data-only" in sys.argv:
    rows = check_catalog()
    print("WO_LOCALIZATION_DATA_PASS: " + str(len(rows)) + " authored/derived rows x17")
else:
    run()
