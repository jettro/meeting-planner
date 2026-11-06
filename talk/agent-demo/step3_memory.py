from datetime import date

from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna", instructions="You plan meetings. Answer in one sentence.")


@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."


first = agent.run_sync("My name is Sam, and I need a room for six people next Friday.")
print(first.output)

second = agent.run_sync(
    "What was my name, and for how many people?",
    message_history=first.all_messages(),
)
print(second.output)
