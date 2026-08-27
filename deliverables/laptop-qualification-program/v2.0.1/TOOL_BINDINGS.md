# Tool Bindings

**Current implementation binding, not part of the portable qualification contract.**

The method is defined by NEW_LAPTOP_EVALUATION_PLAYBOOK_v2.md and the five schemas. The assignments below are the current way that contract is executed. Any tool here may be replaced without changing the playbook or the schemas; a replacement must satisfy the same contract role.

| Tool | Contract role it fulfills |
|---|---|
| Git + CI/CD | Store manifests, test plans, threshold policies, scripts, agent classification, evidence references, and decision history; run scheduled currency checks; open drift PRs |
| Terraform or OpenTofu | Provision supporting cloud resources: evidence storage, ingestion, identities, dashboards, and the dynamic device groups that define eval rings |
| Azure | Current cloud substrate for evidence storage, ingestion, identity, automation, monitoring, and reporting; its services remain replaceable beneath the contract |
| Cloud Posse Atmos | Layer org defaults and per-candidate manifests over the Terraform/OpenTofu components |
| Microsoft Graph | Write path: apply Intune objects (remediations, apps, assignments) from versioned JSON. Read path: pull remediation output and inventory into the evidence store |
| Intune | Deliver the evaluation package to managed devices and enforce the real fleet delivery path, which is itself under evaluation |
| Ansible | Accelerate bench-lab iteration where direct access exists; final packages must still be validated through the fleet delivery path |
| HP CMSL + HPIA | Vendor ground truth and currency for BIOS, drivers, and SoftPaqs |
| Evidence collector v2.0.1 | Current Phase 1 implementation of Safe/Restricted bundle handling, trusted native capture, section-failure records, and hashed manifests |
| Versioned agent-classification rules | Organization-owned, digest-approved product/class mappings for services, tasks, drivers, and minifilters without vendor names in the portable method |
| Approved CMSL module binding | Exact module-manifest path and preapproved complete-tree SHA-256 required before the collector executes the current vendor tooling |
| Collector unit and bench test matrix | Verify helper contracts locally and reserve token-, privilege-, and hardware-dependent checks for representative bench units |
| SysTrack | Longitudinal measurement: corporate floor in production, persona cohorts, pilot telemetry, DEX confirmation |
| ServiceNow | Incidents, repairs, support effort, and lifecycle events feeding Phase 4 and Phase 6 |
| Evidence Fabric (storage + index) | Preserve normalized evidence records, baseline releases, provenance, and verdict history |

Replacement rule: when a binding changes, re-validate that the contract role is still fully met, record the change in Phase 6 monitoring, and mark evidence stale only where the test plan's staleness dependencies say the measurement path itself changed.
