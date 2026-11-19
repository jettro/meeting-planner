# Design: the team as configuration, and finding a slide fast

> **Status:** built 2026-11-09, as proposed (Q1-Q4 answered as proposed). Slides 31-32; the switcher
> and still mode are in `slides.js`; the viewer in `yaml.js`; the catalog route in `serve.py`.
> Two asks from the human: show akgentic's YAML configuration - a prompt among it - in a slide
> you can scroll through; and a way to switch slides quickly, with a preview, without the deck
> getting too heavy.

## 1. The team as configuration

### What there is

`agents/catalog/` holds 29 YAML files in three namespaces (`meeting-planner`,
`meeting-planner-chat`, `memory-keeper`). Every file is a **card** with the same header - `id`,
`kind` (team, agent, prompt, model, tool), `namespace`, `model_type` (the Python class that reads
it) - and a `payload`. Cards point at each other with `__ref__`:

```
team.yaml ── entry_point: human → coordinator → scheduler
                                              → facility_manager → catering
facility_manager.yaml ── prompt:    __ref__ facility_manager_prompt   (52 lines of text)
                     ── model_cfg: __ref__ default_model             (openai, gpt-6-luna)
                     ── tools:     __ref__ location_mcp, place_memory, booking_rules
location_mcp.yaml ── url: ${LOCATION_MCP_URL}, bearer_token: ${LOCATION_MCP_API_KEY}
```

### Proposed slides

| # | Slide | Content |
|---|---|---|
| Y1 | **A team is configuration** | a small diagram of the cards for one agent: the team card's tree, then `@FacilityManager`'s card with arrows to its prompt, model and three tools. One line each on what is *not* in code: who is on the team and under whom, which model, which prompt, which tools, which guardrail. Takeaway: *change a prompt or a model without touching Python* |
| Y2 | **The cards, to scroll through** | a viewer: the file names on the left as tabs - `team.yaml`, `facility_manager.yaml`, `facility_manager_prompt.yaml`, `default_model.yaml`, `location_mcp.yaml`, `booking_rules.yaml`, then under *the chat guard* (2026-11-19) `chat_guard.yaml`, `guard.yaml`, `guard_prompt.yaml`, `guard_model.yaml` - and the chosen file on the right, highlighted, in a panel that scrolls |

### How you move through the viewer

The arrow keys and the clicker already mean *next and previous slide*, so they cannot also
scroll. Proposed:

- **→ / PageDown / the clicker** - the next file (each tab is a step, like any build-up);
- **the trackpad or mouse wheel** over the panel - scroll the file; a visible scroll bar;
- **`j` / `k`** - scroll down and up by a few lines, for the keyboard;
- a click on a tab - that file.

### Where the YAML comes from

| Option | How | For | Against |
|---|---|---|---|
| **a. Read the real files** | `serve.py` also serves `agents/catalog/` (read-only) under `/catalog/`; the viewer fetches them | always what runs; a 52-line prompt is not copied by hand | the deck depends on the repository layout; a PDF export needs them inlined then |
| **b. Paste them in** | like the code slides | the deck stands alone | 6 files, ~200 lines, copied and kept in step by hand |

Proposed: **a** - the code slides were pasted because they are short and edited for the slide;
these are shown as they are, and their length is the point.

### Where in the deck

After *What messages buy you* (30): the messages are types in Python, and the team that sends
them is configuration. That also sets up the later *why akgentic* slide.

## 2. Finding a slide fast

### A slide switcher

- **`o`** (overview), or a faint **slides** button beside *notes* and *fast*, opens a popup over
  the deck: every slide as a small preview in a grid, six to a row, the current one marked, the
  extras after a divider.
- **Click** a preview, or move with the arrow keys and press **Enter** - that slide, fully built.
- **Type a number** and Enter - that slide. **Esc** closes.
- The previews are the slides themselves, copied and shrunk once when the popup first opens -
  every step shown, notes left out. No images to keep up to date.

### What makes it heavy, and the stills

The live slides are the heavy ones: two planner frames, two console frames, two terminals - each
a whole application. They load only when their slide is first shown, and then stay.

- **In the switcher**, a live slide is never copied with its frame: its preview is a **still** - a
  screenshot in `img/`, taken once - or, until there is one, a card saying *live: localhost:8300*.
- **A still mode**, `s` or a faint *still* button: every live slide shows its still instead of the
  application, with a small *still* label. For a venue where the demo or the network fails - the
  plan's backup (T1) in the deck itself - or for a run-through without the services running.
- The stills: the planner, the console, and a terminal after each run - six screenshots, taken
  from the running applications at 1920 x 1080.

## Questions

| Id | Question | Options |
|---|---|---|
| Q1 | Y1 and Y2, or only the viewer? | both (proposed); only Y2 |
| Q2 | Where the YAML comes from | a, the real files (proposed); b, pasted |
| Q3 | The switcher: a popup grid, or a strip along the bottom? | popup grid (proposed) - all fifty at once; a strip shows ten at a time and needs scrolling |
| Q4 | Still mode, as well as the switcher's stills? | yes (proposed) - one set of screenshots serves both; or switcher only |

## Built (2026-11-09)

- **Keys**: `o` the switcher (and a faint *slides* button), `s` still mode (and *still*), `j`/`k`
  scroll the YAML viewer. In the switcher: click, arrows and Enter, or digits and Enter; Esc or
  `o` closes. The switcher counts the previews on a row, so it fits any window.
- **`serve.py`** serves `/catalog/` - only `.yaml` files inside `agents/catalog`; anything else is a
  404 (checked: `/catalog/../../.env` is refused). `SLIDES_PORT` runs a second copy.
- **The steps event**: the engine now tells a slide when a step is shown or hidden (`steps`), which
  the viewer uses; any slide may.
- **A missing still** shows *no still yet* in the deck and a *live* card in the switcher - never a
  broken image.

### The stills - placeholders for now

`img/still-planner.png` and `img/still-console.png` were taken with headless Chrome, which has no
session: they show the sign-in pages. The terminal stills (`still-terminal-tool.png`,
`still-terminal-meeting.png`) do not exist yet. A good still shows a moment - a planned meeting,
the chat with its cards, the trace in the console, a terminal after a run - and only the person
presenting can choose and stage it. To take one at exactly the size the slide shows it:

1. Open the app in Chrome, get it to the moment you want.
2. DevTools → *Toggle device toolbar* → *Responsive*, and set the size and the device pixel ratio:
   the planner and the console **1536 x 813 at 1.25**; a terminal **1240 x 1016 at 1**.
3. DevTools menu (⋮) → *Capture screenshot*, and save it over the file in `talk/slides/img/`.

The second planner and console slides (the demo after memory) use the same two stills; give them
their own files when they should show a different moment.
