import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ceridwen import db
from ceridwen.agent import run_agent

"""
Run with: uv run uvicorn ceridwen.main:app --reload
"""

DB_PATH = Path(__file__).parent / "database" / "ceridwen.db"


@asynccontextmanager
async def lifespan(_fast_api_app: FastAPI):
    db.init_db(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    model: str
    message: str
    thread_id: str


@app.post("/chat")
def chat(request: ChatRequest):
    if not db.thread_exists(DB_PATH, request.thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")

    messages = db.get_messages(DB_PATH, request.thread_id)
    start = len(messages)
    messages.append({"role": "user", "content": request.message})

    return StreamingResponse(
        _stream_turn(request.model, messages, request.thread_id, start),
        media_type="application/x-ndjson",
    )


def _stream_turn(
    model: str, messages: list[dict], thread_id: str, start: int
) -> Iterator[str]:
    for event in run_agent(model, messages):
        yield f"{json.dumps(event)}\n"
    db.add_messages(DB_PATH, thread_id, messages[start:])


@app.post("/threads")
def add_thread():
    thread_id = db.create_thread(DB_PATH)
    return {"id": thread_id}


@app.get("/threads")
def get_threads():
    return db.list_threads(DB_PATH)


@app.get("/threads/{thread_id}/messages")
def get_messages_from_thread(thread_id: str):
    if not db.thread_exists(DB_PATH, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return db.get_messages(DB_PATH, thread_id)


@app.delete("/threads/{thread_id}")
def delete_thread(thread_id: str):
    if not db.thread_exists(DB_PATH, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete_thread(DB_PATH, thread_id)
