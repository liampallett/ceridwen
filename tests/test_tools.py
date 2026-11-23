from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ceridwen.tools import TOOLS, execute_tool


def test_add_returns_sum():
    assert execute_tool("add", {"a": 2, "b": 3}) == 5


def test_add_handles_negative_numbers():
    assert execute_tool("add", {"a": -4, "b": 1}) == -3


def test_current_time_returns_utc_iso_timestamp():
    r = execute_tool("current_time", {})

    parsed = datetime.fromisoformat(r)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == timezone.utc.utcoffset(None)


def test_unknown_tool_raises_value_error():
    with pytest.raises(ValueError, match="not_a_tool"):
        execute_tool("not_a_tool", {})


@pytest.mark.parametrize(
    "args",
    [
        {"a": "2", "b": 3},      # numeric string isn't coerced (StrictInt)
        {"a": 2.0, "b": 3},      # neither is a float
        {"a": True, "b": 3},     # bools are ints in Python, but not here
        {"a": 2},                # missing argument
        {"a": 2, "b": 3, "c": 4},  # extra argument (extra="forbid")
    ],
)
def test_add_rejects_invalid_arguments(args):
    with pytest.raises(ValidationError):
        execute_tool("add", args)


def test_current_time_rejects_arguments():
    with pytest.raises(ValidationError):
        execute_tool("current_time", {"timezone": "Europe/London"})


def test_every_tool_has_function_and_schema():
    for name, entry in TOOLS.items():
        assert callable(entry["function"]), name
        assert "validation_schema" in entry, name
