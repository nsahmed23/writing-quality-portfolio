"""Iteration-5 report: the v5 targeted rerun (full and short arms) against the same arms' v4 replies from iteration 4.

Usage: py -3.11 report5.py   -> iteration-5/report.md, report.json, report.html (dark)
Reads: iteration-5/case-*/<arm>/run-*/{grading4.json,timing.json,outputs/}, iteration-5/correctness/*.json,
       iteration-5/pairwise/<arm>-v5-vs-v4/<lane>/*.json, and the matching iteration-4 grading for the v4 columns.
"""
import html
import json
import math
import statistics as st
from pathlib import Path

WS = Path(__file__).resolve().parent
IT5, IT4 = WS / "iteration-5", WS / "iteration-4"
ARMS = ("full", "short")
LANE_LABEL = {"codex": "Codex gpt-6-astra", "agy": "Gemini 3.8 Flash (Antigravity CLI)"}


def load(it: Path, arm: str):
    runs = []
    for cd in sorted(it.glob("case-*")):
        case = json.loads((cd / "case.json").read_text(encoding="utf-8"))
        for rd in sorted((cd / arm).glob("run-*")):
            g = rd / "grading4.json"
            if not g.exists():
                continue
            grade = json.loads(g.read_text(encoding="utf-8"))
            timing = json.loads((rd / "timing.json").read_text(encoding="utf-8")) if (rd / "timing.json").exists() else {}
            resp = rd / "outputs" / "response.md"
            cmds = rd / "outputs" / "commands.txt"
            runs.append({"case": case, "arm": arm, "run": rd.name, "grade": grade, "timing": timing,
                         "response": resp.read_text(encoding="utf-8").replace("\r\n", "\n") if resp.exists() else "",
                         "commands": cmds.read_text(encoding="utf-8") if cmds.exists() else None})
    return runs


def correctness(it: Path):
    traps, contra = [], []
    cdir = it / "correctness"
    if cdir.exists():
        for p in sorted(cdir.glob("traps-*.json")):
            traps.extend(json.loads(p.read_text(encoding="utf-8")))
        cp = cdir / "contradictions.json"
        if cp.exists():
            contra = json.loads(cp.read_text(encoding="utf-8"))
    return traps, contra


def sign_p(k, n):
    if n == 0:
        return float("nan")
    tail = sum(math.comb(n, i) for i in range(0, min(k, n - k) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def pairwise():
    out = {}
    root = IT5 / "pairwise"
    for pair_dir in sorted(root.glob("*-v5-vs-v4")):
        arm = pair_dir.name.split("-")[0]
        for lane_dir in sorted(p for p in pair_dir.iterdir() if p.is_dir()):
            by = {}
            for p in lane_dir.glob("*.json"):
                r = json.loads(p.read_text(encoding="utf-8"))
                by.setdefault((r["case_name"], r["run"]), {"arms": r["arms"]})[r["order"]] = r["winner_arm"]
            rows = []
            for (cn, run), o in sorted(by.items()):
                a, b = o.get(1), o.get(2)
                if a is None or b is None:
                    res = "incomplete"
                elif a == b and a == o["arms"][0]:
                    res = "v5"
                elif a == b and a == o["arms"][1]:
                    res = "v4"
                elif a == b:
                    res = a
                else:
                    res = "inconsistent"
                rows.append({"case": cn, "run": run, "result": res})
            t = {k: sum(1 for r in rows if r["result"] == k) for k in ("v5", "v4", "tie", "both_unacceptable", "inconsistent", "incomplete")}
            out[(arm, lane_dir.name)] = {"rows": rows, "totals": t, "p": sign_p(t["v5"], t["v5"] + t["v4"])}
    return out


def stats(runs, traps5, cases):
    shapes = [s for r in runs for s in r["grade"].get("shape", []) if s["passed"] is not None]
    inv = [r["grade"]["inventory_rate"] for r in runs if r["grade"]["inventory_rate"] is not None]
    return {
        "runs": len(runs),
        "shape": f"{sum(1 for s in shapes if s['passed'])}/{len(shapes)}",
        "inventory": round(st.mean(inv), 3) if inv else None,
        "median_chars": int(st.median(r["grade"]["chars"] for r in runs)) if runs else None,
        "median_seconds": round(st.median(r["timing"].get("total_duration_seconds", 0) for r in runs), 1) if runs else None,
        "trap_wrong": sum(1 for t in traps5 if t["arm"] == runs[0]["arm"] and t["verdict"] == "asserts_wrong") if runs else 0,
        "delete_lines": [r["grade"]["fixture"]["delete_line"] for r in runs if r["grade"].get("fixture")],
    }


def build():
    traps5, contra5 = correctness(IT5)
    traps4, _ = correctness(IT4)
    cases = [json.loads((cd / "case.json").read_text(encoding="utf-8"))["name"] for cd in sorted(IT5.glob("case-*"))]
    rep = {"cases": cases, "arms": {}, "per_case": [], "pairwise": {}, "traps_wrong": [t for t in traps5 if t["verdict"] == "asserts_wrong"],
           "contradictions": contra5, "runs": []}
    for arm in ARMS:
        r5 = load(IT5, arm)
        r4 = [r for r in load(IT4, arm) if r["case"]["name"] in cases]
        rep["arms"][arm] = {"v5": stats(r5, traps5, cases), "v4": stats(r4, traps4, cases)}
        for r in r5:
            rep["runs"].append({"case": r["case"]["name"], "arm": arm, "run": r["run"], "chars": r["grade"]["chars"], "response": r["response"],
                                "commands": r["commands"], "shape": r["grade"].get("shape", []),
                                "inventory_miss": [i["item"] for i in r["grade"]["inventory"] if not i["hit"]],
                                "trap_wrong": [t for t in traps5 if t["case"] == r["case"]["name"] and t["arm"] == arm and t["run"] == r["run"] and t["verdict"] == "asserts_wrong"]})
    for cn in cases:
        row = {"case": cn, "arms": {}}
        for arm in ARMS:
            for ver, it in (("v5", IT5), ("v4", IT4)):
                rs = [r for r in load(it, arm) if r["case"]["name"] == cn]
                shapes = [s for r in rs for s in r["grade"].get("shape", []) if s["passed"] is not None]
                traps = traps5 if ver == "v5" else traps4
                row["arms"][f"{arm}-{ver}"] = {
                    "shape": f"{sum(1 for s in shapes if s['passed'])}/{len(shapes)}" if shapes else "-",
                    "inventory": round(st.mean(r["grade"]["inventory_rate"] for r in rs), 2) if rs and rs[0]["grade"]["inventory_rate"] is not None else None,
                    "chars": int(st.median(r["grade"]["chars"] for r in rs)) if rs else None,
                    "delete": [r["grade"]["fixture"]["delete_line"] for r in rs if r["grade"].get("fixture")],
                    "failed": [s["text"] for r in rs for s in r["grade"].get("shape", []) if s["passed"] is False],
                    "wrong": [f"{t['run']} {t['trap_id']}" for t in traps if t["case"] == cn and t["arm"] == arm and t["verdict"] == "asserts_wrong"],
                }
        rep["per_case"].append(row)
    for (arm, lane), v in pairwise().items():
        rep["pairwise"][f"{arm}/{lane}"] = v
    return rep


def to_md(rep):
    L = ["# Iteration 5: v5 targeted rerun (full and short) against v4", "",
         "Cases: the ones v5 touches (12 force-delete under a waiver, 5 TCP explanation, 6 sourdough premise, 11 two issues) plus 2 JWT rotation as the brevity watch. Two runs per arm on Opus 5. Each v5 reply is judged blind against the same arm's v4 reply of the same run index (Codex and Gemini, both orders; a winner only when it survives reversal).", "",
         "## Arms", "", "| arm | version | shape pass | inventory | median chars | median s | trap errors | case-12 decision |", "|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        for ver in ("v5", "v4"):
            s = rep["arms"][arm][ver]
            dl = "; ".join((d or "asked, no delete") for d in s["delete_lines"]) or "-"
            L.append(f"| {arm} | {ver} | {s['shape']} | {s['inventory']} | {s['median_chars']} | {s['median_seconds']} | {s['trap_wrong']} | {dl} |")
    L += ["", "## Pairwise, v5 vs v4 (stable pairs)", "", "| arm / judge | v5 wins | v4 wins | tie | both bad | inconsistent | incomplete | p (sign) |", "|---|---|---|---|---|---|---|---|"]
    for key, v in rep["pairwise"].items():
        arm, lane = key.split("/")
        t = v["totals"]
        L.append(f"| {arm} / {LANE_LABEL.get(lane, lane)} | {t['v5']} | {t['v4']} | {t['tie']} | {t['both_unacceptable']} | {t['inconsistent']} | {t['incomplete']} | {v['p']:.3f} |")
    L += ["", "## Per case", "", "| case | full v5 | full v4 | short v5 | short v4 |", "|---|---|---|---|---|"]
    for row in rep["per_case"]:
        cells = []
        for k in ("full-v5", "full-v4", "short-v5", "short-v4"):
            x = row["arms"][k]
            cells.append(f"{x['shape']} / inv {x['inventory']} / {x['chars']}" + (f" / {'; '.join((d or 'asked') for d in x['delete'])}" if x["delete"] else "") + (f" / wrong: {', '.join(x['wrong'])}" if x["wrong"] else ""))
        L.append(f"| {row['case']} | " + " | ".join(cells) + " |")
    L += ["", "## Pairwise per case", ""]
    for key, v in rep["pairwise"].items():
        L.append(f"- {key}: " + ", ".join(f"{r['case']} {r['run']}={r['result']}" for r in v["rows"]))
    L += ["", "## Failed shape assertions (v5)", ""]
    for row in rep["per_case"]:
        for k in ("full-v5", "short-v5"):
            for s in row["arms"][k]["failed"]:
                L.append(f"- {row['case']} / {k}: {s}")
    L += ["", "## Correctness (v5)", ""]
    if not rep["traps_wrong"] and not rep["contradictions"]:
        L.append("No wrong trap assertions and no cross-run contradictions recorded." if (IT5 / "correctness").exists() else "Not yet graded.")
    for t in rep["traps_wrong"]:
        L.append(f"- wrong: {t['case']} / {t['arm']} {t['run']} / {t['trap_id']}: \"{t.get('quote', '')[:160]}\"")
    for c in rep["contradictions"]:
        L.append(f"- contradiction: {c['case']} / {c['arm']}: {c['topic']} (right: {c.get('which_is_right', 'unknown')})")
    return "\n".join(L) + "\n"


HEAD = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Iteration 5: v5 vs v4</title>
<style>
:root{color-scheme:dark;--bg:#0f1115;--surface:#171a21;--text:#e6e6e6;--muted:#9aa3b2;--border:#2a2f3a;--accent:#6ea8fe;--green:#5fd38d;--red:#ff7b7b;--amber:#f2c94c}
html,body{background:var(--bg);color:var(--text);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:14px}
h1{font-size:1.35em;margin:.2em 0}h2{font-size:1.1em;margin:1.4em 0 .4em;color:var(--accent)}h3{font-size:1em;margin:1em 0 .3em}
table{border-collapse:collapse;width:100%;font-size:.86em;margin:.4em 0}th,td{border:1px solid var(--border);padding:5px 6px;text-align:left;vertical-align:top}th{background:var(--surface)}
.wrap{overflow-x:auto}.ok{color:var(--green)}.bad{color:var(--red)}.warn{color:var(--amber)}.muted{color:var(--muted)}
details{border:1px solid var(--border);border-radius:8px;padding:6px 10px;margin:6px 0;background:var(--surface)}summary{cursor:pointer;font-weight:600}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0d11;border:1px solid var(--border);border-radius:6px;padding:8px;font-size:.84em}
</style></head><body>"""


def to_html(rep):
    e = html.escape
    md = to_md(rep).split("\n")
    H = [HEAD, "<h1>Iteration 5: v5 targeted rerun against v4</h1>"]
    in_table = False
    for ln in md[1:]:
        t = ln.rstrip()
        if t.startswith("| ") and "---" not in t:
            cells = [c.strip() for c in t.strip("|").split("|")]
            if not in_table:
                H.append("<div class='wrap'><table>"); in_table = True
                H.append("<tr>" + "".join(f"<th>{e(c)}</th>" for c in cells) + "</tr>")
            else:
                H.append("<tr>" + "".join(f"<td>{e(c)}</td>" for c in cells) + "</tr>")
            continue
        if in_table and not t.startswith("|"):
            H.append("</table></div>"); in_table = False
        if t.startswith("|---"):
            continue
        if t.startswith("## "):
            H.append(f"<h2>{e(t[3:])}</h2>")
        elif t.startswith("- "):
            H.append(f"<p class='{'bad' if t.startswith('- wrong') else ''}'>{e(t[2:])}</p>")
        elif t:
            H.append(f"<p>{e(t)}</p>")
    if in_table:
        H.append("</table></div>")
    H.append("<h2>Replies (v5)</h2>")
    for r in rep["runs"]:
        H.append(f"<details><summary>{e(r['case'])} · {r['arm']} {r['run']} · {r['chars']} chars</summary>")
        if r["shape"]:
            H.append("<ul>" + "".join(f"<li class='{'ok' if s['passed'] else ('bad' if s['passed'] is False else 'warn')}'>{e(s['text'])} <span class='muted'>{e(str(s['evidence']))[:300]}</span></li>" for s in r["shape"]) + "</ul>")
        if r["trap_wrong"]:
            H.append("<ul>" + "".join(f"<li class='bad'>wrong on {e(t['trap_id'])}: \"{e(t.get('quote', '')[:200])}\"</li>" for t in r["trap_wrong"]) + "</ul>")
        if r["commands"]:
            H.append("<p class='muted'>commands.txt</p><pre>" + e(r["commands"]) + "</pre>")
        H.append("<pre>" + e(r["response"]) + "</pre></details>")
    H.append("</body></html>")
    return "\n".join(H)


def main():
    rep = build()
    (IT5 / "report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    (IT5 / "report.md").write_text(to_md(rep), encoding="utf-8")
    (IT5 / "report.html").write_text(to_html(rep), encoding="utf-8")
    print(to_md(rep))


if __name__ == "__main__":
    main()
