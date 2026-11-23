"""FastAPI app: thread management endpoints and the streaming chat endpoint.

Run with: uv run uvicorn ceridwen.main:app --reload
"""

import json
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ceridwen import db
from ceridwen.agent import run_agent
from ceridwen.ollama_client import generate_title, list_models

DB_PATH = Path(__file__).parent / "database" / "ceridwen.db"


@asynccontextmanager
async def lifespan(_fast_api_app: FastAPI):
    """Create the database tables when the server starts."""
    db.init_db(DB_PATH)
    yield


app = FastAPI(lifespan=lifespan)


class ChatRequest(BaseModel):
    """Body of a ``POST /chat`` request."""

    model: str
    message: str
    thread_id: str


class ThreadPatch(BaseModel):
    """Body of a ``PATCH /threads/{thread_id}`` request."""

    title: str


@app.post("/chat")
def chat(request: ChatRequest):
    """Send a message to a thread and stream the agent's reply as NDJSON.

    The thread's history is loaded, the new message appended, and the agent's
    events streamed back one JSON object per line. Once the stream ends, the
    new message and everything the agent added are saved to the thread.

    Raises:
        HTTPException: 404 if the thread doesn't exist.
    """
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
    """Stream the agent's events as NDJSON lines, then save the turn.

    Saving happens after the last event, so if the client disconnects
    mid-stream, nothing from this turn is saved. If Ollama fails partway
    through, an ``error`` event is sent instead and nothing is saved, so the
    thread is left as it was and the message can simply be sent again.

    After a thread's first turn, the model is asked for a title, which is
    saved and sent as a final ``title`` event. Titling failures are ignored:
    the thread just stays untitled.

    Args:
        model: Name of the Ollama model to use.
        messages: The thread's history plus the new user message.
        thread_id: Thread to save the new messages to.
        start: Index in ``messages`` where this turn's messages begin.

    Yields:
        One JSON-encoded event per line.
    """
    try:
        for event in run_agent(model, messages):
            yield f"{json.dumps(event)}\n"
    except httpx.HTTPError as e:
        yield f"{json.dumps({'type': 'error', 'data': str(e)})}\n"
        return
    db.add_messages(DB_PATH, thread_id, messages[start:])
    if start == 0:
        title = ""

        try:
            title = generate_title(model, messages[start]["content"])
        except httpx.HTTPError:
            pass

        if title:
            db.rename_thread(DB_PATH, thread_id, title)
            yield f"{json.dumps({'type': 'title', 'data': title})}\n"


@app.get("/models")
def get_models():
    """List the models installed in Ollama. 503 if Ollama can't be reached."""
    try:
        return list_models()
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503, detail="ollama service unavailable"
        ) from None


@app.post("/threads")
def add_thread():
    """Create a thread and return its ID."""
    thread_id = db.create_thread(DB_PATH)
    return {"id": thread_id}


@app.get("/threads")
def get_threads():
    """List all threads, most recently updated first."""
    return db.list_threads(DB_PATH)


@app.get("/threads/{thread_id}/messages")
def get_messages_from_thread(thread_id: str):
    """Return a thread's messages, oldest first. 404 if it doesn't exist."""
    if not db.thread_exists(DB_PATH, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return db.get_messages(DB_PATH, thread_id)


@app.delete("/threads/{thread_id}")
def delete_thread(thread_id: str):
    """Delete a thread and its messages. 404 if it doesn't exist."""
    if not db.thread_exists(DB_PATH, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    db.delete_thread(DB_PATH, thread_id)


@app.patch("/threads/{thread_id}")
def rename_thread(thread_id: str, thread_patch: ThreadPatch):
    """Rename a thread. 404 if it doesn't exist."""
    if not db.thread_exists(DB_PATH, thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    db.rename_thread(DB_PATH, thread_id, thread_patch.title)
