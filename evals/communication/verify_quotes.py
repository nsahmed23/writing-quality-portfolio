"""Audit grader judgments: every passed judgment assertion must cite a span that occurs verbatim in the reply.

Usage: py -3.11 verify_quotes.py <iteration-dir> [--apply] [--file grading4.json --key shape]

Without --apply: report. With --apply: flip unverifiable passes to failed (evidence annotated) and recompute summaries.
Quotes are taken from the evidence string: any run of text inside straight or curly double quotes, or inside single
quotes when at least 12 characters long. A pass is verifiable if at least one such quote (whitespace-normalized,
case-insensitive) occurs in response.md. Script-decided entries ("[script]") and inline-grader entries are skipped.
"""
import json
import re
import sys
from pathlib import Path

DQUOTE_RE = re.compile(r"[\"“]([^\"”]{6,}?)[\"”]")
SQUOTE_RE = re.compile(r"(?<![A-Za-z])'([^']{12,}?)'(?![A-Za-z])")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).replace("’", "'").replace("‘", "'").strip().lower()


def quotes_in(evidence: str):
    """Double-quoted spans first; single-quoted spans only as a fallback, and never ones that start or end
    inside a word (apostrophes in hasn't / haven't must not pair up)."""
    found = [m.group(1) for m in DQUOTE_RE.finditer(evidence)]
    if not found:
        found = [m.group(1) for m in SQUOTE_RE.finditer(evidence)]
    for q in found:
        if q:
            yield q


def main():
    it = Path(sys.argv[1])
    apply = "--apply" in sys.argv
    fname = sys.argv[sys.argv.index("--file") + 1] if "--file" in sys.argv else "grading.json"
    key = sys.argv[sys.argv.index("--key") + 1] if "--key" in sys.argv else "expectations"
    total = verified = unverifiable = no_quote = 0
    for g in sorted(it.rglob(fname)):
        d = json.loads(g.read_text(encoding="utf-8"))
        resp = (g.parent / "outputs" / "response.md")
        if not resp.exists():
            continue
        body = norm(resp.read_text(encoding="utf-8"))
        changed = False
        for e in d[key]:
            ev = e.get("evidence", "")
            voided_before = ev.startswith("[quote-audit")
            if voided_before:
                ev = re.sub(r"^\[quote-audit [A-Z_]+\] ", "", ev)  # re-check a previously voided pass
            elif e.get("passed") is not True or ev.startswith(("[script]", "[inline grader]")):
                continue
            total += 1
            qs = list(quotes_in(ev))

            def found(q: str) -> bool:
                # an ellipsis inside a quote marks elided text: every segment (6+ chars) must occur
                segs = [s for s in re.split(r"\s*(?:\.\.\.|…)\s*", q) if len(s.strip()) >= 6]
                return bool(segs) and all(norm(s) in body for s in segs)

            if ev.lower().lstrip().startswith("no such passage"):
                # absence claim: the grader asserts the reply lacks something; any quoted term is a search term
                # that must NOT occur in the reply. Contradicted if one does; otherwise accepted as absence evidence.
                # only terms that the assertion itself names count as search terms; other quotes are context
                hits = [q for q in qs if norm(q) in body and norm(q) in norm(e['text'])]
                if hits:
                    unverifiable += 1
                    status = "ABSENCE_CONTRADICTED"
                    if voided_before:
                        continue
                    print(f"  {status}: {g.parent.relative_to(it)} :: {e['text'][:60]} :: found {hits[0][:60]!r}")
                    if apply:
                        e["passed"] = False
                        e["evidence"] = f"[quote-audit {status}] " + ev
                        changed = True
                    continue
                verified += 1
                if voided_before and apply:
                    e["passed"] = True
                    e["evidence"] = ev
                    changed = True
                continue
            if not qs:
                no_quote += 1
                status = "NO_QUOTE"
            elif any(found(q) for q in qs):
                verified += 1
                if voided_before and apply:
                    e["passed"] = True
                    e["evidence"] = ev
                    changed = True
                    print(f"  RESTORED: {g.parent.relative_to(it)} :: {e['text'][:60]}")
                continue
            else:
                unverifiable += 1
                status = "QUOTE_NOT_FOUND"
                if voided_before:
                    continue  # already voided; leave as is
            print(f"  {status}: {g.parent.relative_to(it)} :: {e['text'][:60]} :: {ev[:100]!r}")
            if apply:
                e["passed"] = False
                e["evidence"] = f"[quote-audit {status}] " + ev
                changed = True
        if changed:
            ex = d[key]; p = sum(1 for x in ex if x["passed"]); t = len(ex)
            if "summary" in d:  # iteration 1-3 grading.json carries a summary block; grading4.json does not
                d["summary"] = {"passed": p, "failed": t - p, "total": t, "pass_rate": round(p / t, 4)}
            g.write_text(json.dumps(d, indent=2), encoding="utf-8")
    print(f"judgment passes: {total}; verified by quote: {verified}; quote not found: {unverifiable}; no quote given: {no_quote}" + ("; applied" if apply else ""))


if __name__ == "__main__":
    main()
