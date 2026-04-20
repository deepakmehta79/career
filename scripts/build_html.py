#!/usr/bin/env python3
"""
Build cork-events/index.html from the latest Markdown digest.

Run from repo root:
    python3 scripts/build_html.py

Inputs read:
    cork-events/README.md       -> today's rendered digest
    cork-events/digests/*.md    -> full archive (newest first)

Outputs written:
    cork-events/index.html      -> styled standalone page (GitHub Pages entry)
    cork-events/archive.html    -> full list of past digests with links

No secrets handled here. Safe to run locally or in CI.
"""
from __future__ import annotations

import datetime as dt
import html
import pathlib
import re
import sys

try:
    import markdown
except ImportError:
    sys.stderr.write(
        "The 'markdown' package is required. Install with: pip install markdown\n"
    )
    sys.exit(1)


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CORK_DIR = REPO_ROOT / "cork-events"
DIGESTS_DIR = CORK_DIR / "digests"
INDEX_OUT = CORK_DIR / "index.html"
ARCHIVE_OUT = CORK_DIR / "archive.html"

# The markdown file we treat as "today's digest" for the index page.
LATEST_MD = CORK_DIR / "README.md"


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<meta name="description" content="Daily auto-generated digest of professional development events, lectures and networking opportunities in Cork, Ireland.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ctext y='52' font-size='56'%3E%F0%9F%93%85%3C/text%3E%3C/svg%3E">
<style>
:root {{
  --bg: #ffffff;
  --fg: #1f2328;
  --muted: #6b7280;
  --accent: #0969da;
  --accent-weak: #ddf4ff;
  --border: #d0d7de;
  --card: #f6f8fa;
  --star: #bf8700;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #9198a1;
    --accent: #4493f8;
    --accent-weak: #0b3a6a;
    --border: #30363d;
    --card: #161b22;
    --star: #e3b341;
  }}
}}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue",
               Helvetica, Arial, sans-serif;
  color: var(--fg);
  background: var(--bg);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 20px 80px;
}}
header.top {{
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}}
header.top .brand {{ font-weight: 700; letter-spacing: 0.2px; }}
header.top .meta {{ color: var(--muted); font-size: 0.9rem; }}
h1 {{ font-size: 1.9rem; margin: 24px 0 4px; }}
h2 {{ font-size: 1.35rem; margin: 36px 0 10px; padding-bottom: 4px; border-bottom: 1px solid var(--border); }}
h3 {{ font-size: 1.1rem; margin: 22px 0 6px; }}
p {{ margin: 0.6em 0; }}
blockquote {{
  margin: 12px 0;
  padding: 10px 14px;
  background: var(--accent-weak);
  border-left: 3px solid var(--accent);
  color: var(--fg);
  border-radius: 4px;
}}
blockquote p {{ margin: 0.2em 0; }}
ul, ol {{ padding-left: 22px; }}
li {{ margin: 6px 0; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
hr {{ border: none; border-top: 1px solid var(--border); margin: 28px 0; }}
code {{
  background: var(--card);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 0.92em;
}}
em {{ color: var(--muted); }}
.digest h3 {{ display: flex; align-items: center; gap: 6px; }}
.digest h2:first-of-type {{ margin-top: 18px; }}

/* Star pick cards: the ⭐ High-value opportunities section.
   We target h3 blocks that come immediately after that h2. */
.star-section {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 6px 20px 18px;
  margin-bottom: 20px;
}}
.star-section h2 {{ border-bottom: none; color: var(--star); }}
.star-section h3 {{ color: var(--fg); }}

footer.bottom {{
  margin-top: 60px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 0.9rem;
}}
.pill {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-weak);
  color: var(--accent);
  font-size: 0.8rem;
  font-weight: 600;
  margin-left: 6px;
  vertical-align: middle;
}}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <div class="brand">Cork Events<span class="pill">daily</span></div>
  <div class="meta">
    Last updated <time datetime="{iso}">{pretty}</time> ·
    <a href="archive.html">archive</a>
  </div>
</header>

<main class="digest">
{body_html}
</main>

<footer class="bottom">
  <p>Auto-generated daily. Events within the next 8 weeks are added; events that have passed or fallen out of the window are removed on the next run.</p>
  <p>Source Markdown: <a href="README.md">cork-events/README.md</a> · Full archive: <a href="digests/">cork-events/digests/</a></p>
</footer>
</div>
</body>
</html>
"""


ARCHIVE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>Cork Events — Archive</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 760px; margin: 0 auto; padding: 32px 20px; line-height: 1.5;
       color: #1f2328; background: #ffffff; }}
@media (prefers-color-scheme: dark) {{
  body {{ color: #e6edf3; background: #0d1117; }}
  a {{ color: #4493f8; }}
}}
a {{ color: #0969da; text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
h1 {{ font-size: 1.6rem; }}
li {{ margin: 6px 0; }}
.muted {{ color: #6b7280; }}
</style>
</head>
<body>
<p><a href="index.html">← today's digest</a></p>
<h1>Cork Events — Archive</h1>
<p class="muted">All daily digests, newest first.</p>
<ul>
{items}
</ul>
</body>
</html>
"""


def star_wrap(html_body: str) -> str:
    """Wrap the ⭐ High-value opportunities H2 section in a styled card."""
    # Match the H2 marker and everything up to the next H2 or HR
    pattern = re.compile(
        r'(<h2[^>]*>[^<]*(?:⭐|&#11088;|High-value opportunities)[^<]*</h2>)'
        r'(.*?)(?=<h2|<hr|$)',
        re.DOTALL | re.IGNORECASE,
    )

    def repl(m: re.Match) -> str:
        return f'<section class="star-section">{m.group(1)}{m.group(2)}</section>'

    return pattern.sub(repl, html_body, count=1)


def render(md_path: pathlib.Path) -> str:
    md_text = md_path.read_text(encoding="utf-8")
    md = markdown.Markdown(extensions=["extra", "sane_lists", "tables"])
    body_html = md.convert(md_text)
    # Strip the H1 (we render our own header) — keep only the first one.
    body_html = re.sub(r'<h1[^>]*>.*?</h1>', '', body_html, count=1, flags=re.S)
    body_html = star_wrap(body_html)
    return body_html


def build_index() -> None:
    if not LATEST_MD.exists():
        sys.stderr.write(f"Missing {LATEST_MD}\n")
        sys.exit(1)

    body_html = render(LATEST_MD)
    now = dt.datetime.now(dt.timezone.utc)
    # Title pulls from the first H1 in the Markdown, if any.
    first_h1 = re.search(r'^#\s+(.+)$', LATEST_MD.read_text(encoding="utf-8"), re.M)
    title = html.escape(first_h1.group(1).strip()) if first_h1 else "Cork Events"

    index_html = PAGE_TEMPLATE.format(
        title=title,
        iso=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        pretty=now.strftime("%d %B %Y"),
        body_html=body_html,
    )
    INDEX_OUT.write_text(index_html, encoding="utf-8")
    print(f"wrote {INDEX_OUT.relative_to(REPO_ROOT)}")


def build_archive() -> None:
    if not DIGESTS_DIR.exists():
        return
    files = sorted(DIGESTS_DIR.glob("*.md"), reverse=True)
    if not files:
        items_html = "<li class='muted'>(no digests yet)</li>"
    else:
        items_html = "\n".join(
            f'<li><a href="digests/{f.name}">{f.stem}</a></li>'
            for f in files
        )
    ARCHIVE_OUT.write_text(
        ARCHIVE_TEMPLATE.format(items=items_html),
        encoding="utf-8",
    )
    print(f"wrote {ARCHIVE_OUT.relative_to(REPO_ROOT)}")


def main() -> None:
    build_index()
    build_archive()


if __name__ == "__main__":
    main()
