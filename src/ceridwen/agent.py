from collections.abc import Iterator

from ceridwen.ollama_client import stream_chat
from ceridwen.tools import execute_tool

MAX_TURNS = 5


def run_agent(model: str, messages: list[dict]) -> Iterator[dict]:
    for _ in range(MAX_TURNS):                                   # one pass = one model call
        # fresh "notepads" for THIS model call
        # (what text did it say? what tools did it ask for?)
        thinking = ""
        content = ""
        tool_calls = []

        for event in stream_chat(model, messages):
            yield event                           # pass it straight on: the app keeps streaming
            # then peek at the event's type and note down anything you need
            match event["type"]:
                case "thinking":
                    thinking += event["data"]
                case "content":
                    content += event["data"]
                case "tool_call":
                    tool_calls.append(event["data"])
                case "done":
                    pass

        # the model call has finished. Did it ask for any tools?
        # no  -> return (the whole answer is done)
        # yes -> carry on below

        if not tool_calls:
            return

        # 1. append the assistant's message (its text + tool calls) to messages

        messages.append(
            {
                "role": "assistant",
                "content": content,
                "tool_calls": [
                    {
                        "id": call["id"],
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"]
                        }
                    }
                    for call in tool_calls
                ]
            }
        )

        # 2. for each tool call: run it, append a {"role": "tool", ...} message

        for call in tool_calls:
            try:
                result = execute_tool(call["name"], call["arguments"])
                success = True
            except Exception as e:
                result = f'Error running {call["name"]}: {e!r}'
                print(result)
                success = False

            result = str(result)

            messages.append(
                {
                    "role": "tool",
                    "tool_name": call["name"],
                    "content": result
                }
            )

            yield {
                "type": "tool_result",
                "data": {
                    "id": call["id"],
                    "name": call["name"],
                    "result": result,
                    "success": success
                }
            }
        # loop back round: the model gets called again with the longer list

    yield {
        "type": "error",
        "data": "model exceeded 5 tool calls"
    }