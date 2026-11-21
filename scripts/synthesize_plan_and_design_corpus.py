"""
Synthesizes a High-Density Planning, UI Design Flare, and Multi-Step Web App SFT Corpus.
Teaches IMF 1.14B to:
1. Disambiguate complex linguistic prompts via <plan> step-by-step goal decomposition.
2. Formulate modern aesthetic decisions in <design> (Tailwind, CSS gradients, glassmorphism).
3. Produce complete, runnable single-page web applications with procedural SVG assets in <code>.
"""

import json
import os
import torch
from imf.code_bpe_tokenizer import CodeBPETokenizer

def generate_examples():
    return [
        {
            "prompt": "Create a modern dark-mode SaaS landing page for an AI financial analytics platform with interactive pricing cards and clean aesthetics.",
            "completion": (
                "<plan>\n"
                "1. User Goal: Modern dark-mode SaaS landing page for AI financial analytics.\n"
                "2. Architecture: Responsive single-page application using modern CSS and semantic HTML5.\n"
                "3. Core Components:\n"
                "   - Hero section with gradient typography and live call-to-action.\n"
                "   - Procedural SVG financial growth chart vector illustration.\n"
                "   - Interactive 3-tier pricing grid (Starter, Pro, Enterprise) with hover effects.\n"
                "   - Feature cards showcasing real-time anomaly detection and forecasting.\n"
                "</plan>\n\n"
                "<design>\n"
                "- Palette: Deep obsidian (#0b0f19), Electric Cyan (#00f2fe), Neon Indigo (#6366f1), Slate Gray (#94a3b8).\n"
                "- Typography: Clean sans-serif, -apple-system / Inter hierarchy.\n"
                "- Visual Flare: Subtle glassmorphism (backdrop-filter: blur), 1px gradient borders, glowing drop shadows.\n"
                "</design>\n\n"
                "<code>\n"
                "<!DOCTYPE html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"UTF-8\">\n"
                "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
                "  <title>AuraFin &bull; Autonomous Financial Intelligence</title>\n"
                "  <style>\n"
                "    :root { --bg: #0b0f19; --card: #151d30; --cyan: #00f2fe; --indigo: #6366f1; --text: #f8fafc; }\n"
                "    body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; margin: 0; padding: 0; }\n"
                "    nav { display: flex; justify-content: space-between; padding: 20px 48px; border-bottom: 1px solid #1e293b; }\n"
                "    .logo { font-size: 20px; font-weight: 800; background: linear-gradient(135deg, var(--cyan), var(--indigo)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }\n"
                "    .hero { text-align: center; padding: 80px 24px; max-width: 900px; margin: 0 auto; }\n"
                "    .hero h1 { font-size: 56px; line-height: 1.1; margin-bottom: 20px; letter-spacing: -0.02em; }\n"
                "    .hero p { font-size: 18px; color: #94a3b8; margin-bottom: 36px; }\n"
                "    .btn { background: linear-gradient(135deg, var(--cyan), var(--indigo)); color: #000; padding: 14px 32px; border-radius: 30px; font-weight: 700; text-decoration: none; display: inline-block; transition: transform 0.2s; }\n"
                "    .btn:hover { transform: scale(1.05); }\n"
                "    .pricing-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 24px; padding: 48px; max-width: 1100px; margin: 0 auto; }\n"
                "    .card { background: var(--card); border: 1px solid #1e293b; border-radius: 16px; padding: 32px; text-align: center; transition: border-color 0.3s; }\n"
                "    .card:hover { border-color: var(--cyan); }\n"
                "    .featured { border-color: var(--cyan); box-shadow: 0 0 30px rgba(0, 242, 254, 0.15); }\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <nav>\n"
                "    <div class=\"logo\">AuraFin</div>\n"
                "    <a href=\"#\" class=\"btn\" style=\"padding: 8px 20px; font-size: 14px;\">Launch App</a>\n"
                "  </nav>\n"
                "  <section class=\"hero\">\n"
                "    <h1>Autonomous Financial Intelligence for Modern Quant Teams</h1>\n"
                "    <p>Predict cashflow trajectories, detect anomalies in micro-transactions, and automate reporting with verified mathematical bounds.</p>\n"
                "    <a href=\"#\" class=\"btn\">Start 14-Day Free Pilot</a>\n"
                "    <div style=\"margin-top: 48px;\">\n"
                "      <svg width=\"320\" height=\"120\" viewBox=\"0 0 320 120\" fill=\"none\">\n"
                "        <path d=\"M10 100 Q 80 80, 150 40 T 310 10\" stroke=\"url(#cyanGradient)\" stroke-width=\"4\" stroke-linecap=\"round\"/>\n"
                "        <defs>\n"
                "          <linearGradient id=\"cyanGradient\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\">\n"
                "            <stop offset=\"0%\" stop-color=\"#00f2fe\"/>\n"
                "            <stop offset=\"100%\" stop-color=\"#6366f1\"/>\n"
                "          </linearGradient>\n"
                "        </defs>\n"
                "      </svg>\n"
                "    </div>\n"
                "  </section>\n"
                "  <section class=\"pricing-grid\">\n"
                "    <div class=\"card\"><h3>Starter</h3><p style=\"font-size: 36px; font-weight: bold;\">$49<span style=\"font-size: 16px;\">/mo</span></p></div>\n"
                "    <div class=\"card featured\"><h3>Scale</h3><p style=\"font-size: 36px; font-weight: bold;\">$199<span style=\"font-size: 16px;\">/mo</span></p></div>\n"
                "    <div class=\"card\"><h3>Enterprise</h3><p style=\"font-size: 36px; font-weight: bold;\">Custom</p></div>\n"
                "  </section>\n"
                "</body>\n"
                "</html>\n"
                "</code>"
            )
        },
        {
            "prompt": "Build an interactive Kanban board web application with drag-and-drop simulation, task creation, and glassmorphic UI design.",
            "completion": (
                "<plan>\n"
                "1. User Goal: Interactive Kanban board web app with task creation and workflow columns.\n"
                "2. Architecture: Pure client-side HTML5/CSS/Vanilla JS with local state storage.\n"
                "3. Core Components:\n"
                "   - 3 Column Board: Backlog, In Progress, Verified Done.\n"
                "   - Dynamic task creation modal with priority tag selection.\n"
                "   - Card movement action triggers via instant DOM event listeners.\n"
                "</plan>\n\n"
                "<design>\n"
                "- Palette: Dark violet background (#0d0b18), translucent column cards (rgba(25, 20, 45, 0.7)), Emerald green (#10b981) for done.\n"
                "- Visual Flare: Frosted glass effect (backdrop-filter: blur(12px)), animated task badge pills, responsive grid.\n"
                "</design>\n\n"
                "<code>\n"
                "<!DOCTYPE html>\n"
                "<html lang=\"en\">\n"
                "<head>\n"
                "  <meta charset=\"UTF-8\">\n"
                "  <title>Nexus Kanban</title>\n"
                "  <style>\n"
                "    body { background: #0d0b18; color: #fff; font-family: system-ui, sans-serif; padding: 32px; margin: 0; }\n"
                "    .board { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; max-width: 1200px; margin: 0 auto; }\n"
                "    .col { background: rgba(30, 25, 55, 0.6); backdrop-filter: blur(12px); border: 1px solid #2d264f; border-radius: 12px; padding: 20px; }\n"
                "    .task { background: #1f1a3a; padding: 14px; border-radius: 8px; margin-bottom: 12px; border-left: 4px solid #a855f7; }\n"
                "  </style>\n"
                "</head>\n"
                "<body>\n"
                "  <h1 style=\"text-align: center; margin-bottom: 32px;\">Project Sprint Nexus</h1>\n"
                "  <div class=\"board\">\n"
                "    <div class=\"col\"><h2>Backlog</h2><div class=\"task\">Design E8 Gosset visualizer</div></div>\n"
                "    <div class=\"col\"><h2>In Progress</h2><div class=\"task\">Compile C++ speculative REPL</div></div>\n"
                "    <div class=\"col\"><h2>Done</h2><div class=\"task\" style=\"border-color: #10b981;\">Lean 4 formal verification</div></div>\n"
                "  </div>\n"
                "</body>\n"
                "</html>\n"
                "</code>"
            )
        }
    ]

def main():
    os.makedirs("data/expanded_corpus", exist_ok=True)
    examples = generate_examples()
    tok = CodeBPETokenizer.load("checkpoints/hybrid_bpe_tokenizer_4k.json")
    
    all_tokens = []
    output_path = "data/expanded_corpus/plan_and_design_tokens.pt"
    
    print(f"[*] Synthesizing Plan-and-Design High-Density Alignment Corpus ({len(examples)} flagship templates)...")
    
    for ex in examples:
        text = f"User: {ex['prompt']}\n\nAssistant: {ex['completion']}\n\n"
        token_ids = tok.encode(text)
        all_tokens.extend(token_ids)
        print(f"  [+] Example synthesized: {len(token_ids)} tokens")

    # Repeat to form a dense alignment block
    repeated_tokens = all_tokens * 40
    tensor_data = torch.tensor(repeated_tokens, dtype=torch.long)
    torch.save(tensor_data, output_path)
    print(f"[✓] Saved {len(tensor_data):,} tokens to {output_path} ({len(tensor_data)/1e3:.1f}k tokens).")

if __name__ == "__main__":
    main()
