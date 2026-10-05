"""Exercise native option policy, type inheritance and stable configuration keys."""

import unreal


def run():
    cls = unreal.load_class(None, "/Game/Mods/WorkerOptimizer/BP_PrioritySettings.BP_PrioritySettings_C")
    assert cls, "Production priority settings do not exist"
    settings = unreal.new_object(cls)
    call = lambda name, *args: settings.call_method(name, args=args)
    for priority in range(5):
        assert call("ParsePriority", str(priority), False) == (True, priority)
        assert call("ParsePriority", str(priority), True) == (True, priority)
        assert call("ResolvePriority", str(priority), "inherit") == priority
        for override in range(5):
            assert call("ResolvePriority", str(priority), str(override)) == override
    assert call("ParsePriority", "inherit", True) == (True, -1)
    assert not call("ParsePriority", "inherit", False)[0]
    for bad in ("", "-1", "5", "100", "2.0", "2x", "garbage", " 3"):
        assert not call("ParsePriority", bad, True)[0]
        assert call("ResolvePriority", bad, "inherit") == 2
        assert call("ResolvePriority", "4", bad) == 4
        assert call("ResolvePriority", bad, "0") == 0
    assert call("IsStrictValue", "Strict")
    assert not call("IsStrictValue", "Weighted")
    assert call("IsStrictValue", "future_unsupported_mode")
    category_key = call("CategoryOptionId", "food.production")
    type_key = call("TypeOptionId", "food.production")
    assert category_key == "WorkerOptimizer.category.food.production"
    assert type_key == "WorkerOptimizer.type.food.production"
    assert category_key != type_key, "Categories and types cannot overwrite one another"
    assert call("TypeOptionId", "future.building") == "WorkerOptimizer.type.future.building"
    assert call("CategoryLabelKey", "food_process") == "toolbar.food_process"
    assert call("ResolveLabel", "future.building", "missing.translation") == "future.building"
    assert not call("EnsureDefinitionOptions", None, "future.building", "food_process", "missing.translation")
    assert not call("RegisterGeneral", None)
    assert not call("RegisterCategory", None, "food", "Nahrung")
    assert not call("RegisterType", None, "future.building", "New Building")
    assert call("ReadPriority", None, "food", "future.building") == 2
    assert call("ReadStrictMode", None)
    invalid_context = settings
    assert not call("EnsureDefinitionOptions", invalid_context, "future.building", "food_process", "missing.translation")
    assert not call("EnsureDefinitionOptions", invalid_context, "None", "food_process", "")
    assert not list(settings.get_editor_property("RegisteredCategories")), "Native failures must not populate the registration cache"
    assert not list(settings.get_editor_property("RegisteredTypes"))
    assert not call("RegisterGeneral", invalid_context)
    assert not call("RegisterCategory", invalid_context, "food", "Food")
    assert not call("RegisterType", invalid_context, "future.building", "New Building")
    assert call("ReadPriority", invalid_context, "food", "future.building") == 2
    assert call("ReadStrictMode", invalid_context)
    unreal.log("WO_PRIORITY_SETTINGS_TESTS_PASS: five levels, all type/category combinations, inheritance for new types, malformed stored values, distinct internal keys and strict/weighted parsing; native settings persistence not exercised")


run()
