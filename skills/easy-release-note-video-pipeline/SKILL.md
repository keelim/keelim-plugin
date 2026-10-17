---
name: easy-release-note-video-pipeline
description: Use when turning an official article or release note into an Easy Release Note short-form video through a distinct motion-graphics concept, bilingual or requested-language renders, Google Vids voiceover extraction and local mux, and private YouTube or Naver Clip draft upload with live verification.
capabilities:
  read_only: false
  local_write: true
  network_read: true
  external_write: true
  credentials: true
  hooks: false
---

# Easy Release Note Video Pipeline

## Overview

Use this skill for the complete, evidence-backed path from a verified release
note to finished short-form masters and platform drafts.

The default outcome is:

- a source-faithful package
- a visibly distinct motion-graphics concept
- English and Korean masters, unless the user requests one language
- Google Vids voiceover when requested
- locally extracted and muxed audio
- a private YouTube draft and/or Naver Clip draft only when explicitly requested
- local records updated with the live platform state

This skill owns the production handoff and publishing verification. Reuse an
existing repo-local script/package/rendering skill when one already creates the
source brief, manifests, or visual project.

## Modes

Infer the narrowest mode that completes the request:

1. `plan`: source brief, script, visual concept, metadata, and production notes.
2. `produce`: render, voiceover, mux, media validation, and local records.
3. `upload-draft`: upload the explicitly named master and save it private or as
   a draft on the requested platform.
4. `publish`: final public registration only when the user explicitly says to
   publish, register, or make public.

Do not treat `upload` as permission for `publish`.

## Required Inputs

Resolve these from the request and repository before doing production work:

- official source URL or user-provided source text
- product and update name
- target language or bilingual requirement
- target duration
- intended platform for each language
- final render directory and manifest/package paths
- whether Google Vids voiceover is requested
- whether the user authorized upload, draft saving, or public registration

For fast-moving updates, re-check the primary source before writing or
uploading metadata.

## Golden Path

### 1. Establish the source contract

- Prefer official release notes, docs, launch posts, or vendor announcements.
- Record access date, confirmed facts, caveats, rollout limits, and source URLs.
- Separate confirmed facts from interpretation.
- Never invent dates, availability, pricing, compatibility, or feature behavior.

### 2. Pass the visual-distinctness gate

Before implementation, inspect recent comparable episodes or templates.

Record:

- patterns that must not be repeated
- the new visual world
- layout grammar
- motion grammar
- typography behavior
- source treatment
- similarity risk

When the user asks for a completely different style, start a new visual
template. Do not inherit the previous palette, card system, scene framing, or
transition rhythm merely because the old template is available.

Deleting an old video or template is a separate destructive action. Only delete
the exact assets the user explicitly identifies.

### 3. Build the language masters

- Default to an English and Korean pair.
- Keep facts and caveats equivalent across languages, but write natural scripts.
- Keep narration, captions, on-screen text, metadata, and filenames
  language-consistent.
- Record a single-language exception when the user requests only one language.
- Use 1080 x 1920, 9:16, MP4/H.264, 30 fps, yuv420p, BT.709 SDR, and AAC 48 kHz
  stereo unless the repository specifies a stricter target.

Review at least three representative frames per language for safe areas, text
fit, visual identity, and source accuracy.

### 4. Create Google Vids voiceover when requested

Use the language-coded narration file as the script source.

Record:

- requested and actual voice
- language
- Google Vids URL
- Drive export URL
- exported file path
- audio duration

If Google Vids has no audio-only export:

1. Export the Vids project as MP4 to Google Drive.
2. Download the MP4.
3. Extract its audio locally to M4A/AAC at 48 kHz.
4. Mux that audio onto the high-quality local visual master.

Do not use the lower-quality Vids video track as the final visual when a better
local render exists.

### 5. Reconcile duration before mux

Probe both inputs before muxing.

- If narration is shorter, preserve the intended visual ending.
- If narration is longer, extend the final visual frame for the measured gap.
- Never use a shortest-stream option when it would truncate narration.
- Record the visual duration, audio duration, gap, and chosen treatment.

After muxing, verify the final stream dimensions, codecs, frame rate, audio
sample rate, duration, and file size. Run the repository validator when one
exists, such as `uv run ern validate <slug>`, and inspect the final master with
`ffprobe`.

### 6. Prepare truthful metadata

Use the source brief and language manifest as the metadata source of truth.

- Keep titles concise and factual.
- Use a small number of relevant hashtags.
- Keep source URLs and caveats.
- Set AI disclosure truthfully when AI voice or generated/transformed visuals
  are present.
- Optimize for clarity and search intent, but never promise a view count or use
  spam, fake engagement, or misleading claims.

### 7. Upload the English master to YouTube when authorized

Default safety settings:

- visibility: Private
- audience: not made for kids
- AI disclosure: Yes when applicable
- category: Science & Technology when appropriate

Use the final language-coded master, not an older preview. After saving, verify:

- title and description persisted
- `All changes saved`
- Checks result
- actual selected visibility
- restrictions
- the final row in YouTube Studio's Shorts tab
- final Shorts URL

If page header, toast, radio selection, and list row disagree, reopen Details
and verify the selected values before updating local records.

### 8. Upload the Korean master to Naver Clip when authorized

Use the final Korean vertical MP4.

Before input, keep the Clip description at or below 300 characters so hashtags
are not silently truncated.

Default draft settings:

- category: `테크 > 인터넷, AI` when appropriate
- AI 활용: ON when applicable
- 전체 공개: OFF
- playback country: `전세계`
- comments: `허용`
- information tags and content links: empty unless genuinely relevant

Click `임시저장`, not `등록`, unless public registration was explicitly
authorized.

After saving, verify:

- `임시 저장 되었습니다` confirmation
- content-list row duration and description
- row status `초안`
- draft URL
- account and handle

Do not report completion from the edit screen alone.

### 9. Persist the evidence

Follow the repository's existing schema rather than inventing a second manifest
format. Record at minimum:

- uploaded filename
- final master path and duration
- platform draft or video URL
- title or description used
- category, audience, AI-use, comments, and visibility
- visible save/check/list-row evidence
- timestamp and timezone
- `registration_performed: false` when stopped at draft

Update both the machine-readable episode manifest and human-readable package
verification notes when those artifacts exist.

## Completion Gates

Production is complete only when:

- the final master exists
- media validation passes
- narration is not truncated
- visual frames are reviewed
- local manifests point to the current final master

An upload-draft task is complete only when the platform's saved list confirms
the draft/private state. A public task is complete only when the live platform
confirms publication and returns a final URL.

## Failure Handling

- File chooser blocked: use an authorized cloud picker or Computer Use for the
  native dialog.
- Vids offers video only: export MP4, extract audio, and mux locally.
- Voiceover exceeds the visual: extend the final frame; do not cut speech.
- Description exceeds a platform limit: shorten it before saving; do not leave a
  broken hashtag.
- Upload or encoding limit appears: record the exact visible limit and stop.
- Visibility is unexpectedly public: switch it back to private before saving.
- UI state is ambiguous: reopen the draft and verify the actual controls.

## Final Report

Report only the evidence the user needs:

- final master path
- duration and validation result
- voice and mux treatment
- platform and language
- saved state
- draft/private URL
- whether final publish or registration was intentionally skipped
