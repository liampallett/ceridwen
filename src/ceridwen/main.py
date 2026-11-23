from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from ceridwen.ollama_client import stream_chat

"""
Run with: uv run uvicorn ceridwen.main:app --reload
"""


app = FastAPI()


class ChatRequest(BaseModel):
    model: str
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat/stream")
def streaming_endpoint(request: ChatRequest):
    messages = [{"role": "user", "content": request.message}]
    lines = (f"{json.dumps(event)}\n" for event in stream_chat(request.model, messages))
    return StreamingResponse(
        lines,
        media_type="application/x-ndjson"
    )