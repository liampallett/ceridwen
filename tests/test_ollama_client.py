import json
from unittest.mock import patch

import httpx
import pytest

from ceridwen.ollama_client import stream_chat
from ceridwen.tools import build_tools

MODEL = "gemma4:12b-mlx"


def run_stream(chunks: list) -> list[dict]:
    """Feed fake Ollama lines through stream_chat and collect the events.

    Dicts are JSON-encoded like Ollama's real output; strings are passed
    through as-is (handy for blank lines).
    """
    lines = [c if isinstance(c, str) else json.dumps(c) for c in chunks]
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_response = mock_stream.return_value.__enter__.return_value
        mock_response.iter_lines.return_value = lines
        return list(stream_chat(MODEL, "Hello"))


def msg(**fields) -> dict:
    """A mid-stream Ollama chunk with the given message fields."""
    return {"model": MODEL, "message": {"role": "assistant", "content": "", **fields}, "done": False}


DONE_CHUNK = {
    "model": MODEL,
    "message": {"role": "assistant", "content": ""},
    "done": True,
    "done_reason": "stop",
    "total_duration": 458613750,
    "load_duration": 1613125,
    "prompt_eval_count": 56,
    "prompt_eval_duration": 92917,
    "eval_count": 36,
    "eval_duration": 455230042,
}


# --- the request ---

def test_stream_chat_connection_error():
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_stream.side_effect = httpx.ConnectError("Connection refused")

        # stream_chat is a generator: nothing runs (so nothing raises)
        # until it's iterated, hence list().
        with pytest.raises(httpx.ConnectError):
            list(stream_chat(MODEL, "Hello"))


def test_stream_chat_sends_expected_request():
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value.iter_lines.return_value = []

        list(stream_chat(MODEL, "Hello"))

        mock_stream.assert_called_once_with(
            "POST",
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": MODEL,
                "tools": build_tools(),
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
            },
            timeout=120,
        )


# --- events ---

def test_content_chunks_become_content_events():
    events = run_stream([msg(content="Hello"), msg(content=" world")])

    assert events == [
        {"type": "content", "data": "Hello"},
        {"type": "content", "data": " world"},
    ]


def test_thinking_chunks_become_thinking_events():
    events = run_stream([msg(thinking="The"), msg(thinking=" user")])

    assert events == [
        {"type": "thinking", "data": "The"},
        {"type": "thinking", "data": " user"},
    ]


def test_empty_chunks_and_blank_lines_yield_nothing():
    assert run_stream(["", msg(), msg(content="", thinking="")]) == []


def test_tool_call_is_flattened():
    events = run_stream([msg(tool_calls=[
        {"id": "call_314rv1rn", "function": {"index": 0, "name": "current_time", "arguments": {}}}
    ])])

    assert events == [{
        "type": "tool_call",
        "data": {"id": "call_314rv1rn", "name": "current_time", "arguments": {}},
    }]


def test_multiple_tool_calls_in_one_chunk_become_separate_events_in_order():
    events = run_stream([msg(tool_calls=[
        {"id": "call_a", "function": {"index": 0, "name": "current_time", "arguments": {}}},
        {"id": "call_b", "function": {"index": 1, "name": "weather", "arguments": {"location": "Sheffield"}}},
    ])])

    assert [e["data"]["id"] for e in events] == ["call_a", "call_b"]
    assert events[1]["data"]["arguments"] == {"location": "Sheffield"}


def test_tool_call_without_id_gets_none():
    events = run_stream([msg(tool_calls=[
        {"function": {"name": "current_time", "arguments": {}}}
    ])])

    assert events[0]["data"]["id"] is None


def test_done_chunk_yields_selected_metrics_only():
    events = run_stream([DONE_CHUNK])

    assert events == [{
        "type": "done",
        "data": {
            "done_reason": "stop",
            "total_duration": 458613750,
            "eval_count": 36,
            "prompt_eval_count": 56,
        },
    }]


def test_realistic_tool_call_turn():
    # Shape of a real Gemma response: think, call a tool, finish.
    events = run_stream([
        msg(thinking="I should use"),
        msg(thinking=" current_time."),
        msg(tool_calls=[{"id": "call_1", "function": {"index": 0, "name": "current_time", "arguments": {}}}]),
        DONE_CHUNK,
    ])

    assert [e["type"] for e in events] == ["thinking", "thinking", "tool_call", "done"]
