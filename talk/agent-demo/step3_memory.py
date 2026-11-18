from datetime import date

from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna", instructions="You plan meetings. Answer in one sentence.")


@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."


question = "My name is Sam, and I need a room for six people next Friday."
print(f"> {question}\n")
first = agent.run_sync(question)
print(first.output)

question = "What was my name, and for how many people?"
print(f"\n> {question}\n")
second = agent.run_sync(question, message_history=first.all_messages())
print(second.output)
