"""Scaffold iteration-5: the v5 targeted rerun on the cases v5 touches, full and short arms only, two runs each.

Cases (from iteration-4-plan step 3 and the three reviews): 2 jwt-key-rotation (brevity watch), 5 explain-tcp-handshake,
6 sourdough-flour-premise, 11 two-issues-one-message, 12 force-delete-unmerged-waiver (fixture).
Layout mirrors iteration-4 so grade4.py, verify_quotes.py, report4.py and pairwise5.py work unchanged:
  iteration-5/case-NN-name/{case.json,<arm>/run-N/{case.json,prompt.txt,inputs/repo,outputs/}}
case.json is copied from iteration-4 (which carries the reviewed inventory alternatives and the sourdough key as a property).
Usage: py -3.11 build_iter5.py
"""
import json
import shutil
from pathlib import Path

import build_iter2 as b2
from build_iter4 import EXECUTOR_NOTE_FIXTURE

WS = Path(__file__).resolve().parent
IT4 = WS / "iteration-4"
IT5 = WS / "iteration-5"
CASE_IDS = (2, 5, 6, 11, 12)
ARMS = ("full", "short")
RUNS = (1, 2)


def main():
    (IT5 / "prompts").mkdir(parents=True, exist_ok=True)
    made = 0
    for cd4 in sorted(IT4.glob("case-*")):
        case = json.loads((cd4 / "case.json").read_text(encoding="utf-8"))
        if case["id"] not in CASE_IDS:
            continue
        cd5 = IT5 / cd4.name
        cd5.mkdir(parents=True, exist_ok=True)
        (cd5 / "case.json").write_text(json.dumps(case, indent=2), encoding="utf-8")
        shutil.copy2(IT4 / "prompts" / f"{cd4.name}.txt", IT5 / "prompts" / f"{cd4.name}.txt")
        for arm in ARMS:
            for r in RUNS:
                rd = cd5 / arm / f"run-{r}"
                (rd / "outputs").mkdir(parents=True, exist_ok=True)
                cj = dict(case)
                if case.get("fixture"):
                    repo = rd / "inputs" / "repo"
                    if not (repo / ".git").exists():
                        b2.make_repo(repo)
                    cj["prompt"] = case["prompt"].replace("{REPO}", b2.win(str(repo).replace(b2.BS, "/")))
                    cj["executor_note"] = EXECUTOR_NOTE_FIXTURE
                    (rd / "prompt.txt").write_text(cj["prompt"], encoding="utf-8")
                (rd / "case.json").write_text(json.dumps(cj, indent=2), encoding="utf-8")
                made += 1
    print(f"iteration-5 scaffolded: {len(CASE_IDS)} cases x {len(ARMS)} arms x {len(RUNS)} runs = {made} executor runs")


if __name__ == "__main__":
    main()
