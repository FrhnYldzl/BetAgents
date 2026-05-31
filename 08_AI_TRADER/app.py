"""
AI TRADER v0.1 — Streamlit MVP UI
====================================

Digital Twin Trader prototip arayuz.

5 ana sayfa:
  1) Dashboard      — 5 model ozet metrikler
  2) Hafta Picks    — Q5+a2 sniper onerileri
  3) Model Arena    — Karsilastirma + Bonferroni
  4) Sinyaller      — s_shots/s_referee/s_cards detay
  5) Sezon & CLV    — Trend + CLV analiz

Calistir: streamlit run app.py
"""
from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
sys.path.insert(0, str(YAZILIM / "02_VERI"))


DB_PATH = YAZILIM / "02_VERI" / "bahis_agent.db"

SEASON_CONV = {
    "1718":"2017-18","1819":"2018-19","1920":"2019-20","2021":"2020-21",
    "2122":"2021-22","2223":"2022-23","2324":"2023-24","2425":"2024-25","2526":"2025-26",
}


# ============================================================
# STYLING
# ============================================================

st.set_page_config(
    page_title="AI TRADER — Digital Twin",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* Modern theme */
    .stApp {
        background-color: #0f172a;
        color: #e2e8f0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stMetric {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 16px;
    }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 28px;
        font-weight: 700;
    }
    .stMetric [data-testid="stMetricLabel"] {
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .pick-card {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        margin: 8px 0;
    }
    .pick-allin {
        border-left: 4px solid #10b981;
    }
    .pick-standart {
        border-left: 4px solid #f59e0b;
    }
    .pick-warning {
        border-left: 4px solid #ef4444;
    }
    h1, h2, h3 {
        color: #f8fafc;
    }
    .stDataFrame {
        background-color: #1e293b;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING (cached)
# ============================================================

@st.cache_data(ttl=300)
def load_signal_snapshots():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM signal_snapshots
        WHERE source='football_data'
    """, conn)
    conn.close()
    df["season_canon"] = df["season"].astype(str).map(lambda s: SEASON_CONV.get(s, s))
    df["matchday"] = pd.to_datetime(df["kickoff_iso"]).dt.strftime("%Y-%m-%d")
    return df


@st.cache_data(ttl=300)
def load_matches_v2():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM matches_v2 WHERE is_settled=1
    """, conn)
    conn.close()
    return df


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
# SIDEBAR
# ============================================================

with st.sidebar:
    st.markdown("# 🎯 AI TRADER")
    st.caption("Digital Twin Trader v0.1")
    st.markdown("---")
    page = st.radio(
        "Sayfa",
        ["🏠 Dashboard", "📅 Haftanın Picks", "🤖 Model Arena",
         "📊 Sinyaller", "📈 Sezon & CLV", "ℹ️ Hakkında"],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.caption("**Bankroll**")
    bankroll = st.number_input("Mevcut bankroll (TL)", value=10000, step=1000)
    risk = st.select_slider(
        "Risk profili",
        options=["Konservatif", "Orta", "Agresif"],
        value="Orta",
    )
    st.markdown("---")
    st.caption("**Veri Durumu**")
    df_ss = load_signal_snapshots()
    n_total = len(df_ss[df_ss["settled"]==1])
    st.metric("Settled match", f"{n_total:,}")
    n_with_v14 = df_ss["score_v14"].notna().sum()
    st.metric("score_v14", f"{n_with_v14:,}")


df = df_ss[df_ss["settled"]==1].copy()


# ============================================================
# 1) DASHBOARD
# ============================================================

if page == "🏠 Dashboard":
    st.title("🎯 Dashboard — AI Trader v0.1")
    st.caption("Digital Twin Trader · Sürekli iyileşen edge sistemi")

    # KPI cards
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Toplam Sample", f"{len(df):,}",
                  delta=f"+{len(df)-10657:,} (Sezon A)")
    with col2:
        n_sezon = df["season_canon"].nunique()
        st.metric("Aktif Sezon", n_sezon, delta="9 sezon (9K+8.5K)")
    with col3:
        n_lig = df["league_code"].nunique()
        st.metric("Lig Sayısı", n_lig, delta="6 lig")
    with col4:
        ssh = df["s_shots"].notna().sum()
        st.metric("Yeni Sinyaller", "3", delta=f"shots {ssh*100//len(df)}% cov")

    st.markdown("---")
    st.subheader("📊 5 Model Q5+a2 Sniper — Tarihsel Hit Rate")

    # Compute Q5+a2 hit per model
    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]

    model_data = []
    for name, leagues in models:
        sub_lig = df[df["league_code"].isin(leagues)].copy()
        sub_lig["dir_fc"] = sub_lig.apply(
            lambda r: fav_confirmed(r.to_dict(), 1), axis=1
        )
        sub_lig = sub_lig[sub_lig["dir_fc"].notna()].copy()
        sub_lig = sub_lig.sort_values("score_v14", ascending=False)
        # K=1 picks
        picks = []
        for (md, lg), group in sub_lig.groupby(["matchday", "league_code"]):
            top = group.head(1)
            for _, leg in top.iterrows():
                d = leg["dir_fc"]
                o = get_odd(leg.to_dict(), d)
                if not o or o < 1.01: continue
                d_n = normalize_dir(d)
                won = leg.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_n]
                picks.append({
                    "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                    "agree": int(leg["agree_count"] or 0),
                    "odd": o, "won": won,
                })
        if not picks: continue
        df_p = pd.DataFrame(picks)
        try:
            df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"],
                               duplicates="drop")
        except:
            continue
        q5a2 = df_p[(df_p["q"]=="Q5") & (df_p["agree"]>=2)]
        n = len(q5a2)
        hit = q5a2["won"].mean()*100 if n else 0
        model_data.append({"Model": name, "Q5+a2 n": n,
                          "Hit %": f"{hit:.0f}%", "Avg Odd": f"{q5a2['odd'].mean():.2f}" if n else "-"})

    df_models = pd.DataFrame(model_data)
    st.dataframe(df_models, use_container_width=True, hide_index=True)

    # Bonferroni evidence
    st.markdown("---")
    st.subheader("🎉 Bonferroni Doğrulandı — V2 19K Sample")
    st.success("**3/5 model Bonferroni-significant edge** (p < 0.0025):\n\n"
               "- **DUOVOX**: p=0.0000 ⭐⭐⭐\n"
               "- **TRIOVOX**: p=0.0001 ⭐⭐⭐\n"
               "- **MONOVOX-E0**: p=0.0017 ⭐⭐⭐\n"
               "- TRIVOX: p=0.0071 (%1 anlamlı)\n"
               "- MONOVOX-SP1: p=0.0081 (%1 anlamlı)")

    # Quick stats
    st.markdown("---")
    st.subheader("📈 Sezon Dağılımı")
    sezon_dist = df.groupby("season_canon").size().reset_index(name="n")
    fig = px.bar(sezon_dist, x="season_canon", y="n",
                color="n", color_continuous_scale="Viridis",
                title="Sezon başına maç sayısı (19K dağıtım)")
    fig.update_layout(plot_bgcolor="#1e293b", paper_bgcolor="#0f172a",
                     font=dict(color="#e2e8f0"))
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 2) HAFTALIK PICKS (mock for now — 2025-26 sezonu içinde)
# ============================================================

elif page == "📅 Haftanın Picks":
    st.title("📅 Haftanın Picks")
    st.caption("Q5+agree2 selective sniper önerileri")

    # En son sezondan picks
    df_recent = df[df["season_canon"] == "2025-26"].copy()
    if df_recent.empty:
        df_recent = df[df["season_canon"] == "2024-25"].copy()

    st.info(f"📌 Sample sezonu: {df_recent['season_canon'].iloc[0] if len(df_recent) else 'YOK'}, "
            f"{len(df_recent)} maç")

    # Apply FAV_CONFIRMED + score_v14 sort
    df_recent["dir_fc"] = df_recent.apply(
        lambda r: fav_confirmed(r.to_dict(), 1), axis=1
    )
    df_recent = df_recent[df_recent["dir_fc"].notna()].copy()
    df_recent["odd_used"] = df_recent.apply(
        lambda r: get_odd(r.to_dict(), r["dir_fc"]), axis=1
    )
    df_recent = df_recent[df_recent["odd_used"].notna()].copy()
    df_recent = df_recent.sort_values("score_v14", ascending=False)

    # K=1 picks (top-1 per matchday × league)
    picks = []
    for (md, lg), group in df_recent.groupby(["matchday","league_code"]):
        top = group.head(1)
        for _, leg in top.iterrows():
            picks.append({
                "matchday": md, "league": lg,
                "home": leg["home_team"], "away": leg["away_team"],
                "direction": leg["dir_fc"],
                "odd": leg["odd_used"],
                "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                "agree": int(leg["agree_count"] or 0),
                "result": leg.get("result_1x2"),
                "settled": leg["settled"],
            })

    df_picks = pd.DataFrame(picks)
    if df_picks.empty:
        st.warning("Pick yok bu sezonda.")
    else:
        # Quintile
        try:
            df_picks["quintile"] = pd.qcut(df_picks["score"], 5,
                                           labels=["Q1","Q2","Q3","Q4","Q5"],
                                           duplicates="drop")
        except:
            df_picks["quintile"] = "?"

        # Pozisyon kategori
        def pos_category(r):
            if r["quintile"] == "Q5" and r["agree"] >= 2:
                return "ALL-IN", 5
            elif r["quintile"] == "Q5":
                return "BÜYÜK", 3
            elif r["quintile"] == "Q4":
                return "STANDART", 1
            elif r["quintile"] == "Q3" and r["agree"] >= 2:
                return "KÜÇÜK", 0.5
            else:
                return "PAS", 0

        df_picks[["category","multiplier"]] = df_picks.apply(
            lambda r: pd.Series(pos_category(r)), axis=1
        )
        df_picks["stake_tl"] = (bankroll * 0.01 * df_picks["multiplier"]).astype(int)

        # ALL-IN
        all_in = df_picks[df_picks["category"]=="ALL-IN"].head(20)
        if not all_in.empty:
            st.subheader(f"🔥 ALL-IN ({len(all_in)})")
            for _, p in all_in.iterrows():
                won_marker = ("✅" if p["result"]=="H" and p["direction"] in ("HOME","H","1")
                              else "✅" if p["result"]=="D" and p["direction"] in ("DRAW","D","X")
                              else "✅" if p["result"]=="A" and p["direction"] in ("AWAY","A","2")
                              else ("❌" if p["settled"] else "⏳"))
                with st.container():
                    cols = st.columns([4, 1, 1, 1, 1])
                    cols[0].markdown(f"**{p['home']} - {p['away']}** ({p['league']}, {p['matchday']})")
                    cols[1].metric("Yön", normalize_dir(p["direction"]))
                    cols[2].metric("Oran", f"{p['odd']:.2f}")
                    cols[3].metric("Stake", f"{p['stake_tl']:,} TL")
                    cols[4].markdown(f"### {won_marker}")
                    st.caption(f"Score: {p['score']:.3f} · Agree: {p['agree']}/4")
                    st.markdown("---")

        # STANDART/BUYUK
        std = df_picks[df_picks["category"].isin(["BÜYÜK","STANDART"])].head(15)
        if not std.empty:
            st.subheader(f"⭐ BÜYÜK + STANDART ({len(std)})")
            st.dataframe(std[["matchday","league","home","away","direction","odd",
                            "category","stake_tl","agree","result"]],
                       use_container_width=True, hide_index=True)


# ============================================================
# 3) MODEL ARENA
# ============================================================

elif page == "🤖 Model Arena":
    st.title("🤖 Model Arena")
    st.caption("15 model versiyonu — eski vs yeni paradigma")

    # Show Q5+a2 comparison for 5 main models
    st.subheader("🏆 5 Ana Model Q5+a2 — 19K Sample")

    models = [
        ("TRIVOX (T1)", ["T1"]),
        ("MONOVOX-E0", ["E0"]),
        ("DUOVOX (E0+SP1)", ["E0","SP1"]),
        ("TRIOVOX (E0+SP1+D1)", ["E0","SP1","D1"]),
        ("MONOVOX-SP1", ["SP1"]),
    ]

    arena_data = []
    for name, leagues in models:
        sub_lig = df[df["league_code"].isin(leagues)].copy()
        sub_lig["dir_fc"] = sub_lig.apply(
            lambda r: fav_confirmed(r.to_dict(), 1), axis=1
        )
        sub_lig = sub_lig[sub_lig["dir_fc"].notna()].copy()
        sub_lig = sub_lig.sort_values("score_v14", ascending=False)
        picks = []
        for (md, lg), group in sub_lig.groupby(["matchday","league_code"]):
            top = group.head(1)
            for _, leg in top.iterrows():
                d = leg["dir_fc"]
                o = get_odd(leg.to_dict(), d)
                if not o or o < 1.01: continue
                d_n = normalize_dir(d)
                won = leg.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_n]
                picks.append({
                    "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                    "agree": int(leg["agree_count"] or 0),
                    "odd": o, "won": won,
                    "season": leg["season_canon"],
                })
        if not picks: continue
        df_p = pd.DataFrame(picks)
        try:
            df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"],
                               duplicates="drop")
        except: continue
        # K=1 baseline
        n_all = len(df_p)
        hit_all = df_p["won"].mean()*100
        # Q5+a2
        q5a2 = df_p[(df_p["q"]=="Q5") & (df_p["agree"]>=2)]
        n_q5 = len(q5a2)
        hit_q5 = q5a2["won"].mean()*100 if n_q5 else 0
        avg_odd_q5 = q5a2["odd"].mean() if n_q5 else 0
        edge_q5 = (hit_q5/100 - 1/avg_odd_q5)*100 if avg_odd_q5 else 0
        arena_data.append({
            "Model": name,
            "K=1 n": n_all,
            "K=1 hit": f"{hit_all:.0f}%",
            "Q5+a2 n": n_q5,
            "Q5+a2 hit": f"{hit_q5:.0f}%",
            "Q5+a2 odd": f"{avg_odd_q5:.2f}",
            "Q5+a2 edge": f"{edge_q5:+.1f}pp",
        })

    df_arena = pd.DataFrame(arena_data)
    st.dataframe(df_arena, use_container_width=True, hide_index=True)

    # Plot — Q5 hit rate per model
    st.markdown("---")
    st.subheader("📊 Q5 Hit Rate per Sezon (heatmap)")

    heatmap_data = []
    seasons_order = ["2017-18","2018-19","2019-20","2020-21","2021-22",
                     "2022-23","2023-24","2024-25","2025-26"]
    for name, leagues in models:
        sub_lig = df[df["league_code"].isin(leagues)].copy()
        sub_lig["dir_fc"] = sub_lig.apply(
            lambda r: fav_confirmed(r.to_dict(), 1), axis=1
        )
        sub_lig = sub_lig[sub_lig["dir_fc"].notna()].copy()
        sub_lig = sub_lig.sort_values("score_v14", ascending=False)
        picks = []
        for (md, lg), group in sub_lig.groupby(["matchday","league_code"]):
            top = group.head(1)
            for _, leg in top.iterrows():
                d = leg["dir_fc"]
                o = get_odd(leg.to_dict(), d)
                if not o or o < 1.01: continue
                d_n = normalize_dir(d)
                won = leg.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_n]
                picks.append({
                    "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                    "season": leg["season_canon"],
                    "won": won,
                })
        if not picks: continue
        df_p = pd.DataFrame(picks)
        try:
            df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"],
                               duplicates="drop")
        except: continue
        q5 = df_p[df_p["q"]=="Q5"]
        for ss in seasons_order:
            sub = q5[q5["season"]==ss]
            if len(sub) >= 5:
                hit = sub["won"].mean()*100
                heatmap_data.append({"Model": name, "Sezon": ss, "Hit%": hit, "n": len(sub)})

    if heatmap_data:
        df_hm = pd.DataFrame(heatmap_data)
        pivot = df_hm.pivot_table(index="Model", columns="Sezon", values="Hit%")
        fig = go.Figure(data=go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=[[0, '#1e293b'], [0.5, '#f59e0b'], [1, '#10b981']],
            text=[[f"{v:.0f}%" if pd.notna(v) else "" for v in row] for row in pivot.values],
            texttemplate="%{text}", textfont={"size": 12},
            zmin=40, zmax=90,
        ))
        fig.update_layout(
            title="Q5 Hit Rate × Model × Sezon",
            plot_bgcolor="#1e293b", paper_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"), height=400,
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 4) SİNYALLER
# ============================================================

elif page == "📊 Sinyaller":
    st.title("📊 Sinyaller — Detay Analiz")
    st.caption("9 sinyal (5 klasik + 3 match stats + 1 ek)")

    st.subheader("🎯 Yeni 3 Sinyal Edge")

    signal_data = [
        {"Sinyal": "s_shots HOME", "Coverage": "Shots-form HOME yön", "n": 6468,
         "hit%": 59, "baseline%": 53.6, "edge": "+5.06pp", "Durum": "✅ Anlamlı"},
        {"Sinyal": "s_shots AWAY", "Coverage": "Shots-form AWAY yön", "n": 7515,
         "hit%": 43, "baseline%": 35.6, "edge": "+7.40pp", "Durum": "⭐ Güçlü"},
        {"Sinyal": "s_referee HOME", "Coverage": "Hakem ev-bias", "n": 572,
         "hit%": 48, "baseline%": 32.8, "edge": "+15.30pp", "Durum": "🔥 ÇOK GÜÇLÜ"},
        {"Sinyal": "s_referee AWAY", "Coverage": "Hakem dep-bias", "n": 1059,
         "hit%": 34, "baseline%": 21.2, "edge": "+12.45pp", "Durum": "🔥 ÇOK GÜÇLÜ"},
        {"Sinyal": "s_cards DRAW", "Coverage": "Gergin maç DRAW", "n": 340,
         "hit%": 24, "baseline%": 25.3, "edge": "-0.87pp", "Durum": "❌ Zayıf"},
    ]
    st.dataframe(pd.DataFrame(signal_data), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("🔥 BÜYÜK BULGU — Referee Bias")
    st.success("""
    Hakem geçmiş eğilimi tek başına **+%12-15 edge** veriyor!
    Bu, müstakil bir mikro-model olarak değerlendirilebilir.

    Sample 572-1059 maç istatistiksel olarak anlamlı.
    """)

    # Score distribution
    st.markdown("---")
    st.subheader("📈 Score_v14 Dağılımı")
    fig = px.histogram(df[df["score_v14"].notna() & (df["score_v14"] > 0)],
                      x="score_v14", nbins=50,
                      title="Score_v14 dağılımı (19K sample)")
    fig.update_layout(plot_bgcolor="#1e293b", paper_bgcolor="#0f172a",
                     font=dict(color="#e2e8f0"))
    st.plotly_chart(fig, use_container_width=True)

    # Signal coverage breakdown
    st.markdown("---")
    st.subheader("📊 Sinyal Coverage")
    coverage_data = []
    for sig in ["s_anomaly", "s_model", "s_xg", "s_form", "s_shots", "s_referee", "s_cards"]:
        if sig in df.columns:
            n = ((df[sig].notna()) & (df[sig] > 0)).sum()
            coverage_data.append({
                "Sinyal": sig.replace("s_", "").upper(),
                "Coverage": f"{n}/{len(df)} ({n/len(df)*100:.0f}%)",
                "n_active": int(n),
            })
    df_cov = pd.DataFrame(coverage_data)
    st.dataframe(df_cov, use_container_width=True, hide_index=True)


# ============================================================
# 5) SEZON & CLV
# ============================================================

elif page == "📈 Sezon & CLV":
    st.title("📈 Sezon Trendleri & CLV")
    st.caption("9 sezon stabilite + CLV ölçümü")

    # Sezon-by-sezon hit rate (TRIVOX örneği)
    st.subheader("📊 9 Sezon Q5 Hit Rate Trendi")

    model_sel = st.selectbox(
        "Model seç",
        ["TRIVOX (T1)", "MONOVOX-E0", "DUOVOX (E0+SP1)", "TRIOVOX (E0+SP1+D1)", "MONOVOX-SP1"]
    )
    league_map = {
        "TRIVOX (T1)": ["T1"], "MONOVOX-E0": ["E0"],
        "DUOVOX (E0+SP1)": ["E0","SP1"],
        "TRIOVOX (E0+SP1+D1)": ["E0","SP1","D1"],
        "MONOVOX-SP1": ["SP1"],
    }
    leagues = league_map[model_sel]

    sub_lig = df[df["league_code"].isin(leagues)].copy()
    sub_lig["dir_fc"] = sub_lig.apply(
        lambda r: fav_confirmed(r.to_dict(), 1), axis=1
    )
    sub_lig = sub_lig[sub_lig["dir_fc"].notna()].copy()
    sub_lig = sub_lig.sort_values("score_v14", ascending=False)
    picks = []
    for (md, lg), group in sub_lig.groupby(["matchday","league_code"]):
        top = group.head(1)
        for _, leg in top.iterrows():
            d = leg["dir_fc"]
            o = get_odd(leg.to_dict(), d)
            if not o or o < 1.01: continue
            d_n = normalize_dir(d)
            won = leg.get("result_1x2") == {"HOME":"H","AWAY":"A","DRAW":"D"}[d_n]
            picks.append({
                "score": float(leg["score_v14"]) if pd.notna(leg["score_v14"]) else 0,
                "season": leg["season_canon"],
                "won": won,
            })

    if picks:
        df_p = pd.DataFrame(picks)
        df_p["q"] = pd.qcut(df_p["score"], 5, labels=["Q1","Q2","Q3","Q4","Q5"],
                           duplicates="drop")
        q5 = df_p[df_p["q"]=="Q5"]
        seasons_order = ["2017-18","2018-19","2019-20","2020-21","2021-22",
                        "2022-23","2023-24","2024-25","2025-26"]
        trend_data = []
        for ss in seasons_order:
            sub = q5[q5["season"]==ss]
            if len(sub) >= 5:
                trend_data.append({
                    "season": ss, "n": len(sub),
                    "hit": sub["won"].mean()*100
                })
        df_t = pd.DataFrame(trend_data)
        if not df_t.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_t["season"], y=df_t["hit"],
                                marker_color="#10b981",
                                text=[f"%{h:.0f} ({n})" for h,n in zip(df_t["hit"], df_t["n"])],
                                textposition="outside"))
            fig.add_hline(y=66, line_dash="dash", line_color="#f59e0b",
                         annotation_text="Hedef %66")
            fig.add_hline(y=50, line_dash="dot", line_color="#ef4444",
                         annotation_text="Breakeven")
            fig.update_layout(
                title=f"{model_sel} — Q5 Hit Rate per Sezon",
                yaxis_title="Hit %", xaxis_title="Sezon",
                plot_bgcolor="#1e293b", paper_bgcolor="#0f172a",
                font=dict(color="#e2e8f0"),
                yaxis=dict(range=[40, 100]),
            )
            st.plotly_chart(fig, use_container_width=True)

    # CLV Analizi
    st.markdown("---")
    st.subheader("📊 CLV (Closing Line Value)")
    st.info("""
    **CLV = (opening_odd / closing_odd) - 1**

    Pozitif CLV = piyasayı yenmek (sharp money ile aynı yönde)
    Negatif CLV = favori-bias (modelin edge'i piyasa-yenmekten gelmiyor)
    """)

    # matches_v2'den CLV özet
    try:
        conn = sqlite3.connect(DB_PATH)
        clv_df = pd.read_sql_query("""
            SELECT league_code,
                   COUNT(*) as n,
                   AVG(clv_home) as clv_h,
                   AVG(clv_draw) as clv_d,
                   AVG(clv_away) as clv_a,
                   AVG(clv_over25) as clv_o,
                   AVG(clv_under25) as clv_u
            FROM matches_v2 WHERE has_clv=1
            GROUP BY league_code ORDER BY league_code
        """, conn)
        conn.close()

        if not clv_df.empty:
            st.dataframe(
                clv_df.assign(**{
                    "clv_h": clv_df["clv_h"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-"),
                    "clv_d": clv_df["clv_d"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-"),
                    "clv_a": clv_df["clv_a"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-"),
                    "clv_o": clv_df["clv_o"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-"),
                    "clv_u": clv_df["clv_u"].apply(lambda x: f"{x*100:+.2f}%" if pd.notna(x) else "-"),
                })[["league_code","n","clv_h","clv_d","clv_a","clv_o","clv_u"]]
                .rename(columns={"league_code":"Lig","clv_h":"CLV-H","clv_d":"CLV-X",
                               "clv_a":"CLV-A","clv_o":"CLV-Ust","clv_u":"CLV-Alt"}),
                use_container_width=True, hide_index=True
            )
    except Exception as e:
        st.error(f"CLV yüklenemedi: {e}")


# ============================================================
# 6) HAKKINDA
# ============================================================

elif page == "ℹ️ Hakkında":
    st.title("ℹ️ Hakkında")
    st.markdown("""
    ## AI TRADER v0.1 — Digital Twin Trader

    **Vizyon:** Trader'ın yanında olan, her hafta ne yapacağını söyleyen,
    kararlarından öğrenen, kendi edge'ini sürekli geliştiren AI partner.

    ### Mevcut Durum
    - **Veri**: 19,198 maç (9 sezon × 6 lig)
    - **5 Model**: TRIVOX, MONOVOX-E0, DUOVOX, TRIOVOX, MONOVOX-SP1
    - **9 Sinyal**: anomaly, model, xG, form, sharp, invvar, shots, referee, cards
    - **2 Score**: score_v13 (eski 4-6 sinyal), score_v14 (yeni 9 sinyal)

    ### Bonferroni Doğrulandı (V2 19K)
    - DUOVOX: p=0.0000 ⭐⭐⭐
    - TRIOVOX: p=0.0001 ⭐⭐⭐
    - MONOVOX-E0: p=0.0017 ⭐⭐⭐

    ### Trader Stratejisi
    - **Q5 + agree2** → SNIPER (ALL-IN)
    - **Q5 + agree1** → BÜYÜK
    - **Q4** → STANDART
    - **Q3 + agree2** → KÜÇÜK
    - **Q1-Q2** → PAS

    ### Yol Haritası
    1. ✅ V2 19K sample + Bonferroni
    2. ✅ score_v14 + 3 yeni sinyal
    3. 🔄 UI MVP (bu sayfa)
    4. ⏳ Multi-market V2 (A/Ü 2.5)
    5. ⏳ V2 model retrain
    6. ⏳ FotMob T1 xG
    7. ⏳ Telegram bot + voice
    8. ⏳ 2026-27 live shadow run

    ### Dokümanlar
    Tüm strateji dokümanları `YAZILIM/RAPOR/v2_*.md` altında.

    ---
    *Built with ❤️ for the trader.*
    """)


# ============================================================
# FOOTER
# ============================================================

st.sidebar.markdown("---")
st.sidebar.caption("**v0.1** — MVP prototype")
st.sidebar.caption(f"Data updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}")
