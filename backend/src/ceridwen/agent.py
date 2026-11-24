"""The agent loop: call the model, run the tools it asks for, repeat until done."""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ceridwen.ollama_client import stream_chat
from ceridwen.tools import execute_tool

MAX_TURNS = 5  # maximum model calls per user message before giving up


def _without_thinking(messages: list[dict]) -> list[dict]:
    """Return copies of ``messages`` with any ``thinking`` key removed.

    Thinking is saved with each assistant message so the app can show it
    later, but the model has no use for its old reasoning, so it is left out
    of what gets sent back. The originals are not modified.
    """
    return [{k: v for k, v in m.items() if k != "thinking"} for m in messages]


def run_agent(model: str, messages: list[dict]) -> Iterator[dict]:
    """Run one user turn through the model, executing tool calls as they come.

    Each pass makes one model call and streams its events straight through.
    If the model asked for tools, they are run, the call and its results are
    added to the conversation, and the model is called again. The loop ends
    when the model replies without calling a tool, or after ``MAX_TURNS``
    passes.

    The system prompt is read from ``prompts/system.md`` on every call and
    placed in front of the conversation for each model call, but is never
    added to ``messages``, so it is never saved with a thread.

    Args:
        model: Name of the Ollama model to use.
        messages: The conversation so far, in Ollama's message format. It is
            modified in place: every assistant message, tool call and tool
            result from this turn is appended, so afterwards it holds the
            full conversation.

    Yields:
        Events from ``stream_chat`` as they arrive, plus a ``tool_result``
        event after each tool runs, and an ``error`` event if the turn limit
        is reached.
    """
    system_prompt = (Path(__file__).parent / "prompts" / "system.md").read_text()
    system_message = {
        "role": "system",
        "content": system_prompt.replace("{date}", datetime.now(UTC).isoformat()),
    }
    for _ in range(MAX_TURNS):  # one pass = one model call
        # fresh "notepads" for THIS model call
        # (what text did it say? what tools did it ask for?)
        thinking = ""
        content = ""
        tool_calls = []

        for event in stream_chat(model, [system_message, *_without_thinking(messages)]):
            yield event  # pass it straight on: the app keeps streaming
            # then peek at the event's type and note down anything you need
            match event["type"]:
                case "thinking":
                    thinking += event["data"]
                case "content":
                    content += event["data"]
                case "tool_call":
                    tool_calls.append(event["data"])
                case "done":
                    pass

        # 1. append the assistant's message (its text + tool calls) to messages
        message: dict = {"role": "assistant", "content": content}

        if tool_calls:
            message["tool_calls"] = [
                {
                    "id": call["id"],
                    "function": {
                        "name": call["name"],
                        "arguments": call["arguments"],
                    },
                }
                for call in tool_calls
            ]

        if thinking:
            message["thinking"] = thinking

        messages.append(message)

        if not tool_calls:
            return

        # 2. for each tool call: run it, append a {"role": "tool", ...} message

        for call in tool_calls:
            try:
                result = execute_tool(call["name"], call["arguments"])
                success = True
            except Exception as e:  # noqa: BLE001 - any tool failure is reported back to the model
                result = f"Error running {call['name']}: {e!r}"
                print(result)
                success = False

            result = str(result)

            messages.append(
                {"role": "tool", "tool_name": call["name"], "content": result}
            )

            yield {
                "type": "tool_result",
                "data": {
                    "id": call["id"],
                    "name": call["name"],
                    "result": result,
                    "success": success,
                },
            }
        # loop back round: the model gets called again with the longer list

    yield {"type": "error", "data": f"model exceeded {MAX_TURNS} tool calls"}
