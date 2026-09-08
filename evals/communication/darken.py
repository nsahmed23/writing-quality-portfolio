"""Post-process a generate_review.py static page into dark mode.

Usage: py -3.11 darken.py <input.html> <output.html>

The viewer defines its palette as CSS variables on :root, so a second :root block
appended after the original wins by source order. A few hardcoded light colors in
the template are replaced directly.
"""
import sys
from pathlib import Path

DARK_CSS = """
<style id="dark-mode-override">
  :root {
    color-scheme: dark;
    --bg: #0f1115;
    --surface: #171a21;
    --text: #e6e6e6;
    --text-muted: #9aa3b2;
    --border: #2a2f3a;
    --accent: #6ea8fe;
    --accent-hover: #8bbcff;
    --green: #5fd38d;
    --green-bg: rgba(95, 211, 141, 0.16);
    --red: #ff7b7b;
    --red-bg: rgba(255, 123, 123, 0.16);
    --header-bg: #171a21;
    --header-text: #e6e6e6;
  }
  html, body { background: var(--bg); color: var(--text); }
  pre, code { background: #0b0d11; color: #e6e6e6; }
  textarea, input, select { background: var(--surface); color: var(--text); border-color: var(--border); }
  table th { background: var(--surface); }
  a { color: var(--accent); }
  ::selection { background: rgba(110, 168, 254, 0.35); }
</style>
"""

REPLACEMENTS = {
    "#faf9f5": "#171a21",      # page/surface tint
    "#ffffff": "#171a21",
    "#fceaea": "rgba(255, 123, 123, 0.16)",  # light red badge bg
    "#eef2e8": "rgba(95, 211, 141, 0.16)",   # light green badge bg
    "#e8e6dc": "#2a2f3a",      # border
    "background: white": "background: #171a21",
    "background-color: white": "background-color: #171a21",
}


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    html = src.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS.items():
        html = html.replace(old, new)
    marker = "</head>"
    if marker in html:
        html = html.replace(marker, DARK_CSS + marker, 1)
    else:
        html = html.replace("<body", DARK_CSS + "<body", 1)
    dst.write_text(html, encoding="utf-8")
    print(f"dark page written: {dst} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
