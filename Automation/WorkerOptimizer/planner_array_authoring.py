"""Local MakeArray64 authoring configuration; no global toolset replacement."""

import re


MAKE_ARRAY = 'Utilities|Array|MakeArray'


def configure_make_array64(target_graph, type_id, created_node, *, add_node_pin=None):
    """Post-create callback shared by ordinary and direct-member writers."""
    if type_id != MAKE_ARRAY:
        return
    if add_node_pin is None:
        from editor_toolset.toolsets.blueprint import BlueprintTools as BP
        add_node_pin = BP.add_node_pin

    def indices():
        result = []
        for pin in created_node.list_all_pins():
            match = re.fullmatch(r'\[(\d+)\]', str(pin.get_pin_name()))
            if match:
                result.append(int(match.group(1)))
        return sorted(result)

    current = indices()
    assert 1 <= len(current) <= 64 and current == list(range(len(current))), current
    for _ in range(len(current), 64):
        add_node_pin(created_node)
    assert indices() == list(range(64)), 'MakeArray64 must expose exactly64 contiguous element pins'


def decorate_create_node(create_node_fn, post_create_callback):
    """Compose after creation, preserving the original arguments and node."""
    def create_node(target_graph, type_id, position, *args, **kwargs):
        node = create_node_fn(target_graph, type_id, position, *args, **kwargs)
        if post_create_callback is not None:
            post_create_callback(target_graph, type_id, node)
        return node
    return create_node


def write_graph_dsl(graph, code, *, post_create_callback=None):
    """BlueprintTools-equivalent writer with an optional graph-local callback."""
    import unreal
    import toolset_registry
    from editor_toolset.toolsets import blueprint_dsl
    from editor_toolset.toolsets.blueprint import BlueprintTools as BP

    if post_create_callback is None:
        return BP.write_graph_dsl(graph, code)
    with toolset_registry.tool_raising_exceptions():
        blueprint_dsl.Transpiler(
            graph, decorate_create_node(BP.create_node, post_create_callback),
            BP.connect_pins, BP._get_node_info, BP.set_pin_value,
            lambda target: BP.find_nodes(target), delete_node_fn=BP.delete_node,
            find_node_types_fn=lambda query: BP.find_node_types(graph, query),
        ).transpile(code)
        blueprint = unreal.Blueprint.cast(graph.get_outer())
        if blueprint:
            BP.compile_blueprint(blueprint)
