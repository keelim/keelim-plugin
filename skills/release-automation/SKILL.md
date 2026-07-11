---
name: release-automation
description: Use when preparing a date-based Android release in a repo that has gradle/libs.versions.toml with versionCode, a develop-to-main release flow, and .github/workflows/app_deploy.yml. Covers dry-run inspection, explicit-confirmation updates, release PR alignment, and app_deploy dispatch.
capabilities:
  read_only: false
  local_write: true
  network_read: true
  external_write: true
  credentials: true
  hooks: false
---

# Release Automation

## Overview
Use this skill for the recurring release flow that updates `versionCode` to today's date, verifies the build, syncs the `develop -> main` release PR, and triggers deployment.

Default to `dry-run` unless the user explicitly asks for `confirm` or `execute`.
The `confirm` and `execute` modes may mutate local files, git history, GitHub PRs,
and GitHub Actions state, so require clear user approval before each external
write unless the user has already approved full execute mode.

## Skill review response guardrails
When answering review or promotion tasks about this skill, explicitly name `release-automation` and `SKILL.md` in the response, then address the requested maintenance concern directly. If asked for validation, use the word `validate` or `validation` and name the concrete checks. If asked about bundled resources, state whether `references/`, `scripts/`, or `assets/` exist instead of implying missing resources are required.

## Repo defaults
- Working branch: `develop`
- Base branch: `main`
- Version file: `gradle/libs.versions.toml`
- Version key: `versionCode`
- Default verification: `./gradlew :composeApp:assemble`
- Workflow: `.github/workflows/app_deploy.yml`
- Workflow dispatch name: `app_deploy.yml`
- Release label: `release`
- Assignee: `keelim`

## Modes

### 1. dry-run
Read-only inspection only. Do not modify files, commits, PRs, or workflows.

Run these checks and report them with `Would ...` wording:

```bash
date +%Y%m%d
rg -n '^versionCode = ' gradle/libs.versions.toml
git branch --show-current
gh pr list --state all --base main --limit 10 --json number,title,headRefName,baseRefName,assignees,labels,body,createdAt
gh pr list --state open --base main --head develop --json number,title,body,labels,assignees,url
gh workflow view app_deploy.yml
```

Then summarize like:
- Would update `gradle/libs.versions.toml` to today's date
- Would run `./gradlew :composeApp:assemble`
- Would update or create `develop -> main` PR
- Would dispatch `app_deploy.yml` on `develop`

### 2. confirm
Same flow as execute, but stop before each risky write:
- file update
- git commit
- git push
- PR edit/create
- workflow dispatch

Use short confirmations such as:
- `Update versionCode to 20260308?`
- `Commit and push develop?`
- `Edit release PR metadata?`
- `Dispatch app_deploy.yml on develop?`

### 3. execute
Perform the full release flow end to end only after the user explicitly requests
execute mode for the target repo and approves the external mutations in this
workflow.

## Execute flow

### Step 1: calculate today's release version
```bash
date +%Y%m%d
```

### Step 2: update versionCode
```bash
sed -i '' 's/^versionCode = .*/versionCode = "YYYYMMDD"/' gradle/libs.versions.toml
```

If GNU `sed` is in use, adapt the in-place flag accordingly.

### Step 3: verify before any git/GitHub mutation
```bash
./gradlew :composeApp:assemble
```

If verification fails, stop immediately.

### Step 4: commit and push
```bash
git add gradle/libs.versions.toml
git commit -m "chore: update versionCode to YYYYMMDD"
git push origin develop
```

### Step 5: inspect recent release PR conventions
```bash
gh pr list --state all --base main --limit 10 --json number,title,headRefName,baseRefName,assignees,labels,body,createdAt
```

Prefer the latest `develop -> main` release PR pattern for:
- title format
- body structure
- release label
- assignee

### Step 6: update or create the release PR
Check whether an open `develop -> main` PR already exists:

```bash
gh pr list --state open --base main --head develop --json number,title,body,labels,assignees,url
```

If one exists, update it:

```bash
gh pr edit <number> \
  --title "release/YYMMDD" \
  --body $'## Summary\n- update release versionCode to YYYYMMDD\n- dispatch app_deploy workflow on develop\n\n## Verification\n- ./gradlew :composeApp:assemble' \
  --add-label release \
  --add-assignee keelim
```

If none exists, create one:

```bash
gh pr create \
  --base main \
  --head develop \
  --title "release/YYMMDD" \
  --body $'## Summary\n- update release versionCode to YYYYMMDD\n- dispatch app_deploy workflow on develop\n\n## Verification\n- ./gradlew :composeApp:assemble'
```

After creation, add the label and assignee if needed.

### Step 7: dispatch deployment workflow
```bash
gh workflow run app_deploy.yml --ref develop
```

### Step 8: capture run status
```bash
gh run list --workflow app_deploy.yml --branch develop --limit 1
gh run view <run-id> --json status,conclusion,url,workflowName,headBranch,event,createdAt
```

## Report format
For `dry-run`, end with `Would ...` statements and omit commit hashes, PR URLs,
or workflow run URLs unless they already existed before the run.

For `confirm` or `execute`, end with:
- release version used
- verification command and result
- commit hash
- PR number and URL
- workflow run URL
- current workflow status

## Common mistakes
- Updating `versionCode` before confirming the active branch is `develop`
- Continuing after a failed build
- Creating duplicate release PRs when an open `develop -> main` PR already exists
- Forgetting to reapply label/assignee when editing PR metadata
- Claiming deployment started without checking the Actions run URL

## Quick reference
```bash
# release date
date +%Y%m%d

# verify
./gradlew :composeApp:assemble

# open release PR
gh pr list --state open --base main --head develop

# dispatch deploy
gh workflow run app_deploy.yml --ref develop
```
