"""Record subagent timing from a task notification.

Usage: py -3.11 timing.py <iteration> <eval-dir-name> <arm> <run> <total_tokens> <duration_ms> [...repeat groups of 6]
Example: py -3.11 timing.py iteration-2 eval-0-premise-check with_skill 1 150118 553627
"""
import json
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent


def main():
    args = sys.argv[1:]
    if len(args) % 6 != 0 or not args:
        print(__doc__)
        sys.exit(2)
    for i in range(0, len(args), 6):
        it, ev, arm, run, tokens, ms = args[i:i + 6]
        run_dir = WS / it / ev / arm / f"run-{run}"
        if not run_dir.exists():
            print("MISSING run dir:", run_dir)
            sys.exit(1)
        ms_i = int(ms)
        (run_dir / "timing.json").write_text(json.dumps({
            "total_tokens": int(tokens),
            "duration_ms": ms_i,
            "total_duration_seconds": round(ms_i / 1000, 1),
        }, indent=2), encoding="utf-8")
        has_resp = (run_dir / "outputs" / "response.md").exists()
        print(f"timing saved: {ev}/{arm}/run-{run} tokens={tokens} s={ms_i/1000:.1f} response={'yes' if has_resp else 'NO'}")


if __name__ == "__main__":
    main()
