import os
from datetime import date

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset

from calls import show_calls

agent = Agent(
    "openai:gpt-6-luna",
    instructions=(
        "You plan meetings: find a time, book a room, order lunch. "
        "Nobody can answer questions: decide for yourself and finish the whole job."
    ),
    toolsets=[
        MCPToolset(os.environ["MEETING_MCP_URL"], auth=os.environ["MEETING_MCP_API_KEY"]),
        MCPToolset(os.environ["LOCATION_MCP_URL"], auth=os.environ["LOCATION_MCP_API_KEY"]),
        MCPToolset(os.environ["NOMNOM_MCP_URL"], auth=os.environ["NOMNOM_MCP_API_KEY"]),
    ],
)


@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."


request = "A design review with Sanne and Daan on Tuesday, somewhere quiet. And lunch."
print(f"> {request}\n")

result = agent.run_sync(request, event_stream_handler=show_calls)
print(result.output)
