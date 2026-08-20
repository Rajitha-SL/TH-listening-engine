"""
Trailhead Market Listening Engine - Native Desktop GUI Application
Built with CustomTkinter for executive-ready standalone operation.
"""

import sys
import os
import threading
import subprocess
import time
import argparse
import webbrowser
from datetime import datetime
from typing import Dict, Any, Optional

import customtkinter as ctk
import schedule
from dotenv import load_dotenv

from main import run_weekly_mode, run_query_mode, load_config, get_resource_path

# Initialize dotenv
load_dotenv()

# Set default CustomTkinter appearance & theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def update_env_file(key: str, value: str, env_path: str = ".env"):
    """Updates or inserts key=value pair in .env file."""
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                found = True
                break
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    os.environ[key] = value


def open_filepath(filepath: str):
    """Opens a file or directory using system default viewer."""
    if not os.path.exists(filepath):
        return
    try:
        if os.name == 'nt':
            os.startfile(filepath)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', filepath])
        else:
            subprocess.Popen(['xdg-open', filepath])
    except Exception as e:
        print(f"Error opening filepath {filepath}: {e}")


class EngineArgs:
    """Helper namespace for engine arguments."""
    def __init__(self, mode="weekly", prompt=None, days=None, mock=False, history="memory/history_store.json", output_dir="output"):
        self.mode = mode
        self.prompt = prompt
        self.days = days
        self.mock = mock
        self.history = history
        self.output_dir = output_dir


class SchedulerManager:
    """Thread-safe background scheduler manager running as daemon."""
    def __init__(self, run_callback, status_update_callback):
        self.run_callback = run_callback
        self.status_update_callback = status_update_callback
        self.enabled = False
        self.thread = None
        self.stop_event = threading.Event()
        self.scheduled_day = "monday"
        self.scheduled_time = "14:00"  # 14:00 UTC / 07:00 AM PT default

    def start(self):
        if self.enabled:
            return
        self.enabled = True
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.enabled = False
        self.stop_event.set()
        schedule.clear()

    def update_schedule(self, day: str, time_str: str):
        self.scheduled_day = day.lower().strip()
        self.scheduled_time = time_str.strip()
        schedule.clear()
        day_func = getattr(schedule.every(), self.scheduled_day, None)
        if day_func:
            day_func.at(self.scheduled_time).do(self.run_callback)
        else:
            schedule.every().monday.at(self.scheduled_time).do(self.run_callback)

    def _run_loop(self):
        self.update_schedule(self.scheduled_day, self.scheduled_time)
        while not self.stop_event.is_set():
            schedule.run_pending()
            next_run = schedule.next_run()
            if self.status_update_callback and next_run:
                self.status_update_callback(next_run)
            self.stop_event.wait(5.0)


class TrailheadApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Trailhead Market Listening Engine - Desktop Suite")
        self.geometry("1100 x 750")
        self.minsize(950, 650)

        self.config_data = load_config("config.yaml")
        self.is_running = False

        # Build UI layout
        self._create_sidebar()
        self._create_tabview()

        # Initialize Scheduler Manager
        self.scheduler = SchedulerManager(
            run_callback=self._trigger_scheduled_run,
            status_update_callback=self._on_scheduler_next_run_update
        )

        # Refresh state
        self._check_api_key_status()
        self._refresh_report_list()

    def _show_tooltip_popup(self, title: str, text: str):
        """Displays a clean modal popover with help/tooltip information."""
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("520x320")
        popup.resizable(False, False)
        popup.grab_set()

        lbl_title = ctk.CTkLabel(popup, text=title, font=ctk.CTkFont(size=15, weight="bold"))
        lbl_title.pack(padx=20, pady=(20, 10), anchor="w")

        textbox = ctk.CTkTextbox(popup, font=ctk.CTkFont(size=12), wrap="word")
        textbox.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        textbox.insert("1.0", text)
        textbox.configure(state="disabled")

        btn_close = ctk.CTkButton(popup, text="Close", width=100, command=popup.destroy)
        btn_close.pack(pady=(0, 15))

    def _create_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y", padx=0, pady=0)

        # App Title & Subtitle
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text=" Trailhead Engine", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.logo_label.pack(padx=20, pady=(20, 5), anchor="w")

        self.sub_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Market Listening Suite", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray"
        )
        self.sub_label.pack(padx=20, pady=(0, 25), anchor="w")

        # API Key Status Badge
        self.api_status_box = ctk.CTkFrame(self.sidebar_frame, fg_color=("gray85", "gray20"), corner_radius=8)
        self.api_status_box.pack(padx=15, pady=10, fill="x")

        self.api_status_title = ctk.CTkLabel(
            self.api_status_box, 
            text="Claude API Key:", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.api_status_title.pack(padx=10, pady=(8, 2), anchor="w")

        self.api_status_lbl = ctk.CTkLabel(
            self.api_status_box, 
            text="Checking...", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="orange"
        )
        self.api_status_lbl.pack(padx=10, pady=(0, 8), anchor="w")

        # Scheduler Status Badge
        self.sched_status_box = ctk.CTkFrame(self.sidebar_frame, fg_color=("gray85", "gray20"), corner_radius=8)
        self.sched_status_box.pack(padx=15, pady=10, fill="x")

        self.sched_status_title = ctk.CTkLabel(
            self.sched_status_box, 
            text="Auto-Scheduler:", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.sched_status_title.pack(padx=10, pady=(8, 2), anchor="w")

        self.sched_status_lbl = ctk.CTkLabel(
            self.sched_status_box, 
            text="Disabled", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.sched_status_lbl.pack(padx=10, pady=(0, 8), anchor="w")

        # System info & Theme selector at bottom of sidebar
        self.theme_lbl = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", font=ctk.CTkFont(size=12))
        self.theme_lbl.pack(side="bottom", padx=20, pady=(0, 5), anchor="w")

        self.theme_option = ctk.CTkOptionMenu(
            self.sidebar_frame, 
            values=["Dark", "Light", "System"],
            command=self._change_appearance_mode
        )
        self.theme_option.pack(side="bottom", padx=20, pady=(0, 20), fill="x")
        self.theme_option.set("Dark")

    def _create_tabview(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        self.tab_run = self.tabview.add(" Run Intelligence ")
        self.tab_config = self.tabview.add(" Settings & API Key ")
        self.tab_scheduler = self.tabview.add(" Background Scheduler ")
        self.tab_reports = self.tabview.add(" Reports Viewer ")
        self.tab_help = self.tabview.add(" 📖 Help & Manual ")

        self._setup_run_tab()
        self._setup_config_tab()
        self._setup_scheduler_tab()
        self._setup_reports_tab()
        self._setup_help_tab()

    def _setup_run_tab(self):
        # Mode Selection
        self.mode_frame = ctk.CTkFrame(self.tab_run, fg_color="transparent")
        self.mode_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.mode_lbl = ctk.CTkLabel(self.mode_frame, text="Execution Mode:", font=ctk.CTkFont(size=13, weight="bold"))
        self.mode_lbl.pack(side="left", padx=(0, 10))

        self.btn_help_mode = ctk.CTkButton(
            self.mode_frame, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Execution Modes Help",
                "• Targeted Query Brief (Query Mode):\nAllows entering custom prompts or selecting quick presets (e.g. 'Copilot security risks in legal') to run focused market ingestion & synthesis for client meetings.\n\n• Automated Weekly Digest (Weekly Mode):\nExecutes a broad scan across all subreddits and RSS feeds configured in config.yaml, updating historical trend memory store."
            )
        )
        self.btn_help_mode.pack(side="left", padx=(0, 15))

        self.mode_var = ctk.StringVar(value="query")
        self.radio_query = ctk.CTkRadioButton(
            self.mode_frame, text="Targeted Query Brief", variable=self.mode_var, value="query",
            command=self._on_mode_change
        )
        self.radio_query.pack(side="left", padx=10)

        self.radio_weekly = ctk.CTkRadioButton(
            self.mode_frame, text="Automated Weekly Digest", variable=self.mode_var, value="weekly",
            command=self._on_mode_change
        )
        self.radio_weekly.pack(side="left", padx=10)

        # Target Query Section
        self.query_frame = ctk.CTkFrame(self.tab_run, fg_color=("gray90", "gray17"), corner_radius=8)
        self.query_frame.pack(fill="x", padx=10, pady=10)

        self.query_lbl = ctk.CTkLabel(
            self.query_frame, text="Target Intelligence Prompt Query:", 
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.query_lbl.pack(padx=15, pady=(10, 2), anchor="w")

        self.query_entry = ctk.CTkEntry(
            self.query_frame, 
            placeholder_text="e.g. M365 Copilot security risks and shadow AI bypasses",
            font=ctk.CTkFont(size=13)
        )
        self.query_entry.pack(padx=15, pady=(0, 10), fill="x")

        # Presets Buttons
        self.presets_frame = ctk.CTkFrame(self.query_frame, fg_color="transparent")
        self.presets_frame.pack(padx=15, pady=(0, 10), fill="x")

        self.preset_lbl = ctk.CTkLabel(self.presets_frame, text="Quick Presets:", font=ctk.CTkFont(size=11, weight="bold"), text_color="gray")
        self.preset_lbl.pack(side="left", padx=(0, 10))

        p1 = ctk.CTkButton(
            self.presets_frame, text="Copilot Security", height=24, font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray28"), hover_color=("gray65", "gray35"),
            command=lambda: self._set_preset_prompt("Copilot draft emails referencing confidential severance templates")
        )
        p1.pack(side="left", padx=5)

        p2 = ctk.CTkButton(
            self.presets_frame, text="Manager Friction", height=24, font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray28"), hover_color=("gray65", "gray35"),
            command=lambda: self._set_preset_prompt("Middle managers carrying adoption burden and developer refusal")
        )
        p2.pack(side="left", padx=5)

        p3 = ctk.CTkButton(
            self.presets_frame, text="Shadow AI Bypasses", height=24, font=ctk.CTkFont(size=11),
            fg_color=("gray75", "gray28"), hover_color=("gray65", "gray35"),
            command=lambda: self._set_preset_prompt("Sysadmin lockdowns driving legal and frontline shadow AI workarounds")
        )
        p3.pack(side="left", padx=5)

        # Execution Controls (Days Lookback & Mock Mode)
        self.opts_frame = ctk.CTkFrame(self.tab_run, fg_color="transparent")
        self.opts_frame.pack(fill="x", padx=10, pady=5)

        self.days_lbl = ctk.CTkLabel(self.opts_frame, text="Lookback Days:", font=ctk.CTkFont(size=12, weight="bold"))
        self.days_lbl.pack(side="left", padx=(0, 5))

        self.btn_help_days = ctk.CTkButton(
            self.opts_frame, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Lookback Days Help",
                "Filters ingested Reddit posts and RSS articles by age.\n\n• 7 Days: Best for recent weekly trend monitoring.\n• 14-30 Days: Best for deeper historical research and on-demand client prep briefs."
            )
        )
        self.btn_help_days.pack(side="left", padx=(0, 10))

        self.days_slider = ctk.CTkSlider(
            self.opts_frame, from_=1, to=30, number_of_steps=29, width=180,
            command=self._on_slider_change
        )
        self.days_slider.set(7)
        self.days_slider.pack(side="left", padx=5)

        self.days_val_lbl = ctk.CTkLabel(self.opts_frame, text="7 Days", font=ctk.CTkFont(size=12, weight="bold"), width=50)
        self.days_val_lbl.pack(side="left", padx=5)

        self.mock_var = ctk.BooleanVar(value=False)
        self.mock_switch = ctk.CTkSwitch(
            self.opts_frame, text="Dry-Run / Mock Mode (Offline Testing)", 
            variable=self.mock_var, font=ctk.CTkFont(size=12)
        )
        self.mock_switch.pack(side="right", padx=10)

        # Action Buttons
        self.actions_frame = ctk.CTkFrame(self.tab_run, fg_color="transparent")
        self.actions_frame.pack(fill="x", padx=10, pady=10)

        self.run_btn = ctk.CTkButton(
            self.actions_frame, text="🚀 Run Ingestion & Synthesis Engine", 
            font=ctk.CTkFont(size=14, weight="bold"), height=40,
            fg_color="#1f538d", hover_color="#14375e",
            command=self._start_engine_run
        )
        self.run_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.cancel_btn = ctk.CTkButton(
            self.actions_frame, text="Stop Engine", 
            font=ctk.CTkFont(size=13, weight="bold"), height=40, width=120,
            fg_color="#c0392b", hover_color="#962d22", state="disabled",
            command=self._on_stop_engine_click
        )
        self.cancel_btn.pack(side="right")

        # Live Terminal Console Log Display
        self.log_frame = ctk.CTkFrame(self.tab_run, fg_color=("gray90", "gray17"), corner_radius=8)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.log_title = ctk.CTkLabel(self.log_frame, text="Live Execution Console Output:", font=ctk.CTkFont(size=12, weight="bold"))
        self.log_title.pack(padx=10, pady=(8, 2), anchor="w")

        self.console_textbox = ctk.CTkTextbox(
            self.log_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("white", "black"), text_color=("black", "#00ff66")
        )
        self.console_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.console_textbox.configure(state="disabled")

    def _setup_config_tab(self):
        # API Key Card
        self.key_box = ctk.CTkFrame(self.tab_config, fg_color=("gray90", "gray17"), corner_radius=8)
        self.key_box.pack(fill="x", padx=15, pady=15)

        self.api_key_lbl = ctk.CTkLabel(
            self.key_box, text="🔑 Anthropic Claude API Key Configuration", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.api_key_lbl.pack(side="left", padx=15, pady=(15, 5))

        self.btn_help_api = ctk.CTkButton(
            self.key_box, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Claude API Key Help",
                "What is it?\nYour API key connects the engine to Anthropic's Claude 3.5 Sonnet LLM for market synthesis.\n\nSecurity:\nStored strictly in your local .env file. Never uploaded or shared.\n\nHow to get a key:\nSign in to console.anthropic.com, navigate to API Keys, and generate a key starting with 'sk-ant-api...'."
            )
        )
        self.btn_help_api.pack(side="right", padx=15, pady=(15, 5))

        self.api_key_desc = ctk.CTkLabel(
            self.key_box, 
            text="Enter your Anthropic API Key below. It will be saved securely to your local .env file.",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.api_key_desc.pack(padx=15, pady=(0, 10), anchor="w")

        self.key_entry_frame = ctk.CTkFrame(self.key_box, fg_color="transparent")
        self.key_entry_frame.pack(fill="x", padx=15, pady=(0, 15))

        current_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.api_key_entry = ctk.CTkEntry(
            self.key_entry_frame, show="*", placeholder_text="sk-ant-api...",
            font=ctk.CTkFont(size=13)
        )
        self.api_key_entry.insert(0, current_key)
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.show_key_var = ctk.BooleanVar(value=False)
        self.show_key_chk = ctk.CTkCheckBox(
            self.key_entry_frame, text="Show Key", variable=self.show_key_var,
            command=self._toggle_show_key, width=80
        )
        self.show_key_chk.pack(side="left", padx=5)

        self.save_key_btn = ctk.CTkButton(
            self.key_entry_frame, text="Save Key", width=100,
            command=self._save_api_key
        )
        self.save_key_btn.pack(side="left", padx=5)

        # Config YAML preview/info
        self.sources_frame = ctk.CTkFrame(self.tab_config, fg_color=("gray90", "gray17"), corner_radius=8)
        self.sources_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.sources_lbl = ctk.CTkLabel(
            self.sources_frame, text="📡 Active Target Data Sources (config.yaml)", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.sources_lbl.pack(padx=15, pady=(15, 5), anchor="w")

        subreddits = self.config_data.get("target_sources", {}).get("subreddits", [])
        rss_feeds = self.config_data.get("target_sources", {}).get("rss_feeds", [])

        formatted_subreddits = [f"r/{s}" if isinstance(s, str) else f"r/{s.get('name', str(s))}" for s in subreddits]

        formatted_rss = []
        for feed in rss_feeds:
            if isinstance(feed, dict):
                name = feed.get("name")
                url = feed.get("url")
                if name and url:
                    formatted_rss.append(f"{name} ({url})")
                elif name:
                    formatted_rss.append(name)
                elif url:
                    formatted_rss.append(url)
            elif isinstance(feed, str):
                formatted_rss.append(feed)
            else:
                formatted_rss.append(str(feed))

        sources_text = f"Subreddits ({len(subreddits)}):\n  " + (", ".join(formatted_subreddits) if formatted_subreddits else "None configured") + "\n\n"
        sources_text += f"RSS Feeds ({len(rss_feeds)}):\n  " + ("\n  ".join(formatted_rss) if formatted_rss else "None configured")

        self.sources_textbox = ctk.CTkTextbox(self.sources_frame, font=ctk.CTkFont(size=12))
        self.sources_textbox.pack(fill="both", expand=True, padx=15, pady=(5, 15))
        self.sources_textbox.insert("1.0", sources_text)
        self.sources_textbox.configure(state="disabled")

    def _setup_scheduler_tab(self):
        self.sched_box = ctk.CTkFrame(self.tab_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
        self.sched_box.pack(fill="x", padx=15, pady=15)

        self.sched_title = ctk.CTkLabel(
            self.sched_box, text="⏰ Automated Background Digest Scheduling", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.sched_title.pack(side="left", padx=15, pady=(15, 5))

        self.btn_help_sched = ctk.CTkButton(
            self.sched_box, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Background Auto-Scheduler Help",
                "Automates Weekly Intelligence Digest generation.\n\n• When enabled, the background daemon loop runs pending schedule tasks.\n• Default timing: Monday at 14:00 UTC (07:00 AM PT).\n• Automatically saves both .md and .html reports to output/ folder."
            )
        )
        self.btn_help_sched.pack(side="right", padx=15, pady=(15, 5))

        self.sched_desc = ctk.CTkLabel(
            self.sched_box, 
            text="Enable scheduled background runs to automatically produce weekly intelligence digests for Barbara without user intervention.",
            font=ctk.CTkFont(size=12), text_color="gray"
        )
        self.sched_desc.pack(padx=15, pady=(0, 15), anchor="w")

        self.sched_toggle_frame = ctk.CTkFrame(self.sched_box, fg_color="transparent")
        self.sched_toggle_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.sched_switch = ctk.CTkSwitch(
            self.sched_toggle_frame, text="Enable Automated Background Digest Schedule",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_scheduler_toggle
        )
        self.sched_switch.pack(side="left", padx=5)

        # Schedule Config Options
        self.sched_opts = ctk.CTkFrame(self.tab_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
        self.sched_opts.pack(fill="x", padx=15, pady=(0, 15))

        self.day_lbl = ctk.CTkLabel(self.sched_opts, text="Day of Week:", font=ctk.CTkFont(size=12, weight="bold"))
        self.day_lbl.pack(side="left", padx=(15, 5), pady=15)

        self.day_option = ctk.CTkOptionMenu(
            self.sched_opts, 
            values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
            command=self._on_schedule_option_change
        )
        self.day_option.set("Monday")
        self.day_option.pack(side="left", padx=5, pady=15)

        self.time_lbl = ctk.CTkLabel(self.sched_opts, text="Execution Time (UTC):", font=ctk.CTkFont(size=12, weight="bold"))
        self.time_lbl.pack(side="left", padx=(15, 5), pady=15)

        self.time_entry = ctk.CTkEntry(self.sched_opts, width=80, font=ctk.CTkFont(size=12))
        self.time_entry.insert(0, "14:00")
        self.time_entry.pack(side="left", padx=5, pady=15)

        self.update_sched_btn = ctk.CTkButton(
            self.sched_opts, text="Update Timing", width=110,
            command=self._on_schedule_option_change
        )
        self.update_sched_btn.pack(side="left", padx=10, pady=15)

        # Next Scheduled Run Info Display
        self.next_run_box = ctk.CTkFrame(self.tab_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
        self.next_run_box.pack(fill="x", padx=15, pady=(0, 15))

        self.next_run_title = ctk.CTkLabel(self.next_run_box, text="Next Scheduled Run Status:", font=ctk.CTkFont(size=12, weight="bold"))
        self.next_run_title.pack(padx=15, pady=(12, 2), anchor="w")

        self.next_run_lbl = ctk.CTkLabel(
            self.next_run_box, text="Schedule is currently turned off.", 
            font=ctk.CTkFont(size=13), text_color="gray"
        )
        self.next_run_lbl.pack(padx=15, pady=(0, 12), anchor="w")

    def _setup_reports_tab(self):
        self.reports_top_frame = ctk.CTkFrame(self.tab_reports, fg_color="transparent")
        self.reports_top_frame.pack(fill="x", padx=10, pady=10)

        self.refresh_reports_btn = ctk.CTkButton(
            self.reports_top_frame, text="🔄 Refresh Reports List", width=160,
            command=self._refresh_report_list
        )
        self.refresh_reports_btn.pack(side="left", padx=(0, 10))

        self.open_folder_btn = ctk.CTkButton(
            self.reports_top_frame, text="📁 Open Output Directory", width=170,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray38"),
            command=lambda: open_filepath(os.path.abspath("output"))
        )
        self.open_folder_btn.pack(side="left", padx=5)

        self.open_html_btn = ctk.CTkButton(
            self.reports_top_frame, text="🌐 Launch HTML in Web Browser", width=210,
            fg_color="#2fa572", hover_color="#1e6b4a",
            command=self._open_selected_report_browser
        )
        self.open_html_btn.pack(side="right", padx=5)

        self.open_file_btn = ctk.CTkButton(
            self.reports_top_frame, text="↗️ Open Selected File", width=160,
            fg_color="#1f538d", hover_color="#14375e",
            command=self._open_selected_report_external
        )
        self.open_file_btn.pack(side="right", padx=5)

        # Split View: Left List, Right Markdown/HTML Preview
        self.reports_split_frame = ctk.CTkFrame(self.tab_reports, fg_color="transparent")
        self.reports_split_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Reports Selection Listbox / Option Menu
        self.reports_left_frame = ctk.CTkFrame(self.reports_split_frame, width=280, fg_color=("gray90", "gray17"))
        self.reports_left_frame.pack(side="left", fill="y", padx=(0, 10))

        self.list_lbl = ctk.CTkLabel(self.reports_left_frame, text="Generated Reports (.md & .html):", font=ctk.CTkFont(size=12, weight="bold"))
        self.list_lbl.pack(padx=10, pady=(10, 5), anchor="w")

        self.reports_option_menu = ctk.CTkOptionMenu(
            self.reports_left_frame, values=["No reports found"],
            command=self._on_report_selected
        )
        self.reports_option_menu.pack(padx=10, pady=10, fill="x")

        # Preview Pane
        self.reports_preview_frame = ctk.CTkFrame(self.reports_split_frame, fg_color=("gray90", "gray17"))
        self.reports_preview_frame.pack(side="right", fill="both", expand=True)

        self.preview_lbl = ctk.CTkLabel(self.reports_preview_frame, text="Report Document Preview:", font=ctk.CTkFont(size=12, weight="bold"))
        self.preview_lbl.pack(padx=10, pady=(10, 5), anchor="w")

        self.preview_textbox = ctk.CTkTextbox(
            self.reports_preview_frame, font=ctk.CTkFont(size=12)
        )
        self.preview_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _setup_help_tab(self):
        # Quick action buttons at top
        self.help_top_frame = ctk.CTkFrame(self.tab_help, fg_color="transparent")
        self.help_top_frame.pack(fill="x", padx=10, pady=10)

        b1 = ctk.CTkButton(
            self.help_top_frame, text="🔑 Anthropic API Console", width=160,
            command=lambda: webbrowser.open("https://console.anthropic.com/")
        )
        b1.pack(side="left", padx=(0, 10))

        b2 = ctk.CTkButton(
            self.help_top_frame, text="📘 Client Setup Manual", width=160,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray38"),
            command=lambda: open_filepath(os.path.abspath("CLIENT_SETUP_GUIDE.md"))
        )
        b2.pack(side="left", padx=5)

        b3 = ctk.CTkButton(
            self.help_top_frame, text="📁 Open Output Directory", width=160,
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray38"),
            command=lambda: open_filepath(os.path.abspath("output"))
        )
        b3.pack(side="left", padx=5)

        # Help Textbox
        self.help_textbox = ctk.CTkTextbox(self.tab_help, font=ctk.CTkFont(size=12))
        self.help_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        help_text = """🛰️ TRAILHEAD MARKET LISTENING ENGINE — IN-APP USER MANUAL

1. GETTING STARTED & SETUP
• Your API Key is configured in the "Settings & API Key" tab.
• Stored safely in your local .env file (never uploaded or shared).
• Get a key at console.anthropic.com.

2. RUNNING INTELLIGENCE INGESTION
• Targeted Query Brief (Query Mode):
  - Enter specific prompts (e.g. "Copilot security risks in legal") or click quick presets.
  - Generates both Markdown (.md) and interactive HTML (.html) reports with direct source evidence links.
• Automated Weekly Digest (Weekly Mode):
  - Comprehensive scan across all configured subreddits and RSS feeds in config.yaml.
  - Updates long-term trend memory store (history_store.json).

3. AUTO-SCHEDULER
• Background daemon auto-runs weekly digests on schedule (default: Monday 07:00 AM PT / 14:00 UTC).
• Runs seamlessly in background while app is open.

4. REPORTS & EXPORTS
• Outputs saved to output/ folder in standardized 24-hour timestamp format:
  - digest_YYYY_MM_DD_HHMM.html & digest_YYYY_MM_DD_HHMM.md
  - query_YYYY_MM_DD_HHMM.html & query_YYYY_MM_DD_HHMM.md
• Click "🌐 Launch HTML in Web Browser" to open interactive HTML report.

5. TROUBLESHOOTING
• Missing API Key: Check Settings & API Key tab. Ensure key starts with sk-ant-api...
• Network Connection: Ingestion requires active internet connection for Reddit & RSS feeds.
• Mock Mode: Enable Dry-Run / Mock Mode switch for testing without invoking external APIs.
"""
        self.help_textbox.insert("1.0", help_text)
        self.help_textbox.configure(state="disabled")

    # --- Controller Logic & Event Handlers ---

    def _check_api_key_status(self):
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if key:
            self.api_status_lbl.configure(text="Configured ✓", text_color="#2FA572")
        else:
            self.api_status_lbl.configure(text="Missing ⚠️", text_color="#E74C3C")

    def _toggle_show_key(self):
        if self.show_key_var.get():
            self.api_key_entry.configure(show="")
        else:
            self.api_key_entry.configure(show="*")

    def _save_api_key(self):
        new_key = self.api_key_entry.get().strip()
        update_env_file("ANTHROPIC_API_KEY", new_key)
        self._check_api_key_status()
        self._append_log("API Key saved successfully to .env")

    def _on_mode_change(self):
        if self.mode_var.get() == "weekly":
            self.query_entry.configure(state="disabled")
        else:
            self.query_entry.configure(state="normal")

    def _set_preset_prompt(self, text: str):
        self.mode_var.set("query")
        self._on_mode_change()
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, text)

    def _on_slider_change(self, value):
        self.days_val_lbl.configure(text=f"{int(value)} days")

    def _change_appearance_mode(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def _append_log(self, message: str):
        """Thread-safe UI log update using self.after(0, ...)"""
        def update():
            self.log_textbox.insert("end", message + "\n")
            self.log_textbox.see("end")
        self.after(0, update)

    def _update_progress(self, val: float):
        """Thread-safe UI progress bar update using self.after(0, ...)"""
        self.after(0, lambda: self.progress_bar.set(val))

    def _set_running_state(self, running: bool):
        """Thread-safe state toggle for buttons."""
        def update():
            self.is_running = running
            if running:
                self.run_btn.configure(state="disabled", text="⏳ Running Engine...")
                self.cancel_btn.configure(state="normal")
            else:
                self.run_btn.configure(state="normal", text="🚀 Run Ingestion & Synthesis Engine")
                self.cancel_btn.configure(state="disabled")
        self.after(0, update)

    def _on_stop_engine_click(self):
        """Handler to cancel or stop engine execution."""
        if not self.is_running:
            return
        self._append_log("⚠️ Engine execution stop requested by user.")
        self._set_running_state(False)

    def _start_engine_run(self):
        if self.is_running:
            return

        mode = self.mode_var.get()
        prompt = self.query_entry.get().strip()
        days = int(self.days_slider.get())
        mock = self.mock_switch.get() == 1

        if mode == "query" and not prompt:
            self._append_log("⚠️ Error: Please enter a target prompt query or select a preset.")
            return

        self._set_running_state(True)
        self.log_textbox.delete("1.0", "end")
        self._append_log(f"Starting Engine execution [Mode: {mode.upper()}, Lookback: {days} days, Mock: {mock}]...")

        # Worker Thread execution
        thread = threading.Thread(
            target=self._worker_run_engine,
            args=(mode, prompt, days, mock),
            daemon=True
        )
        thread.start()

    def _worker_run_engine(self, mode: str, prompt: str, days: int, mock: bool):
        """Background worker thread to run main engine without blocking GUI."""
        args = EngineArgs(mode=mode, prompt=prompt, days=days, mock=mock)
        try:
            if mode == "weekly":
                output_file = run_weekly_mode(
                    self.config_data, args, status_callback=self._append_log
                )
            else:
                output_file = run_query_mode(
                    self.config_data, args, status_callback=self._append_log
                )

            self._append_log(f" SUCCESS: Report generated at: {output_file}")
            self.after(0, self._refresh_report_list)
        except Exception as e:
            self._append_log(f"❌ ERROR during engine execution: {e}")
        finally:
            self._set_running_state(False)

    # --- Background Scheduler Handlers ---

    def _on_scheduler_toggle(self):
        enabled = self.sched_switch.get() == 1
        if enabled:
            day = self.day_option.get()
            time_str = self.time_entry.get().strip() or "14:00"
            self.scheduler.update_schedule(day, time_str)
            self.scheduler.start()
            self.sched_status_lbl.configure(text="Active ✓", text_color="#2FA572")
            self._append_log(f"Scheduler enabled for every {day} at {time_str} UTC.")
        else:
            self.scheduler.stop()
            self.sched_status_lbl.configure(text="Disabled", text_color="gray")
            self.next_run_lbl.configure(text="Schedule is currently turned off.", text_color="gray")
            self._append_log("Scheduler disabled.")

    def _on_schedule_option_change(self, *args):
        if self.sched_switch.get() == 1:
            day = self.day_option.get()
            time_str = self.time_entry.get().strip() or "14:00"
            self.scheduler.update_schedule(day, time_str)
            self._append_log(f"Schedule updated to every {day} at {time_str} UTC.")

    def _on_scheduler_next_run_update(self, next_run_dt: datetime):
        """Thread-safe UI callback from scheduler manager."""
        def update():
            next_str = next_run_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            self.next_run_lbl.configure(text=f"Next Automated Digest: {next_str}", text_color="#2FA572")
        self.after(0, update)

    def _trigger_scheduled_run(self):
        """Callback triggered by `schedule` background worker."""
        if self.is_running:
            self._append_log("⏰ Scheduled run skipped: Engine is currently running another task.")
            return
        self._set_running_state(True)
        self._append_log("⏰ Scheduled Background Run Triggered!")
        thread = threading.Thread(
            target=self._worker_run_engine,
            args=("weekly", "", 7, False),
            daemon=True
        )
        thread.start()

    # --- Reports Viewer Handlers ---

    def _refresh_report_list(self):
        output_dir = "output"
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        files = [f for f in os.listdir(output_dir) if f.endswith(".md") or f.endswith(".html")]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True)

        def update():
            if not files:
                self.reports_option_menu.configure(values=["No reports found"])
                self.reports_option_menu.set("No reports found")
                self.preview_textbox.delete("1.0", "end")
            else:
                self.reports_option_menu.configure(values=files)
                self.reports_option_menu.set(files[0])
                self._on_report_selected(files[0])
        self.after(0, update)

    def _on_report_selected(self, choice: str):
        if choice == "No reports found":
            return
        filepath = os.path.join("output", choice)
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.preview_textbox.delete("1.0", "end")
            self.preview_textbox.insert("1.0", content)

    def _open_selected_report_external(self):
        choice = self.reports_option_menu.get()
        if choice and choice != "No reports found":
            filepath = os.path.abspath(os.path.join("output", choice))
            open_filepath(filepath)

    def _open_selected_report_browser(self):
        choice = self.reports_option_menu.get()
        if choice and choice != "No reports found":
            if choice.endswith(".html"):
                filepath = os.path.abspath(os.path.join("output", choice))
            else:
                base = os.path.splitext(choice)[0]
                html_candidate = base + ".html"
                if os.path.exists(os.path.join("output", html_candidate)):
                    filepath = os.path.abspath(os.path.join("output", html_candidate))
                else:
                    filepath = os.path.abspath(os.path.join("output", choice))
            webbrowser.open(filepath)


def main():
    app = TrailheadApp()
    app.mainloop()


if __name__ == "__main__":
    main()
