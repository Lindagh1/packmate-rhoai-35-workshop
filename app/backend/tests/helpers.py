import json
from types import SimpleNamespace


def make_tool_call(
    tool_id: str,
    tool_name: str,
    arguments: dict | str,
) -> SimpleNamespace:
    if isinstance(arguments, dict):
        arguments = json.dumps(arguments)

    return SimpleNamespace(
        id=tool_id,
        function=SimpleNamespace(name=tool_name, arguments=arguments),
    )
