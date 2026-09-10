"""Blind pairwise for the v5 targeted rerun: an iteration-5 arm against the same arm's iteration-4 replies (v5 vs v4),
same protocol as pairwise4 (seeded order, both orders, winner only when it survives reversal, answer key from case.json).

Usage:
  py -3.11 pairwise5.py --lane codex|agy --arm full|short [--case N] [--dry-run] [--no-tools]
  py -3.11 pairwise5.py --summary
Outputs: iteration-5/pairwise/<arm>-v5-vs-v4/<lane>/<case>-run-N-orderK.json
"""
import json
import random
import subprocess
import sys
from pathlib import Path

from pairwise import JUDGE_TEMPLATE, parse_verdict, run_lane

WS = Path(__file__).resolve().parent
IT5, IT4 = WS / "iteration-5", WS / "iteration-4"


def load_pairs(arm: str, only_case=None):
    pairs = []
    for cd in sorted(IT5.glob("case-*")):
        case = json.loads((cd / "case.json").read_text(encoding="utf-8"))
        if only_case is not None and case["id"] != only_case:
            continue
        for rd in sorted((cd / arm).glob("run-*")):
            ra = rd / "outputs" / "response.md"
            rb = IT4 / cd.name / arm / rd.name / "outputs" / "response.md"
            if ra.exists() and rb.exists():
                run_case = json.loads((rd / "case.json").read_text(encoding="utf-8"))
                pairs.append({"case": case, "run": rd.name, "request": run_case["prompt"],
                              "a": ra.read_text(encoding="utf-8"), "b": rb.read_text(encoding="utf-8")})
    return pairs


def judge(lane: str, arm: str, only_case=None, dry=False):
    out_dir = IT5 / "pairwise" / f"{arm}-v5-vs-v4" / lane
    out_dir.mkdir(parents=True, exist_ok=True)
    va, vb = f"{arm}-v5", f"{arm}-v4"
    for pair in load_pairs(arm, only_case):
        name_base = f"{pair['case']['name']}-{pair['run']}"
        for order in (1, 2):
            target = out_dir / f"{name_base}-order{order}.json"
            if target.exists() and json.loads(target.read_text(encoding="utf-8")).get("verdict"):
                continue
            rnd = random.Random(f"{name_base}-{va}-{vb}")
            a_first = rnd.random() < 0.5
            if order == 2:
                a_first = not a_first
            r1, r2 = (pair["a"], pair["b"]) if a_first else (pair["b"], pair["a"])
            mapping = {"1": va if a_first else vb, "2": vb if a_first else va}
            key = pair["case"]["expected"]
            prompt = JUDGE_TEMPLATE.format(request=pair["request"], first=key["first"], truth=key["truth"], r1=r1, r2=r2)
            if "--no-tools" in sys.argv:
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
            rec = {"lane": lane, "arms": [va, vb], "case_id": pair["case"]["id"], "case_name": pair["case"]["name"], "kind": pair["case"]["kind"],
                   "run": pair["run"], "order": order, "mapping": mapping, "verdict": verdict,
                   "winner_arm": (mapping.get(verdict["winner"]) if verdict and verdict["winner"] in ("1", "2") else (verdict["winner"] if verdict else None)),
                   "seconds": secs, "raw_tail": raw[-1200:]}
            target.write_text(json.dumps(rec, indent=2), encoding="utf-8")
            print(f"{lane} {va}-vs-{vb} {name_base} order{order}: {rec['winner_arm']} ({secs}s)")


def summary():
    root = IT5 / "pairwise"
    print(f"{'pair':16s} {'lane':6s} {'case':34s} v5   v4   tie  both_bad  inconsistent  incomplete")
    totals = {}
    for pair_dir in sorted(root.glob("*-v5-vs-v4")):
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
                elif a == b and a == arms[0]:
                    res = "v5"
                elif a == b and a == arms[1]:
                    res = "v4"
                elif a == b:
                    res = a
                else:
                    res = "inconsistent"
                per_case.setdefault(cn, []).append(res)
            for cn, res in per_case.items():
                c = {k: res.count(k) for k in ("v5", "v4", "tie", "both_unacceptable", "inconsistent", "incomplete")}
                print(f"{pair_dir.name:16s} {lane_dir.name:6s} {cn[:34]:34s} {c['v5']:^4d} {c['v4']:^4d} {c['tie']:^4d} {c['both_unacceptable']:^8d} {c['inconsistent']:^12d} {c['incomplete']:^10d}")
                t = totals.setdefault((pair_dir.name, lane_dir.name), {k: 0 for k in c})
                for k, v in c.items():
                    t[k] += v
    print("--- totals:")
    for k, v in totals.items():
        print(f"  {k[0]} / {k[1]}: {v}")
    (root / "summary5.json").write_text(json.dumps({f"{k[0]}/{k[1]}": v for k, v in totals.items()}, indent=2), encoding="utf-8")


def main():
    if "--summary" in sys.argv:
        summary()
        return
    lane = sys.argv[sys.argv.index("--lane") + 1]
    arm = sys.argv[sys.argv.index("--arm") + 1]
    only_case = int(sys.argv[sys.argv.index("--case") + 1]) if "--case" in sys.argv else None
    judge(lane, arm, only_case, dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
