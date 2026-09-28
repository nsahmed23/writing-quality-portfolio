#!/usr/bin/env python3
"""Independently recount preserved pilot arithmetic without evaluator imports or model calls.

From the repository root: python evaluation/status/recount_pilot.py
An alternate checkout can be supplied with --repo-root PATH.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re


def read_jsonl(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def overlaps(left, right):
    """Offsets denote half-open Unicode codepoint ranges."""
    return left["start"] < right["end"] and right["start"] < left["end"]


def exact(left, right):
    return (
        left["start"] == right["start"]
        and left["end"] == right["end"]
        and left["normalized_issue_code"] == right["normalized_issue_code"]
    )


def same_code_overlap(left, right):
    return overlaps(left, right) and left["normalized_issue_code"] == right["normalized_issue_code"]


def maximum_pairs(predictions, gold, criterion):
    """Find a maximum-cardinality one-to-one pairing for one matching rule."""
    edges = [[j for j, item in enumerate(gold) if criterion(pred, item)]
             for pred in predictions]
    assigned = {}

    def augment(i, seen):
        for j in edges[i]:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or augment(assigned[j], seen):
                assigned[j] = i
                return True
        return False

    for i in range(len(predictions)):
        augment(i, set())
    return [(predictions[i], gold[j]) for j, i in assigned.items()]


def recount(repo_root):
    pilot = repo_root / "evaluation/pilot"
    cases = {split: read_jsonl(pilot / f"corpus/cases.{split}.jsonl")
             for split in ("dev", "test")}
    private_gold = {split: read_jsonl(pilot / f"private/gold/gold.{split}.jsonl")
                    for split in ("dev", "test")}
    decisions = {item["case_id"]: item["case_decision"]
                 for split in ("dev", "test") for item in private_gold[split]}
    for split in ("dev", "test"):
        outcomes = Counter()
        errors = []
        for case in cases[split]:
            suffix = int(re.search(r"-(\d{3})$", case["case_id"]).group(1))
            predicted = "CHANGE" if suffix <= 5 else "KEEP"
            actual = decisions[case["case_id"]]
            outcomes[(predicted, actual)] += 1
            if predicted != actual:
                errors.append(case["case_id"])
        print(f"suffix {split}: {len(cases[split])} cases, "
              f"CHANGE/CHANGE={outcomes['CHANGE', 'CHANGE']}, "
              f"KEEP/KEEP={outcomes['KEEP', 'KEEP']}, mismatches={errors}")

    gold_by_case = defaultdict(list)
    for item in read_jsonl(pilot / "private/gold/scoring.test.jsonl"):
        if item["decision"] == "CHANGE":
            gold_by_case[item["case_id"]].append(item)

    public = json.loads((pilot / "taxonomy/problem-families.json").read_text(encoding="utf-8"))
    native = json.loads((pilot / "taxonomy/native-map.json").read_text(encoding="utf-8"))
    native_outputs = set(native["gold_issue_family_to_normalized"].values())
    public_change = {item["code"] for item in public["change_families"]}
    unreachable = public_change - native_outputs
    print(f"taxonomy: {len(public_change) + len(public['keep_families'])} public codes, "
          f"{len(native_outputs)} distinct native-map outputs, "
          f"{len(unreachable)} unreachable public CHANGE codes: {sorted(unreachable)}")

    normalized = sorted((pilot / "runs/stage1-sealed-v1/normalized").glob("*.jsonl"))
    scores = {name: Counter() for name in ("exact", "same_code_overlap", "any_overlap")}
    criteria = {"exact": exact, "same_code_overlap": same_code_overlap,
                "any_overlap": overlaps}
    containment = Counter()
    unreachable_counts = Counter()
    critical = Counter()
    total = Counter()
    unreachable_with_overlap = 0
    for path in normalized:
        predictions = defaultdict(list)
        for item in read_jsonl(path):
            if item["decision"] == "CHANGE":
                predictions[item["case_id"]].append(item)
        for case in cases["test"]:
            case_id = case["case_id"]
            pred = predictions[case_id]
            gold = gold_by_case[case_id]
            total["predicted_change"] += len(pred)
            total["gold_change"] += len(gold)
            for name, criterion in criteria.items():
                pairs = maximum_pairs(pred, gold, criterion)
                scores[name]["TP"] += len(pairs)
                scores[name]["FP"] += len(pred) - len(pairs)
                scores[name]["FN"] += len(gold) - len(pairs)
                if name == "same_code_overlap":
                    for found, target in pairs:
                        if exact(found, target):
                            continue
                        if found["start"] <= target["start"] and found["end"] >= target["end"]:
                            containment["prediction_encloses"] += 1
                        elif target["start"] <= found["start"] and target["end"] >= found["end"]:
                            containment["prediction_narrower"] += 1
                        else:
                            containment["crossing"] += 1
            for found in pred:
                if found["normalized_issue_code"] in unreachable:
                    unreachable_counts[found["normalized_issue_code"]] += 1
                    unreachable_with_overlap += any(overlaps(found, target) for target in gold)
            for target in gold:
                if target["severity"] == "critical":
                    critical["opportunities"] += 1
                    critical["any_overlap"] += any(overlaps(found, target) for found in pred)
                    critical["exact"] += any(exact(found, target) for found in pred)

    print(f"valid normalized runs: {len(normalized)}; findings: {dict(total)}")
    for name, score in scores.items():
        print(f"{name}: TP={score['TP']} FP={score['FP']} FN={score['FN']}")
    print(f"same-code extra containment: {dict(containment)}")
    print(f"unreachable predictions: {sum(unreachable_counts.values())}, "
          f"by code={dict(sorted(unreachable_counts.items()))}, "
          f"overlapping gold CHANGE={unreachable_with_overlap}")
    print(f"critical: {dict(critical)}")

    source = pilot / "runs/stage1-sealed-v1/raw"
    inbox = pilot / "runs/stage1-sealed-v1/inbox"
    raw_files = sorted(source.glob("*.jsonl"))
    inbox_files = sorted(inbox.glob("*.jsonl"))
    differences = sorted(
        set(p.name for p in raw_files) ^ set(p.name for p in inbox_files)
        | {p.name for p in raw_files if (inbox / p.name).exists()
           and p.read_bytes() != (inbox / p.name).read_bytes()}
    )
    digest = hashlib.sha256()
    for path in raw_files:
        digest.update(path.read_bytes())
    print(f"raw/inbox: {len(raw_files)}/{len(inbox_files)} files, "
          f"byte differences={differences}; concatenated sorted raw SHA-256={digest.hexdigest()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    recount(args.repo_root.resolve())


if __name__ == "__main__":
    main()
