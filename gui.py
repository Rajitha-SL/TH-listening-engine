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
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

import customtkinter as ctk
import schedule
from dotenv import load_dotenv

import tkinter.messagebox
from main import run_weekly_mode, run_query_mode, load_config, get_resource_path
from src.storage.trend_memory import TrendMemoryStore

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
    def __init__(self, mode="weekly", prompt=None, days=None, limit=5, mock=False, history="memory/history_store.json", output_dir="output"):
        self.mode = mode
        self.prompt = prompt
        self.days = days
        self.limit = limit
        self.article_limit = limit
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


def _get_app_root() -> Path:
    """Returns persistent application root directory for both source and PyInstaller executable runs."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


class TrailheadApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Trailhead Market Listening Engine - Desktop Suite")
        self.minsize(980, 700)
        self.pack_propagate(False)

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

        # Enforce permanent zoomed state via Tk event queue to avoid CustomTkinter resize bounce
        self.after(150, lambda: self.state("zoomed"))

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
        """Creates clean, modern dark/light sidebar with status indicators."""
        self.sidebar_frame = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar_frame.pack(side="left", fill="y", padx=0, pady=0)
        self.sidebar_frame.pack_propagate(False)

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
            text="Weekly Scheduler:", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.sched_status_title.pack(padx=10, pady=(8, 2), anchor="w")

        self.sched_status_lbl = ctk.CTkLabel(
            self.sched_status_box, 
            text="Active", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="green"
        )
        self.sched_status_lbl.pack(padx=10, pady=(0, 2), anchor="w")

        self.sched_next_lbl = ctk.CTkLabel(
            self.sched_status_box, 
            text="Next: Mon 08:00", 
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        self.sched_next_lbl.pack(padx=10, pady=(0, 8), anchor="w")

        # Quick Actions Section
        self.actions_lbl = ctk.CTkLabel(
            self.sidebar_frame, 
            text="Quick Actions", 
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.actions_lbl.pack(padx=20, pady=(15, 5), anchor="w")

        self.btn_open_out = ctk.CTkButton(
            self.sidebar_frame,
            text="📁 Open Output Folder",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            anchor="w",
            command=self._open_output_folder
        )
        self.btn_open_out.pack(padx=15, pady=5, fill="x")

        self.btn_open_env = ctk.CTkButton(
            self.sidebar_frame,
            text="🔑 Configure API Key",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            anchor="w",
            command=self._open_env_dialog
        )
        self.btn_open_env.pack(padx=15, pady=5, fill="x")

        self.btn_help = ctk.CTkButton(
            self.sidebar_frame,
            text="❓ Help & Documentation",
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            anchor="w",
            command=self._show_help_dialog
        )
        self.btn_help.pack(padx=15, pady=5, fill="x")

        # Appearance Mode Dropdown Header
        self.appearance_header = ctk.CTkLabel(
            self.sidebar_frame,
            text="Appearance Mode",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="gray"
        )
        self.appearance_header.pack(padx=20, pady=(20, 2), anchor="w")

        # Theme Switcher Dropdown
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Dark", "Light", "System"],
            command=self._change_appearance_mode
        )
        self.appearance_mode_optionemenu.pack(padx=15, pady=(0, 15), fill="x", side="bottom")

    def _create_tabview(self):
        self.tabview = ctk.CTkTabview(self, corner_radius=10)
        self.tabview.pack(side="right", fill="both", expand=True, padx=15, pady=15)
        self.tabview.pack_propagate(False)

        self.tab_run = self.tabview.add(" Run Intelligence ")
        self.tab_config = self.tabview.add(" Settings & API Key ")
        self.tab_scheduler = self.tabview.add(" Background Scheduler ")
        self.tab_reports = self.tabview.add(" Reports Viewer ")
        self.tab_help = self.tabview.add(" 📖 Help & Manual ")

        # Scrollable Viewports for fixed-geometry tab consistency
        self.scroll_run = ctk.CTkScrollableFrame(self.tab_run, fg_color="transparent")
        self.scroll_run.pack(fill="both", expand=True, padx=10, pady=10)

        self.scroll_config = ctk.CTkScrollableFrame(self.tab_config, fg_color="transparent")
        self.scroll_config.pack(fill="both", expand=True, padx=10, pady=10)

        self.scroll_scheduler = ctk.CTkScrollableFrame(self.tab_scheduler, fg_color="transparent")
        self.scroll_scheduler.pack(fill="both", expand=True, padx=10, pady=10)

        self.scroll_reports = ctk.CTkScrollableFrame(self.tab_reports, fg_color="transparent")
        self.scroll_reports.pack(fill="both", expand=True, padx=10, pady=10)

        self.scroll_help = ctk.CTkScrollableFrame(self.tab_help, fg_color="transparent")
        self.scroll_help.pack(fill="both", expand=True, padx=10, pady=10)

        self._setup_run_tab()
        self._setup_config_tab()
        self._setup_scheduler_tab()
        self._setup_reports_tab()
        self._setup_help_tab()

    def _setup_run_tab(self):
        # Mode Selection
        self.mode_frame = ctk.CTkFrame(self.scroll_run, fg_color="transparent")
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
        self.query_frame = ctk.CTkFrame(self.scroll_run, fg_color=("gray90", "gray17"), corner_radius=8)
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
        self.presets_frame.pack(fill="x", padx=15, pady=(0, 10))

        self.preset_lbl = ctk.CTkLabel(self.presets_frame, text="Quick Focus Presets:", font=ctk.CTkFont(size=11), text_color="gray")
        self.preset_lbl.pack(side="left", padx=(0, 10))

        presets = [
            ("Copilot Friction", "Copilot developer friction"),
            ("Shadow AI Risks", "Shadow AI ChatGPT data"),
            ("Manager Burden", "Manager AI workflow metrics"),
            ("Legal Compliance", "Enterprise AI legal compliance")
        ]

        for title, text in presets:
            btn = ctk.CTkButton(
                self.presets_frame, text=title, font=ctk.CTkFont(size=11, weight="bold"),
                height=26, fg_color=("gray80", "gray25"), text_color=("black", "white"),
                hover_color=("gray70", "gray35"),
                command=lambda t_title=title, t_text=text: self._set_preset_prompt(t_title, t_text)
            )
            btn.pack(side="left", padx=4)

        # Execution Controls (Days Lookback, Article Count & Mock Mode)
        self.opts_frame = ctk.CTkFrame(self.scroll_run, fg_color=("gray90", "gray17"), corner_radius=8)
        self.opts_frame.pack(fill="x", padx=10, pady=10)

        # Row 1: Lookback Timeframe slider + numerical value badge
        row1 = ctk.CTkFrame(self.opts_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(10, 5))

        self.days_lbl = ctk.CTkLabel(row1, text="Lookback Timeframe:", font=ctk.CTkFont(size=12, weight="bold"))
        self.days_lbl.pack(side="left", padx=(0, 5))

        self.btn_help_days = ctk.CTkButton(
            row1, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Lookback Days Help",
                "Filters ingested Reddit posts and RSS articles by age.\n\n• 7 Days: Best for recent weekly trend monitoring.\n• 14-30 Days: Best for deeper historical research and on-demand client prep briefs."
            )
        )
        self.btn_help_days.pack(side="left", padx=(0, 15))

        self.days_slider = ctk.CTkSlider(
            row1, from_=1, to=30, number_of_steps=29, width=180,
            command=self._on_slider_change
        )
        self.days_slider.set(7)
        self.days_slider.pack(side="left", padx=5)

        self.days_val_lbl = ctk.CTkLabel(row1, text="7 Days", font=ctk.CTkFont(size=12, weight="bold"), width=60)
        self.days_val_lbl.pack(side="left", padx=5)

        # Row 2: Number of Articles slider + numerical value badge
        row2 = ctk.CTkFrame(self.opts_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=5)

        self.limit_lbl = ctk.CTkLabel(row2, text="Number of Articles:", font=ctk.CTkFont(size=12, weight="bold"))
        self.limit_lbl.pack(side="left", padx=(0, 5))

        self.btn_help_limit = ctk.CTkButton(
            row2, text="?", width=24, height=24, font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("gray70", "gray30"), hover_color=("gray60", "gray40"),
            command=lambda: self._show_tooltip_popup(
                "Top Evidence Articles Help",
                "Controls the target number of grounded evidence items synthesized and displayed in the output brief (5 to 12 articles)."
            )
        )
        self.btn_help_limit.pack(side="left", padx=(0, 15))

        self.limit_slider = ctk.CTkSlider(
            row2, from_=5, to=12, number_of_steps=7, width=180,
            command=self._on_limit_slider_change
        )
        self.limit_slider.set(5)
        self.limit_slider.pack(side="left", padx=5)

        self.limit_val_lbl = ctk.CTkLabel(row2, text="5 Articles", font=ctk.CTkFont(size=12, weight="bold"), width=70)
        self.limit_val_lbl.pack(side="left", padx=5)

        # Row 3: Dry-Run / Mock Mode toggle switch + descriptive caption
        row3 = ctk.CTkFrame(self.opts_frame, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(5, 10))

        self.mock_var = ctk.BooleanVar(value=False)
        self.mock_switch = ctk.CTkSwitch(
            row3, text="Dry-Run / Mock Mode", 
            variable=self.mock_var, font=ctk.CTkFont(size=12, weight="bold")
        )
        self.mock_switch.pack(side="left", padx=(0, 10))

        mock_desc = ctk.CTkLabel(
            row3, text="(Simulate pipeline without consuming Anthropic API tokens)", 
            font=ctk.CTkFont(size=11, slant="italic"), text_color="gray"
        )
        mock_desc.pack(side="left", padx=0)

        # Action Buttons
        self.actions_frame = ctk.CTkFrame(self.scroll_run, fg_color="transparent")
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
        self.stop_btn = self.cancel_btn

        # Live Terminal Console Log Display
        self.log_frame = ctk.CTkFrame(self.scroll_run, fg_color=("gray90", "gray17"), corner_radius=8)
        self.log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        self.log_title = ctk.CTkLabel(self.log_frame, text="Live Execution Console Output:", font=ctk.CTkFont(size=12, weight="bold"))
        self.log_title.pack(padx=10, pady=(8, 2), anchor="w")

        self.console_textbox = ctk.CTkTextbox(
            self.log_frame, font=ctk.CTkFont(family="Consolas", size=11),
            fg_color=("white", "black"), text_color=("black", "#00ff66"),
            height=240
        )
        self.console_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.console_textbox.configure(state="disabled")
        self.log_textbox = self.console_textbox

    def _setup_config_tab(self):
        # API Key Card
        self.key_box = ctk.CTkFrame(self.scroll_config, fg_color=("gray90", "gray17"), corner_radius=8)
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
        self.sources_frame = ctk.CTkFrame(self.scroll_config, fg_color=("gray90", "gray17"), corner_radius=8)
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
        self.sched_box = ctk.CTkFrame(self.scroll_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
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
        self.sched_opts = ctk.CTkFrame(self.scroll_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
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
        self.next_run_box = ctk.CTkFrame(self.scroll_scheduler, fg_color=("gray90", "gray17"), corner_radius=8)
        self.next_run_box.pack(fill="x", padx=15, pady=(0, 15))

        self.next_run_title = ctk.CTkLabel(self.next_run_box, text="Next Scheduled Run Status:", font=ctk.CTkFont(size=12, weight="bold"))
        self.next_run_title.pack(padx=15, pady=(12, 2), anchor="w")

        self.next_run_lbl = ctk.CTkLabel(
            self.next_run_box, text="Schedule is currently turned off.", 
            font=ctk.CTkFont(size=13), text_color="gray"
        )
        self.next_run_lbl.pack(padx=15, pady=(0, 12), anchor="w")

    def _setup_reports_tab(self):
        self.reports_top_frame = ctk.CTkFrame(self.scroll_reports, fg_color="transparent")
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

        # Historical Trend Velocity Panel
        self.trend_frame = ctk.CTkFrame(self.scroll_reports, fg_color=("gray90", "gray17"), corner_radius=8)
        self.trend_frame.pack(fill="x", padx=10, pady=(5, 10))

        self.trend_hdr = ctk.CTkFrame(self.trend_frame, fg_color="transparent")
        self.trend_hdr.pack(fill="x", padx=10, pady=5)

        self.trend_lbl = ctk.CTkLabel(
            self.trend_hdr, text="📊 Historical Trend Velocity Memory & Run Snapshots",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.trend_lbl.pack(side="left", padx=5)

        self.clear_mem_btn = ctk.CTkButton(
            self.trend_hdr, text="🗑️ Clear Historical Memory Cache", width=220,
            fg_color="#831843", hover_color="#9f1239",
            command=self._clear_memory_cache_dialog
        )
        self.clear_mem_btn.pack(side="right", padx=5)

        # Split View: Left List, Right Markdown/HTML Preview
        self.reports_split_frame = ctk.CTkFrame(self.scroll_reports, fg_color="transparent")
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
            self.reports_preview_frame, font=ctk.CTkFont(size=12), height=360
        )
        self.preview_textbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _setup_help_tab(self):
        # Quick action buttons at top
        self.help_top_frame = ctk.CTkFrame(self.scroll_help, fg_color="transparent")
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

        # Help Card Containers with Structured Text & Bullet Formatting
        help_sections = [
            ("1. QUICK START IN 3 STEPS", [
                "• Step 1: Add your Anthropic API Key under the 'Settings & API Key' tab. Saved securely to local .env file.",
                "• Step 2: Choose an execution mode: 'Targeted Query Brief' for specific topics or 'Automated Weekly Digest' for broad scans.",
                "• Step 3: Click 'Run Ingestion & Synthesis Engine' to launch parallel multi-source collection and Claude synthesis."
            ]),
            ("2. QUERY CUSTOMIZATION & FOCUS PRESETS", [
                "• On-Demand Focus: Type any custom advisory question or select 1-click presets (Copilot Developer Friction, Shadow AI Risks, Manager Burden, Legal Compliance).",
                "• Lookback Window: Adjust lookback slider from 1 to 30 days (applies hard UNIX timestamp gating).",
                "• Article Count: Select 3 to 5 evidence cards to balance depth over volume without fluff."
            ]),
            ("3. UNDERSTANDING OUTPUT BRIEFS & TREND MOMENTUM", [
                "• Framework Hypotheses: [H1] Fear to Impatience, [H2] Middle Manager Burden, [H3] Executive Mandate vs Reality, [EMERGING] Unprompted Patterns.",
                "• Trend Velocity Badges: Green (▲ Strengthening ≥ +15%), Blue (● Steady ±14%), Amber (▼ Fading ≤ -15%), Purple (✨ New Pattern).",
                "• Direct Source Links: Click direct links to open verified Reddit discussions or job postings."
            ]),
            ("4. AUTOMATED BACKGROUND WEEKLY DIGEST", [
                "• Automatic Scanning: Enable the background scheduler switch to automate weekly scanning.",
                "• Default Schedule: Runs Mondays at 07:00 AM PT (14:00 UTC) continuously while desktop suite is open.",
                "• Automatic Saving: Saves formatted .html and .md reports directly to output/ folder."
            ]),
            ("5. REPORTS VIEWER & MEMORY CACHE MANAGEMENT", [
                "• Built-in Viewer: Browse past reports under 'Generated Reports', preview markdown text, or click 'Launch HTML in Web Browser'.",
                "• Trend Memory Store: Snapshot history stored in data/trend_history.db.",
                "• Reset Baselines: Click 'Clear Historical Memory Cache' in the Reports tab to clear trend velocity memory."
            ])
        ]

        for sec_title, bullet_points in help_sections:
            sec_card = ctk.CTkFrame(self.scroll_help, fg_color=("gray90", "gray17"), corner_radius=8)
            sec_card.pack(fill="x", padx=10, pady=6)

            card_lbl = ctk.CTkLabel(
                sec_card, text=sec_title, 
                font=ctk.CTkFont(size=13, weight="bold")
            )
            card_lbl.pack(padx=15, pady=(10, 4), anchor="w")

            for point in bullet_points:
                pt_lbl = ctk.CTkLabel(
                    sec_card, text=point, font=ctk.CTkFont(size=12),
                    justify="left", wraplength=650
                )
                pt_lbl.pack(padx=20, pady=2, anchor="w")
            
            # Spacer at bottom of card
            spacer = ctk.CTkFrame(sec_card, height=6, fg_color="transparent")
            spacer.pack()

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

    def _set_preset_prompt(self, title: str, text: str):
        self.mode_var.set("query")
        self._on_mode_change()
        self.query_entry.configure(state="normal")
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, text)
        self.log_textbox.configure(state="normal")
        self._append_log(f"Selected preset topic: '{title}'")
        self.log_textbox.configure(state="disabled")

    def _on_slider_change(self, value):
        self.days_val_lbl.configure(text=f"{int(value)} Days")

    def _on_limit_slider_change(self, value):
        self.limit_val_lbl.configure(text=f"{int(value)} Articles")

    def _change_appearance_mode(self, new_appearance_mode: str):
        if new_appearance_mode == "System":
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                winreg.CloseKey(key)
                mode = "Light" if val == 1 else "Dark"
                ctk.set_appearance_mode(mode)
            except Exception:
                ctk.set_appearance_mode("System")
        else:
            ctk.set_appearance_mode(new_appearance_mode)

    def _open_output_folder(self):
        """Opens the generated reports/output directory in the Windows File Explorer."""
        try:
            output_dir = _get_app_root() / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if sys.platform == "win32":
                os.startfile(str(output_dir))
            elif sys.platform == "darwin":
                subprocess.run(["open", str(output_dir)])
            else:
                subprocess.run(["xdg-open", str(output_dir)])
                
            self._log(f"[Explorer] Opened output folder: {output_dir}")
        except Exception as e:
            self._log(f"[Error] Could not open output folder: {e}")

    def _open_env_dialog(self):
        """Opens modal dialog for configuring API key."""
        dialog = ctk.CTkInputDialog(text="Enter your Anthropic Claude API Key:", title="Configure API Key")
        key = dialog.get_input()
        if key is not None and key.strip():
            update_env_file("ANTHROPIC_API_KEY", key.strip())
            self._check_api_key_status()
            self._log("[Config] API Key saved to .env file.")

    def _show_help_dialog(self):
        """Opens help and documentation popover."""
        self._show_tooltip_popup(
            "Trailhead Engine Documentation",
            "Welcome to Trailhead Market Listening Engine.\n\n"
            "• Weekly Mode: Ingests signals across all monitored subreddits & RSS feeds over the past week.\n"
            "• Targeted Query Brief: On-demand focused query brief matching your search prompt.\n"
            "• Output: Generates executive Markdown & interactive HTML reports saved to output/ folder.\n"
            "• Presets: Click any preset button to auto-fill high-density search terms."
        )

    def _log(self, message: str):
        """Thread-safe UI log update alias."""
        self._append_log(message)

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
        """Handles user request to stop a running background job."""
        self._log("\n⚠️ Stop requested. Resetting engine state...")
        self.is_running = False
        if hasattr(self, "run_btn") and self.run_btn:
            self.run_btn.configure(state="normal", text="🚀 Run Ingestion & Synthesis Engine")
        if hasattr(self, "stop_btn") and self.stop_btn:
            self.stop_btn.configure(state="disabled")
        if hasattr(self, "cancel_btn") and self.cancel_btn:
            self.cancel_btn.configure(state="disabled")
        if hasattr(self, "progress_bar") and self.progress_bar:
            self.progress_bar.stop()

    def _start_engine_run(self):
        if self.is_running:
            return

        mode = self.mode_var.get()
        prompt = self.query_entry.get().strip()
        days = int(self.days_slider.get())
        limit = int(self.limit_slider.get())
        mock = self.mock_switch.get() == 1

        if mode == "query" and not prompt:
            self.log_textbox.configure(state="normal")
            self.log_textbox.delete("1.0", "end")
            self.log_textbox.insert("end", "⚠️ Please enter a Target Intelligence Prompt Query before running the engine.\n")
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")
            self._set_running_state(False)
            return

        self._set_running_state(True)
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
        
        self._append_log(f"[Engine] Target Query: '{prompt}'")
        self._append_log(f"[Engine] Lookback Window: {days} days")
        self._append_log(f"[Engine] Target Output Limit: {limit} articles")
        self._append_log(f"[Engine] Dry-Run / Mock Mode: {mock}")
        self._append_log(f"Starting Engine execution [Mode: {mode.upper()}]...")

        # Worker Thread execution
        thread = threading.Thread(
            target=self._worker_run_engine,
            args=(mode, prompt, days, limit, mock),
            daemon=True
        )
        thread.start()

    def _worker_run_engine(self, mode: str, prompt: str, days: int, limit: int, mock: bool):
        """Background worker thread to run main engine without blocking GUI."""
        args = EngineArgs(mode=mode, prompt=prompt, days=days, limit=limit, mock=mock)
        try:
            if mode == "weekly":
                output_file = run_weekly_mode(
                    self.config_data, args, status_callback=self._append_log
                )
            else:
                output_file = run_query_mode(
                    self.config_data, args, status_callback=self._append_log
                )

            self._append_log(f"\n✅ SUCCESS: Report generated at: {output_file}")
            self.after(0, self._refresh_report_list)
        except Exception as e:
            import traceback
            err_details = traceback.format_exc()
            self._append_log(f"\n❌ ERROR during engine execution: {e}\n{err_details}")
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

    def _clear_memory_cache_dialog(self):
        msg = "Are you sure you want to clear all historical trend velocity baselines?\n\nThis will reset cross-run signal tracking."
        if tkinter.messagebox.askyesno("Confirm Memory Reset", msg):
            try:
                store = TrendMemoryStore()
                store.clear_memory_cache()
                self._append_console_log("[Memory] Trend baseline history reset.")
                tkinter.messagebox.showinfo("Memory Reset", "Historical trend memory store cleared successfully.")
            except Exception as e:
                tkinter.messagebox.showerror("Error", f"Failed to clear memory: {e}")


def main():
    app = TrailheadApp()
    app.mainloop()


if __name__ == "__main__":
    main()
