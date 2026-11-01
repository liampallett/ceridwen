from unittest.mock import patch

import httpx
import pytest

from ceridwen.ollama_client import chat, stream_chat


def test_chat_connection_error():
    with patch("ceridwen.ollama_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            chat("gemma4:12b-mlx", "Hello")


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


def test_stream_chat_returns_chunks():
    with patch("ceridwen.ollama_client.httpx.stream") as mock_stream:
        mock_response = mock_stream.return_value.__enter__.return_value
        mock_response.iter_lines.return_value = [
            '{"message":{"content":"Hello"},"done":false}',
            '{"message":{"content":" world"},"done":false}',
            '{"message":{"content":""},"done":true}'
        ]

        r = stream_chat("gemma4:12b-mlx", "Hello")
        chunks = list(r)

        assert chunks == ["Hello", " world"]
        mock_stream.assert_called_once_with(
            "POST",
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "gemma4:12b-mlx",
                "messages": [
                    {
                        "role": "user",
                        "content": "Hello"
                    }
                ],
                "stream": True
            },
            timeout=120
        )