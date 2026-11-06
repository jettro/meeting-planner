from datetime import date

from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna", instructions="You plan meetings. Answer in one sentence.")


@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."


result = agent.run_sync("What is the date of next Friday?")
print(result.output)
