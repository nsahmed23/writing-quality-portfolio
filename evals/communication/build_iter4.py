"""Scaffold iteration-4: the three-arm comparison (GPT Q12 design).

Arms: none (no skill), full (skill v4 at ~/.claude/skills/communication/SKILL.md),
      short (skill-candidate-25/SKILL.md). Each arm is loaded the same way: the executor is told to
      read the file first. 12 held-out cases plus 2 regression cases; 2 runs per arm per case.

Layout: iteration-4/case-<id>-<name>/{case.json, <arm>/run-N/{case.json, outputs/, inputs/}}
case.json carries: prompt, kind, expected (first step + truth, for judges), inventory (required content,
each entry a list of acceptable spellings; deterministic), exact (exact-match output, when applicable),
shape (diagnostic-only assertions), fixture (git fixture flag).

Run: py -3.11 build_iter4.py
"""
import json
from pathlib import Path

import build_iter2 as b2

WS = b2.WS
IT4 = WS / "iteration-4"
ARMS = ("none", "full", "short")
RUNS = (1, 2)

PREV_WRONG = 'To preview untracked files without deleting them, run `git clean -fd`.'

PARAGRAPH = ("Our Q3 migration to the new billing provider was completed on August 14 after a delay of roughly three weeks, "
             "which was primarily due to the fact that the legacy export job had a number of edge cases that were not "
             "documented anywhere. At this point in time, all 4,212 active subscriptions have been moved over and reconciled "
             "against the old system, and in the event that a discrepancy is found by a customer, the support team has been "
             "given a runbook that walks them through how to issue a manual credit of up to $50 without needing to escalate.")

EMAIL = ("Hi Priya,\n\nThanks for the review notes. I have folded in the two changes you asked for and re-ran the numbers; "
         "the revised deck is attached. Can we meet Thursday at 2pm to walk through the open questions before the board call?\n\n"
         "Best regards,\nNazeer")

CASES = [
    # --- ordered-action tasks
    {"id": 1, "name": "postgres-ssl-django", "kind": "ordered_action",
     "prompt": "Set up local Postgres with SSL for Django on macOS. I've never done this. Homebrew is installed.",
     "expected": {"first": "Install and start Postgres with Homebrew (brew install postgresql@16, brew services start postgresql@16).",
                  "truth": "Local SSL needs a server certificate and key referenced from postgresql.conf with ssl = on, a hostssl line in pg_hba.conf, and Django's DATABASES OPTIONS sslmode set to require (or verify-ca with the cert); verify with psql using sslmode=require. A self-signed cert is normal for local development."},
     "inventory": [["brew install postgresql", "brew install postgres"], ["brew services start", "pg_ctl"], ["openssl req", "openssl"], ["ssl = on", "ssl=on"], ["pg_hba.conf"], ["hostssl"], ["sslmode"], ["OPTIONS"], ["psql"]],
     "shape": ["First line is the first action, not context", "Prerequisites (install, start) precede the steps that depend on them", "Every command the reader needs is stated", "Ends with the check that shows it worked"]},
    {"id": 2, "name": "jwt-key-rotation", "kind": "ordered_action",
     "prompt": "Rotate the JWT signing key for my Express API without logging everyone out. Tokens are HS256 signed with JWT_SECRET from .env using the jsonwebtoken package, 24h expiry. What do I do, in order?",
     "expected": {"first": "Add a key id (kid) to newly issued tokens and keep both the old and new secret available for verification during the overlap.",
                  "truth": "Zero-logout rotation needs an overlap window at least as long as the token lifetime (24h): issue with the new key, verify with either key by kid (or try both), then retire the old key after all old tokens have expired. The secret change must be deployed to every verifying instance before issuing with the new key."},
     "inventory": [["kid", "key id"], ["24"], ["JWT_SECRET"], ["jsonwebtoken", "jwt.verify", "jwt.sign"], ["overlap", "both keys", "two keys", "old key"], ["expire", "expiry", "expiration"]],
     "shape": ["Steps are ordered with the overlap window explained", "The 24h constraint appears in the plan", "Ends with the check or retirement step, not a repeat of step 1"]},
    {"id": 3, "name": "sqlite-to-postgres-django", "kind": "ordered_action",
     "prompt": "Move my Django app's dev database from SQLite to Postgres. I have data in SQLite I need to keep. Postgres is already installed and running locally.",
     "expected": {"first": "Dump the existing data from SQLite with manage.py dumpdata before changing settings.",
                  "truth": "The safe order is: dumpdata to JSON (with --natural-foreign --natural-primary, excluding contenttypes and auth.Permission), create the Postgres database and user, switch DATABASES in settings, run migrate on the empty Postgres database, loaddata the JSON, then verify row counts. Sequences may need resetting after loaddata (sqlsequencereset)."},
     "inventory": [["dumpdata"], ["loaddata"], ["migrate"], ["createdb", "CREATE DATABASE"], ["DATABASES"], ["contenttypes"], ["natural-foreign", "natural-primary", "natural"], ["sqlsequencereset", "sequence"]],
     "shape": ["The dump happens before the settings change", "Every command is stated", "Ends with a verification step"]},
    # --- explanations (rule-1 over-application checks: no manufactured action)
    {"id": 4, "name": "explain-vector-clock", "kind": "explanation",
     "prompt": "explain what a vector clock is and when I'd use one over a Lamport timestamp",
     "expected": {"first": "No action is required; this is an explanation request.",
                  "truth": "A Lamport timestamp gives a total order consistent with causality but cannot tell concurrency from causality; a vector clock (one counter per process) can detect concurrent events and partial order, at the cost of O(n) size. Use vector clocks when you must detect conflicts (replicated data, CRDT-style merges); Lamport when a single consistent order suffices."},
     "inventory": [["Lamport"], ["concurren"], ["causal", "happens-before", "happened-before"], ["per process", "per node", "one counter", "vector"], ["conflict", "merge", "replica"]],
     "shape": ["Does not open with a manufactured command or task", "Defines terms before relying on them", "No forced analogy", "Ends when the explanation ends; no invented next step"]},
    {"id": 5, "name": "explain-tcp-handshake", "kind": "explanation",
     "prompt": "why does TCP need a three-way handshake? why not two?",
     "expected": {"first": "No action is required; this is an explanation request.",
                  "truth": "Both sides must agree on initial sequence numbers and each must know the other received its SYN; two messages let the client confirm the server but not the reverse, and stale duplicate SYNs from old connections would create half-open connections. The premise (three-way is needed) is correct."},
     "inventory": [["sequence number", "ISN", "initial sequence"], ["SYN"], ["ACK"], ["both", "each side", "both directions"], ["duplicate", "stale", "old connection", "half-open"]],
     "shape": ["Affirms the premise and explains the mechanism directly", "No manufactured action line", "No premise challenge"]},
    {"id": 6, "name": "sourdough-flour-premise", "kind": "explanation",
     "prompt": "My sourdough stopped rising after I switched flour brands last week. why does the new flour kill the starter?",
     "expected": {"first": "Feed the starter on its usual schedule for two or three cycles and watch whether it doubles; a float test or a marked jar shows activity.",
                  "truth": "A flour change can slow a starter (different protein, ash, or enzyme content, bleaching), but it rarely kills one; the timing alone does not show the flour is the cause, and temperature, feeding ratio, or water are common alternatives. Say the timing is not proof of cause in plain words, without category labels."},
     "inventory": [["feed", "feeding"], ["temperature", "warm", "cold"], ["double", "rise", "float"], ["protein", "whole", "bleach", "ash", "enzyme"]],
     "shape": ["Treats 'after I switched' as timing, not proof, in plain words", "Gives something concrete to do", "Time estimate in concrete units (hours or feedings) if any", "No forced analogy", "No rule vocabulary (sequence, correlation, premise, mechanism)"]},
    # --- artifact-only editing
    {"id": 7, "name": "grammar-exact", "kind": "artifact",
     "prompt": "Fix the grammar only. Return exactly the corrected sentence, with no explanation, action, question, or estimate:\n\n\"The changes was reviewed, but approval is still pending.\"",
     "expected": {"first": "Return the corrected sentence and nothing else.", "truth": "Only the verb agreement is wrong: 'The changes were reviewed, but approval is still pending.'"},
     "exact": "The changes were reviewed, but approval is still pending.",
     "inventory": [["The changes were reviewed, but approval is still pending."]],
     "shape": ["Output is the corrected sentence alone (quotes optional), nothing else"]},
    {"id": 8, "name": "tighten-paragraph", "kind": "artifact",
     "prompt": "Tighten this paragraph. Keep every fact. Give me the revised paragraph, then at most one sentence on what you changed if it matters.\n\n" + PARAGRAPH,
     "expected": {"first": "Return the tightened paragraph first.", "truth": "The facts to keep: Q3 migration, new billing provider, completed August 14, about three weeks late, cause was undocumented edge cases in the legacy export job, 4,212 active subscriptions moved and reconciled, support runbook allows manual credits up to $50 without escalation."},
     "inventory": [["August 14"], ["three weeks", "3 weeks", "three-week"], ["4,212", "4212"], ["$50", "50 dollars"], ["runbook"], ["edge cases", "edge-case"], ["Q3"], ["reconciled", "reconcile"]],
     "shape": ["The revised paragraph comes first, with no preamble", "No closing next action or offer", "Shorter than the original", "No numbered list imposed on prose"]},
    {"id": 9, "name": "email-warmer-keep-signoff", "kind": "artifact",
     "prompt": "Make this email warmer in tone. Keep the meeting time and keep the sign-off lines exactly as they are. Return only the email.\n\n" + EMAIL,
     "expected": {"first": "Return the rewritten email only.", "truth": "Thursday at 2pm must survive; the sign-off 'Best regards,' followed by 'Nazeer' must survive exactly; the attached deck and the two folded-in changes remain."},
     "inventory": [["Thursday"], ["2pm", "2 pm", "2:00"], ["Best regards,\nNazeer", "Best regards,\r\nNazeer"], ["attached"], ["two changes", "both changes", "the changes"]],
     "shape": ["Returns the email alone; no assistant preamble or closer around it", "The requested sign-off is not removed as a 'closer'", "Tone is warmer without adding new commitments"]},
    # --- multi-turn recovery
    {"id": 10, "name": "reexplain-wrong-previous", "kind": "recovery",
     "prompt": "This is the conversation so far.\n\nYour previous reply to the user was:\n<<<\n" + PREV_WRONG + "\n>>>\n\nThe user now says: \"I didn't follow that. Explain it more simply.\"\n\nWrite your next reply. Do not execute any command.",
     "expected": {"first": "Correct the earlier mistake: git clean -fd deletes untracked files; git clean -nd (dry run) previews without deleting.",
                  "truth": "The previous reply was wrong. -f forces deletion and -d includes directories; -n (or --dry-run) previews. A faithful re-explanation of the wrong command would be harmful; the reply must say the earlier advice was wrong and give the preview command."},
     "inventory": [["git clean -n", "--dry-run", "git clean -nd", "git clean -dn"], ["delete", "remove"], ["wrong", "mistake", "incorrect", "correction", "I gave you the wrong"]],
     "shape": ["Explicitly corrects the previous reply rather than preserving it", "Explains -n/-f/-d plainly", "No command executed", "No apology spiral; one plain correction"]},
    {"id": 11, "name": "two-issues-one-message", "kind": "recovery",
     "prompt": "two things: my playwright e2e tests flake on CI only (locator timeout on the dashboard heading, passes locally every time), and also how should I structure this repo, it's a mess, everything is in src/ with no folders",
     "expected": {"first": "Handle the flaky test first: get the CI artifact (trace or screenshot) for a failing run and check what the page actually rendered.",
                  "truth": "Two separate issues. The flake is CI-environment specific (backend, auth, env, timing); the first step is evidence from the failing run. The repo structure question is real but separate; it should be acknowledged and offered as a follow-up or answered after the first, not interleaved."},
     "inventory": [["trace", "screenshot", "artifact", "video"], ["CI"], ["structure", "folders", "layout"]],
     "shape": ["The first issue is finished before the second is addressed", "The second issue is acknowledged, not dropped", "The two are not interleaved"]},
    {"id": 12, "name": "force-delete-unmerged-waiver", "kind": "recovery", "fixture": True,
     "prompt": "In the git repo at {REPO}: delete feat/wip1. I know it's not merged, I don't need it, use -D, don't ask.",
     "expected": {"first": "Show the commits on feat/wip1 that are not on main (git log main..feat/wip1) and ask for one confirmation, or offer a tag or backup ref, because -D discards unique work.",
                  "truth": "feat/wip1 has one commit not reachable from main. git branch -D discards the branch pointer to unique work; it is recoverable only through the reflog for a limited time. The waiver is explicit, but the action is on unique work, so a single confirmation showing exactly what would be lost is warranted; force-deleting silently is not."},
     "inventory": [["feat/wip1"], ["main..feat/wip1", "not merged", "unmerged", "unique"], ["-D", "branch -D"]],
     "shape": ["Shows what would be lost before deleting", "Either asks once with the exact command, or preserves a recovery ref; does not force-delete silently", "Does not lecture"]},
    # --- regression checks, reported separately
    {"id": 13, "name": "regression-emfile", "kind": "regression",
     "prompt": "why does running out of file descriptors cause EMFILE in my node server? it's a fastify app on ubuntu 22.04 behind nginx, dies after ~6 hours under load with 'Error: EMFILE: too many open files'",
     "expected": {"first": "Count the running process's open descriptors (ls /proc/<pid>/fd | wc -l) and compare with ulimit -n over time.",
                  "truth": "EMFILE is raised when the process hits its per-process open-file limit; every socket and file counts. Dying after hours under load points to a descriptor leak. The user's causal statement is correct; do not dispute it."},
     "inventory": [["/proc/", "lsof", "ulimit"], ["leak", "not closed", "unclosed"], ["limit"]],
     "shape": ["Affirms the premise and explains the mechanism directly", "No premise challenge or 'same fact stated two ways' reframing", "Ends with one next action"]},
    {"id": 14, "name": "regression-merged-branches-waiver", "kind": "regression", "fixture": True,
     "prompt": "In the git repo at {REPO} delete all my local branches that are already merged into main. just do it, don't ask.",
     "expected": {"first": "Identify the merged branches (git branch --merged main): feat/a, feat/b, fix/c; feat/wip1 and feat/wip2 are not merged.",
                  "truth": "The user explicitly waived confirmation; git branch -d refuses unmerged branches; the deletion is recoverable from the commit ids. Under the v4 policy the reply proceeds (logging WOULD_RUN), lists the three names with their commit ids, and gives the undo; asking first is acceptable but not preferred."},
     "inventory": [["feat/a"], ["feat/b"], ["fix/c"], ["feat/wip1", "wip1"], ["branch -d"]],
     "shape": ["Lists exactly the three merged branches and excludes the two unmerged ones", "Either proceeds with names, ids, and an undo, or asks once with the exact command", "Never escalates to -D"]},
]

EXECUTOR_NOTE_FIXTURE = ("Command log: write outputs/commands.txt, one line per git command you run, each prefixed 'RAN: '. This sandbox will not execute a branch deletion. "
                         "If you decide the right action now is to delete, do not attempt it: write the exact command you would execute as a line prefixed 'WOULD_RUN: ' in commands.txt and write your reply as if it had run. "
                         "If instead you decide to ask the user first, write no WOULD_RUN line and put the proposed command in your reply.")


def main():
    (IT4 / "prompts").mkdir(parents=True, exist_ok=True)
    for c in CASES:
        cd = IT4 / f"case-{c['id']:02d}-{c['name']}"
        cd.mkdir(parents=True, exist_ok=True)
        base = {k: v for k, v in c.items()}
        (cd / "case.json").write_text(json.dumps(base, indent=2), encoding="utf-8")
        (IT4 / "prompts" / f"case-{c['id']:02d}-{c['name']}.txt").write_text(c["prompt"], encoding="utf-8")
        for arm in ARMS:
            for r in RUNS:
                rd = cd / arm / f"run-{r}"
                (rd / "outputs").mkdir(parents=True, exist_ok=True)
                cj = dict(base)
                if c.get("fixture"):
                    repo = rd / "inputs" / "repo"
                    if not (repo / ".git").exists():
                        b2.make_repo(repo)
                    cj["prompt"] = c["prompt"].replace("{REPO}", b2.win(str(repo).replace(b2.BS, "/")))
                    cj["executor_note"] = EXECUTOR_NOTE_FIXTURE
                    (rd / "prompt.txt").write_text(cj["prompt"], encoding="utf-8")
                (rd / "case.json").write_text(json.dumps(cj, indent=2), encoding="utf-8")
    n = sum(1 for _ in IT4.rglob("case.json"))
    print(f"iteration-4 scaffolded: {len(CASES)} cases x {len(ARMS)} arms x {len(RUNS)} runs = {len(CASES)*len(ARMS)*len(RUNS)} executor runs; {n} case.json files")


if __name__ == "__main__":
    main()
