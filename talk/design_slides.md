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
| S7 | **Speaker notes** in an `<aside class="notes">` per slide; hidden on the slide | written now, shown by S8 later |
| S8 | **Presenter view** - later: `p` opens a second window with the notes, the next slide and a timer, kept in step through a `BroadcastChannel` | not needed for the first step; small enough to add without a framework |
| S9 | **Served from `localhost`**, port 8500, with `make talk`; never opened as a file | the planner's login cookie is only sent to `localhost` - the same trap as `127.0.0.1` in `docs/demo.md` |
| S10 | **Demo slides are iframes** of the planner and the services, with a link to open the same page in a tab, and a recorded video as the fallback | to be proven by the next step: the login must work inside the frame, and no server may forbid framing |
| S11 | **No CDN, no web fonts**: the system font (San Francisco on the Mac that presents), images in `talk/slides/img/` | venue wifi cannot be trusted |
| S12 | **The style** - see below | |
| S13 | **Images from the old deck** (the balloons, the unconvinced man) are copied into `img/` as compressed JPEGs, only those used | the originals are 7-50 MB TIFFs |

## The style (S12)

Simple, and quiet enough that the demo is the loudest thing on screen.

- **White canvas, near-black text, one accent colour.** The accent is a CSS variable,
  `--accent`, a placeholder until the Yuma logo and its colour are in.
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

The about slide uses the bio from the DevPulse page and the old deck. The logo is a placeholder.

## Next steps

1. Agree on this design and the style, with the Yuma logo and colour.
2. **The iframe spike** (S10): one slide with the planner in a frame, logged in, on the projector
   resolution. If it fails, the demo goes in a tab and S10 changes.
3. One build-up diagram (the anatomy of an agent) to settle how diagrams are drawn.
4. Then the deck, part by part, as in [`plan.md`](plan.md).

## Open questions

1. The Yuma logo: as SVG if there is one, and its brand colour for `--accent`.
2. A photo on the about slide, or none?
3. The DevPulse page says *Principle Consultant*; the about slide says *Principal Consultant*.
   Which is right?
