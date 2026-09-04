# 🛰️ Trailhead Market Listening Engine — Executive User Manual
**Client Setup & Operating Guide for Barbara Roos**

Welcome to the **Trailhead Market Listening Engine Desktop Suite**. This standalone application allows Trailhead Communications to monitor enterprise AI adoption sentiment, surface frontline friction patterns across Reddit and RSS feeds, and generate executive-ready intelligence briefs powered by Anthropic Claude 3.5 Sonnet.

---

## 🚀 1. Quick Start & Installation

No Python or terminal installation is required. Everything needed to run the engine is pre-bundled in the standalone application.

1. **Locate the ZIP Package**: Find `TrailheadEngine_v1.0_Standalone.zip` in your release distribution.
2. **Extract the Archive**: Right-click `TrailheadEngine_v1.0_Standalone.zip` and choose **Extract All...** to extract to your preferred folder (e.g., `Desktop` or `Documents`).
3. **Launch the Engine**: Open the extracted `TrailheadEngine` folder and double-click:
   ```text
   TrailheadEngine.exe
   ```
4. **Desktop Application**: The CustomTkinter dark-themed desktop suite will launch immediately.

---

## 🔑 2. Configuring Your Claude API Key

Before running live market synthesis, configure your Anthropic Claude API key.

1. In the app, click the **Settings & API Key** tab.
2. In the **Anthropic Claude API Key Configuration** card, paste your API key (starts with `sk-ant-api...`).
3. Click **Save Key**.
4. Check the left sidebar: the API Key badge will update to **Configured ✓** in green.

> 🔒 **Privacy & Security Note:** Your API key is stored on this computer in a `.env` file. When you run a live (non-mock) brief, the key and the scraped discussion text are sent to Anthropic to generate the synthesis. They are not uploaded to GitHub by the desktop app.

---

## ⚡ 3. Running Intelligence Ingestion

The engine supports two primary operating modes depending on your consulting needs:

### A. Targeted On-Demand Intelligence Briefs (`Query Mode`)
Use this mode when preparing for specific client meetings or investigating targeted topics (e.g., security risks, middle-management burnout, or shadow AI workarounds).

1. Click the **Run Intelligence** tab.
2. Select **Targeted Query Brief**.
3. Type your prompt into the query box (e.g., *"M365 Copilot security risks and shadow AI bypasses in legal"*), or click one of the **Quick Presets**:
   - `Copilot Security`
   - `Manager Friction`
   - `Shadow AI Bypasses`
4. Adjust the **Lookback Days** slider (default: `14 days`).
5. Click **⚡ Run Market Listening Engine**.
6. View live step-by-step processing in the **Live Execution Output Log**.

### B. Automated Weekly Intelligence Digests (`Weekly Mode`)
Use this mode for routine broad-market monitoring.

1. Click the **Run Intelligence** tab.
2. Select **Automated Weekly Digest**.
3. Click **⚡ Run Market Listening Engine**.
4. The engine will ingest across all configured subreddits (`r/humanresources`, `r/managers`, `r/sysadmin`, etc.) and RSS feeds, perform noise filtering, synthesize findings via Claude, and update historical trend memory.

---

## ⏰ 4. Automated Background Scheduling

You can configure the engine to generate weekly digests automatically without manual intervention:

1. Click the **Background Scheduler** tab.
2. Toggle the switch: **Enable Automated Background Digest Schedule**.
3. Default timing is pre-set to **Monday at 14:00 UTC (07:00 AM PT)**.
4. You can adjust the day or UTC execution time anytime using the dropdown controls.
5. The sidebar badge will display **Active ✓** and show the timestamp of the next automated run.

---

## 📂 5. Accessing & Exporting Reports

All generated intelligence briefs are saved as structured, publication-grade Markdown (`.md`) files with full verbatim quotes, source links, and executive takeaways.

1. Click the **Reports Viewer** tab.
2. Select any report from the dropdown list to preview formatted content inline.
3. Click **↗️ Open Selected in System App** to view or edit the report in your default Markdown editor (Word, VS Code, Notepad, Typora, etc.).
4. Click **📁 Open Output Directory** to open Windows File Explorer directly to the `output/` folder containing all saved briefs.

---

## 🛠️ Summary of Controls & Troubleshooting

| Feature | Location | Description |
| :--- | :--- | :--- |
| **API Status** | Sidebar | Indicates whether `ANTHROPIC_API_KEY` is present. |
| **Dry-Run / Mock Mode** | Run Intelligence Tab | Enable switch to test workflow without incurring API calls. |
| **Appearance Mode** | Sidebar Bottom | Switch between **Dark**, **Light**, or **System** visual themes. |
| **Output Directory** | `output/` folder | Contains timestamped report files (e.g. `digest_2026_08_20_140000.md`). |

*For support or custom source additions (new subreddits/RSS feeds), update `config.yaml` or contact your system administrator.*
