from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict


class CurrentTimeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


def current_time() -> str:
    return datetime.now(timezone.utc).isoformat()


TOOLS = {
    "current_time": {
        "function": current_time,
        "description": "Use this tool to fetch the current time in UTC, ISO format.",
        "validation_schema": CurrentTimeArguments
    }
}


def build_tools() -> list[dict]:
    tool_list = []
    for name, tool_dict in TOOLS.items():
        tool_list.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool_dict["description"],
                "parameters": tool_dict["validation_schema"].model_json_schema(),
            }
        })

    return tool_list


def execute_tool(name: str, args: dict):
    if name not in TOOLS:
        raise ValueError(f"Tool {name} not in tool dict.")
    tool_dict = TOOLS[name]
    tool = tool_dict["function"]
    validation_schema = tool_dict["validation_schema"]
    validated = validation_schema.model_validate(args)
    validated_args = validated.model_dump()
    return tool(**validated_args)