import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from ceridwen.main import app

client = TestClient(app)

MODEL = "gemma4:12b-mlx"

EVENTS = [
    {"type": "thinking", "data": "Line one\nline two"},
    {"type": "content", "data": "Hello"},
    {"type": "tool_call", "data": {"id": None, "name": "current_time", "arguments": {}}},
    {"type": "done", "data": {"done_reason": "stop", "eval_count": 3}},
]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_streaming_endpoint_sends_ndjson():
    with patch("ceridwen.main.stream_chat") as mock_stream:
        mock_stream.return_value = iter(EVENTS)

        r = client.post("/chat/stream", json={"model": MODEL, "message": "Hello"})

        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/x-ndjson")
        mock_stream.assert_called_once_with(MODEL, "Hello")


def test_streaming_endpoint_one_valid_json_object_per_line():
    with patch("ceridwen.main.stream_chat") as mock_stream:
        mock_stream.return_value = iter(EVENTS)

        r = client.post("/chat/stream", json={"model": MODEL, "message": "Hello"})

        # Every event ends with exactly one newline; newlines inside the
        # data (the thinking event) must be escaped, not split across lines.
        assert r.text.endswith("\n")
        lines = r.text.splitlines()
        assert [json.loads(line) for line in lines] == EVENTS


def test_streaming_endpoint_rejects_missing_fields():
    r = client.post("/chat/stream", json={"model": MODEL})
    assert r.status_code == 422
