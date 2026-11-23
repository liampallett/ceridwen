# Ceridwen

Ceridwen is a local assistant built with Python, with a native Swift app planned. Bring your own model and keep conversation state on your computer. Its name comes from the Welsh goddess of inspiration and knowledge.

> **Status:** early rebuild (v2). The backend streams responses from a local model and can call tools in a loop. Conversation history, memory, skills and the SwiftUI app are planned but not built yet.

---

# What the Project Is

Ceridwen is a personal AI assistant that runs against a local model through [Ollama](https://ollama.com), so nothing leaves the machine. It's built for one user (me) and the things I actually use an assistant for: writing emails, summarising YouTube videos, getting maths explained while doing homework, and talking through LeetCode problems.

v2 is a ground-up rebuild. The first version was a LangChain terminal app that grew from 8 files to over 20 through features I never really needed, including image generation. v2 starts small and only adds a feature when I find I'm missing it. The goal is a codebase I understand line by line, with a FastAPI backend and, eventually, a native macOS app on top.

---

# How It Works

The backend has four small modules, each with one job:

| Module | Job |
| --- | --- |
| `main.py` | HTTP. Receives a message, streams events back as NDJSON. |
| `agent.py` | The agent loop. Calls the model, runs any tools it asks for, calls it again until it answers. |
| `ollama_client.py` | Talks to Ollama. Turns Ollama's raw stream into Ceridwen's own events. |
| `tools.py` | The tool registry. Describes tools to the model and validates its arguments before running them. |

A request flows like this:

1. `POST /chat/stream` receives `{"model": ..., "message": ...}`.
2. The agent sends the conversation to Ollama, with the system prompt (`prompts/system.md`, re-read on every request) placed in front.
3. As the model streams, every event is passed straight through to the client.
4. If the model asked for a tool, the agent runs it, adds the call and its result to the conversation, and calls the model again. This repeats until the model answers in plain text, or stops after `MAX_TURNS` model calls.

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

**The system prompt is added on every call, never stored in the conversation.** When threads are saved, they'll hold only the real conversation, so editing the prompt changes every thread's behaviour, not just new ones.

**Strict argument validation.** Each tool declares a Pydantic model with `extra="forbid"` and strict types. That same model generates the JSON Schema the LLM sees, so the description and the validation can't drift apart. Small models do invent arguments, so this matters.

---

# Tech Stack

- Languages used:
- Frameworks/libraries:
- Tools and platforms:

---

# What I Learned

- What new skills did I gain?
- What concepts became clearer through building this?
- What surprised me during development?

---

# How to Run the Project

**Prerequisites**

- Python 3.14 and [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com) running locally, with a model that supports tool calling

**Install**

```bash
git clone https://github.com/liampallett/ceridwen
cd ceridwen-v2
uv sync
ollama pull gemma4:12b-mlx   # or any tool-capable model
```

**Run the backend**

```bash
uv run uvicorn ceridwen.main:app --reload
```

**Send a message**

```bash
curl -N http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"model": "gemma4:12b-mlx", "message": "What time is it?"}'
```

**Run the tests and linter**

```bash
uv run pytest
uv run ruff check .
```

---

# Project Structure

# Future Improvements

- What features would I add next?
- What parts could be improved or refactored?
- What ideas did I not have time to implement?

---

## GenAI Disclosure

The GenAI tool Claude Opus 5.5 was used during the development of this project for assistance and bug finding. No code
was written by the LLM.