from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna")

result = agent.run_sync("What is the date of next Friday?")
print(result.output)
