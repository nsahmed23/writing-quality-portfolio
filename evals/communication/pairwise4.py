"""Blind pairwise judging for iteration-4 across arbitrary arm pairs, reusing pairwise.py's lanes and protocol.

Usage:
  py -3.11 pairwise4.py iteration-4 --lane codex|agy|kimi --arms full,none [--case N] [--dry-run]
  py -3.11 pairwise4.py iteration-4 --summary

Each pair: arm A run-N vs arm B run-N for the same case, judged twice with reversed order; a winner counts only
when it survives reversal. The answer key comes from case.json "expected" (first, truth), written without the skill.
"""
import json
import random
import subprocess
import sys
from pathlib import Path

from pairwise import JUDGE_TEMPLATE, LANES, STDIN_LANES, SCRATCH, parse_verdict, run_lane


def load_pairs(it: Path, arm_a: str, arm_b: str, only_case=None):
    pairs = []
    for cd in sorted(it.glob("case-*")):
        case = json.loads((cd / "case.json").read_text(encoding="utf-8"))
        if only_case is not None and case["id"] != only_case:
            continue
        for rd in sorted((cd / arm_a).glob("run-*")):
            ra = rd / "outputs" / "response.md"
            rb = cd / arm_b / rd.name / "outputs" / "response.md"
            if ra.exists() and rb.exists():
                run_case = json.loads((rd / "case.json").read_text(encoding="utf-8"))
                pairs.append({"case": case, "run": rd.name, "request": run_case["prompt"],
                              "a": ra.read_text(encoding="utf-8"), "b": rb.read_text(encoding="utf-8")})
    return pairs


def judge(it: Path, lane: str, arm_a: str, arm_b: str, only_case=None, dry=False):
    out_dir = it / "pairwise" / f"{arm_a}-vs-{arm_b}" / lane
    out_dir.mkdir(parents=True, exist_ok=True)
    for pair in load_pairs(it, arm_a, arm_b, only_case):
        name_base = f"{pair['case']['name']}-{pair['run']}"
        for order in (1, 2):
            target = out_dir / f"{name_base}-order{order}.json"
            if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("verdict"):
                continue
            rnd = random.Random(f"{name_base}-{arm_a}-{arm_b}")
            a_first = rnd.random() < 0.5
            if order == 2:
                a_first = not a_first
            r1, r2 = (pair["a"], pair["b"]) if a_first else (pair["b"], pair["a"])
            mapping = {"1": arm_a if a_first else arm_b, "2": arm_b if a_first else arm_a}
            key = pair["case"]["expected"]
            prompt = JUDGE_TEMPLATE.format(request=pair["request"], first=key["first"], truth=key["truth"], r1=r1, r2=r2)
            if "--no-tools" in sys.argv:  # retry aid for headless judges that try to run commands and get auto-denied
                prompt += chr(10) + "Judge from the text above alone. Do not run any command or tool; you have no repository access."
            if dry:
                print(f"DRY {lane} {name_base} order{order} chars={len(prompt)} mapping={mapping}")
                continue
            verdict, raw, secs = None, "", 0
            for _ in (1, 2):
                try:
                    raw, secs = run_lane(lane, prompt)
                    verdict = parse_verdict(raw)
                except subprocess.TimeoutExpired:
                    raw, secs = "TIMEOUT", 300
                if verdict:
                    break
            rec = {"lane": lane, "arms": [arm_a, arm_b], "case_id": pair["case"]["id"], "case_name": pair["case"]["name"], "kind": pair["case"]["kind"],
                   "run": pair["run"], "order": order, "mapping": mapping, "verdict": verdict,
                   "winner_arm": (mapping.get(verdict["winner"]) if verdict and verdict["winner"] in ("1", "2") else (verdict["winner"] if verdict else None)),
                   "seconds": secs, "raw_tail": raw[-1200:]}
            target.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(f"{lane} {arm_a}-vs-{arm_b} {name_base} order{order}: {rec['winner_arm']} ({secs}s)")


def summary(it: Path):
    root = it / "pairwise"
    print(f"{'pair':16s} {'lane':6s} {'case':34s} A-wins B-wins tie both_bad inconsistent")
    totals = {}
    for pair_dir in sorted(root.glob("*-vs-*")):
        for lane_dir in sorted(p for p in pair_dir.iterdir() if p.is_dir()):
            by = {}
            for p in lane_dir.glob("*.json"):
                r = json.loads(p.read_text(encoding="utf-8"))
                by.setdefault((r["case_name"], r["run"]), {"arms": r["arms"]})[r["order"]] = r["winner_arm"]
            per_case = {}
            for (cn, run), o in sorted(by.items()):
                a, b = o.get(1), o.get(2)
                arms = o["arms"]
                if a is None or b is None:
                    res = "incomplete"
                elif a == b and a in arms:
                    res = "A" if a == arms[0] else "B"
                elif a == b:
                    res = a  # tie or both_unacceptable
                else:
                    res = "inconsistent"
                per_case.setdefault(cn, []).append(res)
            for cn, res in per_case.items():
                c = {k: res.count(k) for k in ("A", "B", "tie", "both_unacceptable", "inconsistent")}
                print(f"{pair_dir.name:16s} {lane_dir.name:6s} {cn[:34]:34s} {c['A']:^6d} {c['B']:^6d} {c['tie']:^3d} {c['both_unacceptable']:^8d} {c['inconsistent']:^12d}")
                t = totals.setdefault((pair_dir.name, lane_dir.name), {k: 0 for k in c})
                for k, v in c.items():
                    t[k] += v
    print("--- totals (A = first arm in the pair name):")
    for k, v in totals.items():
        print(f"  {k[0]} / {k[1]}: {v}")
    (root / "summary4.json").write_text(json.dumps({f"{k[0]}/{k[1]}": v for k, v in totals.items()}, indent=2), encoding="utf-8")


def main():
    it = Path(sys.argv[1])
    if "--summary" in sys.argv:
        summary(it)
        return
    lane = sys.argv[sys.argv.index("--lane") + 1]
    arm_a, arm_b = sys.argv[sys.argv.index("--arms") + 1].split(",")
    only_case = int(sys.argv[sys.argv.index("--case") + 1]) if "--case" in sys.argv else None
    judge(it, lane, arm_a, arm_b, only_case, dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
