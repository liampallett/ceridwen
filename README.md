# Ceridwen

Ceridwen is a local assistant built with Python, with a native Swift app planned. Bring your own model and keep conversation state on your computer. Its name comes from the Welsh goddess of inspiration and knowledge.

> **Status:** early rebuild (v2). The backend streams responses from a local model, calls tools in a loop, and saves conversations as threads in SQLite. Ghost mode, memory, skills and the SwiftUI app are planned but not built yet.

---

# What the Project Is

Ceridwen is a personal AI assistant that runs against a local model through [Ollama](https://ollama.com), so nothing leaves the machine. It's built for one user (me) and the things I actually use an assistant for: writing emails, summarising YouTube videos, getting maths explained while doing homework, and talking through LeetCode problems.

v2 is a ground-up rebuild. The first version was a LangChain terminal app that grew from 8 files to over 20 through features I never really needed, including image generation. v2 starts small and only adds a feature when I find I'm missing it. The goal is a codebase I understand line by line, with a FastAPI backend and, eventually, a native macOS app on top.

---

# How It Works

The backend has five small modules, each with one job:

| Module | Job |
| --- | --- |
| `main.py` | HTTP. Thread endpoints, and the chat endpoint that streams events back as NDJSON. |
| `agent.py` | The agent loop. Calls the model, runs any tools it asks for, calls it again until it answers. |
| `ollama_client.py` | Talks to Ollama. Turns Ollama's raw stream into Ceridwen's own events. |
| `tools.py` | The tool registry. Describes tools to the model and validates its arguments before running them. |
| `db.py` | SQLite storage for threads and their messages. |

A chat request flows like this:

1. `POST /chat` receives `{"model": ..., "message": ..., "thread_id": ...}`.
2. The thread's history is loaded from SQLite and the new message is appended.
3. The agent sends the conversation to Ollama, with the system prompt (`prompts/system.md`, re-read on every request) placed in front.
4. As the model streams, every event is passed straight through to the client.
5. If the model asked for a tool, the agent runs it, adds the call and its result to the conversation, and calls the model again. This repeats until the model answers in plain text, or stops after `MAX_TURNS` model calls.
6. Once the stream ends, everything new this turn (the user's message, any tool calls and results, and the reply) is saved to the thread.

The API:

| Endpoint | Does |
| --- | --- |
| `POST /threads` | Create a thread, returns `{"id": ...}` |
| `GET /threads` | List threads, most recently active first |
| `GET /threads/{id}/messages` | A thread's messages, oldest first |
| `DELETE /threads/{id}` | Delete a thread and its messages |
| `POST /chat` | Send a message to a thread, streams events back |

Every line of the response is one JSON event:

| Type | Data |
| --- | --- |
| `thinking` | A chunk of the model's reasoning |
| `content` | A chunk of the answer |
| `tool_call` | `{id, name, arguments}` |
| `tool_result` | `{id, name, result, success}` |
| `done` | Metrics for one model call (`done_reason`, `total_duration` in ns, token counts) |
| `error` | Something went wrong mid-stream |

---

# Engineering Decisions

**Python backend + SwiftUI frontend, rather than all-Swift.** A Swift app could talk to Ollama directly with no second process. I chose the split because the tools I want (YouTube transcripts, PDF reading, web scraping) are much better served in Python, it's the language I'm fluent in, and it keeps the Swift side mostly UI. The trade-off is process management: something has to start and supervise the backend.

**Raw HTTP to Ollama, rather than the `ollama` package or LangChain.** v1 hid everything behind LangChain and LangGraph, which made it hard to understand. Calling Ollama's API directly with `httpx` keeps the protocol visible. The cost is writing the JSON handling myself, but it's all contained in `ollama_client.py`, so swapping to a library later would be a one-module change.

**Ceridwen's own event format, rather than passing Ollama's chunks through.** Ollama's tool calls are nested and carry fields nothing else needs. Flattening them into small typed events keeps Ollama's format inside one module, and the same events are what the Swift app will decode (a `type` plus a payload maps naturally onto a Swift enum). The cost is converting tool calls back into Ollama's shape when they go into the conversation history.

**NDJSON, rather than plain text.** Once tool calls and thinking were streaming alongside the answer, plain text couldn't tell them apart. One JSON object per line is simple to produce and to parse incrementally. Errors after a stream has started can only travel as events, because the `200 OK` has already been sent.

**Streaming only.** There's no non-streaming endpoint. I always want responses to appear as they're generated, and keeping two code paths for the same thing is how v1 bloated.

**Tool failures go back to the model, not up the stack.** Any exception from a tool is caught and returned as the tool's result, so the model can see what went wrong and either retry or tell the user. This is a deliberately broad catch at an untrusted boundary. The error is also logged, and the `tool_result` event is marked `success: false` so the app can show it.

**The backend owns conversation history.** The client sends only the new message and a thread ID, and the backend loads the rest from SQLite. Tool calls and results live in the backend's loop anyway, so keeping history there keeps the app a thin display, and any future client gets the same behaviour for free.

**Plain `sqlite3`, rather than an ORM.** Two tables don't need SQLAlchemy, and writing the SQL by hand keeps it visible, in the same spirit as calling Ollama directly. Messages are stored one row per turn (not one per streamed event), in the same shape the agent uses, so a loaded thread can go straight back to the model. Tool calls are stored as JSON text, since SQLite has no JSON type.

**The system prompt is added on every call, never stored in the conversation.** Saved threads hold only the real conversation, so editing the prompt changes every thread's behaviour, not just new ones.

**Strict argument validation.** Each tool declares a Pydantic model with `extra="forbid"` and strict types. That same model generates the JSON Schema the LLM sees, so the description and the validation can't drift apart. Small models do invent arguments, so this matters.

---

# Tech Stack

- **Languages:** Python 3.14 (Swift planned)
- **Frameworks/libraries:** FastAPI, Uvicorn, httpx, Pydantic, SQLite (`sqlite3`)
- **Tools and platforms:** Ollama (developed against `gemma4:12b-mlx`), uv, pytest, ruff

---

# What I Learned

- **An LLM has no memory.** "Continuing a conversation" means resending the whole history every time. Once that clicked, it was obvious why history storage belongs in the backend, and why a thread is really just a list of messages.
- **Generators are lazy.** Nothing inside a generator runs, errors included, until something iterates it. That shaped the agent loop (a generator wrapped around another generator), how its tests are written, and why saving a turn has to happen *after* the stream's last `yield`.
- **What tool calling actually looks like on the wire.** Not a magic function call: the model emits a structured request, my code runs the tool, and the result goes back as another message. Streaming means rebuilding the assistant's message from pieces as they arrive.
- **Once a streamed response starts, errors become data.** The `200 OK` has already been sent, so a failure partway through can only be reported as an event in the stream.
- **Small models are confidently wrong about tools.** Gemma happily called an `add` tool that didn't exist, with arguments it made up. Validating everything the model sends isn't paranoia.
- **Bugs hide until something depends on the data.** The agent never added its final reply to the conversation, and nothing noticed until threads started saving it.

---

# How to Run the Project

**Prerequisites**

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally, with a model that supports tool calling

**Install**

```bash
git clone https://github.com/liampallett/ceridwen
cd ceridwen
uv sync
ollama pull gemma4:12b-mlx   # or any tool-capable model
```

**Run the backend**

```bash
uv run uvicorn ceridwen.main:app --reload
```

**Start a thread and send a message**

```bash
curl -X POST http://127.0.0.1:8000/threads
# -> {"id": "<thread-id>"}

curl -N http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma4:12b-mlx", "message": "What time is it?", "thread_id": "<thread-id>"}'
```

The database is created automatically at `src/ceridwen/database/ceridwen.db` on first run.

**Run the tests and linter**

```bash
uv run pytest
uv run ruff check .
```

---

# Project Structure

```
src/ceridwen/
├── main.py            # FastAPI app: thread endpoints and /chat
├── agent.py           # agent loop: model calls, tool execution, turn limit
├── ollama_client.py   # Ollama HTTP client and event translation
├── tools.py           # tool registry, schemas and validation
├── db.py              # SQLite storage for threads and messages
└── prompts/
    └── system.md      # system prompt, re-read on every request
tests/                 # one test file per module; Ollama is mocked, databases are temporary
```

# Future Improvements

- **SwiftUI app:** native macOS client with a thread sidebar, streamed thinking, tool activity and LaTeX rendering.
- **Ghost mode:** chats that are never written to the database.
- **Thread titles:** auto-generated from the first message, plus renaming.
- **Memory and skills:** stored in a central data folder rather than per-directory, which was v1's bug.
- **More tools:** YouTube transcripts and web search first.
- **Saving interrupted turns:** if the client disconnects mid-stream, nothing from that turn is saved yet.
- **Database location:** move it to `~/Library/Application Support/Ceridwen/` rather than inside the package.
- **Editing the system prompt from the app**, with any model-proposed changes shown as a diff for approval.
- **Smarter turn limit:** a final no-tools call so the model answers with what it has, rather than stopping with an error.
- **Time-to-first-token and tokens-per-second metrics.**

---

## GenAI Disclosure

Claude Opus 5.5 was used for guidance, code review and debugging. All application code in src/ was written by me. The
test suite and parts of this README were written by Claude and reviewed by me.
