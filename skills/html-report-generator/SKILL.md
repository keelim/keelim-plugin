---
name: html-report-generator
description: Generate secure offline HTML reports from generic block-model JSON using a reusable template, stdlib Python renderer, and offline/security validation. Use when the user wants a local standalone HTML report, a reusable HTML report foundation, or validation that a generated report does not use CDNs or external communication.
---

# HTML Report Generator

## Overview

Use this skill to turn generic report JSON into a standalone offline HTML report. The skill is intentionally reusable: future report workflows can produce the same block-model JSON and let this renderer handle HTML layout, escaping, and offline validation.

The generated report must be local-only. Do not use CDNs, remote fonts, remote images, external scripts, external stylesheets, iframes, analytics, or browser network APIs.

## Workflow

1. Shape report data as the generic block model described in `references/report-schema.md`.
2. Render HTML with `scripts/render_html_report.py`.
3. Validate the generated HTML before presenting it. Use `--validate` during rendering or `--check-html` for an existing file.
4. If validation fails, fix the input/template/renderer rather than sharing the HTML.

## Quick Start

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/html-report-generator/scripts/render_html_report.py \
  --input skills/html-report-generator/examples/demo-report.json.sample \
  --output /tmp/html-report-demo.html \
  --validate
```

Validate an existing report:

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/html-report-generator/scripts/render_html_report.py --check-html /tmp/html-report-demo.html
```

## Input Model

Use a report-level object with generic fields only. Prefer `title`, `subtitle`, `summary`, `metadata`, `metrics`, `sections`, `tables`, `findings`, `links`, and `appendix`. Keep domain-specific data normalization in the calling skill, then pass this renderer the generic report object.

## Offline HTML Contract

Generated HTML must satisfy:

- No `http://` or `https://` URLs.
- No CDN, remote image, remote font, external script, external stylesheet, iframe, analytics, beacon, or network API.
- No `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, or `sendBeacon`.
- A restrictive Content Security Policy with `connect-src 'none'`.
- Every rendered value is escaped unless it is renderer-owned static markup.

Remote URLs found in report text are replaced with `[remote-url-omitted]` before rendering. If unsafe markup is introduced through the template or a future renderer change, validation must fail.

## Verification

```bash
uv --cache-dir .skillopt/uv-cache run --python 3.12 python skills/html-report-generator/scripts/test_render_html_report.py
env PYTHONPYCACHEPREFIX=.omx/pycache uv --cache-dir .skillopt/uv-cache run --python 3.12 python -m py_compile skills/html-report-generator/scripts/render_html_report.py skills/html-report-generator/scripts/test_render_html_report.py
uv --cache-dir .skillopt/uv-cache run --python 3.12 --with pyyaml python /Users/keelim/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/html-report-generator
git diff --check
```

## Review Answer Guardrails

When answering plugin skill review or promotion questions about this skill, keep the response anchored to `html-report-generator` and the concrete maintenance surface being reviewed.

- For SKILL.md improvement recommendations, explicitly name `html-report-generator` and `SKILL.md`, keep the recommendation concise, and preserve the generic block-model workflow rather than narrowing it to one report domain.
- For validation questions, name the relevant validation commands or checks from the Verification section, including renderer tests, `py_compile`, skill quick validation, and `git diff --check` when applicable.
- For promotion or packaging questions, state that `html-report-generator` must preserve its bundled `references/`, `scripts/`, and `assets/` resources, especially `references/report-schema.md`, `scripts/render_html_report.py`, `scripts/test_render_html_report.py`, and `assets/report-template.html`.
