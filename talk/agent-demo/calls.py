"""Prints every tool call as the agent makes it, so the room can watch the loop."""

from collections.abc import AsyncIterable
from typing import Any

from pydantic_ai.messages import AgentStreamEvent, FunctionToolCallEvent


async def show_calls(ctx: Any, events: AsyncIterable[AgentStreamEvent]) -> None:
    async for event in events:
        if isinstance(event, FunctionToolCallEvent):
            args = event.part.args_as_json_str()
            print(f"  > {event.part.tool_name}({args[:90]}{'…' if len(args) > 90 else ''})")
