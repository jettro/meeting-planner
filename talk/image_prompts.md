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

---

# The speaker, as a comic character - `me-comic` (slide 2, 2026-11-19)

A less corporate introduction: the presenter drawn into the comic of slide 3, at work on what
the talk is about. The left side of the slide (name, role, logo) stays; the picture takes the
right side, and what the slide used to say moves to the speaker notes.

**How to make it**

1. A **new** ChatGPT conversation (not the robot one), so it does not mix the two prompts up.
2. **Attach** two or three recent photos of yourself - face clearly visible, different angles -
   and, as the style reference, `meeting-01-quick-meeting.jpg` and `meeting-06-build-a-team.jpg`
   from `talk/slides/img/`, and `robot-3.png` for the robot.
3. **Square, 1:1 (1024 x 1024)** - it fills the right half of the slide.
4. **Save it** as PNG; the slide uses `talk/slides/img/me-comic.jpg`, made the same way as the
   robot pictures (background set to exactly #F8F5F5, JPEG quality 86). Until then the slide shows
   a placeholder.

The prompt keeps out names and personal details on purpose: the photos are enough.

**The prompt**

> Draw the person from the attached photos as a comic character, in the exact hand-drawn style of
> the attached comic panels: bold ink outlines, warm slightly textured colours, gentle humour,
> the same kind of character drawing as the man in those panels - but with this person's face,
> hair, glasses (if any) and build, recognisable at a glance and friendly.
>
> The scene, square 1:1: the person stands at a workbench, sleeves rolled up, building a small
> team of robots - the robot from the attached robot image, in the same cream, teal and orange.
> One robot sits half-assembled on the bench; the person fits its head with one hand and holds a
> big magnifying glass in the other, looking through it with curiosity at a tiny robot that
> holds up a document - finding the right thing. A second robot, finished, stands beside the
> person and hands over a wrench, like an apprentice. On a small shelf behind: a stack of books,
> an open notebook with sketches of boxes and arrows, and a warm coffee mug. The person looks
> pleased and a little amused - a builder who enjoys sharing knowledge, not a corporate
> portrait.
>
> Plain, flat, very light warm off-white background (#F8F5F5) behind the scene, so it blends
> into a presentation slide. No text, no letters, no logos, no words anywhere in the image.

**If a result is off**

- **Not recognisable**: attach one more photo, and say *"keep the face closer to the photos:
  [what is off - the hair, the glasses, the beard]"*.
- **Too realistic, or too cartoonish**: *"exactly the drawing style of the attached comic panels"*.
- **Text appears**: *"the same image, without any text or letters"*.
