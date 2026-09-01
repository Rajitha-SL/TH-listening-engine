================================================================================
 TRAILHEAD MARKET LISTENING ENGINE v1.0 - QUICK START GUIDE FOR BARBARA ROOS
================================================================================

Welcome to the Trailhead Market Listening Engine desktop advisory suite!

QUICK START IN 3 EASY STEPS:
--------------------------------------------------------------------------------
1. CONFIGURE API KEY:
   - Double-click 'TrailheadEngine.exe' to open the application.
   - Go to the 'Settings & API Key' tab.
   - Enter your Anthropic Claude API Key (starts with 'sk-ant-api...') and click 'Save Key'.
   - Keys are stored on this computer in .env. Live runs send the key and scraped text to Anthropic; they are not uploaded to GitHub by the app.

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
