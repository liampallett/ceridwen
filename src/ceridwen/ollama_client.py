import httpx
import json
from collections.abc import Iterator
from ceridwen.tools import build_tools


def stream_chat(model: str, message: str) -> Iterator[dict]:
    with httpx.stream(
        "POST",
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": model,
            "tools": build_tools(),
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
                    yield {"type": "tool_call", "data": {
                        "id": call_id,
                        "name": name,
                        "arguments": arguments
                    }}
            if done:
                metrics = {key: chunk[key] for key in ("done_reason", "total_duration", "eval_count", "prompt_eval_count")}
                yield {"type": "done", "data": metrics}