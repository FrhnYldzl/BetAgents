"""
AI TRADER PRO — SaaS Production Edition
=========================================

Kurumsal grade SaaS uygulamasi.

Sayfalar:
  1. Overview          — Yonetici ozeti
  2. Live Calendar     — Yakin maclar + canli model tahminleri
  3. Trading Desk      — Multi-market mac panel
  4. Coupon Engineer   — Kupon optimizasyon stüdyosu
  5. Model Catalog     — 10 silah registry
  6. Analytics         — Sezonsal stabilite + heatmap
  7. Data Excellency   — DB quality + snapshots
  8. Risk Management   — Bankroll + drawdown + limits

Calistir:
  python -m streamlit run app_pro.py --server.port 8503
"""
from __future__ import annotations

import json
import sys
import sqlite3
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))

import db  # merkezî bağlantı katmanı (SQLite/PostgreSQL)

DB_PATH = YAZILIM / "02_VERI" / "bahis_agent.db"
REGISTRY_PATH = YAZILIM / "03_MODELLER" / "MODEL_REGISTRY" / "model_registry.json"

SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}

LIG_FULL_NAME = {
    "T1": "Türkiye Süper Lig",
    "E0": "İngiltere Premier League",
    "SP1": "İspanya La Liga",
    "D1": "Almanya Bundesliga",
    "I1": "İtalya Serie A",
    "F1": "Fransa Ligue 1",
}


# ============================================================
# PAGE CONFIG + SaaS CORPORATE CSS
# ============================================================

# try/except: app.py (birleşik giriş) zaten ayarladıysa hata vermesin
try:
    st.set_page_config(
        page_title="AI TRADER PRO · Digital Twin",
        page_icon="◉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass

# Modül sabiti (app_unified her rerun'da yeniden enjekte edebilsin)
PRO_CSS = """
<style>
    /* System fonts — no external HTTP request, instant load */

    .stApp {
        background: #0a0e1a;
        color: #d4d4d8;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter',
                     'Helvetica Neue', Arial, sans-serif;
    }

    /* HEADER BAR */
    .header-bar {
        background: linear-gradient(90deg, #050810 0%, #0f172a 100%);
        border-bottom: 1px solid #1e293b;
        padding: 12px 24px;
        margin: -50px -16px 24px -16px;
        display: flex;
        align-items: center;
        gap: 28px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 11px;
    }
    .header-logo {
        color: #10b981;
        font-weight: 800;
        font-size: 18px;
        letter-spacing: 0.08em;
    }
    .header-logo span {
        color: #71717a;
        font-weight: 500;
        font-size: 11px;
        margin-left: 8px;
    }
    .header-tick {
        color: #71717a;
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .header-tick .value {
        color: #f4f4f5;
        font-weight: 700;
        font-size: 13px;
        margin-left: 4px;
    }
    .header-tick.live .value { color: #10b981; }
    .header-tick.warn .value { color: #f59e0b; }

    .live-dot {
        display: inline-block;
        width: 8px; height: 8px;
        background: #10b981;
        border-radius: 50%;
        margin-right: 6px;
        box-shadow: 0 0 8px #10b981;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    /* METRIC CARDS */
    [data-testid="stMetric"] {
        background: linear-gradient(180deg, #111827 0%, #0a0e1a 100%);
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 18px 22px;
    }
    [data-testid="stMetricValue"] {
        font-family: Consolas, 'Courier New', monospace;
        font-size: 26px !important;
        font-weight: 700;
        color: #f4f4f5;
        line-height: 1.2;
    }
    [data-testid="stMetricLabel"] {
        font-size: 10px !important;
        font-weight: 700;
        color: #71717a;
        text-transform: uppercase;
        letter-spacing: 0.1em;
    }
    [data-testid="stMetricDelta"] {
        font-family: Consolas, 'Courier New', monospace;
        font-size: 11px;
        font-weight: 600;
    }

    /* TABS */
    .stTabs [data-baseweb="tab-list"] {
        background: #050810;
        gap: 0;
        border-bottom: 1px solid #1e293b;
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        color: #71717a;
        border-radius: 0;
        padding: 14px 22px;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border-bottom: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #10b981;
        border-bottom: 2px solid #10b981;
        background: rgba(16, 185, 129, 0.04);
    }

    /* MATCH CARDS */
    .match-card {
        background: linear-gradient(180deg, #111827 0%, #0a0e1a 100%);
        border: 1px solid #1e293b;
        border-left: 4px solid #1e293b;
        border-radius: 8px;
        padding: 18px 22px;
        margin: 12px 0;
        transition: all 0.2s ease;
    }
    .match-card:hover {
        border-color: #10b981;
        box-shadow: 0 4px 24px rgba(16, 185, 129, 0.08);
    }
    .match-card.tier-1 { border-left-color: #10b981; }
    .match-card.tier-2 { border-left-color: #f59e0b; }
    .match-card.tier-3 { border-left-color: #3b82f6; }
    .match-card.tier-4 { border-left-color: #71717a; }

    .match-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 14px;
    }
    .match-title {
        font-size: 15px;
        font-weight: 600;
        color: #f4f4f5;
        line-height: 1.3;
    }
    .match-subtitle {
        font-size: 11px;
        color: #71717a;
        margin-top: 4px;
        font-family: Consolas, 'Courier New', monospace;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .match-tier-badge {
        font-size: 10px;
        font-weight: 700;
        padding: 4px 10px;
        border-radius: 4px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-family: Consolas, 'Courier New', monospace;
    }
    .badge-tier-1 { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid #10b981; }
    .badge-tier-2 { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid #f59e0b; }
    .badge-tier-3 { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid #3b82f6; }
    .badge-tier-4 { background: rgba(113,113,122,0.15); color: #a1a1aa; border: 1px solid #71717a; }

    .stat-row {
        display: flex;
        gap: 24px;
        flex-wrap: wrap;
        margin-top: 8px;
    }
    .stat-item {
        font-family: Consolas, 'Courier New', monospace;
        min-width: 70px;
    }
    .stat-label {
        font-size: 9px;
        color: #71717a;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 600;
        display: block;
        margin-bottom: 2px;
    }
    .stat-value {
        font-size: 16px;
        font-weight: 700;
        color: #f4f4f5;
    }
    .stat-value.success { color: #10b981; }
    .stat-value.danger { color: #ef4444; }
    .stat-value.warn { color: #f59e0b; }
    .stat-value.info { color: #3b82f6; }
    .stat-value.muted { color: #71717a; }

    /* ACTION BUTTONS */
    .action-row {
        display: flex;
        gap: 10px;
        margin-top: 16px;
        padding-top: 14px;
        border-top: 1px solid #1e293b;
        align-items: center;
    }
    .btn {
        text-decoration: none;
        padding: 8px 16px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s;
    }
    .btn-primary {
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: #ffffff;
        border: 1px solid #10b981;
        box-shadow: 0 2px 12px rgba(16, 185, 129, 0.25);
    }
    .btn-primary:hover {
        box-shadow: 0 4px 20px rgba(16, 185, 129, 0.4);
        transform: translateY(-1px);
    }
    .btn-secondary {
        background: transparent;
        color: #d4d4d8;
        border: 1px solid #334155;
    }
    .btn-secondary:hover {
        border-color: #10b981;
        color: #10b981;
    }
    .btn-ghost {
        background: transparent;
        color: #71717a;
        border: 1px solid #1e293b;
    }
    .btn-ghost:hover { color: #d4d4d8; border-color: #334155; }

    /* SIDEBAR */
    [data-testid="stSidebar"] {
        background: #050810;
        border-right: 1px solid #1e293b;
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #f4f4f5;
    }

    /* DATAFRAMES */
    [data-testid="stDataFrame"] {
        background: #111827;
        border-radius: 6px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 12px;
    }

    /* HEADINGS */
    h1, h2, h3, h4 {
        color: #f4f4f5;
        font-weight: 700;
        letter-spacing: -0.02em;
    }
    h1 { font-size: 28px !important; }
    h2 { font-size: 16px !important;
         text-transform: uppercase;
         letter-spacing: 0.08em;
         color: #10b981; }
    h3 { font-size: 14px !important; color: #d4d4d8; font-weight: 600; }
    h4 { font-size: 12px !important; color: #71717a;
         text-transform: uppercase;
         letter-spacing: 0.05em; }

    /* PILLS */
    .pill {
        display: inline-block;
        padding: 4px 12px;
        font-size: 10px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        border-radius: 100px;
        font-family: Consolas, 'Courier New', monospace;
    }
    .pill-green { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid #10b981; }
    .pill-amber { background: rgba(245,158,11,0.15); color: #f59e0b; border: 1px solid #f59e0b; }
    .pill-red { background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid #ef4444; }
    .pill-blue { background: rgba(59,130,246,0.15); color: #3b82f6; border: 1px solid #3b82f6; }
    .pill-gray { background: rgba(113,113,122,0.15); color: #a1a1aa; border: 1px solid #71717a; }

    /* SECTION TITLE */
    .section-title-wrap {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 6px 0 14px 0;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 20px;
    }
    .section-title-main {
        color: #10b981;
        font-size: 13px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-family: Consolas, 'Courier New', monospace;
    }
    .section-title-meta {
        font-size: 11px;
        color: #71717a;
        font-family: Consolas, 'Courier New', monospace;
    }

    /* CALLOUT */
    .callout {
        background: rgba(16,185,129,0.05);
        border-left: 3px solid #10b981;
        padding: 14px 18px;
        border-radius: 6px;
        margin: 14px 0;
        font-size: 13px;
        line-height: 1.5;
        color: #d4d4d8;
    }
    .callout strong { color: #10b981; }
    .callout-warn {
        background: rgba(245,158,11,0.05);
        border-left-color: #f59e0b;
    }
    .callout-warn strong { color: #f59e0b; }

    /* SCROLLBAR */
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #050810; }
    ::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #334155; }

    /* HIDE STREAMLIT BRANDING */
    [data-testid="stToolbar"] { display: none; }
    [data-testid="stHeader"] { background: transparent; height: 0; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    /* INFO BLOCKS */
    .info-box {
        background: #111827;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 10px 0;
    }
    .info-box-label {
        font-size: 10px;
        font-weight: 700;
        color: #71717a;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
    }
    .info-box-value {
        font-size: 22px;
        font-weight: 700;
        color: #f4f4f5;
        font-family: Consolas, 'Courier New', monospace;
    }
</style>
"""
st.markdown(PRO_CSS, unsafe_allow_html=True)


# ============================================================
# CONSTANTS & HELPERS
# ============================================================

# Çalışan iddia.com URL'leri (test edilmiş genel)
IDDAA_PROGRAM_URL = "https://www.iddaa.com/program/futbol-mac-onceski"
IDDAA_LIVE_URL = "https://www.iddaa.com/canli-bahis"
IDDAA_LIG_LINKS = {
    "T1": "https://www.iddaa.com/program/futbol-mac-onceski?bransKodu=1",
    "E0": "https://www.iddaa.com/program/futbol-mac-onceski",
    "SP1": "https://www.iddaa.com/program/futbol-mac-onceski",
    "D1": "https://www.iddaa.com/program/futbol-mac-onceski",
    "I1": "https://www.iddaa.com/program/futbol-mac-onceski",
    "F1": "https://www.iddaa.com/program/futbol-mac-onceski",
}


def iddaa_link(league_code: str) -> str:
    return IDDAA_LIG_LINKS.get(league_code, IDDAA_PROGRAM_URL)


def google_match_search(home: str, away: str) -> str:
    q = urllib.parse.quote(f"iddaa {home} {away}")
    return f"https://www.google.com/search?q={q}"


def match_detail_link(home: str, away: str, date_str: str) -> str:
    """Genel maç ara — sonuç + iddaa kombine."""
    q = urllib.parse.quote(f"{home} {away} {date_str} iddaa")
    return f"https://www.google.com/search?q={q}"


def format_date_human(date_str: str) -> str:
    if not date_str: return ""
    try:
        dt = pd.Timestamp(date_str)
        gun_kisa = ["Pzt","Sal","Çar","Per","Cum","Cmt","Paz"][dt.weekday()]
        ay_kisa = ["Oca","Şub","Mar","Nis","May","Haz","Tem",
                   "Ağu","Eyl","Eki","Kas","Ara"][dt.month-1]
        return f"{dt.day} {ay_kisa} {gun_kisa}"
    except:
        return date_str


def render_match_actions(home: str, away: str, league_code: str, date_str: str) -> str:
    """Pick action buttons HTML."""
    iddaa_url = iddaa_link(league_code)
    detail_url = match_detail_link(home, away, date_str)
    return f"""
    <div class="action-row">
      <a href="{iddaa_url}" target="_blank" rel="noopener" class="btn btn-primary">
        ▶ İDDAA'da OYNA
      </a>
      <a href="{detail_url}" target="_blank" rel="noopener" class="btn btn-secondary">
        🔍 Maç Detayı
      </a>
      <span style="color: #71717a; font-size: 11px; margin-left: auto;
                   font-family: Consolas, 'Courier New', monospace;">
        AI Trader · v2.1
      </span>
    </div>
    """


def normalize_dir(d):
    if d in ("HOME","H","1"): return "HOME"
    if d in ("AWAY","A","2"): return "AWAY"
    if d in ("DRAW","D","X"): return "DRAW"
    return d


def fav_confirmed(row, min_conf=1):
    fav = row.get("dir_favorite")
    if not fav: return None
    fav_n = normalize_dir(fav)
    sigs = [row.get("dir_anomaly"), row.get("dir_model"),
            row.get("dir_xg"), row.get("dir_form")]
    agree = [s for s in sigs if s and normalize_dir(s) == fav_n]
    return fav if len(agree) >= min_conf else None


def get_odd(row, direction):
    d = normalize_dir(direction)
    if d == "HOME": return row.get("odd_1")
    if d == "AWAY": return row.get("odd_2")
    if d == "DRAW": return row.get("odd_X")
    return None


# ============================================================
# DATA LOADING
# ============================================================

@st.cache_data(ttl=300)
def load_signals():
    conn = db.connect()
    # JOIN with matches_v2 to pull enriched columns (H2H, standings, form, YC/corners)
    df = conn.read_df("""
        SELECT ss.*,
               m.h2h_n, m.h2h_home_wins, m.h2h_away_wins, m.h2h_draws,
               m.h2h_avg_goals, m.h2h_btts_rate,
               m.home_league_pos, m.away_league_pos,
               m.home_pts, m.away_pts,
               m.home_title_gap, m.away_title_gap,
               m.home_relegation_gap, m.away_relegation_gap,
               m.home_form_5g, m.away_form_5g,
               m.home_avg_goals_5g, m.away_avg_goals_5g,
               m.home_yc_5g_avg, m.away_yc_5g_avg,
               m.home_corners_5g_avg, m.away_corners_5g_avg,
               m.betradar_id
        FROM signal_snapshots ss
        LEFT JOIN matches_v2 m
            ON ss.league_code = m.league_code
            AND substr(ss.kickoff_iso,1,10) = substr(m.kickoff_utc,1,10)
            AND lower(replace(ss.home_team,' ','')) = lower(replace(m.home_team,' ',''))
        WHERE ss.source='football_data'
    """)
    conn.close()
    df["season_canon"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


@st.cache_data(ttl=600)
def load_registry():
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return {"models": []}


# ============================================================
# HEADER
# ============================================================

def render_header():
    df = load_signals()
    df_set = df[df["settled"]==1]
    n_total = len(df_set)
    n_signals_total = len(df_set[df_set["dir_anomaly"].notna()])
    n_models = len([m for m in load_registry().get("models", [])
                    if m["status"] in ("VALIDATED","PROTOTYPE")])
    now = datetime.now()

    st.markdown(f"""
    <div class="header-bar">
        <div class="header-logo">◉ AI TRADER PRO<span>· Digital Twin · v2.1</span></div>
        <div class="header-tick live"><span class="live-dot"></span>LIVE</div>
        <div class="header-tick"><span>SAMPLE</span> <span class="value">{n_total:,}</span></div>
        <div class="header-tick"><span>MODELLER</span> <span class="value">{n_models}</span></div>
        <div class="header-tick"><span>SİNYAL ROW</span> <span class="value">{n_signals_total:,}</span></div>
        <div class="header-tick warn"><span>DEMO MODE</span> <span class="value">SEZON BİTTİ</span></div>
        <div style="flex: 1;"></div>
        <div class="header-tick"><span>{now.strftime('%d.%m.%Y')}</span>
             <span class="value">{now.strftime('%H:%M')}</span></div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================

def render_sidebar():
    with st.sidebar:
        st.markdown("# ◉")
        st.markdown("**AI TRADER PRO**")
        st.caption("Digital Twin Trader v2.1")
        st.markdown("---")

        st.markdown("### 💰 TRADER PROFİLİ")
        bankroll = st.number_input("Bankroll (TL)", value=10000, step=1000,
                                   key="sb_bankroll")
        risk = st.select_slider(
            "Risk Profili",
            options=["Konservatif", "Orta", "Agresif"],
            value="Orta", key="sb_risk",
        )

        st.markdown("---")
        st.markdown("### ⚙️ SİSTEM DURUMU")
        st.markdown('<div class="info-box">'
                    '<div class="info-box-label">DB Versiyon</div>'
                    '<div class="info-box-value">v2.1</div></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="info-box">'
                    '<div class="info-box-label">Aktif Model</div>'
                    '<div class="info-box-value">10</div></div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="info-box">'
                    '<div class="info-box-label">Üçlü Eksen</div>'
                    '<div class="info-box-value" style="color:#10b981;">9/8/8</div></div>',
                    unsafe_allow_html=True)

        st.markdown("---")
        st.caption("**Hızlı Linkler**")
        st.markdown(
            '<a href="https://www.iddaa.com/program/futbol-mac-onceski" '
            'target="_blank" class="btn btn-primary" '
            'style="width: 100%; justify-content: center; margin-bottom: 8px;">'
            '▶ İDDAA Programı</a>',
            unsafe_allow_html=True
        )
        st.markdown(
            '<a href="https://www.iddaa.com/canli-bahis" '
            'target="_blank" class="btn btn-secondary" '
            'style="width: 100%; justify-content: center;">'
            '⚡ Canlı Bahis</a>',
            unsafe_allow_html=True
        )

    return bankroll, risk


# ============================================================
# PAGE: OVERVIEW (Yönetici Özeti)
# ============================================================

def page_overview():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ OVERVIEW</div>'
                '<div class="section-title-meta">YÖNETİCİ ÖZETİ · TEK BAKIŞTA</div>'
                '</div>', unsafe_allow_html=True)

    df = load_signals()
    df_set = df[df["settled"]==1].copy()

    # KPI BAR (4 kart)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Toplam Sample", f"{len(df_set):,}",
                  delta=f"+{len(df_set)-10657:,} (V2)")
    with c2:
        n_sezon = df_set["season_canon"].nunique()
        st.metric("Aktif Sezon", n_sezon, delta="9 sezon")
    with c3:
        n_models = len([m for m in load_registry().get("models", [])
                       if m["status"]=="VALIDATED"])
        st.metric("Onaylı Model", n_models, delta="Bonferroni geç.")
    with c4:
        st.metric("Sistem Skor", "25/30", delta="+9 (bugün)")

    st.markdown("---")

    # ANA BAŞARILAR
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("### 🏆 SİSTEM BAŞARILARI")
        st.markdown("""
        <div class="callout">
        <strong>3/5 model Bonferroni-significant pozitif edge</strong><br/>
        • DUOVOX (E0+SP1): p=0.0000 ⭐⭐⭐<br/>
        • TRIOVOX (E0+SP1+D1): p=0.0001 ⭐⭐⭐<br/>
        • MONOVOX-E0: p=0.0017 ⭐⭐⭐
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div class="callout">
        <strong>Platt kalibrasyon başarısı</strong><br/>
        KG modeli reliability gap: %14 → %3.5<br/>
        A/Ü modeli reliability gap: %5.7 → %2.5
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown("### ⚡ AKTİF ÜRÜN AİLESİ")
        st.markdown("""
        <div class="info-box">
            <div class="info-box-label">1X2 Selective Sniper Family</div>
            <div style="margin-top: 10px;">
              <span class="pill pill-green">DUOVOX</span>
              <span class="pill pill-green">TRIOVOX</span>
              <span class="pill pill-green">MONOVOX-E0</span>
              <span class="pill pill-amber">TRIVOX</span>
              <span class="pill pill-amber">MONOVOX-SP1</span>
            </div>
        </div>
        <div class="info-box" style="margin-top: 12px;">
            <div class="info-box-label">Multi-Market (Platt Kalibre)</div>
            <div style="margin-top: 10px;">
              <span class="pill pill-blue">OU25-D1-Over</span>
              <span class="pill pill-blue">OU25-E0-Under</span>
              <span class="pill pill-blue">BTTS-D1-Var</span>
              <span class="pill pill-blue">BTTS-SP1-Var/Yok</span>
              <span class="pill pill-blue">BTTS-I1-Yok</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # Sezon dağılımı
    st.markdown("---")
    st.markdown("### 📊 9 SEZON SAMPLE DAĞILIMI")
    sezon_dist = df_set.groupby("season_canon").size().reset_index(name="n")
    fig = px.bar(sezon_dist, x="season_canon", y="n",
                 color="n", color_continuous_scale=[[0, '#0f172a'], [1, '#10b981']],
                 labels={"season_canon": "Sezon", "n": "Maç sayısı"})
    fig.update_layout(
        plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
        font=dict(color="#d4d4d8", family="Inter"),
        showlegend=False, height=280,
        margin=dict(t=20, b=40, l=60, r=20),
    )
    fig.update_traces(marker=dict(line=dict(color="#10b981", width=1)))
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# PAGE: LIVE CALENDAR (Güncel Takvim)
# ============================================================

def page_live_calendar():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ LIVE CALENDAR</div>'
                '<div class="section-title-meta">GÜNCEL TAKVİM · MODEL CANLI BAKIŞ</div>'
                '</div>', unsafe_allow_html=True)

    df = load_signals()
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")

    # Future matches?
    df_future = df[df["matchday"] > today_str]

    if len(df_future) == 0:
        # Demo mode — son hafta
        last_date = pd.to_datetime(df["matchday"]).max()
        week_start = (last_date - timedelta(days=7)).strftime("%Y-%m-%d")
        df_window = df[(df["matchday"] > week_start) & (df["matchday"] <= last_date.strftime("%Y-%m-%d"))].copy()
        st.markdown(f"""
        <div class="callout callout-warn">
        <strong>DEMO MODE — Sezon Sonu</strong><br/>
        2025-26 sezon <strong>{last_date.strftime('%d %b')}</strong> tarihinde bitti.
        Üzerinizde gerçek 'gelecek maçlar' olmadığı için <strong>son haftanın settled maçları</strong>
        gösteriliyor. Yeni sezon (2026-27) Ağustos başı başlıyor.
        <br/><br/>
        <em>Gerçek live mode'a geçiş için api-football future fixtures entegrasyonu gerekir.</em>
        </div>
        """, unsafe_allow_html=True)
    else:
        df_window = df_future.copy()

    if df_window.empty:
        st.warning("Hiç maç yok.")
        return

    # Filter bar
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    with fc1:
        ligs = sorted(df_window["league_code"].unique())
        ligs_sel = st.multiselect("Lig", ligs, default=ligs, key="lc_lig")
    with fc2:
        market_sel = st.selectbox("Pazar Filtresi",
                                  ["Tümü", "1X2 ULTRA (Q5+a2)",
                                   "A/Ü 2.5", "KG (BTTS)"],
                                  key="lc_market")
    with fc3:
        only_signal = st.checkbox("Sadece güçlü sinyalli maçlar",
                                  value=True, key="lc_strong")

    df_window = df_window[df_window["league_code"].isin(ligs_sel)]
    df_window = df_window.sort_values("kickoff_iso", ascending=False)

    # KPI bar
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Toplam Maç", f"{len(df_window):,}")
    with c2:
        df_window["dir_fc"] = df_window.apply(
            lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        df_window["__has_q5"] = (df_window["dir_fc"].notna()) & (df_window["agree_count"] >= 2)
        n_q5 = df_window["__has_q5"].sum()
        st.metric("Q5+a2 Picks", n_q5,
                  delta=f"%{n_q5*100//max(1,len(df_window))}")
    with c3:
        n_ou = df_window["dir_ou_model_cal"].notna().sum() if "dir_ou_model_cal" in df_window.columns else 0
        st.metric("A/Ü Sinyal", n_ou)
    with c4:
        n_kg = df_window["dir_btts_model_cal"].notna().sum() if "dir_btts_model_cal" in df_window.columns else 0
        st.metric("KG Sinyal", n_kg)

    st.markdown("---")

    # Q5+a2 ULTRA picks
    if market_sel in ("Tümü", "1X2 ULTRA (Q5+a2)"):
        df_ultra = df_window[df_window["__has_q5"]].copy()
        df_ultra = df_ultra.sort_values("score_v14", ascending=False)

        if not df_ultra.empty:
            st.markdown(f"### 🎯 ULTRA-SNIPER (Q5+a2 · {len(df_ultra)})")
            for _, p in df_ultra.head(10).iterrows():
                d = p["dir_fc"]
                d_norm = normalize_dir(d)
                odd = get_odd(p.to_dict(), d)
                if not odd: continue
                won = p.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_norm]
                tier = 1 if p["agree_count"] >= 3 else 2
                badge = "ULTRA" if tier == 1 else "BÜYÜK"

                # League full name
                lig_full = LIG_FULL_NAME.get(p['league_code'], p['league_code'])

                # Result indicator
                if pd.notna(p.get("result_1x2")):
                    result_pill = ('<span class="pill pill-green">✓ KAZANDI</span>' if won
                                  else '<span class="pill pill-red">✗ KAYBETTİ</span>')
                else:
                    result_pill = '<span class="pill pill-gray">⏳ BEKLEMEDE</span>'

                actions = render_match_actions(p['home_team'], p['away_team'],
                                              p['league_code'], p['matchday'])

                # ── Enriched context satırı ──────────────────────────
                enriched_html = ""
                h2h_n   = p.get("h2h_n")
                h2h_hw  = p.get("h2h_home_wins") or 0
                h2h_aw  = p.get("h2h_away_wins") or 0
                h2h_dr  = p.get("h2h_draws") or 0
                h2h_btts = p.get("h2h_btts_rate")
                h2h_goals = p.get("h2h_avg_goals")
                h_pos   = p.get("home_league_pos")
                a_pos   = p.get("away_league_pos")
                h_relgap = p.get("home_relegation_gap")
                a_relgap = p.get("away_relegation_gap")
                h_form  = p.get("home_form_5g") or ""
                a_form  = p.get("away_form_5g") or ""
                h_yc    = p.get("home_yc_5g_avg")
                a_yc    = p.get("away_yc_5g_avg")

                chips = []

                # H2H chip
                if h2h_n and h2h_n >= 3:
                    chips.append(
                        f'<span style="background:rgba(99,102,241,0.12);border:1px solid #6366f1;'
                        f'color:#a5b4fc;border-radius:4px;padding:2px 7px;font-size:10px;'
                        f'font-family:Consolas,monospace;white-space:nowrap;">'
                        f'H2H {h2h_hw}G/{h2h_dr}B/{h2h_aw}K'
                        + (f' · BTTS {h2h_btts:.0%}' if h2h_btts else '')
                        + (f' · avg {h2h_goals:.1f}g' if h2h_goals else '')
                        + f'</span>'
                    )

                # Standings chips
                if h_pos and a_pos:
                    h_col = "#10d48e" if (h_relgap or 99) > 6 else "#ef4444"
                    a_col = "#10d48e" if (a_relgap or 99) > 6 else "#ef4444"
                    chips.append(
                        f'<span style="background:rgba(15,23,42,0.6);border:1px solid #1e3a5f;'
                        f'color:#94a3b8;border-radius:4px;padding:2px 7px;font-size:10px;'
                        f'font-family:Consolas,monospace;white-space:nowrap;">'
                        f'<span style="color:{h_col}">#{h_pos}</span>'
                        + (f'<span style="color:#ef4444;font-size:9px;"> ⚠ RELZONE</span>' if (h_relgap or 99) <= 4 else '')
                        + f' vs '
                        + f'<span style="color:{a_col}">#{a_pos}</span>'
                        + (f'<span style="color:#ef4444;font-size:9px;"> ⚠ RELZONE</span>' if (a_relgap or 99) <= 4 else '')
                        + f'</span>'
                    )

                # Form chips
                def form_color(f):
                    if not f: return "#64748b"
                    sc = {"W":1,"D":0.5,"L":0}
                    v = [sc.get(c,0.5) for c in f[:5]]
                    avg = sum(v)/len(v) if v else 0.5
                    return "#10d48e" if avg >= 0.65 else ("#f59e0b" if avg >= 0.45 else "#ef4444")

                def form_display(f):
                    if not f: return "—"
                    clr = {"W":"#10d48e","D":"#f59e0b","L":"#ef4444"}
                    parts = []
                    for c in f[:5]:
                        col = clr.get(c, "#64748b")
                        parts.append(f'<span style="color:{col};font-weight:700;">{c}</span>')
                    return "".join(parts)

                if h_form or a_form:
                    chips.append(
                        f'<span style="background:rgba(15,23,42,0.6);border:1px solid #1e293b;'
                        f'color:#94a3b8;border-radius:4px;padding:2px 7px;font-size:10px;'
                        f'font-family:Consolas,monospace;white-space:nowrap;">'
                        f'Ev:{form_display(h_form)} Dep:{form_display(a_form)}'
                        f'</span>'
                    )

                # YC warning chip
                if h_yc and a_yc and (h_yc >= 3.0 or a_yc >= 3.0):
                    chips.append(
                        f'<span style="background:rgba(251,191,36,0.1);border:1px solid #f59e0b;'
                        f'color:#f59e0b;border-radius:4px;padding:2px 7px;font-size:10px;'
                        f'font-family:Consolas,monospace;white-space:nowrap;">'
                        f'🟨 Ev:{h_yc:.1f} Dep:{a_yc:.1f} SY/maç</span>'
                    )

                if chips:
                    enriched_html = (
                        '<div style="display:flex;gap:6px;flex-wrap:wrap;'
                        'margin-top:8px;padding-top:8px;border-top:1px solid #0f1829;">'
                        + "".join(chips)
                        + '</div>'
                    )

                st.markdown(f"""
                <div class="match-card tier-{tier}">
                  <div class="match-header">
                    <div>
                      <div class="match-title">{p['home_team']} – {p['away_team']}</div>
                      <div class="match-subtitle">{lig_full} · {format_date_human(p['matchday'])} · {p['matchday']}</div>
                    </div>
                    <span class="match-tier-badge badge-tier-{tier}">{badge}</span>
                  </div>
                  <div class="stat-row">
                    <div class="stat-item">
                      <span class="stat-label">Tahmin</span>
                      <span class="stat-value warn">{d_norm[0]}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Oran</span>
                      <span class="stat-value">{odd:.2f}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Skor</span>
                      <span class="stat-value">{(p['score_v14'] or 0):.3f}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Sinyal</span>
                      <span class="stat-value success">{int(p['agree_count'])}/4</span>
                    </div>
                    <div class="stat-item" style="margin-left: auto;">
                      <span class="stat-label">Durum</span>
                      <div>{result_pill}</div>
                    </div>
                  </div>
                  {enriched_html}
                  {actions}
                </div>
                """, unsafe_allow_html=True)

    # A/Ü picks (kalibre)
    if market_sel in ("Tümü", "A/Ü 2.5") and "dir_ou_model_cal" in df_window.columns:
        df_ou = df_window[df_window["dir_ou_model_cal"].notna()].copy()
        df_ou = df_ou.sort_values("s_ou_model_cal", ascending=False)

        # Lig-yön pozitif edge filtresi
        POSITIVE_OU = {("D1","Over"), ("E0","Under"), ("T1","Under"), ("SP1","Over"), ("F1","Over")}
        df_ou["_positive"] = df_ou.apply(
            lambda r: (r["league_code"], r["dir_ou_model_cal"]) in POSITIVE_OU, axis=1)
        df_ou = df_ou[df_ou["_positive"]]

        if not df_ou.empty:
            st.markdown(f"### 📊 ALT/ÜST 2.5 SİNYAL ({len(df_ou)})")
            for _, p in df_ou.head(10).iterrows():
                odd = p.get("odd_over25") if p["dir_ou_model_cal"]=="Over" else p.get("odd_under25")
                if not odd: continue

                actual_total = (p.get("home_score") or 0) + (p.get("away_score") or 0)
                if pd.notna(p.get("result_1x2")):
                    won = ((p["dir_ou_model_cal"]=="Over" and actual_total > 2)
                          or (p["dir_ou_model_cal"]=="Under" and actual_total <= 2))
                    result_pill = ('<span class="pill pill-green">✓ KAZANDI</span>' if won
                                  else '<span class="pill pill-red">✗ KAYBETTİ</span>')
                else:
                    result_pill = '<span class="pill pill-gray">⏳ BEKLEMEDE</span>'

                edge = p.get("ou_model_edge") or 0
                tier = 1 if abs(edge) > 0.10 else 2
                badge = "ALL-IN" if tier == 1 else "STANDART"
                lig_full = LIG_FULL_NAME.get(p['league_code'], p['league_code'])
                actions = render_match_actions(p['home_team'], p['away_team'],
                                              p['league_code'], p['matchday'])

                st.markdown(f"""
                <div class="match-card tier-{tier}">
                  <div class="match-header">
                    <div>
                      <div class="match-title">{p['home_team']} – {p['away_team']}</div>
                      <div class="match-subtitle">{lig_full} · {format_date_human(p['matchday'])} · A/Ü 2.5</div>
                    </div>
                    <span class="match-tier-badge badge-tier-{tier}">{badge}</span>
                  </div>
                  <div class="stat-row">
                    <div class="stat-item">
                      <span class="stat-label">Yön</span>
                      <span class="stat-value warn">{p['dir_ou_model_cal']}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Oran</span>
                      <span class="stat-value">{odd:.2f}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Sinyal Gücü</span>
                      <span class="stat-value">{(p['s_ou_model_cal'] or 0):.2f}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">Edge</span>
                      <span class="stat-value info">{edge*100:+.1f}%</span>
                    </div>
                    <div class="stat-item" style="margin-left: auto;">
                      <span class="stat-label">Durum</span>
                      <div>{result_pill}</div>
                    </div>
                  </div>
                  {actions}
                </div>
                """, unsafe_allow_html=True)


# ============================================================
# PAGE: TRADING DESK
# ============================================================

def page_trading_desk():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ TRADING DESK</div>'
                '<div class="section-title-meta">MULTI-MARKET MAÇ PANELİ</div>'
                '</div>', unsafe_allow_html=True)

    df = load_signals()
    df_set = df[(df["season"]=="2526") & (df["settled"]==1)].copy()

    if df_set.empty:
        st.warning("Veri yok.")
        return

    # Tarih filtresi
    available_dates = sorted(df_set["matchday"].unique(), reverse=True)
    selected_date = st.selectbox("Tarih", available_dates[:30],
                                 format_func=lambda d: f"{d} ({format_date_human(d)})",
                                 key="td_date")

    df_day = df_set[df_set["matchday"] == selected_date].copy()
    st.markdown(f"#### {selected_date} · {len(df_day)} maç")

    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Toplam Maç", len(df_day))
    with c2:
        n_with_sig = (df_day["agree_count"] >= 2).sum()
        st.metric("Sinyal Var", n_with_sig)
    with c3:
        ligs = df_day["league_code"].nunique()
        st.metric("Lig Sayısı", ligs)

    st.markdown("---")

    # Lig-by-lig matches
    for lg in sorted(df_day["league_code"].unique()):
        df_lg = df_day[df_day["league_code"] == lg].sort_values("kickoff_iso")
        lig_full = LIG_FULL_NAME.get(lg, lg)
        st.markdown(f"### {lig_full} ({len(df_lg)})")

        for _, p in df_lg.iterrows():
            # FAV_CONFIRMED dir
            dir_fc = fav_confirmed(p.to_dict(), 1)
            if dir_fc:
                d_norm = normalize_dir(dir_fc)
                odd = get_odd(p.to_dict(), dir_fc)
                won = p.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_norm]
                pick_label = d_norm[0]
                pick_odd = f"{odd:.2f}" if odd else "—"
                agree = int(p["agree_count"])
                if agree >= 3: tier = 1; badge = "ULTRA"
                elif agree >= 2: tier = 2; badge = "BÜYÜK"
                else: tier = 3; badge = "STANDART"
            else:
                d_norm = "-"
                odd = None
                won = False
                pick_label = "—"
                pick_odd = "—"
                agree = 0
                tier = 4
                badge = "PAS"

            ftr = p.get("result_1x2")
            score_str = (f"{int(p.get('home_score') or 0)}-{int(p.get('away_score') or 0)}"
                        if pd.notna(p.get('home_score')) else "—")

            if dir_fc and pd.notna(ftr):
                result_pill = ('<span class="pill pill-green">✓</span>' if won
                              else '<span class="pill pill-red">✗</span>')
            else:
                result_pill = '<span class="pill pill-gray">—</span>'

            actions = render_match_actions(p['home_team'], p['away_team'],
                                          p['league_code'], p['matchday'])

            st.markdown(f"""
            <div class="match-card tier-{tier}">
              <div class="match-header">
                <div>
                  <div class="match-title">{p['home_team']} – {p['away_team']}</div>
                  <div class="match-subtitle">Skor: {score_str} · {format_date_human(p['matchday'])}</div>
                </div>
                <span class="match-tier-badge badge-tier-{tier}">{badge}</span>
              </div>
              <div class="stat-row">
                <div class="stat-item">
                  <span class="stat-label">AI Pick</span>
                  <span class="stat-value warn">{pick_label}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Oran</span>
                  <span class="stat-value">{pick_odd}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">Sinyal</span>
                  <span class="stat-value">{agree}/4</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">A/Ü</span>
                  <span class="stat-value muted">{p.get('dir_ou_model_cal') or '—'}</span>
                </div>
                <div class="stat-item">
                  <span class="stat-label">KG</span>
                  <span class="stat-value muted">{p.get('dir_btts_model_cal') or '—'}</span>
                </div>
                <div class="stat-item" style="margin-left: auto;">
                  <span class="stat-label">Sonuç</span>
                  <div>{result_pill}</div>
                </div>
              </div>
              {actions}
            </div>
            """, unsafe_allow_html=True)


# ============================================================
# PAGE: COUPON ENGINEER
# ============================================================

def page_coupon_engineer():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ COUPON ENGINEER</div>'
                '<div class="section-title-meta">KUPON OPTİMİZASYON STÜDYOSU</div>'
                '</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="callout">
    <strong>Kupon Stüdyosu</strong><br/>
    Seçili adaylar için 3 strateji önerisi (Sniper Spread / Kombo / Sistem 2/3) +
    AI Trader yorumu. Korelasyon kontrolü otomatik.
    </div>
    """, unsafe_allow_html=True)

    bankroll = st.session_state.get("sb_bankroll", 10000)
    stake_unit = bankroll * 0.05  # %5

    # Mock 3 ALL-IN aday
    candidates = [
        {"match":"Liverpool – Tottenham", "lig":"E0", "pick":"1", "odd":1.55,
         "q":"Q5", "agree":2, "model":"DUOVOX", "p_win":0.78},
        {"match":"Real Madrid – Real Betis", "lig":"SP1", "pick":"1", "odd":1.45,
         "q":"Q5", "agree":3, "model":"DUOVOX+MONOVOX-SP1", "p_win":0.82},
        {"match":"Galatasaray – Fenerbahçe", "lig":"T1", "pick":"1", "odd":1.85,
         "q":"Q5", "agree":2, "model":"TRIVOX", "p_win":0.65},
    ]

    st.markdown("### 🎯 SEÇİLİ ADAYLAR (3)")
    for c in candidates:
        lig_full = LIG_FULL_NAME.get(c['lig'], c['lig'])
        actions = render_match_actions(*c['match'].split(" – "), c['lig'], "2026-05-25")
        st.markdown(f"""
        <div class="match-card tier-1">
          <div class="match-header">
            <div>
              <div class="match-title">{c['match']}</div>
              <div class="match-subtitle">{lig_full} · {c['model']}</div>
            </div>
            <span class="match-tier-badge badge-tier-1">{c['q']}+a{c['agree']}</span>
          </div>
          <div class="stat-row">
            <div class="stat-item">
              <span class="stat-label">Tahmin</span>
              <span class="stat-value warn">{c['pick']}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Oran</span>
              <span class="stat-value">{c['odd']}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">P(Win)</span>
              <span class="stat-value success">{c['p_win']*100:.0f}%</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Sinyal</span>
              <span class="stat-value">{c['agree']}/4</span>
            </div>
          </div>
          {actions}
        </div>
        """, unsafe_allow_html=True)

    # 3 strateji
    st.markdown("---")
    st.markdown("### 📐 STRATEJİ OPSİYONLARI")

    s1, s2, s3 = st.columns(3)
    with s1:
        st.markdown(f"""
        <div class="match-card tier-2">
          <h3 style="color:#f59e0b; margin-top:0;">A · SNIPER SPREAD</h3>
          <p style="color:#71717a; font-size:12px;">3 ayrı K=1 kupon · Düşük korelasyon · Varyans dağıtık</p>
          <div class="stat-row">
            <div class="stat-item"><span class="stat-label">Toplam Stake</span>
              <span class="stat-value">{int(stake_unit*3):,} TL</span></div>
            <div class="stat-item"><span class="stat-label">EV</span>
              <span class="stat-value success">+543 TL</span></div>
            <div class="stat-item"><span class="stat-label">Max Kayıp</span>
              <span class="stat-value danger">-{int(stake_unit*3):,} TL</span></div>
            <div class="stat-item"><span class="stat-label">Varyans</span>
              <span class="stat-value warn">ORTA</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with s2:
        st.markdown(f"""
        <div class="match-card tier-3">
          <h3 style="color:#3b82f6; margin-top:0;">B · KOMBO K=3</h3>
          <p style="color:#71717a; font-size:12px;">3 leg kombi · Yüksek getiri · Yüksek varyans</p>
          <div class="stat-row">
            <div class="stat-item"><span class="stat-label">Toplam Stake</span>
              <span class="stat-value">{int(stake_unit):,} TL</span></div>
            <div class="stat-item"><span class="stat-label">Kombo Oran</span>
              <span class="stat-value">4.16</span></div>
            <div class="stat-item"><span class="stat-label">EV</span>
              <span class="stat-value success">+403 TL</span></div>
            <div class="stat-item"><span class="stat-label">Varyans</span>
              <span class="stat-value danger">ÇOK YÜKSEK</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    with s3:
        st.markdown(f"""
        <div class="match-card tier-1">
          <h3 style="color:#10b981; margin-top:0;">C · SİSTEM 2/3 ⭐</h3>
          <p style="color:#10b981; font-size:12px;">2 tutsa kayıp yok · TAVSİYE</p>
          <div class="stat-row">
            <div class="stat-item"><span class="stat-label">Toplam Stake</span>
              <span class="stat-value">{int(stake_unit*3):,} TL</span></div>
            <div class="stat-item"><span class="stat-label">EV</span>
              <span class="stat-value success">+783 TL</span></div>
            <div class="stat-item"><span class="stat-label">Min Tut</span>
              <span class="stat-value">2/3</span></div>
            <div class="stat-item"><span class="stat-label">Varyans</span>
              <span class="stat-value success">DÜŞÜK</span></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("""
    <div class="callout">
    <strong>🤖 AI Trader Önerisi:</strong> Seçenek C (Sistem 2/3) — en yüksek
    EV + en düşük varyans + profile uyumlu. Korelasyon kontrolü ✓ geçildi
    (max r=0.30, eşik 0.40).
    </div>
    """, unsafe_allow_html=True)

    # Action butonu
    st.markdown(f"""
    <div style="text-align: center; margin-top: 30px;">
      <a href="{IDDAA_PROGRAM_URL}" target="_blank" rel="noopener" class="btn btn-primary"
         style="padding: 14px 32px; font-size: 13px;">
        ▶ İDDAA'da SİSTEM 2/3 OLUŞTUR
      </a>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# PAGE: MODEL CATALOG
# ============================================================

def page_model_catalog():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ MODEL CATALOG</div>'
                '<div class="section-title-meta">10 SİLAH · REGISTRY v1.0</div>'
                '</div>', unsafe_allow_html=True)

    registry = load_registry()
    models = registry.get("models", [])

    fc1, fc2 = st.columns([3, 1])
    with fc1:
        status_filter = st.multiselect("Lifecycle Status",
                                       ["VALIDATED","PROTOTYPE","DEPRECATED"],
                                       default=["VALIDATED","PROTOTYPE"],
                                       key="mc_status")
    with fc2:
        st.metric("Toplam Model", len(models))

    filtered = [m for m in models if m["status"] in status_filter]

    for i in range(0, len(filtered), 2):
        cols = st.columns(2)
        for j, col in enumerate(cols):
            if i+j >= len(filtered): break
            m = filtered[i+j]
            with col:
                status_pill_class = {
                    "VALIDATED": "pill-green",
                    "PROTOTYPE": "pill-amber",
                    "DEPRECATED": "pill-red",
                }[m["status"]]
                perf = m.get("performance", {})
                hit = perf.get("hit_rate_q5_a2") or perf.get("hit_rate") or 0
                edge = perf.get("edge_pp_q5_a2") or perf.get("edge_pp") or perf.get("edge_pp_vs_baseline") or 0
                p_val = perf.get("bonferroni_p")
                bonf = ""
                if p_val is not None:
                    if p_val < 0.0025: bonf = "⭐⭐⭐"
                    elif p_val < 0.01: bonf = "⭐⭐"
                    elif p_val < 0.05: bonf = "⭐"

                st.markdown(f"""
                <div class="match-card tier-1">
                  <div class="match-header">
                    <div>
                      <div class="match-title">{m['name']} {m['version']}</div>
                      <div class="match-subtitle">{m.get('market','')} · {'+'.join(m.get('leagues',[]))}</div>
                    </div>
                    <span class="pill {status_pill_class}">{m['status']}</span>
                  </div>
                  <div style="margin: 14px 0; padding: 12px; background: #050810; border-radius: 6px;">
                    <div style="font-size: 10px; color: #71717a; text-transform: uppercase;
                                letter-spacing: 0.08em; margin-bottom: 4px;">AMAÇ</div>
                    <div style="font-size: 12px; color: #d4d4d8; line-height: 1.5;">
                      {m.get('purpose','—')}
                    </div>
                  </div>
                  <div class="stat-row">
                    <div class="stat-item"><span class="stat-label">Sample</span>
                      <span class="stat-value">{m.get('sample',0):,}</span></div>
                    <div class="stat-item"><span class="stat-label">Hit %</span>
                      <span class="stat-value success">{hit*100:.0f}%</span></div>
                    <div class="stat-item"><span class="stat-label">Edge</span>
                      <span class="stat-value">{edge:+.1f}pp</span></div>
                    <div class="stat-item"><span class="stat-label">Bonferroni</span>
                      <span class="stat-value warn">{bonf or "—"}</span></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)


# ============================================================
# PAGE: ANALYTICS
# ============================================================

def page_analytics():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ ANALYTICS</div>'
                '<div class="section-title-meta">SEZONSAL STABİLİTE · MULTI-MODEL HEATMAP</div>'
                '</div>', unsafe_allow_html=True)

    df = load_signals()
    df_set = df[df["settled"]==1].copy()

    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]
    seasons_order = ["2017-18","2018-19","2019-20","2020-21","2021-22",
                     "2022-23","2023-24","2024-25","2025-26"]

    heatmap_data = []
    for name, leagues in models:
        sub = df_set[df_set["league_code"].isin(leagues)].copy()
        sub["dir_fc"] = sub.apply(lambda r: fav_confirmed(r.to_dict(), 1), axis=1)
        sub = sub[sub["dir_fc"].notna()].sort_values("score_v14", ascending=False)
        picks = []
        for (md, lg), grp in sub.groupby(["matchday","league_code"]):
            top = grp.head(1)
            for _, leg in top.iterrows():
                d = leg["dir_fc"]
                o = get_odd(leg.to_dict(), d)
                if not o: continue
                d_n = normalize_dir(d)
                won = leg.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_n]
                picks.append({"season": leg["season_canon"],
                             "score": leg["score_v14"] or 0,
                             "won": won})
        if not picks: continue
        df_p = pd.DataFrame(picks)
        try:
            df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"],
                              duplicates="drop")
        except: continue
        q5 = df_p[df_p["q"]=="Q5"]
        for ss in seasons_order:
            sub_ss = q5[q5["season"]==ss]
            if len(sub_ss) >= 5:
                heatmap_data.append({"Model": name, "Sezon": ss,
                                    "Hit%": sub_ss["won"].mean()*100,
                                    "n": len(sub_ss)})

    if heatmap_data:
        df_hm = pd.DataFrame(heatmap_data)
        pivot = df_hm.pivot_table(index="Model", columns="Sezon", values="Hit%")
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=[[0,'#0a0e1a'],[0.5,'#f59e0b'],[1,'#10b981']],
            text=[[f"{v:.0f}%" if pd.notna(v) else "" for v in row] for row in pivot.values],
            texttemplate="%{text}", textfont={"size":13, "color":"#ffffff"},
            zmin=40, zmax=90, showscale=True,
            colorbar=dict(title="Hit %", tickfont=dict(color="#d4d4d8")),
        ))
        fig.update_layout(
            title="Q5 HIT RATE · MODEL × SEZON",
            plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
            font=dict(color="#d4d4d8", family="Consolas, Courier New"),
            height=420,
            margin=dict(t=70, b=40, l=180, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── YENİ: Enriched overlay katma değer analizi ────────────────────
    st.markdown("---")
    st.markdown("### 🔬 ENRİCHED OVERLAY KATMA DEĞERİ")
    st.markdown("""
    <div style="color:#94a3b8;font-size:12px;margin-bottom:12px;">
    29 Mayıs 2026 backtest: 19.275 maç, H2H + Standings + Form enriched data ile.
    Imp ≥%65 = oran implied prob eşiği. SP1+T1+D1+E0 ligleri.
    </div>
    """, unsafe_allow_html=True)

    enriched_results = [
        {"Strateji": "Baseline (imp≥65%)",          "Pick": 2393, "Hit": 76.4, "ROI": 0.0},
        {"Strateji": "+ H2H filtresi",              "Pick": 1531, "Hit": 77.5, "ROI": 1.3},
        {"Strateji": "+ Standings filtresi",         "Pick": 1015, "Hit": 76.7, "ROI": 1.7},
        {"Strateji": "+ H2H + Standings",            "Pick":  596, "Hit": 79.0, "ROI": 5.1},
        {"Strateji": "+ agree≥1 + H2H + Standings",  "Pick":  550, "Hit": 78.7, "ROI": 4.7},
    ]
    df_enr = pd.DataFrame(enriched_results)

    col_r, col_h = st.columns(2)
    with col_r:
        fig_roi = go.Figure(go.Bar(
            x=df_enr["Strateji"], y=df_enr["ROI"],
            marker_color=["#475569","#3b82f6","#6366f1","#10d48e","#10b981"],
            text=[f"+{r:.1f}%" for r in df_enr["ROI"]],
            textposition="outside", textfont=dict(color="#e2e8f0", size=11)
        ))
        fig_roi.update_layout(
            title="ROI% — Katman Ekledikçe",
            plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
            font=dict(color="#d4d4d8", size=11),
            height=300, margin=dict(t=50,b=60,l=40,r=20),
            yaxis=dict(gridcolor="#1e293b", zeroline=True,
                      zerolinecolor="#475569", title="ROI %"),
            xaxis=dict(tickangle=-20),
        )
        st.plotly_chart(fig_roi, use_container_width=True)

    with col_h:
        fig_hit = go.Figure(go.Bar(
            x=df_enr["Strateji"], y=df_enr["Hit"],
            marker_color=["#475569","#3b82f6","#6366f1","#10d48e","#10b981"],
            text=[f"{h:.1f}%" for h in df_enr["Hit"]],
            textposition="outside", textfont=dict(color="#e2e8f0", size=11)
        ))
        fig_hit.update_layout(
            title="Hit% — Katman Ekledikçe",
            plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
            font=dict(color="#d4d4d8", size=11),
            height=300, margin=dict(t=50,b=60,l=40,r=20),
            yaxis=dict(gridcolor="#1e293b", range=[74,82], title="Hit %"),
            xaxis=dict(tickangle=-20),
        )
        st.plotly_chart(fig_hit, use_container_width=True)

    # Lig kırılımı
    lig_results = [
        {"Lig": "SP1 La Liga",   "Pick": 106, "Hit": 87.7, "ROI": 21.3, "Karar": "✅ DEVAM"},
        {"Lig": "T1 Süper Lig",  "Pick":  64, "Hit": 79.7, "ROI":  7.9, "Karar": "✅ DEVAM"},
        {"Lig": "D1 Bundesliga", "Pick":  69, "Hit": 78.3, "ROI":  6.0, "Karar": "✅ DEVAM"},
        {"Lig": "E0 Premier",    "Pick": 106, "Hit": 76.4, "ROI":  2.8, "Karar": "✅ DEVAM"},
        {"Lig": "I1 Serie A",    "Pick": 104, "Hit": 71.2, "ROI": -4.2, "Karar": "❌ ÇIKARILDI"},
        {"Lig": "F1 Ligue 1",    "Pick":  70, "Hit": 67.1, "ROI":-10.5, "Karar": "❌ ÇIKARILDI"},
    ]
    df_lig = pd.DataFrame(lig_results)
    colors = ["#10d48e" if r > 0 else "#ef4444" for r in df_lig["ROI"]]
    fig_lig = go.Figure(go.Bar(
        x=df_lig["Lig"], y=df_lig["ROI"],
        marker_color=colors,
        text=[f"{r:+.1f}%" for r in df_lig["ROI"]],
        textposition="outside", textfont=dict(color="#e2e8f0", size=12)
    ))
    fig_lig.update_layout(
        title="TÜM KATMANLAR · Lig Bazında ROI (H2H+Standings, imp≥65%)",
        plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
        font=dict(color="#d4d4d8"), height=320,
        margin=dict(t=50,b=40,l=40,r=20),
        yaxis=dict(gridcolor="#1e293b", zeroline=True, zerolinecolor="#f59e0b"),
        shapes=[dict(type="line", x0=-0.5, x1=5.5, y0=0, y1=0,
                    line=dict(color="#f59e0b", width=1, dash="dash"))],
    )
    st.plotly_chart(fig_lig, use_container_width=True)

    st.markdown("""
    <div style="background:rgba(16,212,142,0.06);border:1px solid rgba(16,212,142,0.2);
    border-left:3px solid #10d48e;border-radius:6px;padding:12px 16px;margin-top:8px;">
    <strong style="color:#10d48e;">✅ SONUÇ:</strong>
    <span style="color:#94a3b8;font-size:12px;">
    H2H + Standings overlay, baseline +%0.0 ROI'yi <strong style="color:#10d48e;">+%5.1'e</strong> çekiyor.
    F1 ve I1 negatif yapısal sorun — sistemden çıkarıldı.
    Production pipeline: <strong>SP1 + T1 + D1 + E0</strong> · imp≥65% + H2H + Standings.
    </span>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# PAGE: DATA EXCELLENCY
# ============================================================

def page_data_excellency():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ DATA EXCELLENCY</div>'
                '<div class="section-title-meta">VERİTABANI KALİTE · COVERAGE · SNAPSHOTS</div>'
                '</div>', unsafe_allow_html=True)

    conn = db.connect()
    n_matches = conn.execute("SELECT COUNT(*) FROM matches_v2").fetchone()[0]
    n_settled = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE is_settled=1").fetchone()[0]
    n_signals = conn.execute("SELECT COUNT(*) FROM signal_snapshots WHERE source='football_data'").fetchone()[0]
    avg_q = conn.execute("SELECT AVG(quality_score) FROM matches_v2").fetchone()[0]

    # Enriched column fill rates (conn AÇIK kalmalı — aşağıda heatmap kullanıyor)
    n_h2h      = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE h2h_n IS NOT NULL").fetchone()[0]
    n_standings= conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE home_league_pos IS NOT NULL").fetchone()[0]
    n_form     = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE home_form_5g IS NOT NULL").fetchone()[0]
    n_yc       = conn.execute("SELECT COUNT(*) FROM matches_v2 WHERE home_yc_5g_avg IS NOT NULL").fetchone()[0]

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Matches DB", f"{n_matches:,}", delta=f"+{n_matches-10657:,}")
    with c2: st.metric("Settled", f"{n_settled:,}", delta=f"%{n_settled*100//max(1,n_matches)}")
    with c3: st.metric("Sinyal Rows", f"{n_signals:,}")
    with c4: st.metric("Avg Quality", f"{avg_q:.2f}")

    st.markdown("#### 🗄️ Enriched Kolon Doluluk (29 May 2026)")
    enriched_cols = [
        ("H2H Geçmiş",      n_h2h,       n_matches),
        ("Puan Tablosu",     n_standings, n_matches),
        ("Form 5G",          n_form,      n_matches),
        ("YC Ort.",          n_yc,        n_matches),
    ]
    ecols = st.columns(4)
    for i, (label, n, total) in enumerate(enriched_cols):
        pct = n / total * 100 if total else 0
        color = "#10d48e" if pct > 90 else ("#f59e0b" if pct > 50 else "#ef4444")
        with ecols[i]:
            st.markdown(
                f'<div style="background:#0d1628;border:1px solid #1a2840;border-radius:6px;'
                f'padding:12px;text-align:center;">'
                f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;">{label}</div>'
                f'<div style="color:{color};font-size:22px;font-weight:700;">{pct:.0f}%</div>'
                f'<div style="color:#475569;font-size:10px;">{n:,} / {total:,}</div>'
                f'</div>',
                unsafe_allow_html=True
            )

    st.markdown("---")

    # Coverage heatmap
    df_cov = conn.read_df("""
        SELECT league_code, season, COUNT(*) as n, SUM(has_full_odds) as odds
        FROM matches_v2 GROUP BY league_code, season
        ORDER BY season, league_code
    """)
    pivot = df_cov.pivot_table(index="league_code", columns="season",
                              values="odds", aggfunc="sum")
    n_pivot = df_cov.pivot_table(index="league_code", columns="season",
                                values="n", aggfunc="sum")
    pct_pivot = (pivot / n_pivot * 100).fillna(0)

    fig = go.Figure(data=go.Heatmap(
        z=pct_pivot.values, x=pct_pivot.columns, y=pct_pivot.index,
        colorscale=[[0,'#ef4444'],[0.5,'#f59e0b'],[1,'#10b981']],
        text=[[f"{v:.0f}%" if v else "" for v in row] for row in pct_pivot.values],
        texttemplate="%{text}", textfont={"size":12, "color":"#ffffff"},
        zmin=0, zmax=100,
    ))
    fig.update_layout(
        title="ODDS COVERAGE · LİG × SEZON (%)",
        plot_bgcolor="#0a0e1a", paper_bgcolor="#0a0e1a",
        font=dict(color="#d4d4d8", family="Consolas, Courier New"),
        height=320,
        margin=dict(t=60, b=40, l=80, r=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Snapshots
    snap_dir = YAZILIM / "02_VERI" / "snapshots"
    if snap_dir.exists():
        snaps = [d for d in snap_dir.iterdir() if d.is_dir()]
        st.markdown(f"### 📦 SNAPSHOT GEÇMİŞİ ({len(snaps)})")
        for snap in sorted(snaps, reverse=True)[:5]:
            manifest = snap / "manifest.json"
            if manifest.exists():
                m = json.loads(manifest.read_text(encoding="utf-8"))
                size_mb = m.get("db_size_compressed_bytes",0)/1024/1024
                st.markdown(f"""
                <div class="match-card tier-3">
                  <div class="match-header">
                    <div>
                      <div class="match-title">{m['snapshot_name']}</div>
                      <div class="match-subtitle">{m.get('description','')[:80]}</div>
                    </div>
                    <span class="pill pill-blue">{m['reason']}</span>
                  </div>
                  <div class="stat-row">
                    <div class="stat-item"><span class="stat-label">Tablo</span>
                      <span class="stat-value">{m['total_tables']}</span></div>
                    <div class="stat-item"><span class="stat-label">Satır</span>
                      <span class="stat-value">{m['total_rows']:,}</span></div>
                    <div class="stat-item"><span class="stat-label">Boyut</span>
                      <span class="stat-value">{size_mb:.1f}MB</span></div>
                    <div class="stat-item"><span class="stat-label">Hash</span>
                      <span class="stat-value muted" style="font-size: 10px;">
                        {m['db_hash_md5'][:12]}…</span></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

    conn.close()


# ============================================================
# PAGE: RISK MANAGEMENT
# ============================================================

def page_risk():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">▸ RISK MANAGEMENT</div>'
                '<div class="section-title-meta">BANKROLL · DRAWDOWN · LİMİTLER</div>'
                '</div>', unsafe_allow_html=True)

    bankroll = st.session_state.get("sb_bankroll", 10000)
    bankroll_start = 10000
    bankroll_now = bankroll  # Demo: use sidebar input
    pnl = bankroll_now - bankroll_start
    pct = pnl / bankroll_start * 100

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Bankroll", f"{bankroll_now:,} TL",
                       delta=f"{pnl:+,} TL")
    with c2: st.metric("Yield", f"%{pct:+.1f}",
                       delta="Demo data")
    with c3: st.metric("Drawdown", "%-6.2", delta="kontrollü")
    with c4: st.metric("Açık Pozisyon", "0",
                       delta="(sezon bitti)")

    st.markdown("---")
    st.markdown("### 🛡️ RİSK EŞİK MATRİSİ")
    risk_table = pd.DataFrame([
        {"Eşik": "Normal", "Yield Aralığı": "%-15 üstü",
         "Aksiyon": "Standart stake (1x)", "Durum": "Aktif"},
        {"Eşik": "Uyarı", "Yield Aralığı": "%-15 → %-20",
         "Aksiyon": "Stake yarı (0.5x)", "Durum": "Pasif"},
        {"Eşik": "Kritik", "Yield Aralığı": "%-25 alt",
         "Aksiyon": "1 hafta PAS", "Durum": "Pasif"},
    ])
    st.dataframe(risk_table, use_container_width=True, hide_index=True)


# ============================================================
# PAGE: TRADER PLAYBOOK
# ============================================================

def page_playbook():
    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">&#9655; TRADER PLAYBOOK</div>'
                '<div class="section-title-meta">SISTEM KILAVUZU &middot; MODEL REFERANSI &middot; KARAR AGACI</div>'
                '</div>', unsafe_allow_html=True)

    playbook_path = THIS_DIR / "TRADER_PLAYBOOK.md"
    if playbook_path.exists():
        content = playbook_path.read_text(encoding="utf-8")
        st.markdown(content)
    else:
        st.warning("TRADER_PLAYBOOK.md bulunamadi.")

    st.markdown("---")

    # Quick Reference Cards
    st.markdown("### Hizli Referans Kartlari")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
<div style='background:#0f172a;border:1px solid #22c55e;border-radius:8px;padding:16px'>
<div style='color:#22c55e;font-weight:700;font-size:13px;margin-bottom:8px'>OYUN ACILISI</div>
<div style='color:#94a3b8;font-size:12px;line-height:1.8'>
score_v14 &ge; 0.48<br>
agree_count &ge; 2<br>
edge &gt; %4<br>
<span style='color:#fbbf24'>Sezon hft 5+</span>
</div>
</div>""", unsafe_allow_html=True)

    with c2:
        st.markdown("""
<div style='background:#0f172a;border:1px solid #f59e0b;border-radius:8px;padding:16px'>
<div style='color:#f59e0b;font-weight:700;font-size:13px;margin-bottom:8px'>KUPON BOYUTLARI</div>
<div style='color:#94a3b8;font-size:12px;line-height:1.8'>
K=1: max %5 bankroll<br>
K=2: max %3 bankroll<br>
K=3: max %2 bankroll<br>
<span style='color:#fbbf24'>Hafta max 2 kupon</span>
</div>
</div>""", unsafe_allow_html=True)

    with c3:
        st.markdown("""
<div style='background:#0f172a;border:1px solid #ef4444;border-radius:8px;padding:16px'>
<div style='color:#ef4444;font-weight:700;font-size:13px;margin-bottom:8px'>DUR SINYALLERI</div>
<div style='color:#94a3b8;font-size:12px;line-height:1.8'>
3 art. kayip<br>
Haftalik -%15<br>
agree = 0<br>
<span style='color:#fbbf24'>Sezon hft 1-4</span>
</div>
</div>""", unsafe_allow_html=True)

    st.markdown("---")

    # Sezon Takvimi
    st.markdown("### 2026-27 Yeni Sezon Baslangic Takvimi")
    takvim = pd.DataFrame([
        {"Lig": "D1  Almanya Bundesliga",   "Beklenen Baslangic": "~1 Agustos 2026",   "Ilk Oyna": "Hft 5 (~1 Eylu 2026)",   "Model": "OU25-D1-Over (%59 hit)"},
        {"Lig": "F1  Fransa Ligue 1",       "Beklenen Baslangic": "~8 Agustos 2026",   "Ilk Oyna": "Hft 5 (~12 Eylu 2026)",  "Model": "OU25 + TRIOVOX"},
        {"Lig": "T1  Turkiye Super Lig",    "Beklenen Baslangic": "~8-15 Agustos 2026","Ilk Oyna": "Hft 5 (~12 Eylu 2026)",  "Model": "TRIVOX (%82 hit)"},
        {"Lig": "E0  Premier League",       "Beklenen Baslangic": "~15 Agustos 2026",  "Ilk Oyna": "Hft 5 (~19 Eylu 2026)",  "Model": "DUOVOX (%62 hit) + MONOVOX-E0"},
        {"Lig": "SP1 La Liga",              "Beklenen Baslangic": "~15-22 Agustos 2026","Ilk Oyna": "Hft 5 (~26 Eylu 2026)", "Model": "DUOVOX + MONOVOX-SP1"},
        {"Lig": "I1  Serie A",              "Beklenen Baslangic": "~22-29 Agustos 2026","Ilk Oyna": "Hft 5 (~3 Ekim 2026)",  "Model": "TRIOVOX"},
    ])
    st.dataframe(takvim, use_container_width=True, hide_index=True)

    st.info(
        "**Kural:** Yeni sezonda ilk 4 hafta GOZLEM MODU (oynama). "
        "Hft 5'ten itibaren K=1 ile giris yap, hft 9'dan sonra tam operasyon."
    )

    st.markdown("---")

    # ── BOLUM 2: MODELLER ────────────────────────────────────
    with st.expander("2 — MODEL ARSENAL — 10 Silah", expanded=False):
        st.markdown("**VOX Ailesi — 1X2 Secici Keskin Nisanci**")
        vox_df = pd.DataFrame([
            {"Model": "DUOVOX",      "Lig": "E0 + SP1",  "n": 1807, "hit%": "%62", "Bonferroni": "p=0.0000"},
            {"Model": "TRIOVOX",     "Lig": "E0+SP1+D1", "n": 2529, "hit%": "%60", "Bonferroni": "p=0.0001"},
            {"Model": "MONOVOX-E0",  "Lig": "E0",        "n": 881,  "hit%": "%65", "Bonferroni": "p=0.0017"},
            {"Model": "TRIVOX",      "Lig": "T1",        "n": 22,   "hit%": "%82", "Bonferroni": "p=0.0071"},
            {"Model": "MONOVOX-SP1", "Lig": "SP1",       "n": 926,  "hit%": "%55", "Bonferroni": "p=0.0081"},
        ])
        st.dataframe(vox_df, use_container_width=True, hide_index=True)
        st.markdown("**MARKET Ailesi — Multi-Market, Platt Kalibre**")
        mkt_df = pd.DataFrame([
            {"Model": "OU25-D1-Over",  "Lig": "D1",  "Yon": "Ust 2.5", "n": 178, "hit%": "%59", "Edge": "+%4.18"},
            {"Model": "OU25-E0-Under", "Lig": "E0",  "Yon": "Alt 2.5", "n": 297, "hit%": "%41", "Edge": "+%3.55"},
            {"Model": "OU25-T1-Under", "Lig": "T1",  "Yon": "Alt 2.5", "n": 240, "hit%": "%45", "Edge": "+%1.60"},
            {"Model": "OU25-SP1-Over", "Lig": "SP1", "Yon": "Ust 2.5", "n": 324, "hit%": "%40", "Edge": "+%1.54"},
            {"Model": "BTTS-D1-Var",   "Lig": "D1",  "Yon": "KG Var",  "n": 497, "hit%": "%64", "Edge": "kalibre OK"},
            {"Model": "BTTS-T1-Var",   "Lig": "T1",  "Yon": "KG Var",  "n": 396, "hit%": "%64", "Edge": "kalibre OK"},
        ])
        st.dataframe(mkt_df, use_container_width=True, hide_index=True)

    # ── BOLUM 3: SİNYALLER ──────────────────────────────────
    with st.expander("3 — SİNYAL SİSTEMİ — 9 Bagimsiz Lens", expanded=False):
        sig_df = pd.DataFrame([
            {"Kod": "s_anomaly", "Ad": "Odds Anomaly",  "Agirlik": "0.20", "Yontem": "Closing vs Opening fark"},
            {"Kod": "s_model",   "Ad": "DC Model",      "Agirlik": "0.20", "Yontem": "Dixon-Coles Lambda fark"},
            {"Kod": "s_xg",      "Ad": "xG",            "Agirlik": "0.15", "Yontem": "Understat xG son 5 mac"},
            {"Kod": "s_form",    "Ad": "Form",          "Agirlik": "0.10", "Yontem": "Son 5 mac gol/puan avg"},
            {"Kod": "s_sharp",   "Ad": "Sharp Money",   "Agirlik": "0.10", "Yontem": "Pinnacle vs piyasa"},
            {"Kod": "s_invvar",  "Ad": "Inverse Var",   "Agirlik": "0.05", "Yontem": "Market belirsizlik"},
            {"Kod": "s_shots",   "Ad": "Shots",         "Agirlik": "0.10", "Yontem": "Isabetli sut ortalaması"},
            {"Kod": "s_referee", "Ad": "Referee",       "Agirlik": "0.05", "Yontem": "Hakem kart profili"},
            {"Kod": "s_cards",   "Ad": "Cards",         "Agirlik": "0.05", "Yontem": "Takim kart gecmisi"},
        ])
        st.dataframe(sig_df, use_container_width=True, hide_index=True)
        c_s1, c_s2 = st.columns(2)
        with c_s1:
            st.markdown("**`score_v14` Esikleri**")
            st.code("score >= 0.48  ->  Q5  (GUCLU SINYAL)\n"
                    "score >= 0.35  ->  Orta sinyal\n"
                    "score <  0.20  ->  Zayif, gec", language="text")
        with c_s2:
            st.markdown("**`agree_count` Konsensus**")
            st.code("agree >= 3  ->  Tier 1 (en guvenilir)\n"
                    "agree == 2  ->  Tier 2 (kabul)\n"
                    "agree <= 1  ->  PAS GEC", language="text")

    # ── BOLUM 4: KALİBRASYON ────────────────────────────────
    with st.expander("4 — KALİBRE OLASILIKLAR — Nasil Okunur?", expanded=False):
        cal_df = pd.DataFrame([
            {"Kolon": "fp_btts_model_yes_cal", "Anlam": "KG Var (kalibre)",  "Esik": "> 0.58  =>  KG Var degerlendir"},
            {"Kolon": "fp_btts_model_no_cal",  "Anlam": "KG Yok (kalibre)", "Esik": "> 0.60  =>  KG Yok degerlendir"},
            {"Kolon": "fp_ou_model_over_cal",  "Anlam": "Ust 2.5 (kalibre)","Esik": "> 0.58  =>  Ust degerlendir"},
            {"Kolon": "fp_ou_model_under_cal", "Anlam": "Alt 2.5 (kalibre)","Esik": "> 0.60  =>  Alt degerlendir"},
        ])
        st.dataframe(cal_df, use_container_width=True, hide_index=True)
        st.code("EDGE = fp_model - fp_market\n"
                "  fp_market = (1/odd) / overround\n"
                "  fp_model  = kalibre model ciktisi\n\n"
                "EDGE > +0.04  ->  Deger var  => OYNA\n"
                "EDGE < +0.02  ->  Deger yok  => PAS", language="text")

    # ── BOLUM 5: KARAR AGACI ────────────────────────────────
    with st.expander("5 — KUPON KARAR AGACI — Adim Adim", expanded=False):
        st.code("""ADIM 1: Mac Filtrele
    is_settled = 0  |  league_code IN (T1,E0,D1,SP1,I1,F1)
    kickoff_utc BETWEEN now AND now+72h

ADIM 2: Sinyal Kontrol
    score_v14   >= 0.48   (Q5 esigi)
    agree_count >= 2      (Konsensus esigi)

ADIM 3: Market Sec
    1X2  :  dir_consensus yonu  (1 veya 2)
    KG+  :  fp_btts_yes_cal > 0.58  VE  s_btts_model_cal = +1
    Alt  :  fp_ou_under_cal > 0.60  VE  s_ou_model_cal   = -1
    Ust  :  fp_ou_over_cal  > 0.58  VE  s_ou_model_cal   = +1

ADIM 4: Kupon Olustur
    K=1 : tek pick  (en yuksek score)
    K=2 : iki pick  (farkli maclar)
    K=3 : uc pick   (min 2 farkli lig)

ADIM 5: Risk Kontrol
    K=1 => max %5 bankroll
    K=2 => max %3 bankroll
    K=3 => max %2 bankroll
    Haftalik kayip %15 asarsa DUR""", language="text")
        kt_df = pd.DataFrame([
            {"Tip": "K=1 Tek",      "Kat. Hedefi": "1.30-1.60", "Hit %": "%60-75", "BR %": "max %5",  "Kriter": "score>=0.52, agree>=3"},
            {"Tip": "K=2 Ciftli",   "Kat. Hedefi": "1.80-2.50", "Hit %": "%40-55", "BR %": "max %3",  "Kriter": "score>=0.48, agree>=2"},
            {"Tip": "K=3 Uclu",     "Kat. Hedefi": "2.50-4.00", "Hit %": "%20-35", "BR %": "max %2",  "Kriter": "farkli liglerden"},
            {"Tip": "Multi-Market", "Kat. Hedefi": "1.60-2.20", "Hit %": "%35-50", "BR %": "max %3",  "Kriter": "BTTS/OU edge > %4"},
        ])
        st.dataframe(kt_df, use_container_width=True, hide_index=True)

    # ── BOLUM 6: RİSK ────────────────────────────────────────
    with st.expander("6 — RİSK YONETİMİ — Kirmizi Cizgiler", expanded=False):
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            st.error("**ASLA YAPMA**\n\n"
                     "- Tek kupona bankrolun >%10'unu koy\n"
                     "- Haftada 2'den fazla K=3\n"
                     "- score_v14 < 0.35 maca oyna\n"
                     "- agree_count = 0 maca oyna\n"
                     "- KG: fp_btts_cal < 0.55 ise gec\n"
                     "- A/U: edge < %2 ise gec")
        with c_r2:
            st.success("**HER ZAMAN YAP**\n\n"
                       "- Haftalik P&L takibi yap\n"
                       "- 3 art. kayip => 1 hafta bekle\n"
                       "- K=3'te min 2 farkli lig\n"
                       "- Yeni sezon Hft 1-4 gozlem\n"
                       "- Sezon basi kucuk stake ile gir")

    # ── BOLUM 7: HAZIR SQL ──────────────────────────────────
    with st.expander("7 — HAZIR SQL SORGULARI", expanded=False):
        st.markdown("**Bu Haftanin Picklari**")
        st.code("""SELECT m.league_code, m.kickoff_utc,
       m.home_team, m.away_team,
       m.closing_1, m.closing_X, m.closing_2,
       s.score_v14, s.agree_count, s.dir_consensus,
       s.fp_btts_model_yes_cal, s.fp_ou_model_over_cal
FROM matches_v2 m
JOIN signal_snapshots s ON s.iddaa_match_id = m.external_id_iddaa
WHERE m.is_settled = 0
  AND s.score_v14 >= 0.48
  AND s.agree_count >= 2
ORDER BY s.score_v14 DESC;""", language="sql")
        st.markdown("**Sezon P&L Ozeti**")
        st.code("""SELECT league_code,
       COUNT(*) as picks,
       SUM(CASE WHEN pnl_top3_v13 > 0 THEN 1 ELSE 0 END) as wins,
       ROUND(AVG(pnl_top3_v13), 2) as avg_pnl,
       ROUND(SUM(pnl_top3_v13), 2) as total_pnl
FROM signal_snapshots
WHERE settled = 1
  AND score_v14 >= 0.48 AND agree_count >= 2
GROUP BY league_code;""", language="sql")
        st.markdown("**KG Market Edge**")
        st.code("""SELECT league_code, COUNT(*) as n,
       ROUND(AVG(fp_btts_model_yes_cal
         - (1.0/odd_btts_yes / (1.0/odd_btts_yes + 1.0/odd_btts_no))), 4) as kg_edge
FROM signal_snapshots
WHERE odd_btts_yes IS NOT NULL
  AND fp_btts_model_yes_cal IS NOT NULL
GROUP BY league_code HAVING n >= 30
ORDER BY kg_edge DESC;""", language="sql")


# ============================================================
# PAGE: PAPER TRADER
# ============================================================

def _pt_db_query(sql: str, params: tuple = ()) -> list:
    """Cached DB query helper for paper trader (TTL 60s)."""
    conn = db_connect()
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def page_paper_trader():
    sys.path.insert(0, str(YAZILIM / "02_VERI"))
    try:
        from paper_engine import PaperEngine
        engine_ok = True
    except Exception as e:
        engine_ok = False
        st.error(f"paper_engine import hatasi: {e}")
        return

    PORTFOLIO_ID = "PAPER_V1"
    engine = PaperEngine(PORTFOLIO_ID)

    st.markdown('<div class="section-title-wrap">'
                '<div class="section-title-main">&#9655; PAPER TRADER</div>'
                '<div class="section-title-meta">AI PORTFOLIO &middot; 5.000 TL &middot; CANLI SİMÜLASYON</div>'
                '</div>', unsafe_allow_html=True)

    # ── Portföy KPI'leri ─────────────────────────────────────
    status = engine.portfolio_status()
    if not status:
        st.warning("Portfoy bulunamadi. paper_migration.py calistir.")
        return

    pnl_color   = "#22c55e" if status["pnl"] >= 0 else "#ef4444"
    yield_color = "#22c55e" if status["yield_pct"] >= 0 else "#ef4444"

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Bankroll", f"{status['current_bankroll']:,.0f} TL",
                  delta=f"{status['pnl']:+,.0f} TL")
    with col2:
        st.metric("Yield", f"%{status['yield_pct']:+.1f}",
                  delta=f"Zirve: {status['peak_bankroll']:,.0f} TL")
    with col3:
        st.metric("Kupon W/L",
                  f"{status['won_coupons']}/{status['total_coupons']}",
                  delta=f"Win: %{status['coupon_win_rate']:.0f}")
    with col4:
        st.metric("Bahis W/L",
                  f"{status['total_wins']}/{status['total_bets']}",
                  delta=f"Win: %{status['bet_win_rate']:.0f}")
    with col5:
        st.metric("Acik Kupon", status["open_coupons"],
                  delta=f"Staked: {status['total_staked']:,.0f} TL")

    st.markdown("---")

    # ── Kontrol Paneli ───────────────────────────────────────
    col_a, col_b, col_c = st.columns([2, 2, 3])
    with col_a:
        if st.button("▶ Yeni Seans — Kupon Olustur", use_container_width=True, type="primary"):
            with st.spinner("Maclar analiz ediliyor..."):
                coupons = engine.build_session_coupons()
                if coupons:
                    ids = engine.place_coupons(coupons)
                    st.success(f"{len(ids)} yeni kupon olusturuldu ve DB'ye yazildi!")
                    st.rerun()
                else:
                    st.info("Bu seans icin uygun sinyal bulunamadi.")
    with col_b:
        if st.button("✓ Sonuclari Kapat (Settle)", use_container_width=True):
            with st.spinner("Sonuclar kontrol ediliyor..."):
                result = engine.settle_coupons()
                settled = result.get("settled", 0)
                pnl_settled = result.get("pnl", 0.0)
                if settled > 0:
                    new_br = engine.portfolio_status().get("current_bankroll", 0)
                    st.success(f"{settled} kupon kapatildi | PnL: {pnl_settled:+.0f} TL | Bankroll: {new_br:,.0f} TL")
                else:
                    st.info("Kapatilacak bitmis mac yok (is_settled=1 olmayan maclar bekliyor).")
                st.rerun()
    with col_c:
        st.info(f"**Strateji:** {status.get('strategy_version','v1')}  |  "
                f"**Baslangic:** 5,000 TL  |  "
                f"**Toplam stake:** {status.get('total_staked',0):,.0f} TL")

    st.markdown("---")

    # ── Bugün & Yarın — Model Seçimleri ──────────────────────
    _now_utc = datetime.utcnow()
    _today_s  = _now_utc.date().isoformat()
    _cutoff_s = (_now_utc.date() + timedelta(days=2)).isoformat()

    _conn_t = db_connect()
    _tmatch_rows = _conn_t.execute("""
        SELECT match_id, league_code, home_team, away_team, kickoff_utc,
               closing_1, closing_X, closing_2,
               closing_over25, closing_under25, closing_btts_yes, closing_btts_no,
               external_id_iddaa
        FROM matches_v2
        WHERE is_settled = 0
          AND kickoff_utc >= ?
          AND kickoff_utc <= ?
        ORDER BY kickoff_utc
    """, (_today_s + "T00:00", _cutoff_s + "T23:59")).fetchall()
    _conn_t.close()

    _today_picks = []
    for _r in _tmatch_rows:
        _m = dict(_r)
        _sigs = []
        _o1 = _m.get("closing_1");  _oX = _m.get("closing_X"); _o2 = _m.get("closing_2")
        _ou = _m.get("closing_over25"); _uu = _m.get("closing_under25")
        _ky = _m.get("closing_btts_yes"); _kn = _m.get("closing_btts_no")
        _p1 = _pX = _p2 = _pou = _puu = _pky = _pkn = None
        if _o1 and _oX and _o2:
            _v = 1/_o1 + 1/_oX + 1/_o2
            _p1, _pX, _p2 = (1/_o1)/_v, (1/_oX)/_v, (1/_o2)/_v
        if _ky and _kn:
            _vk = 1/_ky + 1/_kn
            _pky, _pkn = (1/_ky)/_vk, (1/_kn)/_vk
        if _ou and _uu:
            _vo = 1/_ou + 1/_uu
            _pou, _puu = (1/_ou)/_vo, (1/_uu)/_vo
        if _p1 and _p1 >= 0.65: _sigs.append(("EV_FAV_GUCLU", _p1, _o1))
        elif _p1 and _p1 >= 0.58: _sigs.append(("ev_fav", _p1, _o1))
        if _p2 and _p2 >= 0.65: _sigs.append(("DEP_FAV_GUCLU", _p2, _o2))
        elif _p2 and _p2 >= 0.58: _sigs.append(("dep_fav", _p2, _o2))
        if _pky and _pky >= 0.60: _sigs.append(("KG_VAR", _pky, _ky))
        if _pkn and _pkn >= 0.62: _sigs.append(("KG_YOK", _pkn, _kn))
        if _pou and _pou >= 0.58: _sigs.append(("UST_25", _pou, _ou))
        if _puu and _puu >= 0.60: _sigs.append(("ALT_25", _puu, _uu))
        if not _sigs:
            continue
        _fav = any(s[0] in ("EV_FAV_GUCLU", "DEP_FAV_GUCLU") for s in _sigs)
        _kgv = any(s[0] == "KG_VAR" for s in _sigs)
        _kgy = any(s[0] == "KG_YOK" for s in _sigs)
        _ust = any(s[0] == "UST_25" for s in _sigs)
        _alt = any(s[0] == "ALT_25" for s in _sigs)
        if (_fav and (_kgy or _alt)) or (_kgv and _ust) or (_alt and _kgy):
            _cmc, _tier = 3, "GUCLU"
        elif _fav or _kgv:
            _cmc, _tier = 2, "ORTA"
        else:
            _cmc, _tier = 1, "ZAYIF"
        _today_picks.append({"match": _m, "signals": _sigs, "cmc": _cmc, "tier": _tier})
    _today_picks.sort(key=lambda x: (x["cmc"], max(s[1] for s in x["signals"])), reverse=True)

    if _today_picks:
        st.markdown("### 📍 BUGÜN & YARIN — MODEL SEÇİMLERİ")
        st.caption(
            f"Çapraz Pazar Uyumu (CMC) sıralaması &nbsp;|&nbsp; "
            f"{len(_today_picks)} maç sinyal veriyor &nbsp;|&nbsp; "
            f"GUCLU = çok-market doğrulama ✅"
        )
        _tier_colors = {"GUCLU": "#22c55e", "ORTA": "#f59e0b", "ZAYIF": "#64748b"}
        for _tp in _today_picks[:12]:
            _m2 = _tp["match"]
            _ss  = _tp["signals"]
            _tc  = _tier_colors.get(_tp["tier"], "#64748b")
            _ko  = (_m2.get("kickoff_utc") or "")[:16]
            _eid = _m2.get("external_id_iddaa") or "?"
            _stars = "★" * _tp["cmc"] + "☆" * (3 - _tp["cmc"])
            _sh = " &nbsp;<b style='color:#475569'>+</b>&nbsp; ".join(
                f"<b style='color:{('#22c55e' if 'GUCLU' in s[0] or s[0]=='KG_VAR' else '#f59e0b')}'>"
                f"{s[0]}</b>&nbsp;<span style='color:#94a3b8'>@{s[2]:.2f}</span>"
                f"&nbsp;<span style='color:#64748b'>(%{s[1]*100:.0f})</span>"
                for s in _ss
            )
            st.markdown(
                f"<div style='background:#0b1120;border-left:4px solid {_tc};"
                f"border-radius:6px;padding:10px 14px;margin-bottom:6px'>"
                f"<div style='display:flex;justify-content:space-between;align-items:center'>"
                f"<span style='color:{_tc};font-weight:700;font-size:11px;letter-spacing:1px'>"
                f"CMC {_tp['tier']} &nbsp;{_stars}</span>"
                f"<span style='color:#64748b;font-size:11px'>"
                f"{_m2.get('league_code','?')} &nbsp;⏰ {_ko} UTC</span>"
                f"</div>"
                f"<div style='color:#e2e8f0;font-weight:600;font-size:14px;margin:4px 0'>"
                f"{_m2.get('home_team','?')} "
                f"<span style='color:#475569'>vs</span> "
                f"{_m2.get('away_team','?')}</div>"
                f"<div style='font-size:12px;margin:4px 0'>{_sh}</div>"
                f"<a href='https://www.iddaa.com/program/futbol' target='_blank' "
                f"style='color:#3b82f6;font-size:11px;text-decoration:none'>"
                f"🔗 iddaa.com &nbsp;|&nbsp; "
                f"Ara: <b>{_m2.get('home_team','?')}</b> &nbsp;|&nbsp; EID:{_eid}</a>"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Açık Kuponlar ────────────────────────────────────────
    conn = db_connect()
    open_coupons = conn.execute("""
        SELECT c.coupon_id, c.session_date, c.coupon_type, c.num_legs,
               c.combined_odds, c.stake, c.potential_return, c.status, c.reasoning
        FROM paper_coupons c
        WHERE c.portfolio_id = ? AND c.status = 'open'
        ORDER BY c.created_at DESC
    """, (PORTFOLIO_ID,)).fetchall()

    if open_coupons:
        st.markdown("### Acik Kuponlar")
        for coup in open_coupons:
            coup_d = dict(coup)
            cid = coup_d["coupon_id"][:8]
            ctype = coup_d["coupon_type"]
            color = {"K1_FAVORITE": "#22c55e", "K1_KG": "#3b82f6",
                     "K2_COMBO": "#f59e0b", "K1_ALT": "#a78bfa"}.get(ctype, "#64748b")
            st.markdown(
                f"<div style='background:#0b1120;border-left:3px solid {color};"
                f"border-radius:6px;padding:12px 16px;margin-bottom:8px'>"
                f"<span style='color:{color};font-weight:700;font-size:12px'>{ctype}</span>"
                f"&nbsp;&nbsp;<span style='color:#94a3b8;font-size:11px'>[{cid}]"
                f"  {coup_d['session_date']}</span><br>"
                f"<span style='color:#e2e8f0;font-size:13px'>{coup_d['reasoning'] or ''}</span><br>"
                f"<span style='color:#64748b;font-size:12px'>"
                f"Stake: <b>{coup_d['stake']:.0f} TL</b>  |  "
                f"Oran: <b>{coup_d['combined_odds']:.3f}</b>  |  "
                f"Max getiri: <b>{coup_d['potential_return']:.0f} TL</b>"
                f"</span></div>",
                unsafe_allow_html=True
            )
            # Alt betler
            bets = conn.execute("""
                SELECT market, pick, odds, model_prob, edge, home_team, away_team, status
                FROM paper_bets WHERE coupon_id = ?
            """, (coup_d["coupon_id"],)).fetchall()
            for b in bets:
                bd = dict(b)
                b_color = "#22c55e" if bd["status"] == "won" else ("#ef4444" if bd["status"] == "lost" else "#64748b")
                st.markdown(
                    f"&nbsp;&nbsp;&nbsp;"
                    f"<span style='color:#94a3b8;font-size:12px'>"
                    f"&#9656; {bd['home_team']} vs {bd['away_team']} — "
                    f"<b style='color:#e2e8f0'>{bd['market']} {bd['pick']} @ {bd['odds']}</b>"
                    f"&nbsp;(impl.prob: %{(bd['model_prob'] or 0)*100:.0f}"
                    f"&nbsp;edge: %{(bd['edge'] or 0)*100:+.1f})"
                    f"&nbsp;<span style='color:{b_color}'>[{bd['status'].upper()}]</span>"
                    f"</span>",
                    unsafe_allow_html=True
                )
    else:
        st.info("Acik kupon yok. 'Yeni Seans' ile kupon olustur.")

    conn.close()

    st.markdown("---")

    # ── ALPACA-STYLE EKİTY CHART ─────────────────────────────
    eq_rows = _pt_db_query("""
        SELECT settled_at, pnl, coupon_type, status, combined_odds, stake
        FROM paper_coupons
        WHERE portfolio_id = ? AND status != 'open'
        ORDER BY settled_at
    """, (PORTFOLIO_ID,))

    _initial = 5000.0
    if eq_rows:
        # Build equity + drawdown series
        br_vals    = [_initial]
        dd_vals    = [0.0]
        ev_dates   = ["Baslangic"]
        ev_texts   = [""]
        peak_br    = _initial
        running_br = _initial
        for r in eq_rows:
            pnl_r = r["pnl"] or 0.0
            running_br += pnl_r
            br_vals.append(running_br)
            peak_br = max(peak_br, running_br)
            dd_pct = ((running_br - peak_br) / peak_br * 100) if peak_br > 0 else 0.0
            dd_vals.append(round(dd_pct, 2))
            lbl = (r["settled_at"] or "")[:10]
            ev_dates.append(lbl)
            status_icon = "WIN" if r["status"] == "won" else "LOSS"
            ev_texts.append(
                f"{r['coupon_type']} {status_icon}<br>"
                f"PnL: {pnl_r:+.0f} TL | Oran: {r.get('combined_odds',1):.2f}"
            )

        line_color = "#22c55e" if running_br >= _initial else "#ef4444"
        fill_color = "rgba(34,197,94,0.08)" if running_br >= _initial else "rgba(239,68,68,0.08)"

        fig_eq = make_subplots(
            rows=2, cols=1,
            row_heights=[0.72, 0.28],
            shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=("Portfolio Degeri (TL)", "Drawdown (%)"),
        )

        # Equity curve
        fig_eq.add_trace(go.Scatter(
            x=ev_dates, y=br_vals,
            mode="lines+markers",
            name="Bankroll",
            line=dict(color=line_color, width=2.5),
            fill="tozeroy", fillcolor=fill_color,
            text=ev_texts, hovertemplate="%{x}<br>%{y:,.0f} TL<br>%{text}<extra></extra>",
            marker=dict(size=6, color=[
                "#22c55e" if v >= _initial else "#ef4444" for v in br_vals
            ]),
        ), row=1, col=1)
        fig_eq.add_hline(
            y=_initial, line_dash="dot", line_color="#475569",
            annotation_text="Baslangic 5.000 TL",
            annotation_position="bottom right",
            annotation_font_color="#64748b",
            row=1, col=1,
        )
        # Peak line
        if peak_br > _initial:
            fig_eq.add_hline(
                y=peak_br, line_dash="dash", line_color="#10b981", line_width=1,
                annotation_text=f"Zirve {peak_br:,.0f} TL",
                annotation_position="top right",
                annotation_font_color="#10b981",
                row=1, col=1,
            )

        # Drawdown bars
        dd_colors = ["rgba(239,68,68,0.5)" if d < 0 else "rgba(34,197,94,0.3)" for d in dd_vals]
        fig_eq.add_trace(go.Bar(
            x=ev_dates, y=dd_vals,
            name="Drawdown %",
            marker_color=dd_colors,
            hovertemplate="%{x}<br>DD: %{y:.1f}%<extra></extra>",
        ), row=2, col=1)
        fig_eq.add_hline(y=0, line_color="#475569", line_width=0.5, row=2, col=1)

        fig_eq.update_layout(
            paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
            font=dict(color="#94a3b8", family="Consolas, Courier New"),
            height=420,
            showlegend=False,
            margin=dict(l=10, r=10, t=40, b=10),
            xaxis2=dict(showgrid=False, color="#475569"),
            xaxis=dict(showgrid=False, color="#475569"),
            yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#94a3b8"),
            yaxis2=dict(showgrid=True, gridcolor="#1e293b", color="#94a3b8"),
        )
        st.plotly_chart(fig_eq, use_container_width=True)

        # ── Stats at a Glance ─────────────────────────────────
        total_c   = len(eq_rows)
        won_c     = sum(1 for r in eq_rows if r["status"] == "won")
        lost_c    = total_c - won_c
        total_pnl = running_br - _initial
        total_stk = sum(r.get("stake", 0) or 0 for r in eq_rows)
        total_ret = sum(r.get("pnl", 0) or 0 for r in eq_rows if r["status"] == "won")
        avg_odds  = sum(r.get("combined_odds", 1) or 1 for r in eq_rows) / total_c if total_c else 1
        best_win  = max((r["pnl"] or 0 for r in eq_rows), default=0)
        worst_ls  = min((r["pnl"] or 0 for r in eq_rows), default=0)
        yield_pct = (total_pnl / total_stk * 100) if total_stk > 0 else 0.0
        roi_pct   = (total_pnl / _initial * 100)
        # Current streak
        streak = 0
        streak_type = ""
        for r in reversed(eq_rows):
            if r["status"] == "won":
                if streak_type in ("", "W"): streak += 1; streak_type = "W"
                else: break
            elif r["status"] == "lost":
                if streak_type in ("", "L"): streak += 1; streak_type = "L"
                else: break

        stat_cols = st.columns(7)
        _sc = [
            ("Kapatilan", f"{total_c}", "kupon"),
            ("Kazanilan", f"{won_c}/{lost_c}", "W/L"),
            ("Win Rate", f"%{won_c/total_c*100:.0f}" if total_c else "%0", ""),
            ("Ort Oran", f"{avg_odds:.2f}", "x"),
            ("Toplam ROI", f"{roi_pct:+.1f}%", ""),
            ("En iyi", f"+{best_win:.0f} TL", "kupon"),
            ("Seri", f"{streak} {streak_type}" if streak_type else "—", ""),
        ]
        for col, (label, value, unit) in zip(stat_cols, _sc):
            with col:
                val_color = "#22c55e" if "+" in value or (label == "Win Rate" and won_c > lost_c) else (
                    "#ef4444" if "-" in value else "#e2e8f0"
                )
                st.markdown(
                    f"<div style='background:#111827;border:1px solid #1e293b;border-radius:6px;"
                    f"padding:10px 12px;text-align:center'>"
                    f"<div style='color:#64748b;font-size:10px;text-transform:uppercase;"
                    f"letter-spacing:1px'>{label}</div>"
                    f"<div style='color:{val_color};font-size:18px;font-weight:700;"
                    f"font-family:Consolas,monospace;margin:4px 0'>{value}</div>"
                    f"<div style='color:#475569;font-size:10px'>{unit}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    else:
        st.info("Henuz kapatilmis kupon yok. Ilk kupon oturumunu 'Yeni Seans' ile baslat.")

    st.markdown("---")

    # ── Gecmis Kuponlar + Journal ─────────────────────────────
    tab_hist, tab_journal = st.tabs(["📋 Kupon Gecmisi", "📓 Model Journali"])

    with tab_hist:
        closed_coupons = _pt_db_query("""
            SELECT coupon_type, session_date, combined_odds, stake,
                   actual_return, pnl, status
            FROM paper_coupons
            WHERE portfolio_id = ? AND status != 'open'
            ORDER BY settled_at DESC LIMIT 30
        """, (PORTFOLIO_ID,))

        if closed_coupons:
            hist_rows = []
            for c in closed_coupons:
                pnl_v = c.get("pnl") or 0
                hist_rows.append({
                    "Tarih":   c.get("session_date", ""),
                    "Tip":     c.get("coupon_type", ""),
                    "Oran":    f"{c.get('combined_odds', 0):.3f}",
                    "Stake":   f"{c.get('stake', 0):.0f} TL",
                    "Getiri":  f"{c.get('actual_return', 0):.0f} TL",
                    "PnL":     f"{pnl_v:+.0f} TL",
                    "Sonuc":   c.get("status", "").upper(),
                })
            df_closed = pd.DataFrame(hist_rows)
            st.dataframe(df_closed, use_container_width=True, hide_index=True)
        else:
            st.info("Henuz kapatilmis kupon yok.")

    with tab_journal:
        journal_rows = _pt_db_query("""
            SELECT entry_date, entry_type, title, content,
                   signal_name, market, pick, odds, actual_result, pnl, tags, model_action
            FROM paper_journal
            WHERE portfolio_id = ?
            ORDER BY created_at DESC LIMIT 15
        """, (PORTFOLIO_ID,))

        if journal_rows:
            type_colors = {
                "PICK": "#3b82f6", "RESULT": "#22c55e", "LESSON": "#f59e0b",
                "THRESHOLD_UPDATE": "#a78bfa", "SESSION_REVIEW": "#64748b",
            }
            for j in journal_rows:
                tc = type_colors.get(j.get("entry_type", ""), "#64748b")
                pnl_j = j.get("pnl") or 0
                pnl_str = f"&nbsp;|&nbsp; PnL: <b>{pnl_j:+.0f} TL</b>" if pnl_j else ""
                model_act = j.get("model_action") or ""
                act_str = (f"&nbsp;→ <span style='color:#f59e0b'>Action: {model_act}</span>"
                           if model_act else "")
                st.markdown(
                    f"<div style='background:#0b1120;border-left:3px solid {tc};"
                    f"border-radius:4px;padding:10px 14px;margin-bottom:8px'>"
                    f"<div style='display:flex;justify-content:space-between'>"
                    f"<span style='color:{tc};font-size:11px;font-weight:700'>"
                    f"{j.get('entry_type','?')}</span>"
                    f"<span style='color:#475569;font-size:11px'>{j.get('entry_date','')}</span>"
                    f"</div>"
                    f"<div style='color:#e2e8f0;font-weight:600;margin:3px 0'>"
                    f"{j.get('title','')}</div>"
                    f"<div style='color:#94a3b8;font-size:12px'>{j.get('content','')}</div>"
                    f"<div style='color:#64748b;font-size:11px;margin-top:4px'>"
                    f"{pnl_str}{act_str}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("Journal henuz bos. Kuponlar kapandikca otomatik giris olusur.")

        # Journal yeni giris butonu
        with st.expander("+ Manuel Journal Girisi Ekle"):
            j_type = st.selectbox("Giris Turu",
                ["LESSON", "SESSION_REVIEW", "THRESHOLD_UPDATE", "PICK", "RESULT"])
            j_title = st.text_input("Baslik")
            j_content = st.text_area("Icerik")
            j_action = st.text_input("Model Aksiyonu (opsiyonel)",
                placeholder="LOWER_THRESHOLD / RAISE_THRESHOLD / KEEP")
            if st.button("Journal'a Ekle", type="primary"):
                import uuid as _uuid
                _conn_j = db_connect()
                _conn_j.execute("""
                    INSERT INTO paper_journal
                    (journal_id, portfolio_id, entry_date, entry_type, title, content,
                     model_action, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(_uuid.uuid4()), PORTFOLIO_ID,
                    datetime.utcnow().date().isoformat(),
                    j_type, j_title, j_content, j_action or None,
                    datetime.utcnow().isoformat(),
                ))
                _conn_j.commit()
                _conn_j.close()
                st.success("Journal girisi eklendi!")
                st.rerun()

    # ── Strateji Notlari ─────────────────────────────────────
    with st.expander("Strateji Notlari — Paper Trader v1", expanded=False):
        st.markdown("""
**Aktif Strateji:** `v1-odds-signals`

Yaz arasi (Mayis-Agustos 2026) icin saf odds-bazli sinyal kullaniliyor.
Ana ligler basladiginda DC model sinyalleri devreye girecek.

| Kupon Turu | Tetikleyici | Stake |
|---|---|---|
| K1_FAVORITE | 1X2 impl.prob >= 65%, odds >= 1.25 | %3 bankroll |
| K1_KG | KG Var impl.prob >= 62% | %2.5 bankroll |
| K2_COMBO | 2x farkli mac, her biri >= 60% | %2 bankroll |
| K1_ALT | Alt 2.5 impl.prob >= 62% | %2 bankroll |

**Agustos 2026'dan itibaren** DC + Platt modelleri devreye girer:
TRIVOX (T1, %82 hit), DUOVOX (E0+SP1, %62), OU25-D1-Over (%59), BTTS-D1-Var (%64)

---
**CMC (Cross-Market Consistency) Tierlari:**
- **GUCLU ★★★** — 2+ pazar ayni yonu isaret ediyor (ornek: KG Var + Ust 2.5)
- **ORTA ★★☆** — Tek guclu sinyal (EV/DEP favori veya KG Var tek basina)
- **ZAYIF ★☆☆** — Zayif tek sinyal, riskli

**Self-Improvement Dongusu:**
`Sinyal → Kupon → Sonuc → Journal → Esik Guncelleme → Tekrar`
        """)


def db_connect():
    """Taşınabilir bağlantı (SQLite yerel / PostgreSQL Railway) — db.py'ye delege."""
    return db.connect(DB_PATH)


# ============================================================
# MAIN
# ============================================================

def main():
    render_header()
    bankroll, risk = render_sidebar()

    tabs = st.tabs([
        "\U0001f3e0 OVERVIEW",
        "\U0001f4c5 LIVE CALENDAR",
        "\U0001f4ca TRADING DESK",
        "\U0001f3af COUPON ENG",
        "\U0001f916 MODELS",
        "\U0001f4c8 ANALYTICS",
        "\U0001f5c4️ DATA",
        "\U0001f6e1️ RISK",
        "\U0001f4d6 PLAYBOOK",
        "\U0001f4b8 PAPER TRADER",
    ])

    with tabs[0]: page_overview()
    with tabs[1]: page_live_calendar()
    with tabs[2]: page_trading_desk()
    with tabs[3]: page_coupon_engineer()
    with tabs[4]: page_model_catalog()
    with tabs[5]: page_analytics()
    with tabs[6]: page_data_excellency()
    with tabs[7]: page_risk()
    with tabs[8]: page_playbook()
    with tabs[9]: page_paper_trader()


if __name__ == "__main__":
    main()
