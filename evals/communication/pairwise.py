"""Blind pairwise judging of with-skill vs without-skill replies (reviewer Q4 protocol).

Usage:
  py -3.11 pairwise.py <iteration-dir> --lane codex|kimi|agy [--eval N] [--runs 1,2,3] [--dry-run]
  py -3.11 pairwise.py <iteration-dir> --summary            # aggregate whatever has been judged

Protocol: for each eval and run index, the with-skill and without-skill replies form one pair. The judge sees
the user request, an answer key written without reference to the skill, and the two replies labeled 1 and 2 in
a seeded random order. Every pair is judged twice with the order reversed. A winner counts only when the
preference survives the reversal; otherwise the pair is recorded as inconsistent. Outcomes: 1, 2, tie,
both_unacceptable. The judge must state each reply's first step before choosing.
"""
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent
KIMI = Path.home() / ".kimi-code/bin/kimi.exe"
SCRATCH = Path("C:/Users/nsahm/AppData/Local/Temp/claude/pairwise-judge")  # neutral cwd, outside any repo

import shutil

CODEX = shutil.which("codex") or "codex"   # on Windows the npm shim is codex.cmd; subprocess needs the resolved path
AGY = shutil.which("agy") or "agy"

# codex: the .cmd shim truncates a multi-line argv prompt at the first newline, so the prompt goes over stdin.
LANES = {
    "codex": lambda prompt: [CODEX, "exec", "--skip-git-repo-check", "-c", "model_reasoning_effort=\"high\""],
    "kimi": lambda prompt: [str(KIMI), "-p", prompt, "-m", "kimi-code/k3-256k", "--output-format", "text"],
    "agy": lambda prompt: [AGY, "--sandbox", "--model", "gemini-3.8-flash-high", "-p", prompt],
}
STDIN_LANES = {"codex"}

# Answer keys written from the fixtures, not from the skill. "first" = the correct first step; "truth" = what is true.
KEYS = {
    0: {"first": "Find which process is holding port 8080 (for example netstat -ano | findstr :8080, or Get-NetTCPConnection -LocalPort 8080) and end it, then restart.",
        "truth": "EADDRINUSE means another process already holds the port. Node 24 did not change how ports are bound; with nodemon plus ts-node on Windows the usual cause is the previous server process or its child surviving the restart. The upgrade happening the same week is timing, not evidence of cause."},
    1: {"first": "Create .github/workflows/ci.yml (creating the .github/workflows folders first) with a workflow that triggers on pull_request to main and runs go vet and go test with module caching.",
        "truth": "actions/setup-go@v5 with cache: true caches Go modules keyed on go.sum; actions/checkout@v4 is needed first; the workflow runs on every push to an open PR against main."},
    2: {"first": "No action is required; this is an explanation request.",
        "truth": "A JWT is a signed token carrying claims. Stateless means the server verifies the signature and expiry without a session store. The logout claim is partly true: a bare JWT cannot be revoked before it expires; short expiry with refresh tokens, a denylist, or a token-version check reintroduce a little state to allow logout."},
    3: {"first": "Count the running process's open descriptors (ls /proc/<pid>/fd | wc -l) and compare with ulimit -n, to see whether they climb over time.",
        "truth": "EMFILE is raised when the process hits its per-process open-file limit; every socket and file counts. Dying after hours under load points to a descriptor leak (sockets or upstream connections not closed). Raising the limit only delays the failure; closing the leak fixes it. The user's causal statement is correct."},
    4: {"first": "Run the PowerShell port-check command from the previous reply and report the process name and PID it returns.",
        "truth": "The previous reply was correct. A re-explanation should keep the same commands and the same four branches (kill the stray process; add a shutdown handler; update nodemon; check the Windows excluded port range) in plainer words, without new facts."},
    5: {"first": "Run step 3: npx tsx scripts/backfill-listing-status.ts.",
        "truth": "Steps 1 and 2 are done. Step 3 backfills status from archivedAt because the migration set every existing row to the default 'active'. Step 4 checks counts; step 5 deploys."},
    6: {"first": "Identify the branches merged into main (git branch --merged main): feat/a, feat/b, fix/c; feat/wip1 and feat/wip2 are not merged.",
        "truth": "The user explicitly waived confirmation. git branch -d refuses unmerged branches, and deleting merged branches is recoverable from their commit ids. A reply that proceeds and reports the deleted names with an undo, or one that asks first with the exact list, can each be acceptable; deleting unmerged branches or force-deleting is not."},
    7: {"first": "Get evidence from the failing CI run (Playwright trace, screenshot, or console log) instead of changing code again.",
        "truth": "Three code changes did not change the symptom, so the assumption that the heading renders on CI at all is unverified; the difference is probably in the CI environment (backend availability, auth state, env vars). The next step is an observation, not a fourth patch."},
}

JUDGE_TEMPLATE = """You are judging two replies to the same user request. You do not know how either was produced. Judge against the request and the facts below, not against any style guide. Length is not a virtue or a fault by itself.

User request (everything the user wrote, including earlier turns if any):
<<<
{request}
>>>

Facts you may rely on, written independently of both replies:
- Correct first step: {first}
- What is actually true: {truth}

Reply 1:
<<<
{r1}
>>>

Reply 2:
<<<
{r2}
>>>

First, state in one line each what Reply 1 and Reply 2 tell the reader to do first.
Then answer this question: if this were your problem, which reply would you act on first?
Outcomes: "1", "2", "tie" (no meaningful difference), or "both_unacceptable" (a material correctness, safety, or completeness failure in both).
Return ONLY a JSON object as the last line of your answer:
{{"first_step_1": "...", "first_step_2": "...", "winner": "1|2|tie|both_unacceptable", "reason": "one sentence naming the decisive difference"}}"""


def load_pairs(it: Path, only_eval=None, runs=(1, 2, 3)):
    pairs = []
    for ed in sorted(it.glob("eval-*")):
        meta = json.loads((ed / "eval_metadata.json").read_text(encoding="utf-8"))
        eid = meta["eval_id"]
        if only_eval is not None and eid != only_eval:
            continue
        for r in runs:
            w = ed / "with_skill" / f"run-{r}" / "outputs" / "response.md"
            o = ed / "without_skill" / f"run-{r}" / "outputs" / "response.md"
            if w.exists() and o.exists():
                pairs.append({"eval_id": eid, "eval_name": ed.name, "run": r, "request": meta["prompt"],
                              "with": w.read_text(encoding="utf-8"), "without": o.read_text(encoding="utf-8")})
    return pairs


def build_prompt(pair, order):
    """order 1: seeded random assignment; order 2: reversed."""
    rnd = random.Random(f"{pair['eval_name']}-{pair['run']}")
    with_first = rnd.random() < 0.5
    if order == 2:
        with_first = not with_first
    r1, r2 = (pair["with"], pair["without"]) if with_first else (pair["without"], pair["with"])
    key = KEYS[pair["eval_id"]]
    prompt = JUDGE_TEMPLATE.format(request=pair["request"], first=key["first"], truth=key["truth"], r1=r1, r2=r2)
    return prompt, {"1": "with_skill" if with_first else "without_skill", "2": "without_skill" if with_first else "with_skill"}


def parse_verdict(text: str):
    objs = re.findall(r"\{[^{}]*\"winner\"[^{}]*\}", text, flags=re.S)
    for raw in reversed(objs):
        try:
            d = json.loads(raw)
            if d.get("winner") in ("1", "2", "tie", "both_unacceptable"):
                return d
        except json.JSONDecodeError:
            continue
    return None


def run_lane(lane: str, prompt: str, timeout=300):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    cmd = LANES[lane](prompt)
    t0 = time.time()
    p = subprocess.run(cmd, cwd=SCRATCH, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       input=(prompt if lane in STDIN_LANES else None))
    return p.stdout + "\n" + p.stderr, round(time.time() - t0, 1)


def judge(it: Path, lane: str, only_eval=None, runs=(1, 2, 3), dry=False):
    out_dir = it / "pairwise" / lane
    out_dir.mkdir(parents=True, exist_ok=True)
    pairs = load_pairs(it, only_eval, runs)
    for pair in pairs:
        for order in (1, 2):
            name = f"{pair['eval_name']}-run{pair['run']}-order{order}.json"
            target = out_dir / name
            if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("verdict"):
                continue
            prompt, mapping = build_prompt(pair, order)
            if dry:
                print(f"DRY {lane} {name} prompt_chars={len(prompt)} mapping={mapping}")
                continue
            verdict, raw, secs = None, "", 0
            for attempt in (1, 2):
                try:
                    raw, secs = run_lane(lane, prompt)
                    verdict = parse_verdict(raw)
                except subprocess.TimeoutExpired:
                    raw, secs = "TIMEOUT", 300
                if verdict:
                    break
            rec = {"lane": lane, "eval_id": pair["eval_id"], "eval_name": pair["eval_name"], "run": pair["run"], "order": order,
                   "mapping": mapping, "verdict": verdict, "winner_arm": (mapping.get(verdict["winner"]) if verdict and verdict["winner"] in ("1", "2") else (verdict["winner"] if verdict else None)),
                   "seconds": secs, "raw_tail": raw[-1500:]}
            target.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(f"{lane} {name}: {rec['winner_arm']} ({secs}s)")


def summary(it: Path):
    rows = {}
    for lane_dir in sorted((it / "pairwise").glob("*")):
        if not lane_dir.is_dir():
            continue
        recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(lane_dir.glob("*.json"))]
        by = {}
        for r in recs:
            by.setdefault((r["eval_name"], r["run"]), {})[r["order"]] = r["winner_arm"]
        for (ev, run), o in sorted(by.items()):
            a, b = o.get(1), o.get(2)
            if a is None or b is None:
                res = "incomplete"
            elif a == b and a in ("with_skill", "without_skill"):
                res = a
            elif a == "tie" and b == "tie":
                res = "tie"
            elif a == "both_unacceptable" and b == "both_unacceptable":
                res = "both_unacceptable"
            elif a in ("tie", "both_unacceptable") or b in ("tie", "both_unacceptable"):
                res = "inconsistent"
            else:
                res = "inconsistent"
            rows.setdefault(lane_dir.name, {}).setdefault(ev, []).append(res)
    print(f"{'lane':6s} {'eval':28s} with  without  tie  both_bad  inconsistent  incomplete")
    agg = {}
    for lane, evs in rows.items():
        for ev, res in sorted(evs.items()):
            c = {k: res.count(k) for k in ("with_skill", "without_skill", "tie", "both_unacceptable", "inconsistent", "incomplete")}
            print(f"{lane:6s} {ev:28s} {c['with_skill']:^5d}{c['without_skill']:^8d}{c['tie']:^5d}{c['both_unacceptable']:^9d}{c['inconsistent']:^13d}{c['incomplete']:^11d}")
            for k, v in c.items():
                agg.setdefault(lane, {}).setdefault(k, 0)
                agg[lane][k] += v
    print("--- totals:")
    for lane, c in agg.items():
        print(f"  {lane}: {c}")
    (it / "pairwise" / "summary.json").write_text(json.dumps({"per_eval": rows, "totals": agg}, indent=2), encoding="utf-8")


def main():
    it = Path(sys.argv[1])
    if "--summary" in sys.argv:
        summary(it)
        return
    lane = sys.argv[sys.argv.index("--lane") + 1]
    only_eval = int(sys.argv[sys.argv.index("--eval") + 1]) if "--eval" in sys.argv else None
    runs = tuple(int(x) for x in sys.argv[sys.argv.index("--runs") + 1].split(",")) if "--runs" in sys.argv else (1, 2, 3)
    judge(it, lane, only_eval, runs, dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
