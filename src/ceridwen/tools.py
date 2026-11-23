"""Tool registry: the tools the model can call, their schemas and validation.

Each entry in ``TOOLS`` has a function, a description (which the model relies
on to decide when to call it), and a Pydantic model describing its arguments.
The same Pydantic model generates the JSON Schema the model sees and validates
whatever arguments it sends, so the two can't drift apart.
"""

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict


# No docstrings on argument models: Pydantic copies a model's docstring into
# its JSON Schema, which would change what build_tools() sends to the model.
class CurrentTimeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def current_time() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


TOOLS = {
    "current_time": {
        "function": current_time,
        "description": "Use this tool to fetch the current time in UTC, ISO format.",
        "validation_schema": CurrentTimeArguments,
    }
}


def build_tools() -> list[dict]:
    """Describe every registered tool in the format Ollama expects.

    Returns:
        One ``{"type": "function", "function": {name, description,
        parameters}}`` dict per tool, where ``parameters`` is the JSON Schema
        generated from the tool's argument model.
    """
    tool_list = []
    for name, tool_dict in TOOLS.items():
        tool_list.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool_dict["description"],
                    "parameters": tool_dict["validation_schema"].model_json_schema(),
                },
            }
        )

    return tool_list


def execute_tool(name: str, args: dict):
    """Validate the model's arguments for a tool, then run it.

    Args:
        name: Tool name, as the model sent it.
        args: Arguments, as the model sent them.

    Returns:
        Whatever the tool returns.

    Raises:
        ValueError: No tool with that name is registered.
        pydantic.ValidationError: The arguments don't match the tool's schema.
    """
    if name not in TOOLS:
        raise ValueError(f"Tool {name} not in tool dict.")
    tool_dict = TOOLS[name]
    tool = tool_dict["function"]
    validation_schema = tool_dict["validation_schema"]
    validated = validation_schema.model_validate(args)
    validated_args = validated.model_dump()
    return tool(**validated_args)
