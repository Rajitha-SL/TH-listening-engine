# 🛰️ Trailhead Market Listening Engine

An enterprise market listening and AI adoption intelligence suite built for **Trailhead Communications**. The engine automatically monitors, ingests, filters, and synthesizes unstructured market signals across enterprise practitioner communities (Reddit, IT/HR forums, RSS feeds) to surface frontline friction patterns regarding AI adoption, tool dissatisfaction, and operational workarounds.

---

## 🌟 Key Features

- **Multi-Source Data Ingestion**: Automatically collects posts and comments from targeted subreddits (`r/humanresources`, `r/managers`, `r/sysadmin`, etc.) and industry RSS feeds.
- **Noise & Fluff Filtering**: Pre-filters promotional posts, vendor marketing, webinars, and low-signal fluff before AI synthesis.
- **Claude 3.5 Sonnet Synthesis**: Leverages Anthropic's Claude 3.5 Sonnet with Pydantic structured output models to categorize market findings into hypotheses (H1, H2, H3, Emerging).
- **Strict Evidence Standards**: Every finding requires verbatim quotes, persona tags (e.g. *IT Admin*, *HR Director*), company context, upvote signals, and source URLs.
- **Longitudinal Trend Memory**: Tracks historical pattern recurrence across runs (`memory/history_store.json`), labeling patterns as `New Pattern`, `Strengthening`, or `Fading`.
- **Native Desktop GUI Suite**: Built with CustomTkinter for executive operation, featuring one-click execution, live console output, background scheduler, API key configuration, and built-in report viewing.
- **Dual Execution Modes**:
  - **Automated Weekly Digest**: Comprehensive multi-source scan for weekly advisory reports.
  - **On-Demand Targeted Query Brief**: Fast, focused intelligence briefs for specific client prompts.
- **Standalone Distribution**: Fully packaged PyInstaller distribution ready for non-technical users.

---

## 🏗️ Architecture Overview

```text
TH-listening-engine/
├── config.yaml                     # Ingestion sources, keywords, and hypothesis definitions
├── main.py                         # CLI entrypoint & execution pipelines
├── gui.py                          # CustomTkinter native desktop application
├── gui.spec                        # PyInstaller spec configuration (collects CustomTkinter assets)
├── build_exe.py                    # Automated build script producing standalone EXE & ZIP archive
├── CLIENT_SETUP_GUIDE.md           # Client user manual for Barbara Roos
├── memory/                         # Persistence directory for trend memory store
│   └── history_store.json
├── output/                         # Generated Markdown intelligence briefs
├── src/
│   ├── collectors/                 # Reddit (PRAW/JSON) & Web (RSS) collectors
│   │   ├── reddit_collector.py
│   │   └── web_collector.py
│   ├── processors/                 # Content filtering & Claude 3.5 Sonnet synthesis
│   │   ├── filter.py
│   │   └── claude_synthesizer.py
│   ├── storage/                    # Trend memory manager & occurrence counter
│   │   └── memory_manager.py
│   └── formatters/                 # Markdown digest & query brief builder
│       └── markdown_builder.py
└── tests/                          # Pytest suite covering collectors, synthesizer, memory, & GUI
    ├── test_engine.py
    └── test_gui.py
```

---

## 🚀 Quick Start

### 1. Prerequisites & Setup

Ensure Python 3.10+ is installed. Clone the repository and install dependencies:

```bash
git clone https://github.com/Rajitha-SL/TH-listening-engine.git
cd TH-listening-engine
pip install -r requirements.txt
```

Set up your `.env` file with your Anthropic API key:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

---

## 💻 Usage

### A. Desktop Application (GUI)

Launch the native CustomTkinter desktop interface:

```bash
python gui.py
```

Features include:
- **Run Intelligence Tab**: Select mode, enter custom queries or use presets, adjust lookback days slider, and run live.
- **Settings & API Key Tab**: Manage Claude API key securely in local `.env`.
- **Background Scheduler Tab**: Configure auto-runs for Monday 07:00 AM PT (14:00 UTC).
- **Reports Viewer Tab**: Preview generated markdown reports inline or open in default viewer.

---

### B. Command-Line Interface (CLI)

#### 1. Automated Weekly Digest Mode
```bash
python main.py --mode weekly --days 7
```

#### 2. Targeted Query Brief Mode
```bash
python main.py --mode query --prompt "M365 Copilot security risks in legal" --days 14
```

#### 3. Dry-Run / Mock Mode (No API Calls)
```bash
python main.py --mode query --prompt "middle manager adoption burden" --mock
```

---

## 📦 Building Standalone Executable

To package the desktop application into a standalone folder and distribution ZIP archive for client delivery:

```bash
python build_exe.py
```

The build script invokes PyInstaller using `gui.spec` with full CustomTkinter asset collection (`--collect-all customtkinter`) and generates:
- Standalone Folder: `dist/TrailheadEngine/`
- Zip Archive: `dist/TrailheadEngine_v1.0_Standalone.zip`

Client user guide is available in [`CLIENT_SETUP_GUIDE.md`](CLIENT_SETUP_GUIDE.md).

---

## 🧪 Testing

Run the full unit and integration test suite:

```bash
python -m pytest
```

---

## 📄 License

Internal tool built for **Trailhead Communications**. All rights reserved.