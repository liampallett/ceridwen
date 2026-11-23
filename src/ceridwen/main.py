import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ceridwen.agent import run_agent

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
    lines = (f"{json.dumps(event)}\n" for event in run_agent(request.model, messages))
    return StreamingResponse(lines, media_type="application/x-ndjson")
