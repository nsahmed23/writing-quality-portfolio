"""Deterministic checks and document-level evidence aggregation."""

import random
from collections import Counter, defaultdict

from evaluation.benchmark_v2.anchors import AnchorError, resolve_anchor

from .contracts import strict_json, validate_suite


def check_text(text: str, checks: dict) -> list[dict]:
    """Literal candidate checks; a pass says nothing about semantic truth."""
    if not isinstance(text, str) or not isinstance(checks, dict):
        raise ValueError("invalid candidate/checks")
    results = []
    for index, literal in enumerate(checks.get("required", [])):
        passed = literal in text
        results.append({"id": f"required_{index}", "passed": passed,
                        "message": f"required literal {index} {'present' if passed else 'missing'}"})
    for index, literal in enumerate(checks.get("forbidden", [])):
        passed = literal not in text
        results.append({"id": f"forbidden_{index}", "passed": passed,
                        "message": f"forbidden literal {index} {'absent' if passed else 'present'}"})
    if "max_words" in checks:
        passed = len(text.split()) <= checks["max_words"]
        results.append({"id": "max_words", "passed": passed,
                        "message": f"candidate word count {'within' if passed else 'above'} limit"})
    if "exact" in checks:
        passed = text == checks["exact"]
        results.append({"id": "exact", "passed": passed,
                        "message": f"candidate {'matches' if passed else 'differs from'} exact output"})
    return results


def parse_judgment(raw: bytes, a: str, b: str) -> dict:
    """Validate a displayed-order model judgment without guessing intent."""
    try:
        value = strict_json(raw)
        if not isinstance(value, dict) or set(value) != {"winner", "reason", "evidence"}:
            raise ValueError("judgment fields must be winner/reason/evidence")
        winner = value["winner"]
        if winner not in ("A", "B", "tie", "both_bad"):
            raise ValueError("invalid winner")
        if not isinstance(value["reason"], str) or not value["reason"].strip():
            raise ValueError("reason is blank")
        evidence = value["evidence"]
        if not isinstance(evidence, list) or not evidence:
            raise ValueError("evidence must be nonempty")
        candidates = set()
        for item in evidence:
            if not isinstance(item, dict) or set(item) not in ({"candidate", "quote"}, {"candidate", "quote", "occurrence"}):
                raise ValueError("invalid evidence fields")
            candidate = item["candidate"]
            if candidate not in ("A", "B"):
                raise ValueError("invalid evidence candidate")
            quote = item["quote"]
            if not isinstance(quote, str) or not quote:
                raise ValueError("empty evidence quote")
            resolve_anchor(a if candidate == "A" else b, quote,
                           occurrence=item.get("occurrence"))
            candidates.add(candidate)
        if winner != "tie" and candidates != {"A", "B"}:
            raise ValueError("decisive or both_bad judgment requires both candidate quotes")
        return {"valid": True, "winner": winner, "error": None}
    except (ValueError, AnchorError) as exc:
        return {"valid": False, "winner": None, "error": str(exc)}


def _check(checks, identifier, passed, message):
    checks.append({"id": identifier, "passed": bool(passed), "message": message})


def _interval(values, seed):
    rng = random.Random(seed)
    n = len(values)
    samples = sorted(sum(rng.choice(values) for _ in range(n)) / n
                     for _ in range(2000))
    return samples[49], samples[1949]  # nearest empirical 2.5th / 97.5th


def build_report(suite: dict, records: list[dict], judges: list[dict], *, mode: str,
                 calibration: dict | None = None, execution: str = "live",
                 seed: int = 0) -> dict:
    """Aggregate canonical lowercase records, with one vote per document."""
    validate_suite(suite)
    if mode not in ("calibrate", "compare", "score") or execution not in ("live", "demo"):
        raise ValueError("invalid report mode or execution")
    if not isinstance(records, list) or not isinstance(judges, list) or not judges:
        raise ValueError("records and nonempty judges are required")
    judge_by_id = {}
    for judge in judges:
        if (not isinstance(judge, dict) or not isinstance(judge.get("id"), str) or
                not judge["id"].strip() or not isinstance(judge.get("family"), str) or
                not judge["family"].strip() or judge["id"] in judge_by_id):
            raise ValueError("judges require unique nonblank id and family")
        judge_by_id[judge["id"]] = judge
    split = "calibration" if mode == "calibrate" else "test"
    cases = [c for c in suite["cases"] if c["split"] == split and
             (mode != "calibrate" or c["expected"] is not None)]
    if mode == "score" and not cases:
        cases = list(suite["cases"])
    case_by_id = {c["id"]: c for c in cases}
    keys = {(c["id"], j, order) for c in cases for j in judge_by_id for order in (1, 2)}
    grouped = defaultdict(list)
    invalid = unexpected = 0
    for record in records:
        if not isinstance(record, dict):
            invalid += 1
            continue
        key = (record.get("case_id"), record.get("judge_id"), record.get("order"))
        if key not in keys:
            unexpected += 1
            continue
        case = case_by_id[key[0]]
        judge = judge_by_id[key[1]]
        if (record.get("document_id") != case["document_id"] or
                record.get("lane") != case["lane"] or record.get("split") != case["split"] or
                record.get("family") != judge["family"] or type(record.get("order")) is not int or
                type(record.get("valid")) is not bool or
                record.get("winner") not in ("a", "b", "tie", "both_bad", None) or
                (record["valid"] and record["winner"] is None) or
                (not record["valid"] and record["winner"] is not None)):
            invalid += 1
            continue
        grouped[key].append(record)
        if not record["valid"]:
            invalid += 1
    missing = len(keys - set(grouped))
    duplicates = sum(max(0, len(items) - 1) for items in grouped.values())
    complete = bool(cases) and not (missing or duplicates or invalid or unexpected)
    results = {}
    disagree = 0
    for case in cases:
        for judge in judges:
            r1 = grouped.get((case["id"], judge["id"], 1), [])
            r2 = grouped.get((case["id"], judge["id"], 2), [])
            stable = (len(r1) == len(r2) == 1 and r1[0]["valid"] and
                      r2[0]["valid"] and r1[0]["winner"] == r2[0]["winner"])
            if (len(r1) == len(r2) == 1 and r1[0]["valid"] and r2[0]["valid"]
                    and r1[0]["winner"] != r2[0]["winner"]):
                disagree += 1
            results[(case["id"], judge["id"])] = r1[0]["winner"] if stable else None
    by_judge, checks = {}, []
    for judge in judges:
        labeled = [c for c in cases if mode == "calibrate" and c["expected"] is not None]
        total = len(labeled)
        stable = sum(results[(c["id"], judge["id"])] is not None for c in labeled)
        correct = sum(results[(c["id"], judge["id"])] == c["expected"] for c in labeled)
        judge_complete = all(len(grouped.get((c["id"], judge["id"], order), [])) == 1 and
                             grouped[(c["id"], judge["id"], order)][0]["valid"]
                             for c in cases for order in (1, 2))
        accuracy = correct / total if total else None
        order_stability = stable / total if total else None
        eligible_judge = (mode == "calibrate" and judge_complete and total >= 8 and
                          len({c["document_id"] for c in labeled}) >= 4 and
                          accuracy is not None and accuracy >= .90 and order_stability >= .90)
        by_judge[judge["id"]] = {"family": judge["family"], "controls": total,
                                "documents": len({c["document_id"] for c in labeled}),
                                "complete": judge_complete, "eligible": eligible_judge}
        if total:
            by_judge[judge["id"]].update(accuracy=accuracy, order_stability=order_stability)
        if mode == "calibrate":
            judge_check_id = "calibration_judge_" + judge["id"].encode("utf-8").hex()
            _check(checks, judge_check_id, eligible_judge,
                   f"{total} controls, {by_judge[judge['id']]['documents']} documents; accuracy and order stability >=0.90")
    decisions = {}
    for case in cases:
        votes = [results[(case["id"], judge["id"])] for judge in judges]
        decisions[case["id"]] = votes[0] if votes[0] is not None and all(v == votes[0] for v in votes) else None
    candidate_fail = baseline_fail = 0
    for case in cases:
        candidate_fail += sum(not c["passed"] for c in check_text(case["b"], case["checks"]))
        baseline_fail += sum(not c["passed"] for c in check_text(case["a"], case["checks"]))
    counts = {"expected_records": len(keys), "received_records": len(records),
              "missing_records": missing, "duplicate_records": duplicates,
              "invalid_records": invalid, "unexpected_records": unexpected,
              "order_disagreements": disagree,
              "abstentions": sum(v is None for v in decisions.values()),
              "ties": sum(v == "tie" for v in decisions.values()),
              "both_bad": sum(v == "both_bad" for v in decisions.values()),
              "candidate_check_failures": candidate_fail,
              "baseline_check_failures": baseline_fail}
    _check(checks, "coverage", complete, "all expected case/judge/order records must be unique and valid")
    if mode == "compare":
        _check(checks, "judge_families", len({j["family"] for j in judges}) >= 2,
               "live comparison requires at least two independent judge families")
    if mode == "compare":
        certificate_ok = isinstance(calibration, dict) and calibration.get("eligible") is True and calibration.get("execution") == "live"
        _check(checks, "calibration_certificate", certificate_ok, "eligible live calibration required")
    else:
        certificate_ok = False
    by_lane = {}
    for lane in ("editing", "communication"):
        lane_cases = [c for c in cases if c["lane"] == lane]
        if not lane_cases:
            continue
        docs = defaultdict(list)
        for case in lane_cases:
            docs[case["document_id"]].append({"a": -1, "b": 1}.get(decisions[case["id"]], 0))
        values = [sum(v) / len(v) for v in docs.values()]
        mean = sum(values) / len(values)
        lower, upper = _interval(values, seed) if mode == "compare" else (None, None)
        lane_recommendation = "inconclusive"
        if mode == "compare" and len(docs) >= 5 and complete and certificate_ok and execution == "live" and len({j["family"] for j in judges}) >= 2:
            if lower > 0 and not candidate_fail:
                lane_recommendation = "candidate"
            elif upper < 0 and not baseline_fail:
                lane_recommendation = "baseline"
        by_lane[lane] = {"cases": len(lane_cases), "documents": len(docs),
                         "mean": mean, "recommendation": lane_recommendation}
        if lower is not None:
            by_lane[lane].update(ci_lower=lower, ci_upper=upper)
        if mode == "compare":
            _check(checks, f"lane_documents_{lane}", len(docs) >= 5,
                   "at least five independent documents required")
    _check(checks, "candidate_checks", candidate_fail == 0,
           f"{candidate_fail} literal candidate check failures")
    _check(checks, "baseline_checks", baseline_fail == 0,
           f"{baseline_fail} literal baseline check failures")
    _check(checks, "live_execution", execution == "live", "demo is software smoke evidence only")
    eligible = (complete and execution == "live" and
                (all(j["eligible"] for j in by_judge.values()) if mode == "calibrate" else
                 mode == "compare" and certificate_ok and len({j["family"] for j in judges}) >= 2 and
                 all(v["documents"] >= 5 for v in by_lane.values()) and bool(by_lane)))
    recommendation = "not_applicable" if mode != "compare" else "inconclusive"
    if mode == "compare" and eligible:
        if all(l["recommendation"] == "candidate" for l in by_lane.values()):
            recommendation = "candidate"
        elif any(l["recommendation"] == "baseline" for l in by_lane.values()) or candidate_fail:
            recommendation = "baseline" if not baseline_fail else "inconclusive"
    metrics = {}
    if mode == "calibrate" and by_judge:
        metrics["calibration_accuracy"] = min(j["accuracy"] for j in by_judge.values() if "accuracy" in j) if cases else None
        metrics["order_stability"] = min(j["order_stability"] for j in by_judge.values() if "order_stability" in j) if cases else None
        metrics = {key: value for key, value in metrics.items() if value is not None}
    return {"schema_version": 1, "evaluation_type": "automated_proxy",
            "execution": execution, "mode": mode, "complete": complete,
            "eligible": eligible, "recommendation": recommendation,
            "metrics": metrics, "checks": checks, "by_judge": by_judge,
            "by_lane": by_lane, "counts": counts}
