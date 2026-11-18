from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna")

question = "What is the date of next Friday?"
print(f"> {question}\n")
result = agent.run_sync(question)
print(result.output)
