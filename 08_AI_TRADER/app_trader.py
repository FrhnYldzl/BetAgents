"""
AI TRADER — iddaa.com Paper Trading Terminal
=============================================
Dark professional trading terminal UI for sports betting paper trading.

Run:
  python -m streamlit run app_trader.py --server.port 8504
"""
from __future__ import annotations

import re
import sys
import math
import uuid
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ── Paths ──────────────────────────────────────────────────────
THIS_DIR = Path(__file__).resolve().parent
YAZILIM  = THIS_DIR.parent
DB_PATH  = YAZILIM / "02_VERI" / "bahis_agent.db"
sys.path.insert(0, str(YAZILIM / "02_VERI"))

PORTFOLIO_ID = "PAPER_V1"
INITIAL_BANKROLL = 5_000.0
IDDAA_URL = "https://www.iddaa.com/program/futbol-mac-onceski"


def db_connect():
    """Taşınabilir bağlantı (SQLite yerel / PostgreSQL Railway) — db.py'ye delege."""
    import db as _dbcore
    return _dbcore.connect(DB_PATH)


# ── Page config ────────────────────────────────────────────────
# try/except: app.py (birleşik giriş) zaten ayarladıysa hata vermesin
try:
    st.set_page_config(
        page_title="AI TRADER · iddaa paper",
        page_icon="◉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# ── CSS ────────────────────────────────────────────────────────
# Modül sabiti olarak tut (app_unified her rerun'da yeniden enjekte edebilsin)
TRADER_CSS = """
<style>
/* ── Base ── */
.stApp {
    background: #0a0d14;
    color: #e2e8f0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter',
                 'Helvetica Neue', Arial, sans-serif;
}

/* ── Hide Streamlit chrome ── */
[data-testid="stToolbar"]  { display: none; }
[data-testid="stHeader"]   { background: transparent; height: 0; }
footer                     { visibility: hidden; }
#MainMenu                  { visibility: hidden; }
[data-testid="stSidebar"] > div:first-child > div:first-child { display: none; }

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #070b12 !important;
    border-right: 1px solid #1e293b;
    min-width: 200px !important;
    max-width: 220px !important;
}
[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    border: 1px solid #1e293b;
    color: #94a3b8;
    font-size: 12px;
    padding: 8px 14px;
    width: 100%;
    text-align: left;
    border-radius: 6px;
    font-family: -apple-system, sans-serif;
    transition: all 0.15s;
    margin-bottom: 2px;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(16,212,142,0.08);
    border-color: #10d48e;
    color: #10d48e;
}

/* ── Top status bar ── */
.status-bar {
    background: linear-gradient(90deg, #060a12 0%, #0d1526 100%);
    border-bottom: 1px solid #1e293b;
    padding: 10px 20px;
    margin: -50px -16px 20px -16px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 11px;
}
.sb-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}
.chip-green {
    background: rgba(16,212,142,0.10);
    border: 1px solid #10d48e;
    color: #10d48e;
}
.chip-orange {
    background: rgba(245,158,11,0.10);
    border: 1px solid #f59e0b;
    color: #f59e0b;
}
.chip-blue {
    background: rgba(59,130,246,0.10);
    border: 1px solid #3b82f6;
    color: #3b82f6;
}
.chip-gray {
    background: rgba(100,116,139,0.10);
    border: 1px solid #334155;
    color: #64748b;
}
.sb-label {
    color: #64748b;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.sb-value {
    color: #e2e8f0;
    font-weight: 700;
    font-size: 12px;
    margin-left: 4px;
    font-family: Consolas, 'Courier New', monospace;
}
.sb-spacer { flex: 1; }
.sb-btn {
    padding: 5px 12px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    cursor: pointer;
    font-family: Consolas, monospace;
    text-decoration: none;
}
.btn-dry  { background: #1e293b; border: 1px solid #334155; color: #94a3b8; }
.btn-live { background: rgba(16,212,142,0.15); border: 1px solid #10d48e; color: #10d48e; }

/* ── KPI Cards ── */
.kpi-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.kpi-card {
    flex: 1;
    min-width: 160px;
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 20px 22px;
}
.kpi-label {
    font-size: 10px;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 8px;
}
.kpi-value {
    font-size: 26px;
    font-weight: 700;
    color: #e2e8f0;
    font-family: Consolas, 'Courier New', monospace;
    line-height: 1.1;
}
.kpi-delta {
    font-size: 11px;
    font-weight: 600;
    font-family: Consolas, 'Courier New', monospace;
    margin-top: 6px;
}
.kpi-delta.pos { color: #10d48e; }
.kpi-delta.neg { color: #ef4444; }
.kpi-delta.muted { color: #64748b; }

/* ── Section title ── */
.sec-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 0 12px 0;
    border-bottom: 1px solid #1e293b;
    margin-bottom: 18px;
}
.sec-title-main {
    color: #10d48e;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-family: Consolas, 'Courier New', monospace;
}
.sec-title-meta {
    font-size: 11px;
    color: #64748b;
    font-family: Consolas, 'Courier New', monospace;
}

/* ── Coupon / Position Cards ── */
.pos-card {
    background: #0d1628;
    border: 1px solid #1a2840;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 14px;
}
.pos-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.pos-type {
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-family: Consolas, monospace;
}
.pos-meta { color: #64748b; font-size: 11px; font-family: Consolas, monospace; }
.pos-reasoning {
    color: #94a3b8;
    font-size: 12px;
    line-height: 1.5;
    margin: 6px 0 10px 0;
}
.bet-row {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    background: rgba(10,13,20,0.6);
    border-radius: 4px;
    margin-bottom: 4px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 11px;
    flex-wrap: wrap;
}
.bet-match { color: #e2e8f0; font-weight: 600; flex: 1; min-width: 120px; }
.bet-market { color: #64748b; }
.bet-pick { color: #f59e0b; font-weight: 700; }
.bet-odds { color: #e2e8f0; }
.bet-prob { color: #94a3b8; }
.signal-bar-wrap { width: 60px; height: 4px; background: #1e293b; border-radius: 2px; }
.signal-bar { height: 4px; background: #10d48e; border-radius: 2px; }

/* ── Match signal cards ── */
.match-card {
    background: #0d1628;
    border: 1px solid #1a2840;
    border-left: 4px solid #1e293b;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.match-card.tier-strong { border-left-color: #10d48e; }
.match-card.tier-orta   { border-left-color: #f59e0b; }
.match-card.tier-zayif  { border-left-color: #3b82f6; }
.match-title  { font-size: 14px; font-weight: 600; color: #e2e8f0; }
.match-sub    { font-size: 11px; color: #64748b; font-family: Consolas, monospace;
                text-transform: uppercase; letter-spacing: 0.04em; margin-top: 3px; }
.stat-row { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 8px; }
.stat-item { font-family: Consolas, monospace; min-width: 60px; }
.stat-lbl  { font-size: 9px; color: #64748b; text-transform: uppercase;
             letter-spacing: 0.08em; display: block; margin-bottom: 2px; }
.stat-val  { font-size: 15px; font-weight: 700; color: #e2e8f0; }
.stat-val.grn { color: #10d48e; }
.stat-val.org { color: #f59e0b; }
.stat-val.red { color: #ef4444; }
.stat-val.dim { color: #64748b; }

/* ── Journal entries ── */
.journal-entry {
    background: #0b1120;
    border-left: 3px solid #1e293b;
    border-radius: 4px;
    padding: 10px 14px;
    margin-bottom: 8px;
}

/* ── Dataframes ── */
[data-testid="stDataFrame"] {
    background: #111827;
    border-radius: 6px;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 12px;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #070b12; }
::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #334155; }

/* ── Streamlit metrics override ── */
[data-testid="stMetric"] {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] {
    font-family: Consolas, 'Courier New', monospace !important;
    font-size: 22px !important;
    font-weight: 700;
    color: #e2e8f0;
}
[data-testid="stMetricLabel"] {
    font-size: 10px !important;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.1em;
}
</style>
"""
st.markdown(TRADER_CSS, unsafe_allow_html=True)


# ============================================================
# DATA HELPERS
# ============================================================

def _db_rows(sql: str, params: tuple = ()) -> list[dict]:
    conn = db_connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


# ── SVG Position Chart (Meridian-style) ──────────────────────────────────────

def _svg_position_chart(stake: float, potential: float, color: str, uid: str = "") -> str:
    """Meridian-style mini position chart: stake TL (entry) → potential return TL (target).
    Bezier S-curve with gradient fill, exactly like Meridian Capital equity sparklines."""
    W, H  = 170, 68
    ml, mr, mt, mb = 8, 8, 10, 22  # margins
    x0, y0 = float(ml),     float(H - mb)   # entry: bottom-left
    x1, y1 = float(W - mr), float(mt)       # target: top-right
    cw     = x1 - x0

    # Bezier control points: flat start, steep climb at 60%
    bx1, by1 = x0 + cw * 0.42, y0
    bx2, by2 = x0 + cw * 0.58, y1

    path  = f"M{x0:.0f},{y0:.0f} C{bx1:.1f},{by1:.1f} {bx2:.1f},{by2:.1f} {x1:.0f},{y1:.0f}"
    area  = f"{path} L{x1:.0f},{y0:.0f} Z"
    roi   = (potential - stake) / stake * 100 if stake > 0 else 0
    gid   = f"pcg{uid[:8].replace('-', '')}"
    mid_y = (y0 + y1) / 2

    return (
        f'<svg width="{W}" height="{H}">'
        f'<defs>'
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%"   stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient>'
        f'</defs>'
        # baseline
        f'<line x1="{ml}" y1="{y0:.0f}" x2="{W-mr}" y2="{y0:.0f}" '
        f'stroke="#1e293b" stroke-width="1"/>'
        # mid-grid (dotted)
        f'<line x1="{ml}" y1="{mid_y:.0f}" x2="{W-mr}" y2="{mid_y:.0f}" '
        f'stroke="#1a2840" stroke-width="0.5" stroke-dasharray="3,5"/>'
        # top-grid (target level, dotted)
        f'<line x1="{ml}" y1="{mt}" x2="{W-mr}" y2="{mt}" '
        f'stroke="#1a2840" stroke-width="0.5" stroke-dasharray="3,5"/>'
        # gradient fill under curve
        f'<path d="{area}" fill="url(#{gid})"/>'
        # the main curve
        f'<path d="{path}" stroke="{color}" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        # vertical dashed drop from target dot to baseline
        f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x1:.0f}" y2="{y0:.0f}" '
        f'stroke="{color}" stroke-width="0.8" stroke-dasharray="2,3" opacity="0.35"/>'
        # entry dot (semi-transparent)
        f'<circle cx="{x0:.0f}" cy="{y0:.0f}" r="3.5" fill="{color}" opacity="0.55"/>'
        # target dot (bright, solid)
        f'<circle cx="{x1:.0f}" cy="{y1:.0f}" r="4.5" fill="{color}"/>'
        # ── labels ──
        # entry label bottom-left
        f'<text x="{ml}" y="{H-4}" font-size="9" font-family="Consolas,monospace" '
        f'fill="#475569">GİRİŞ {stake:.0f} TL</text>'
        # target label top-right
        f'<text x="{W-mr}" y="{mt-2}" text-anchor="end" font-size="10" '
        f'font-family="Consolas,monospace" fill="{color}" font-weight="700">'
        f'HEDEF {potential:.0f} TL</text>'
        # ROI in the middle of the chart
        f'<text x="{(x0+x1)/2:.0f}" y="{mid_y-6:.0f}" text-anchor="middle" '
        f'font-size="11" font-family="Consolas,monospace" fill="{color}" font-weight="700">'
        f'+{roi:.0f}%</text>'
        f'</svg>'
    )


def _svg_settlement_chart(stake: float, pnl: float, uid: str = "") -> str:
    """Settlement chart for Journal RESULT entries.
    Won (pnl >= 0): green curve reaches target dot + ✓ marker.
    Lost (pnl < 0): red curve falls from stake to baseline + ✗ marker."""
    W, H  = 170, 68
    ml, mr, mt, mb = 8, 8, 10, 22
    x0, y0 = float(ml), float(H - mb)    # entry point
    x1     = float(W - mr)
    cw     = x1 - x0
    gid    = f"scg{uid[:8].replace('-', '')}"

    if pnl >= 0:
        # ── WON: upward bezier (green), same shape as open chart ──
        color  = "#10d48e"
        y1     = float(mt)
        bx1, by1 = x0 + cw * 0.42, y0
        bx2, by2 = x0 + cw * 0.58, y1
        path   = f"M{x0:.0f},{y0:.0f} C{bx1:.1f},{by1:.1f} {bx2:.1f},{by2:.1f} {x1:.0f},{y1:.0f}"
        area   = f"{path} L{x1:.0f},{y0:.0f} Z"
        symbol = "✓"
        result = f"+{pnl:.0f} TL"
        result_y = mt - 2
        end_dot_y = y1
    else:
        # ── LOST: downward bezier (red), falls from stake level to baseline ──
        color  = "#ef4444"
        y1     = float(H - mb)           # ends at baseline (0 = full loss)
        bx1, by1 = x0 + cw * 0.28, y0   # flat-ish start
        bx2, by2 = x0 + cw * 0.72, y1   # steep drop
        path   = f"M{x0:.0f},{y0:.0f} C{bx1:.1f},{by1:.1f} {bx2:.1f},{by2:.1f} {x1:.0f},{y1:.0f}"
        # fill area between the falling curve and the baseline
        mid_x  = (x0 + x1) / 2
        area   = f"M{x0:.0f},{y0:.0f} C{bx1:.1f},{by1:.1f} {bx2:.1f},{by2:.1f} {x1:.0f},{y1:.0f} Z"
        symbol = "✗"
        result = f"{pnl:.0f} TL"
        result_y = mt + 12   # position below top since line falls down
        end_dot_y = y1

    mid_y = (y0 + float(mt)) / 2

    return (
        f'<svg width="{W}" height="{H}">'
        f'<defs>'
        f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%"   stop-color="{color}" stop-opacity="0.22"/>'
        f'<stop offset="100%" stop-color="{color}" stop-opacity="0.02"/>'
        f'</linearGradient>'
        f'</defs>'
        # baseline
        f'<line x1="{ml}" y1="{H-mb}" x2="{W-mr}" y2="{H-mb}" stroke="#1e293b" stroke-width="1"/>'
        # mid grid
        f'<line x1="{ml}" y1="{mid_y:.0f}" x2="{W-mr}" y2="{mid_y:.0f}" '
        f'stroke="#1a2840" stroke-width="0.5" stroke-dasharray="3,5"/>'
        # fill
        f'<path d="{area}" fill="url(#{gid})"/>'
        # curve
        f'<path d="{path}" stroke="{color}" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
        # entry dot
        f'<circle cx="{x0:.0f}" cy="{y0:.0f}" r="3.5" fill="{color}" opacity="0.55"/>'
        # end dot (large, solid, bright)
        f'<circle cx="{x1:.0f}" cy="{end_dot_y:.0f}" r="5" fill="{color}"/>'
        # outcome symbol on end dot
        f'<text x="{x1:.0f}" y="{end_dot_y:.0f}" text-anchor="middle" dominant-baseline="middle" '
        f'font-size="8" font-weight="900" fill="#0a0d14">{symbol}</text>'
        # result label (top-right for won, mid-right for lost)
        f'<text x="{W-mr}" y="{result_y}" text-anchor="end" font-size="11" '
        f'font-family="Consolas,monospace" fill="{color}" font-weight="700">{result}</text>'
        # entry label
        f'<text x="{ml}" y="{H-4}" font-size="9" font-family="Consolas,monospace" '
        f'fill="#475569">STAKE {stake:.0f} TL</text>'
        f'</svg>'
    )


@st.cache_data(ttl=60)
def load_portfolio() -> dict:
    conn = db_connect()
    try:
        row = conn.execute(
            "SELECT * FROM paper_portfolio WHERE portfolio_id=?",
            (PORTFOLIO_ID,),
        ).fetchone()
        if row is None:
            return {}
        p = dict(row)
        staked = p.get("total_staked") or 0.0
        total_return = p.get("total_return") or 0.0
        pnl = total_return - staked
        yield_pct = (pnl / staked * 100) if staked > 0 else 0.0
        total_coupons = p.get("total_coupons") or 0
        won_coupons = p.get("won_coupons") or 0
        total_bets = p.get("total_bets") or 0
        total_wins = p.get("total_wins") or 0
        open_c = conn.execute(
            "SELECT COUNT(*) FROM paper_coupons WHERE portfolio_id=? AND status='open'",
            (PORTFOLIO_ID,),
        ).fetchone()[0]
        staked_open = conn.execute(
            "SELECT COALESCE(SUM(stake),0) FROM paper_coupons WHERE portfolio_id=? AND status='open'",
            (PORTFOLIO_ID,),
        ).fetchone()[0]
        p["pnl"] = round(pnl, 2)
        p["yield_pct"] = round(yield_pct, 2)
        p["coupon_win_rate"] = round(won_coupons / total_coupons * 100, 1) if total_coupons else 0.0
        p["bet_win_rate"] = round(total_wins / total_bets * 100, 1) if total_bets else 0.0
        p["open_coupons"] = open_c
        p["staked_open"] = round(staked_open, 2)
        p["buying_power"] = round((p.get("current_bankroll") or 0) - staked_open, 2)
        return p
    finally:
        conn.close()


def _regime_chip(bankroll: float) -> str:
    change_pct = (bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL * 100
    if change_pct >= -5:
        return '<span class="sb-chip chip-green">● REGIME: STRONG</span>'
    else:
        return '<span class="sb-chip chip-orange">● OFF-SEASON</span>'


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("""
        <div style="padding: 18px 14px 10px 14px;">
          <div style="color:#10d48e; font-size:20px; font-weight:900;
                      letter-spacing:0.06em; font-family:Consolas,monospace;">
            ◉ AI TRADER
          </div>
          <div style="color:#475569; font-size:11px; margin-top:2px;
                      font-family:Consolas,monospace; letter-spacing:0.04em;">
            iddaa · paper
          </div>
        </div>
        <div style="border-bottom:1px solid #1e293b; margin:0 0 12px 0;"></div>
        """, unsafe_allow_html=True)

        st.markdown('<div style="color:#64748b;font-size:9px;text-transform:uppercase;'
                    'letter-spacing:0.1em;padding:4px 14px 6px 14px;">TRADING</div>',
                    unsafe_allow_html=True)

        nav_items = [
            ("TRADING", ["Overview", "Matches", "Charts"]),
            ("PORTFOLIO", ["Positions", "Orders", "Risk"]),
            ("ACCOUNT", ["Journal", "Settings"]),
        ]

        page = st.session_state.get("page", "Overview")

        for group, items in nav_items:
            st.markdown(
                f'<div style="color:#475569;font-size:9px;text-transform:uppercase;'
                f'letter-spacing:0.1em;padding:10px 14px 4px 14px;">{group}</div>',
                unsafe_allow_html=True,
            )
            for item in items:
                if st.button(
                    item,
                    key=f"nav_{item}",
                    use_container_width=True,
                ):
                    st.session_state["page"] = item
                    st.rerun()

        st.markdown('<div style="border-top:1px solid #1e293b;margin:16px 0 10px 0;"></div>',
                    unsafe_allow_html=True)
        import db as _dbcore_sb
        _sb_db_label = "PostgreSQL" if _dbcore_sb.is_postgres() else DB_PATH.stem
        st.markdown(
            f'<div style="color:#64748b;font-size:10px;font-family:Consolas,monospace;'
            f'padding:0 14px;">DB: {_sb_db_label}</div>',
            unsafe_allow_html=True,
        )

    return st.session_state.get("page", "Overview")


# ============================================================
# STATUS BAR
# ============================================================

def render_status_bar(portfolio: dict) -> None:
    bankroll = portfolio.get("current_bankroll") or INITIAL_BANKROLL
    pnl = portfolio.get("pnl") or 0.0
    open_c = portfolio.get("open_coupons") or 0
    regime = _regime_chip(bankroll)
    now = datetime.now().strftime("%H:%M")

    st.markdown(f"""
    <div class="status-bar">
      {regime}
      <span class="sb-label">BANKROLL:<span class="sb-value">{bankroll:,.0f} TL</span></span>
      <span class="sb-label">SCAN:<span class="sb-value" style="color:#10d48e;">live</span></span>
      <span class="sb-label">OPEN:<span class="sb-value">{open_c}</span></span>
      <span class="sb-label">P&L:<span class="sb-value"
        style="color:{'#10d48e' if pnl >= 0 else '#ef4444'};">{pnl:+,.0f} TL</span></span>
      <span class="sb-spacer"></span>
      <span class="sb-chip chip-gray">PAPER_V1 ▾</span>
      <span class="sb-btn btn-dry">DRY-RUN</span>
      <span class="sb-btn btn-live">PAPER</span>
      <span style="color:#475569;font-size:11px;font-family:Consolas,monospace;
                   cursor:pointer;">↻ {now}</span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# TODAY'S PICKS PREVIEW  (shared by Overview & Matches)
# ============================================================

def _calc_signals_for_matches(matches: list) -> list:
    """Return enriched picks list sorted by CMC tier + probability."""
    def calc_probs(odds_list):
        raw = [1.0 / o if o else 0.0 for o in odds_list]
        total = sum(raw)
        if total <= 0:
            return [0.0] * len(odds_list)
        return [r / total for r in raw]

    picks = []
    for m in matches:
        sigs = []
        o1   = m.get("closing_1")
        oX   = m.get("closing_X")
        o2   = m.get("closing_2")
        o_ov = m.get("closing_over25")
        o_un = m.get("closing_under25")
        o_ky = m.get("closing_btts_yes")
        o_kn = m.get("closing_btts_no")

        if o1 and oX and o2:
            p1, pX, p2 = calc_probs([o1, oX, o2])
            if p1 >= 0.65:
                sigs.append(("EV_FAV", p1, o1, "1X2"))
            elif p1 >= 0.58:
                sigs.append(("FAV", p1, o1, "1X2"))
            if p2 >= 0.65:
                sigs.append(("DEP_FAV", p2, o2, "1X2"))
        if o_ky and o_kn:
            pky, _ = calc_probs([o_ky, o_kn])
            if pky >= 0.60:
                sigs.append(("KG_VAR", pky, o_ky, "BTTS"))
        if o_ov and o_un:
            pov, pun = calc_probs([o_ov, o_un])
            if pov >= 0.58:
                sigs.append(("UST_25", pov, o_ov, "OU"))
            if pun >= 0.60:
                sigs.append(("ALT_25", pun, o_un, "OU"))

        if not sigs:
            continue

        has_strong = any(s[0] in ("EV_FAV", "DEP_FAV") for s in sigs)
        has_kg     = any(s[0] == "KG_VAR" for s in sigs)
        has_alt    = any(s[0] == "ALT_25" for s in sigs)
        has_ust    = any(s[0] == "UST_25" for s in sigs)

        if (has_strong and (has_alt or has_kg)) or (has_kg and (has_alt or has_ust)):
            cmc, tier = 3, "GUCLU"
        elif has_strong or has_kg:
            cmc, tier = 2, "ORTA"
        else:
            cmc, tier = 1, "ZAYIF"

        picks.append({"match": m, "signals": sigs, "cmc": cmc, "tier": tier})

    picks.sort(key=lambda x: (x["cmc"], max(s[1] for s in x["signals"])), reverse=True)
    return picks


def _show_today_preview() -> None:
    """Compact today+tomorrow signal summary shown on Overview page."""
    now_utc   = datetime.utcnow()
    today_s   = now_utc.date().isoformat()
    cutoff_s  = (now_utc.date() + timedelta(days=2)).isoformat()

    matches = _db_rows("""
        SELECT match_id, league_code, home_team, away_team, kickoff_utc,
               closing_1, closing_X, closing_2,
               closing_over25, closing_under25,
               closing_btts_yes, closing_btts_no,
               external_id_iddaa
        FROM matches_v2
        WHERE is_settled=0
          AND kickoff_utc >= ? AND kickoff_utc <= ?
        ORDER BY kickoff_utc
    """, (today_s + "T00:00", cutoff_s + "T23:59"))

    picks = _calc_signals_for_matches(matches)
    top   = picks[:5]  # show max 5 on overview

    if not top:
        return

    st.markdown(f"""
    <div class="sec-title" style="margin-top:24px;">
      <div class="sec-title-main">▸ TODAY'S SIGNALS ({len(picks)} mac)</div>
      <div class="sec-title-meta">
        {sum(1 for p in picks if p['tier']=='GUCLU')} GUCLU ·
        {sum(1 for p in picks if p['tier']=='ORTA')} ORTA ·
        {sum(1 for p in picks if p['tier']=='ZAYIF')} ZAYIF
      </div>
    </div>
    """, unsafe_allow_html=True)

    TIER_BG   = {"GUCLU": "rgba(16,212,142,0.08)",  "ORTA": "rgba(245,158,11,0.08)",  "ZAYIF": "rgba(59,130,246,0.08)"}
    TIER_BORD = {"GUCLU": "#10d48e",                 "ORTA": "#f59e0b",                "ZAYIF": "#3b82f6"}
    TIER_TXT  = {"GUCLU": "#10d48e",                 "ORTA": "#f59e0b",                "ZAYIF": "#3b82f6"}

    rows_html = ""
    for p in top:
        m     = p["match"]
        tc    = TIER_TXT[p["tier"]]
        bg    = TIER_BG[p["tier"]]
        bord  = TIER_BORD[p["tier"]]
        stars = "★" * p["cmc"] + "☆" * (3 - p["cmc"])
        ko    = (m.get("kickoff_utc") or "")[:16].replace("T", " ")
        eid   = m.get("external_id_iddaa") or "?"

        sig_parts = []
        for s in p["signals"]:
            clr = "#10d48e" if "FAV" in s[0] else "#f59e0b"
            sig_parts.append(
                f'<span style="color:{clr};font-weight:700;">{s[0]}</span>'
                f'<span style="color:#64748b;"> @{s[2]:.2f}</span>'
                f'<span style="color:#94a3b8;"> %{int(s[1]*100)}</span>'
            )
        sig_html = " &nbsp;·&nbsp; ".join(sig_parts)

        rows_html += (
            f'<div style="background:{bg};border:1px solid {bord};border-left:3px solid {bord};'
            f'border-radius:6px;padding:10px 16px;margin-bottom:8px;'
            f'display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
            f'<div style="min-width:140px;">'
            f'<div style="color:#e2e8f0;font-size:13px;font-weight:600;">'
            f'{m.get("home_team","?")} vs {m.get("away_team","?")}</div>'
            f'<div style="color:#475569;font-size:10px;font-family:Consolas,monospace;margin-top:2px;">'
            f'{m.get("league_code","?")} · {ko} UTC</div>'
            f'</div>'
            f'<div style="flex:1;font-size:11px;font-family:Consolas,monospace;">{sig_html}</div>'
            f'<div style="text-align:right;white-space:nowrap;">'
            f'<span style="color:{tc};font-size:11px;font-weight:700;font-family:Consolas,monospace;">{p["tier"]} {stars}</span>'
            f'<div style="color:#475569;font-size:10px;font-family:Consolas,monospace;">EID:{eid}</div>'
            f'</div>'
            f'</div>'
        )

    if len(picks) > 5:
        rows_html += (
            f'<div style="color:#475569;font-size:11px;font-family:Consolas,monospace;padding:4px 0;">'
            f'... ve {len(picks)-5} mac daha — Matches sayfasina bak</div>'
        )
    st.markdown(rows_html, unsafe_allow_html=True)


# ============================================================
# PAGE: OVERVIEW
# ============================================================

@st.cache_data(ttl=900, show_spinner=False)
def get_ready_coupons(stake: float = 100.0):
    """HAZIR KUPONLAR — oynanmamış maçlardan MBS-uyumlu öneriler (15 dk cache)."""
    try:
        from paper_engine import PaperEngine
        return PaperEngine(PORTFOLIO_ID).recommend_coupons(stake=stake)
    except Exception:
        return []


def render_ready_coupons() -> None:
    """Overview'da 'HAZIR KUPONLAR' bölümü — manuel oynamak için, edge-dürüst."""
    try:
        recs = get_ready_coupons(100.0)
    except Exception:
        recs = []
    st.markdown(
        '<div class="sec-title" style="margin-top:6px;">'
        '<div class="sec-title-main">▸ HAZIR KUPONLAR</div>'
        '<div class="sec-title-meta">OYNANMAMIŞ · MBS-UYUMLU · 100 TL · MANUEL OYNA</div></div>',
        unsafe_allow_html=True)
    if not recs:
        st.markdown('<div style="color:#475569;font-size:12px;padding:6px 0 14px 0;">'
                    'Şu an uygun (başlamamış) maç/sinyal yok — worker yeni program çekince güncellenir.'
                    '</div>', unsafe_allow_html=True)
        return
    TYPE_LABEL = {"TEK_FAVORI": "TEK MAÇ (favori)", "K3_KOMBO": "3'LÜ KOMBO", "K3_VALUE": "3'LÜ VALUE"}
    cols = st.columns(len(recs))
    for col, rc in zip(cols, recs):
        with col:
            edge = rc["avg_edge"]
            ev_ok = edge > 0
            ev_color = "#10d48e" if ev_ok else "#f59e0b"
            ev_txt = (f"+DEĞER %{edge*100:.1f}" if ev_ok else f"−EV %{edge*100:.1f}")
            legs_html = ""
            for L in rc["legs"]:
                ko = (L["kickoff"] or "")[:16].replace("T", " ")
                legs_html += (
                    '<div style="border-top:1px solid #18233a;padding:6px 0;">'
                    f'<div style="color:#e2e8f0;font-size:12px;font-weight:600;">{L["home"]} '
                    f'<span style="color:#475569;">v</span> {L["away"]}</div>'
                    '<div style="font-family:Consolas,monospace;font-size:11px;margin-top:2px;">'
                    f'<span style="color:#10d48e;font-weight:700;">{L["market"]}:{L["pick"]}</span> '
                    f'<span style="color:#94a3b8;">@{L["odds"]:.2f}</span> '
                    f'<span style="color:#64748b;">· %{L["model_prob"]*100:.0f} · MBS{L["mbs"]}</span></div>'
                    f'<div style="color:#3a4a63;font-size:10px;">{L["league"]} · {ko} UTC</div></div>')
            st.markdown(
                f'<div style="background:#0d1628;border:1px solid #1a2840;border-left:3px solid {ev_color};'
                'border-radius:10px;padding:12px 14px;margin-bottom:6px;">'
                '<div style="display:flex;justify-content:space-between;align-items:center;">'
                f'<span style="color:#e2e8f0;font-weight:800;font-size:13px;font-family:Consolas,monospace;">'
                f'{TYPE_LABEL.get(rc["type"], rc["type"])}</span>'
                f'<span style="color:{ev_color};font-size:10px;font-weight:700;">{ev_txt}</span></div>'
                f'{legs_html}'
                '<div style="border-top:1px solid #1a2840;margin-top:6px;padding-top:6px;font-family:Consolas,monospace;">'
                f'<span style="color:#94a3b8;font-size:11px;">Kombine </span>'
                f'<span style="color:#e2e8f0;font-weight:700;">{rc["combined_odds"]}</span>'
                f'<span style="color:#475569;font-size:11px;"> · 100→</span>'
                f'<span style="color:#10d48e;font-weight:700;">{rc["gross"]:.0f} TL</span>'
                f'<span style="color:#475569;font-size:11px;"> · tutma %{rc["win_prob"]*100:.0f}</span></div>'
                '</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#475569;font-size:10px;padding:2px 0 12px 0;">'
                '⚠️ Öneri — garanti değil. −EV ise model "PAS" diyor (eğlence amaçlı). 15 dk\'da bir güncellenir.'
                '</div>', unsafe_allow_html=True)


def page_ready_coupons(portfolio: dict) -> None:
    """Ayrı sayfa: SENİN manuel oynaman için öneriler (sistemin kuponlarından AYRI)."""
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ HAZIR KUPONLAR (MANUEL)</div>
      <div class="sec-title-meta">SENİN OYNAMAN İÇİN ÖNERİLER</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#10182a;border:1px solid #1e2d4a;border-left:3px solid #3b82f6;'
        'border-radius:8px;padding:10px 14px;margin:4px 0 12px 0;color:#94a3b8;font-size:12px;line-height:1.6;">'
        'ℹ️ Bu kuponlar <b style="color:#e2e8f0;">SENİN manuel oynaman</b> için önerilir — '
        'iddaa\'da kendin oynarsın. <b style="color:#e2e8f0;">Sistemin kendi otomatik (paper) kuponlarından AYRIDIR</b>; '
        'bunlar bankroll\'a/portföye dahil değildir, sadece öneridir. '
        'Sistemin kuponları için → <b>Genel Bakış</b> · <b>Pozisyonlar</b> · <b>Emirler</b>.'
        '</div>', unsafe_allow_html=True)
    render_ready_coupons()


# ════════════════════════════════════════════════════════════════
# CLV — TRUTH METER (Faz 0): çizgiyi yeniyor muyuz?
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def get_clv_data():
    """CLV backfill + karne + son bahisler (10 dk cache). Hata olursa boş döner."""
    try:
        import clv as _clv
        _clv.backfill_clv(PORTFOLIO_ID)          # idempotent — başlamış maçlar için hesapla
        return {
            "summary": _clv.clv_summary(PORTFOLIO_ID),
            "recent":  _clv.recent_bets(PORTFOLIO_ID, limit=20),
        }
    except Exception as e:
        return {"summary": None, "recent": [], "error": str(e)}


def _clv_tile(label: str, value: str, color: str, sub: str = "") -> str:
    return (
        f'<div style="flex:1;background:#0d1628;border:1px solid #1a2840;'
        f'border-top:3px solid {color};border-radius:10px;padding:12px 14px;">'
        f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;'
        f'letter-spacing:0.08em;font-weight:700;">{label}</div>'
        f'<div style="color:{color};font-size:24px;font-weight:900;'
        f'font-family:Consolas,monospace;margin-top:4px;">{value}</div>'
        f'<div style="color:#475569;font-size:10px;margin-top:2px;">{sub}</div></div>')


def page_clv(portfolio: dict) -> None:
    """CLV dashboard — sistemin GERÇEK karnesi (P&L değil, çizgiyi yenme)."""
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ CLV · ÇİZGİYİ YENİYOR MUYUZ?</div>
      <div class="sec-title-meta">CLOSING LINE VALUE · GERÇEK EDGE KARNESİ</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#10182a;border:1px solid #1e2d4a;border-left:3px solid #3b82f6;'
        'border-radius:8px;padding:10px 14px;margin:4px 0 14px 0;color:#94a3b8;font-size:12px;line-height:1.6;">'
        'ℹ️ <b style="color:#e2e8f0;">CLV = (giriş oranı ÷ kapanış oranı) − 1</b>. '
        'Pozitifse kapanıştan <b style="color:#10d48e;">daha iyi fiyat</b> yakaladık = uzun vadede kâr işareti. '
        'P&L gürültülüdür ve aylar alır; <b style="color:#e2e8f0;">CLV haftalar içinde "edge var mı?"</b> sorusuna cevap verir. '
        'Not: giriş ve kapanış aynı kitabın (iddaa) oranı → bu <b>intra-iddaa CLV</b>, '
        'sharp-book CLV\'si değil. Anlamlı yorum için <b style="color:#e2e8f0;">≥150 bahis</b> gerekir.'
        '</div>', unsafe_allow_html=True)

    data = get_clv_data()
    s = data.get("summary")
    if not s or not s["overall"]["n"]:
        st.markdown('<div style="color:#475569;font-size:13px;padding:10px 0;">'
                    'Henüz CLV hesaplanabilir (maçı başlamış) bahis yok. '
                    'Maçlar başladıkça karne otomatik dolar — 10 dk\'da bir güncellenir.'
                    '</div>', unsafe_allow_html=True)
        if data.get("error"):
            st.caption(f"({data['error']})")
        return

    o = s["overall"]
    n = o["n"]
    mean = o["mean"]; med = o["median"]; beat = o["beat_rate"]
    pos = mean > 0
    main_color = "#10d48e" if pos else "#f59e0b"

    # KPI satırı
    tiles = "".join([
        _clv_tile("CLV'li Bahis", f"{n}", "#3b82f6",
                  "≥150 anlamlı" if n < 150 else "anlamlı örneklem ✓"),
        _clv_tile("Ortalama CLV", f"{mean*100:+.2f}%", main_color,
                  "edge işareti" if pos else "edge yok"),
        _clv_tile("Medyan CLV", f"{med*100:+.2f}%", "#94a3b8", ""),
        _clv_tile("Beat-rate", f"{beat*100:.0f}%", "#94a3b8", "CLV>0 oranı"),
    ])
    st.markdown(f'<div style="display:flex;gap:10px;margin-bottom:10px;">{tiles}</div>',
                unsafe_allow_html=True)

    # VERDİKT
    if n < 30:
        verdict = ("⏳ Örneklem küçük (n<30) — yorum için erken. Karne dolmaya devam ediyor.", "#64748b")
    elif pos and n >= 150:
        verdict = (f"✅ EDGE İŞARETİ: {n} bahiste ortalama +{mean*100:.2f}% CLV. "
                   "Bu pazar/nişe yüklenmeyi değerlendir.", "#10d48e")
    elif pos:
        verdict = (f"🟡 Umut verici (+{mean*100:.2f}%) ama n={n}<150 — kesin değil, örneklem büyümeli.", "#f59e0b")
    else:
        verdict = (f"🔴 Ortalama CLV negatif ({mean*100:.2f}%) — bu örneklemde çizgiyi yenmiyoruz. "
                   "Verimli-pazar duvarı; nişlere bakılmalı.", "#ef4444")
    st.markdown(
        f'<div style="background:#0d1628;border-left:3px solid {verdict[1]};border-radius:8px;'
        f'padding:10px 14px;margin:4px 0 14px 0;color:{verdict[1]};font-size:13px;font-weight:600;">'
        f'{verdict[0]}</div>', unsafe_allow_html=True)

    # Pazar + Lig kırılımı
    def _breakdown(title, d):
        rows = ""
        for k, a in d.items():
            if not a["n"]:
                continue
            c = "#10d48e" if (a["mean"] or 0) > 0 else "#f59e0b"
            rows += (
                '<tr style="border-top:1px solid #18233a;">'
                f'<td style="padding:5px 8px;color:#e2e8f0;font-size:12px;">{k}</td>'
                f'<td style="padding:5px 8px;color:#94a3b8;font-size:12px;text-align:right;font-family:Consolas;">{a["n"]}</td>'
                f'<td style="padding:5px 8px;color:{c};font-size:12px;text-align:right;font-family:Consolas;font-weight:700;">{a["mean"]*100:+.2f}%</td>'
                f'<td style="padding:5px 8px;color:#94a3b8;font-size:12px;text-align:right;font-family:Consolas;">{a["beat_rate"]*100:.0f}%</td>'
                '</tr>')
        return (
            f'<div style="flex:1;background:#0d1628;border:1px solid #1a2840;border-radius:10px;padding:8px 6px;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;'
            f'font-weight:700;padding:4px 8px;">{title}</div>'
            '<table style="width:100%;border-collapse:collapse;">'
            '<tr style="color:#475569;font-size:9px;text-transform:uppercase;">'
            '<td style="padding:2px 8px;">İsim</td><td style="padding:2px 8px;text-align:right;">n</td>'
            '<td style="padding:2px 8px;text-align:right;">Ort CLV</td><td style="padding:2px 8px;text-align:right;">Beat</td></tr>'
            f'{rows}</table></div>')

    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:12px;">'
        f'{_breakdown("PAZAR BAZLI", s["by_market"])}{_breakdown("LİG BAZLI", s["by_league"])}'
        f'</div>', unsafe_allow_html=True)

    # Son bahisler
    recent = data.get("recent") or []
    if recent:
        st.markdown('<div class="sec-title" style="margin-top:6px;">'
                    '<div class="sec-title-main">▸ SON BAHİSLER · GİRİŞ vs KAPANIŞ</div></div>',
                    unsafe_allow_html=True)
        rows = ""
        for b in recent:
            clv = b.get("clv") or 0.0
            c = "#10d48e" if clv > 0 else ("#ef4444" if clv < 0 else "#64748b")
            entry = b.get("odds") or 0.0
            close = b.get("closing_odds")
            entry_s = f"{entry:.2f}" if entry else "—"
            close_s = f"{close:.2f}" if close else "—"
            ko = (b.get("kickoff_utc") or "")[:10]
            rows += (
                '<tr style="border-top:1px solid #18233a;">'
                f'<td style="padding:5px 8px;color:#e2e8f0;font-size:11px;">{b.get("home_team","?")} v {b.get("away_team","?")}</td>'
                f'<td style="padding:5px 8px;color:#10d48e;font-size:11px;font-family:Consolas;">{b.get("market","")}:{b.get("pick","")}</td>'
                f'<td style="padding:5px 8px;color:#94a3b8;font-size:11px;text-align:right;font-family:Consolas;">{entry_s}</td>'
                f'<td style="padding:5px 8px;color:#94a3b8;font-size:11px;text-align:right;font-family:Consolas;">{close_s}</td>'
                f'<td style="padding:5px 8px;color:{c};font-size:11px;text-align:right;font-family:Consolas;font-weight:700;">{clv*100:+.1f}%</td>'
                f'<td style="padding:5px 8px;color:#3a4a63;font-size:10px;text-align:right;">{ko}</td>'
                '</tr>')
        st.markdown(
            '<div style="background:#0d1628;border:1px solid #1a2840;border-radius:10px;padding:6px;overflow-x:auto;">'
            '<table style="width:100%;border-collapse:collapse;">'
            '<tr style="color:#475569;font-size:9px;text-transform:uppercase;">'
            '<td style="padding:2px 8px;">Maç</td><td style="padding:2px 8px;">Seçim</td>'
            '<td style="padding:2px 8px;text-align:right;">Giriş</td><td style="padding:2px 8px;text-align:right;">Kapanış</td>'
            '<td style="padding:2px 8px;text-align:right;">CLV</td><td style="padding:2px 8px;text-align:right;">Tarih</td></tr>'
            f'{rows}</table></div>', unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# KUPON ANALİZİ — DATA · MODEL · TRADE
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def get_coupon_analysis():
    try:
        import analyze_coupons as _ac
        return _ac.analyze(PORTFOLIO_ID)
    except Exception as e:
        return {"error": str(e)}


def page_coupon_analysis(portfolio: dict) -> None:
    """Kazanan/kaybeden kupon analizi — DATA · MODEL · TRADE çerçevesi."""
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ KUPON ANALİZİ</div>
      <div class="sec-title-meta">DATA · MODEL · TRADE · KAZANAN/KAYBEDEN</div>
    </div>
    """, unsafe_allow_html=True)

    a = get_coupon_analysis()
    if a.get("error") or "overview" not in a:
        st.warning(f"Analiz yüklenemedi: {a.get('error','veri yok')}")
        return
    o = a["overview"]
    n_dec = o["coupons_decided"]

    def _pc(x):
        return f"%{x*100:.0f}" if x is not None else "—"

    # KPI tiles
    roi = o["roi"]
    roi_c = "#10d48e" if (roi or 0) > 0 else "#ef4444" if (roi or 0) < 0 else "#94a3b8"
    tiles = "".join([
        _clv_tile("Karar Kupon", f"{n_dec}", "#3b82f6", f"+{o['coupons_open']} açık · {o['coupons_void']} void"),
        _clv_tile("İsabet", _pc(o["hit_rate"]), "#94a3b8", f"{o['coupons_won']}/{n_dec} kazanan"),
        _clv_tile("ROI", f"{roi:+.1f}%" if roi is not None else "—", roi_c, f"PnL {o['pnl']:+.0f} TL"),
        _clv_tile("Bankroll", f"{o['bankroll_cur']:.0f}" if o['bankroll_cur'] else "—", "#94a3b8",
                  f"başlangıç {o['bankroll_init']:.0f}" if o['bankroll_init'] else ""),
    ])
    st.markdown(f'<div style="display:flex;gap:10px;margin-bottom:10px;">{tiles}</div>',
                unsafe_allow_html=True)

    # Örneklem uyarısı
    if n_dec < 30:
        st.markdown(
            f'<div style="background:#1a1410;border-left:3px solid #f59e0b;border-radius:8px;'
            f'padding:10px 14px;margin-bottom:14px;color:#f59e0b;font-size:13px;font-weight:600;">'
            f'⚠️ Karar verilen kupon = {n_dec} (&lt;30). Bu örneklemde win/loss & ROI <b>GÜRÜLTÜ</b> — '
            f'yorum erken. Bu aşamada <b>CLV</b> ve <b>kalibrasyon</b> daha hızlı sinyal verir. '
            f'(Haziran = sezon arası; gerçek test ligler Ağustos\'ta açılınca başlar.)'
            f'</div>', unsafe_allow_html=True)

    # tablo helper
    def _tbl(title, headers, rows_data):
        head = "".join(f'<td style="padding:2px 8px;text-align:right;">{h}</td>' for h in headers[1:])
        head = f'<td style="padding:2px 8px;">{headers[0]}</td>' + head
        body = ""
        for r in rows_data:
            cells = f'<td style="padding:5px 8px;color:#e2e8f0;font-size:12px;">{r[0]}</td>'
            for cell, color in r[1:]:
                cells += (f'<td style="padding:5px 8px;color:{color};font-size:12px;text-align:right;'
                          f'font-family:Consolas,monospace;">{cell}</td>')
            body += f'<tr style="border-top:1px solid #18233a;">{cells}</tr>'
        return (
            f'<div style="flex:1;background:#0d1628;border:1px solid #1a2840;border-radius:10px;padding:8px 6px;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:0.08em;'
            f'font-weight:700;padding:4px 8px;">{title}</div>'
            f'<table style="width:100%;border-collapse:collapse;">'
            f'<tr style="color:#475569;font-size:9px;text-transform:uppercase;">{head}</tr>{body}</table></div>')

    # MODEL: kalibrasyon + edge
    calib_rows = []
    for c in a["calibration"]:
        if c["n"]:
            gap = c["gap"]
            gc = "#10d48e" if abs(gap) <= 0.07 else "#f59e0b" if abs(gap) <= 0.15 else "#ef4444"
            calib_rows.append([c["band"], (str(c["n"]), "#94a3b8"), (_pc(c["pred"]), "#64748b"),
                               (_pc(c["actual"]), "#e2e8f0"), (f"{gap*100:+.0f}p", gc)])
        else:
            calib_rows.append([c["band"], ("0", "#3a4a63"), ("—", "#3a4a63"), ("—", "#3a4a63"), ("—", "#3a4a63")])
    edge_rows = []
    for e in a["edge_perf"]:
        edge_rows.append([e["band"], (str(e["n"]), "#94a3b8"), (_pc(e["hit_rate"]), "#e2e8f0")])
    st.markdown('<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:0.1em;'
                'font-weight:700;margin:6px 0 4px 0;">🧠 MODEL — kalibrasyon & edge geçerliliği</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:12px;">'
        f'{_tbl("KALİBRASYON (tahmin vs gerçek)", ["Bant","n","Tahmin","Gerçek","Fark"], calib_rows)}'
        f'{_tbl("EDGE → İSABET", ["Edge bandı","n","İsabet"], edge_rows)}'
        f'</div>', unsafe_allow_html=True)

    # TRADE: tür + lig
    type_rows = [[k, (str(v["n"]), "#94a3b8"), (_pc(v["hit_rate"]), "#e2e8f0"),
                  (f"{v['roi']:+.0f}%" if v["roi"] is not None else "—",
                   "#10d48e" if (v["roi"] or 0) > 0 else "#ef4444" if (v["roi"] or 0) < 0 else "#94a3b8")]
                 for k, v in sorted(a["by_type"].items())]
    league_rows = [[k, (str(v["n"]), "#94a3b8"), (_pc(v["hit_rate"]), "#e2e8f0")]
                   for k, v in sorted(a["by_league"].items())]
    st.markdown('<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:0.1em;'
                'font-weight:700;margin:6px 0 4px 0;">💸 TRADE — tür & lig performansı</div>',
                unsafe_allow_html=True)
    st.markdown(
        f'<div style="display:flex;gap:10px;margin-bottom:12px;">'
        f'{_tbl("KUPON TÜRÜ", ["Tür","n","İsabet","ROI"], type_rows or [["(veri yok)",("","#3a4a63"),("","#3a4a63"),("","#3a4a63")]])}'
        f'{_tbl("LİG", ["Lig","n","İsabet"], league_rows or [["(veri yok)",("","#3a4a63"),("","#3a4a63")]])}'
        f'</div>', unsafe_allow_html=True)

    # DATA kalite + CLV özet satırı
    dq = a["data_quality"]
    clv = a["clv"]
    vr = dq["void_rate"]
    vr_c = "#10d48e" if (vr or 0) < 0.15 else "#f59e0b" if (vr or 0) < 0.4 else "#ef4444"
    clv_c = "#10d48e" if (clv and clv["mean"] > 0) else "#94a3b8"
    clv_val = (f"{clv['mean']*100:+.2f}%" if clv else "—")
    clv_sub = (f"beat {_pc(clv['beat_rate'])} · n={clv['n']}" if clv else "veri yok")
    cov_val = _pc(dq["closing_coverage"])
    settled_n = str(dq["settled_bets"])
    tiles2 = "".join([
        _clv_tile("📊 Void oranı", _pc(vr), vr_c, "yüksek=operasyonel sorun"),
        _clv_tile("Kapanış kapsamı", cov_val, "#94a3b8", "CLV için gerekli"),
        _clv_tile("CLV", clv_val, clv_c, clv_sub),
        _clv_tile("Settle bahis", settled_n, "#3b82f6", "truth meter girdisi"),
    ])
    st.markdown(f'<div style="display:flex;gap:10px;">{tiles2}</div>', unsafe_allow_html=True)


def page_overview(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ OVERVIEW</div>
      <div class="sec-title-meta">PAPER TRADING DASHBOARD</div>
    </div>
    """, unsafe_allow_html=True)

    bankroll = portfolio.get("current_bankroll") or INITIAL_BANKROLL
    pnl = portfolio.get("pnl") or 0.0
    yield_pct = portfolio.get("yield_pct") or 0.0
    open_c = portfolio.get("open_coupons") or 0
    buying_power = portfolio.get("buying_power") or bankroll

    pnl_sign = "pos" if pnl >= 0 else "neg"
    pnl_color = "#10d48e" if pnl >= 0 else "#ef4444"

    st.markdown(f"""
    <div class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Portfolio Value</div>
        <div class="kpi-value">{bankroll:,.0f} TL</div>
        <div class="kpi-delta muted">Baslangic: {INITIAL_BANKROLL:,.0f} TL</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total P&L</div>
        <div class="kpi-value" style="color:{pnl_color};">{pnl:+,.0f} TL</div>
        <div class="kpi-delta {pnl_sign}">Yield: {yield_pct:+.1f}%</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Open Coupons</div>
        <div class="kpi-value">{open_c}</div>
        <div class="kpi-delta muted">Staked: {portfolio.get('staked_open', 0):,.0f} TL</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Buying Power</div>
        <div class="kpi-value">{buying_power:,.0f} TL</div>
        <div class="kpi-delta muted">Acik kupon dusuldu</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── HEDEFLİ DÖNEM İLERLEME ÇUBUĞU ───────────────────────
    try:
        from paper_engine import PaperEngine
        _eng_p = PaperEngine(PORTFOLIO_ID)
        per = _eng_p.manage_period()
        ps   = per["period_start_bankroll"]
        tgt  = per["target"]
        cur  = per["current"]
        prog = max(0.0, min(100.0, per["progress_pct"]))
        days = per["days_elapsed"]
        locked = per["locked_profit"]
        pstatus = per["status"]
        comp = per["completed_periods"]

        # Renk: hedefe yaklaştıkça yeşil
        bar_color = "#10d48e" if prog >= 60 else "#3b82f6" if prog >= 20 else "#f59e0b"
        if pstatus == "target_hit":
            bar_color = "#10d48e"
        elif pstatus == "stopped":
            bar_color = "#ef4444"

        status_label = {
            "active":     "● AKTIF DÖNEM",
            "target_hit": "🎯 HEDEF TUTTU",
            "stopped":    "⛔ STOP-LOSS",
        }.get(pstatus, pstatus)

        st.markdown(f"""
        <div style="background:#0d1628;border:1px solid #1a2840;border-radius:10px;
             padding:14px 18px;margin:6px 0 16px 0;">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <div>
              <span style="color:{bar_color};font-size:12px;font-weight:700;
                    font-family:Consolas,monospace;letter-spacing:0.06em;">{status_label}</span>
              <span style="color:#475569;font-size:11px;font-family:Consolas,monospace;margin-left:10px;">
                Dönem başı: {ps:,.0f} TL · {days} gün · Tamamlanan dönem: {comp}</span>
            </div>
            <div style="text-align:right;font-family:Consolas,monospace;">
              <span style="color:#94a3b8;font-size:11px;">Kilitli kâr: </span>
              <span style="color:#10d48e;font-size:13px;font-weight:700;">{locked:,.0f} TL</span>
            </div>
          </div>
          <div style="background:#0a0f1a;border-radius:6px;height:26px;position:relative;overflow:hidden;">
            <div style="background:linear-gradient(90deg,{bar_color}88,{bar_color});
                 width:{prog:.0f}%;height:100%;border-radius:6px;transition:width 0.3s;"></div>
            <div style="position:absolute;top:0;left:0;width:100%;height:100%;
                 display:flex;align-items:center;justify-content:center;
                 font-family:Consolas,monospace;font-size:12px;font-weight:700;color:#e2e8f0;">
              {cur:,.0f} / {tgt:,.0f} TL  ·  %{prog:.0f} (hedef +%20)
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception:
        pass

    # ── Settle button (compact, above tabs) ─────────────────
    settle_col, _ = st.columns([1, 3])
    with settle_col:
        if st.button("✓ SETTLE ALL", use_container_width=True, key="settle_overview"):
            try:
                from paper_engine import PaperEngine
                _eng = PaperEngine(PORTFOLIO_ID)
                _res = _eng.settle_coupons()
                _n = _res.get("settled", 0)
                _p = _res.get("pnl", 0.0)
                if _n > 0:
                    st.success(f"{_n} kupon kapatildi | PnL: {_p:+.0f} TL")
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.info("Kapanacak bitik mac bulunamadi.")
            except Exception as _e:
                st.error(f"Settle hatasi: {_e}")

    TYPE_COLORS = {
        "K2_FAVORI":   "#10d48e",
        "K2_VALUE":    "#3b82f6",
        "K2_KARISIK":  "#f59e0b",
        "K3_KOMBO":    "#a78bfa",
        "K1_FAVORITE": "#10d48e",
        "K1_KG":       "#3b82f6",
        "K2_COMBO":    "#f59e0b",
        "K1_ALT":      "#a78bfa",
    }
    TYPE_DESC = {
        "K2_FAVORI":   "2'li Favori",
        "K2_VALUE":    "2'li Value",
        "K2_KARISIK":  "2'li Karisik",
        "K3_KOMBO":    "3'lu Kombo",
        "K1_FAVORITE": "Favori (eski)",
        "K1_KG":       "KG (eski)",
        "K2_COMBO":    "2'li Kombin",
        "K1_ALT":      "Alt 2.5 (eski)",
    }

    now_utc = datetime.utcnow()

    # ── Queries ─────────────────────────────────────────────
    open_coupons = _db_rows("""
        SELECT coupon_id, session_date, coupon_type, num_legs,
               combined_odds, stake, potential_return, reasoning
        FROM paper_coupons
        WHERE portfolio_id=? AND status='open'
        ORDER BY created_at DESC
    """, (PORTFOLIO_ID,))

    won_coupons = _db_rows("""
        SELECT coupon_id, session_date, coupon_type, num_legs,
               combined_odds, stake, actual_return, pnl, settled_at
        FROM paper_coupons
        WHERE portfolio_id=? AND status='won'
        ORDER BY settled_at DESC LIMIT 20
    """, (PORTFOLIO_ID,))

    lost_coupons = _db_rows("""
        SELECT coupon_id, session_date, coupon_type, num_legs,
               combined_odds, stake, actual_return, pnl, settled_at
        FROM paper_coupons
        WHERE portfolio_id=? AND status='lost'
        ORDER BY settled_at DESC LIMIT 20
    """, (PORTFOLIO_ID,))

    # ── Bekleyen sub-filter (Devam Eden / Başlamamış) ────────
    # Bir kuponun en erken kickoff'una göre filtrele
    def _earliest_kickoff(coupon_id: str) -> datetime | None:
        bets = _db_rows(
            "SELECT kickoff_utc FROM paper_bets WHERE coupon_id=?",
            (coupon_id,)
        )
        times = []
        for b in bets:
            ko = b.get("kickoff_utc") or ""
            try:
                times.append(datetime.fromisoformat(ko.replace("Z", "")))
            except Exception:
                pass
        return min(times) if times else None

    # Separate Başlamamış vs Devam Eden
    bekleyen_baslamamis = []
    bekleyen_devam      = []
    for c in open_coupons:
        ko = _earliest_kickoff(c.get("coupon_id", ""))
        if ko is None or ko > now_utc:
            bekleyen_baslamamis.append(c)
        else:
            bekleyen_devam.append(c)

    # ── MAIN TABS ────────────────────────────────────────────
    n_open = len(open_coupons)
    n_won  = len(won_coupons)
    n_lost = len(lost_coupons)

    tab_bekleyen, tab_kazanan, tab_kaybeden, tab_arsiv = st.tabs([
        f"Bekleyen  ({n_open})",
        f"Kazanan  ({n_won})",
        f"Kaybeden  ({n_lost})",
        "Arsiv",
    ])

    # ════════════════════════════════════════════════════════
    # TAB 1: BEKLEYEN
    # ════════════════════════════════════════════════════════
    with tab_bekleyen:
        if not open_coupons:
            st.markdown(
                '<div style="color:#475569;font-size:13px;padding:20px 0;">'
                'Acik kupon yok. Matches sayfasindan AUTO-PLAY SIGNALS ile kupon olusturun.'
                '</div>',
                unsafe_allow_html=True,
            )
            _show_today_preview()
        else:
            # Sub-tabs: Tümü / Devam Eden / Başlamamış
            sub_tumu, sub_devam, sub_baslamamis = st.tabs([
                f"Tumu  ({n_open})",
                f"Devam Eden  ({len(bekleyen_devam)})",
                f"Baslamamis  ({len(bekleyen_baslamamis)})",
            ])

            def _render_open_coupons(coupon_list):
                if not coupon_list:
                    st.markdown(
                        '<div style="color:#475569;font-size:12px;padding:12px 0;">Bu filtrede kupon yok.</div>',
                        unsafe_allow_html=True
                    )
                    return
                cols_per_row = 2
                for i in range(0, len(coupon_list), cols_per_row):
                    _cols = st.columns(cols_per_row)
                    for j, coup in enumerate(coupon_list[i : i + cols_per_row]):
                        with _cols[j]:
                            ctype = coup.get("coupon_type", "")
                            tc = TYPE_COLORS.get(ctype, "#64748b")
                            cid = (coup.get("coupon_id") or "")[:8]
                            reasoning = (coup.get("reasoning") or "")[:80]
                            ctype_desc = TYPE_DESC.get(ctype, ctype)

                            bets = _db_rows("""
                                SELECT home_team, away_team, market, pick, odds,
                                       model_prob, implied_prob, edge, signal_score,
                                       status, kickoff_utc
                                FROM paper_bets WHERE coupon_id=?
                                ORDER BY odds DESC
                            """, (coup["coupon_id"],))

                            bet_html = ""
                            for b in bets:
                                mp_raw   = b.get("model_prob") or 0
                                ip_raw   = b.get("implied_prob") or 0
                                edge_v   = b.get("edge") or 0
                                sc       = b.get("signal_score") or 0
                                mp_pct   = mp_raw * 100
                                ip_pct   = ip_raw * 100
                                edge_pct = edge_v * 100
                                home     = (b.get("home_team") or "?")[:16]
                                away     = (b.get("away_team") or "?")[:16]
                                ko_raw   = b.get("kickoff_utc") or ""
                                mkt      = b.get("market", "")
                                pck      = b.get("pick", "")
                                ods      = b.get("odds") or 0
                                try:
                                    ko_dt   = datetime.fromisoformat(ko_raw.replace("Z", ""))
                                    ko_disp = ko_dt.strftime("%d %b %H:%M")
                                    delta_h = (ko_dt - now_utc).total_seconds() / 3600
                                    if delta_h > 2:
                                        chip_bg, chip_bd, chip_cl, chip_lb = "rgba(59,130,246,0.12)", "#3b82f6", "#3b82f6", "UPCOMING"
                                    elif delta_h > -2:
                                        chip_bg, chip_bd, chip_cl, chip_lb = "rgba(16,212,142,0.12)", "#10d48e", "#10d48e", "LIVE"
                                    else:
                                        chip_bg, chip_bd, chip_cl, chip_lb = "rgba(100,116,139,0.12)", "#475569", "#64748b", "FIN"
                                    ko_chip = (f'<span style="background:{chip_bg};border:1px solid {chip_bd};'
                                               f'color:{chip_cl};border-radius:3px;padding:1px 6px;font-size:9px;'
                                               f'font-weight:700;letter-spacing:0.05em;">{chip_lb}</span>')
                                except Exception:
                                    ko_disp = ko_raw[:10]
                                    ko_chip = ""
                                mp_clr   = "#10d48e" if mp_pct >= 65 else "#f59e0b" if mp_pct >= 58 else "#64748b"
                                edge_clr = "#10d48e" if edge_pct >= 0 else "#ef4444"
                                edge_sgn = "+" if edge_pct >= 0 else ""
                                sc_clr   = "#10d48e" if sc > 0.70 else "#f59e0b" if sc > 0.45 else "#64748b"
                                bet_html += (
                                    '<div style="background:rgba(10,13,20,0.55);border:1px solid #1a2840;'
                                    'border-radius:5px;padding:7px 10px;margin-bottom:6px;">'
                                    '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;'
                                    'font-family:Consolas,Courier New,monospace;font-size:11px;">'
                                    f'<span style="color:#475569;font-size:10px;min-width:64px;">{ko_disp}</span>'
                                    f'{ko_chip}'
                                    f'<span style="color:#e2e8f0;font-weight:600;flex:1;min-width:90px;">{home} vs {away}</span>'
                                    f'<span style="color:#64748b;background:rgba(100,116,139,0.1);border-radius:3px;padding:1px 5px;">{mkt}</span>'
                                    f'<span style="color:#f59e0b;font-weight:700;font-size:12px;">{pck}</span>'
                                    f'<span style="color:#e2e8f0;font-weight:600;">@{ods:.2f}</span>'
                                    '</div>'
                                    '<div style="display:flex;align-items:center;gap:14px;margin-top:5px;flex-wrap:wrap;">'
                                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">Model <span style="color:{mp_clr};font-weight:700;">%{mp_pct:.0f}</span></span>'
                                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">Piyasa <span style="color:#64748b;">%{ip_pct:.0f}</span></span>'
                                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">Edge <span style="color:{edge_clr};font-weight:700;">{edge_sgn}{edge_pct:.1f}%</span></span>'
                                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">Guven <span style="color:{sc_clr};">{sc:.2f}</span></span>'
                                    '</div>'
                                    '</div>'
                                )
                            roi_pct = (
                                ((coup.get("potential_return") or 0) - (coup.get("stake") or 0))
                                / (coup.get("stake") or 1) * 100
                            )
                            pot  = coup.get("potential_return") or 0
                            odds = coup.get("combined_odds") or 0
                            stk  = coup.get("stake") or 0
                            legs = coup.get("num_legs", 1)
                            sdt  = coup.get("session_date", "")
                            rsn  = reasoning
                            svg_chart = _svg_position_chart(stk, pot, tc, cid)
                            card_html = (
                                f'<div style="background:#0d1628;border:1px solid #1a2840;border-left:3px solid {tc};'
                                f'border-radius:8px;padding:14px 16px;margin-bottom:14px;">'
                                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                                f'<div>'
                                f'<span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;font-family:Consolas,monospace;color:{tc};">{ctype_desc}</span>'
                                f'<span style="color:#2d3f5e;font-size:10px;font-family:Consolas,monospace;margin-left:8px;">[{cid}]</span>'
                                f'</div>'
                                f'<div style="text-align:right;">'
                                f'<div style="color:{tc};font-size:14px;font-weight:700;font-family:Consolas,monospace;">&#9658; {pot:.0f} TL</div>'
                                f'<div style="color:#475569;font-size:10px;font-family:Consolas,monospace;">+{roi_pct:.0f}% ROI</div>'
                                f'</div>'
                                f'</div>'

                    # Stats row: ORAN · STAKE · AYAK · TARİH  +  chart inline right
                    f'<div style="display:flex;align-items:center;justify-content:space-between;'
                    f'gap:12px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #0f1829;">'

                                # stats row: ORAN · STAKE · AYAK · TARIH + chart
                                f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #0f1829;">'
                                f'<div style="display:flex;gap:16px;flex-wrap:wrap;">'
                                f'<div style="font-family:Consolas,monospace;"><span style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:0.08em;display:block;">ORAN</span><span style="font-size:18px;font-weight:700;color:#e2e8f0;">{odds:.3f}x</span></div>'
                                f'<div style="font-family:Consolas,monospace;"><span style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:0.08em;display:block;">STAKE</span><span style="font-size:18px;font-weight:700;color:#e2e8f0;">{stk:.0f} TL</span></div>'
                                f'<div style="font-family:Consolas,monospace;"><span style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:0.08em;display:block;">AYAK</span><span style="font-size:18px;font-weight:700;color:#64748b;">{legs}</span></div>'
                                f'<div style="font-family:Consolas,monospace;"><span style="font-size:9px;color:#475569;text-transform:uppercase;letter-spacing:0.08em;display:block;">TARIH</span><span style="font-size:13px;font-weight:600;color:#64748b;">{sdt}</span></div>'
                                f'</div>'
                                f'<div style="flex-shrink:0;">'
                                + svg_chart
                                + f'</div>'
                                f'</div>'
                            )
                            if rsn:
                                card_html += (
                                    f'<div style="color:#64748b;font-size:11px;line-height:1.4;'
                                    f'margin-bottom:10px;font-style:italic;">{rsn}</div>'
                                )
                            card_html += bet_html + '</div>'
                            st.markdown(card_html, unsafe_allow_html=True)

            with sub_tumu:
                _render_open_coupons(open_coupons)
            with sub_devam:
                _render_open_coupons(bekleyen_devam)
            with sub_baslamamis:
                _render_open_coupons(bekleyen_baslamamis)

    # ════════════════════════════════════════════════════════
    # TAB 2: KAZANAN
    # ════════════════════════════════════════════════════════
    with tab_kazanan:
        if not won_coupons:
            st.markdown(
                '<div style="color:#475569;font-size:13px;padding:20px 0;">Henuz kazanilan kupon yok.</div>',
                unsafe_allow_html=True
            )
        else:
            for coup in won_coupons:
                ctype = coup.get("coupon_type", "")
                tc    = TYPE_COLORS.get(ctype, "#10d48e")
                cid   = (coup.get("coupon_id") or "")[:8]
                pnl   = coup.get("pnl") or 0
                stk   = coup.get("stake") or 0
                pot   = coup.get("actual_return") or 0
                odds  = coup.get("combined_odds") or 0
                legs  = coup.get("num_legs", 1)
                sdt   = coup.get("session_date", "")
                sat   = (coup.get("settled_at") or "")[:10]
                roi   = (pot - stk) / stk * 100 if stk else 0
                svg   = _svg_settlement_chart(stk, pnl, cid)
                bets  = _db_rows(
                    "SELECT home_team, away_team, market, pick, odds, home_score, away_score FROM paper_bets WHERE coupon_id=?",
                    (coup["coupon_id"],)
                )
                bet_rows = ""
                for b in bets:
                    sc = f"{b.get('home_score','-')}-{b.get('away_score','-')}"
                    bet_rows += (
                        f'<div style="color:#475569;font-size:11px;font-family:Consolas,monospace;'
                        f'padding:3px 0;border-bottom:1px solid #0f1829;">'
                        f'{(b.get("home_team") or "?")[:14]} vs {(b.get("away_team") or "?")[:14]}'
                        f' &nbsp;·&nbsp; {b.get("market","")} {b.get("pick","")} @{b.get("odds",0):.2f}'
                        f' &nbsp;·&nbsp; <span style="color:#10d48e;">Skor: {sc}</span></div>'
                    )
                card = (
                    f'<div style="background:rgba(16,212,142,0.04);border:1px solid #1a2840;'
                    f'border-left:4px solid #10d48e;border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                    f'<span style="background:#10d48e;color:#0a0d14;font-size:10px;font-weight:800;'
                    f'padding:2px 8px;border-radius:4px;text-transform:uppercase;">KAZANDI</span>'
                    f'<span style="color:#10d48e;font-size:13px;font-weight:700;font-family:Consolas,monospace;">+{pnl:.0f} TL</span>'
                    f'<span style="color:#475569;font-size:10px;font-family:Consolas,monospace;margin-left:auto;">{sat} · [{cid}]</span>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;margin-bottom:8px;">'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">ORAN <span style="color:#e2e8f0;font-weight:700;">{odds:.3f}x</span></span>'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">STAKE <span style="color:#e2e8f0;">{stk:.0f} TL</span></span>'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">GETIRI <span style="color:#10d48e;">{pot:.0f} TL</span></span>'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">ROI <span style="color:#10d48e;">+{roi:.0f}%</span></span>'
                    f'</div>'
                    f'{bet_rows}'
                    f'</div>'
                    f'<div style="flex-shrink:0;border-left:1px solid #1a2840;padding-left:12px;">'
                    + svg
                    + f'</div></div></div>'
                )
                st.markdown(card, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # TAB 3: KAYBEDEN
    # ════════════════════════════════════════════════════════
    with tab_kaybeden:
        if not lost_coupons:
            st.markdown(
                '<div style="color:#475569;font-size:13px;padding:20px 0;">Henuz kaybedilen kupon yok.</div>',
                unsafe_allow_html=True
            )
        else:
            for coup in lost_coupons:
                cid  = (coup.get("coupon_id") or "")[:8]
                pnl  = coup.get("pnl") or 0
                stk  = coup.get("stake") or 0
                odds = coup.get("combined_odds") or 0
                sat  = (coup.get("settled_at") or "")[:10]
                svg  = _svg_settlement_chart(stk, pnl, cid)
                bets = _db_rows(
                    "SELECT home_team, away_team, market, pick, odds, home_score, away_score FROM paper_bets WHERE coupon_id=?",
                    (coup["coupon_id"],)
                )
                bet_rows = ""
                for b in bets:
                    sc = f"{b.get('home_score','-')}-{b.get('away_score','-')}"
                    bet_rows += (
                        f'<div style="color:#475569;font-size:11px;font-family:Consolas,monospace;'
                        f'padding:3px 0;border-bottom:1px solid #0f1829;">'
                        f'{(b.get("home_team") or "?")[:14]} vs {(b.get("away_team") or "?")[:14]}'
                        f' &nbsp;·&nbsp; {b.get("market","")} {b.get("pick","")} @{b.get("odds",0):.2f}'
                        f' &nbsp;·&nbsp; <span style="color:#ef4444;">Skor: {sc}</span></div>'
                    )
                card = (
                    f'<div style="background:rgba(239,68,68,0.04);border:1px solid #1a2840;'
                    f'border-left:4px solid #ef4444;border-radius:8px;padding:12px 16px;margin-bottom:10px;">'
                    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;">'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">'
                    f'<span style="background:#ef4444;color:#fff;font-size:10px;font-weight:800;'
                    f'padding:2px 8px;border-radius:4px;text-transform:uppercase;">KAYBETTI</span>'
                    f'<span style="color:#ef4444;font-size:13px;font-weight:700;font-family:Consolas,monospace;">{pnl:.0f} TL</span>'
                    f'<span style="color:#475569;font-size:10px;font-family:Consolas,monospace;margin-left:auto;">{sat} · [{cid}]</span>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;margin-bottom:8px;">'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">ORAN <span style="color:#e2e8f0;">{odds:.3f}x</span></span>'
                    f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">STAKE <span style="color:#e2e8f0;">{stk:.0f} TL</span></span>'
                    f'</div>'
                    f'{bet_rows}'
                    f'</div>'
                    f'<div style="flex-shrink:0;border-left:1px solid #1a2840;padding-left:12px;">'
                    + svg
                    + f'</div></div></div>'
                )
                st.markdown(card, unsafe_allow_html=True)

    # ════════════════════════════════════════════════════════
    # TAB 4: ARŞİV
    # ════════════════════════════════════════════════════════
    with tab_arsiv:
        all_settled = _db_rows("""
            SELECT session_date, coupon_type, num_legs, combined_odds,
                   stake, actual_return, pnl, status, settled_at
            FROM paper_coupons
            WHERE portfolio_id=? AND status != 'open'
            ORDER BY settled_at DESC
        """, (PORTFOLIO_ID,))
        if not all_settled:
            st.markdown(
                '<div style="color:#475569;font-size:13px;padding:20px 0;">Arsiv bos.</div>',
                unsafe_allow_html=True
            )
        else:
            table = []
            for r in all_settled:
                won_flag = r.get("status") == "won"
                pnl_v    = r.get("pnl") or 0
                table.append({
                    "Tarih":   (r.get("settled_at") or "")[:10],
                    "Tip":     r.get("coupon_type", ""),
                    "Ayak":    r.get("num_legs", 0),
                    "Oran":    f"{(r.get('combined_odds') or 0):.3f}",
                    "Stake":   f"{(r.get('stake') or 0):.0f} TL",
                    "Getiri":  f"{(r.get('actual_return') or 0):.0f} TL",
                    "PnL":     f"{pnl_v:+.0f} TL",
                    "Sonuc":   "KAZANDI" if won_flag else "KAYBETTI",
                })
            import pandas as pd
            df = pd.DataFrame(table)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PnL": st.column_config.TextColumn("PnL"),
                    "Sonuc": st.column_config.TextColumn("Sonuc"),
                }
            )

    # ── Today's signals quick preview (her zaman altta) ─────
    _show_today_preview()


# ============================================================
# PAGE: MATCHES
# ============================================================

# ════════════════════════════════════════════════════════════════
# SUPERPOWER SİNYAL — konfluans + tarihsel kanıt (gerekçeli)
# ════════════════════════════════════════════════════════════════

@st.cache_data(ttl=600, show_spinner=False)
def get_superpower(limit: int = 6):
    try:
        import superpower as _sp
        return _sp.superpower_signals(limit=limit, portfolio_id=PORTFOLIO_ID)
    except Exception:
        return []


def render_superpower() -> None:
    """Gerekçeli SUPERPOWER sinyal bölümü — sinyal sayfasının tepesinde."""
    sigs = get_superpower(6)
    st.markdown(
        '<div class="sec-title" style="margin-top:2px;">'
        '<div class="sec-title-main">⚡ SUPERPOWER SİNYAL</div>'
        '<div class="sec-title-meta">KONFLUANS + TARİHSEL KANIT · GEREKÇELİ</div></div>',
        unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#10182a;border:1px solid #1e2d4a;border-left:3px solid #a78bfa;'
        'border-radius:8px;padding:9px 13px;margin:2px 0 12px 0;color:#94a3b8;font-size:11px;line-height:1.6;">'
        'ℹ️ SUPERPOWER = kör favori DEĞİL. Skor; <b style="color:#e2e8f0;">piyasa güveni (düşük ağırlık)</b> + '
        '<b style="color:#10d48e;">ortogonal teyit</b> (sharp money · H2H · çoklu-pazar — çizgide olmayan bilgi) + '
        '<b style="color:#f5c518;">tarihsel kanıt</b> (bu sinyal tipi geçmişte kazandı mı / +CLV mi?) harmanıdır. '
        'Kanıt zayıfsa skor düşer ve tier "İZLE" kalır — dürüstlük gereği.'
        '</div>', unsafe_allow_html=True)

    if not sigs:
        st.markdown('<div style="color:#475569;font-size:12px;padding:6px 0 14px 0;">'
                    'Şu an değerlendirilecek (başlamamış, oranlı) maç yok — worker yeni program çekince dolar.'
                    '</div>', unsafe_allow_html=True)
        return

    TIER = {
        "SUPERPOWER": ("#f5c518", "⚡ SUPERPOWER", "rgba(245,197,24,0.07)"),
        "GÜÇLÜ":      ("#10d48e", "★ GÜÇLÜ",      "rgba(16,212,142,0.05)"),
        "İZLE":       ("#64748b", "İZLE",          "#0d1628"),
    }
    n_super = sum(1 for x in sigs if x["tier"] == "SUPERPOWER")
    if n_super == 0:
        st.markdown('<div style="color:#f59e0b;font-size:11px;margin-bottom:8px;">'
                    '⚠️ Şu an SUPERPOWER tier sinyal YOK (yeterli konfluans/tarihsel kanıt birikmedi). '
                    'En güçlü adaylar aşağıda — gerçek test ligler Ağustos\'ta açılınca güçlenir.'
                    '</div>', unsafe_allow_html=True)

    for x in sigs:
        col, label, bg = TIER.get(x["tier"], ("#64748b", x["tier"], "#0d1628"))
        ko = (x.get("kickoff") or "")[:16].replace("T", " ")
        verify = _verify_link(f'{x.get("home","?")} vs {x.get("away","?")}', (x.get("kickoff") or "")[:10])
        reasons_html = "".join(
            f'<li style="color:#94a3b8;font-size:11px;line-height:1.55;margin-bottom:2px;">{r}</li>'
            for r in x.get("reasons", []))
        edge = x.get("edge") or 0.0
        edge_c = "#10d48e" if edge > 0 else "#ef4444"
        st.markdown(
            f'<div style="background:{bg};border:1px solid #1a2840;border-left:4px solid {col};'
            f'border-radius:10px;padding:12px 15px;margin-bottom:9px;">'
            # üst satır: tier + skor + maç
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
            f'<div><span style="background:{col};color:#0a0d14;font-size:10px;font-weight:800;'
            f'padding:2px 8px;border-radius:4px;letter-spacing:0.05em;">{label}</span>'
            f'<span style="color:#e2e8f0;font-weight:700;font-size:13px;margin-left:8px;">'
            f'{x.get("home","?")} <span style="color:#475569;">v</span> {x.get("away","?")}</span></div>'
            f'<div style="text-align:right;"><span style="color:{col};font-size:20px;font-weight:900;'
            f'font-family:Consolas,monospace;">{x.get("score",0):.0f}</span>'
            f'<span style="color:#475569;font-size:10px;"> /100</span></div>'
            f'</div>'
            # pick satırı
            f'<div style="font-family:Consolas,monospace;font-size:12px;margin-bottom:6px;">'
            f'<span style="color:#10d48e;font-weight:700;">{x.get("market","")}:{x.get("pick","")}</span> '
            f'<span style="color:#94a3b8;">@{x.get("odds",0):.2f}</span> '
            f'<span style="color:#475569;">· {x.get("league","")} · {ko} UTC · </span>'
            f'<span style="color:{edge_c};">edge %{edge*100:+.1f}</span> '
            f'<span style="color:#64748b;">· {x.get("confirmers",0)} teyit</span></div>'
            # gerekçeler
            f'<div style="background:rgba(10,13,20,0.4);border-radius:6px;padding:7px 10px 7px 6px;margin-bottom:6px;">'
            f'<ul style="margin:0;padding-left:18px;">{reasons_html}</ul></div>'
            f'<div>{verify}</div>'
            f'</div>', unsafe_allow_html=True)

    st.markdown('<div style="color:#475569;font-size:10px;padding:2px 0 14px 0;">'
                '⚠️ Gerekçeli öneri — garanti değil. Skor yüksek olsa bile −EV olabilir; '
                'gerçek doğrulama <b>CLV · Edge Karne</b> sayfasında. 10 dk\'da bir güncellenir.'
                '</div>', unsafe_allow_html=True)


def page_matches(portfolio: dict) -> None:
    now_utc  = datetime.utcnow()
    today_s  = now_utc.date().isoformat()
    cutoff_s = (now_utc.date() + timedelta(days=2)).isoformat()

    matches = _db_rows("""
        SELECT match_id, league_code, home_team, away_team, kickoff_utc,
               closing_1, closing_X, closing_2,
               closing_over25, closing_under25,
               closing_btts_yes, closing_btts_no,
               external_id_iddaa
        FROM matches_v2
        WHERE is_settled=0
          AND kickoff_utc >= ? AND kickoff_utc <= ?
        ORDER BY kickoff_utc
    """, (today_s + "T00:00", cutoff_s + "T23:59"))

    picks = _calc_signals_for_matches(matches)

    # ── Header ─────────────────────────────────────────────
    h_l, h_r = st.columns([3, 1])
    with h_l:
        st.markdown(f"""
        <div class="sec-title">
          <div class="sec-title-main">▸ MATCHES — SIGNALS</div>
          <div class="sec-title-meta">{len(picks)} sinyal ·
            <span style="color:#10d48e;">{sum(1 for p in picks if p['tier']=='GUCLU')} GUCLU</span> ·
            <span style="color:#f59e0b;">{sum(1 for p in picks if p['tier']=='ORTA')} ORTA</span> ·
            <span style="color:#3b82f6;">{sum(1 for p in picks if p['tier']=='ZAYIF')} ZAYIF</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    with h_r:
        if st.button("▶ AUTO-PLAY", type="primary", use_container_width=True):
            _auto_play()

    # ── ⚡ SUPERPOWER SİNYAL (gerekçeli, konfluans + tarihsel) ──
    render_superpower()
    st.markdown('<div style="border-top:1px solid #1a2840;margin:6px 0 14px 0;"></div>',
                unsafe_allow_html=True)

    if not picks:
        st.markdown(
            '<div style="color:#475569;font-size:13px;padding:20px 0;">'
            'Bu aralikta sinyal veren mac bulunamadi.</div>',
            unsafe_allow_html=True,
        )
        return

    TIER_COLORS = {"GUCLU": "#10d48e", "ORTA": "#f59e0b", "ZAYIF": "#3b82f6"}
    TIER_CLASS  = {"GUCLU": "tier-strong", "ORTA": "tier-orta", "ZAYIF": "tier-zayif"}

    # ── Filter tabs ─────────────────────────────────────────
    tab_all, tab_g, tab_o, tab_z = st.tabs(["Tümü", "★★★ GUCLU", "★★☆ ORTA", "★☆☆ ZAYIF"])

    def _render_match_list(subset):
        for p in subset:
            m     = p["match"]
            tc    = TIER_COLORS[p["tier"]]
            bord_l = {"GUCLU": "#10d48e", "ORTA": "#f59e0b", "ZAYIF": "#3b82f6"}[p["tier"]]
            stars = "★" * p["cmc"] + "☆" * (3 - p["cmc"])
            ko    = (m.get("kickoff_utc") or "")[:16].replace("T", " ")
            eid   = m.get("external_id_iddaa") or "?"
            home  = m.get("home_team", "?")
            away  = m.get("away_team", "?")
            league = m.get("league_code", "?")

            try:
                ko_dt   = datetime.fromisoformat((m.get("kickoff_utc") or "").replace("Z", ""))
                delta_h = (ko_dt - now_utc).total_seconds() / 3600
                if delta_h > 2:
                    ko_chip = '<span style="color:#3b82f6;font-size:9px;font-weight:700;">UPCOMING</span>'
                elif delta_h > -2:
                    ko_chip = '<span style="color:#10d48e;font-size:9px;font-weight:700;">&#9679; LIVE</span>'
                else:
                    ko_chip = '<span style="color:#475569;font-size:9px;">FIN</span>'
            except Exception:
                ko_chip = ""

            sig_parts = []
            for s in p["signals"]:
                sc = "#10d48e" if "FAV" in s[0] else "#f59e0b"
                sig_parts.append(
                    f'<span style="color:{sc};font-weight:700;">{s[0]}</span>'
                    f'<span style="color:#64748b;"> @{s[2]:.2f}</span>'
                    f'<span style="color:#94a3b8;"> %{int(s[1]*100)}</span>'
                )
            sig_html = " &nbsp; ".join(sig_parts)

            q = urllib.parse.quote(f"iddaa {home} {away}")
            iddaa_search = f"https://www.google.com/search?q={q}"

            card = (
                f'<div style="background:#0d1628;border:1px solid #1a2840;border-left:4px solid {bord_l};'
                f'border-radius:8px;padding:14px 18px;margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:flex-start;">'
                f'<div>'
                f'<div style="font-size:14px;font-weight:600;color:#e2e8f0;">{home} vs {away}</div>'
                f'<div style="font-size:11px;color:#64748b;font-family:Consolas,monospace;'
                f'text-transform:uppercase;letter-spacing:0.04em;margin-top:3px;display:flex;gap:8px;align-items:center;">'
                f'<span>{league}</span><span>·</span><span>{ko} UTC</span> {ko_chip}'
                f'</div>'
                f'</div>'
                f'<span style="color:{tc};font-size:12px;font-weight:700;font-family:Consolas,monospace;">'
                f'{p["tier"]} {stars}</span>'
                f'</div>'
                f'<div style="margin:8px 0;font-size:12px;font-family:Consolas,monospace;">{sig_html}</div>'
                f'<a href="{iddaa_search}" target="_blank" '
                f'style="color:#3b82f6;font-size:11px;font-family:Consolas,monospace;text-decoration:none;">'
                f'&#x2197; Google arama &nbsp; EID:{eid}</a>'
                f'</div>'
            )
            st.markdown(card, unsafe_allow_html=True)

    with tab_all:
        _render_match_list(picks[:20])
    with tab_g:
        subset = [p for p in picks if p["tier"] == "GUCLU"]
        _render_match_list(subset) if subset else st.info("GUCLU sinyal yok.")
    with tab_o:
        subset = [p for p in picks if p["tier"] == "ORTA"]
        _render_match_list(subset) if subset else st.info("ORTA sinyal yok.")
    with tab_z:
        subset = [p for p in picks if p["tier"] == "ZAYIF"]
        _render_match_list(subset) if subset else st.info("ZAYIF sinyal yok.")


def _auto_play() -> None:
    try:
        from paper_engine import PaperEngine
        engine = PaperEngine(PORTFOLIO_ID)
        with st.spinner("Maclar analiz ediliyor..."):
            coupons = engine.build_session_coupons()
            if coupons:
                ids = engine.place_coupons(coupons)
                st.success(f"{len(ids)} yeni kupon olusturuldu!")
                st.cache_data.clear()
            else:
                st.info("Bu seans icin uygun sinyal bulunamadi.")
    except Exception as e:
        st.error(f"AUTO-PLAY hatasi: {e}")


# ============================================================
# PAGE: CHARTS (Portfolio equity chart)
# ============================================================

def page_charts(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ CHARTS — EQUITY & DRAWDOWN</div>
    </div>
    """, unsafe_allow_html=True)

    eq_rows = _db_rows("""
        SELECT settled_at, pnl, coupon_type, status, combined_odds, stake
        FROM paper_coupons
        WHERE portfolio_id=? AND status != 'open'
        ORDER BY settled_at
    """, (PORTFOLIO_ID,))

    if not eq_rows:
        st.info("Henuz kapatilmis kupon yok.")
        return

    br_vals, dd_vals, ev_dates, ev_texts = [INITIAL_BANKROLL], [0.0], ["Baslangic"], [""]
    peak_br = INITIAL_BANKROLL
    running_br = INITIAL_BANKROLL

    for r in eq_rows:
        pnl_r = r.get("pnl") or 0.0
        running_br += pnl_r
        br_vals.append(running_br)
        peak_br = max(peak_br, running_br)
        dd_pct = ((running_br - peak_br) / peak_br * 100) if peak_br > 0 else 0.0
        dd_vals.append(round(dd_pct, 2))
        lbl = (r.get("settled_at") or "")[:10]
        ev_dates.append(lbl)
        status_icon = "WIN" if r.get("status") == "won" else "LOSS"
        ev_texts.append(
            f"{r.get('coupon_type','')} {status_icon}<br>"
            f"PnL: {pnl_r:+.0f} TL | Oran: {r.get('combined_odds',1):.2f}"
        )

    line_color = "#10d48e" if running_br >= INITIAL_BANKROLL else "#ef4444"
    fill_color = (
        "rgba(16,212,142,0.08)" if running_br >= INITIAL_BANKROLL
        else "rgba(239,68,68,0.08)"
    )

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.70, 0.30],
        shared_xaxes=True,
        vertical_spacing=0.04,
        subplot_titles=("Portfolio Degeri (TL)", "Drawdown (%)"),
    )

    fig.add_trace(go.Scatter(
        x=ev_dates, y=br_vals,
        mode="lines+markers",
        name="Bankroll",
        line=dict(color=line_color, width=2.5),
        fill="tozeroy", fillcolor=fill_color,
        text=ev_texts,
        hovertemplate="%{x}<br>%{y:,.0f} TL<br>%{text}<extra></extra>",
        marker=dict(
            size=7,
            color=["#10d48e" if v >= INITIAL_BANKROLL else "#ef4444" for v in br_vals],
        ),
    ), row=1, col=1)

    fig.add_hline(
        y=INITIAL_BANKROLL, line_dash="dot", line_color="#334155",
        annotation_text=f"Baslangic {INITIAL_BANKROLL:,.0f} TL",
        annotation_position="bottom right",
        annotation_font_color="#475569",
        row=1, col=1,
    )

    if peak_br > INITIAL_BANKROLL:
        fig.add_hline(
            y=peak_br, line_dash="dash", line_color="#10d48e", line_width=1,
            annotation_text=f"Zirve {peak_br:,.0f} TL",
            annotation_position="top right",
            annotation_font_color="#10d48e",
            row=1, col=1,
        )

    dd_colors = [
        "rgba(239,68,68,0.5)" if d < 0 else "rgba(16,212,142,0.3)"
        for d in dd_vals
    ]
    fig.add_trace(go.Bar(
        x=ev_dates, y=dd_vals,
        name="Drawdown %",
        marker_color=dd_colors,
        hovertemplate="%{x}<br>DD: %{y:.1f}%<extra></extra>",
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="#0a0d14", plot_bgcolor="#0a0d14",
        font=dict(color="#94a3b8", family="Consolas, Courier New"),
        height=480,
        showlegend=False,
        margin=dict(l=10, r=10, t=50, b=10),
        xaxis=dict(showgrid=False, color="#475569"),
        xaxis2=dict(showgrid=False, color="#475569"),
        yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#94a3b8"),
        yaxis2=dict(showgrid=True, gridcolor="#1e293b", color="#94a3b8"),
    )
    fig.update_annotations(font_size=11)
    st.plotly_chart(fig, use_container_width=True)

    # ── Stats ────────────────────────────────────────────────
    total_c = len(eq_rows)
    won_c = sum(1 for r in eq_rows if r.get("status") == "won")
    total_pnl = running_br - INITIAL_BANKROLL
    total_stk = sum(r.get("stake") or 0 for r in eq_rows)
    avg_odds = (
        sum(r.get("combined_odds") or 1 for r in eq_rows) / total_c if total_c else 1
    )
    best_win = max((r.get("pnl") or 0 for r in eq_rows), default=0)
    yield_pct = (total_pnl / total_stk * 100) if total_stk > 0 else 0.0

    # Streak
    streak, streak_type = 0, ""
    for r in reversed(eq_rows):
        st_r = r.get("status", "")
        if st_r == "won":
            if streak_type in ("", "W"):
                streak += 1; streak_type = "W"
            else:
                break
        elif st_r == "lost":
            if streak_type in ("", "L"):
                streak += 1; streak_type = "L"
            else:
                break

    stat_data = [
        ("Kapatilan", str(total_c), "kupon"),
        ("Kazanilan", f"{won_c}/{total_c - won_c}", "W/L"),
        ("Win Rate", f"%{won_c/total_c*100:.0f}" if total_c else "%0", ""),
        ("Ort Oran", f"{avg_odds:.2f}", "x"),
        ("Yield", f"{yield_pct:+.1f}%", ""),
        ("En Iyi", f"+{best_win:.0f} TL", ""),
        ("Seri", f"{streak} {streak_type}" if streak_type else "—", ""),
    ]

    s_cols = st.columns(len(stat_data))
    for col, (label, value, unit) in zip(s_cols, stat_data):
        with col:
            val_color = (
                "#10d48e" if ("+" in value and value != "—")
                else ("#ef4444" if "-" in value else "#e2e8f0")
            )
            st.markdown(
                f"<div style='background:#111827;border:1px solid #1e293b;"
                f"border-radius:6px;padding:10px 12px;text-align:center;'>"
                f"<div style='color:#64748b;font-size:9px;text-transform:uppercase;"
                f"letter-spacing:1px;'>{label}</div>"
                f"<div style='color:{val_color};font-size:17px;font-weight:700;"
                f"font-family:Consolas,monospace;margin:4px 0;'>{value}</div>"
                f"<div style='color:#475569;font-size:10px;'>{unit}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )


# ============================================================
# PAGE: POSITIONS
# ============================================================

def page_positions(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ POSITIONS — ALL COUPONS</div>
    </div>
    """, unsafe_allow_html=True)

    rows = _db_rows("""
        SELECT coupon_type, session_date, combined_odds, stake,
               actual_return, pnl, status
        FROM paper_coupons
        WHERE portfolio_id=?
        ORDER BY created_at DESC LIMIT 50
    """, (PORTFOLIO_ID,))

    if not rows:
        st.info("Henuz kupon yok.")
        return

    table = []
    for r in rows:
        pnl_v = r.get("pnl") or 0.0
        table.append({
            "Tarih": r.get("session_date", ""),
            "Tip":   r.get("coupon_type", ""),
            "Oran":  f"{(r.get('combined_odds') or 0):.3f}",
            "Stake": f"{(r.get('stake') or 0):.0f} TL",
            "Getiri": f"{(r.get('actual_return') or 0):.0f} TL",
            "PnL":   f"{pnl_v:+.0f} TL",
            "Sonuc": (r.get("status") or "").upper(),
        })
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


# ============================================================
# PAGE: ORDERS
# ============================================================

def page_orders(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ ORDERS — BET HISTORY</div>
    </div>
    """, unsafe_allow_html=True)

    bets = _db_rows("""
        SELECT league, home_team, away_team, market, pick, odds,
               model_prob, edge, signal_score, signal_name,
               status, result, settled_at
        FROM paper_bets
        WHERE portfolio_id=?
        ORDER BY settled_at DESC NULLS LAST LIMIT 80
    """, (PORTFOLIO_ID,))

    if not bets:
        st.info("Henuz bahis yok.")
        return

    table = []
    for b in bets:
        mp = (b.get("model_prob") or 0) * 100
        edge = (b.get("edge") or 0) * 100
        table.append({
            "Lig":    b.get("league", ""),
            "Mac":    f"{b.get('home_team','?')} vs {b.get('away_team','?')}",
            "Market": b.get("market", ""),
            "Pick":   b.get("pick", ""),
            "Oran":   f"{(b.get('odds') or 0):.2f}",
            "Prob%":  f"{mp:.0f}%",
            "Edge%":  f"{edge:+.1f}%",
            "Sinyal": b.get("signal_name", ""),
            "Durum":  (b.get("status") or "").upper(),
            "Sonuc":  b.get("result") or "—",
        })
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)


# ============================================================
# PAGE: RISK
# ============================================================

def page_risk(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ RISK — BANKROLL & LIMITS</div>
    </div>
    """, unsafe_allow_html=True)

    bankroll = portfolio.get("current_bankroll") or INITIAL_BANKROLL
    pnl = portfolio.get("pnl") or 0.0
    dd_pct = ((bankroll - (portfolio.get("peak_bankroll") or bankroll)) /
              (portfolio.get("peak_bankroll") or bankroll) * 100)
    yield_pct = portfolio.get("yield_pct") or 0.0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Bankroll", f"{bankroll:,.0f} TL", delta=f"{pnl:+,.0f} TL")
    with c2:
        st.metric("Yield", f"{yield_pct:+.1f}%")
    with c3:
        st.metric("Drawdown", f"{dd_pct:.1f}%")
    with c4:
        st.metric("Acik Kupon", portfolio.get("open_coupons", 0))

    st.markdown("---")

    risk_table = pd.DataFrame([
        {"Esik": "Normal",  "Durum": "Yield > -15%",  "Aksiyon": "Standart stake (1x)"},
        {"Esik": "Uyari",   "Durum": "Yield -15%-20%", "Aksiyon": "Stake yari (0.5x)"},
        {"Esik": "Kritik",  "Durum": "Yield < -25%",  "Aksiyon": "1 hafta PAS"},
    ])
    st.dataframe(risk_table, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown(
        "**Aktif Eşikler (min 2 ayak — iddaa.com tekli yok):** "
        "K2_FAVORI stake=%2.5 bankroll · K2_VALUE=%2 · K2_KARISIK=%2 · K3_KOMBO=%1.5"
    )


# ============================================================
# PAGE: JOURNAL
# ============================================================

def _verify_link(match_p: str, date_str: str = "") -> str:
    """Bir maç için bağımsız skor-doğrulama linki (Google skor kartı).
    Skoru iddaa'dan çekiyoruz; bu link kullanıcının sonucu 3. taraftan
    bağımsız teyit etmesi için ('tıkla, sonucu gör')."""
    from urllib.parse import quote
    teams = re.sub(r"\s*\(.*?\)\s*", " ", (match_p or "")).strip()
    q_teams = teams.replace(" vs ", " ").replace(" VS ", " ").replace(" v ", " ")
    query = f"{q_teams} {date_str} maç sonucu".strip()
    url = "https://www.google.com/search?q=" + quote(query)
    return (
        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
        f'style="color:#3b82f6;font-size:10px;text-decoration:none;'
        f'font-family:Consolas,monospace;display:inline-flex;align-items:center;gap:3px;">'
        f'🔗 sonucu bağımsız gör</a>'
    )


def page_journal(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ JOURNAL — MODEL NOTES</div>
      <div class="sec-title-meta">SKOR KAYNAĞI: İDDAA · 🔗 İLE BAĞIMSIZ TEYİT (GOOGLE)</div>
    </div>
    """, unsafe_allow_html=True)

    entries = _db_rows("""
        SELECT entry_date, entry_type, title, content,
               signal_name, market, pick, odds, actual_result, pnl,
               tags, model_action
        FROM paper_journal
        WHERE portfolio_id=?
        ORDER BY created_at DESC LIMIT 20
    """, (PORTFOLIO_ID,))

    TYPE_COLORS = {
        "PICK":               "#3b82f6",
        "RESULT":             "#10d48e",
        "LESSON":             "#f59e0b",
        "THRESHOLD_UPDATE":   "#a78bfa",
        "SESSION_REVIEW":     "#64748b",
    }

    if entries:
        for j in entries:
            etype     = j.get("entry_type", "?")
            edate     = j.get("entry_date", "")
            etitle    = j.get("title", "")
            econt     = j.get("content", "")
            pnl_j     = j.get("pnl") or 0
            model_act = j.get("model_action") or ""

            # ── RESULT entries: Meridian-style settlement card with chart ──
            if etype == "RESULT":
                won       = pnl_j >= 0
                tc        = "#10d48e" if won else "#ef4444"
                badge_bg  = "rgba(16,212,142,0.08)" if won else "rgba(239,68,68,0.08)"
                badge_txt = "✓ KAZANDI" if won else "✗ KAYBETTİ"

                # Parse stake from content: "Stake: 150 TL"
                m_stake = re.search(r"Stake:\s*(\d+(?:\.\d+)?)\s*TL", econt)
                stake_val = float(m_stake.group(1)) if m_stake else abs(pnl_j)

                svg_settle = _svg_settlement_chart(stake_val, pnl_j, edate)

                # ── Parse content lines ──
                raw_lines   = [l.strip() for l in econt.split("\n") if l.strip()]
                header_line = raw_lines[0] if raw_lines else ""
                trade_note  = ""
                bet_details = ""

                for bl in raw_lines[1:]:
                    # Trade Notu satırı ayrıştır
                    if bl.startswith("Trade Notu:"):
                        trade_note = bl[len("Trade Notu:"):].strip()
                        continue

                    # Bet satırı: parse edip renkli chiplerle göster
                    # Format: "Team A vs Team B | MKT PICK @odds | Model:%X Piyasa:%Y Edge:Z% Güven:W | Skor:S | OUTCOME"
                    parts   = [p.strip() for p in bl.split("|")]
                    match_p = parts[0] if len(parts) > 0 else bl
                    mkt_p   = parts[1] if len(parts) > 1 else ""
                    sig_p   = parts[2] if len(parts) > 2 else ""
                    skor_p  = parts[3] if len(parts) > 3 else ""
                    oc_p    = parts[4] if len(parts) > 4 else ""

                    # Outcome chip coloring
                    oc_clean = oc_p.strip().upper()
                    if oc_clean == "WON":
                        oc_bg, oc_cl = "rgba(16,212,142,0.15)", "#10d48e"
                    elif oc_clean == "LOST":
                        oc_bg, oc_cl = "rgba(239,68,68,0.12)", "#ef4444"
                    else:
                        oc_bg, oc_cl = "rgba(100,116,139,0.1)", "#64748b"

                    # Parse Model/Edge/Güven from sig_p
                    mp_match  = re.search(r"Model:%(\d+(?:\.\d+)?)", sig_p)
                    ip_match  = re.search(r"Piyasa:%(\d+(?:\.\d+)?)", sig_p)
                    edg_match = re.search(r"Edge:([+-]?\d+(?:\.\d+)?)%", sig_p)
                    sc_match  = re.search(r"Güven:(\d+(?:\.\d+)?)", sig_p)

                    mp_pct   = float(mp_match.group(1))  if mp_match  else 0.0
                    ip_pct   = float(ip_match.group(1))  if ip_match  else 0.0
                    edge_val = float(edg_match.group(1)) if edg_match else 0.0
                    sc_val   = float(sc_match.group(1))  if sc_match  else 0.0

                    mp_clr   = "#10d48e" if mp_pct >= 65 else "#f59e0b" if mp_pct >= 58 else "#64748b"
                    edge_clr = "#10d48e" if edge_val >= 0 else "#ef4444"
                    edge_sgn = "+" if edge_val >= 0 else ""
                    sc_clr   = "#10d48e" if sc_val > 0.70 else "#f59e0b" if sc_val > 0.45 else "#64748b"

                    bet_details += (
                        f'<div style="background:rgba(10,13,20,0.5);border:1px solid #1a2840;'
                        f'border-radius:5px;padding:7px 10px;margin-bottom:5px;">'

                        # Row 1: match + market + skor + outcome
                        f'<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">'
                        f'<span style="color:#e2e8f0;font-weight:600;font-size:11px;'
                        f'font-family:Consolas,monospace;flex:1;">{match_p}</span>'
                        f'<span style="color:#f59e0b;font-size:11px;font-family:Consolas,monospace;">{mkt_p}</span>'
                        f'<span style="color:#94a3b8;font-size:11px;font-family:Consolas,monospace;">{skor_p}</span>'
                        f'<span style="background:{oc_bg};color:{oc_cl};border-radius:3px;'
                        f'padding:1px 7px;font-size:10px;font-weight:700;'
                        f'letter-spacing:0.05em;">{oc_clean}</span>'
                        f'</div>'

                        # Row 2: model signal chips (only if parsed)
                        + (
                            f'<div style="display:flex;gap:12px;flex-wrap:wrap;">'
                            f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">'
                            f'Model <span style="color:{mp_clr};font-weight:700;">%{mp_pct:.0f}</span></span>'
                            f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">'
                            f'Piyasa <span style="color:#64748b;">%{ip_pct:.0f}</span></span>'
                            f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">'
                            f'Edge <span style="color:{edge_clr};font-weight:700;">'
                            f'{edge_sgn}{edge_val:.1f}%</span></span>'
                            f'<span style="font-size:10px;font-family:Consolas,monospace;color:#475569;">'
                            f'Güven <span style="color:{sc_clr};">{sc_val:.2f}</span></span>'
                            f'</div>'
                            if sig_p else ""
                        )
                        # Row 3: bağımsız skor doğrulama linki
                        + f'<div style="margin-top:6px;">{_verify_link(match_p, edate)}</div>'
                        + f'</div>'  # end bet row
                    )

                # ── Trade Notu ──
                trade_note_html = ""
                if trade_note:
                    trade_note_html = (
                        f'<div style="background:rgba(59,130,246,0.06);border:1px solid rgba(59,130,246,0.15);'
                        f'border-left:3px solid #3b82f6;border-radius:4px;'
                        f'padding:7px 10px;margin-top:8px;">'
                        f'<span style="color:#3b82f6;font-size:9px;font-weight:700;'
                        f'text-transform:uppercase;letter-spacing:0.08em;display:block;margin-bottom:3px;">✎ TRADE NOTU</span>'
                        f'<span style="color:#94a3b8;font-size:11px;font-style:italic;'
                        f'line-height:1.5;">{trade_note}</span>'
                        f'</div>'
                    )

                entry_html = (
                    f'<div style="background:{badge_bg};border:1px solid #1a2840;'
                    f'border-left:4px solid {tc};border-radius:8px;'
                    f'padding:14px 16px;margin-bottom:12px;">'

                    # header row: badge + date
                    f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">'
                    f'<span style="background:{tc};color:#0a0d14;font-size:10px;font-weight:800;'
                    f'text-transform:uppercase;letter-spacing:0.08em;padding:2px 8px;border-radius:4px;">'
                    f'{badge_txt}</span>'
                    f'<span style="color:#475569;font-size:11px;font-family:Consolas,monospace;">{edate}</span>'
                    f'</div>'

                    # title
                    f'<div style="color:#e2e8f0;font-weight:700;font-size:14px;margin-bottom:10px;">{etitle}</div>'

                    # body: LEFT=details+chart RIGHT removed (chart goes below header for clarity)
                    f'<div style="display:flex;gap:14px;align-items:flex-start;">'

                    # LEFT: coupon header summary + enriched bet rows + trade note
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="color:#64748b;font-size:11px;font-family:Consolas,monospace;'
                    f'margin-bottom:8px;">{header_line}</div>'
                    f'{bet_details}'
                    f'{trade_note_html}'
                    + (f'<div style="color:#475569;font-size:10px;font-family:Consolas,monospace;margin-top:6px;">'
                       f'→ {model_act}</div>' if model_act else "")
                    + f'</div>'  # end LEFT

                    # RIGHT: settlement chart
                    f'<div style="flex-shrink:0;border-left:1px solid #1a2840;padding-left:14px;">'
                    + svg_settle
                    + f'</div>'   # end RIGHT
                    f'</div>'     # end body flex
                    f'</div>'     # end card
                )

            else:
                # ── Other entry types: simple clean card ──
                tc = TYPE_COLORS.get(etype, "#64748b")
                pnl_str   = f" · PnL: {pnl_j:+.0f} TL" if pnl_j else ""
                act_str   = f" → {model_act}" if model_act else ""
                entry_html = (
                    f'<div style="background:#0b1120;border-left:3px solid {tc};'
                    f'border-radius:4px;padding:10px 14px;margin-bottom:8px;">'
                    f'<div style="display:flex;justify-content:space-between;margin-bottom:4px;">'
                    f'<span style="color:{tc};font-size:10px;font-weight:700;'
                    f'text-transform:uppercase;letter-spacing:0.08em;">{etype}</span>'
                    f'<span style="color:#475569;font-size:11px;font-family:Consolas,monospace;">{edate}</span>'
                    f'</div>'
                    f'<div style="color:#e2e8f0;font-weight:600;font-size:13px;margin-bottom:3px;">{etitle}</div>'
                    f'<div style="color:#94a3b8;font-size:12px;line-height:1.5;">{econt}</div>'
                    f'<div style="color:#475569;font-size:11px;margin-top:4px;'
                    f'font-family:Consolas,monospace;">{pnl_str}{act_str}</div>'
                    f'</div>'
                )

            st.markdown(entry_html, unsafe_allow_html=True)
    else:
        st.info("Journal henuz bos. Kuponlar kapandikca otomatik giris olusur.")

    st.markdown("---")

    with st.expander("+ Manuel Journal Girisi Ekle"):
        j_type = st.selectbox(
            "Giris Turu",
            ["LESSON", "SESSION_REVIEW", "THRESHOLD_UPDATE", "PICK", "RESULT"],
        )
        j_title = st.text_input("Baslik")
        j_content = st.text_area("Icerik")
        j_action = st.text_input(
            "Model Aksiyonu (opsiyonel)",
            placeholder="LOWER_THRESHOLD / RAISE_THRESHOLD / KEEP",
        )
        if st.button("Journal'a Ekle", type="primary"):
            conn = db_connect()
            conn.execute(
                """INSERT INTO paper_journal
                   (journal_id, portfolio_id, entry_date, entry_type,
                    title, content, model_action, created_at)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4()),
                    PORTFOLIO_ID,
                    datetime.utcnow().date().isoformat(),
                    j_type,
                    j_title,
                    j_content,
                    j_action or None,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            st.success("Journal girisi eklendi!")
            st.cache_data.clear()
            st.rerun()


# ============================================================
# PAGE: SETTINGS
# ============================================================

def page_settings(portfolio: dict) -> None:
    st.markdown("""
    <div class="sec-title">
      <div class="sec-title-main">▸ SETTINGS</div>
    </div>
    """, unsafe_allow_html=True)

    import db as _dbcore
    _db_backend = _dbcore.backend()
    _db_label = "PostgreSQL (Railway)" if _db_backend == "postgres" else f"SQLite ({DB_PATH})"
    st.markdown(f"""
    | Alan | Deger |
    |---|---|
    | Portfolio ID | `{PORTFOLIO_ID}` |
    | Veritabanı | `{_db_label}` |
    | Initial Bankroll | `{INITIAL_BANKROLL:,.0f} TL` |
    | Strategy | `{portfolio.get('strategy_version', 'v1')}` |
    | Status | `{portfolio.get('status', '—')}` |
    | Created | `{portfolio.get('created_at', '—')}` |
    """)

    st.markdown("---")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✓ Settle Open Coupons", use_container_width=True):
            try:
                from paper_engine import PaperEngine
                engine = PaperEngine(PORTFOLIO_ID)
                result = engine.settle_coupons()
                settled = result.get("settled", 0)
                pnl_s = result.get("pnl", 0.0)
                if settled > 0:
                    st.success(
                        f"{settled} kupon kapatildi | PnL: {pnl_s:+.0f} TL"
                    )
                    st.cache_data.clear()
                else:
                    st.info("Kapatilacak bitmis mac bulunamadi.")
            except Exception as e:
                st.error(f"Settle hatasi: {e}")

    with col_b:
        if st.button("↻ Cache Temizle", use_container_width=True):
            st.cache_data.clear()
            st.success("Cache temizlendi.")
            st.rerun()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    portfolio = load_portfolio()

    page = render_sidebar()
    render_status_bar(portfolio)

    PAGE_MAP = {
        "Overview":  page_overview,
        "Matches":   page_matches,
        "Charts":    page_charts,
        "Positions": page_positions,
        "Orders":    page_orders,
        "Risk":      page_risk,
        "Journal":   page_journal,
        "Settings":  page_settings,
    }

    func = PAGE_MAP.get(page, page_overview)
    func(portfolio)


if __name__ == "__main__":
    main()
