# Image prompts: from one agent to a team

Three images for slides 19, 20 and 22 (2026-11-18). They are one series: the same robots, the
same style, the same framing, so they read as one story told in three panels.

## How to make them look like one set

1. **Start one ChatGPT conversation for all three**, and generate them in order. Ask for the next
   one *in the same conversation*, so it keeps the characters.
2. **Attach two reference images** to the first prompt, from `talk/slides/img/`:
   `robot-3.png` (the robot) and `meeting-06-build-a-team.jpg` (the comic style).
3. **Same size for all three**: landscape, 3:2 (1536 x 1024).
4. **Save them** as PNG, then make the JPEGs the slides use: `talk/slides/img/art-1-solo.jpg`,
   `art-2-team.jpg` and `art-3-lead.jpg`. The slides show a placeholder until those exist.

**Made on 2026-11-18**: ChatGPT gave 1536 x 1024 PNGs of 2-2.8 MB, on a background a shade darker
than the slide (#F6F1F2-#F8F3F3 against #F8F5F5). The JPEGs (300-490 KB) were made with the
near-white, near-grey pixels set to exactly #F8F5F5 - the cream robots are untouched - so no edge
shows on the projector. Do the same for a new version: any near-white with less than 8 between
its channels, quality 86.

## The style, in every prompt

Paste this block at the start of each prompt:

> Hand-drawn comic illustration in the exact style of the attached images: cream-white robots
> with teal and orange details, a teal cap with an antenna, big round goggle eyes, orange
> sneakers; bold ink outlines, warm slightly textured colours, gentle humour. Landscape 3:2.
> Plain, flat, very light warm off-white background (#F8F5F5) with nothing else behind the
> scene, so it blends into a presentation slide. No text, no letters, no words anywhere in the
> image. Keep the characters and the style identical across the images in this conversation.

## 1. One agent, every job - `art-1-solo` (slide 19)

> [style block]
>
> One robot alone at a cluttered desk, clearly overwhelmed: sweat drops, eyes spinning, cap
> askew. It tries to do everything at once with too many arms: one hand flips through a big
> calendar, one holds a ring of room keys, one holds a lunch menu and a sandwich, one dials an
> old telephone, one types. Around it hangs a whole wall of tools on hooks - far too many to
> choose from: calendars, keys, menus, wrenches, stamps, plugs, magnifying glasses. Tall,
> tilting stacks of paper and envelopes pile up on the desk and the floor; one stack is about to
> fall. A coffee cup tips over. Funny, not sad.

## 2. A team without a lead - `art-2-team` (slide 20)

> [style block]
>
> The same robot, now as a team of four identical robots of this kind, each with its own
> small set of tools: one with a calendar, one with a ring of room keys, one with a lunch tray
> and a sandwich, one with a telephone. They are cheerful and busy, and each job is clearly
> lighter than before. But nobody is in charge, and it shows: two robots reach for the same
> room key at the same time and bump into each other; envelopes fly back and forth in a tangle
> of arrows between them; one robot waits, idle, tapping its foot; another delivers a sandwich
> to a robot that already has one. Happy faces, slightly chaotic scene.

## 3. A lead who hands out the work - `art-3-lead` (slide 22)

> [style block]
>
> The same four robots, now with a fifth robot of the same kind as their lead, recognisable by a
> headset and a clipboard with a checklist. The lead stands in the middle and hands one envelope
> to each specialist: the calendar robot, the room-key robot, the lunch robot. Each works calmly
> on its own task at its own small table. Envelopes travel in neat, clear lines from the lead to
> each robot and back - no tangles. A finished envelope comes back to the lead, who ticks it off
> the checklist. Everyone relaxed and smiling; the scene is tidy and calm.

## If a result is off

- **Text in the image**: ask *"the same image, without any text or letters"*.
- **The style drifts**: attach the earlier image of the series and say *"keep exactly this style
  and these characters"*.
- **The background is not plain**: ask for *"the same image on a plain flat #F8F5F5
  background"*. A transparent PNG also works; the slide background is that colour.
