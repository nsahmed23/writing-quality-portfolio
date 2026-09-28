# Capability map

Checked at: 2026-08-26T02:19:51Z

| Capability | Available | Limits or evidence | Plan effect |
|---|---|---|---|
| Web search | Not used | Exact HTTP header rule and complete local pins | Evaluation remains offline |
| Page or URL retrieval | Not used | Complete local source snapshots | No freshness fetch needed |
| Uploaded files | Yes | Portfolio ZIP already extracted and pinned | Frozen baseline available |
| Private corpora or apps | Limited | No permissioned author samples | Validated voice score pending |
| PDF/document parsing | Not needed | Sources and cases are text | No effect |
| Vision | Not needed | No visual claims | No effect |
| Spreadsheet/data tools | Available | Standard-library JSONL and CSV sufficient | No external dependency |
| Code or shell | Yes | Python 3.14.4; no pytest | Use unittest and trace |
| Subagents/workers | Yes | Same shared filesystem; agents are not humans | Parallel authorship and generation with disjoint files |
| Background/cloud persistence | Not needed | Durable local checkpoints | Resume from `resume.md` |
| Artifact creation | Yes | Local user-facing outputs directory | Publish reports and packets locally |
| Scheduled refresh | Not needed | Exact-commit benchmark | No effect |
| External write actions | Not authorized | No push requested in this turn | Keep GitHub unchanged |

Degradations applied: no real human agreement or authenticated voice score can be completed locally. Stage 2 candidate execution remains locked until human Stage 1 adjudication.
