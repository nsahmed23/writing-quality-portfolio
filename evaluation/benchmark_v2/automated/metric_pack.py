"""Local Plugin Eval extension for an explicitly selected automated proxy report.

This reads existing files only. It neither invokes a judge nor changes Plugin Eval's
core score. WQ_EVAL_REPORT is deliberately mandatory to avoid implicit stale runs.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys


HEX = re.compile(r"[0-9a-f]{64}\Z")


class InvalidEvidence(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidEvidence(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value):
    raise InvalidEvidence(f"nonfinite JSON value: {value}")


def _digest(value, name):
    if not isinstance(value, str) or HEX.fullmatch(value) is None:
        raise InvalidEvidence(f"missing or invalid {name}")


def _finite_tree(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise InvalidEvidence("nonfinite report number")
    if isinstance(value, dict):
        for member in value.values():
            _finite_tree(member)
    elif isinstance(value, list):
        for member in value:
            _finite_tree(member)


def _validate(report):
    if not isinstance(report, dict):
        raise InvalidEvidence("report must be an object")
    _finite_tree(report)
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        raise InvalidEvidence("unsupported report schema_version")
    if report.get("evaluation_type") != "automated_proxy":
        raise InvalidEvidence("report is not automated_proxy")
    if report.get("execution") not in ("live", "demo"):
        raise InvalidEvidence("invalid report execution")
    if report.get("mode") not in ("calibrate", "compare", "score"):
        raise InvalidEvidence("invalid report mode")
    if any(type(report.get(key)) is not bool for key in ("complete", "eligible")):
        raise InvalidEvidence("complete and eligible must be booleans")
    if report.get("recommendation") not in ("candidate", "baseline", "inconclusive", "not_applicable"):
        raise InvalidEvidence("invalid recommendation")
    if any(not isinstance(report.get(key), dict) for key in ("metrics", "by_judge", "by_lane", "counts")):
        raise InvalidEvidence("metrics, by_judge, by_lane and counts must be objects")
    for key, value in report["metrics"].items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise InvalidEvidence("invalid metric ID")
        if type(value) not in (int, float) or not math.isfinite(value):
            raise InvalidEvidence(f"metric {key} must be finite and numeric")
    checks = report.get("checks")
    if not isinstance(checks, list):
        raise InvalidEvidence("checks must be an array")
    ids = set()
    for item in checks:
        if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", item["id"])
                or type(item.get("passed")) is not bool
                or not isinstance(item.get("message"), str)):
            raise InvalidEvidence("invalid check")
        if item["id"] in ids:
            raise InvalidEvidence("duplicate check ID")
        ids.add(item["id"])
    provenance = report.get("provenance")
    if not isinstance(provenance, dict):
        raise InvalidEvidence("missing provenance")
    for key in ("suite_sha256", "rubric_sha256", "config_sha256", "judge_signature"):
        _digest(provenance.get(key), key)
    candidate_hash = provenance.get("candidate_skill_sha256")
    if candidate_hash is not None:
        _digest(candidate_hash, "candidate_skill_sha256")
    if report["mode"] == "compare" and report["execution"] == "live":
        _digest(candidate_hash, "candidate_skill_sha256")
    return report


def _target_skill(target, kind):
    if kind not in ("skill", "plugin"):
        raise InvalidEvidence(f"unsupported target kind: {kind}")
    path = Path(target)
    if path.is_file() and path.name == "SKILL.md" and kind == "skill":
        return path
    if kind == "skill" and path.is_dir():
        return path / "SKILL.md"
    if kind == "plugin" and path.is_dir():
        candidates = list(path.glob("skills/*/SKILL.md"))
        if len(candidates) != 1:
            raise InvalidEvidence("plugin target needs exactly one skill; analyze the specific skill for a portfolio")
        return candidates[0]
    raise InvalidEvidence("target has no unambiguous SKILL.md")


def _warning(message):
    return {"checks": [{"id": "wq-automated-evidence", "category": "custom",
                        "severity": "warning", "status": "warn", "message": message,
                        "evidence": [], "remediation": ["Select a fresh live compare report with WQ_EVAL_REPORT and re-run analyze."]}],
            "metrics": [], "artifacts": []}


def analyze(target, kind, report_path=None):
    selected = report_path if report_path is not None else os.environ.get("WQ_EVAL_REPORT")
    if not selected:
        return _warning("WQ_EVAL_REPORT is required; no existing comparison was selected.")
    try:
        report_file = Path(selected).expanduser().resolve(strict=True)
        report = _validate(json.loads(report_file.read_text(encoding="utf-8"),
                                      object_pairs_hook=_unique, parse_constant=_reject_constant))
        skill_path = _target_skill(target, kind)
        digest = hashlib.sha256(skill_path.read_bytes()).hexdigest()
        recorded = report["provenance"].get("candidate_skill_sha256")
        if report["execution"] != "live" or report["mode"] != "compare":
            return _warning("Calibration or demo report is informative only; no quality pass is available.")
        if recorded != digest:
            return _warning("Candidate SKILL.md hash differs from the selected report; evidence is stale or mismatched.")
    except (OSError, UnicodeError, json.JSONDecodeError, InvalidEvidence) as exc:
        return _warning(f"Cannot use selected automated report: {exc}")

    lanes = report["by_lane"]
    lane_gate = bool(lanes) and all(
        isinstance(value, dict) and value.get("recommendation") == "candidate"
        and type(value.get("documents")) is int and value["documents"] >= 5
        and type(value.get("ci_lower")) in (int, float) and value["ci_lower"] > 0
        for value in lanes.values())
    allowed = (report["complete"] and report["eligible"] and lane_gate
               and report["recommendation"] == "candidate"
               and bool(report["checks"])
               and all(c["passed"] for c in report["checks"] if c["id"] != "baseline_checks"))
    message = ("Eligible live comparison recommends this exact candidate."
               if allowed else "Live comparison does not establish a candidate recommendation.")
    checks = [{"id": "wq-automated-evidence", "category": "custom",
               "severity": "info" if allowed else "warning",
               "status": "pass" if allowed else "warn", "message": message,
               "evidence": [f"report: {report_file}", f"candidate_skill_sha256: {digest}"],
               "remediation": []}]
    for item in report["checks"]:
        checks.append({"id": "wq-automated-" + item["id"], "category": "custom",
                       "severity": "info" if allowed and item["passed"] else "warning",
                       "status": "pass" if allowed and item["passed"] else "warn",
                       "message": item["message"], "evidence": [], "remediation": []})
    metrics = [{"id": "wq-automated-" + key.replace("_", "-"),
                "category": "custom", "value": value, "unit": "proxy", "band": "informational"}
               for key, value in sorted(report["metrics"].items())]
    for lane in ("editing", "communication"):
        lane_data = report["by_lane"].get(lane)
        if not isinstance(lane_data, dict):
            continue
        for key in ("cases", "documents", "mean", "ci_lower", "ci_upper"):
            value = lane_data.get(key)
            if type(value) in (int, float) and math.isfinite(value):
                metrics.append({"id": f"wq-automated-{lane}-{key.replace('_', '-')}",
                                "category": "custom", "value": value,
                                "unit": "count" if key in ("cases", "documents") else "proxy",
                                "band": "informational"})
    return {"checks": checks, "metrics": metrics,
            "artifacts": [{"id": "wq-automated-report", "type": "custom",
                           "label": "Automated proxy report", "description": str(report_file)}]}


def main():
    if len(sys.argv) != 3:
        result = _warning("Expected target path and target kind arguments.")
    else:
        result = analyze(sys.argv[1], sys.argv[2])
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
