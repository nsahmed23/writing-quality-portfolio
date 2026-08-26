# Human-review gate hardening implementation record

## Status

The preserved pilot implements this pre-review hardening as a prospective protocol amendment. It is not part of the original preregistration. The amendment was frozen before any human ratings were collected, so no rating data was migrated or reinterpreted.

The implementation computes complete acceptance across all six adjudicated components, applies the 0.80 threshold copied from the already frozen exact-precision gate, binds the frozen roster anchor into packet identity, and verifies completed review packets against the bound anchor. The corresponding RED tests are present and pass in the preserved pilot.

Residual limits remain. No human review has been run, local hashes cannot prove reviewer identity, and Stage 2 remains locked. Any future benchmark-v2 changes beyond this preserved amendment are unimplemented unless separately identified and tested.

## Problem

The future human gate must not confuse reviewer agreement with finding acceptance. Two reviewers can agree perfectly that every finding is invalid. The roster also needs to be bound before review so a caller cannot supply a different roster and a matching digest in the same invocation.

## Implemented acceptance gate

Define `human_finding_acceptance_rate` as the share of findings for which all six adjudicated components are true:

- `finding_valid`;
- `span_valid`;
- `problem_valid`;
- `context_valid`;
- `severity_valid`;
- `operation_valid`.

The amendment uses 0.80 as a prospective threshold and records that it was copied mechanically from the already frozen exact-precision threshold before any human ratings existed. The original threshold file and the amendment checkpoint preserve the relevant hashes.

Agreement remains descriptive and separate. Perfect agreement with zero accepted findings must fail.

For a system with no CHANGE findings, acceptance is not applicable rather than an invented 1.0. Recall and other objective gates continue to control eligibility.

## Implemented roster trust sequence

1. Confirm real reviewer identities outside the evaluator.
2. Freeze a private pre-review roster anchor containing exact identities, attestations, run ID, source panel hash, anchor kind, and frozen status.
3. Bind the roster-anchor digest into the review packet identity.
4. Freeze a detached packet checkpoint before distributing forms.
5. During completed review assembly, derive the expected roster digest only from the bound packet manifest.

A caller may supply the anchor document for verification, but cannot supply or select its expected digest. Changing the roster changes the packet identity and cannot match the detached checkpoint.

Local hashes still cannot prove that named people are real. The real-human confirmation is an external trust root. Stronger proof would require independently signed or externally published anchors.

## Implemented RED tests

- Flip each of the six validity components independently. Each reduces complete acceptance.
- Two reviewers mark every finding invalid identically. Agreement is 1.0, acceptance is 0.0, and the gate fails.
- Four of five accepted findings pass at 0.80; three of five fail.
- A zero-CHANGE projection returns null acceptance and an explicit not-applicable condition.
- A packet built with roster A rejects roster B even when a caller computes B's digest.
- Changing the manifest roster-anchor digest invalidates the packet identity.
- Completed verification exposes no caller-controlled expected roster digest.
- An anchor with the wrong panel report hash is rejected.
- Legacy unanchored packets cannot unlock Stage 2.
- The amendment proves the threshold was set before ratings.

## Future review impact

The amendment leaves the sealed corpus, prompts, model outputs, raw artifacts, and original report unchanged. It changes the effective human gate, rating contract, and review-packet identity prospectively. No human review packet predating the amendment may unlock Stage 2.
