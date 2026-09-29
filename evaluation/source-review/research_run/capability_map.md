# Capability map

Checked at: 2026-08-25T18:32:32Z

| Capability | Available | Limits or evidence | Plan effect |
|---|---|---|---|
| Web search | No | Required HTTP User-Agent cannot be guaranteed by the search tool. | Do not use search. |
| Page or URL retrieval | Yes | GitHub CLI permits an explicit exact User-Agent header. | Use official GitHub APIs only for metadata. |
| Uploaded files | Yes | Local ZIP and extracted portfolio are available. | Compare directly with the published local tree. |
| Private corpora or apps | No | Not needed or authorized. | Public evidence only. |
| PDF/document parsing | Yes | Not needed for the named Markdown and code sources. | No effect. |
| Vision | Yes | Not needed unless a repository makes a material image-only claim. | Text-first inspection. |
| Spreadsheet/data tools | Yes | CSV ledgers are sufficient. | Maintain canonical registers. |
| Code or shell | Yes | Read-only source inspection is allowed; third-party code will not run. | Clone pinned snapshots and inspect text. |
| Subagents/workers | Yes | Five additional slots. | Use distinct bounded source workstreams and an independent audit. |
| Background/cloud persistence | No | Local checkpoints are available. | Resume from `research_state.json`. |
| Artifact creation | Yes | Local files can be created under the task workspace. | Produce an auditable research bundle. |
| Scheduled refresh | No | Not requested. | State a refresh trigger. |
| External write actions | No | Investigation does not authorize repository changes. | No edits or pushes to the portfolio. |

Degradations applied: no general web search; official GitHub metadata plus local commit-pinned repository snapshots replace browser retrieval.
