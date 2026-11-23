from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ConfigDict, StrictInt, ValidationError

from ceridwen.tools import TOOLS, build_tools, execute_tool


# A throwaway tool with typed arguments, so execute_tool's validation is
# tested independently of whichever real tools happen to exist.
class EchoArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n: StrictInt


def echo(n: int) -> int:
    return n


@pytest.fixture
def fake_tool(monkeypatch):
    monkeypatch.setitem(
        TOOLS,
        "echo",
        {
            "function": echo,
            "description": "Test-only tool that returns its argument.",
            "validation_schema": EchoArguments,
        },
    )


# --- execute_tool ---


def test_current_time_returns_utc_iso_timestamp():
    parsed = datetime.fromisoformat(execute_tool("current_time", {}))

    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == UTC.utcoffset(None)


def test_current_time_rejects_arguments():
    with pytest.raises(ValidationError):
        execute_tool("current_time", {"timezone": "Europe/London"})


def test_unknown_tool_raises_value_error():
    with pytest.raises(ValueError, match="not_a_tool"):
        execute_tool("not_a_tool", {})


def test_execute_tool_passes_validated_arguments(fake_tool):
    assert execute_tool("echo", {"n": 7}) == 7


@pytest.mark.parametrize(
    "args",
    [
        {"n": "7"},  # numeric string isn't coerced (StrictInt)
        {"n": 7.0},  # neither is a float
        {"n": True},  # bools are ints in Python, but not here
        {},  # missing argument
        {"n": 7, "m": 8},  # extra argument (extra="forbid")
    ],
)
def test_execute_tool_rejects_invalid_arguments(fake_tool, args):
    with pytest.raises(ValidationError):
        execute_tool("echo", args)


# --- registry ---


def test_every_tool_has_function_description_and_schema():
    for name, entry in TOOLS.items():
        assert callable(entry["function"]), name
        assert entry["description"].strip(), name
        assert "validation_schema" in entry, name


# --- build_tools ---


def test_build_tools_returns_one_entry_per_tool():
    tools = build_tools()

    assert len(tools) == len(TOOLS)
    assert {t["function"]["name"] for t in tools} == set(TOOLS)


def test_build_tools_uses_ollama_format():
    for t in build_tools():
        assert t["type"] == "function"
        assert set(t["function"]) == {"name", "description", "parameters"}

        entry = TOOLS[t["function"]["name"]]
        assert t["function"]["description"] == entry["description"]
        assert (
            t["function"]["parameters"]
            == entry["validation_schema"].model_json_schema()
        )


def test_build_tools_includes_typed_parameters(fake_tool):
    echo_tool = next(t for t in build_tools() if t["function"]["name"] == "echo")
    params = echo_tool["function"]["parameters"]

    assert params["type"] == "object"
    assert params["required"] == ["n"]
    assert params["properties"]["n"]["type"] == "integer"


def test_build_tools_current_time_takes_no_parameters():
    time_tool = next(
        t for t in build_tools() if t["function"]["name"] == "current_time"
    )
    params = time_tool["function"]["parameters"]

    assert params["properties"] == {}
    assert "required" not in params
