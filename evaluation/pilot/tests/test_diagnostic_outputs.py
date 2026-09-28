from __future__ import annotations

import unittest

from wqeval.validation import (
    ValidationError,
    flatten_diagnostic_outputs,
    validate_finding,
    validate_diagnostic_output,
    validate_diagnostic_output_set,
)

from tests.support import case


def output(case_id: str = "C001", *, decision: str = "CHANGE", findings: list[dict] | None = None) -> dict:
    if findings is None:
        findings = [
            {
                "finding_id": "F001",
                "start": 0,
                "end": 3,
                "span": "The",
                "decision": "CHANGE",
                "problem_name": "Vague reference",
                "system_issue_code": "vague_reference",
                "normalized_issue_code": "vague_reference",
                "context_explanation": "The antecedent is missing in this isolated sentence.",
                "severity": "medium",
                "suggested_operation": {
                    "operation_code": "resolve_reference",
                    "instruction": "Name the subject.",
                    "replacement": None,
                },
                "field_origin": "authored",
            }
        ]
    return {"schema_version": "1.0", "case_id": case_id, "case_decision": decision, "findings": findings}


class DiagnosticOutputTests(unittest.TestCase):
    def test_valid_change_and_empty_keep_outputs(self) -> None:
        source = case()
        validate_diagnostic_output(output(), source, allowed_normalized_codes={"vague_reference"})
        validate_diagnostic_output(output(decision="KEEP", findings=[]), source)

        unknown = output()
        unknown["findings"][0]["normalized_issue_code"] = "invented_family"
        with self.assertRaises(ValidationError):
            validate_diagnostic_output(unknown, source, allowed_normalized_codes={"vague_reference"})

        unmapped = output()
        unmapped["findings"][0]["normalized_issue_code"] = "UNMAPPED"
        validate_diagnostic_output(unmapped, source, allowed_normalized_codes={"vague_reference"})

        safe_keep = output(decision="KEEP")
        safe_keep["findings"][0]["decision"] = "KEEP"
        safe_keep["findings"][0]["suggested_operation"] = {
            "operation_code": "preserve",
            "instruction": "Preserve the construction as written.",
            "replacement": None,
        }
        validate_diagnostic_output(safe_keep, source)

        destructive_keep = output(decision="KEEP")
        destructive_keep["findings"][0]["decision"] = "KEEP"
        destructive_keep["findings"][0]["suggested_operation"] = {
            "operation_code": "delete",
            "instruction": "Delete the legitimate construction.",
            "replacement": "",
        }
        with self.assertRaises(ValidationError):
            validate_diagnostic_output(destructive_keep, source)

    def test_case_decision_duplicate_ids_and_unknown_fields_fail(self) -> None:
        source = case()
        inconsistent = output(decision="KEEP")
        duplicate = output(findings=output()["findings"] * 2)
        unknown = dict(output(), score=91)
        redundant_nested = output()
        redundant_nested["findings"][0]["schema_version"] = "1.0"
        redundant_nested["findings"][0]["case_id"] = "C001"
        for item in (inconsistent, duplicate, unknown, redundant_nested):
            with self.subTest(item=item), self.assertRaises(ValidationError):
                validate_diagnostic_output(item, source)

    def test_output_set_requires_every_case_exactly_once(self) -> None:
        cases = [case("C001"), case("C002", "The API passed.")]
        records = [output("C001"), output("C002", decision="KEEP", findings=[])]
        validate_diagnostic_output_set(records, cases)
        with self.assertRaises(ValidationError):
            validate_diagnostic_output_set(records[:1], cases)
        with self.assertRaises(ValidationError):
            validate_diagnostic_output_set(records + [records[0]], cases)

    def test_flattening_preserves_finding_fields_and_provenance(self) -> None:
        records = [output(), output("C002", decision="KEEP", findings=[])]
        flattened = flatten_diagnostic_outputs(records, system_id="union", run_number=2)
        self.assertEqual(len(flattened), 1)
        self.assertEqual(flattened[0]["case_id"], "C001")
        self.assertEqual(flattened[0]["system_id"], "union")
        self.assertEqual(flattened[0]["run_number"], 2)
        self.assertEqual(flattened[0]["normalized_issue_code"], "vague_reference")
        validate_finding(flattened[0], case())


if __name__ == "__main__":
    unittest.main()
