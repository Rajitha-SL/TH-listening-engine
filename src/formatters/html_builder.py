"""
HTML Report Builder for Trailhead Market Listening Engine.
Generates executive-ready, interactive HTML intelligence digests & briefs with clickable evidence links.
"""

import os
import html
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.net_safety import sanitize_public_https_url


class HTMLBuilder:
    """Builds responsive, executive-ready HTML reports with grounded evidence cards."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client_name = "Barbara Roos (Executive AI Adoption Advisor)"

    def build_weekly_html(
        self,
        report_date: str,
        synthesis_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
        limit: Optional[int] = None
    ) -> str:
        """Generates formatted HTML string for Weekly Intelligence Digest."""
        title = "🛰️ Trailhead Market Listening Engine - Weekly Digest"
        subtitle = f"Automated Weekly Market Ingestion & Synthesis | Date: {report_date}"
        return self._render_html(title, subtitle, report_date, synthesis_data, findings, is_query=False, limit=limit)

    def build_query_html(
        self,
        query_prompt: str,
        report_date: str,
        synthesis_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
        limit: Optional[int] = None
    ) -> str:
        """Generates formatted HTML string for On-Demand Targeted Query Brief."""
        title = "🎯 Targeted Market Intelligence Brief"
        subtitle = f"Prompt: &ldquo;{html.escape(query_prompt)}&rdquo; | Date: {report_date}"
        return self._render_html(title, subtitle, report_date, synthesis_data, findings, is_query=True, prompt=query_prompt, limit=limit)

    def _render_html(
        self,
        title: str,
        subtitle: str,
        report_date: str,
        synthesis_data: Dict[str, Any],
        findings: List[Dict[str, Any]],
        is_query: bool = False,
        prompt: Optional[str] = None,
        limit: Optional[int] = None
    ) -> str:
        exec_summary = synthesis_data.get("summary_overview") or synthesis_data.get("executive_summary") or "Market intelligence synthesis complete."
        
        # Display all findings up to limit (if specified)
        evidence_items = findings[:limit] if limit else findings

        # Status badge color helper
        def status_badge(status: str, delta_pct: float = 0.0) -> str:
            st = (status or "").lower()
            pct_str = f" (+{delta_pct}%)" if delta_pct > 0 else (f" ({delta_pct}%)" if delta_pct < 0 else "")
            if "strengthen" in st:
                return f'<span class="badge badge-strengthening">▲ Strengthening{pct_str}</span>'
            elif "fade" in st:
                return f'<span class="badge badge-fading">▼ Fading{pct_str}</span>'
            elif "steady" in st:
                return f'<span class="badge badge-steady">● Steady</span>'
            elif "new" in st:
                return f'<span class="badge badge-new">✨ New Pattern</span>'
            return f'<span class="badge badge-default">{html.escape(status or "Active")}</span>'

        # Signal strength badge
        def signal_badge(strength: str) -> str:
            s = (strength or "High").lower()
            if "high" in s:
                return '<span class="badge badge-high">High Signal</span>'
            elif "medium" in s:
                return '<span class="badge badge-medium">Medium Signal</span>'
            return f'<span class="badge badge-low">{html.escape(strength or "Normal")}</span>'

        ENTERPRISE_WHITELIST = [
            "sysadmin", "ExperiencedDevs", "ITManagers", "MachineLearning",
            "artificial", "LocalLLaMA", "ChatGPTCoding", "consulting",
            "salesforce", "managers", "humanresources", "cybersecurity"
        ]

        import re

        def _clean_html_text(text: str) -> str:
            """Strips raw HTML markup (e.g. <table>, <tr>, <td>, <div>, <img>, <a>, <!-- SC_OFF -->) and unescapes entities."""
            if not text or not isinstance(text, str):
                return ""
            text = html.unescape(text)
            clean = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)
            clean = re.sub(r'<[^>]+>', ' ', clean)
            clean = re.sub(r'\s+', ' ', clean).strip()
            return clean

        def _sanitize_url(raw_url: Optional[str]) -> str:
            return sanitize_public_https_url(raw_url)

        # Build Findings HTML Cards
        findings_html = ""
        for i, item in enumerate(evidence_items, 1):
            pattern_name = html.escape(_clean_html_text(str(item.get("pattern_name", f"Finding #{i}"))))
            hypothesis_id = html.escape(_clean_html_text(str(item.get("hypothesis_id", "H1"))))
            verbatim_quote = html.escape(_clean_html_text(str(item.get("verbatim_quote", ""))))
            persona_tag = html.escape(_clean_html_text(str(item.get("persona_tag", "Practitioner"))))
            company_context = html.escape(_clean_html_text(str(item.get("company_context", "Enterprise"))))
            source_url = item.get("source_url") or item.get("permalink") or "#"
            sanitized_source_url = _sanitize_url(source_url)
            safe_source_url = html.escape(sanitized_source_url)
            trend_status = str(item.get("trend_status", "Active"))
            source_count = item.get("source_count") or item.get("upvotes") or 1
            exec_takeaway = html.escape(_clean_html_text(str(item.get("executive_takeaway", "Monitored practitioner signal."))))

            url_lower = safe_source_url.lower()
            if "reddit.com" in url_lower:
                btn_label = "📄 Open Discussion Post on Reddit &rarr;"
            elif any(jb in url_lower for jb in ["remoteok.com", "weworkremotely.com", "greenhouse.io", "lever.co", "indeed.com"]):
                btn_label = "💼 Open AI Transformation Posting &rarr;"
            else:
                btn_label = "🌐 Open Verified Discussion Mirror &rarr;"

            findings_html += f"""
            <div class="card finding-card" id="finding-{i}">
                <div class="finding-header">
                    <div class="finding-title-group">
                        <span class="hypo-id">{hypothesis_id}</span>
                        <h3 class="finding-title">{pattern_name}</h3>
                    </div>
                    <div class="badge-group">
                        {status_badge(trend_status, float(item.get("delta_pct") or 0.0))}
                        {signal_badge(str(item.get("signal_strength", "High")))}
                    </div>
                </div>

                <div class="persona-row">
                    <span class="persona-badge">👤 {persona_tag}</span>
                    <span class="context-badge">🏢 {company_context}</span>
                    <span class="volume-badge">📊 {source_count} Signal Count</span>
                </div>

                <div class="quote-box">
                    <div class="quote-label">💬 Grounded Verbatim Quote:</div>
                    <blockquote class="verbatim-quote">&ldquo;{verbatim_quote}&rdquo;</blockquote>
                </div>

                <div class="takeaway-box">
                    <strong>💡 Executive Advisory Takeaway:</strong> {exec_takeaway}
                </div>

                <div class="source-link-row">
                    <a href="{safe_source_url}" target="_blank" rel="noopener noreferrer" class="source-btn">
                        {btn_label}
                    </a>
                </div>
            </div>"""

        # Build Momentum Table Rows
        table_rows = ""
        for item in findings:
            p_name = html.escape(str(item.get("pattern_name", "Pattern")))
            h_id = html.escape(str(item.get("hypothesis_id", "H1")))
            p_tag = html.escape(str(item.get("persona_tag", "Practitioner")))
            s_url = item.get("source_url") or item.get("permalink") or "#"
            sanitized_s_url = _sanitize_url(s_url)
            safe_url = html.escape(sanitized_s_url)
            t_status = str(item.get("trend_status", "Active"))
            table_rows += f"""
            <tr>
                <td><strong>[{h_id}]</strong> {p_name}</td>
                <td>{status_badge(t_status)}</td>
                <td><span class="persona-pill">{p_tag}</span></td>
                <td><a href="{safe_url}" target="_blank" rel="noopener noreferrer" class="table-link">View Source &rarr;</a></td>
            </tr>
            """

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src data:; base-uri 'none'; form-action 'none';">
    <title>{html.escape(title)}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: #111827;
            --card-border: #1f2937;
            --accent-blue: #3b82f6;
            --accent-hover: #2563eb;
            --text-main: #f9fafb;
            --text-muted: #9ca3af;
            --quote-bg: #1e293b;
            --quote-border: #3b82f6;
            --success-bg: #064e3b;
            --success-text: #34d399;
            --warning-bg: #78350f;
            --warning-text: #fbbf24;
            --info-bg: #1e3a8a;
            --info-text: #93c5fd;
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
            padding: 30px 20px;
        }}

        .container {{
            max-width: 1050px;
            margin: 0 auto;
        }}

        header {{
            background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%);
            border: 1px solid #312e81;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
        }}

        .header-title {{
            font-size: 26px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 8px;
        }}

        .header-subtitle {{
            font-size: 14px;
            color: var(--text-muted);
            margin-bottom: 15px;
        }}

        .meta-bar {{
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            font-size: 13px;
            padding-top: 15px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .meta-item {{
            background: rgba(255, 255, 255, 0.05);
            padding: 4px 12px;
            border-radius: 20px;
        }}

        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }}

        .section-heading {{
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-bottom: 15px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .exec-summary-text {{
            font-size: 15px;
            color: #e2e8f0;
            line-height: 1.7;
        }}

        /* Findings Cards */
        .finding-card {{
            border-left: 4px solid var(--accent-blue);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}

        .finding-card:hover {{
            border-color: #60a5fa;
            transform: translateY(-2px);
        }}

        .finding-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 15px;
            margin-bottom: 12px;
        }}

        .finding-title-group {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .hypo-id {{
            background: #312e81;
            color: #a5b4fc;
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        }}

        .finding-title {{
            font-size: 17px;
            font-weight: 600;
            color: #ffffff;
        }}

        .badge-group {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}

        .badge {{
            font-size: 12px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 20px;
            display: inline-block;
        }}

        .badge-strengthening {{ background: var(--success-bg); color: var(--success-text); }}
        .badge-new {{ background: var(--info-bg); color: var(--info-text); }}
        .badge-fading {{ background: var(--warning-bg); color: var(--warning-text); }}
        .badge-high {{ background: #831843; color: #fbcfe8; }}
        .badge-medium {{ background: #374151; color: #d1d5db; }}
        .badge-default {{ background: #374151; color: #d1d5db; }}

        .persona-row {{
            display: flex;
            gap: 15px;
            font-size: 13px;
            color: var(--text-muted);
            margin-bottom: 15px;
            flex-wrap: wrap;
        }}

        .quote-box {{
            background-color: var(--quote-bg);
            border-left: 3px solid var(--quote-border);
            padding: 14px 18px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 15px;
        }}

        .quote-label {{
            font-size: 12px;
            font-weight: 600;
            color: #93c5fd;
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .verbatim-quote {{
            font-size: 14px;
            font-style: italic;
            color: #f1f5f9;
        }}

        .takeaway-box {{
            background: rgba(30, 41, 59, 0.5);
            border: 1px dashed #334155;
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 13.5px;
            color: #cbd5e1;
            margin-bottom: 15px;
        }}

        .source-link-row {{
            margin-top: 10px;
        }}

        .source-btn {{
            display: inline-flex;
            align-items: center;
            background-color: #1e293b;
            color: #60a5fa;
            border: 1px solid #334155;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 500;
            transition: all 0.2s ease;
        }}

        .source-btn:hover {{
            background-color: var(--accent-blue);
            color: #ffffff;
            border-color: var(--accent-blue);
        }}

        /* Table */
        .table-container {{
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            text-align: left;
        }}

        th, td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--card-border);
        }}

        th {{
            background-color: #1e293b;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.5px;
        }}

        tr:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}

        .persona-pill {{
            background: #1f2937;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            color: #cbd5e1;
        }}

        .table-link {{
            color: #60a5fa;
            text-decoration: none;
        }}

        .table-link:hover {{ text-decoration: underline; }}

        footer {{
            text-align: center;
            font-size: 12px;
            color: var(--text-muted);
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid var(--card-border);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1 class="header-title">{html.escape(title)}</h1>
            <p class="header-subtitle">{subtitle}</p>
            <div class="meta-bar">
                <span class="meta-item">👤 <strong>Client:</strong> {html.escape(self.client_name)}</span>
                <span class="meta-item">📅 <strong>Report Date:</strong> {html.escape(report_date)}</span>
                <span class="meta-item">🔒 <strong>Evidence Policy:</strong> 100% Verbatim Grounded Quotes</span>
            </div>
        </header>

        <div class="card">
            <h2 class="section-heading">📌 Executive Summary Overview</h2>
            <p class="exec-summary-text">{html.escape(exec_summary)}</p>
        </div>

        <div class="card">
            <h2 class="section-heading">📊 Trend Momentum Snapshot</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Hypothesis / Pattern</th>
                            <th>Trend Momentum</th>
                            <th>Persona Tag</th>
                            <th>Verified Source Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows if table_rows else '<tr><td colspan="4">No findings recorded.</td></tr>'}
                    </tbody>
                </table>
            </div>
        </div>

        <h2 class="section-heading" style="margin-top: 30px; margin-bottom: 20px;">
            🔗 Grounded Evidence Cards (Top {len(evidence_items)} Findings with Direct Links)
        </h2>

        {findings_html if findings_html else '<div class="card"><p>No evidence findings collected.</p></div>'}

        <footer>
            <p>Generated by <strong>Trailhead Market Listening Engine v1.0</strong> | Trailhead Communications Advisory</p>
        </footer>
    </div>
</body>
</html>
"""
