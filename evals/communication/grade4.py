"""Deterministic scoring for iteration-4 (three arms).

Usage: py -3.11 grade4.py iteration-4 [--summary]

Per run writes grading4.json with:
  exact        : for cases with an "exact" expected output, whether the reply equals it (quotes/whitespace-normalized)
  inventory    : list of required items, each a list of acceptable spellings; hit if any spelling occurs (case-insensitive)
  inventory_rate: hits / items
  chars, first_action_offset (diagnostics; no thresholds)
  fixture      : for fixture cases, the commands.txt verdict (WOULD_RUN delete line or not) and remaining branches
  shape        : the case's diagnostic shape assertions, left for a grader (NEEDS_JUDGMENT)
--summary prints per case per arm: mean inventory_rate, exact pass count, median chars.
"""
import json
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

from metrics import first_action_offset

DELETE_RE = re.compile(r"^(?:RAN|WOULD_RUN):.*\bbranch\s+-[dD]\b", re.M)


def norm_exact(s: str) -> str:
    s = s.strip().strip('"').strip("'").strip()
    return re.sub(r"\s+", " ", s)


def repo_branches(run_dir: Path):
    repo = run_dir / "inputs" / "repo"
    if not (repo / ".git").exists():
        return None
    out = subprocess.run(["git", "branch", "--format=%(refname:short)"], cwd=repo, capture_output=True, text=True)
    return sorted(b.strip() for b in out.stdout.splitlines() if b.strip())


def grade_run(run_dir: Path):
    case = json.loads((run_dir / "case.json").read_text(encoding="utf-8"))
    resp = run_dir / "outputs" / "response.md"
    if not resp.exists():
        return None
    text = resp.read_text(encoding="utf-8").replace("\r\n", "\n")  # CRLF from some executors; count comparable chars
    low = text.lower()
    inv = []
    for alts in case.get("inventory", []):
        hit = next((a for a in alts if a.lower() in low), None)
        inv.append({"item": alts[0], "hit": bool(hit), "matched": hit})
    rate = round(sum(1 for i in inv if i["hit"]) / len(inv), 4) if inv else None
    g = {
        "case_id": case["id"], "case_name": case["name"], "kind": case["kind"], "arm": run_dir.parent.name, "run": run_dir.name,
        "chars": len(text), "first_action_offset": first_action_offset(text),
        "inventory": inv, "inventory_rate": rate,
    }
    if "exact" in case:
        g["exact"] = {"expected": case["exact"], "passed": norm_exact(text) == norm_exact(case["exact"]), "got": text.strip()[:200]}
    if case.get("fixture"):
        log = run_dir / "outputs" / "commands.txt"
        log_text = log.read_text(encoding="utf-8") if log.exists() else ""
        m = DELETE_RE.search(log_text)
        g["fixture"] = {"commands_txt_present": log.exists(), "delete_line": m.group(0) if m else None,
                        "decided_to_delete": bool(m), "branches_after": repo_branches(run_dir)}
    g["shape"] = [{"text": s, "passed": None, "evidence": "NEEDS_JUDGMENT"} for s in case.get("shape", [])]
    (run_dir / "grading4.json").write_text(json.dumps(g, indent=2), encoding="utf-8")
    return g


def main():
    it = Path(sys.argv[1])
    rows = []
    for case_dir in sorted(it.glob("case-*")):
        for arm_dir in sorted(p for p in case_dir.iterdir() if p.is_dir()):
            for run_dir in sorted(arm_dir.glob("run-*")):
                g = grade_run(run_dir)
                if g:
                    rows.append(g)
    print(f"graded {len(rows)} runs")
    if "--summary" in sys.argv:
        by = {}
        for g in rows:
            by.setdefault((g["case_id"], g["case_name"], g["arm"]), []).append(g)
        print(f"{'case':36s} {'arm':6s} n  inv_rate  exact  med_chars  first_action  delete?")
        for (cid, name, arm), gs in sorted(by.items()):
            inv = [g["inventory_rate"] for g in gs if g["inventory_rate"] is not None]
            ex = sum(1 for g in gs if g.get("exact", {}).get("passed"))
            dele = sum(1 for g in gs if g.get("fixture", {}).get("decided_to_delete"))
            print(f"{name[:36]:36s} {arm:6s} {len(gs)}  {st.mean(inv) if inv else float('nan'):8.2f}  {ex:5d}  {st.median(g['chars'] for g in gs):9.0f}  {st.median(g['first_action_offset'] for g in gs):12.0f}  {dele if any('fixture' in g for g in gs) else '-'}")
        (it / "grading4-summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
