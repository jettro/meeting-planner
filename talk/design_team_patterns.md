# Design: team architectures - what others say, and what the sample does

> **Status:** built 2026-11-06 as slides 16-20 (`patterns.js` draws slide B's diagrams). Q2-Q5
> got the defaults below, to be changed when the human disagrees; Q6 is open.
> Part 3 of the story in [`plan.md`](plan.md) ("Bring a crew", about 10 minutes). It comes after
> *Run it* (slide 15) and before the sample (now slides 21-22).

## Where the talk is when this starts

The room has seen what an agent is (slide 4), its parts (5-9), the first sign of a team (10), and
one agent in code, run live (11-15). Now: when do you need more than one, how do you arrange
them, and what goes wrong - and then the sample as one worked answer.

## What the sources say (checked 2026-11-06)

All URLs were opened. The figures for Google, Cognition 2026 and Anthropic 2026 were checked a
second time against the page text.

| Source | Date | What it adds to the talk |
|---|---|---|
| Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Dec 2024 | workflows (code decides the path) vs agents (the model decides); five patterns: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer. *Start simple* |
| Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) | Jun 2025 | a lead agent with parallel subagents: +90 % on their research eval, at about 15x the tokens of a chat. Poor fit when agents depend on each other |
| Cognition, [Don't build multi-agents](https://cognition.com/blog/dont-build-multi-agents) | Jun 2025 | the counter-argument: share full context; *actions carry implicit decisions*; two subagents built a game that did not fit together |
| OpenAI, [A practical guide to building agents](https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf) | 2025 | *maximize a single agent first*; then the manager pattern (agents as tools) or decentralized handoffs |
| LangChain, [Choosing the right multi-agent architecture](https://www.langchain.com/blog/choosing-the-right-multi-agent-architecture) | Jan 2026 | subagents (supervisor), skills, handoffs, router; start with one agent |
| Anthropic, [When to use multi-agent systems](https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them) | Jan 2026 | three reasons only: context protection, parallelization, specialization. *"Decomposition follows context, not problem type."* 3-10x the tokens |
| Google Research, [Towards a science of scaling agent systems](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/) | Jan 2026 | 180 configurations: centralized +81 % on parallel work, every multi-agent variant 39-70 % worse on sequential planning; independent agents amplify errors 17.2x, with an orchestrator 4.4x |
| Google ADK, [workflow patterns](https://adk.dev/workflows/patterns/) | 2026 | sequential, parallel, loop, coordinator, hierarchical, generate-and-review, human-in-the-loop |
| Microsoft Agent Framework, [orchestrations](https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/) | 2026 | sequential, concurrent, handoff, group chat, magentic (a manager with a task ledger) |
| Berkeley, [Why do multi-agent LLM systems fail?](https://arxiv.org/abs/2503.13657) | 2025 | 14 failure modes over 1,600 traces: design, misalignment between agents, verification |
| Cognition, [Multi-agents: what's actually working](https://cognition.com/blog/multi-agents-working) | Apr 2026 | the follow-up: a reviewer with a clean context works, a manager with children works; parallel writers and negotiating swarms still do not. *"Writes stay single-threaded"* |

**The consensus, in one line each:**
- **Start with one agent.** Every party says it (Anthropic, OpenAI, LangChain, Cognition).
- **When you split, put something in charge.** The orchestrator / supervisor / manager is the one
  pattern everybody endorses, and it is also where errors are caught (17x vs 4x).
- **Split by context, not by job title.** Anthropic 2026 - and that is a *bounded context*, the
  same reason we split services (old slide 43).
- **Many may think, one should write.** Cognition 2026.
- **It costs tokens**: 3-15x a single agent.

## The patterns - five names for the same five things

| Pattern | Anthropic | OpenAI | LangChain | Google ADK | Microsoft | old deck |
|---|---|---|---|---|---|---|
| **Pipeline** - one after the other | prompt chaining | chaining | - | sequential | sequential | - |
| **Fan-out** - side by side, then gather | parallelization | parallel runs | - | parallel | concurrent | *parallel execution* (39) |
| **Orchestrator** - one in charge, others as workers; nested, it is a hierarchy | orchestrator-workers | manager | supervisor, hierarchical | coordinator, hierarchical | magentic | 40-41 (diagrams, probably supervisor and hierarchy) |
| **Handoff** - pass the conversation on | routing | handoffs | handoffs, router | transfer | handoff | - |
| **Group chat** - all in one conversation | - | - | network, swarm | - | group chat | *group chat* (42) |
| **Generator + reviewer** - one makes, one checks | evaluator-optimizer | evaluator loop | - | generate and review | - | - |

## What the sample does with this

| Pattern | In the meeting planner |
|---|---|
| Orchestrator | **`@Coordinator`** - last year's *Personal Assistant*, and it is **plain code** - a deterministic orchestrator, the way Anthropic's *workflow* describes it. The 4.4x containment, without a model in charge |
| Hierarchy | `@FacilityManager` with `@Catering` under it |
| Handoff / router | `@Intake`, the front door for the chat |
| Human in the loop | `@Human` is a team member; nothing is booked before a yes |
| Split by context | Scheduler, FacilityManager and Catering each own one service and its MCP tools - one bounded context each |
| Turned down | group chat, and a model as the router - harder to trust, to test and to explain |

## Proposed slides (part 3, about 10 minutes)

| # | Slide | Content |
|---|---|---|
| A | **Start with one agent** | the consensus, with the logos' words: Anthropic *start simple*, OpenAI *maximize a single agent first*, Cognition *don't build multi-agents*. Then the three reasons that justify more (context protection, parallelization, specialization), and the price: 3-15x the tokens |
| B | **Five patterns** | five small diagrams that appear one by one (pipeline, fan-out, orchestrator, handoff, group chat - generator + reviewer as a sixth, or folded into the orchestrator). Under each, in small type, the names Anthropic, OpenAI, Google and Microsoft use. The old deck's parallel and group chat redrawn in the new style |
| C | **What goes wrong** | Google's numbers as three big figures: +81 % on parallel work, -39 to -70 % on sequential, errors 17x without an orchestrator and 4x with one. Then Cognition 2026: *many may think, one should write* |
| D | **Split like services** | old slide 43 (microservices) redrawn: split by *bounded context*, not by job title - Anthropic's *decomposition follows context* next to it |
| E | **The crew, now built** | old slide 38's crew with the reveal it exists, and which patterns the sample uses (the table above): an orchestrator in plain code, a hierarchy, a front door, a human. Leads into the sample slides |

The plan's *four questions* (who does what, how do they talk, who keeps what, where is the human)
could follow E or be folded into it - see Q4.

## Answers and defaults

| Id | Answer |
|---|---|
| Q1 | **All five slides** - answered by the human |
| Q2 | default: **text, with the source in small type** - the definition slide already makes the point that the big names are quoted; screenshots can be added later |
| Q3 | default: **not on B**; generator + reviewer appears on C as what works today (Cognition 2026), and can lead into the guardrails slide |
| Q4 | default: **not built yet** - the architecture slide (17) already answers *who does what* and *where is the human* |
| Q5 | default: **shown on B, and turned down on E** |
| Q6 | still open - B's *orchestrator* covers supervisor and hierarchy either way |

## Open questions (as first asked)

| Id | Question | Options |
|---|---|---|
| Q1 | **Five slides, or fewer?** Part 3 is budgeted at 10 minutes | (a) all five; (b) merge A and C into one *when it pays and when it hurts*; (c) B and E only, with A and C in the speaker notes |
| Q2 | **Screenshots of the sources**, as on the definition slide? | (a) yes for A (three quotes in browser frames), text elsewhere; (b) only text with the source in small type; (c) screenshots everywhere - heavy |
| Q3 | **Generator + reviewer**: its own pattern on B? | it is the one Cognition says works best today; but the sample does not use it. Could be the hook for the guardrails slide (plan T4) |
| Q4 | **The four questions**: a slide of their own after E, or folded into E? | |
| Q5 | **Group chat** - show it, and say why the sample turned it down? | the old deck had it; 2026 sources say negotiating swarms are *mostly a distraction* |
| Q6 | **Old slides 40-41** are diagrams only, and could not be read from the file. What did they show? | if supervisor and hierarchy, they map onto *orchestrator* |
