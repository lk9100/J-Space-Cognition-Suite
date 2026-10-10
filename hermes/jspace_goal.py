#!/usr/bin/env python3
"""jspace_goal: bridge from the J-Space skill to the Hermes goal mechanism.

On Hermes the standing goal and the keep-working loop belong to the host (`/goal`).
This bridge writes the same per-session goal state that `/goal` writes, so the host
judges the goal after every turn. It also adds the suite ship check
(`control.py check --stage ship`) as a Hermes quality gate: the host runs the gate
before judging, and a failing gate short-circuits the judge.

Usage (run from an agent terminal; the session key comes from HERMES_SESSION_KEY):

  jspace_goal.py status [--json]
  jspace_goal.py set --goal TEXT [--outcome ...] [--verification ...]
                 [--constraints ...] [--boundaries ...] [--stop-when ...]
                 [--max-turns N] [--if-absent]
  jspace_goal.py gate add --ship-check --task DIR [--timeout S] [--max-retries N]
  jspace_goal.py gate add --command CMD [--timeout S] [--max-retries N]
  jspace_goal.py gate list | gate remove N | gate clear
  jspace_goal.py subgoal add TEXT | subgoal list | subgoal clear
  jspace_goal.py pause | resume | clear

Exit codes: 0 = success. 2 = usage or environment error. 3 = the session store is
unreachable (fall back to setting the goal manually with /goal).

The script prefers the installation's runtime Python, which owns the supported
SQLite build, and re-executes itself under it when needed.
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

MARKER = "JSPACE_GOAL_BRIDGE_STAGE"
CHECKOUT = Path.home() / ".hermes" / "hermes-agent"


# ----------------------------------------------------------------------- runtime

def _stage() -> bool:
    """Load the Hermes checkout; report whether the session store is reachable."""
    os.environ.pop("PYTHONHOME", None)
    os.environ.pop("PYTHONPATH", None)
    checkout = Path(os.environ.get("HERMES_AGENT_ROOT") or CHECKOUT)
    if str(checkout) not in sys.path:
        sys.path.insert(0, str(checkout))
    try:
        import hermes_bootstrap  # noqa: F401
    except Exception:
        pass
    try:
        from hermes_cli.goals import _get_session_db

        return _get_session_db() is not None
    except Exception:
        return False


def _runtime_candidates():
    """Interpreters to try, most specific first."""
    seen = set()
    paths = []
    override = os.environ.get("JSPACE_GOAL_PYTHON")
    if override:
        paths.append(Path(override))
    tools = Path.home() / ".hermes" / "tools"
    if tools.is_dir():
        paths.extend(sorted((p / "bin" / "python3" for p in tools.glob("python-*")), reverse=True))
    for path in paths:
        key = str(path)
        if key not in seen:
            seen.add(key)
            yield key


def _reexec() -> None:
    """Replace this process with a run under the first runtime Python that works."""
    script = str(Path(__file__).resolve())
    for candidate in _runtime_candidates():
        try:
            probe = subprocess.run([candidate, "-I", script, "--probe"],
                                   capture_output=True, timeout=40)
        except Exception:
            continue
        if probe.returncode == 0:
            env = dict(os.environ)
            env[MARKER] = "1"
            os.execve(candidate, [candidate, "-I", script, *sys.argv[1:]], env)
    # no candidate worked; the caller reports the failure
    return


def _unavailable() -> int:
    print(
        "jspace_goal: the Hermes session store is unreachable from this interpreter.\n"
        "Set JSPACE_GOAL_PYTHON to the Hermes runtime Python, or ask the user to set the\n"
        "goal manually with /goal and /goal gate add, then continue.",
        file=sys.stderr,
    )
    return 3


# ----------------------------------------------------------------------- helpers

def _ship_check_command(task: str) -> str:
    """The canonical suite ship check, pinned to this runtime and skill copy."""
    skill = Path(__file__).resolve().parent.parent
    control = skill / "scripts" / "control.py"
    python = sys.executable or "python3"
    target = str(Path(task).expanduser().resolve())
    return (f"{shlex.quote(python)} {shlex.quote(str(control))} "
            f"--root {shlex.quote(target)} check --stage ship")


def _no_goal(command: str) -> int:
    print(f"jspace_goal: no active goal. Run 'set' before '{command}'.", file=sys.stderr)
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jspace_goal.py",
        description="Bridge from the J-Space skill to the Hermes goal mechanism.",
    )
    parser.add_argument("--session", help="session key override (default: HERMES_SESSION_KEY)")
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="show the session goal, contract, gates, subgoals")
    status.add_argument("--json", action="store_true", help="machine-readable output")

    sett = sub.add_parser("set", help="set the session goal (replaces an existing goal)")
    sett.add_argument("--goal", required=True)
    sett.add_argument("--outcome", default="")
    sett.add_argument("--verification", default="")
    sett.add_argument("--constraints", default="")
    sett.add_argument("--boundaries", default="")
    sett.add_argument("--stop-when", dest="stop_when", default="")
    sett.add_argument("--max-turns", dest="max_turns", type=int, default=None)
    sett.add_argument("--if-absent", dest="if_absent", action="store_true",
                      help="keep an existing goal unchanged")

    gate = sub.add_parser("gate", help="manage quality gates")
    gsub = gate.add_subparsers(dest="gate_action")
    gadd = gsub.add_parser("add", help="add a quality gate")
    gadd.add_argument("--command", dest="gate_command", default="")
    gadd.add_argument("--ship-check", dest="ship_check", action="store_true",
                      help="use the suite ship check as the gate")
    gadd.add_argument("--task", default="", help="task directory for --ship-check")
    gadd.add_argument("--timeout", type=int, default=None)
    gadd.add_argument("--max-retries", dest="max_retries", type=int, default=None)
    gsub.add_parser("list", help="list gates")
    grem = gsub.add_parser("remove", help="remove a gate by 1-based index")
    grem.add_argument("index", type=int)
    gsub.add_parser("clear", help="remove all gates")

    subg = sub.add_parser("subgoal", help="manage additional criteria (/subgoal)")
    ssub = subg.add_subparsers(dest="sub_action")
    sadd = ssub.add_parser("add", help="append a criterion")
    sadd.add_argument("text")
    ssub.add_parser("list", help="list criteria")
    ssub.add_parser("clear", help="remove all criteria")

    sub.add_parser("pause", help="pause the goal loop")
    sub.add_parser("resume", help="resume the goal loop (resets the turn budget)")
    sub.add_parser("clear", help="clear the goal")
    return parser


# -------------------------------------------------------------------------- main

def main(argv) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        from hermes_cli.goals import GoalContract, GoalManager
    except Exception as exc:
        print(f"jspace_goal: cannot load the Hermes goals module ({exc}).", file=sys.stderr)
        return 3

    session = (args.session or os.environ.get("HERMES_SESSION_KEY") or "").strip()
    if not session:
        print("jspace_goal: no session key. Set HERMES_SESSION_KEY or pass --session.", file=sys.stderr)
        return 2
    mgr = GoalManager(session_id=session)

    if args.command == "status":
        state = mgr.state
        if args.json:
            payload = {"session": session,
                       "goal": json.loads(state.to_json()) if state else None}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 0
        print(f"session: {session}")
        print(mgr.status_line())
        if state is not None and mgr.has_goal():
            print("contract:")
            print(state.contract.render_block() or "  (none)")
            print("gates:")
            print(mgr.render_gates())
            print("subgoals:")
            print(mgr.render_subgoals())
        return 0

    if args.command == "set":
        state = mgr.state
        if args.if_absent and state is not None and mgr.has_goal():
            print(f"⊙ Goal kept ({state.status}, {state.turns_used}/{state.max_turns} turns): {state.goal}")
            print("  --if-absent: nothing changed. Use 'clear' first to replace it, or 'resume' to restart it.")
            return 0
        contract = GoalContract(outcome=args.outcome, verification=args.verification,
                                constraints=args.constraints, boundaries=args.boundaries,
                                stop_when=args.stop_when)
        state = mgr.set(args.goal, max_turns=args.max_turns,
                        contract=None if contract.is_empty() else contract)
        print(f"⊙ Goal set ({state.max_turns}-turn budget): {state.goal}")
        print("  The host judges this goal after every turn. Add the ship check as a gate next.")
        return 0

    if args.command == "gate":
        if args.gate_action == "add":
            if args.ship_check:
                if not args.task:
                    print("jspace_goal: --ship-check needs --task DIR.", file=sys.stderr)
                    return 2
                command = _ship_check_command(args.task)
            else:
                command = (args.gate_command or "").strip()
                if not command:
                    print("jspace_goal: give --command CMD, or --ship-check with --task DIR.",
                          file=sys.stderr)
                    return 2
            state = mgr.state
            if not mgr.has_goal() or state is None:
                return _no_goal("gate add")
            if any(gate.command == command for gate in state.gates):
                print(f"⚿ Gate already present: $ {command}")
                return 0
            gate = mgr.add_gate(command, timeout_seconds=args.timeout, max_retries=args.max_retries)
            print(f"⚿ Gate added: $ {gate.command} ({gate.max_retries} retries, "
                  f"{gate.timeout_seconds}s timeout). It must pass before the goal can complete.")
            return 0
        if args.gate_action == "list":
            print(mgr.render_gates())
            return 0
        if args.gate_action == "remove":
            if not mgr.has_goal():
                return _no_goal("gate remove")
            try:
                removed = mgr.remove_gate(args.index)
            except IndexError as exc:
                print(f"jspace_goal: {exc}", file=sys.stderr)
                return 2
            print(f"✓ Gate removed: $ {removed}")
            return 0
        if args.gate_action == "clear":
            if not mgr.has_goal():
                return _no_goal("gate clear")
            count = mgr.clear_gates()
            print(f"✓ Cleared {count} gate(s)." if count else "No gates to clear.")
            return 0
        print("jspace_goal: gate needs an action: add, list, remove, clear.", file=sys.stderr)
        return 2

    if args.command == "subgoal":
        if args.sub_action == "add":
            if not mgr.has_goal():
                return _no_goal("subgoal add")
            text = mgr.add_subgoal(args.text)
            state = mgr.state
            count = len(state.subgoals) if state is not None else 1
            print(f"✓ Added subgoal {count}: {text}")
            return 0
        if args.sub_action == "list":
            print(mgr.render_subgoals())
            return 0
        if args.sub_action == "clear":
            if not mgr.has_goal():
                return _no_goal("subgoal clear")
            count = mgr.clear_subgoals()
            print(f"✓ Cleared {count} subgoal(s)." if count else "No subgoals to clear.")
            return 0
        print("jspace_goal: subgoal needs an action: add, list, clear.", file=sys.stderr)
        return 2

    if args.command == "pause":
        state = mgr.pause(reason="paused via jspace_goal")
        print(f"⏸ Goal paused: {state.goal}" if state else "No goal set.")
        return 0

    if args.command == "resume":
        state = mgr.resume()
        if state is None:
            print("No goal to resume.")
            return 0
        print(f"▶ Goal resumed ({state.max_turns}-turn budget reset): {state.goal}")
        return 0

    if args.command == "clear":
        had = mgr.has_goal()
        mgr.clear()
        print("✓ Goal cleared." if had else "No active goal.")
        return 0

    return 2


def _is_runtime_interpreter() -> bool:
    """True when the current interpreter is already one of the runtime candidates."""
    try:
        current = str(Path(sys.executable).resolve())
    except Exception:
        return False
    for cand in _runtime_candidates():
        try:
            if str(Path(cand).resolve()) == current:
                return True
        except Exception:
            continue
    return False


if __name__ == "__main__":
    if "--probe" in sys.argv[1:]:
        sys.exit(0 if _stage() else 1)
    # Prefer the installation's runtime Python: it owns the supported SQLite build.
    # Fall back to the current interpreter only when no candidate works.
    if os.environ.get(MARKER) != "1" and not _is_runtime_interpreter():
        _reexec()
    if not _stage():
        sys.exit(_unavailable())
    sys.exit(main(sys.argv[1:]))