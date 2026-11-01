from ceridwen.main import app
from fastapi.testclient import TestClient
from unittest.mock import patch


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_endpoint():
    with patch("ceridwen.main.chat") as mock_chat:
        mock_chat.return_value = "Hello from mocked Ollama!"

        response = client.post(
            "/chat",
            json={
                "model": "gemma4:12b-mlx",
                "message": "Hello"
            }
        )

        assert response.status_code == 200
        assert response.json() == {
            "response": "Hello from mocked Ollama!"
        }

        mock_chat.assert_called_once_with(
            "gemma4:12b-mlx",
            "Hello"
        )


def test_streaming_endpoint():
    with patch("ceridwen.main.stream_chat") as mock_stream:
        mock_stream.return_value = ["Hello", " ", "world!"]

        r = client.post(
            "/chat/stream",
            json={
                "model": "gemma4:12b-mlx",
                "message": "Hello"
            }
        )

        assert r.status_code == 200
        assert r.text == "Hello world!"

        mock_stream.assert_called_once_with(
            "gemma4:12b-mlx",
            "Hello"
        )