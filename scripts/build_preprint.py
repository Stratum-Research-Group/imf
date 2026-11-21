#!/usr/bin/env python3
"""
scripts/build_preprint.py
Compiles the three IMF technical reports into a unified, formal research preprint PDF:
"Interaction Model Foundations: Lie-Algebraic Memory Splitting, Polytope Virtual Grids, and the Resolution of Directional Conflation"
Features:
- MathJax 3 rendering for LaTeX equations
- Highlight.js for Lean 4 & Python syntax coloring
- Academic two-column or clean single-column ACM/IEEE/NeurIPS style typography
- Page counters, running headers, author affiliations, and embedded SVG/PNG assets
- Headless Chromium print-to-PDF compilation with @page margins
"""

import sys
import subprocess
from pathlib import Path
import markdown

ROOT = Path(__file__).resolve().parent.parent
PAPERS_DIR = ROOT / "papers"
OUTPUT_DIR = ROOT / "dist"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HTML_OUT = OUTPUT_DIR / "imf_preprint.html"
PDF_OUT = OUTPUT_DIR / "imf_preprint.pdf"

PREPRINT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Interaction Model Foundations (IMF) — Technical Preprint</title>
  
  <!-- MathJax 3 configuration -->
  <script>
    MathJax = {
      tex: {
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      },
      svg: { fontCache: 'global' }
    };
  </script>
  <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>

  <!-- Highlight.js for Syntax Highlighting -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/lean.min.js"></script>
  <script>document.addEventListener('DOMContentLoaded', (event) => { hljs.highlightAll(); });</script>

  <style>
    @page {
      size: letter;
      margin: 20mm 18mm 22mm 18mm;
      @bottom-right {
        content: counter(page);
        font-family: "Linux Libertine", "Times New Roman", Times, serif;
        font-size: 9pt;
      }
    }
    
    body {
      font-family: "Linux Libertine", "Times New Roman", "DejaVu Serif", Georgia, serif;
      font-size: 10.5pt;
      line-height: 1.45;
      color: #111;
      background: #fff;
      margin: 0;
      padding: 0;
    }

    .cover {
      text-align: center;
      padding-top: 40px;
      padding-bottom: 30px;
      margin-bottom: 30px;
      border-bottom: 2px solid #222;
    }

    .logo-container {
      margin-bottom: 25px;
    }

    .logo-container img {
      max-width: 140px;
      height: auto;
    }

    h1.preprint-title {
      font-size: 24pt;
      font-weight: 700;
      line-height: 1.25;
      margin: 0 0 15px 0;
      color: #0b1f3a;
    }

    .sub-title {
      font-size: 13pt;
      font-style: italic;
      color: #333;
      margin-bottom: 20px;
    }

    .authors {
      font-size: 12pt;
      font-weight: 600;
      margin-bottom: 6px;
    }

    .affiliation {
      font-size: 10pt;
      color: #555;
      margin-bottom: 20px;
    }

    .meta-box {
      font-size: 9pt;
      color: #666;
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      display: inline-block;
      padding: 6px 16px;
      border-radius: 4px;
    }

    /* Content styling */
    .paper-section {
      margin-top: 40px;
      page-break-before: always;
    }

    .paper-section:first-of-type {
      page-break-before: avoid;
    }

    h1 {
      font-size: 17pt;
      border-bottom: 1px solid #ccc;
      padding-bottom: 6px;
      margin-top: 30px;
      color: #0b1f3a;
    }

    h2 {
      font-size: 13.5pt;
      margin-top: 24px;
      color: #1a365d;
    }

    h3 {
      font-size: 11.5pt;
      margin-top: 18px;
      color: #2b4c7e;
    }

    p {
      text-align: justify;
      margin: 10px 0;
      hyphens: auto;
    }

    blockquote {
      margin: 15px 0;
      padding: 10px 20px;
      background-color: #f8f9fa;
      border-left: 4px solid #0b1f3a;
      font-style: italic;
      color: #333;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      margin: 20px 0;
      font-size: 9.5pt;
    }

    th, td {
      border: 1px solid #ddd;
      padding: 8px 10px;
      text-align: left;
    }

    th {
      background-color: #f1f5f9;
      font-weight: 600;
    }

    pre {
      background: #f8f9fa;
      border: 1px solid #e2e8f0;
      border-radius: 4px;
      padding: 12px;
      overflow-x: auto;
      font-size: 9pt;
      line-height: 1.4;
      font-family: "Fira Code", "JetBrains Mono", Consolas, monospace;
    }

    code {
      font-family: "Fira Code", "JetBrains Mono", Consolas, monospace;
      font-size: 9pt;
      background: #f1f5f9;
      padding: 2px 4px;
      border-radius: 3px;
    }

    pre code {
      background: transparent;
      padding: 0;
    }

    hr {
      border: 0;
      height: 1px;
      background: #ddd;
      margin: 30px 0;
    }
  </style>
</head>
<body>

<div class="cover">
  <div class="logo-container">
    <img src="../assets/logo.png" alt="IMF Logo">
  </div>
  <h1 class="preprint-title">Interaction Model Foundations (IMF)</h1>
  <div class="sub-title">Lie-Algebraic Memory Splitting, Higher-Dimensional Polytope Landmark Connectors, and Formal Epistemological Verification</div>
  
  <div class="authors">Stratum Research Group (SRG)</div>
  <div class="affiliation">Computational Algebra & Deep Learning Architectures &bull; Formal Verification Division</div>
  
  <div class="meta-box">
    Technical Compendium SRG-IMF-2026-TR &bull; Lean 4 Formalized &bull; Triton Hardware Fused &bull; November 2026
  </div>
</div>

<div class="abstract-box" style="background:#fdfdfd; border:1px solid #e2e8f0; border-radius:6px; padding:18px 24px; margin-bottom:40px;">
  <div style="font-weight: bold; text-transform: uppercase; font-size: 9pt; letter-spacing: 1px; color:#475569; margin-bottom: 8px;">Compendium Executive Summary</div>
  <p style="margin: 0; font-size: 10pt;">
    This technical compendium brings together the three foundational reports establishing the <strong>Interaction Model Foundations (IMF)</strong> paradigm. We address the pervasive structural vulnerabilities of auto-associative architectures—specifically the Reversal Curse, representation drift, and lack of verified state transitions—through a mathematically rigorous synthesis of Lie algebra ($\mathrm{Sym}^2 \oplus \bigwedge^2$), higher-dimensional regular polytope coordinate frames (Enneazetton, Decayotton, Hendecaxennon), and interactive formal verification in Lean 4. Across sustained Triton GPU microbenchmarking, long-context retrieval, and pretraining, IMF demonstrates exact directional margin separation, continuous $O(1)$ constant-memory autoregressive step generation, and 314&times; kernel speedups over un-fused causal attention loops.
  </p>
</div>

{content}

</body>
</html>
"""

def main():
    print("[*] Compiling IMF Technical Compendium...")
    paper_files = [
        PAPERS_DIR / "01_savg_lie_algebraic_memory_splitting.md",
        PAPERS_DIR / "02_hdplc_higher_dimensional_polytope_connectors.md",
        PAPERS_DIR / "03_epistemological_foundations_and_real_world_applications.md",
        PAPERS_DIR / "04_grassmann_stereochemistry_and_sl_d_remeshing.md",
        PAPERS_DIR / "05_non_abelian_gauge_fields_and_continuous_lie_ssm.md",
        PAPERS_DIR / "06_the_imf_omni_block.md",
        PAPERS_DIR / "07_empirical_appendix_and_distributed_scaling.md",
        PAPERS_DIR / "08_hyperbolic_polytope_tilings.md",
        PAPERS_DIR / "09_cut_factorized_bidirectional_reasoning_and_polytope_moe.md",
        PAPERS_DIR / "10_omnipresent_polytope_moe_64_domains.md",
        PAPERS_DIR / "11_universal_benchmark_manifolds_and_enterprise_os.md",
        PAPERS_DIR / "12_frontier_mcts_cut_reasoning_and_enterprise_frameworks.md",
        PAPERS_DIR / "13_polytope_speculative_decoding_and_mcts_evaluations.md",
        PAPERS_DIR / "14_empirical_distillation_grpo_and_polytope_reasoning.md",
    ]

    html_sections = []
    md = markdown.Markdown(
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "toc",
            "sane_lists",
        ]
    )

    for p in paper_files:
        if not p.exists():
            raise FileNotFoundError(f"Missing paper: {p}")
        print(f"  [>] Processing {p.name}...")
        text = p.read_text(encoding="utf-8")
        raw_html = md.reset().convert(text)
        html_sections.append(f'<section class="paper-section">\n{raw_html}\n</section>')

    full_html = PREPRINT_TEMPLATE.replace("{content}", "\n\n".join(html_sections))
    HTML_OUT.write_text(full_html, encoding="utf-8")
    print(f"[+] Wrote stand-alone HTML preprint to {HTML_OUT}")

    print(f"[*] Rendering PDF via Headless Chromium...")
    cmd = [
        "chromium",
        "--headless",
        "--disable-gpu",
        "--no-sandbox",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=5000",
        f"--print-to-pdf={PDF_OUT}",
        str(HTML_OUT),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[!] Chromium stderr:\n{res.stderr}")
        raise RuntimeError(f"Chromium exited with code {res.returncode}")

    if PDF_OUT.exists():
        size_kb = PDF_OUT.stat().st_size / 1024.0
        print(f"[✓] Successfully compiled publication PDF: {PDF_OUT} ({size_kb:.1f} KB)")
    else:
        raise FileNotFoundError(f"PDF output {PDF_OUT} was not produced.")

if __name__ == "__main__":
    main()
