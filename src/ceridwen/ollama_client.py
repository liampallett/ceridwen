import httpx


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