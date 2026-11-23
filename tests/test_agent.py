import copy
from unittest.mock import patch

import pytest

from ceridwen.agent import run_agent

MODEL = "gemma4:12b-mlx"
DONE = {"type": "done", "data": {"done_reason": "stop"}}


def text(s: str) -> dict:
    return {"type": "content", "data": s}


def thinking(s: str) -> dict:
    return {"type": "thinking", "data": s}


def tool_call(name: str, arguments: dict | None = None, call_id: str = "call_1") -> dict:
    return {"type": "tool_call", "data": {"id": call_id, "name": name, "arguments": arguments or {}}}


def tool_result(name: str, result: str, success: bool = True, call_id: str = "call_1") -> dict:
    return {"type": "tool_result", "data": {"id": call_id, "name": name, "result": result, "success": success}}


class FakeModel:
    """Stands in for stream_chat: one scripted list of events per model call.

    It records a *copy* of the messages it was sent each time, because
    run_agent keeps appending to the same list afterwards. The system
    message (always first) is recorded separately in system_prompts, so
    `seen` holds just the conversation. Calling it more
    times than scripted fails the test, which catches runaway loops.
    """

    def __init__(self, *turns: list[dict]):
        self.turns = list(turns)
        self.seen: list[list[dict]] = []
        self.system_prompts: list[dict] = []

    def __call__(self, model: str, messages: list[dict]):
        assert model == MODEL
        if not self.turns:
            pytest.fail("run_agent called the model more times than expected")
        self.system_prompts.append(copy.deepcopy(messages[0]))
        self.seen.append(copy.deepcopy(messages[1:]))  # conversation only, system message stripped
        return iter(self.turns.pop(0))


def run(fake: FakeModel, messages: list[dict]) -> list[dict]:
    with patch("ceridwen.agent.stream_chat", side_effect=fake):
        return list(run_agent(MODEL, messages))


# --- no tools ---

def test_plain_answer_passes_events_through_and_stops():
    turn = [thinking("Hmm"), text("Hello"), text("!"), DONE]
    fake = FakeModel(turn)
    messages = [{"role": "user", "content": "Hi"}]

    events = run(fake, messages)

    assert events == turn
    assert len(fake.seen) == 1
    assert messages == [{"role": "user", "content": "Hi"}]  # nothing appended


# --- one tool round trip ---

def test_tool_round_trip_calls_model_twice_and_streams_both_turns():
    first = [thinking("Need the time"), tool_call("current_time"), DONE]
    second = [text("It's 04:14."), DONE]
    fake = FakeModel(first, second)

    with patch("ceridwen.agent.execute_tool", return_value="2026-11-23T04:14:00+00:00"):
        events = run(fake, [{"role": "user", "content": "What time is it?"}])

    # the tool_result event sits between the two model turns
    assert events == first + [tool_result("current_time", "2026-11-23T04:14:00+00:00")] + second
    assert len(fake.seen) == 2


def test_tool_round_trip_builds_conversation_in_ollama_format():
    fake = FakeModel(
        [tool_call("current_time", call_id="call_abc"), DONE],
        [text("It's 04:14."), DONE],
    )
    messages = [{"role": "user", "content": "What time is it?"}]

    with patch("ceridwen.agent.execute_tool", return_value="2026-11-23T04:14:00+00:00"):
        run(fake, messages)

    expected = [
        {"role": "user", "content": "What time is it?"},
        {"role": "assistant", "content": "", "tool_calls": [
            {"id": "call_abc", "function": {"name": "current_time", "arguments": {}}}
        ]},
        {"role": "tool", "tool_name": "current_time", "content": "2026-11-23T04:14:00+00:00"},
    ]
    assert fake.seen[1] == expected   # what the second model call was sent
    assert messages == expected       # the caller's list was grown in place


def test_tool_is_executed_with_its_name_and_arguments():
    fake = FakeModel(
        [tool_call("weather", {"location": "Sheffield"}), DONE],
        [text("Grim."), DONE],
    )

    with patch("ceridwen.agent.execute_tool", return_value="rain") as mock_exec:
        run(fake, [{"role": "user", "content": "Weather?"}])

    mock_exec.assert_called_once_with("weather", {"location": "Sheffield"})


def test_non_string_tool_results_are_stringified():
    fake = FakeModel([tool_call("count"), DONE], [text("42."), DONE])
    messages = [{"role": "user", "content": "Count"}]

    with patch("ceridwen.agent.execute_tool", return_value=42):
        run(fake, messages)

    assert messages[-1]["content"] == "42"


def test_text_said_alongside_a_tool_call_is_kept():
    fake = FakeModel(
        [text("Let me "), text("check."), tool_call("current_time"), DONE],
        [text("04:14."), DONE],
    )
    messages = [{"role": "user", "content": "Time?"}]

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        run(fake, messages)

    assert messages[1]["content"] == "Let me check."


# --- several tools ---

def test_two_tool_calls_in_one_turn():
    fake = FakeModel(
        [tool_call("current_time", call_id="a"), tool_call("weather", {"location": "Sheffield"}, call_id="b"), DONE],
        [text("Done."), DONE],
    )
    messages = [{"role": "user", "content": "Time and weather?"}]

    with patch("ceridwen.agent.execute_tool", side_effect=["04:14", "rain"]) as mock_exec:
        run(fake, messages)

    # one assistant message carrying both calls, then one tool message per call, in order
    assert [c["id"] for c in messages[1]["tool_calls"]] == ["a", "b"]
    assert messages[2] == {"role": "tool", "tool_name": "current_time", "content": "04:14"}
    assert messages[3] == {"role": "tool", "tool_name": "weather", "content": "rain"}
    assert mock_exec.call_count == 2


def test_chained_tool_calls_across_turns():
    # model calls one tool, sees the result, calls another, then answers
    fake = FakeModel(
        [tool_call("current_time", call_id="a"), DONE],
        [tool_call("weather", call_id="b"), DONE],
        [text("All done."), DONE],
    )

    with patch("ceridwen.agent.execute_tool", side_effect=["04:14", "rain"]):
        events = run(fake, [{"role": "user", "content": "Go"}])

    assert len(fake.seen) == 3
    assert len(fake.seen[2]) == 5   # user, assistant, tool, assistant, tool
    assert events[-2:] == [text("All done."), DONE]


def test_notepads_reset_between_turns():
    # If tool_calls carried over from turn 1, turn 2 would look like it called
    # a tool again and the agent would ask the model a third time (FakeModel fails).
    fake = FakeModel([tool_call("current_time"), DONE], [text("04:14."), DONE])

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        run(fake, [{"role": "user", "content": "Time?"}])

    assert len(fake.seen) == 2


# --- tool_result events ---

def test_tool_result_event_carries_stringified_result():
    fake = FakeModel([tool_call("count", call_id="c1"), DONE], [text("42."), DONE])

    with patch("ceridwen.agent.execute_tool", return_value=42):
        events = run(fake, [{"role": "user", "content": "Count"}])

    assert tool_result("count", "42", call_id="c1") in events


def test_one_tool_result_event_per_call_matched_by_id():
    fake = FakeModel(
        [tool_call("current_time", call_id="a"), tool_call("weather", call_id="b"), DONE],
        [text("Done."), DONE],
    )

    with patch("ceridwen.agent.execute_tool", side_effect=["04:14", "rain"]):
        events = run(fake, [{"role": "user", "content": "Go"}])

    results = [e["data"] for e in events if e["type"] == "tool_result"]
    assert [(r["id"], r["result"]) for r in results] == [("a", "04:14"), ("b", "rain")]


# --- failing tools ---

def test_failing_tool_does_not_crash_the_stream():
    fake = FakeModel([tool_call("add", {"a": 2, "b": 2}), DONE], [text("2 + 2 = 4"), DONE])

    with patch("ceridwen.agent.execute_tool", side_effect=ValueError("Tool add not in tool dict.")):
        events = run(fake, [{"role": "user", "content": "Use add"}])

    assert len(fake.seen) == 2                       # the model got a second turn
    assert events[-2:] == [text("2 + 2 = 4"), DONE]  # and its answer streamed


def test_failing_tool_is_reported_to_the_model():
    fake = FakeModel([tool_call("add"), DONE], [text("No add tool."), DONE])
    messages = [{"role": "user", "content": "Use add"}]

    with patch("ceridwen.agent.execute_tool", side_effect=ValueError("Tool add not in tool dict.")):
        run(fake, messages)

    tool_message = fake.seen[1][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_name"] == "add"
    assert "Tool add not in tool dict." in tool_message["content"]


def test_failing_tool_result_event_is_marked_unsuccessful():
    fake = FakeModel([tool_call("add"), DONE], [text("No add tool."), DONE])

    with patch("ceridwen.agent.execute_tool", side_effect=RuntimeError("boom")):
        events = run(fake, [{"role": "user", "content": "Use add"}])

    [result] = [e["data"] for e in events if e["type"] == "tool_result"]
    assert result["success"] is False
    assert "boom" in result["result"]


def test_one_failing_tool_does_not_stop_the_others():
    fake = FakeModel(
        [tool_call("add", call_id="a"), tool_call("current_time", call_id="b"), DONE],
        [text("Done."), DONE],
    )
    messages = [{"role": "user", "content": "Go"}]

    with patch("ceridwen.agent.execute_tool", side_effect=[ValueError("nope"), "04:14"]):
        events = run(fake, messages)

    results = {e["data"]["id"]: e["data"]["success"] for e in events if e["type"] == "tool_result"}
    assert results == {"a": False, "b": True}
    assert messages[3] == {"role": "tool", "tool_name": "current_time", "content": "04:14"}


def test_real_unknown_tool_goes_through_execute_tool():
    # No patching of execute_tool: the genuine "not in tool dict" path.
    fake = FakeModel([tool_call("definitely_not_a_tool"), DONE], [text("Sorry."), DONE])

    events = run(fake, [{"role": "user", "content": "Go"}])

    [result] = [e["data"] for e in events if e["type"] == "tool_result"]
    assert result["success"] is False
    assert "definitely_not_a_tool" in result["result"]


# --- turn limit ---

def test_stops_with_error_event_after_max_turns():
    from ceridwen.agent import MAX_TURNS

    # a model that asks for a tool every single time
    fake = FakeModel(*[[tool_call("current_time"), DONE] for _ in range(MAX_TURNS)])

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        events = run(fake, [{"role": "user", "content": "Loop forever"}])

    assert len(fake.seen) == MAX_TURNS     # never asks a sixth time (FakeModel would fail)
    assert events[-1]["type"] == "error"
    assert [e["type"] for e in events].count("error") == 1


def test_no_error_event_when_answered_within_limit():
    fake = FakeModel([tool_call("current_time"), DONE], [text("04:45."), DONE])

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        events = run(fake, [{"role": "user", "content": "Time?"}])

    assert all(e["type"] != "error" for e in events)


# --- system prompt ---

def test_system_prompt_is_sent_first_on_every_model_call():
    fake = FakeModel([tool_call("current_time"), DONE], [text("04:14."), DONE])

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        run(fake, [{"role": "user", "content": "Time?"}])

    assert len(fake.system_prompts) == 2
    for system in fake.system_prompts:
        assert system["role"] == "system"
        assert "Ceridwen" in system["content"]


def test_system_prompt_is_not_stored_in_the_conversation():
    fake = FakeModel([tool_call("current_time"), DONE], [text("04:14."), DONE])
    messages = [{"role": "user", "content": "Time?"}]

    with patch("ceridwen.agent.execute_tool", return_value="t"):
        run(fake, messages)

    assert all(m["role"] != "system" for m in messages)


def test_system_prompt_comes_from_system_md():
    from pathlib import Path

    import ceridwen.agent

    prompt_file = Path(ceridwen.agent.__file__).parent / "prompts" / "system.md"
    fake = FakeModel([text("Hi"), DONE])

    run(fake, [{"role": "user", "content": "Hi"}])

    assert fake.system_prompts[0]["content"] == prompt_file.read_text()


def test_system_prompt_is_reread_on_each_request(monkeypatch):
    # Edits to system.md must apply from the next message, without a restart.
    import ceridwen.agent

    prompts = iter(["You are version one.", "You are version two."])
    monkeypatch.setattr(ceridwen.agent.Path, "read_text", lambda self, *a, **kw: next(prompts))

    first, second = FakeModel([text("Hi"), DONE]), FakeModel([text("Hi"), DONE])
    run(first, [{"role": "user", "content": "Hi"}])
    run(second, [{"role": "user", "content": "Hi"}])

    assert first.system_prompts[0]["content"] == "You are version one."
    assert second.system_prompts[0]["content"] == "You are version two."
