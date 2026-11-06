# Design: the slides as HTML

> **Status:** proposed, 2026-11-05. The first step is built: the engine, the style, a title slide
> and an about slide. The rest of the deck waits for this design to be agreed.
> The story is in [`plan.md`](plan.md); this is only about how the slides are made.

## Why HTML

The talk switches between slides and a live demo eight or nine times. In Keynote every switch is a
window change; in HTML the planner can *be* a slide, in an iframe. The diagrams that build up -
the anatomy of an agent, the crew that grows, the actors and their messages - are natural in
SVG and CSS. And the deck lives next to the code it is about, so a renamed message type can be
found in the slides too.

What is given up: Keynote's transitions and editing by dragging. A slide is changed in text.

## Decisions

| Id | Decision | Why |
|---|---|---|
| S1 | **No framework**: one `index.html`, one `slides.css`, one `slides.js` (about a hundred lines) | keeps it simple and offline by construction; reveal.js does far more than this talk needs, and would be another thing to learn and vendor. Revisit if S8 turns out to be hard |
| S2 | **A fixed 1920 x 1080 canvas, scaled to the window** | a slide looks the same on the laptop and the projector; sizes are written in pixels of the canvas |
| S3 | **One `<section class="slide">` per slide**, in order, in `index.html` | the deck reads top to bottom as the talk does |
| S4 | **Steps**: an element with class `step` appears on the next key press, in document order | enough for build-up diagrams and lists; no other animation |
| S5 | **Keys**: → ↓ space PageDown forward; ← ↑ PageUp back; Home and End; `f` full screen. A presentation clicker sends PageDown and PageUp | |
| S6 | **The URL says where you are** (`#/3`), so a reload or a demo detour comes back to the same slide | |
| S7 | **Speaker notes** in an `<aside class="notes">` per slide; hidden on the slide | every slide has one |
| S8 | **Notes on the slide, not in a second window**: `n` or a quiet *notes* button at the bottom shows them in a panel over the slide, and they stay open or closed from slide to slide | decided 2026-11-06: the notes are a safety net, not something to read from; a presenter window is more than the talk needs. The button is faint (35 %) until hovered |
| S15 | **Fast mode**: `a` or a *fast* button beside *notes* - every slide appears whole, and → and ← move a whole slide | for a run-through, or when time runs short. As faint as the notes button; a dot (● fast) is the only sign it is on. Remembered in this browser (`localStorage`), so check it is off before the talk |
| S14 | **A PDF export** - later | asked for (plan T8); a print stylesheet that lays every slide out on its own page, steps shown, demo slides as a still with their address |
| S9 | **Served from `localhost`**, port 8500, with `make talk`; never opened as a file | the planner's login cookie is only sent to `localhost` - the same trap as `127.0.0.1` in `docs/demo.md` |
| S10 | **Demo slides are iframes** of the planner and the services, with a link to open the same page in a tab, and a recorded video as the fallback | to be proven by the next step: the login must work inside the frame, and no server may forbid framing |
| S11 | **No CDN, no web fonts**: the system font (San Francisco on the Mac that presents), images in `talk/slides/img/` | venue wifi cannot be trusted |
| S12 | **The style** - see below | |
| S13 | **Images from the old deck** (the balloons, the unconvinced man) are copied into `img/` as compressed JPEGs, only those used | the originals are 7-50 MB TIFFs |

## The style (S12)

Simple, and quiet enough that the demo is the loudest thing on screen.

- **An off-white canvas, near-black text, one accent colour**, from the Yuma brand guidelines
  (Frontify): the canvas is **Off white `#F8F5F5`**, softer than white on a projector; the accent is **Purple `#6434DA`** - readable as text on white, unlike Future
  Green - and panels are **Granular Grey `#F0ECE9`**. Both are CSS variables, `--accent` and
  `--panel`.
- **The title slide is the exception: dark**, as a nod to the DevPulse site, because it is on
  screen while people come in. Their background, cream text and orange; a terminal line
  (`$ devpulse talk --no 7`); a striped isometric cube in Yuma Purple, DevPulse orange and Yuma
  Earth; and the team's own messages streaming past it, slowly. The cube is drawn by
  `title.js`, not copied from their site. On dark, the accent is Yuma Pink `#EBA9FF`.
- **The Yuma logo** is the full black logo, `img/yuma-logo-black.svg`, on the about slide only.
  The guidelines ask for the black logo on a light background, and never in a secondary colour.
- **Fonts:** the system font for now. Yuma's body font is Inter, which can be added as local
  font files (S11); its headline font, BogueSlab Thin, is too thin for a projector, except perhaps
  on the title slide.
- **Big type.** A title is 112 px on the canvas, body text 48 px. Anything smaller than 32 px is
  not meant to be read from the back.
- **One idea per slide**, as in the playful deck: a title that says something, a single line that
  sticks, little else.
- **A thin footer** with the talk's title and the slide number, left out on the title slide.
- **Code** in the system monospace font, at 32 px or more, on a light grey panel; at most fifteen
  lines on a slide.
- **Diagrams** as inline SVG, drawn in the text colour and the accent - no other colours, so the
  accent always means *look here*.
- **Agents are named as in the code**, `@Coordinator`, in the monospace font.

## The first step (built)

| File | What is there |
|---|---|
| `talk/slides/index.html` | the deck: a title slide and an about slide |
| `talk/slides/slides.css` | the canvas, the style, the footer |
| `talk/slides/slides.js` | scaling, keys, steps, the URL |
| `Makefile`, target `talk` | serves `talk/slides` on <http://localhost:8500> |

The about slide uses the bio from the DevPulse page and the old deck, and the Yuma logo.

## The deck so far

| # | Slide |
|---|---|
| 1 | title (dark) |
| 2 | about me |
| 3 | the comic: a quick meeting, and what if I built a team for this? |
| 4 | what is an agent? - four definitions, then the one sentence |
| 5-9 | the anatomy of an agent |
| 10-13 | the first agent in code: an LLM, context, memory, a tool ([`design_agent_demo.md`](design_agent_demo.md)) |
| 14 | run it: the four make targets, and a live terminal (ttyd, `make agent-demo`) |
| 15 | one agent is not enough: a team |
| 16-17 | the sample: what it does, how it is built |
| 18 | the repository |
| 19-20 | live: the planner, the console |

## The comic (slide 3)

Six panels drawn for the talk make one comic page: *could you organise a quick meeting?* -
calendar tetris - the room is *BOOKED* - *can we have lunch as well?* - *could we move it to
Friday?* - *what if I built a team for this?* The last panel's dream is the crew of the talk.

- Three across, two down, on a white page with ink borders and white gutters; one panel per key
  press, landing from slightly small and tilted into place, as if drawn.
- The originals are 1536 x 1024 PNGs of about 3 MB each; the slide uses 1200 px JPEGs of about
  400 KB, `img/meeting-01-quick-meeting.jpg` … `meeting-06-build-a-team.jpg`.
- It replaces the old deck's opening (*the dullest activity of the day*) as the hook for part 1.

## What is an agent? (slide 4)

Screenshots of how four big parties define an agent, each in a plain browser frame with its
domain, one per key press, and then the one short sentence on top of them.

| Who | Page | The definition, in short |
|---|---|---|
| Anthropic | *Building effective agents* (2024) | LLMs dynamically direct their own processes and tool usage |
| OpenAI | *New tools for building agents* (2025) | systems that independently accomplish tasks on behalf of users |
| Google Cloud | *What is an AI agent?* (updated 2026) | software systems that use AI to pursue goals and complete tasks for users |
| IBM | *What are AI agents?* | a system that autonomously performs tasks by designing workflows with available tools |
| Simon Willison | *"agent" may finally have a widely enough agreed upon definition* (September 2025) | **An LLM agent runs tools in a loop to achieve a goal.** |

- The last one is the answer: short, one sentence, and its author argues it is now widely agreed
  on - Anthropic, he notes, settled on *tools in a loop* too. Its three words are purple - **tools,
  loop, goal** - because they are what the anatomy slides that follow build up.
- The screenshots were taken on 2026-11-06 in the browser, with the text enlarged on the page
  before capturing so it is sharp enough for a projector, and sticky headers and cookie banners
  out of the way. OpenAI's sentence sits inside a paragraph, so it is highlighted. Nothing else
  on the pages was changed.
- Files: `img/def-anthropic.png`, `def-openai.png`, `def-google.png`, `def-ibm.png`,
  `def-willison.png`, 70-170 KB each.

## The anatomy of an agent (slides 5-10)

The six slides of the playful pptx, redrawn in this deck's style: the same playful titles and
takeaways, the same robot gaining one piece of gear per slide - clipboard, light bulb, tools,
backpack, shield - and the same diagram growing beside it. `anatomy.js` builds them from one list
of gear, so a word changes in one place.

- The gear is shown as **cards in two columns** (goal, tools, boundaries | LLM, context); the card
  a slide adds is white with a purple edge, the earlier ones are grey. A grid made every card in
  a row as tall as the tallest, and the fifth slide ran into its takeaway.
- The **team slide** shows *You - messages + routing* and the three robots as agents A, B and C,
  appearing one per key press.
- The robots are the pptx's images, made smaller (900 px high, transparent PNG, 640-780 KB each)
  in `img/robot-1.png` … `robot-5.png`. The team uses robots 3, 4 and 5, as the pptx does.
- Not taken over: the pptx's own palette (teal, rust, cream) and its *1 / 6* counter; the deck's
  footer counts instead.

## Introducing the sample (slides 11 and 12)

Two slides, after the agent anatomy and before the repository and the demo.

- **What it does** (*The sample: a meeting planner*): the request in one sentence, then four
  jobs, one per key press - agendas, places, lunch, and *you approve* (purple, because it is the
  point). Each job has a large icon - 📅 🏢 🥗 ✋. Generated pictures in the robots' style were
  considered and turned down (2026-11-06): the icons read well and keep the slide quiet.
- **How it is built**: built bottom-up. The three services are there from the start, each with
  two doors - *MCP · tools* on top for agents, *REST · OpenAPI* at the bottom for people and the
  web page. Then the three agents, each above its one service; `@Catering` beside
  `@FacilityManager`, joined to it, because a room and its lunch go together. Then
  `@Coordinator` across the first two columns, joined to the two it talks to, and `@Human` beside
  it. **A model is white with a purple edge and an *LLM* tag; code is dark and solid** - the one
  visual difference that carries the slide's point.
- The lines are drawn by the boxes' own `::before` and `::after`, so they appear with their box.

## The repository slide (slide 13)

Just before the demo: <https://go.jettro.dev/pulse>, which redirects to
`github.com/jettro/meeting-planner`. To make it more than a link, the crew *arranges* it the way it
arranges a meeting:

- a short trace plays on its own, one message every 0.9 s - the coordinator asks the facility
  manager for "somewhere they can clone it", catering offers lunch with it and is told *No.*;
- then an approval card waits: *@Coordinator asks @Human - show the repository to the room?*
  Nothing is shown before you approve;
- **→ is the approval** (the slide's one step): the card turns into the QR code and the link,
  *✓ approved by @Human*. The joke is the talk's own point - the human approves.

`repo.js` plays it when the slide is shown; `slides.js` now sends a `shown` event to a slide when
it becomes current, and says whether it arrived fully built (coming back from the demo), in which
case everything shows at once. The QR code is `img/qr-pulse.svg`, generated once with Python's
`qrcode` package (29 x 29, error correction M), so nothing is needed at the venue.

Other ideas, not built: the three robots holding up the QR code as a sign; `git clone` typed in a
terminal, letter by letter; the QR code assembling itself from the trace's characters.

## The iframe spike (S10) - it works

A demo slide (`<section class="slide demo" data-src=… data-zoom=…>`) puts the planner in a frame
under a thin dark bar: *live*, the address, and *open in a tab*. Tried on 2026-11-05 against
`make up`, the slides on `localhost:8500`:

- **Framing is allowed.** Neither the planner's nginx nor the server sends `X-Frame-Options` or a
  CSP `frame-ancestors`.
- **The login works inside the frame.** The cookie is `SameSite=Lax`, and `localhost:8500`,
  `:8300` and `:8200` are the same *site* - a port does not make a site - so the cookie is sent.
  Logging in, the Platform tab and the Meetings tab all worked in the frame.
- **The demo keeps its state.** The frame loads the first time its slide is shown and stays; going
  back a slide and forward again shows the same page.
- **The keys.** Once the planner is clicked, it keeps the keys, and the deck cannot listen inside
  a frame from another origin. So the bar has **‹ and › buttons**, and any click on the bar
  gives the keys back to the slides. A clicker is caught the same way: after working in the
  planner, click the bar first. Found in the first try-out, where the arrows seemed dead.
- **No caching.** `make talk` runs `talk/serve.py`, which sends `Cache-Control: no-store`;
  Python's plain server let the browser keep an old `slides.js` after an edit.
- **Bigger on the projector.** `data-zoom="1.25"` renders the page at 1536 px wide and scales
  it up to the canvas.

**The akgentic console** (slide 4, `localhost:8400`) works in a frame the same way: no framing
headers, and it shares the planner's session, so it opens logged in. Opening a team shows a
*Request failed: Not Found - Team not found* toast, in a plain tab as well: the console asks for
the `memory-shared` workspace's tree, and the server refuses shared paths on purpose
(`docs/memory.md`). Harmless, but it shows on the projector - close it, or open a team before
the talk.

Not yet tried: the trace's live socket while a team is running, and the two questions answered
in the frame. Both use the same cookie, so they are expected to work; the next demo run will
show.

## Next steps

1. Agree on this design and the style. Decide on Inter.
2. Run one whole meeting inside the demo slide, with the trace live.
3. One build-up diagram (the anatomy of an agent) to settle how diagrams are drawn.
4. Then the deck, part by part, as in [`plan.md`](plan.md).

## Open questions

1. Inter as local font files, or the system font?
2. A photo on the about slide, or none?
3. The DevPulse page says *Principle Consultant*; the about slide says *Principal Consultant*.
   Which is right?
