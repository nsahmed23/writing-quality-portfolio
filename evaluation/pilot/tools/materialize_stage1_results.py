"""Materialize one immutable Stage 1 report and human-review bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

from tools.prepare_stage1_jobs import encode_json, manifest_job_entries, publish_new_tree
from wqeval.corpus_evidence import verify_frozen_scoring_corpus
from wqeval.panel import build_verified_stage1_panel
from wqeval.review_packets import build_stage1_review_packets
from wqeval.roster_anchor import (
    HumanRosterAnchorError,
    human_roster_anchor_sha256,
    verify_human_roster_anchor,
)
from wqeval.storage import RawStore, _lexical_absolute
from wqeval.strict_json import loads


_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: str, *, label: str) -> str:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _thresholds(project_root: Path, expected_sha256: str) -> tuple[dict[str, Any], str]:
    expected = _digest(expected_sha256, label="expected thresholds")
    store = RawStore(project_root, authorized_root=project_root)
    _, target = store._target("config/thresholds.json")
    payload = store._read_regular_file(target, maximum_bytes=1_000_000)
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise ValueError("threshold configuration does not match the expected SHA-256")
    document = loads(payload)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "stage1", "stage2"}
        or document["schema_version"] != "1.0"
        or not isinstance(document["stage1"], dict)
        or not isinstance(document["stage2"], dict)
    ):
        raise ValueError("threshold configuration fields are invalid")
    return document["stage1"], observed


def _scoring_protocol_amendment(
    project_root: Path,
    expected_sha256: str,
) -> str:
    expected = _digest(expected_sha256, label="expected scoring protocol amendment")
    store = RawStore(project_root, authorized_root=project_root)
    _, target = store._target(".checkpoints/07a_scoring_protocol_amendment.json")
    try:
        payload = store._read_regular_file(target, maximum_bytes=1_000_000)
    except FileNotFoundError as error:
        raise ValueError("scoring protocol amendment checkpoint is missing") from error
    observed = hashlib.sha256(payload).hexdigest()
    if observed != expected:
        raise ValueError(
            "scoring protocol amendment checkpoint does not match the expected SHA-256"
        )
    document = loads(payload)
    if (
        not isinstance(document, dict)
        or document.get("schema_version") != "1.0"
        or document.get("checkpoint")
        != "stage1_scoring_protocol_prospective_safety_amendment"
        or document.get("status") != "frozen_before_human_review"
        or not isinstance(document.get("human_review_state_at_freeze"), dict)
        or document["human_review_state_at_freeze"].get("human_ratings_observed") != 0
        or document["human_review_state_at_freeze"].get(
            "human_adjudications_observed"
        )
        != 0
        or not isinstance(document.get("policy"), dict)
        or document["policy"].get("stage2_remains_locked") is not True
    ):
        raise ValueError("scoring protocol amendment checkpoint fields are invalid")
    return observed


def _load_json_under_root(
    path: str | Path,
    *,
    authorized_root: str | Path,
) -> dict[str, Any]:
    root = _lexical_absolute(authorized_root)
    target = _lexical_absolute(path)
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as error:
        raise ValueError("human roster anchor must be inside authorized_root") from error
    store = RawStore(root, authorized_root=root)
    _, safe_target = store._target(relative)
    value = loads(store._read_regular_file(safe_target, maximum_bytes=5_000_000))
    if not isinstance(value, dict):
        raise ValueError("human roster anchor must be a JSON object")
    return value


def _distribution_package(
    *,
    package_root: str,
    role: str,
    packet_name: str,
    packet: Any,
    template_name: str,
    template: Any,
    review_packet_id: str,
) -> dict[str, Any]:
    """Build one standalone, least-disclosure human-review package."""

    payloads = {
        packet_name: packet,
        template_name: template,
    }
    manifest_name = "distribution-manifest.json"
    manifest = {
        "schema_version": "1.0",
        "package_kind": "stage1_review_distribution",
        "status": "PENDING_HUMAN_REVIEW",
        "role": role,
        "review_packet_id": review_packet_id,
        "manifest_scope": (
            "package_paths enumerates every package member; files hashes every "
            "member except distribution-manifest.json"
        ),
        "package_paths": sorted([*payloads, manifest_name]),
        "files": manifest_job_entries(payloads),
    }
    return {
        **{
            f"{package_root}/{relative_path}": value
            for relative_path, value in payloads.items()
        },
        f"{package_root}/{manifest_name}": manifest,
    }


def materialize_stage1_results(
    *,
    project_root: str | Path,
    run_root: str | Path,
    expected_output_evidence_sha256: str,
    expected_corpus_freeze_sha256: str,
    expected_thresholds_sha256: str,
    expected_scoring_protocol_amendment_sha256: str,
    expected_runs: int,
    expected_systems: int,
    review_seed: int,
    destination_root: str | Path,
    authorized_root: str | Path,
    human_roster_anchor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish a provisional report, or anchored review packages as phase two."""

    project = _lexical_absolute(project_root)
    run = _lexical_absolute(run_root)
    destination = _lexical_absolute(destination_root)
    authorization = _lexical_absolute(authorized_root)
    try:
        destination.relative_to(run)
    except ValueError:
        pass
    else:
        raise ValueError("destination_root must not be inside the immutable run root")
    threshold_values, thresholds_file_sha256 = _thresholds(
        project,
        expected_thresholds_sha256,
    )
    scoring_protocol_amendment_sha256 = _scoring_protocol_amendment(
        project,
        expected_scoring_protocol_amendment_sha256,
    )
    corpus = verify_frozen_scoring_corpus(
        project,
        expected_freeze_manifest_sha256=_digest(
            expected_corpus_freeze_sha256,
            label="expected corpus freeze manifest",
        ),
        split="test",
    )
    panel = build_verified_stage1_panel(
        corpus,
        run_root=run,
        expected_output_evidence_sha256=_digest(
            expected_output_evidence_sha256,
            label="expected output evidence",
        ),
        expected_runs=expected_runs,
        expected_systems=expected_systems,
        thresholds=threshold_values,
    )
    report = panel.report
    evidence = {
        "corpus_freeze_sha256": corpus.freeze_manifest_sha256,
        "output_anchor_sha256": report["evidence"]["output_evidence_sha256"],
        "jobs_manifest_sha256": report["evidence"]["jobs_manifest_sha256"],
        "model_settings_sha256": report["evidence"]["model_settings_sha256"],
        "thresholds_file_sha256": thresholds_file_sha256,
        "thresholds_canonical_sha256": report["evidence"]["thresholds_sha256"],
        "panel_report_canonical_sha256": panel.report_sha256,
        "scoring_protocol_amendment_sha256": (
            scoring_protocol_amendment_sha256
        ),
    }
    execution_order_sha256 = report["evidence"].get("execution_order_sha256")
    if execution_order_sha256 is not None:
        evidence["execution_order_sha256"] = execution_order_sha256
    artifacts: dict[str, Any] = {
        "reports/stage1-provisional-report.json": report,
    }
    materialization_phase = "provisional_report_only"
    packet_id: str | None = None
    roster_anchor_sha256: str | None = None
    if human_roster_anchor is not None:
        try:
            verified_roster_anchor = verify_human_roster_anchor(
                human_roster_anchor,
                expected_source_panel_report_sha256=panel.report_sha256,
                expected_run_id=run.name,
            )
        except HumanRosterAnchorError as error:
            raise ValueError(str(error)) from error
        roster_anchor_sha256 = human_roster_anchor_sha256(verified_roster_anchor)
        review_bundle = build_stage1_review_packets(
            list(corpus.cases),
            list(corpus.gold),
            list(panel.predictions),
            seed=review_seed,
            evidence=evidence,
            human_roster_anchor=verified_roster_anchor,
            expected_run_id=run.name,
            system_prediction_bindings=[
                {
                    "system_id": evaluation.system_id,
                    "prediction_count": len(evaluation.predictions),
                    "change_count": sum(
                        prediction["decision"] == "CHANGE"
                        for prediction in evaluation.predictions
                    ),
                    "predictions_sha256": evaluation.predictions_sha256,
                }
                for evaluation in panel.evaluations
            ],
        )
        packet_id = review_bundle["manifest"]["packet_id"]
        panel_evidence = {
            "schema_version": "1.0",
            "status": "PILOT_UNADJUDICATED",
            "panel_report_canonical_sha256": panel.report_sha256,
            "scoring_protocol_amendment_sha256": (
                scoring_protocol_amendment_sha256
            ),
            "human_roster_anchor_sha256": roster_anchor_sha256,
            "review_packet_id": packet_id,
            "evaluations": [
                {
                    "system_id": evaluation.system_id,
                    "valid_run_numbers": list(evaluation.valid_run_numbers),
                    "invalid_run_numbers": list(evaluation.invalid_run_numbers),
                    "predictions_sha256": evaluation.predictions_sha256,
                    "gate_metrics_sha256": evaluation.gate_metrics_sha256,
                    "model_settings_sha256": evaluation.model_settings_sha256,
                }
                for evaluation in panel.evaluations
            ],
        }
        artifacts.update(
            {
                "private/review-bundle.json": review_bundle,
                "private/panel-evidence.json": panel_evidence,
            }
        )
        for package in (
            _distribution_package(
                package_root="distributions/diagnostic-reviewer",
                role="diagnostic_reviewer",
                packet_name="diagnostic-review-packet.json",
                packet=review_bundle["diagnostic_public"],
                template_name="diagnostic-reviewer-template.json",
                template=review_bundle["diagnostic_reviewer_template"],
                review_packet_id=packet_id,
            ),
            _distribution_package(
                package_root="distributions/diagnostic-adjudicator",
                role="diagnostic_adjudicator",
                packet_name="diagnostic-review-packet.json",
                packet=review_bundle["diagnostic_public"],
                template_name="diagnostic-adjudicator-template.json",
                template=review_bundle["diagnostic_adjudicator_template"],
                review_packet_id=packet_id,
            ),
            _distribution_package(
                package_root="distributions/gold-reviewer",
                role="gold_reviewer",
                packet_name="gold-review-packet.json",
                packet=review_bundle["gold_public"],
                template_name="gold-reviewer-template.json",
                template=review_bundle["gold_reviewer_template"],
                review_packet_id=packet_id,
            ),
            _distribution_package(
                package_root="distributions/gold-adjudicator",
                role="gold_adjudicator",
                packet_name="gold-review-packet.json",
                packet=review_bundle["gold_public"],
                template_name="gold-adjudicator-template.json",
                template=review_bundle["gold_adjudicator_template"],
                review_packet_id=packet_id,
            ),
        ):
            artifacts.update(package)
        materialization_phase = "review_packages"
    tree_manifest = {
        "schema_version": "1.0",
        "status": "PILOT_UNADJUDICATED",
        "materialization_phase": materialization_phase,
        "scoring_protocol_amendment_sha256": scoring_protocol_amendment_sha256,
        "manifest_scope": "all files except this tree-manifest.json",
        "files": manifest_job_entries(artifacts),
    }
    artifacts["tree-manifest.json"] = tree_manifest
    publish_new_tree(destination, artifacts, authorized_root=authorization)
    tree_manifest_payload = encode_json(tree_manifest)
    published_store = RawStore(destination, authorized_root=authorization)
    _, published_manifest = published_store._target("tree-manifest.json")
    published_payload = published_store._read_regular_file(
        published_manifest,
        maximum_bytes=5_000_000,
    )
    if published_payload != tree_manifest_payload:
        raise RuntimeError("published tree manifest differs from the prepared bytes")
    return {
        "schema_version": "1.0",
        "status": "PILOT_UNADJUDICATED",
        "materialization_phase": materialization_phase,
        "stage2_eligible": False,
        "destination_root": str(destination),
        "system_count": report["system_count"],
        "review_packet_id": packet_id,
        "human_roster_anchor_sha256": roster_anchor_sha256,
        "scoring_protocol_amendment_sha256": scoring_protocol_amendment_sha256,
        "panel_report_canonical_sha256": panel.report_sha256,
        "tree_manifest_sha256": hashlib.sha256(published_payload).hexdigest(),
        "file_count": len(artifacts),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--output-evidence-sha256", required=True)
    parser.add_argument("--corpus-freeze-sha256", required=True)
    parser.add_argument("--thresholds-sha256", required=True)
    parser.add_argument("--scoring-protocol-amendment-sha256", required=True)
    parser.add_argument("--expected-runs", type=int, required=True)
    parser.add_argument("--expected-systems", type=int, required=True)
    parser.add_argument("--review-seed", type=int, required=True)
    parser.add_argument("--destination-root", type=Path, required=True)
    parser.add_argument("--authorized-root", type=Path, required=True)
    parser.add_argument("--human-roster-anchor", type=Path)
    arguments = parser.parse_args(argv)
    try:
        human_roster_anchor = (
            _load_json_under_root(
                arguments.human_roster_anchor,
                authorized_root=arguments.authorized_root,
            )
            if arguments.human_roster_anchor is not None
            else None
        )
        summary = materialize_stage1_results(
            project_root=arguments.project_root,
            run_root=arguments.run_root,
            expected_output_evidence_sha256=arguments.output_evidence_sha256,
            expected_corpus_freeze_sha256=arguments.corpus_freeze_sha256,
            expected_thresholds_sha256=arguments.thresholds_sha256,
            expected_scoring_protocol_amendment_sha256=(
                arguments.scoring_protocol_amendment_sha256
            ),
            expected_runs=arguments.expected_runs,
            expected_systems=arguments.expected_systems,
            review_seed=arguments.review_seed,
            destination_root=arguments.destination_root,
            authorized_root=arguments.authorized_root,
            human_roster_anchor=human_roster_anchor,
        )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
