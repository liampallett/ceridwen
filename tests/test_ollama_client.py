import json
from unittest.mock import patch

import httpx
import pytest

from ceridwen.ollama_client import stream_chat
from ceridwen.tools import build_tools

MODEL = "gemma4:12b-mlx"
MESSAGES = [{"role": "user", "content": "Hello"}]


def run_stream(chunks: list) -> list[dict]:
    """Feed fake Ollama lines through stream_chat and collect the events.

    Dicts are JSON-encoded like Ollama's real output; strings are passed
    through as-is (handy for blank lines).
    """
    lines = [c if isinstance(c, str) else json.dumps(c) for c in chunks]
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_response = mock_stream.return_value.__enter__.return_value
        mock_response.iter_lines.return_value = lines
        return list(stream_chat(MODEL, MESSAGES))


def msg(**fields) -> dict:
    """A mid-stream Ollama chunk with the given message fields."""
    return {
        "model": MODEL,
        "message": {"role": "assistant", "content": "", **fields},
        "done": False,
    }


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
            list(stream_chat(MODEL, MESSAGES))


def test_stream_chat_sends_expected_request():
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value.iter_lines.return_value = []

        list(stream_chat(MODEL, MESSAGES))

        mock_stream.assert_called_once_with(
            "POST",
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": MODEL,
                "tools": build_tools(),
                "messages": MESSAGES,
                "stream": True,
            },
            timeout=120,
        )


def test_stream_chat_sends_whole_conversation_unchanged():
    conversation = [
        {"role": "user", "content": "What time is it?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"function": {"name": "current_time", "arguments": {}}}],
        },
        {
            "role": "tool",
            "tool_name": "current_time",
            "content": "2026-11-23T03:49:00+00:00",
        },
    ]
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_stream.return_value.__enter__.return_value.iter_lines.return_value = []

        list(stream_chat(MODEL, conversation))

        assert mock_stream.call_args.kwargs["json"]["messages"] == conversation


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
    events = run_stream(
        [
            msg(
                tool_calls=[
                    {
                        "id": "call_314rv1rn",
                        "function": {
                            "index": 0,
                            "name": "current_time",
                            "arguments": {},
                        },
                    }
                ]
            )
        ]
    )

    assert events == [
        {
            "type": "tool_call",
            "data": {"id": "call_314rv1rn", "name": "current_time", "arguments": {}},
        }
    ]


def test_multiple_tool_calls_in_one_chunk_become_separate_events_in_order():
    events = run_stream(
        [
            msg(
                tool_calls=[
                    {
                        "id": "call_a",
                        "function": {
                            "index": 0,
                            "name": "current_time",
                            "arguments": {},
                        },
                    },
                    {
                        "id": "call_b",
                        "function": {
                            "index": 1,
                            "name": "weather",
                            "arguments": {"location": "Sheffield"},
                        },
                    },
                ]
            )
        ]
    )

    assert [e["data"]["id"] for e in events] == ["call_a", "call_b"]
    assert events[1]["data"]["arguments"] == {"location": "Sheffield"}


def test_tool_call_without_id_gets_none():
    events = run_stream(
        [msg(tool_calls=[{"function": {"name": "current_time", "arguments": {}}}])]
    )

    assert events[0]["data"]["id"] is None


def test_done_chunk_yields_selected_metrics_only():
    events = run_stream([DONE_CHUNK])

    assert events == [
        {
            "type": "done",
            "data": {
                "done_reason": "stop",
                "total_duration": 458613750,
                "eval_count": 36,
                "prompt_eval_count": 56,
            },
        }
    ]


def test_realistic_tool_call_turn():
    # Shape of a real Gemma response: think, call a tool, finish.
    events = run_stream(
        [
            msg(thinking="I should use"),
            msg(thinking=" current_time."),
            msg(
                tool_calls=[
                    {
                        "id": "call_1",
                        "function": {
                            "index": 0,
                            "name": "current_time",
                            "arguments": {},
                        },
                    }
                ]
            ),
            DONE_CHUNK,
        ]
    )

    assert [e["type"] for e in events] == ["thinking", "thinking", "tool_call", "done"]


# --- list_models ---


def test_list_models_returns_names_only():
    from ceridwen.ollama_client import list_models

    with patch("ceridwen.ollama_client.httpx.get") as mock_get:
        mock_get.return_value.json.return_value = {
            "models": [
                {"name": "gemma4:12b-mlx", "size": 7400000000, "details": {}},
                {"name": "qwen3:8b", "size": 5200000000, "details": {}},
            ]
        }

        assert list_models() == ["gemma4:12b-mlx", "qwen3:8b"]
        assert mock_get.call_args.args[0] == "http://127.0.0.1:11434/api/tags"


def test_list_models_raises_when_ollama_is_down():
    from ceridwen.ollama_client import list_models

    with patch("ceridwen.ollama_client.httpx.get") as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            list_models()


# --- generate_title ---


def run_generate_title(reply: str):
    from ceridwen.ollama_client import generate_title

    with patch("ceridwen.ollama_client.httpx.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "model": MODEL,
            "message": {"role": "assistant", "content": reply},
            "done": True,
        }
        title = generate_title(MODEL, "What time is it?")
    return title, mock_post


def test_generate_title_returns_the_reply():
    title, _ = run_generate_title("Current time query")
    assert title == "Current time query"


@pytest.mark.parametrize("reply", ['"Current time query"', "Current time query.", "  Current time query\n"])
def test_generate_title_strips_quotes_punctuation_and_whitespace(reply):
    title, _ = run_generate_title(reply)
    assert title == "Current time query"


def test_generate_title_request_has_no_tools_and_no_streaming():
    _, mock_post = run_generate_title("Current time query")

    body = mock_post.call_args.kwargs["json"]
    assert mock_post.call_args.args[0] == "http://127.0.0.1:11434/api/chat"
    assert "tools" not in body           # a title request must not be able to call tools
    assert body["stream"] is False
    assert body["think"] is False
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][-1] == {"role": "user", "content": "What time is it?"}


def test_generate_title_raises_when_ollama_errors():
    from ceridwen.ollama_client import generate_title

    with patch("ceridwen.ollama_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            generate_title(MODEL, "Hi")
