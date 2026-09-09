"""Distribution metrics per arm (reviewer Q1): reply length and time-to-first-action.

Usage: py -3.11 metrics.py <iteration-dir>

time-to-first-action = character offset of the first fenced code block, inline code span, or line starting with an
imperative verb from a small list. Reported as medians per eval per arm; no pass/fail thresholds.
"""
import json
import re
import statistics as st
import sys
from pathlib import Path

IMPERATIVE_RE = re.compile(r"^(?:\d+[.)]\s+)?(?:run|open|create|add|replace|edit|check|install|delete|paste|reply|confirm|kill|stop|next:|step \d)", re.I | re.M)


def first_action_offset(text: str) -> int:
    cands = []
    m = re.search(r"```", text)
    if m:
        cands.append(m.start())
    m = re.search(r"`[^`\n]+`", text)
    if m:
        cands.append(m.start())
    m = IMPERATIVE_RE.search(text)
    if m:
        cands.append(m.start())
    return min(cands) if cands else len(text)


def main():
    it = Path(sys.argv[1])
    rows = {}
    for resp in sorted(it.rglob("outputs/response.md")):
        run = resp.parent.parent
        arm = run.parent.name
        ev = run.parent.parent.name
        text = resp.read_text(encoding="utf-8")
        rows.setdefault((ev, arm), []).append((len(text), first_action_offset(text)))
    print(f"{'eval':28s} {'arm':14s} n  median_chars  median_first_action_offset")
    out = {}
    for (ev, arm), vals in sorted(rows.items()):
        mc = st.median(v[0] for v in vals)
        mo = st.median(v[1] for v in vals)
        out[f"{ev}/{arm}"] = {"n": len(vals), "median_chars": mc, "median_first_action_offset": mo}
        print(f"{ev:28s} {arm:14s} {len(vals)}  {mc:>12.0f}  {mo:>12.0f}")
    (it / "metrics.json").write_text(json.dumps(out, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
