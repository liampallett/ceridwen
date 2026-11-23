from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, StrictInt


class AddArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: StrictInt
    b: StrictInt


def add(a: int, b: int) -> int:
    return a + b


class CurrentTimeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def current_time() -> str:
    return datetime.now(timezone.utc).isoformat()


TOOLS = {
    "add": {
        "function": add,
        "validation_schema": AddArguments
    },
    "current_time": {
        "function": current_time,
        "validation_schema": CurrentTimeArguments
    }
}


def execute_tool(name: str, args: dict):
    if name not in TOOLS:
        raise ValueError(f"Tool {name} not in tool dict.")
    tool_dict = TOOLS[name]
    tool = tool_dict["function"]
    validation_schema = tool_dict["validation_schema"]
    validated = validation_schema.model_validate(args)
    validated_args = validated.model_dump()
    return tool(**validated_args)