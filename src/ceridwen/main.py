from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

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
    return StreamingResponse(
        stream_chat(request.model, request.message),
        media_type="text/plain"
    )