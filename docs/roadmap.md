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
- [ ] **Context saturation.** Tokens used come from `prompt_eval_count`; the
      model's context size needs Ollama's `/api/show`, so a small backend
      endpoint.
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

- [ ] More tools: emails, YouTube summaries, clipboard, web search/fetch
- [ ] Skills and memory
- [ ] Ghost mode (private threads that aren't saved)
- [ ] Edit the system prompt from the app (and maybe a skill that can)

## Known issues

- Switching threads mid-stream: the reply keeps writing into whichever thread
  is now selected.
- Text said alongside a tool call is glued onto the final reply with no gap.
- Tool success/failure isn't stored, so history can't show failed tools
  differently.
