"""Ollama HTTP client: sends a conversation and translates the stream into events.

This is the only module that knows Ollama's wire format.
"""

import json
from collections.abc import Iterator

import httpx

from ceridwen.tools import build_tools


def list_models() -> list[str]:
    """Return the names of the models installed in Ollama.

    Raises:
        httpx.HTTPError: Ollama couldn't be reached or returned an error.
    """
    url = "http://127.0.0.1:11434/api/tags"
    response = httpx.get(url, timeout=5)
    response.raise_for_status()
    data = response.json()

    return [model["name"] for model in data["models"]]


def generate_title(model: str, message: str) -> str:
    """Ask the model for a short title for a conversation.

    A single non-streaming call, deliberately without tools (so the model
    can't decide to call one) and with thinking switched off (so it doesn't
    reason at length about four words). Quotes, full stops and whitespace
    around the reply are stripped.

    Args:
        model: Name of the Ollama model to use.
        message: The conversation's first user message.

    Returns:
        The title, which may be empty if the model replied with nothing usable.

    Raises:
        httpx.HTTPError: Ollama couldn't be reached or returned an error.
    """
    url = "http://127.0.0.1:11434/api/chat"
    response = httpx.post(
        url,
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Reply with only a title for this conversation, 3 to 6 words, no quotes or punctuation.",
                },
                {"role": "user", "content": message},
            ],
            "stream": False,
            "think": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"].strip(" \"'.\n")


def stream_chat(model: str, messages: list[dict]) -> Iterator[dict]:
    """Send a conversation to Ollama and yield its response as events.

    Makes one model call with every registered tool available. Ollama's
    newline-delimited chunks are translated into Ceridwen's own events, each
    a dict with ``type`` and ``data``:

    - ``thinking``: a chunk of the model's reasoning (str)
    - ``content``: a chunk of the answer (str)
    - ``tool_call``: one requested call, ``{id, name, arguments}``; ``id``
      is ``None`` if Ollama didn't send one
    - ``done``: metrics for the call, ``{done_reason, total_duration,
      eval_count, prompt_eval_count}``; ``total_duration`` is in nanoseconds

    Nothing happens until the generator is iterated, including connection
    errors.

    Args:
        model: Name of the Ollama model.
        messages: The full conversation, system message included.

    Yields:
        Events in the order Ollama sends them.

    Raises:
        httpx.HTTPError: Ollama couldn't be reached or returned an error.
    """
    with httpx.stream(
        "POST",
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "tools": build_tools(),
            "messages": messages,
            "stream": True,
        },
        timeout=120,
    ) as response:
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            message_payload = chunk["message"]
            thinking = message_payload.get("thinking")
            content = message_payload.get("content")
            tool_calls = message_payload.get("tool_calls")
            done = chunk.get("done")
            if thinking:
                yield {"type": "thinking", "data": thinking}
            if content:
                yield {"type": "content", "data": content}
            if tool_calls:
                for call in tool_calls:
                    call_id = call.get("id")
                    name = call["function"]["name"]
                    arguments = call["function"]["arguments"]
                    yield {
                        "type": "tool_call",
                        "data": {"id": call_id, "name": name, "arguments": arguments},
                    }
            if done:
                metrics = {
                    key: chunk[key]
                    for key in (
                        "done_reason",
                        "total_duration",
                        "eval_count",
                        "prompt_eval_count",
                    )
                }
                yield {"type": "done", "data": metrics}
