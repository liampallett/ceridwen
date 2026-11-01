import httpx
import pytest

from ceridwen.ollama_client import chat
from unittest.mock import patch

def test_chat_returns_content():
    with patch("ceridwen.ollama_client.httpx.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "message": {
                "role": "assistant",
                "content": "Hello from Ollama!"
            }
        }

        r = chat("gemma4:12b-mlx", "Hello")

        assert r == "Hello from Ollama!"
        mock_post.assert_called_once_with(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "gemma4:12b-mlx",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello"
                    }
                ],
                "stream": False
            },
            timeout=120
        )

def test_chat_connection_error():
    with patch("ceridwen.ollama_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            chat("gemma4:12b-mlx", "Hello")