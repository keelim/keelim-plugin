---
name: tech-post-maker
description: Use when writing first-person technical posts in a personal engineer voice, especially build logs, case studies, workflow write-ups, or series posts about tools, systems, and engineering habits.
---

# Tech Post Maker

## Overview
Use this skill to turn real engineering work into a strong technical post written in a personal engineer voice.

The target tone is calm, practical, and technically credible. It should sound like an engineer explaining what actually happened, not a founder pitch or a marketing campaign.

## When to Use
Use this skill for:
- Medium posts based on real implementation work
- build logs
- case studies
- workflow write-ups
- tooling notes
- architecture reflections
- series posts such as "how I built my AI harness"
- polishing an existing draft so it sounds more like a personal engineer and less like generic AI output

Do not use this skill for:
- product launch copy
- landing pages
- promotional threads
- API reference docs
- academic papers

## Core Voice
Always prefer:
- first-person singular (`I`)
- short to medium paragraphs
- specific observations over big claims
- practical framing over abstract thought leadership
- technical credibility without showing off
- understated confidence

Avoid:
- self-brand-heavy writing
- corporate or founder-style messaging
- hype like "AI changed everything"
- exaggerated personal storytelling
- generic advice disconnected from real work

If a personal nickname appears in repo names or commands, keep it in factual places only. The narrative voice should stay centered on `I`, not on personal branding.

## Default Structure
For long-form posts, use this structure unless there is a strong reason not to:

1. **Hook**
   - Start from a real repeated task, incident, workflow, or technical tension
   - Prefer concrete work over abstract industry commentary

2. **Why it mattered**
   - Explain why the problem was worth solving
   - Good themes: repetition, friction, trust, maintenance, operational drag

3. **What I built**
   - Introduce the tool, workflow, pattern, or change
   - Keep this section clear before diving into details

4. **How it works**
   - Explain the structure, modes, constraints, and key decisions
   - Include code or commands only when they serve as evidence

5. **What I learned**
   - Extract 3 to 5 grounded lessons
   - Keep them specific to the work, not generic productivity advice

6. **Why it fits into a larger system**
   - Use this especially for series writing
   - Show how the current piece connects to a broader engineering approach

7. **Closing**
   - End by widening slightly from the specific story
   - Leave the reader with a pattern they can notice in their own work

## Modes

### 1. outline
Use this when the raw material exists but the article is not structured yet.

Produce:
- 3 to 5 title options
- optional subtitle
- article angle in one sentence
- section-by-section outline
- recommended reader takeaway

### 2. draft
Use this when there is enough material to write the full post.

Produce:
- title
- subtitle if useful
- full Medium-ready draft
- optional series footer

### 3. polish
Use this when a draft already exists.

Improve:
- tone
- pacing
- transitions
- paragraph length
- clarity
- strength of hook and closing

Keep the original technical meaning intact.

### 4. series
Use this when the post belongs to a larger sequence.

Produce:
- current post title and positioning
- a one-line series framing
- next-post title ideas
- a short outline for the next post

## Input Checklist
Before drafting, get clear on:
- What real work happened?
- What is the one main takeaway?
- Who is the reader?
- Is this a standalone post or part of a series?
- Should the piece feel more like a story, a tutorial, or a hybrid?

If not specified, default to:
- **reader:** technical but broad
- **shape:** hybrid
- **voice:** personal engineer

## Writing Rules
- Open with the work itself when possible
- Prefer one strong idea per article
- Use repo names, commands, and files as proof, not decoration
- Keep code blocks selective and relevant
- Let the reader feel that the workflow is real and lived-in
- If the article includes lessons, make them earned by the story

## Good Patterns
Good opening:
> Every release followed the same pattern.
>
> Update the version code. Run a build. Fix the release PR. Trigger deployment.

Good insight framing:
> None of these steps were difficult. That was exactly the problem.

Good series bridge:
> This solved one part of the problem. The next question was how to package it so it could actually be reused.

## Common Mistakes
- Starting too broad instead of starting from real work
- Explaining the entire industry before the actual project
- Sounding promotional instead of reflective
- Giving lessons that were not supported by the story
- Overusing commands and code blocks until the article reads like documentation
- Making the voice too polished and losing the sense that an actual engineer wrote it

## Output Checklist
Before finalizing, make sure the post:
- sounds like one person reflecting on real work
- has one clear central takeaway
- uses specific evidence from the implementation
- avoids unnecessary hype
- leaves room for a next step if it is part of a series
