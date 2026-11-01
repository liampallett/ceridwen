from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ceridwen.ollama_client import chat, stream_chat

app = FastAPI()


class ChatRequest(BaseModel):
    model: str
    message: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    r = chat(request.model, request.message)
    return {"response": r}


@app.post("/chat/stream")
def streaming_endpoint(request: ChatRequest):
    return StreamingResponse(
        stream_chat(request.model, request.message),
        media_type="text/plain"
    )