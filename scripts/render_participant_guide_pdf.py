#!/usr/bin/env python3
"""Render the participant guide as a styled PDF with integrated screenshots."""

from __future__ import annotations

import datetime as dt
import html
import pathlib
import re
import subprocess
import tempfile

import markdown


ROOT = pathlib.Path(__file__).resolve().parents[1]
GUIDE_MD = ROOT / "workshop" / "PARTICIPANT_GUIDE.md"
OUTPUT_PDF = ROOT / "workshop" / "PARTICIPANT_GUIDE.pdf"


def build_html(markdown_text: str) -> str:
    markdown_text = re.sub(
        r"(?m)^## Module ",
        '<div class="page-break"></div>\n\n## Module ',
        markdown_text,
    )
    body = markdown.markdown(
        markdown_text,
        extensions=["extra", "fenced_code", "sane_lists", "toc"],
        output_format="html5",
    )
    rendered_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Packmate Participant Guide</title>
  <style>
    :root {{
      --rh-red: #ee0000;
      --rh-dark: #151515;
      --rh-gray: #6a6e73;
      --rh-light: #f5f5f5;
      --rh-border: #d2d2d2;
      --rh-link: #0066cc;
    }}

    @page {{
      size: A4;
      margin: 16mm 14mm 18mm 14mm;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      color: var(--rh-dark);
      background: white;
      font-family: "Red Hat Text", "Helvetica Neue", Arial, sans-serif;
      line-height: 1.45;
      font-size: 10.5pt;
    }}

    .cover {{
      border-top: 10px solid var(--rh-red);
      padding: 22mm 0 12mm 0;
      margin-bottom: 8mm;
    }}

    .brand {{
      display: inline-block;
      background: var(--rh-dark);
      color: white;
      padding: 8px 12px;
      font-size: 10pt;
      letter-spacing: 0.02em;
      border-radius: 4px;
      margin-bottom: 10mm;
    }}

    .title {{
      font-size: 26pt;
      font-weight: 700;
      line-height: 1.1;
      margin: 0 0 4mm 0;
    }}

    .subtitle {{
      color: var(--rh-gray);
      font-size: 12pt;
      margin: 0 0 10mm 0;
    }}

    .summary {{
      background: var(--rh-light);
      border-left: 4px solid var(--rh-red);
      padding: 12px 16px;
      margin: 8mm 0 0 0;
    }}

    .meta {{
      margin-top: 10mm;
      color: var(--rh-gray);
      font-size: 9pt;
    }}

    main {{
      width: 100%;
    }}

    h1 {{
      display: none;
    }}

    h2 {{
      margin: 9mm 0 3mm 0;
      padding-bottom: 2mm;
      border-bottom: 2px solid var(--rh-red);
      font-size: 18pt;
      line-height: 1.2;
    }}

    h3 {{
      margin: 6mm 0 2mm 0;
      font-size: 12.5pt;
      color: var(--rh-dark);
    }}

    p, li {{
      orphans: 3;
      widows: 3;
    }}

    strong {{
      color: var(--rh-dark);
    }}

    ul, ol {{
      padding-left: 20px;
    }}

    li {{
      margin: 2mm 0;
    }}

    code {{
      font-family: "Red Hat Mono", "SFMono-Regular", Consolas, monospace;
      background: #f0f0f0;
      border-radius: 4px;
      padding: 1px 4px;
      font-size: 0.94em;
    }}

    pre {{
      background: #1f1f1f;
      color: #f0f0f0;
      padding: 12px 14px;
      border-radius: 6px;
      overflow: hidden;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 9pt;
      line-height: 1.35;
    }}

    pre code {{
      background: transparent;
      color: inherit;
      padding: 0;
    }}

    img {{
      display: block;
      width: 100%;
      max-width: 100%;
      margin: 4mm auto 6mm auto;
      border: 1px solid var(--rh-border);
      border-radius: 8px;
      page-break-inside: avoid;
      break-inside: avoid;
    }}

    a {{
      color: var(--rh-link);
      text-decoration: none;
    }}

    blockquote {{
      margin: 4mm 0;
      padding: 0 0 0 12px;
      border-left: 4px solid var(--rh-border);
      color: var(--rh-gray);
    }}

    .page-break {{
      page-break-before: always;
      break-before: page;
      height: 0;
    }}
  </style>
</head>
<body>
  <section class="cover">
    <div class="brand">Red Hat | Packmate Workshop</div>
    <div class="title">Participant Guide</div>
    <p class="subtitle">Self-service OpenShift AI workshop for building an agentic AI application with MCP and OGX.</p>
    <div class="summary">
      <strong>Workshop flow:</strong> create your project and workbench, bootstrap your sandbox, discover the shared model,
      prototype in Playground, enable MCP tools, inspect the code, use the Packmate app, and run the evaluation pipeline.
    </div>
    <div class="meta">Rendered {html.escape(rendered_at)}</div>
  </section>
  <main>
    {body}
  </main>
</body>
</html>
"""


def main() -> int:
    markdown_text = GUIDE_MD.read_text(encoding="utf-8")
    html_text = build_html(markdown_text)

    with tempfile.TemporaryDirectory(prefix="packmate-guide-") as tmp_dir:
      html_path = pathlib.Path(tmp_dir) / "participant-guide.html"
      html_path.write_text(html_text, encoding="utf-8")

      subprocess.run(
          [
              "google-chrome",
              "--headless=new",
              "--disable-gpu",
              "--no-sandbox",
              "--print-to-pdf-no-header",
              f"--print-to-pdf={OUTPUT_PDF}",
              html_path.as_uri(),
          ],
          check=True,
      )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
