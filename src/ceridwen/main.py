from fastapi import FastAPI
from pydantic import BaseModel

from ceridwen.ollama_client import chat

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