"""
Export Delivery Bundle Script for Barbara Roos
Generates fresh sample briefs, rebuilds standalone distribution executable, creates quickstart guide,
and copies all delivery artifacts directly to the user's Downloads directory.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

import types
from main import load_config, run_query_mode

def main():
    print("=========================================================")
    print(" Trailhead Engine - Delivery Artifact Exporter")
    print("=========================================================\n")

    # Step 1: Generate Fresh Verified Sample HTML Reports
    config = load_config("config.yaml")

    sample_prompts = [
        ("Manager AI Workflow Metrics", "Sample_Brief_Manager_AI_Workflow_Metrics.html"),
        ("Copilot Developer Friction", "Sample_Brief_Copilot_Developer_Friction.html")
    ]

    generated_samples = []

    for prompt, filename in sample_prompts:
        print(f"[*] Generating sample report for prompt: '{prompt}'...")
        args = types.SimpleNamespace(mode="query", prompt=prompt, days=7, limit=5, mock=False)
        out_md = run_query_mode(config, args)
        
        # Determine the generated HTML file path
        out_html = out_md.replace(".md", ".html")
        if os.path.exists(out_html):
            dest_path = os.path.join("output", filename)
            shutil.copy(out_html, dest_path)
            generated_samples.append(dest_path)
            print(f"    Saved sample brief to: {dest_path}")
        else:
            print(f"    [WARNING] Expected HTML file not found: {out_html}")

    # Step 2: Rebuild Standalone Executable
    print("\n[*] Rebuilding standalone executable package via PyInstaller...")
    res = subprocess.run([sys.executable, "build_exe.py"], check=False)
    if res.returncode != 0:
        print("[ERROR] build_exe.py failed. Exiting.")
        sys.exit(1)

    zip_source = os.path.join("dist", "TrailheadEngine_v1.0_Standalone.zip")
    if not os.path.exists(zip_source):
        print(f"[ERROR] Expected ZIP distribution not found: {zip_source}")
        sys.exit(1)

    # Step 3: Create README_Quickstart_Barbara.txt
    readme_path = os.path.join("output", "README_Quickstart_Barbara.txt")
    readme_content = """================================================================================
 TRAILHEAD MARKET LISTENING ENGINE v1.0 - QUICK START GUIDE FOR BARBARA ROOS
================================================================================

Welcome to the Trailhead Market Listening Engine desktop advisory suite!

QUICK START IN 3 EASY STEPS:
--------------------------------------------------------------------------------
1. CONFIGURE API KEY:
   - Double-click 'TrailheadEngine.exe' to open the application.
   - Go to the 'Settings & API Key' tab.
   - Enter your Anthropic Claude API Key (starts with 'sk-ant-api...') and click 'Save Key'.
   - Keys are stored strictly on your local computer in .env and never transmitted.

2. RUN AN ADVISORY BRIEF (ON-DEMAND QUERY MODE):
   - Navigate to the 'Main / Ingestion Engine' tab.
   - Select 'Targeted Query Brief' mode.
   - Type an advisory question or click one of the 1-click presets:
       * Copilot Developer Friction
       * Shadow AI Workaround Risks
       * Middle Manager Burden
       * Enterprise AI Legal & Compliance
   - Adjust the lookback slider (e.g. 7 days) and article limit (e.g. 5 cards).
   - Click 'Run Ingestion & Synthesis Engine'.

3. VIEW & EXPORT INTELLIGENCE BRIEFS:
   - When complete, click 'Launch HTML in Web Browser' to view interactive briefs.
   - Outputs are automatically saved in Markdown (.md) and HTML (.html) formats under the output/ folder.
   - Each evidence card includes:
       * Grounded verbatim quotes and roles
       * Priority hypothesis classification ([H1], [H2], [H3], [EMERGING])
       * Historical trend velocity badges (Strengthening, Steady, Fading)
       * Direct click-through links to verified public discussions & job signals

AUTOMATED WEEKLY DIGEST (BACKGROUND SCHEDULER):
--------------------------------------------------------------------------------
   - Go to the 'Background Scheduler' tab.
   - Turn on the switch to enable automatic weekly digest generation.
   - Default schedule: Mondays at 07:00 AM Pacific (14:00 UTC).
   - Runs silently in the background whenever the application is open.

SUPPORT & FILES:
--------------------------------------------------------------------------------
   - Executable Zip: TrailheadEngine_v1.0_Standalone.zip (Unzip to any folder and run TrailheadEngine.exe)
   - Sample Reports: Sample_Brief_Manager_AI_Workflow_Metrics.html & Sample_Brief_Copilot_Developer_Friction.html
"""

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"[*] Created quickstart guide: {readme_path}")

    # Step 4: Copy Delivery Bundle to User's Downloads Folder
    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    delivery_files = [
        (zip_source, downloads_dir / "TrailheadEngine_v1.0_Standalone.zip"),
        (readme_path, downloads_dir / "README_Quickstart_Barbara.txt")
    ]

    for sample in generated_samples:
        filename = os.path.basename(sample)
        delivery_files.append((sample, downloads_dir / filename))

    print(f"\n[*] Exporting delivery bundle to Downloads folder: {downloads_dir}")
    for src, dst in delivery_files:
        if os.path.exists(src):
            shutil.copy(src, dst)
            print(f"    ✓ Copied: {dst.name}")
        else:
            print(f"    ✗ Missing file: {src}")

    print("\n=========================================================")
    print(" SUCCESS! Delivery bundle exported to Downloads directory:")
    print(f" {downloads_dir}")
    print("=========================================================")

if __name__ == "__main__":
    main()
