#!/usr/bin/env node
// W1-plugin-01 — Generated skill catalog + install matrix for keelim-plugin.
//
// Parses skills/<name>/SKILL.md frontmatter (name, description), detects optional
// Codex metadata (agents/openai.yaml), and renders a catalog (CATALOG.md +
// catalog.json) with an install-command matrix (Vercel skills CLI vs manual symlink).
//
// Usage:
//   node scripts/gen-catalog.mjs           # (re)generate CATALOG.md + catalog.json, exit 0
//   node scripts/gen-catalog.mjs --check   # validate folder<->README parity + metadata, exit 1 on drift
//
// --check fails (exit 1) when ANY of:
//   - a skills/<name> folder is missing from the README "Current skills" list (or vice versa)
//   - a SKILL.md lacks frontmatter name or description
//   - a SKILL.md frontmatter `name` does not match its folder name

import { readFileSync, existsSync, writeFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS_DIR = join(REPO_ROOT, 'skills');
const SKILL_SOURCE = 'keelim/keelim-plugin';

/** @typedef {{ folder: string, name: string, description: string, hasCodexMeta: boolean, errors: string[] }} SkillEntry */

/**
 * @param {string} value
 * @returns {string | boolean}
 */
function parseScalar(value) {
  const trimmed = value.trim();
  if (trimmed === 'true' || trimmed === 'True') return true;
  if (trimmed === 'false' || trimmed === 'False') return false;
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

/**
 * Parse the small mapping-only YAML subset used by SKILL frontmatter and
 * agents/openai.yaml. The Python validator uses PyYAML when available; this
 * keeps the catalog generator dependency-free while still validating content.
 * @param {string} text
 * @param {string} source
 * @returns {Record<string, any>}
 */
function parseSimpleYaml(text, source) {
  const root = {};
  const stack = [{ indent: -1, value: root }];
  const lines = text.split(/\r?\n/);
  for (let i = 0; i < lines.length; i += 1) {
    const raw = lines[i];
    if (!raw.trim() || raw.trimStart().startsWith('#')) continue;
    if (raw.startsWith('\t')) throw new Error(`${source}:${i + 1}: tabs are not supported`);
    const indent = raw.length - raw.trimStart().length;
    const stripped = raw.trim();
    const colon = stripped.indexOf(':');
    if (colon < 0) throw new Error(`${source}:${i + 1}: expected key: value`);
    const key = stripped.slice(0, colon).trim();
    const rawValue = stripped.slice(colon + 1).trim();
    if (!key) throw new Error(`${source}:${i + 1}: empty key`);
    while (stack.length > 0 && indent <= stack[stack.length - 1].indent) stack.pop();
    if (stack.length === 0) throw new Error(`${source}:${i + 1}: invalid indentation`);
    const parent = stack[stack.length - 1].value;
    if (rawValue) {
      parent[key] = parseScalar(rawValue);
      continue;
    }
    const child = {};
    parent[key] = child;
    stack.push({ indent, value: child });
  }
  return root;
}

/**
 * Extract YAML frontmatter name/description from a SKILL.md body.
 * @param {string} text
 * @param {string} source
 * @returns {{ name: string | null, description: string | null }}
 */
function parseFrontmatter(text, source) {
  const m = text.match(/^---\s*\n([\s\S]*?)\n---/);
  if (!m) return { name: null, description: null };
  const values = parseSimpleYaml(m[1], source);
  return {
    name: typeof values.name === 'string' ? values.name : null,
    description: typeof values.description === 'string' ? values.description : null
  };
}

/**
 * @param {unknown} value
 * @returns {boolean}
 */
function isNonEmptyString(value) {
  return typeof value === 'string' && value.trim().length > 0;
}

/**
 * @param {string} folder
 * @returns {string[]}
 */
function validateCodexMeta(folder) {
  const metaPath = join(SKILLS_DIR, folder, 'agents', 'openai.yaml');
  if (!existsSync(metaPath)) return [];
  const errors = [];
  let meta;
  try {
    meta = parseSimpleYaml(readFileSync(metaPath, 'utf8'), metaPath);
  } catch (error) {
    return [`agents/openai.yaml parse error: ${error.message}`];
  }
  if (!meta.interface || typeof meta.interface !== 'object') {
    return ['agents/openai.yaml missing interface mapping'];
  }
  for (const field of ['display_name', 'short_description', 'default_prompt']) {
    if (!isNonEmptyString(meta.interface[field])) {
      errors.push(`agents/openai.yaml interface.${field} must be a non-empty string`);
    }
  }
  if (meta.policy !== undefined) {
    if (!meta.policy || typeof meta.policy !== 'object') {
      errors.push('agents/openai.yaml policy must be a mapping when present');
    } else if (
      meta.policy.allow_implicit_invocation !== undefined &&
      typeof meta.policy.allow_implicit_invocation !== 'boolean'
    ) {
      errors.push('agents/openai.yaml policy.allow_implicit_invocation must be boolean');
    }
  }
  return errors;
}

/**
 * Read all skills with their metadata.
 * @returns {SkillEntry[]}
 */
function readSkills() {
  const folders = readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
  return folders.map((folder) => {
    const errors = [];
    const skillPath = join(SKILLS_DIR, folder, 'SKILL.md');
    let name = null;
    let description = null;
    if (!existsSync(skillPath)) {
      errors.push('missing SKILL.md');
    } else {
      try {
        ({ name, description } = parseFrontmatter(readFileSync(skillPath, 'utf8'), skillPath));
      } catch (error) {
        errors.push(`frontmatter parse error: ${error.message}`);
      }
      if (!name) errors.push('frontmatter missing `name`');
      if (!description) errors.push('frontmatter missing `description`');
      if (name && name !== folder) errors.push(`frontmatter name "${name}" != folder "${folder}"`);
    }
    const hasCodexMeta = existsSync(join(SKILLS_DIR, folder, 'agents', 'openai.yaml'));
    errors.push(...validateCodexMeta(folder));
    return { folder, name: name || folder, description: description || '', hasCodexMeta, errors };
  });
}

/**
 * Parse the README "Current skills" section for declared skill names.
 * @returns {Set<string>}
 */
function parseReadmeSkills() {
  const readme = join(REPO_ROOT, 'README.md');
  if (!existsSync(readme)) return new Set();
  const text = readFileSync(readme, 'utf8');
  const section = text.split(/^##\s+Current skills\s*$/m)[1];
  if (!section) return new Set();
  const body = section.split(/^##\s+/m)[0];
  const names = new Set();
  const re = /^-\s+`([^`]+)`/gm;
  let m;
  while ((m = re.exec(body)) !== null) names.add(m[1]);
  return names;
}

/**
 * @param {SkillEntry} s
 * @returns {{ cli: string, symlinkCodex: string, symlinkClaude: string }}
 */
function installCommands(s) {
  return {
    cli: `npx skills add ${SKILL_SOURCE} --skill ${s.folder} -a codex -a claude-code -y --copy`,
    symlinkCodex: `ln -s ${join(REPO_ROOT, 'skills', s.folder)} ~/.agents/skills/${s.folder}`,
    symlinkClaude: `ln -s ${join(REPO_ROOT, 'skills', s.folder)} ~/.claude/skills/${s.folder}`
  };
}

/**
 * @param {SkillEntry[]} skills
 * @returns {string}
 */
function renderMarkdown(skills) {
  const lines = [
    '# keelim-plugin Skill Catalog',
    '',
    `_Generated by \`scripts/gen-catalog.mjs\` - do not edit by hand. ${skills.length} skills._`,
    '',
    '| Skill | Codex meta | Description |',
    '| --- | --- | --- |'
  ];
  for (const s of skills) {
    const desc = s.description.replace(/\|/g, '\\|');
    lines.push(`| \`${s.folder}\` | ${s.hasCodexMeta ? 'yes' : 'no'} | ${desc} |`);
  }
  lines.push('', '## Install matrix', '');
  for (const s of skills) {
    const cmd = installCommands(s);
    lines.push(
      `### ${s.folder}`,
      '',
      '```bash',
      `# Vercel skills CLI (Codex + Claude)`,
      cmd.cli,
      '',
      `# Manual symlink`,
      cmd.symlinkCodex,
      cmd.symlinkClaude,
      '```',
      ''
    );
  }
  return `${lines.join('\n')}\n`;
}

/**
 * @returns {string}
 */
function catalogGeneratedAt() {
  const epoch = process.env.SOURCE_DATE_EPOCH;
  if (epoch) {
    const seconds = Number.parseInt(epoch, 10);
    if (Number.isFinite(seconds)) return new Date(seconds * 1000).toISOString();
  }
  return '1970-01-01T00:00:00.000Z';
}

/**
 * @param {SkillEntry[]} skills
 * @returns {{ generatedAt: string, source: string, count: number, skills: object[] }}
 */
function buildCatalogJson(skills) {
  return {
    generatedAt: catalogGeneratedAt(),
    source: SKILL_SOURCE,
    count: skills.length,
    skills: skills.map((s) => ({
      name: s.folder,
      description: s.description,
      hasCodexMeta: s.hasCodexMeta,
      install: installCommands(s)
    }))
  };
}

function main() {
  const check = process.argv.includes('--check');
  const skills = readSkills();
  const readmeNames = parseReadmeSkills();
  const folderNames = new Set(skills.map((s) => s.folder));

  const missingFromReadme = [...folderNames].filter((n) => !readmeNames.has(n));
  const missingFolders = [...readmeNames].filter((n) => !folderNames.has(n));
  const metaErrors = skills.filter((s) => s.errors.length > 0);

  const catalogJsonText = `${JSON.stringify(buildCatalogJson(skills), null, 2)}\n`;
  const catalogMarkdown = renderMarkdown(skills);
  const catalogJsonPath = join(REPO_ROOT, 'catalog.json');
  const catalogMarkdownPath = join(REPO_ROOT, 'CATALOG.md');

  if (check) {
    let failed = false;
    if (missingFromReadme.length) {
      console.error(`[gen-catalog] DRIFT: folders not listed in README "Current skills": ${missingFromReadme.join(', ')}`);
      failed = true;
    }
    if (missingFolders.length) {
      console.error(`[gen-catalog] DRIFT: README lists skills with no folder: ${missingFolders.join(', ')}`);
      failed = true;
    }
    for (const s of metaErrors) {
      console.error(`[gen-catalog] META: ${s.folder}: ${s.errors.join('; ')}`);
      failed = true;
    }
    if (!existsSync(catalogJsonPath) || readFileSync(catalogJsonPath, 'utf8') !== catalogJsonText) {
      console.error('[gen-catalog] DRIFT: catalog.json is not up to date');
      failed = true;
    }
    if (!existsSync(catalogMarkdownPath) || readFileSync(catalogMarkdownPath, 'utf8') !== catalogMarkdown) {
      console.error('[gen-catalog] DRIFT: CATALOG.md is not up to date');
      failed = true;
    }
    if (failed) process.exit(1);
    console.log('[gen-catalog] --check OK (README parity + metadata + generated files valid)');
    return;
  }

  writeFileSync(catalogJsonPath, catalogJsonText, 'utf8');
  writeFileSync(catalogMarkdownPath, catalogMarkdown, 'utf8');
  console.log(`[gen-catalog] ${skills.length} skills -> CATALOG.md, catalog.json`);
}

main();
