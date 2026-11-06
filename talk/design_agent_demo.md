# Design: a first agent in code, run from the slides

> **Status:** built, 2026-11-06 - slides 10-14, `talk/agent-demo/`, `make agent-demo`. All four
> steps were run in the container and typed in the terminal page.
> The story is in [`plan.md`](plan.md), the slide engine in [`design_slides.md`](design_slides.md).

## The idea

After the definition (slide 4) and the anatomy of an agent (slides 5-10), the audience has seen an
agent as a picture. The next slides show the same thing as code: a very small pydantic-ai agent
that grows in three steps, and each step is run live in a terminal that sits on the slide.

| Step | What is added | What the audience sees | The anatomy slide it echoes |
|---|---|---|---|
| 1 | just call an LLM | `Agent("openai:gpt-6-luna")` and one `run_sync` - it answers, but has no idea what day it is | the LLM |
| 2 | context in the instructions | an `@agent.instructions` function returns today's date - the same question now gets the right answer | context |
| 3 | memory, simulated | the second run gets `message_history=` the first run's messages - it remembers your name | memory (sets up the memory slide, plan T3) |
| 4 *(optional)* | one tool | `@agent.tool_plain` - closes "tools in a loop to achieve a goal" from slide 4 | tools |

Checked against the installed version (pydantic-ai-slim 2.61.0, in the project's `.venv` through
akgentic): `Agent.instructions`, `Agent.tool_plain` and `run_sync(..., message_history=...)`
exist, and `openai:gpt-6-luna` is in `KnownModelName`.

## Decisions

| Id | Decision | Why |
|---|---|---|
| A1 | **Provider OpenAI, model `openai:gpt-6-luna`**; the key is `OPENAI_API_KEY` from the project's `.env` | decided 2026-11-06. A small model is fast enough to wait for on stage; the key is already there for the sample |
| A2 | **Its own mini project in `talk/agent-demo/`**: a `pyproject.toml` with only `pydantic-ai-slim[openai]` (pinned to 2.61.0, the version the sample uses), a `uv.lock`, and one file per step: `step1.py`, `step2.py`, `step3.py` | the sample must not get pydantic-ai as a dependency for the talk's sake, and a ten-line file reads better on a slide than one inside the sample. One file per step, so each `uv run stepN.py` stands on its own |
| A3 | **The code on the slides matches the files that run** | how is open, see Q3; a copy on a slide drifts from what runs |
| A4 | **A terminal in the browser with [ttyd](https://github.com/tsl0922/ttyd)** | a real shell is more honest for an audience of developers than a "run" button; ttyd serves one over a web page in a single binary |
| A5 | **ttyd runs in a Docker container**: `uv`, Python 3.12, the mini project with `uv sync` done at build time, ttyd on `localhost:8600` | everything is downloaded before the talk, nothing on the venue wifi except the call to OpenAI; and it is apart from the laptop's own shell and files. Docker 29.8 is installed |
| A6 | **The key goes in at start-up** with `docker run --env-file .env`, never in the image or the repo | the image can be rebuilt and shared safely; only `OPENAI_API_KEY` is used |
| A7 | **A `make agent-demo` target** builds and starts the container, next to `make talk` | one command before the talk |
| A8 | **The terminal is a demo slide** (S10): an iframe through the existing `data-src` / `data-zoom` and the ‹ › bar, which already gives the keys back to the deck | no new engine work |
| A9 | **Readable from the back**: ttyd's `-t fontSize=28`, a light theme matching the off-white slides, and a short prompt (`$ `) | the default terminal is far too small for a projector |
| A10 | **The answer is printed plainly**: each step prints only `result.output`; step 3 also prints how many messages were sent along | the audience should read the answer, not a log |

## The steps in code

The real files are `talk/agent-demo/step1_llm.py` to `step4_tool.py`; the slides paste them with
single blank lines. What is below was the first draft.

```python
# step1.py - just call an LLM
from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna")
result = agent.run_sync("What day is it next Friday?")
print(result.output)
```

```python
# step2.py - give it context: today's date
from datetime import date
from pydantic_ai import Agent

agent = Agent("openai:gpt-6-luna", instructions="You plan meetings. Answer in one sentence.")

@agent.instructions
def today() -> str:
    return f"Today is {date.today():%A %d %B %Y}."

result = agent.run_sync("What day is it next Friday?")
print(result.output)
```

```python
# step3.py - simulate memory: send the earlier conversation along
...
first = agent.run_sync("My name is Sam, and I need a room for six people.")
second = agent.run_sync("What was my name, and how many people?",
                        message_history=first.all_messages())
print(second.output)
```

How the `.env` is loaded is part of the build: `docker run --env-file` puts the key in the
environment, so the scripts need no `dotenv` line, which keeps them shorter on the slide.

## The questions, answered (2026-11-06)

| Id | Question | Answer |
|---|---|---|
| Q1 | Layout | **The code first, one slide per step; then one terminal slide** with the steps and their commands on the left and the terminal on the right |
| Q2 | Typing on stage | **Typed live**, with short make targets in the container: `make run-llm`, `make run-system`, `make run-memory`, `make run-tool` |
| Q3 | Code on the slide | **Pasted into `index.html`**, not read from the files - so a change to a step is made twice |
| Q4 | Step 4, a tool | **In** - it has a make target |
| Q5 | Fallback | still open; the plan's backup video (T1) covers it for now |

## Where it goes in the deck

After the five anatomy slides and before the team slide: the definition, the parts as a picture,
the parts as code and run, and only then *one agent is not enough*.

## What building it taught

- **ttyd is not packaged for Debian bookworm**: the image takes ttyd 1.7.7's own release binary,
  pinned by version and checked against its SHA-256.
- **Only the key goes in**: `grep '^OPENAI_API_KEY=' .env | docker run --env-file /dev/stdin`,
  so the key is never on a command line, and the rest of `.env` stays out. The port is published
  on `127.0.0.1` only - it is a writable shell.
- **The answers, on 6 November**: step 1 says it does not know today's date; step 2 says
  "Next Friday is 13 November 2026"; step 3 remembers Sam and six people; step 4 calls
  `free_rooms(2026-11-13, 6)` and names both rooms.

## Next steps

1. A run-through on the projector size (1920 x 1080), to check the terminal's font size.
2. Q5, the fallback.
