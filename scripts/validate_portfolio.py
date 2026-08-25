#!/usr/bin/env python3
"""Deterministic static and fixture validation for the portfolio package."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import yaml


ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SKILLS = (
    "sentence-clarity",
    "doc-typing",
    "memo-structure",
    "concision",
    "sentence-variety",
    "cohesion-emphasis",
    "usage-adjudicator",
)
REQUIRED_ROOT = (
    "README.md",
    "MANIFEST.sha256",
    "RESEARCH_REPORT.md",
    "portfolio-routing.md",
    "portfolio-pass-order.md",
    "glossary.md",
    "source-manifest.md",
    "source-map.md",
    "source-access-ledger.csv",
    "source-coverage-ledger.csv",
    "principle-registry.csv",
    "principle-registry.json",
    "claim-to-source-ledger.csv",
    "conflict-ledger.md",
    "trigger-matrix.csv",
    "defect-and-change-report.md",
    "validation-results.md",
    "negative-control/strunk-white-exclusion-dossier.md",
    "tests/end-to-end-fixtures.md",
    "tests/portfolio-fixtures.yaml",
    ".codex-plugin/plugin.json",
)
REQUIRED_PRINCIPLE_FIELDS = (
    "principle_id",
    "source_id",
    "author",
    "work",
    "edition",
    "chapter_or_section",
    "page_or_location",
    "author_term",
    "canonical_term",
    "writing_level",
    "fault_class",
    "reader_problem",
    "diagnostic_signal",
    "diagnostic_question",
    "revision_operation",
    "procedure",
    "conditions",
    "exceptions",
    "risks",
    "counterexamples",
    "evidence_type",
    "empirical_status",
    "skill_owner",
    "secondary_skill",
    "reference_only",
    "exclusion_reason",
    "example_ids",
    "test_ids",
    "confidence",
)
LEVELS = {
    "Document",
    "Section",
    "Paragraph",
    "Sentence",
    "Clause",
    "Phrase",
    "Word",
    "Usage or convention",
}
SOURCE_IDS = {"WB5", "WBL13", "LAN5", "GOPEN", "GS90", "TUF", "MIN96", "MIN26", "DIA", "GAR5", "STR18", "STR20", "SW4", "PULLUM", "PLAT"}
ID_RE = re.compile(r"\b(?:WB|LAN|GS|TUF|MIN|DIA|GAR|SW|PLAT)(?:-[A-Z]+)*-\d{2}\b")
RANGE_RE = re.compile(r"\b((?:WB|LAN|GS|TUF|MIN|DIA|GAR|SW|PLAT)(?:-[A-Z]+)*-)(\d{2})[–-](\d{2})\b")

errors: list[str] = []
checks: list[str] = []


def require(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation must aggregate errors
        errors.append(f"YAML parse failed: {path.relative_to(ROOT)}: {exc}")
        return None


for rel in REQUIRED_ROOT:
    require((ROOT / rel).is_file(), f"missing root artifact: {rel}")
checks.append(f"root_artifacts={len(REQUIRED_ROOT)}")

plugin = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
require(plugin.get("name") == "writing-quality-portfolio", "plugin name mismatch")
require(plugin.get("version") == "1.0.0", "plugin version mismatch")
require(plugin.get("skills") == "./skills/", "plugin skills path mismatch")
checks.append("plugin_manifest=valid")

registry = json.loads((ROOT / "principle-registry.json").read_text(encoding="utf-8"))
require(isinstance(registry, list) and len(registry) == 252, f"expected 252 principles, got {len(registry) if isinstance(registry, list) else 'non-list'}")
ids: set[str] = set()
for i, row in enumerate(registry, 1):
    missing = [field for field in REQUIRED_PRINCIPLE_FIELDS if field not in row]
    require(not missing, f"principle row {i} missing fields: {missing}")
    pid = row.get("principle_id", "")
    require(bool(pid) and pid not in ids, f"blank or duplicate principle_id at row {i}: {pid!r}")
    ids.add(pid)
    require(row.get("writing_level") in LEVELS, f"invalid writing level for {pid}: {row.get('writing_level')!r}")
    require(bool(row.get("skill_owner") or row.get("reference_only") or row.get("exclusion_reason")), f"principle lacks disposition: {pid}")
    require(bool(row.get("confidence")), f"principle lacks confidence: {pid}")
checks.append(f"principles={len(ids)}")

with (ROOT / "principle-registry.csv").open(encoding="utf-8", newline="") as handle:
    registry_csv = list(csv.DictReader(handle))
require(len(registry_csv) == len(registry), "principle CSV/JSON row-count mismatch")
require([row.get("principle_id") for row in registry_csv] == [row.get("principle_id") for row in registry], "principle CSV/JSON ordering or ID mismatch")
require(set(registry_csv[0]) == set(REQUIRED_PRINCIPLE_FIELDS), "principle CSV field set mismatch")
checks.append("principle_csv_json=aligned")

with (ROOT / "source-coverage-ledger.csv").open(encoding="utf-8", newline="") as handle:
    coverage = list(csv.DictReader(handle))
require(len(coverage) == 321, f"expected 321 coverage rows, got {len(coverage)}")
coverage_sources = {row["source_id"] for row in coverage}
require(SOURCE_IDS <= coverage_sources, f"coverage ledger missing sources: {sorted(SOURCE_IDS - coverage_sources)}")
require(all(row.get("access") and row.get("operational_disposition") for row in coverage), "coverage row lacks access or disposition")
checks.append(f"coverage_rows={len(coverage)}")

with (ROOT / "source-access-ledger.csv").open(encoding="utf-8", newline="") as handle:
    access = list(csv.DictReader(handle))
require(len(access) == 15, f"expected 15 access rows, got {len(access)}")
require(all(row.get("access") and row.get("retrieval_date") and row.get("confidence_matches_edition") for row in access), "access row lacks status/date/confidence")
checks.append(f"access_rows={len(access)}")

fixture_ids: set[str] = set()
all_fixture_kinds: set[str] = set()
for skill in SKILLS:
    directory = ROOT / "skills" / skill
    require(directory.is_dir(), f"missing skill directory: {skill}")
    skill_file = directory / "SKILL.md"
    agent_file = directory / "agents/openai.yaml"
    fixture_file = directory / "tests/fixtures.yaml"
    for path in (skill_file, agent_file, fixture_file, directory / "references/evidence-map.md", directory / "references/examples.md", directory / "references/principles.md"):
        require(path.is_file(), f"missing skill artifact: {path.relative_to(ROOT)}")
    if not skill_file.is_file():
        continue

    text = skill_file.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    require(bool(match), f"invalid frontmatter delimiters: {skill}/SKILL.md")
    if match:
        metadata = yaml.safe_load(match.group(1))
        require(metadata.get("name") == skill, f"frontmatter name mismatch: {skill}")
        description = metadata.get("description", "")
        require(isinstance(description, str) and 20 <= len(description) <= 1024, f"description length invalid: {skill}")
        require(set(metadata) <= {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}, f"unsupported frontmatter key: {skill}: {sorted(set(metadata) - {'name', 'description', 'license', 'compatibility', 'metadata', 'allowed-tools'})}")

    agent = load_yaml(agent_file)
    interface = agent.get("interface", {}) if isinstance(agent, dict) else {}
    require(all(interface.get(k) for k in ("display_name", "short_description", "default_prompt")), f"incomplete agents/openai.yaml: {skill}")
    require(f"${skill}" in interface.get("default_prompt", ""), f"default prompt must mention ${skill}")

    references = set(ID_RE.findall(text))
    for prefix, start, end in RANGE_RE.findall(text):
        references.update(f"{prefix}{n:02d}" for n in range(int(start), int(end) + 1))
    require(bool(references), f"SKILL.md has no principle IDs: {skill}")
    require(not (references - ids), f"unknown principle IDs in {skill}: {sorted(references - ids)}")
    require("references/evidence-map.md" in text, f"SKILL.md does not route to evidence map: {skill}")
    for rel in re.findall(r"`((?:references|tests|agents)/[^`]+)`", text):
        require((directory / rel).is_file(), f"broken skill-local reference: {skill}/{rel}")

    fixtures = load_yaml(fixture_file)
    require(isinstance(fixtures, dict) and fixtures.get("skill") == skill, f"fixture skill mismatch: {skill}")
    items = fixtures.get("fixtures", []) if isinstance(fixtures, dict) else []
    require(len(items) >= 10, f"too few fixtures for {skill}: {len(items)}")
    kinds = {item.get("kind") for item in items}
    all_fixture_kinds |= {kind for kind in kinds if kind}
    require("positive_activation" in kinds, f"missing positive activation fixture: {skill}")
    require("negative_activation" in kinds, f"missing negative activation fixture: {skill}")
    require(bool(kinds & {"boundary", "semantic_preservation", "minimal_intervention", "legitimate_passive", "uncertainty"}), f"missing boundary/preservation fixture: {skill}")
    for item in items:
        fid = item.get("id")
        require(bool(fid) and fid not in fixture_ids, f"blank or duplicate fixture id: {fid!r}")
        fixture_ids.add(fid)
        require(bool(item.get("expect")), f"fixture lacks expected behavior: {fid}")

    combined = "\n".join(path.read_text(encoding="utf-8") for path in directory.rglob("*.md"))
    require(not re.search(r"\b(?:TODO|TBD|TO BE COMPLETED)\b", combined, re.IGNORECASE), f"unfinished marker in {skill}")

checks.append(f"skills={len(SKILLS)}")
checks.append(f"skill_fixtures={len(fixture_ids)}")

portfolio_fixtures = load_yaml(ROOT / "tests/portfolio-fixtures.yaml")
portfolio_items = portfolio_fixtures.get("fixtures", []) if isinstance(portfolio_fixtures, dict) else []
require(len(portfolio_items) >= 14, f"expected at least 14 portfolio fixtures, got {len(portfolio_items)}")
portfolio_categories = {item.get("category") for item in portfolio_items}
for needed in ("routing", "cross_skill", "negative_control", "register_usage", "end_to_end"):
    require(needed in portfolio_categories, f"portfolio fixtures missing category: {needed}")
require(any("preserve" in (item.get("expected") or {}) for item in portfolio_items), "portfolio fixtures lack explicit semantic-preservation expectations")
portfolio_ids = [item.get("id") for item in portfolio_items]
require(all(portfolio_ids) and len(portfolio_ids) == len(set(portfolio_ids)), "portfolio fixture IDs are blank or duplicated")
checks.append(f"portfolio_fixtures={len(portfolio_items)}")

trigger_rows = list(csv.DictReader((ROOT / "trigger-matrix.csv").open(encoding="utf-8", newline="")))
require(len(trigger_rows) == 8, f"expected seven skill trigger rows plus coordinated pass, got {len(trigger_rows)}")
require({row.get("primary_skill") for row in trigger_rows if row.get("primary_skill")} >= set(SKILLS), "trigger matrix does not name every skill")
checks.append(f"trigger_rows={len(trigger_rows)}")

report = (ROOT / "RESEARCH_REPORT.md").read_text(encoding="utf-8")
for part in range(1, 15):
    require(f"Part {['I','II','III','IV','V','VI','VII','VIII','IX','X','XI','XII','XIII','XIV'][part - 1]}:" in report, f"research report missing Part {part}")
require("Full-text extraction of every requested copyrighted book | **Fail" in report, "completion statement does not disclose corpus-access failure")
checks.append("report_parts=14")

if errors:
    print("VALIDATION FAILED")
    for error in errors:
        print(f"- {error}")
    sys.exit(1)

print("VALIDATION PASSED")
for check in checks:
    print(f"- {check}")
