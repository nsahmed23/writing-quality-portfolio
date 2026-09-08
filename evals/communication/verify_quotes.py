"""Audit grader judgments: every passed judgment assertion must cite a span that occurs verbatim in the reply.

Usage: py -3.11 verify_quotes.py <iteration-dir> [--apply]

Without --apply: report. With --apply: flip unverifiable passes to failed (evidence annotated) and recompute summaries.
Quotes are taken from the evidence string: any run of text inside straight or curly double quotes, or inside single
quotes when at least 12 characters long. A pass is verifiable if at least one such quote (whitespace-normalized,
case-insensitive) occurs in response.md. Script-decided entries ("[script]") and inline-grader entries are skipped.
"""
import json
import re
import sys
from pathlib import Path

QUOTE_RE = re.compile(r"[\"“]([^\"”]{6,}?)[\"”]|'([^']{12,}?)'")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def quotes_in(evidence: str):
    for m in QUOTE_RE.finditer(evidence):
        q = m.group(1) or m.group(2)
        if q:
            yield q


def main():
    it = Path(sys.argv[1])
    apply = "--apply" in sys.argv
    total = verified = unverifiable = no_quote = 0
    for g in sorted(it.rglob("grading.json")):
        d = json.loads(g.read_text(encoding="utf-8"))
        resp = (g.parent / "outputs" / "response.md")
        if not resp.exists():
            continue
        body = norm(resp.read_text(encoding="utf-8"))
        changed = False
        for e in d["expectations"]:
            ev = e.get("evidence", "")
            if e.get("passed") is not True or ev.startswith(("[script]", "[inline grader]")):
                continue
            total += 1
            qs = list(quotes_in(ev))
            if not qs:
                no_quote += 1
                status = "NO_QUOTE"
            elif any(norm(q) in body for q in qs):
                verified += 1
                continue
            else:
                unverifiable += 1
                status = "QUOTE_NOT_FOUND"
            print(f"  {status}: {g.parent.relative_to(it)} :: {e['text'][:60]} :: {ev[:100]!r}")
            if apply:
                e["passed"] = False
                e["evidence"] = f"[quote-audit {status}] " + ev
                changed = True
        if changed:
            ex = d["expectations"]; p = sum(1 for x in ex if x["passed"]); t = len(ex)
            d["summary"] = {"passed": p, "failed": t - p, "total": t, "pass_rate": round(p / t, 4)}
            g.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(f"judgment passes: {total}; verified by quote: {verified}; quote not found: {unverifiable}; no quote given: {no_quote}" + ("; applied" if apply else ""))


if __name__ == "__main__":
    main()
