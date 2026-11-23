import copy
import json

import pytest
from fastapi.testclient import TestClient

from ceridwen import main

MODEL = "gemma4:12b-mlx"

EVENTS = [
    {"type": "thinking", "data": "Line one\nline two"},
    {"type": "content", "data": "Hello"},
    {
        "type": "tool_call",
        "data": {"id": None, "name": "current_time", "arguments": {}},
    },
    {"type": "done", "data": {"done_reason": "stop", "eval_count": 3}},
]


class FakeAgent:
    """Stands in for run_agent.

    Like the real one, it grows the messages list in place (here: one
    assistant reply) and yields events. It records a copy of what it was
    given each time, so tests can check the history the agent saw.
    """

    def __init__(self, reply: str = "Hello", events: list[dict] | None = None):
        self.reply = reply
        self.events = events if events is not None else EVENTS
        self.seen: list[list[dict]] = []

    def __call__(self, model: str, messages: list[dict]):
        assert model == MODEL
        self.seen.append(copy.deepcopy(messages))
        messages.append({"role": "assistant", "content": self.reply})
        yield from self.events


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Point the app at a throwaway database, then start it. Using TestClient
    # as a context manager runs the lifespan, so init_db creates the tables.
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "test.db")
    # Never reach a real Ollama for titles; tests that care override this.
    monkeypatch.setattr(main, "generate_title", lambda model, message: "")
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def agent(monkeypatch):
    fake = FakeAgent()
    monkeypatch.setattr(main, "run_agent", fake)
    return fake


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def new_thread(client) -> str:
    return client.post("/threads").json()["id"]


def chat(client, thread_id: str, message: str):
    return client.post(
        "/chat", json={"model": MODEL, "message": message, "thread_id": thread_id}
    )


# --- threads ---


def test_no_threads_to_start_with(client):
    assert client.get("/threads").json() == []


def test_create_thread_returns_id_and_it_is_listed(client):
    r = client.post("/threads")

    assert r.status_code == 200
    thread_id = r.json()["id"]
    assert [t["id"] for t in client.get("/threads").json()] == [thread_id]


def test_new_thread_has_no_messages(client):
    assert client.get(f"/threads/{new_thread(client)}/messages").json() == []


def test_messages_for_unknown_thread_is_404(client):
    assert client.get("/threads/nonsense/messages").status_code == 404


def test_delete_thread(client):
    thread_id = new_thread(client)

    assert client.delete(f"/threads/{thread_id}").status_code == 200
    assert client.get("/threads").json() == []
    assert client.get(f"/threads/{thread_id}/messages").status_code == 404


def test_delete_unknown_thread_is_404(client):
    assert client.delete("/threads/nonsense").status_code == 404


# --- chat: request handling ---


def test_chat_unknown_thread_is_404_and_agent_never_runs(client, agent):
    r = chat(client, "nonsense", "Hello")

    assert r.status_code == 404
    assert agent.seen == []


def test_chat_requires_thread_id(client, agent):
    r = client.post("/chat", json={"model": MODEL, "message": "Hello"})
    assert r.status_code == 422


# --- chat: streaming ---


def test_chat_streams_ndjson(client, agent):
    r = chat(client, new_thread(client), "Hello")

    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-ndjson")


def test_chat_one_valid_json_object_per_line(client, agent):
    r = chat(client, new_thread(client), "Hello")

    # Newlines inside the data (the thinking event) must be escaped,
    # not split across lines.
    assert r.text.endswith("\n")
    assert [json.loads(line) for line in r.text.splitlines()] == EVENTS


# --- chat: history and saving ---


def test_first_message_reaches_agent_on_its_own(client, agent):
    chat(client, new_thread(client), "Hello")

    assert agent.seen == [[{"role": "user", "content": "Hello"}]]


def test_chat_saves_user_message_and_agent_reply(client, agent):
    thread_id = new_thread(client)

    chat(client, thread_id, "Hello")

    assert client.get(f"/threads/{thread_id}/messages").json() == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello"},
    ]


def test_second_message_sees_the_first_in_order(client, agent):
    thread_id = new_thread(client)

    chat(client, thread_id, "First")
    chat(client, thread_id, "Second")

    # history first, newest message last
    assert agent.seen[1] == [
        {"role": "user", "content": "First"},
        {"role": "assistant", "content": "Hello"},
        {"role": "user", "content": "Second"},
    ]


def test_history_is_not_saved_twice(client, agent):
    thread_id = new_thread(client)

    chat(client, thread_id, "First")
    chat(client, thread_id, "Second")

    assert len(client.get(f"/threads/{thread_id}/messages").json()) == 4


def test_threads_do_not_share_history(client, agent):
    a, b = new_thread(client), new_thread(client)

    chat(client, a, "For A")
    chat(client, b, "For B")

    assert agent.seen[1] == [{"role": "user", "content": "For B"}]


def test_chatting_moves_thread_to_top_of_list(client, agent):
    old, new = new_thread(client), new_thread(client)

    chat(client, old, "Bump")

    assert [t["id"] for t in client.get("/threads").json()] == [old, new]


# --- Ollama errors mid-stream ---


def test_ollama_failure_mid_stream_sends_error_event(client, monkeypatch):
    import httpx

    def broken_agent(model, messages):
        yield {"type": "thinking", "data": "Hmm"}
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(main, "run_agent", broken_agent)

    r = chat(client, new_thread(client), "Hello")

    events = [json.loads(line) for line in r.text.splitlines()]
    assert events[0] == {"type": "thinking", "data": "Hmm"}
    assert events[-1]["type"] == "error"
    assert "Connection refused" in events[-1]["data"]
    assert r.text.endswith("\n")


def test_failed_turn_is_not_saved(client, monkeypatch):
    import httpx

    def broken_agent(model, messages):
        raise httpx.ConnectError("Connection refused")
        yield  # makes this a generator, like the real run_agent

    monkeypatch.setattr(main, "run_agent", broken_agent)
    thread_id = new_thread(client)

    chat(client, thread_id, "Hello")

    assert client.get(f"/threads/{thread_id}/messages").json() == []


# --- models ---


def test_models_lists_what_ollama_has(client, monkeypatch):
    monkeypatch.setattr(main, "list_models", lambda: ["gemma4:12b-mlx", "qwen3:8b"])

    r = client.get("/models")

    assert r.status_code == 200
    assert r.json() == ["gemma4:12b-mlx", "qwen3:8b"]


def test_models_is_503_when_ollama_is_down(client, monkeypatch):
    import httpx

    def down():
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(main, "list_models", down)

    assert client.get("/models").status_code == 503


# --- renaming ---


def test_rename_thread(client):
    thread_id = new_thread(client)

    r = client.patch(f"/threads/{thread_id}", json={"title": "Maths homework"})

    assert r.status_code == 200
    [thread] = client.get("/threads").json()
    assert thread["title"] == "Maths homework"


def test_rename_unknown_thread_is_404(client):
    r = client.patch("/threads/nonsense", json={"title": "Nope"})
    assert r.status_code == 404


def test_rename_requires_title(client):
    r = client.patch(f"/threads/{new_thread(client)}", json={})
    assert r.status_code == 422


# --- auto-titling ---


@pytest.fixture
def titler(monkeypatch):
    """Replace generate_title, recording what it was asked to title."""
    calls = []

    def fake_generate_title(model, message):
        calls.append(message)
        return "Greeting"

    monkeypatch.setattr(main, "generate_title", fake_generate_title)
    return calls


def test_first_turn_gets_a_title(client, agent, titler):
    thread_id = new_thread(client)

    chat(client, thread_id, "Hello")

    assert titler == ["Hello"]  # titled from the user's message
    [thread] = client.get("/threads").json()
    assert thread["title"] == "Greeting"


def test_title_event_is_the_last_line(client, agent, titler):
    r = chat(client, new_thread(client), "Hello")

    assert r.text.endswith("\n")
    events = [json.loads(line) for line in r.text.splitlines()]
    assert events[-1] == {"type": "title", "data": "Greeting"}


def test_later_turns_are_not_retitled(client, agent, titler):
    thread_id = new_thread(client)

    chat(client, thread_id, "Hello")
    r = chat(client, thread_id, "Again")

    assert titler == ["Hello"]  # only asked once
    assert all(json.loads(line)["type"] != "title" for line in r.text.splitlines())


def test_titling_failure_is_quiet(client, agent, monkeypatch):
    import httpx

    def broken(model, message):
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(main, "generate_title", broken)
    thread_id = new_thread(client)

    r = chat(client, thread_id, "Hello")

    events = [json.loads(line) for line in r.text.splitlines()]
    assert all(e["type"] not in ("title", "error") for e in events)
    assert (
        len(client.get(f"/threads/{thread_id}/messages").json()) == 2
    )  # turn still saved
    [thread] = client.get("/threads").json()
    assert thread["title"] == ""


def test_empty_title_is_not_saved(client, agent, monkeypatch):
    monkeypatch.setattr(main, "generate_title", lambda model, message: "")
    thread_id = new_thread(client)

    r = chat(client, thread_id, "Hello")

    assert all(json.loads(line)["type"] != "title" for line in r.text.splitlines())
