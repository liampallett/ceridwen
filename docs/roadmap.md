# Roadmap

Rough plan, not a promise. Order is **rename → finish → style**: get the core
features working before polishing how anything looks. Backend tools are a
separate track and can wait until the app is feature-complete.

## Done

- [x] Model picker under the composer
- [x] Today's date in the system prompt
- [x] Thinking saved with messages and shown from history
- [x] Activity block: thinking and tool calls (with results) grouped per turn,
      collapsible, identical live and from history

## 1. The Great Renaming

The app's vocabulary has got muddled (message, turn, step, reply, prompt...).
Write down one name per concept and what it means, then rename the code to
match, backend and app, so the two use the same words.

## 2. Finish (core functionality)

Roughly ordered by dependencies. Most of these need a small backend change as
well, noted where they do; do that alongside the feature rather than later.

- [ ] **Thread renaming and deletion.** App only, since `PATCH` and
      `DELETE /threads/{id}` already exist.
- [ ] **Analytics display.** The `done` event already streams token counts and
      timings; the app currently ignores it. Showing it live is app only.
      Keeping it in history needs a DB column. Add `"model"` to the done
      metrics so each reply can say which model answered.
- [ ] **Context saturation.** An always-visible indicator in the bottom bar
      (a big irk with the Claude app is that it has none). Tokens used come
      from `prompt_eval_count`; the model's context size needs Ollama's
      `/api/show`, so a small backend endpoint.
    - [ ] **Context window breakdown**, like Claude Code's: how much is system
          prompt vs tool definitions vs history vs the latest message. Ollama
          only reports one total, so per-part numbers would have to be
          estimated (e.g. measure each part separately, or approximate from
          character counts). Possible, but approximate.
- [ ] **Effort levels.** Ollama's `think` parameter takes levels on some
      models. Needs a field on `ChatRequest` passed through to `stream_chat`,
      plus a picker in the app.
- [ ] **Images and other files.** Ollama takes images as base64 on the
      message, so the backend must accept, store and forward them. For
      non-image files (PDFs etc.), first decide what attaching one should
      actually mean for a local model.
- [ ] **Voice messages.** Biggest item: needs speech-to-text (Apple's Speech
      framework on-device, or Whisper). A project in itself.
- [ ] _Probably a million other things. Add them here as they come up._

Before starting this list, decide which of these you'll actually use soon
versus which are nice-to-have.

## Models

- Planning to use **inkling-2-mini** (26B, 1M context window) more going
  forwards.
- Ollama doesn't use a model's full context by default: `ollama ps` showed
  inkling loaded at 262,144 tokens. Using the whole 1M means passing
  `num_ctx` in the request options, and a bigger context costs more memory,
  so it may be worth making this a setting rather than always maxing it out.

## Wireframing

Before styling, sketch the screens on the iPad.

- Keep it low-fidelity: boxes, labels, arrows. The point is layout and flow,
  not looks. Grey boxes stop you fussing over colours and fonts too early.
- **Freeform** (free, built into iPadOS) is the easiest start: infinite
  canvas, Pencil support, shapes and sticky notes, syncs to the Mac.
  Excalidraw in Safari is a good alternative with a hand-drawn look. Figma
  is overkill until you're doing the real visual design.
- Sketch one screen per state: empty thread, streaming reply, activity block
  expanded, model and effort pickers open, context indicator, attachments,
  thread rename/delete.
- Use a screenshot of the Claude app as the reference layer and draw over it.

## 3. Style

Make the app look like the Claude desktop app as closely as possible.

- [ ] Activity block in a rounded, bordered box, one row per step
- [ ] Computed summary label instead of "Activity" (e.g. "Thought · used
      current_time"); LLM-generated summary later via a generalised
      `summarise()` refactor of `generate_title`
- [ ] User messages as right-aligned bubbles; drop the User/Assistant captions
- [ ] More spacing between turns
- [ ] "Thinking" indicator while waiting for the first token
- [ ] Composer as one rounded box with the model picker inside it
- [ ] LaTeX rendering for maths

## Backend track (after the app is finished)

### Making it a proper agent

The agent loop already exists: the model picks an action, sees the result and
decides what to do next. What's missing is capability. Each layer builds on
the one before:

1. **Tools that act on your stuff**, not just talk: draft an email into the
   mail app, grab a YouTube transcript, read the clipboard.
2. **Multi-step work.** Give it a goal ("summarise this video and email the
   notes to my group") and it chains the tools itself. Needs a higher or
   adjustable `MAX_TURNS`.
3. **Checking its own work.** After acting, it verifies: reads the file back,
   runs the code it wrote.
4. **Memory** across threads, so it isn't starting from zero each time.
5. **Initiative.** Runs on a schedule or reacts to events (e.g. a morning
   summary) without being asked. Optional, and a big step.

Layers 1 and 2 are the biggest jump. Start with a couple of action tools that
match how Ceridwen is actually used, plus approval prompts.

- [ ] **Tool approval prompts.** Once tools can change things (files, shell,
      emails), the backend pauses and the app shows Allow/Deny before the
      tool runs. Needs a new event type. Required before any tool that can't
      be undone.
- [ ] Raise or make adjustable `MAX_TURNS`
- [ ] Skills and memory
- [ ] Ghost mode (private threads that aren't saved)
- [ ] Edit the system prompt from the app (and maybe a skill that can)

### Tools

What local setups commonly have, roughly in order of usefulness here:

- **Web:** search and page fetch. Matters most, since local models' knowledge
  stops at their training date.
- **Media:** YouTube transcripts, PDF reading, images for models that can see.
- **Your Mac:** clipboard, calendar, reminders, notes, opening apps.
- **Code:** run Python in a sandbox, for maths and data (homework).
- **Files:** read, write and search within a folder you've granted.
- **Shell:** run terminal commands. Powerful, so it most needs approval.
- **Memory:** save and recall facts about you.

Start with: **web search, YouTube transcripts, clipboard**. Then emails.

Most local setups plug tools in through **MCP** (Model Context Protocol), a
standard for ready-made tool servers, rather than writing every tool by
hand. Worth looking at before building each tool from scratch.

## Known issues

- Switching threads mid-stream: the reply keeps writing into whichever thread
  is now selected.
- Text said alongside a tool call is glued onto the final reply with no gap.
- Tool success/failure isn't stored, so history can't show failed tools
  differently.
