# The demo's steps, typed on stage (talk/design_agent_demo.md Q2).
.DEFAULT_GOAL := help
.PHONY: help run-llm run-system run-memory run-tool

help: ## Show the steps
	@awk 'BEGIN {FS = ":.*##"} /^[a-z-]+:.*##/ {printf "  make %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run-llm: ## 1. just call an LLM
	@uv run --frozen step1_llm.py

run-system: ## 2. give it context: today's date
	@uv run --frozen step2_system.py

run-memory: ## 3. simulate memory: send the conversation along
	@uv run --frozen step3_memory.py

run-tool: ## 4. give it a tool
	@uv run --frozen step4_tool.py
