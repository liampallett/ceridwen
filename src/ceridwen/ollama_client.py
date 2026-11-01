import httpx
import json
from collections.abc import Iterator


def chat(model: str, message: str) -> str:
    response = httpx.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": message
                }
            ],
            "stream": False
        },
        timeout=120
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def stream_chat(model: str, message: str) -> Iterator[str]:
    with httpx.stream(
        "POST",
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "messages": [
                {"role": "user", "content": message}
            ],
            "stream": True
        },
        timeout=120
    ) as response:
        response.raise_for_status()

        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            content = data["message"]["content"]
            if content:
                yield content