# Reproducibility notes

- Platform: Windows 11 baseline.
- Python: standard-library implementation, invoked with UTF-8 mode.
- Network: none in evaluator or research run.
- Source inputs: local exact-commit snapshots recorded in `source_register.csv`.
- Raw outputs: exclusive creation with SHA-256 and byte length.
- Randomization: seed and job-order hash recorded before generation.
- Settings: only exposed model settings are recorded; unavailable fields remain unknown.
- Tests: `unittest`, three consecutive full passes, standard-library line coverage at least 80 percent.
- Human review: independent packets and private blinding key; no agent ratings counted as human.
