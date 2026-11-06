from datetime import date

from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna", instructions="You plan meetings. Answer in one sentence.")


@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."


@agent.tool_plain
def free_rooms(day: date, people: int) -> list[str]:
    """The meeting rooms that are free on a day, for a number of people."""
    print(f"  > tool: free_rooms({day}, {people})")
    return ["Attic (8)", "Greenhouse (6)"] if people <= 6 else ["Attic (8)"]


first = agent.run_sync("My name is Sam, and I need a room for six people next Friday.")
second = agent.run_sync("Which rooms are free?", message_history=first.all_messages())
print(second.output)
