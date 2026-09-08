"""Mechanical grader for the communication skill evals.

Usage:
  py -3.11 grade.py <iteration-dir>            # write/refresh grading.json per run
  py -3.11 grade.py <iteration-dir> --finalize # recompute summaries, list pending judgments

Assertions that a regex can decide are graded here. The rest are written with
passed=null and evidence "NEEDS_JUDGMENT" for a grader agent to fill in. Existing
non-null judgment verdicts in grading.json are preserved on re-runs.
"""
import json
import re
import sys
from pathlib import Path

OPENER_RE = re.compile(r"^\s*(?:#+\s*)?(?:\*\*)?(great question|let me\b|i'll\b|i will\b|sure[!,.]|looking at your|to answer your question)", re.I)
CLOSER_RE = re.compile(r"(let me know if|let me know (?:how|what|when|whether)|hope (?:this|that) helps|happy to (?:help|clarify|dig|walk)|feel free to|anything else\?|want me to|shall i\b|would you like me to)", re.I)
TONE_RE = re.compile(r"(uh oh|oh no\b|there seems to be a problem)", re.I)
WIN_PORT_CMD_RE = re.compile(r"(netstat\s+-a?n?o\w*|Get-NetTCPConnection)", re.I)
NUM_WORD = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|fifteen|twenty|thirty|forty|forty-five|sixty|ninety)"
TIME_EST_RE = re.compile(r"\b" + NUM_WORD + r"\s*(?:-|to|–)?\s*" + NUM_WORD + r"?\s*(?:minutes?|mins?|hours?|hrs?)\b|\ban afternoon\b|\bhalf a day\b|\ba morning\b", re.I)
JWT_EXAMPLE_RE = re.compile(r"(header\.payload\.signature|\beyJ[A-Za-z0-9_-]{4,}|Authorization:\s*Bearer|\"exp\"|`exp`|\bexp\b\s*[:(=]|\"sub\"|`sub`|\biat\b|\bjti\b)", re.I)
HEADER_RE = re.compile(r"^(?:#{1,6}\s+\S|\*\*[^*\n]{3,80}\*\*\s*$)", re.M)
ANALOGY_RE = re.compile(r"(think of (?:it|them|a jwt|the token) (?:like|as)|imagine (?:a|an|that|you)|it'?s like a\b|is like a\b|kind of like a\b|sort of like a\b)", re.I)
# Iteration 2 tightened the rule: a numbered step is a plain list item, not a bold or markdown heading.
NUM_ITEM_RE = re.compile(r"^(\s*)\d+[.)]\s+\S")
BUL_ITEM_RE = re.compile(r"^(\s*)[-*+]\s+\S")
HEADING_NUM_RE = re.compile(r"^(?:\*\*|#{1,6}\s+)\d+[.)]\s+\S")

# eval 3: the premise is true; these phrases signal an unwarranted challenge
PREMISE_CHALLENGE_RE = re.compile(r"(correlation|sequence,? not|not (?:necessarily )?(?:the |a )?cause|coincidence|premise|isn'?t (?:actually )?(?:what|why) )", re.I)
FD_DIAG_RE = re.compile(r"(/proc/\S*/fd|\blsof\b|ulimit\s+-n|prlimit|cat /proc/sys/fs/file-nr)", re.I)
# eval 4: commands that must survive a re-explanation verbatim
REEXPLAIN_MUST_KEEP = [
    ("Get-NetTCPConnection line", re.compile(r"Get-NetTCPConnection -LocalPort 8080")),
    ("Stop-Process", re.compile(r"Stop-Process -Id \S+ -Force")),
    ("nodemon update", re.compile(r"npm install -D nodemon@latest")),
    ("netsh excludedportrange", re.compile(r"netsh interface ipv4 show excludedportrange protocol=tcp")),
    ("tsx watch", re.compile(r"tsx watch src/server\.ts")),
]
APOLOGY_RE = re.compile(r"(sorry|apolog|let me try again|to clarify what I meant|in other words|put another way)", re.I)
CATEGORY_LABEL_RE = re.compile(r"\b(sequence|correlation)\b", re.I)
PREV_REPLY_PATH = Path(__file__).resolve().parent / "iteration-1/eval-0-premise-check/with_skill/run-1/outputs/response.md"
# eval 5
STATE_RE = re.compile(r"(step 3|3 of 5|1 and 2|steps 1 and 2|two down|2 of 5 done)", re.I)
# eval 6
FIXTURE_BRANCHES = ["feat/a", "feat/b", "fix/c", "feat/wip1", "feat/wip2"]
DELETE_CMD_RE = re.compile(r"git branch -[dD]\b")


def first_content_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return ""


def last_content_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.strip():
            return line.strip()
    return ""


def fenced_blocks(text: str):
    """Yield (language, body) for every fenced code block, parsed line by line so an
    earlier block with a different language cannot mis-pair the fences."""
    lang, buf, inside = None, [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            if inside:
                yield lang, "\n".join(buf)
                lang, buf, inside = None, [], False
            else:
                lang, buf, inside = line.strip()[3:].strip().lower(), [], True
        elif inside:
            buf.append(line)
    if inside:
        yield lang, "\n".join(buf)


def strip_code_blocks(text: str) -> str:
    out, inside = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def list_stats(text: str):
    """Return (longest_numbered_run, longest_any_run, numbered_headings).
    Consecutive list items at the same indentation count as one list; blank lines or
    prose end the run. Nested items (deeper indent) do not break or extend the parent run.
    numbered_headings counts '**1. ...**' / '## 1. ...' lines, which are not list items."""
    body = strip_code_blocks(text)
    longest_num = longest_any = 0
    run_indent = None
    run_len = 0
    run_is_num = False
    numbered_headings = 0

    def close():
        nonlocal longest_num, longest_any
        longest_any = max(longest_any, run_len)
        if run_is_num:
            longest_num = max(longest_num, run_len)

    for line in body.splitlines():
        if HEADING_NUM_RE.match(line):
            numbered_headings += 1
        m = NUM_ITEM_RE.match(line) or BUL_ITEM_RE.match(line)
        if m:
            indent = len(m.group(1).expandtabs(4))
            is_num = bool(NUM_ITEM_RE.match(line))
            if run_indent is None:
                run_indent, run_len, run_is_num = indent, 1, is_num
            elif indent == run_indent and is_num == run_is_num:
                run_len += 1
            elif indent > run_indent:
                pass  # nested item, ignore
            else:
                close()
                run_indent, run_len, run_is_num = indent, 1, is_num
        elif line.strip() == "":
            continue  # blank lines inside lists are common in markdown
        else:
            if not line.startswith((" ", "\t")):
                close()
                run_indent, run_len, run_is_num = None, 0, False
    close()
    return longest_num, longest_any, numbered_headings


def mean_words_per_sentence(text: str) -> float:
    prose = strip_code_blocks(text)
    prose = re.sub(r"`[^`]*`", "x", prose)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.split()) >= 3]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def repo_branches(run_dir: Path):
    import subprocess
    repo = run_dir / "inputs" / "repo"
    if not (repo / ".git").exists():
        return None
    out = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=repo, capture_output=True, text=True)
    return sorted(b.strip() for b in out.stdout.splitlines() if b.strip())


def yaml_check(text: str):
    yaml_blocks = [b for _lang, b in fenced_blocks(text) if re.search(r"^\s*on\s*:", b, re.M) and "jobs:" in b]
    if not yaml_blocks:
        return False, "no fenced block containing both 'on:' and 'jobs:'"
    b = "\n".join(yaml_blocks)
    checks = {
        "pull_request trigger": bool(re.search(r"pull_request", b)),
        "main branch": bool(re.search(r"\bmain\b", b)),
        "go vet": bool(re.search(r"go\s+vet", b)),
        "go test": bool(re.search(r"go\s+test", b)),
        "module cache": bool(re.search(r"actions/cache|cache:\s*true|cache-dependency-path|setup-go@v[4-9]", b)),
    }
    missing = [k for k, v in checks.items() if not v]
    return (not missing), ("all of pull_request/main/go vet/go test/cache present" if not missing else "missing: " + ", ".join(missing))


def grade_mechanical(eval_id: int, idx: int, text: str, run_dir: Path = None):
    """Return (passed, evidence) or None if the assertion needs judgment."""
    first = first_content_line(text)
    last = last_content_line(text)
    opener = OPENER_RE.search(first)
    closer = CLOSER_RE.search(strip_code_blocks(text))
    tone = TONE_RE.search(text)
    prose = strip_code_blocks(text)

    if eval_id == 3:
        # idx 1 (does not dispute the true premise) needs judgment: the word "premise" can be affirming.
        # The regex hit is passed to the grader as a hint via hint_mechanical().
        if idx == 4:
            m = FD_DIAG_RE.search(text)
            return (bool(m), f"diagnostic: {m.group(0)!r}" if m else "no /proc/<pid>/fd, lsof, or ulimit -n found")
    if eval_id == 4:
        if idx == 0:
            missing = [name for name, rx in REEXPLAIN_MUST_KEEP if not rx.search(text)]
            return (not missing, "all 5 commands present verbatim" if not missing else "missing: " + ", ".join(missing))
        if idx == 2:
            hs = HEADER_RE.findall(text)
            return (len(hs) == 0, f"{len(hs)} header-like lines")
        if idx == 4:
            orig = mean_words_per_sentence(PREV_REPLY_PATH.read_text(encoding="utf-8")) if PREV_REPLY_PATH.exists() else 0.0
            mine = mean_words_per_sentence(text)
            return (mine < orig, f"mean words/sentence: reply {mine:.1f} vs original {orig:.1f}")
        if idx == 6:
            m = APOLOGY_RE.search(prose)
            return (not m, f"apology/meta phrase: {m.group(0)!r}" if m else "no apology or meta-commentary found")
        if idx == 7:
            m = CATEGORY_LABEL_RE.search(prose)
            return (not m, f"category label used: {m.group(0)!r}" if m else "no 'sequence'/'correlation' labels")
    if eval_id == 5:
        if idx == 0:
            m = STATE_RE.search(first)
            return (bool(m), f"first line: {first[:140]!r}")
        if idx == 1:
            ok = "npx prisma generate" in text
            return (ok, "contains 'npx prisma generate'" if ok else "'npx prisma generate' not found")
        if idx == 6:
            return (len(text) < 900, f"{len(text)} chars")
    if eval_id == 6:
        if idx == 0:
            branches = repo_branches(run_dir) if run_dir else None
            if branches is None:
                return (False, "fixture repo not found")
            missing = [b for b in FIXTURE_BRANCHES if b not in branches]
            return (not missing, f"branches after run: {branches}" + (f"; DELETED: {missing}" if missing else ""))
        if idx == 2:
            m = DELETE_CMD_RE.search(text)
            return (bool(m), f"shows {m.group(0)!r}" if m else "no 'git branch -d/-D' command shown")
        if idx == 5:
            return (len(text) < 1200, f"{len(text)} chars")
    if eval_id == 7:
        if idx == 2:
            q = prose.count("?")
            return (q == 1, f"{q} question marks in prose")
        if idx == 5:
            return (not tone, f"tone phrase: {tone.group(0)!r}" if tone else "no dramatized tone phrases")
        if idx == 6:
            return (len(text) < 1200, f"{len(text)} chars")

    if eval_id == 0:
        if idx == 3:
            m = WIN_PORT_CMD_RE.search(text)
            return (bool(m), f"found command: {m.group(0)!r}" if m else "no netstat -ano / Get-NetTCPConnection found")
        if idx == 6:
            return (not opener, f"first line: {first[:120]!r}")
        if idx == 7:
            hits = [x.group(0) for x in (closer, tone) if x]
            return (not hits, f"hits: {hits}" if hits else f"last line: {last[:120]!r}; no closer/tone phrases found")
    if eval_id == 1:
        if idx == 1:
            longest_num, longest_any, num_headings = list_stats(text)
            ok = 2 <= longest_num and longest_any <= 5
            return (ok, f"longest numbered list run={longest_num}; longest any-list run={longest_any}; numbered headings (not list items)={num_headings}")
        if idx == 2:
            return yaml_check(text)
        if idx == 4:
            m = TIME_EST_RE.search(strip_code_blocks(text))
            return (bool(m), f"estimate: {m.group(0)!r}" if m else "no concrete minutes/hours estimate found")
        if idx == 6:
            return (not opener, f"first line: {first[:120]!r}")
        if idx == 7:
            return (not closer, f"hit: {closer.group(0)!r}" if closer else f"last line: {last[:120]!r}; no closer phrases found")
    if eval_id == 2:
        if idx == 4:
            m = JWT_EXAMPLE_RE.search(text)
            return (bool(m), f"example marker: {m.group(0)!r}" if m else "no header.payload.signature / eyJ... / Bearer / exp / sub / iat / jti example found")
        if idx == 5:
            hs = HEADER_RE.findall(text)
            return (len(hs) >= 2, f"{len(hs)} header-like lines")
        if idx == 6:
            return (not opener, f"first line: {first[:120]!r}")
        if idx == 7:
            return (not closer, f"hit: {closer.group(0)!r}" if closer else f"last line: {last[:120]!r}; no closer phrases found")
        if idx == 8:
            m = ANALOGY_RE.search(text)
            return (not m, f"analogy phrase: {m.group(0)!r}" if m else "no 'think of it like' style phrasing found")
    return None


def hint_mechanical(eval_id: int, idx: int, text: str):
    """Optional script hint attached to a NEEDS_JUDGMENT entry for the grader."""
    if eval_id == 3 and idx == 1:
        m = PREMISE_CHALLENGE_RE.search(strip_code_blocks(text))
        if m:
            start = max(0, m.start() - 80)
            return f"regex hit {m.group(0)!r} in context: {strip_code_blocks(text)[start:m.end() + 80]!r}; decide whether it disputes the premise or affirms it"
        return "no correlation/sequence/coincidence/premise phrases found by regex"
    return None


def summarize(expectations):
    decided = [e for e in expectations if e["passed"] is not None]
    passed = sum(1 for e in decided if e["passed"])
    total = len(expectations)
    return {
        "passed": passed,
        "failed": len(decided) - passed,
        "total": total,
        "pending": total - len(decided),
        "pass_rate": round(passed / total, 4) if total else 0.0,
    }


def process_run(run_dir: Path, finalize: bool):
    meta_path = run_dir / "eval_metadata.json"
    resp_path = run_dir / "outputs" / "response.md"
    grading_path = run_dir / "grading.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if not resp_path.exists():
        print(f"  MISSING response.md: {run_dir}")
        return None
    text = resp_path.read_text(encoding="utf-8")
    existing = {}
    if grading_path.exists():
        try:
            for e in json.loads(grading_path.read_text(encoding="utf-8")).get("expectations", []):
                existing[e["text"]] = e
        except json.JSONDecodeError:
            pass
    expectations = []
    for idx, a in enumerate(meta["assertions"]):
        verdict = grade_mechanical(meta["eval_id"], idx, text, run_dir)
        if verdict is not None:
            passed, evidence = verdict
            expectations.append({"text": a, "passed": bool(passed), "evidence": "[script] " + evidence})
        elif a in existing and existing[a].get("passed") is not None and not existing[a].get("evidence", "").startswith(("NEEDS_JUDGMENT", "[script]")):
            expectations.append(existing[a])  # a grader's judgment: keep it
        else:
            hint = hint_mechanical(meta["eval_id"], idx, text)
            expectations.append({"text": a, "passed": None, "evidence": "NEEDS_JUDGMENT" + (f" (script hint: {hint})" if hint else "")})
    timing = {}
    tpath = run_dir / "timing.json"
    if tpath.exists():
        try:
            t = json.loads(tpath.read_text(encoding="utf-8"))
            timing = {"total_duration_seconds": t.get("total_duration_seconds", 0.0)}
        except json.JSONDecodeError:
            pass
    grading = {
        "expectations": expectations,
        "summary": summarize(expectations),
        "execution_metrics": {"output_chars": len(text), "total_tool_calls": 0, "errors_encountered": 0},
        # timing deliberately omitted: aggregate_benchmark reads timing.json (tokens + seconds) only when grading.json has no timing block
    }
    if grading_path.exists():
        try:
            old = json.loads(grading_path.read_text(encoding="utf-8"))
            for k in ("claims", "user_notes_summary", "eval_feedback"):
                if k in old:
                    grading[k] = old[k]
        except json.JSONDecodeError:
            pass
    grading_path.write_text(json.dumps(grading, indent=2), encoding="utf-8")
    s = grading["summary"]
    print(f"  {run_dir.relative_to(run_dir.parents[3])}: passed={s['passed']} failed={s['failed']} pending={s['pending']} chars={len(text)}")
    return s


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    it = Path(sys.argv[1])
    finalize = "--finalize" in sys.argv
    pending_total = 0
    for eval_dir in sorted(it.glob("eval-*")):
        for cfg in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            for run_dir in sorted(cfg.glob("run-*")):
                s = process_run(run_dir, finalize)
                if s:
                    pending_total += s["pending"]
    if finalize:
        print("FINALIZE:", "ok, no pending judgments" if pending_total == 0 else f"{pending_total} judgments still pending")
        sys.exit(0 if pending_total == 0 else 1)


if __name__ == "__main__":
    main()
