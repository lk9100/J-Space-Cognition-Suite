# J-Space Cognition Suite — Hermes Agent Compatibility Report

**Date:** 2026-09-21 · **Upstream:** v3.7.4 / SV1 (commit `b202312`) · **Host:** Hermes Agent v0.21.3
**Author:** @lk9100 (report + adaptation layer, Apache-2.0)

## Summary

The suite integrates with Hermes Agent functionally but not natively. A full integration
audit (using the suite's own protocol against itself: ledger, pass gate, ship checks)
found **three concrete blockers** for official Hermes installs and routing, plus smaller
conformance notes. We built and deployed a local adaptation layer (`hermes/` directory,
this branch) that generates a Hermes-native skill layout from a clean upstream checkout
and keeps it in sync. This report documents the findings and proposes upstream changes.

## Findings

### 1. `modules/` is not a Hermes support directory (blocker)

Hermes Agent treats only `references/`, `templates/`, `assets/`, `scripts/`, and
`examples/` as skill support directories:

- `agent/skill_utils.SKILL_SUPPORT_DIRS = frozenset(("references", "templates", "assets", "scripts"))`
- The official GitHub/URL skill installers copy `SKILL.md` **plus the exact local files
  it references under those whitelisted directories** — unreferenced files are not copied.
- `skill_view` `linked_files` uses the same whitelist.

**Consequence:** an official Hermes install (or any re-install via the Hermes skill
installer) drops **all 13 module files**, leaving a broken skill. Our local install works
only because it was placed into the skills directory manually.

**Proposal:** rename `modules/` → `references/` (the merged layout is fully supported in
Hermes; we verified a mechanical link rewrite preserves every internal reference), or ship
a host-layout variant alongside the upstream layout.

### 2. Description length defeats routing (blocker on most surfaces)

`description` is 262 characters. Hermes indexes skill descriptions in the system prompt
at a hard 60-character budget (`SKILL_PROMPT_DESC_LIMIT`, `desc[:57] + "..."`):

- CLI / TUI / gateway surfaces show: `Operate a selective workspace for complex reasoning, long t...`
- The trigger signal ("Use when work requires durable state, evidence, cross-file
  consistency...") is lost, so the model may fail to route to this skill at all.
- The desktop surface currently shows the full description, so behaviour differs by surface.

**Proposal:** a ≤60-character description with the trigger first, e.g.:
`Reasoning workspace: ledger, gates, ship checks. Long tasks.`
(the full trigger text belongs in a `## When to Use` section, which is also the house
standard for the section).

### 3. Frontmatter lacks host metadata

Only `name` and `description` are present. Common host conventions (agentskills.io
standard, followed by Hermes bundled skills) expect:

```yaml
version: 3.7.4
author: Tiger3807861189 (Upstream)
license: Apache-2.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [reasoning, workspace, long-horizon, verification, ledger]
```

These enable hub categorization, provenance tracing, platform gating, and (in Hermes)
conditional activation such as `requires_toolsets: [terminal]`.

### 4. Controller invocation expects host-specific resolution

Commands use `<python-command> <skill-root>/scripts/jspace.py ...`. Hermes substitutes a
`${HERMES_SKILL_DIR}` template token in SKILL.md bodies at load time and surfaces the skill
directory in the activation message — using it removes an inference step and a path
ambiguity class.

### 5. No `## When to Use` / counter-trigger section

The house authoring standard (and the skill's own philosophy of selectivity) calls for an
explicit trigger + counter-trigger block. Right now the fast-pass exemption ("short tasks:
it has nothing for you") lives in prose and is easy to miss, which contributes to
overloading on quick tasks.

## What is already good (credit)

- v3.7+ `--root TASK_DIRECTORY` (controller) already solves ledger placement — the
  `.jspace/` state can stay with the task instead of the session working directory.
- The suite's structure is entirely compatible with progressive-disclosure skill loading
  (entry + on-demand modules).
- The scientific premise is real and traceable: Gurnee et al., *Verbalizable
  Representations Form a Global Workspace in Language Models* (Anthropic, 2026-07,
  arXiv:2607.15495 / transformer-circuits workspace post); the Jacobian lens and the five
  functional properties are quoted faithfully.
- Standard-library-only controllers, no external dependencies; unit tests are solid.

## Our adaptation (this branch)

- `hermes/build_hermes_skill.py` — idempotent builder producing a Hermes-native layout:
  - `references/` = upstream modules (13) + references (7), merged, links rewritten
    (`modules/X` → `references/X`, `../modules/X` / `../references/X` → same-directory)
  - `SKILL.md` with ≤60-char description, full frontmatter, `## When to Use` +
    `## Hermes Notes` (ledger placement, `todo` tool overlap, `${HERMES_SKILL_DIR}`)
  - `scripts/` verbatim + `verify_suite_hermes.py` (verifies the generated layout:
    frontmatter budget, merged manifest, no stale upstream link forms, controller presence)
  - `LICENSE` / `CITATION.cff` / `THIRD_PARTY_NOTICES.md` copied
- `hermes/sync.sh` — cron entry point: fetch upstream → rebase the adaptation branch →
  rebuild → verify → (via symlink) refresh the deployed skill; silent when unchanged,
  summary + error delivery otherwise.

Deployed as `~/.hermes/skills/j-space` → symlink to the build output, refreshed nightly.

## Ask

1. Consider accepting the merged layout (rename `modules/` → `references/`) or documenting
   a host-variant path — we will gladly contribute the builder/rewrite as a PR in either case.
2. Consider the ≤60-char description + `## When to Use`; the full text already exists in
   the body.
3. Consider adding a Hermes section to `references/host-integration.md` (it currently
   documents a portable contract only) — the bridge/`--root` contract maps cleanly to
   Hermes tool boundaries.

All adaptation code is Apache-2.0, same as upstream. Happy to open a PR against the
upstream repository if any of the above is welcome.
