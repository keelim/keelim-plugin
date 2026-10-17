---
name: eli5
description: Explain a topic for a beginner as a standalone visual HTML page, using ASD-STE100-inspired clarity principles while preserving necessary conditions and evidence. Use for `/eli5`, a simple visual explanation, or an ASD-STE100-inspired HTML explainer.
capabilities:
  read_only: false
  local_write: true
  external_write: false
  network_read: false
  credentials: false
  hooks: false
---

# ELI5

Turn `$ARGUMENTS` into one self-contained HTML explainer for a beginner.
Apply selected ASD-STE100 Simplified Technical English principles to the
explanation. Prefer precise, clear language over a childlike voice or analogy.
This skill is not a complete STE checker and does not certify compliance.

## Workflow

1. Identify the main idea and the reader's required knowledge. Use the supplied
   source to retain prerequisites, conditions, exceptions, risks, and evidence.
   Mark missing facts or uncertainty; do not invent details to simplify the story.
2. Create a standalone `.html` file in the current workspace (or the output
   path the user gives). Use inline CSS and inline SVG/CSS illustrations so it
   opens without internet access or extra files.
3. Keep the large-type layout: a clear title, three to five visual steps,
   and a short “Now you know!” ending. Give each step one short main sentence.
   Put necessary conditions or warnings beside the relevant step in short notes;
   do not remove them to meet a visual or length target.
4. Use labeled diagrams to show actual components and actions. Define necessary
   technical terms in plain language. Use a comparison only if it helps, identify
   it as an analogy, and explain any limit that could mislead the reader.
5. Keep the original meaning, quantities, units, sequence, and strength of claims.
   Distinguish requirements from options and assumptions from established facts.
   Avoid unnecessary jargon, dense paragraphs, tables, and external images.
6. Open or inspect the result after creating it. Check that it is readable on
   a narrow screen, visual meaning remains clear without color alone, and the
   file has no external requests. Compare the explanation with the source:
   every essential condition, exception, risk, and supporting fact must remain.

## Writing rules

- Use short sentences with one topic. In procedures, normally give one
  instruction per sentence. Put a condition first when the reader must know it
  before acting, then state who does what.
- Use active voice and direct verbs. Do not invent an actor if the source does
  not identify one. Keep an unavoidable passive description unambiguous.
- Use one consistent term for each concept. Do not rotate synonyms for variety.
  Define a necessary acronym or technical term at first use; keep official names.
- Write for the user's requested language. For Korean, adapt the clarity
  principles; do not label the result as formally compliant or certified STE.
  English compliance also requires the full writing rules and controlled
  vocabulary, including approved meanings and applicable technical terms.
- Keep the main explanation scannable in about one minute when possible.
  Accuracy and necessary detail take priority over brevity. Clearer wording
  does not by itself prove improved factual accuracy or remove uncertainty.

Source basis: [official ASD-STE100 FAQ](https://www.asd-ste100.org/STE_faq.html)
and [Issue 9](https://www.asd-ste100.org/assets/files/ASD-STE100_ISSUE9.pdf),
especially the rules on words, verbs, sentences, procedures, and descriptions.
These are reference links, not required external resources for the generated
HTML. Paraphrase relevant guidance; do not reproduce the dictionary or long
passages from the standard.

## Completion

Return the created HTML file path and one sentence saying what it explains.
