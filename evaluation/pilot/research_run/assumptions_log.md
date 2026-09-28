# Assumptions log

| ID | Assumption | Consequence if false | Treatment |
|---|---|---|---|
| A-001 | The local pinned source snapshots are complete for the named artifacts. | An authored adapter may omit instructions. | Hash and inventory every referenced source file. |
| A-002 | The session can provide the same model and inherited settings across generator workers. | Cross-system differences may be confounded. | Record observable settings and unknowns; use no overrides. |
| A-003 | Exact Unicode code-point offsets are feasible for all generated findings. | Span matching may be unreliable. | Strictly verify `text[start:end] == span`. |
| A-004 | Synthetic author profiles can test false positives but not authentic voice retention. | Voice claims would be overstated. | Keep validated voice scores pending until permissioned samples exist. |
