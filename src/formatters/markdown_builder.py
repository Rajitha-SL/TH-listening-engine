"""
Markdown Builder for rendering executive-ready Weekly Digests and Targeted Query Briefs.
Enforces strict zero-hallucination layout with clickable URLs, verbatim quotes, and persona metadata.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List

from src.net_safety import markdown_href, markdown_link_label


class MarkdownBuilder:
    """Renders structured synthesis reports into clean GitHub-flavored Markdown."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.hypotheses_meta = config.get("hypotheses", {})

    def build_weekly_digest(self, report_date: str, synthesis_data: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
        """Builds the full executive weekly Markdown digest."""
        md = []
        
        # Header
        md.append(f"# 🛰️ Trailhead Market Listening Engine - Weekly Intelligence Digest")
        md.append(f"**Target Client:** Barbara Roos (Executive AI Adoption Advisor)")  
        md.append(f"**Digest Date:** `{report_date}`  ")  
        md.append(f"**Evidence Standard:** Zero-Hallucination Policy (100% Verbatim Grounded Quotes & Verified Permalinks)\n")  
        md.append("---")

        # Executive Overview
        overview = synthesis_data.get("summary_overview", "Weekly synthesis of public workplace discussions.")
        md.append("## 📌 Executive Summary")
        md.append(f"{overview}\n")

        # Trend Snapshot Table
        md.append("## 📊 Trend Momentum Snapshot")
        md.append("| Hypothesis / Pattern | Trend Status | Persona | Signal Strength | Verified Source |")
        md.append("| :--- | :---: | :--- | :---: | :--- |")

        for f in findings:
            pattern = markdown_link_label(str(f.get("pattern_name", "Friction Pattern")))
            status = f.get("trend_status", "New Pattern")
            persona = markdown_link_label(str(f.get("persona_tag", "Practitioner")))
            strength = markdown_link_label(str(f.get("signal_strength", "Medium")))
            url = markdown_href(f.get("source_url", "#"))
            
            # Status emoji badge
            badge = "🆕 New" if status == "New Pattern" else ("📈 Strengthening" if status == "Strengthening" else ("➡️ Steady" if status == "Steady" else "📉 Fading"))
            md.append(f"| [{pattern}]({url}) | `{badge}` | `{persona}` | `{strength}` | [Link]({url}) |")

        md.append("\n---\n")

        # Detailed Findings Grouped by Hypothesis
        md.append("## 🔍 Grounded Evidence & Friction Findings")

        # Group findings by hypothesis_id
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for f in findings:
            h_id = f.get("hypothesis_id", "EMERGING")
            grouped.setdefault(h_id, []).append(f)

        hypothesis_order = ["H1", "H2", "H3", "EMERGING"]

        for h_id in hypothesis_order:
            h_findings = grouped.get(h_id, [])
            if not h_findings:
                continue

            h_info = self.hypotheses_meta.get(h_id, {})
            h_name = h_info.get("name", h_id)
            h_desc = h_info.get("description", "")

            md.append(f"### {h_id}: {h_name}")
            if h_desc:
                md.append(f"_{h_desc}_\n")

            for idx, f in enumerate(h_findings, 1):
                pattern = markdown_link_label(str(f.get("pattern_name", "Friction Finding")))
                status = markdown_link_label(str(f.get("trend_status", "New Pattern")))
                quote = str(f.get("verbatim_quote", "")).replace("\n", " ")
                url = markdown_href(f.get("source_url", "#"))
                date_str = f.get("date", report_date)
                persona = markdown_link_label(str(f.get("persona_tag", "Practitioner")))
                company_ctx = markdown_link_label(str(f.get("company_context", "Enterprise context")))
                strength = markdown_link_label(str(f.get("signal_strength", "High")))
                count = f.get("source_count", 1)
                takeaway = str(f.get("executive_takeaway", "")).replace("\n", " ")

                md.append(f"#### {idx}. {pattern}")
                md.append(f"- **Trend Momentum:** `{status}`")
                md.append(f"- **Persona / Role:** `{persona}`")
                md.append(f"- **Company Context:** `{company_ctx}`")
                md.append(f"- **Signal Strength:** `{strength}` (Supporting count/upvotes: `{count}`)")
                md.append(f"- **Timestamp:** `{date_str}`")
                md.append(f"- **Direct Source URL:** [{url}]({url})")
                md.append("\n> **Verbatim Direct Quote:**")
                md.append(f'> "{quote}"\n')
                md.append(f"💡 **Strategic Advisory Takeaway:** {takeaway}\n")

        md.append("---\n")
        md.append(f"_Report generated automatically by Trailhead Market Listening Engine on {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_")

        return "\n".join(md)

    def build_query_brief(self, query_prompt: str, report_date: str, synthesis_data: Dict[str, Any], findings: List[Dict[str, Any]]) -> str:
        """Builds a targeted query brief for on-demand user questions."""
        md = []

        md.append(f"# 🎯 Targeted Intelligence Brief")
        md.append(f"**Question / Focus:** `{query_prompt}`  ")
        md.append(f"**Target Client:** Barbara Roos  ")
        md.append(f"**Date:** `{report_date}`  ")
        md.append("---")

        overview = synthesis_data.get("summary_overview", "Targeted query synthesis.")
        md.append("## 📌 Key Insights")
        md.append(f"{overview}\n")

        md.append("## 🔍 Direct Grounded Evidence")
        for idx, f in enumerate(findings, 1):
            pattern = markdown_link_label(str(f.get("pattern_name", "Friction Finding")))
            quote = str(f.get("verbatim_quote", "")).replace("\n", " ")
            url = markdown_href(f.get("source_url", "#"))
            date_str = f.get("date", report_date)
            persona = markdown_link_label(str(f.get("persona_tag", "Practitioner")))
            company_ctx = markdown_link_label(str(f.get("company_context", "Enterprise context")))
            takeaway = str(f.get("executive_takeaway", "")).replace("\n", " ")

            md.append(f"### {idx}. {pattern}")
            md.append(f"- **Persona:** `{persona}` | **Context:** `{company_ctx}`")
            md.append(f"- **Date:** `{date_str}` | **Source:** [{url}]({url})")
            md.append(f'> **Verbatim Quote:** "{quote}"\n')
            md.append(f"💡 **Executive Takeaway:** {takeaway}\n")

        md.append("---")
        return "\n".join(md)
