"""ReAct loop — Anthropic tool-use implementation.

Drives one full conversation turn:
  user message → LLM → tool calls → LLM → ... → text response
"""

import anthropic

from tools import ALL_TOOL_DEFS, execute_tool, memory_read


async def run_turn(
    client: anthropic.AsyncAnthropic,
    model: str,
    system_prompt: str,
    tool_names: list[str],
    history: list[dict],
    user_message: str,
) -> tuple[str, list[dict]]:
    """Run one user turn. Returns (assistant_text, updated_history)."""

    # Inject memory into system prompt if tool is enabled
    system = system_prompt
    if "memory" in tool_names or "memory_read" in tool_names:
        memories = memory_read()
        if memories and memories != "(no memories yet)":
            system = f"{system_prompt}\n\nYour memories from past conversations:\n{memories}"

    active_tools = [ALL_TOOL_DEFS[t] for t in tool_names if t in ALL_TOOL_DEFS]

    messages = history + [{"role": "user", "content": user_message}]

    MAX_ITERATIONS = 8
    for _ in range(MAX_ITERATIONS):
        kwargs: dict = dict(
            model=model,
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        if active_tools:
            kwargs["tools"] = active_tools

        response = await client.messages.create(**kwargs)

        # Collect text from content blocks
        text_parts = [b.text for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn" or not active_tools:
            reply = " ".join(text_parts).strip()
            messages.append({"role": "assistant", "content": response.content})
            return reply, messages

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            # Execute all tool calls in this response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Unexpected stop reason — return whatever text we have
            reply = " ".join(text_parts).strip() or "(no response)"
            messages.append({"role": "assistant", "content": response.content})
            return reply, messages

    return "(max iterations reached)", messages
