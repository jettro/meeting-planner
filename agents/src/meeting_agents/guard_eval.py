"""Run the chat guard's evaluation set against the real model (design_guardrails.md §15.8).

Each case is asked exactly as `@Guard` asks it - the catalog's prompt and model
card, the same question and the same pick-one answer type - but without a team,
so the set runs in seconds. On a language model there is no confidence, so the
measure is plain accuracy (GR15): how often a case comes to what it should.

    make guard-eval
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml
from akgentic.llm import ModelConfig
from akgentic.llm.providers import create_model, get_output_type
from pydantic_ai import Agent

from meeting_agents.guard import (
    AnswerQuestion,
    AnswerTopic,
    MessageQuestion,
    MessageTopic,
    Verdict,
    answer_refused,
    message_refused,
)

AGENTS = Path(__file__).resolve().parents[2]
CATALOG = AGENTS / "catalog" / "meeting-planner"
CASES = AGENTS / "evals" / "guard_cases.yaml"


def _payload(path: Path) -> Any:
    return yaml.safe_load(path.read_text())["payload"]


async def _ask(
    agent: Agent[None, Any],
    config: ModelConfig,
    question: MessageQuestion | AnswerQuestion,
    kind: type[MessageTopic | AnswerTopic],
) -> str:
    result = await agent.run(question.rendering(), output_type=get_output_type(config, kind))
    return str(result.output.topic)


def _mark(refused: bool, expect: str) -> str:
    got = "refuse" if refused else "pass"
    return "ok" if got == expect else f"WRONG ({expect})"


async def run() -> int:
    config = ModelConfig(**_payload(CATALOG / "model" / "guard_model.yaml"))
    prompt = _payload(CATALOG / "prompt" / "guard_prompt.yaml")["value"]
    agent: Agent[None, Any] = Agent(create_model(config), system_prompt=prompt)
    cases = yaml.safe_load(CASES.read_text())

    rows: list[tuple[str, str, str, str]] = []
    for case in cases["message"]:
        question = MessageQuestion(
            message=case["text"], last_said=case.get("last", ""), requested=case.get("requested", False)
        )
        topic = await _ask(agent, config, question, MessageTopic)
        rows.append(
            ("message", case["text"], topic, _mark(message_refused(Verdict(topic=topic)), case["expect"]))
        )
    for case in cases["answer"]:
        question = AnswerQuestion(answer=case["text"], message=case.get("message", ""))
        topic = await _ask(agent, config, question, AnswerTopic)
        rows.append(
            ("answer", case["text"], topic, _mark(answer_refused(Verdict(topic=topic)), case["expect"]))
        )

    wrong = [row for row in rows if row[3] != "ok"]
    for check, text, topic, mark in rows:
        print(f"{mark:<16} {check:<8} {topic:<9} {text[:80]}")
    print(f"\n{config.model}: {len(rows) - len(wrong)}/{len(rows)} right")
    return 1 if wrong else 0


def main() -> None:
    sys.exit(asyncio.run(run()))


if __name__ == "__main__":
    main()
