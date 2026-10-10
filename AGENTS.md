# Project Instructions

This file governs agents that work in this repository. The global rules in
`~/code/kai-global-agents-md/AGENTS.md` also apply. This file specialises them for this
project. It does not replace them.

## Primary Goal

Maintain the Hermes adaptation of the J-Space Cognition Suite. Build a Hermes-native
skill from the clean upstream checkout. Keep the fork in sync. Never change upstream.

## Read Order

1. This file.
2. `HERMES-COMPATIBILITY-REPORT.md`: why the adaptation exists and what changed.
3. `hermes/build_hermes_skill.py`: the builder, the single source of truth for the layout.
4. `hermes/sync.sh`: fetch, rebase, build, verify, deploy, and fork push.
5. `hermes/jspace_goal.py`: the goal-mechanism bridge (Option A wiring).
6. `j-space/`: the pristine upstream tree. Read-only.

## Current State

- Upstream remote `origin`: tag `v3.7.4` / SV1 (`b202312`). Treat it as read-only input.
- Work branch `hermes-adapt` on the fork remote. The fork is the single maintenance home.
- Build output `hermes/out/j-space/`: generated on every build. Never hand-edit it.
- Deployment: the Hermes skills directory holds a symlink to the build output.
- Automation: a nightly cron job runs `hermes/sync.sh` at 04:00. It fetches upstream,
  rebases `hermes-adapt`, rebuilds, verifies, refreshes the deployed symlink, and pushes
  the fork. It stays silent when nothing changed.
- Goal wiring: `hermes/jspace_goal.py` sets the Hermes session goal and adds the suite
  ship check as a quality gate. See `HERMES-COMPATIBILITY-REPORT.md` for the design.

## Operational Rules

1. Do not edit `hermes/out/` or the deployed skill copy. Both are generated. Edits there
   are overwritten on the next build.
2. Do not edit `j-space/`. Put every adaptation change under `hermes/` or in a root
   document (`AGENTS.md`, `HERMES-COMPATIBILITY-REPORT.md`).
3. After a change to the build layer, run the build and the verifier:
   `python3 hermes/build_hermes_skill.py` and
   `python3 hermes/out/j-space/scripts/verify_suite_hermes.py`. Both must pass clean.
4. Keep the generated skill description at or under 60 characters. Keep the frontmatter
   complete.
5. Never push to `origin`. Never open upstream issues or pull requests. The fork is the
   only publication target. `sync.sh` pushes it on every run, including the quick path.
6. Keep `hermes-adapt` commits in the `hermes: ...` subject style. One concern per
   commit. Write British English in Simplified Technical English.
7. Goal policy: a j-space task on Hermes runs under the Hermes goal mechanism. The
   bridge sets the goal and adds the ship-check quality gate. Keep the goal text in step
   with the controller goal.
8. New integration code lives in `hermes/`. When it must ship inside the skill,
   `build_hermes_skill.py` copies it into the build output.
9. Never commit secrets, personal data, or machine-specific absolute paths.

## Success Criteria

- `build_hermes_skill.py` prints `BUILT <n> files, upstream <sha>`.
- `verify_suite_hermes.py` prints `clean`.
- `sync.sh` is silent when the checkout is current. It reports changes or failures
  otherwise.
- Local `hermes-adapt` and `fork/hermes-adapt` match after a sync run.
- The deployed skill loads with all references and scripts present, readiness
  `available`.