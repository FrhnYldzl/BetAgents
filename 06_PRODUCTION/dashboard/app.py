"""
BAHIS AGENT — iddaa.com SaaS + Bloomberg-style görsel zenginlik

Renk dili : iddaa yeşili (#00B14F) + sarı vurgu + açık beyaz zemin
Yapı      : iddaa.com bülteni (sol fixture'lar) + Kuponum (sağ) + alt veri panelleri
Vurgu     : SaaS profesyonel, Bloomberg veri zenginliği, hikaye anlatıcı
"""
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
YAZILIM_DIR = THIS_DIR.parent.parent
sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER"))
sys.path.insert(0, str(YAZILIM_DIR / "02_VERI"))

from base.dixon_coles import DCParams, score_matrix
from base.markets import (
    prob_1x2, prob_over_under, prob_btts,
    prob_handicap, prob_first_half_1x2, prob_first_half_over_under,
    prob_ht_ft, prob_double_chance, top_n_scores,
)
import database as db

# Sprint 2.4 — Risk yönetimi
sys.path.insert(0, str(YAZILIM_DIR / "05_RISK_YONETIMI"))
from risk_manager import (
    overround, vig_adjusted_edge, calc_recommended_stake,
    combo_stake, RiskLimits,
)

# Sprint 2.3 — LLM Augmentation
try:
    from llm_features import extract_features_via_llm, LLM_MODE
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False
    LLM_MODE = "unavailable"

# Sprint 4 — SELECTIVE EDGE (v1.2 pure data)
sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER" / "selective"))
try:
    from selector import get_all_match_signals, select_top_n  # noqa: E402
    from combination_optimizer import optimize_combinations  # noqa: E402
    SELECTIVE_AVAILABLE = True
except Exception as _e:
    SELECTIVE_AVAILABLE = False
    _SELECTIVE_ERR = str(_e)

# ============================================================
# SAYFA YAPILANDIRMA
# ============================================================

st.set_page_config(
    page_title="BAHIS AGENT — Bu Haftanın Kuponları",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",  # hamburger AÇIK
    menu_items={"About": "BAHIS AGENT v0.6 — Kantitatif futbol analiz aracı"},
)

# ============================================================
# CSS — iddaa.com paleti + Bloomberg zenginlik
# ============================================================

CSS = """
<style>
/* BAHIS AGENT v0.6 — Premium SaaS — build 20260527-v2 — glassmorphism + dramatic */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    /* Brand — modern emerald (Linear/Stripe esinli) */
    --brand-50: #ECFDF5;
    --brand-100: #D1FAE5;
    --brand-200: #A7F3D0;
    --brand-300: #6EE7B7;
    --brand-400: #34D399;
    --brand-500: #10B981;   /* Ana brand — modern emerald */
    --brand-600: #059669;
    --brand-700: #047857;
    --brand-800: #065F46;
    --brand-900: #064E3B;

    /* Accent — warm coral (vurgu) */
    --accent-500: #F97316;
    --accent-600: #EA580C;

    /* Surface (Vercel-esinli soft palet) */
    --surface-0: #FFFFFF;
    --surface-50: #FAFAFA;
    --surface-100: #F4F4F5;
    --surface-150: #ECEDEF;
    --surface-200: #E4E4E7;
    --surface-300: #D4D4D8;

    /* Text (Linear-esinli kontrast) */
    --text-strong: #09090B;
    --text-primary: #18181B;
    --text-secondary: #52525B;
    --text-muted: #71717A;
    --text-disabled: #A1A1AA;

    /* Border */
    --border-subtle: #E4E4E7;
    --border-default: #D4D4D8;
    --border-strong: #A1A1AA;

    /* Status colors */
    --success: #10B981;
    --danger: #EF4444;
    --warning: #F59E0B;
    --info: #3B82F6;

    /* Shadows — multi-layer, Linear tarzı */
    --shadow-xs: 0 1px 2px rgba(0,0,0,0.04);
    --shadow-sm: 0 1px 2px rgba(0,0,0,0.04), 0 2px 4px rgba(0,0,0,0.04);
    --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.04), 0 2px 4px -2px rgba(0,0,0,0.03);
    --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.05), 0 4px 6px -4px rgba(0,0,0,0.04);
    --shadow-xl: 0 20px 25px -5px rgba(0,0,0,0.06), 0 8px 10px -6px rgba(0,0,0,0.04);
    --shadow-brand: 0 8px 24px -4px rgba(16, 185, 129, 0.15);
    --shadow-inner: inset 0 1px 2px rgba(0,0,0,0.04);

    /* Radius */
    --r-sm: 6px;
    --r-md: 10px;
    --r-lg: 14px;
    --r-xl: 18px;
    --r-2xl: 24px;
    --r-full: 9999px;

    /* Transition */
    --t-fast: 150ms;
    --t-base: 220ms;
    --t-slow: 350ms;

    /* Backward compat (eski class isimleri için) */
    --iddaa-green: var(--brand-500);
    --iddaa-green-dark: var(--brand-700);
    --iddaa-green-light: var(--brand-50);
    --iddaa-yellow: #FCD34D;
    --bg-white: var(--surface-0);
    --bg-soft: var(--surface-50);
    --bg-panel: var(--surface-100);
    --border: var(--border-subtle);
    --border-strong: var(--border-default);
    --text-primary: var(--text-primary);
    --text-secondary: var(--text-secondary);
    --text-muted: var(--text-muted);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--text-primary) !important;
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
}

.stApp {
    background:
        radial-gradient(at 0% 0%, rgba(16,185,129,0.06) 0%, transparent 40%),
        radial-gradient(at 100% 0%, rgba(99,102,241,0.04) 0%, transparent 45%),
        radial-gradient(at 80% 100%, rgba(245,158,11,0.03) 0%, transparent 40%),
        var(--surface-50) !important;
    background-attachment: fixed !important;
}

.stApp::before {
    content: '';
    position: fixed;
    inset: 0;
    background-image:
        radial-gradient(circle at 1px 1px, rgba(15,23,42,0.04) 1px, transparent 0);
    background-size: 24px 24px;
    pointer-events: none;
    z-index: 0;
}

.block-container {
    padding-top: 2rem !important;
    padding-bottom: 5rem !important;
    max-width: 1320px !important;
    position: relative !important;
    z-index: 1 !important;
    animation: fadeIn 400ms ease-out;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* Dramatic premium header */
.iddaa-header {
    background:
        linear-gradient(135deg, #064E3B 0%, #047857 25%, #10B981 60%, #047857 100%);
    color: white;
    padding: 26px 32px;
    border-radius: var(--r-2xl);
    margin-bottom: 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow:
        0 20px 40px -12px rgba(16,185,129,0.4),
        0 8px 16px -8px rgba(16,185,129,0.3),
        inset 0 1px 0 rgba(255,255,255,0.15);
    position: relative;
    overflow: hidden;
    isolation: isolate;
}
.iddaa-header::before {
    content: '';
    position: absolute;
    inset: 0;
    background:
        radial-gradient(circle at 15% -20%, rgba(255,255,255,0.25), transparent 45%),
        radial-gradient(circle at 85% 120%, rgba(255,255,255,0.12), transparent 50%),
        linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.04) 50%, transparent 100%);
    pointer-events: none;
}
.iddaa-header::after {
    content: '';
    position: absolute;
    inset: 0;
    background-image: radial-gradient(circle at 2px 2px, rgba(255,255,255,0.06) 1px, transparent 0);
    background-size: 28px 28px;
    pointer-events: none;
    opacity: 0.6;
}
.iddaa-header > * { position: relative; z-index: 1; }
.iddaa-header-left {
    display: flex; align-items: center; gap: 18px;
}
.iddaa-header-title {
    font-size: 1.65rem; font-weight: 900;
    letter-spacing: -0.035em;
    line-height: 1;
    text-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.iddaa-header-tag {
    background: rgba(255,255,255,0.18);
    backdrop-filter: blur(8px);
    color: white;
    padding: 4px 11px; border-radius: var(--r-full);
    font-size: 0.7rem; font-weight: 600; letter-spacing: 0.04em;
    border: 1px solid rgba(255,255,255,0.25);
}
.iddaa-header-right {
    display: flex; gap: 22px; font-size: 0.8rem;
    color: rgba(255,255,255,0.92);
    align-items: center;
}
.iddaa-header-right b {
    font-size: 0.95rem; color: white;
    font-weight: 700; letter-spacing: -0.01em;
}

/* Premium hero card — glassmorphism + gradient title */
.hero {
    background: rgba(255,255,255,0.65);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border: 1px solid rgba(255,255,255,0.6);
    border-radius: var(--r-2xl);
    padding: 2.2rem 2.4rem;
    margin-bottom: 28px;
    box-shadow:
        0 8px 32px -8px rgba(16,185,129,0.12),
        0 4px 16px -4px rgba(0,0,0,0.04),
        inset 0 1px 0 rgba(255,255,255,0.8);
    transition: all var(--t-base) ease;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -50%; right: -10%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, var(--brand-200) 0%, transparent 60%);
    opacity: 0.4;
    pointer-events: none;
}
.hero:hover {
    box-shadow:
        0 12px 40px -8px rgba(16,185,129,0.18),
        0 6px 20px -4px rgba(0,0,0,0.06);
    transform: translateY(-2px);
}
.hero-title {
    font-size: 2.4rem; font-weight: 900;
    letter-spacing: -0.04em;
    margin-bottom: 0.7rem;
    background: linear-gradient(135deg, var(--text-strong) 0%, var(--brand-700) 50%, var(--text-strong) 100%);
    background-size: 200% auto;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.05;
    position: relative;
    z-index: 1;
}
.hero-story {
    font-size: 1.08rem; line-height: 1.65;
    color: var(--text-secondary);
    max-width: 820px;
    font-weight: 400;
    position: relative;
    z-index: 1;
}
.hero-story b { color: var(--text-strong); font-weight: 700; }
.hero-story .gh {
    color: var(--brand-600); font-weight: 700;
    background: linear-gradient(120deg, var(--brand-500), var(--brand-700));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    padding: 0 2px;
}

/* Premium KPI strip — büyük sayılar, glassmorphism */
.kpi-strip {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 16px; margin-bottom: 32px;
}
.kpi-card {
    background:
        linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.85) 100%);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(228,228,231,0.6);
    border-radius: var(--r-xl);
    padding: 22px 24px;
    box-shadow:
        0 1px 3px rgba(0,0,0,0.04),
        0 8px 16px -8px rgba(16,185,129,0.06);
    transition: all var(--t-base) cubic-bezier(0.16, 1, 0.3, 1);
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--brand-400), var(--brand-600), var(--brand-400));
    background-size: 200% 100%;
    opacity: 0;
    transition: opacity var(--t-base);
    border-radius: var(--r-xl) var(--r-xl) 0 0;
}
.kpi-card::after {
    content: '';
    position: absolute;
    top: -50%; right: -30%;
    width: 200px; height: 200px;
    background: radial-gradient(circle, var(--brand-100) 0%, transparent 70%);
    opacity: 0;
    pointer-events: none;
    transition: opacity var(--t-base);
}
.kpi-card:hover {
    box-shadow:
        0 4px 8px rgba(0,0,0,0.04),
        0 16px 32px -12px rgba(16,185,129,0.15);
    border-color: var(--brand-200);
    transform: translateY(-3px);
}
.kpi-card:hover::before {
    opacity: 1;
    animation: shimmer 2s linear infinite;
}
.kpi-card:hover::after { opacity: 0.5; }
.kpi-label {
    font-size: 0.7rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.1em;
    font-weight: 700; margin-bottom: 12px;
    display: flex; align-items: center; gap: 7px;
    position: relative; z-index: 1;
}
.kpi-value {
    font-size: 2.1rem; font-weight: 900; color: var(--text-strong);
    line-height: 1; letter-spacing: -0.035em;
    font-feature-settings: "tnum";
    background: linear-gradient(135deg, var(--text-strong) 0%, var(--brand-800) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    position: relative; z-index: 1;
}
.kpi-meta {
    font-size: 0.78rem; color: var(--text-muted); margin-top: 6px;
    font-weight: 500;
    position: relative; z-index: 1;
}

/* Modern fixture bülteni */
.bul-section-header {
    background: linear-gradient(90deg, var(--surface-100) 0%, var(--surface-50) 100%);
    color: var(--text-strong);
    padding: 12px 18px;
    font-size: 0.75rem; font-weight: 700;
    letter-spacing: 0.06em; text-transform: uppercase;
    border-radius: var(--r-lg) var(--r-lg) 0 0;
    border: 1px solid var(--border-subtle);
    border-bottom: none;
    display: flex; justify-content: space-between; align-items: center;
}
.bul-section-meta {
    color: var(--brand-600);
    font-size: 0.7rem; font-weight: 700;
    background: var(--brand-50);
    padding: 2px 9px; border-radius: var(--r-full);
}

.bul-card {
    background: var(--surface-0);
    border: 1px solid var(--border-subtle);
    border-top: none;
    padding: 14px 18px;
    display: grid; grid-template-columns: 64px 1fr auto;
    align-items: center; gap: 14px;
    font-size: 0.92rem;
    transition: all var(--t-fast) ease;
}
.bul-card:hover {
    background: linear-gradient(90deg, var(--brand-50) 0%, var(--surface-0) 100%);
}
.bul-card:last-of-type {
    border-radius: 0 0 var(--r-lg) var(--r-lg);
}
.bul-card + .bul-card { border-top: 1px solid var(--surface-150); }
.bul-time {
    font-size: 0.95rem; color: var(--text-primary);
    font-weight: 700; font-feature-settings: "tnum";
}
.bul-teams {
    display: flex; flex-direction: column; gap: 4px;
    font-weight: 600;
    color: var(--text-strong);
}
.bul-result {
    font-size: 0.72rem; color: var(--text-muted);
    background: var(--surface-100);
    padding: 3px 9px; border-radius: var(--r-sm);
    display: inline-block; align-self: flex-start;
    margin-top: 2px; font-weight: 600;
    font-feature-settings: "tnum";
    border: 1px solid var(--border-subtle);
}
.bul-odds {
    display: flex; gap: 5px;
}
.bul-odd {
    background: var(--surface-100);
    padding: 7px 11px;
    border-radius: var(--r-md);
    font-size: 0.85rem;
    text-align: center; min-width: 44px;
    font-weight: 700;
    color: var(--text-primary);
    font-feature-settings: "tnum";
    border: 1px solid transparent;
    transition: all var(--t-fast);
}
.bul-odd:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-xs);
}
.bul-odd.pick {
    background: linear-gradient(135deg, var(--brand-50), var(--brand-100));
    color: var(--brand-800);
    border: 1px solid var(--brand-300);
    box-shadow: 0 0 0 1px rgba(16,185,129,0.1);
}
.bul-odd.high-edge {
    background: linear-gradient(135deg, #FEF3C7, #FCD34D);
    color: #78350F;
    font-weight: 800;
}
.bul-odd-label {
    font-size: 0.6rem; color: var(--text-muted);
    display: block; margin-bottom: 2px;
    font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase;
}

/* Modern coupon panel (Stripe Dashboard tarzı) */
.coupon-panel {
    background: var(--surface-0);
    border: 1px solid var(--border-subtle);
    border-radius: var(--r-xl);
    padding: 0;
    overflow: hidden;
    position: sticky; top: 1rem;
    box-shadow: var(--shadow-sm);
}
.coupon-panel-header {
    background: linear-gradient(135deg, var(--brand-600), var(--brand-700));
    color: white;
    padding: 16px 20px;
    font-weight: 700; font-size: 0.95rem;
    letter-spacing: -0.01em;
    display: flex; justify-content: space-between; align-items: center;
    position: relative;
}
.coupon-panel-header::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 30% 0%, rgba(255,255,255,0.15), transparent 60%);
    pointer-events: none;
}
.coupon-panel-header-count {
    background: rgba(255,255,255,0.18);
    backdrop-filter: blur(8px);
    color: white;
    padding: 3px 11px;
    border-radius: var(--r-full);
    font-size: 0.78rem;
    font-weight: 800;
    border: 1px solid rgba(255,255,255,0.25);
    font-feature-settings: "tnum";
    z-index: 1;
}

/* Modern tier cards (Linear-style) */
.tier-card {
    background: var(--surface-0);
    border: 1px solid var(--border-subtle);
    border-radius: var(--r-lg);
    padding: 18px 18px 0 18px;
    margin-bottom: 14px;
    box-shadow: var(--shadow-xs);
    transition: all var(--t-base) ease;
    overflow: hidden;
}
.tier-card:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
    border-color: var(--border-default);
}
.tier-header {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 0.7rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 6px;
    padding: 4px 10px;
    border-radius: var(--r-full);
}
.tier-konservatif .tier-header {
    color: var(--brand-700);
    background: var(--brand-50);
}
.tier-dengeli .tier-header {
    color: #B45309;
    background: #FEF3C7;
}
.tier-agresif .tier-header {
    color: #B91C1C;
    background: #FEE2E2;
}

.tier-title {
    font-size: 1.1rem; font-weight: 700;
    margin-bottom: 4px;
    color: var(--text-strong);
    letter-spacing: -0.015em;
}
.tier-desc {
    font-size: 0.8rem; color: var(--text-muted);
    margin-bottom: 14px;
}

.tier-leg {
    padding: 10px 0;
    border-bottom: 1px solid var(--surface-150);
    font-size: 0.88rem;
}
.tier-leg:last-of-type { border-bottom: none; }
.tier-leg-match {
    font-weight: 600;
    color: var(--text-strong);
    font-size: 0.92rem;
}
.tier-leg-pick {
    background: linear-gradient(135deg, var(--brand-50), var(--brand-100));
    color: var(--brand-800);
    padding: 3px 11px; border-radius: var(--r-md);
    font-weight: 700; font-size: 0.8rem;
    display: inline-block; margin-top: 5px;
    border: 1px solid var(--brand-200);
    font-feature-settings: "tnum";
}
.tier-leg-meta {
    font-size: 0.74rem; color: var(--text-muted);
    margin-top: 5px;
    font-weight: 500;
}
.tier-leg-meta .edge {
    color: var(--brand-700);
    font-weight: 700;
    background: var(--brand-50);
    padding: 1px 6px; border-radius: var(--r-sm);
}

.tier-footer {
    background: var(--surface-50);
    margin: 12px -18px 0 -18px;
    padding: 14px 18px;
    border-top: 1px solid var(--border-subtle);
}
.tier-stat {
    display: flex; justify-content: space-between;
    font-size: 0.82rem; padding: 3px 0;
}
.tier-stat-label { color: var(--text-muted); font-weight: 500; }
.tier-stat-value {
    font-weight: 700; color: var(--text-strong);
    font-feature-settings: "tnum";
}

.tier-potansiyel {
    background: linear-gradient(135deg, var(--brand-100) 0%, var(--brand-50) 100%);
    margin: 0 -18px;
    padding: 14px 18px;
    border-top: 1px solid var(--brand-200);
    text-align: center;
    font-weight: 700; color: var(--brand-800);
    font-size: 1rem;
    letter-spacing: -0.005em;
}
.tier-potansiyel b {
    font-size: 1.15rem; font-weight: 800;
    color: var(--brand-700);
    font-feature-settings: "tnum";
}

/* Modern section title */
.section-title {
    display: flex; align-items: center; gap: 12px;
    font-size: 1.15rem; font-weight: 700;
    margin: 28px 0 14px 0;
    color: var(--text-strong);
    letter-spacing: -0.02em;
}
.section-title .bar {
    width: 4px; height: 22px;
    background: linear-gradient(180deg, var(--brand-500), var(--brand-700));
    border-radius: var(--r-sm);
}

/* Modern data grid (Stripe Dashboard) */
.data-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 16px; margin-bottom: 20px;
}
.data-panel {
    background: var(--surface-0);
    border: 1px solid var(--border-subtle);
    border-radius: var(--r-lg);
    padding: 18px 20px;
    box-shadow: var(--shadow-xs);
    transition: all var(--t-base) ease;
}
.data-panel:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
.data-panel-title {
    font-size: 0.72rem; font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.08em;
    margin-bottom: 10px;
    display: flex; align-items: center; gap: 6px;
}
.data-panel-value {
    font-size: 1.85rem; font-weight: 800;
    color: var(--text-strong);
    letter-spacing: -0.025em;
    line-height: 1;
    font-feature-settings: "tnum";
}
.data-panel-meta {
    font-size: 0.8rem; color: var(--text-muted);
    margin-top: 6px; font-weight: 500;
}

/* Modern notice panel (warning) */
.notice-panel {
    background: linear-gradient(135deg, #FEF3C7 0%, #FFFBEB 100%);
    border: 1px solid #FCD34D;
    border-left: 4px solid var(--warning);
    padding: 14px 18px;
    border-radius: var(--r-md);
    margin: 18px 0;
    font-size: 0.9rem; color: #78350F;
    line-height: 1.55;
    box-shadow: var(--shadow-xs);
}
.notice-panel b { color: #92400E; font-weight: 700; }

/* Disclaimer panel */
.disclaimer {
    background: var(--surface-100);
    border: 1px solid var(--border-subtle);
    border-radius: var(--r-md);
    padding: 13px 16px;
    color: var(--text-secondary);
    font-size: 0.82rem;
    line-height: 1.55;
    margin: 18px 0;
}

/* Streamlit defaults gizle */
#MainMenu, footer, header { visibility: hidden !important; }

/* Modern Sidebar */
[data-testid="stSidebar"] {
    background: var(--surface-0) !important;
    border-right: 1px solid var(--border-subtle) !important;
    box-shadow: var(--shadow-xs) !important;
}
[data-testid="stSidebar"] > div {
    padding-top: 1.5rem !important;
}
[data-testid="stSidebar"] h2 {
    color: var(--text-strong) !important;
    font-size: 0.78rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-weight: 700 !important;
    margin: 1.5rem 0 0.7rem 0 !important;
    padding-bottom: 0.4rem !important;
    border-bottom: 1px solid var(--border-subtle) !important;
}

/* Sidebar radio menü */
[data-testid="stSidebar"] [role="radiogroup"] label {
    padding: 8px 12px !important;
    border-radius: var(--r-md) !important;
    transition: background var(--t-fast) !important;
    font-size: 0.88rem !important;
    color: var(--text-primary) !important;
    margin-bottom: 2px !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
    background: var(--surface-100) !important;
}

/* Modern buttons (Linear/Vercel-style) */
.stButton button {
    background: linear-gradient(180deg, var(--brand-500) 0%, var(--brand-600) 100%) !important;
    color: white !important;
    border: 1px solid var(--brand-600) !important;
    border-radius: var(--r-md) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 0.55rem 1.25rem !important;
    box-shadow: 0 1px 2px rgba(16,185,129,0.2), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    transition: all var(--t-fast) !important;
    letter-spacing: -0.005em !important;
}
.stButton button:hover {
    background: linear-gradient(180deg, var(--brand-600) 0%, var(--brand-700) 100%) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 8px rgba(16,185,129,0.25), inset 0 1px 0 rgba(255,255,255,0.15) !important;
}
.stButton button:active {
    transform: translateY(0) !important;
    box-shadow: 0 1px 2px rgba(16,185,129,0.15) !important;
}

/* Modern expander */
[data-testid="stExpander"] {
    background: var(--surface-0) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-xs) !important;
    transition: box-shadow var(--t-base) !important;
    margin: 14px 0 !important;
}
[data-testid="stExpander"]:hover {
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stExpander"] summary {
    font-weight: 600 !important;
    color: var(--text-strong) !important;
    padding: 12px 18px !important;
    font-size: 0.92rem !important;
}

/* Modern inputs */
.stSelectbox > div, .stNumberInput input, .stDateInput input {
    background: var(--surface-0) !important;
    border: 1px solid var(--border-default) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-inner) !important;
    transition: all var(--t-fast) !important;
}
.stSelectbox > div:hover, .stNumberInput input:hover,
.stDateInput input:hover {
    border-color: var(--brand-400) !important;
}
.stSelectbox > div:focus-within, .stNumberInput input:focus,
.stDateInput input:focus {
    border-color: var(--brand-500) !important;
    box-shadow: 0 0 0 3px rgba(16,185,129,0.1), var(--shadow-inner) !important;
    outline: none !important;
}

/* Modern slider */
.stSlider [role="slider"] {
    background: var(--brand-500) !important;
    border-color: var(--brand-600) !important;
    box-shadow: var(--shadow-sm) !important;
}
.stSlider [data-baseweb="slider"] > div > div {
    background: var(--brand-100) !important;
}

/* Modern metric cards */
[data-testid="stMetric"] {
    background: var(--surface-0);
    border: 1px solid var(--border-subtle);
    border-radius: var(--r-lg);
    padding: 16px 18px;
    box-shadow: var(--shadow-xs);
    transition: all var(--t-base);
}
[data-testid="stMetric"]:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
[data-testid="stMetricValue"] {
    font-size: 1.7rem !important;
    font-weight: 800 !important;
    color: var(--text-strong) !important;
    letter-spacing: -0.02em !important;
    font-feature-settings: "tnum";
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    font-size: 0.7rem !important;
    font-weight: 700 !important;
}

/* Modern tabs */
.stTabs [data-baseweb="tab-list"] {
    background: var(--surface-100) !important;
    border-radius: var(--r-md) !important;
    padding: 4px !important;
    gap: 2px !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    border-radius: var(--r-sm) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 8px 14px !important;
    transition: all var(--t-fast) !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: var(--text-strong) !important;
}
.stTabs [aria-selected="true"] {
    background: var(--surface-0) !important;
    color: var(--text-strong) !important;
    box-shadow: var(--shadow-xs) !important;
}

/* Modern dataframe */
[data-testid="stDataFrame"] {
    border-radius: var(--r-md) !important;
    border: 1px solid var(--border-subtle) !important;
    overflow: hidden !important;
}

/* Modern alert (st.success / st.info / st.warning) */
.stAlert {
    border-radius: var(--r-md) !important;
    border: 1px solid var(--border-subtle) !important;
    box-shadow: var(--shadow-xs) !important;
}

/* Custom scrollbar */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--surface-100); }
::-webkit-scrollbar-thumb {
    background: var(--border-default);
    border-radius: var(--r-full);
    border: 2px solid var(--surface-100);
}
::-webkit-scrollbar-thumb:hover { background: var(--text-disabled); }

/* Subtle text helpers */
small {
    color: var(--text-muted);
    font-size: 0.82rem;
}
code {
    background: var(--surface-100) !important;
    color: var(--text-strong) !important;
    padding: 1px 6px !important;
    border-radius: var(--r-sm) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85em !important;
    border: 1px solid var(--border-subtle) !important;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# ============================================================
# VERİ YÜKLEME
# ============================================================

@st.cache_resource
def load_dc_params(league: str) -> DCParams | None:
    p = YAZILIM_DIR / "06_PRODUCTION" / "models" / f"dc_params_{league}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    return DCParams(teams=d["teams"], attack=d["attack"], defence=d["defence"],
                    home_adv=d["home_adv"], rho=d["rho"], xi=d["xi"])


@st.cache_resource
def load_platt(league: str) -> dict | None:
    p = YAZILIM_DIR / "06_PRODUCTION" / "models" / f"platt_params_{league}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


@st.cache_data(ttl=300)
def get_fixtures(league_code: str, anchor: str,
                 days_before: int, days_after: int) -> list[dict]:
    return db.fixtures_for_week(league_code, anchor, days_before, days_after)


@st.cache_data
def load_bet_log() -> pd.DataFrame | None:
    p = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "backtest_bets_v2.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, parse_dates=["match_date"])


@st.cache_data(ttl=60)
def db_stats() -> dict:
    return db.stats_summary()


# ============================================================
# TAKIM AD NORMALİZASYONU
# ============================================================

TEAM_ALIAS = {
    "Manchester City": "Man City", "Manchester United": "Man United",
    "Newcastle United": "Newcastle", "Newcastle": "Newcastle",
    "Wolverhampton Wanderers": "Wolves", "Wolves": "Wolves",
    "Nottingham Forest": "Nott'm Forest", "Tottenham": "Tottenham",
    "Brighton": "Brighton", "Crystal Palace": "Crystal Palace",
    "Aston Villa": "Aston Villa", "Bournemouth": "Bournemouth",
    "Antalyaspor": "Antalyaspor", "Konyaspor": "Konyaspor",
    "Alanyaspor": "Alanyaspor", "Kayserispor": "Kayserispor",
    "Rizespor": "Rizespor", "Gaziantep FK": "Gaziantep",
    "Galatasaray": "Galatasaray", "Sivasspor": "Sivasspor",
    "Hatayspor": "Hatayspor",
    "Başakşehir": "Buyuksehyr", "Basaksehir": "Buyuksehyr",
    "Samsunspor": "Samsunspor",
    "Eyüpspor": "Eyupspor", "Eyupspor": "Eyupspor",
    "Fenerbahçe": "Fenerbahce", "Fenerbahce": "Fenerbahce",
    "Beşiktaş": "Besiktas", "Besiktas": "Besiktas",
    "Adana Demirspor": "Ad. Demirspor",
    "Göztepe": "Goztepe", "Goztepe": "Goztepe",
    "Trabzonspor": "Trabzonspor",
    "Gençlerbirliği": "Genclerbirligi", "Genclerbirligi": "Genclerbirligi",
    "Kasımpaşa": "Kasimpasa", "Kasimpasa": "Kasimpasa",
    "Karagümrük": "Karagumruk", "Karagumruk": "Karagumruk",
    "Ankaragücü": "Ankaragucu", "Ankaragucu": "Ankaragucu",
}

def norm(name: str | None) -> str | None:
    return TEAM_ALIAS.get(name, name) if name else None


# ============================================================
# TAHMİN MOTORU
# ============================================================

def predict(params: DCParams, home: str, away: str,
            platt: dict | None = None) -> dict | None:
    h, a = norm(home), norm(away)
    if h not in params.teams or a not in params.teams:
        return None
    lam, mu = params.expected_goals(h, a)
    M = score_matrix(lam, mu, params.rho, max_goals=10)

    o = prob_1x2(M)
    ou15 = prob_over_under(M, 1.5)
    ou25 = prob_over_under(M, 2.5)
    ou35 = prob_over_under(M, 3.5)
    btts = prob_btts(M)
    dc = prob_double_chance(M)
    hcp_m1 = prob_handicap(M, -1)
    fh = prob_first_half_1x2(lam, mu, params.rho)
    fh_ou05 = prob_first_half_over_under(lam, mu, 0.5, params.rho)
    fh_ou15 = prob_first_half_over_under(lam, mu, 1.5, params.rho)
    htft = prob_ht_ft(lam, mu, params.rho)
    top5 = top_n_scores(M, 5)

    # Platt
    p_o_raw = ou25["over"]
    if platt:
        a_p, b_p = platt["a"], platt["b"]
        eps = 1e-7
        cl = max(min(p_o_raw, 1 - eps), eps)
        logit = np.log(cl / (1 - cl))
        p_o = 1.0 / (1.0 + np.exp(a_p * logit + b_p))
    else:
        p_o = p_o_raw

    return {
        "home": home, "away": away,
        "lam_h": lam, "lam_a": mu,
        "p_1": o["1"], "p_X": o["X"], "p_2": o["2"],
        "p_1X": dc["1X"], "p_12": dc["12"], "p_X2": dc["X2"],
        "p_over15": ou15["over"], "p_under15": ou15["under"],
        "p_over25": float(p_o), "p_under25": float(1 - p_o),
        "p_over35": ou35["over"], "p_under35": ou35["under"],
        "p_btts": btts["yes"], "p_btts_no": btts["no"],
        "p_hcp_m1_1": hcp_m1["1"], "p_hcp_m1_X": hcp_m1["X"], "p_hcp_m1_2": hcp_m1["2"],
        "p_fh_1": fh["1"], "p_fh_X": fh["X"], "p_fh_2": fh["2"],
        "p_fh_over05": fh_ou05["over"], "p_fh_over15": fh_ou15["over"],
        "p_htft": htft, "top5": top5,
    }


# ============================================================
# KUPON MOTORU
# ============================================================

TYPICAL_VIG = 0.07  # iddaa marjı ~%6-10, ortalama %7
RISK_LIMITS = RiskLimits()  # Sprint 2.4 default limits


def sim_market(fair: float) -> float:
    """Fair → bookmaker market odd (vig sonrası)."""
    return round(fair * (1 - TYPICAL_VIG), 2)


def find_candidates(predictions: list[dict],
                    min_net_edge: float = 1.0) -> pd.DataFrame:
    """Sprint 2.4: vig-adjusted edge ile aday bahisler."""
    rows = []
    for p in predictions:
        if not p:
            continue
        opts = [
            ("MS 1", p["p_1"]), ("MS X", p["p_X"]), ("MS 2", p["p_2"]),
            ("1X", p["p_1X"]), ("12", p["p_12"]), ("X2", p["p_X2"]),
            ("Üst 1.5", p["p_over15"]), ("Alt 1.5", p["p_under15"]),
            ("Üst 2.5", p["p_over25"]), ("Alt 2.5", p["p_under25"]),
            ("Üst 3.5", p["p_over35"]), ("Alt 3.5", p["p_under35"]),
            ("KG Var", p["p_btts"]), ("KG Yok", p["p_btts_no"]),
            ("İY 1", p["p_fh_1"]), ("İY X", p["p_fh_X"]), ("İY 2", p["p_fh_2"]),
            ("İY Üst 0.5", p["p_fh_over05"]), ("İY Üst 1.5", p["p_fh_over15"]),
            ("Hcp -1: Ev", p["p_hcp_m1_1"]),
        ]
        if "p_htft" in p:
            best_k = max(p["p_htft"], key=p["p_htft"].get)
            opts.append((f"İY/MS {best_k}", p["p_htft"][best_k]))

        for pick, prob in opts:
            if prob < 0.30 or prob > 0.92:
                continue
            fair = 1 / prob if prob > 0 else 99
            mkt = sim_market(fair)
            edge_raw = (prob * mkt - 1) * 100
            # Sprint 2.4: vig-adjusted net edge
            edge_net = vig_adjusted_edge(prob, mkt, TYPICAL_VIG) * 100
            if edge_net < min_net_edge:
                continue
            rows.append({
                "match": f"{p['home']} - {p['away']}",
                "pick": pick, "p": prob, "fair": fair,
                "market": mkt,
                "edge_pct": edge_raw,
                "edge_net_pct": edge_net,
            })
    return pd.DataFrame(rows).sort_values("edge_net_pct", ascending=False) if rows else pd.DataFrame()


def kelly_stake(p: float, odds: float, bankroll: float,
                fraction: float = 0.25, max_pct: float = 2.0) -> float:
    if odds <= 1 or p <= 0:
        return 0
    b = odds - 1
    f = (p * odds - 1) / b
    return bankroll * max(min(f * fraction, max_pct / 100), 0)


def build_coupons(predictions: list[dict], bankroll: float, kelly_frac: float) -> dict:
    """Sprint 2.4: vig-adjusted edge + risk limits ile kupon önerisi."""
    cands = find_candidates(predictions, min_net_edge=1.0)
    if cands.empty:
        return {"konservatif": (None, {}), "dengeli": (None, {}), "agresif": (None, {})}

    # Sprint 2.4: net edge bazlı filtreler
    cons_pool = cands[(cands["p"] > 0.58) & (cands["edge_net_pct"] > 2.0)].head(1)
    deng_pool = cands[cands["edge_net_pct"] > 1.5].drop_duplicates("match").head(3)
    agg_pool = cands[cands["edge_net_pct"] > 0.5].drop_duplicates("match").head(4)

    # Override limits per user kelly_frac
    custom_limits = RiskLimits(
        kelly_fraction=kelly_frac, max_stake_pct=2.0,
        min_net_edge_pct=0.5,  # daha düşük çünkü kullanıcı görsün, kendi karar versin
    )

    def stats(legs):
        if legs is None or legs.empty:
            return {}
        legs_list = [{"p": r["p"], "odds": r["market"]} for _, r in legs.iterrows()]
        cr = combo_stake(legs_list, bankroll, TYPICAL_VIG, custom_limits)
        if not cr.get("approved"):
            # Fallback: yine de stake göster (risk filtresi sadece bilgi)
            return {
                "odds": cr.get("combined_odds", 0),
                "prob": cr.get("combined_prob", 0),
                "edge": cr.get("edge_raw_pct", 0),
                "edge_net": cr.get("edge_net_pct", 0),
                "stake": 0,
                "return": 0,
                "profit": 0,
                "rejected": cr.get("rejection_reason"),
            }
        return {
            "odds": cr["combined_odds"],
            "prob": cr["combined_prob"],
            "edge": cr["edge_raw_pct"],
            "edge_net": cr["edge_net_pct"],
            "stake": cr["stake"],
            "return": cr["stake"] * cr["combined_odds"],
            "profit": cr["stake"] * cr["combined_odds"] - cr["stake"],
            "rejected": None,
            "combo_vig_pct": cr.get("combo_vig_pct", 0),
        }
    return {
        "konservatif": (cons_pool, stats(cons_pool)),
        "dengeli": (deng_pool, stats(deng_pool)),
        "agresif": (agg_pool, stats(agg_pool)),
    }


# ============================================================
# RENDER: HEADER + KPI
# ============================================================

def render_header(league_name: str, anchor: date, fixture_count: int):
    st.markdown(f"""
    <div class='iddaa-header'>
        <div class='iddaa-header-left'>
            <span style='font-size:1.8rem'>⚽</span>
            <div>
                <div class='iddaa-header-title'>BAHIS AGENT</div>
                <div style='font-size:0.78rem;opacity:0.85'>
                    {league_name} · <b>{fixture_count}</b> maç
                </div>
            </div>
            <span class='iddaa-header-tag'>v0.6</span>
        </div>
        <div class='iddaa-header-right'>
            <div>📅 <b>{anchor.strftime("%d %B %Y")}</b></div>
            <div>🤖 Dixon-Coles + Platt + LightGBM</div>
            <div>🟢 SİSTEM AKTİF</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_kpis(predictions: list[dict], bet_log: pd.DataFrame | None,
                bankroll: float):
    cands = find_candidates([p for p in predictions if p])
    n_match = len([p for p in predictions if p])
    n_value = len(cands)
    best_edge = cands["edge_pct"].max() if not cands.empty else 0

    if bet_log is not None and len(bet_log) > 0:
        last_bk = float(bet_log["bankroll_after"].iloc[-1])
        roi = (last_bk - 10000) / float(bet_log["stake"].sum()) * 100
        win_rate = float(bet_log["won"].mean() * 100)
    else:
        last_bk, roi, win_rate = bankroll, 0, 0

    st.markdown(f"""
    <div class='kpi-strip'>
      <div class='kpi-card'>
        <div class='kpi-label'>📋 Analiz Edilen Maç</div>
        <div class='kpi-value'>{n_match}</div>
        <div class='kpi-meta'>bu hafta</div>
      </div>
      <div class='kpi-card'>
        <div class='kpi-label'>🎯 Bahis Fırsatı</div>
        <div class='kpi-value'>{n_value}</div>
        <div class='kpi-meta'>edge >%2 olan</div>
      </div>
      <div class='kpi-card'>
        <div class='kpi-label'>⚡ En Yüksek Edge</div>
        <div class='kpi-value'>%{best_edge:.1f}</div>
        <div class='kpi-meta'>tek maç</div>
      </div>
      <div class='kpi-card'>
        <div class='kpi-label'>💰 Bankroll</div>
        <div class='kpi-value'>{last_bk:,.0f} ₺</div>
        <div class='kpi-meta'>Backtest ROI %{roi:+.1f}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# RENDER: HERO HİKAYE
# ============================================================

def render_hero(predictions: list[dict], league_name: str, anchor: date,
                days_before: int, days_after: int):
    n = len([p for p in predictions if p])
    cands = find_candidates([p for p in predictions if p])
    n_value = len(cands)
    start = (anchor - timedelta(days=days_before)).strftime("%d %b")
    end = (anchor + timedelta(days=days_after)).strftime("%d %b")

    if n_value > 0:
        story = (
            f"Modelimiz <b>{league_name}</b>'de {start}–{end} arası "
            f"<b class='gh'>{n} maçı</b> analiz etti. "
            f"İçinde <b class='gh'>{n_value} bahis fırsatı</b> bulundu — yani "
            f"<b>model olasılığı</b> ile <b>iddaa oranı</b> arasında pozitif fark gördük. "
            f"Aşağıda <b>3 risk seviyesinde</b> hazır kuponlar var."
        )
    else:
        story = (
            f"<b>{league_name}</b>'de {start}–{end} arası <b>{n} maç</b> analiz ettim. "
            f"Şu anda <b class='gh'>belirgin bir bahis fırsatı yok</b> — "
            f"pas geçmek de bir stratejidir. "
            f"Sidebar'dan farklı bir tarih veya lig dene."
        )

    st.markdown(f"""
    <div class='hero'>
      <div class='hero-title'>📊 Bu Haftanın Kuponları</div>
      <p class='hero-story'>{story}</p>
    </div>
    """, unsafe_allow_html=True)


# ============================================================
# RENDER: FIXTURE LİSTESİ (iddaa.com bülteni gibi)
# ============================================================

def best_picks_for_match(p: dict) -> dict:
    """Bir maç için her market'te en yüksek olasılığı işaretle."""
    return {
        "ms": max([("1", p["p_1"]), ("X", p["p_X"]), ("2", p["p_2"])], key=lambda x: x[1])[0],
        "iy": max([("1", p["p_fh_1"]), ("X", p["p_fh_X"]), ("2", p["p_fh_2"])], key=lambda x: x[1])[0],
        "au": "Üst" if p["p_over25"] > p["p_under25"] else "Alt",
        "kg": "Var" if p["p_btts"] > p["p_btts_no"] else "Yok",
    }


def _odd_box(label: str, prob: float, is_pick: bool) -> str:
    cls = "bul-odd pick" if is_pick else "bul-odd"
    return f"<div class='{cls}'><span class='bul-odd-label'>{label}</span>%{prob*100:.0f}</div>"


def render_fixtures_panel(fixtures: list[dict], predictions: list[dict],
                           league_name: str):
    """iddaa.com bülteni gibi maç listesi."""
    if not fixtures:
        st.markdown(
            "<div class='notice-panel'><b>Bu tarih aralığında maç yok.</b> "
            "Sidebar'dan tarihi değiştir.</div>",
            unsafe_allow_html=True
        )
        return

    # Tarihe göre gruplandır
    by_date: dict[str, list] = {}
    for fx, pred in zip(fixtures, predictions):
        d = fx["kickoff_utc"][:10]
        by_date.setdefault(d, []).append((fx, pred))

    # Tüm HTML'i tek string'de topla — indentation YOK (Streamlit markdown 4+ space = code block)
    parts = []
    for d, items in sorted(by_date.items()):
        try:
            dt = datetime.fromisoformat(d).strftime("%d %B %A")
        except Exception:
            dt = d
        parts.append(
            f"<div class='bul-section-header'>"
            f"<span>📅 {dt} · {league_name}</span>"
            f"<span class='bul-section-meta'>{len(items)} maç</span>"
            f"</div>"
        )
        for fx, pred in items:
            ko_time = fx["kickoff_utc"][11:16]
            score_html = ""
            if fx.get("home_score") is not None:
                score_html = (
                    f"<span class='bul-result'>FT "
                    f"{fx['home_score']}-{fx['away_score']}</span>"
                )

            if pred:
                picks = best_picks_for_match(pred)
                odds_html = (
                    "<div class='bul-odds'>"
                    + _odd_box("1", pred["p_1"], picks["ms"] == "1")
                    + _odd_box("X", pred["p_X"], picks["ms"] == "X")
                    + _odd_box("2", pred["p_2"], picks["ms"] == "2")
                    + "<div style='width:8px'></div>"
                    + _odd_box("Alt", pred["p_under25"], picks["au"] == "Alt")
                    + _odd_box("Üst", pred["p_over25"], picks["au"] == "Üst")
                    + "<div style='width:8px'></div>"
                    + _odd_box("KG V", pred["p_btts"], picks["kg"] == "Var")
                    + _odd_box("KG Y", pred["p_btts_no"], picks["kg"] == "Yok")
                    + "</div>"
                )
            else:
                odds_html = "<span style='color:#9CA3AF;font-size:0.78rem'>Model yok</span>"

            teams_html = (
                f"<div class='bul-teams'>"
                f"<div>{fx['home_team']} <span style='color:#94A3B8'>vs</span> {fx['away_team']}</div>"
                f"{score_html}"
                f"</div>"
            )

            parts.append(
                f"<div class='bul-card'>"
                f"<div class='bul-time'>{ko_time}</div>"
                f"{teams_html}"
                f"{odds_html}"
                f"</div>"
            )
        parts.append("<div style='height:14px'></div>")

    # Tek render — indentation yok, Streamlit code block algılayamaz
    st.markdown("".join(parts), unsafe_allow_html=True)


# ============================================================
# RENDER: KUPONUM PANELİ (sağ kolon, iddaa.com tarzı)
# ============================================================

KUPON_META = {
    "konservatif": {"tag": "🛡️ KONSERVATİF", "title": "Düşük Risk",
                    "desc": "Tek bahis · Edge >%4 · Yüksek olasılık",
                    "cls": "tier-konservatif"},
    "dengeli":     {"tag": "⚖️ DENGELİ",     "title": "Orta Risk",
                    "desc": "2-3 leg · Edge >%3.5",
                    "cls": "tier-dengeli"},
    "agresif":     {"tag": "🚀 AGRESİF",     "title": "Yüksek Risk",
                    "desc": "4 leg parlay · Maksimum potansiyel",
                    "cls": "tier-agresif"},
}


def render_coupon_panel(coupons: dict):
    n_coupons = sum(1 for _, (legs, _) in coupons.items()
                    if legs is not None and not legs.empty)

    st.markdown(f"""
    <div class='coupon-panel'>
      <div class='coupon-panel-header'>
        <span>🎫 Kuponum</span>
        <span class='coupon-panel-header-count'>{n_coupons}</span>
      </div>
      <div style='padding:14px'>
    """, unsafe_allow_html=True)

    if n_coupons == 0:
        st.markdown(
            "<div style='text-align:center;padding:30px 10px;color:#9CA3AF'>"
            "<div style='font-size:2.5rem;margin-bottom:10px'>👋</div>"
            "<div style='font-weight:600;color:#4B5563'>Henüz uygun kupon yok</div>"
            "<div style='font-size:0.82rem;margin-top:6px'>"
            "Modelimiz bu hafta edge tespit etmedi. Yarınki maçları dene veya "
            "ligi değiştir.</div>"
            "</div></div></div>", unsafe_allow_html=True
        )
        return

    for key in ["konservatif", "dengeli", "agresif"]:
        legs, stats = coupons[key]
        meta = KUPON_META[key]

        if legs is None or legs.empty:
            continue

        legs_html = []
        for _, r in legs.iterrows():
            legs_html.append(f"""
            <div class='tier-leg'>
                <div class='tier-leg-match'>{r['match']}</div>
                <div class='tier-leg-pick'>{r['pick']}  @{r['market']:.2f}</div>
                <div class='tier-leg-meta'>
                    Olasılık <b>%{r['p']*100:.0f}</b>  ·
                    <span class='edge'>Edge +%{r['edge_pct']:.1f}</span>
                </div>
            </div>
            """)

        st.markdown(f"""
        <div class='tier-card {meta['cls']}'>
          <div class='tier-header'>{meta['tag']}</div>
          <div class='tier-title'>{meta['title']}</div>
          <div class='tier-desc'>{meta['desc']}</div>
          {''.join(legs_html)}
          <div class='tier-footer'>
            <div class='tier-stat'>
              <span class='tier-stat-label'>Toplam oran</span>
              <span class='tier-stat-value'>{stats['odds']:.2f}</span>
            </div>
            <div class='tier-stat'>
              <span class='tier-stat-label'>Tutma şansı</span>
              <span class='tier-stat-value'>%{stats['prob']*100:.0f}</span>
            </div>
            <div class='tier-stat'>
              <span class='tier-stat-label'>Önerilen stake</span>
              <span class='tier-stat-value'>{stats['stake']:.0f} ₺</span>
            </div>
          </div>
          <div class='tier-potansiyel'>
            🎯 Tutarsa <b>{stats['return']:.0f} ₺</b>
            <span style='font-size:0.85rem;font-weight:600;color:#16A34A'>
              (+{stats['profit']:.0f}₺)
            </span>
          </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)


# ============================================================
# RENDER: BLOOMBERG-TARZI VERİ ALANI
# ============================================================

def render_data_panels(bet_log: pd.DataFrame | None, params: DCParams | None,
                        cands: pd.DataFrame):
    st.markdown("""
    <div class='section-title'>
        <div class='bar'></div>
        <span>📊 Sistem Performansı</span>
    </div>
    """, unsafe_allow_html=True)

    if bet_log is None or bet_log.empty:
        st.info("Backtest verisi yok.")
        return

    starting = 10000.0
    final = float(bet_log["bankroll_after"].iloc[-1])
    pnl = final - starting
    roi = pnl / float(bet_log["stake"].sum()) * 100
    win = float(bet_log["won"].mean() * 100)
    clv = float(bet_log["clv_pct"].mean())

    # 3-panel KPI Bloomberg-tarzı
    st.markdown(f"""
    <div class='data-grid'>
      <div class='data-panel'>
        <div class='data-panel-title'>💰 Backtest Bankroll</div>
        <div class='data-panel-value' style='color:#16A34A'>
          {final:,.0f} ₺
        </div>
        <div class='data-panel-meta'>
          {pnl:+,.0f} ₺ kar ({roi:+.2f}% ROI)
        </div>
      </div>
      <div class='data-panel'>
        <div class='data-panel-title'>🎯 Kazanma Oranı</div>
        <div class='data-panel-value'>%{win:.1f}</div>
        <div class='data-panel-meta'>{int(bet_log['won'].sum())} / {len(bet_log)} bahis</div>
      </div>
      <div class='data-panel'>
        <div class='data-panel-title'>📉 CLV (Closing Line Value)</div>
        <div class='data-panel-value' style='color:{"#16A34A" if clv > 0 else "#DC2626"}'>
          %{clv:+.2f}
        </div>
        <div class='data-panel-meta'>
          {"✓ Pozitif edge sinyali" if clv > 0 else "⚠️ Negatif — şans olabilir"}
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Equity curve
    col1, col2 = st.columns([2, 1])

    with col1:
        eq = [starting] + bet_log["bankroll_after"].tolist()
        dates = [bet_log["match_date"].min()] + bet_log["match_date"].tolist()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=eq, mode="lines",
            line=dict(color="#00B14F", width=2.5),
            fill="tozeroy", fillcolor="rgba(0,177,79,0.08)",
            hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f} ₺<extra></extra>",
        ))
        fig.add_hline(y=starting, line_dash="dot", line_color="#9CA3AF")
        fig.update_layout(
            height=240,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=False, color="#6B7280"),
            yaxis=dict(showgrid=True, gridcolor="#E5E7EB",
                       color="#6B7280", tickformat=",.0f"),
            font=dict(family="Inter, sans-serif", color="#6B7280"),
            title=dict(text="Bankroll Evrimi (Backtest)",
                       font=dict(size=12, color="#4B5563"),
                       x=0.02, y=0.95),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        if not cands.empty:
            # Pazar dağılımı
            cands["market_group"] = cands["pick"].str.split(" ").str[0]
            mg = cands["market_group"].value_counts().head(6)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                y=mg.index, x=mg.values, orientation="h",
                marker_color="#00B14F",
            ))
            fig.update_layout(
                height=240,
                margin=dict(l=0, r=0, t=30, b=0),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False,
                xaxis=dict(showgrid=True, gridcolor="#E5E7EB", color="#6B7280"),
                yaxis=dict(showgrid=False, color="#0F1F17"),
                font=dict(family="Inter, sans-serif", color="#6B7280"),
                title=dict(text="Bu Haftaki Edge Pazarları",
                           font=dict(size=12, color="#4B5563"), x=0.02),
            )
            st.plotly_chart(fig, use_container_width=True)


# ============================================================
# SIDEBAR
# ============================================================

LEAGUES = {
    "T1":  "🇹🇷 Türkiye Süper Lig",
    "E0":  "🏴 Premier League",
    "D1":  "🇩🇪 Bundesliga",
    "I1":  "🇮🇹 Serie A",
    "SP1": "🇪🇸 La Liga",
    "F1":  "🇫🇷 Ligue 1",
}


PAGES = [
    "🎯 Haftanın Kombini (T05 production)",
    "🏆 Haftanın 3 Maçı (SELECTIVE EDGE)",
    "📊 Sinyal Pivot (Backtest 4188 maç)",
    "🏠 Bu Haftanın Kuponları",
    "🎯 Tavsiye Edilen Kuponlar (Canlı)",
    "📈 Sistem Performansı",
    "🔬 Bilimsel Kanıt",
    "🌍 Veri Setleri",
    "🧠 Teknik Mimari",
    "🗺️ Yol Haritası",
    "❓ Hakkında",
]


def render_sidebar():
    with st.sidebar:
        st.markdown(
            "<div style='padding:0.5rem 0 1rem 0'>"
            "<div style='font-size:1.4rem;font-weight:800;color:#003F19'>⚽ BAHIS AGENT</div>"
            "<div style='font-size:0.78rem;color:#6B7280'>v0.6 — AI-powered analiz</div>"
            "</div>",
            unsafe_allow_html=True
        )

        # ─── PAGE SELECTOR ───
        st.markdown("## 📋 Sayfalar")
        page = st.radio(
            "Sayfa",
            options=PAGES,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("## 🌍 Lig")
        league = st.selectbox(
            "Lig", options=list(LEAGUES.keys()),
            format_func=lambda x: LEAGUES[x], label_visibility="collapsed",
        )

        st.markdown("## 📅 Tarih")
        anchor = st.date_input(
            "Tarih",
            value=date(2025, 5, 4),
            min_value=date(2024, 8, 1),
            max_value=date(2025, 6, 1),
            label_visibility="collapsed",
            help="Free plan 2022-2024 sezonu erişebilir.",
        )
        c1, c2 = st.columns(2)
        with c1:
            db_d = st.number_input("Önceki gün", 0, 14, 1, 1)
        with c2:
            da_d = st.number_input("Sonraki gün", 0, 14, 6, 1)

        st.markdown("## 💰 Bütçe")
        bankroll = st.number_input("Bankroll (₺)", 500, 1_000_000, 10000, 500,
                                   label_visibility="collapsed")
        kf = st.slider("Risk (Kelly)", 0.10, 1.0, 0.25, 0.05,
                       help="0.25 önerilir (varyansı yarıya indirir)")

        st.markdown("## 📊 Sistem")
        s = db_stats()
        st.caption(f"📦 DB: **{s['total_fixtures']:,}** maç")
        st.caption(f"🌐 API bugün: **{s['api_today']['n'] or 0}** / 100")
        if (s['api_today']['n'] or 0) > 80:
            st.warning("⚠️ Günlük API kotası dolmak üzere")

        st.markdown("---")
        st.caption("**BAHIS AGENT** v0.6 · Eğitim/araştırma amaçlıdır")
        st.caption("18+ · [Yeşilay 0850 222 39 39](tel:08502223939)")

        return page, league, anchor, db_d, da_d, bankroll, kf


# ============================================================
# YENİ SAYFALAR (SaaS multi-page)
# ============================================================

def page_selective_edge():
    """🏆 SELECTIVE EDGE v1.2 — Haftanın 3 Maçı (PURE DATA)."""
    st.markdown(
        "<h1 style='font-size:2rem;background:linear-gradient(90deg,#00B14F,#FFD600);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:900'>"
        "🏆 Haftanın 3 Maçı — SELECTIVE EDGE v1.2</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color:#4B5563;font-size:1.02rem;line-height:1.55;margin-bottom:1.2rem'>"
        "<b>Pure data, no humans.</b> Yorumcu sinyali çıkarıldı — yalnız iddaa API "
        "verisi + matematik. Sinyaller: "
        "<b>cross-market anomali (0.40) + DC model divergence (0.30) + line movement (0.15) + market consistency (0.15)</b>."
        "</p>",
        unsafe_allow_html=True
    )

    if not SELECTIVE_AVAILABLE:
        st.error(f"SELECTIVE EDGE modülleri yüklenemedi: {_SELECTIVE_ERR}")
        return

    # ─── Snapshot info ───
    import sqlite3
    conn = sqlite3.connect(YAZILIM_DIR / "02_VERI" / "bahis_agent.db")
    conn.row_factory = sqlite3.Row
    snap_row = conn.execute(
        "SELECT snapshot_id, COUNT(DISTINCT iddaa_match_id) as n, MAX(fetched_at) as fa "
        "FROM iddaa_odds GROUP BY snapshot_id ORDER BY snapshot_id DESC LIMIT 1"
    ).fetchone()
    n_tipsters = conn.execute("SELECT COUNT(*) FROM tipster_stats").fetchone()[0]
    conn.close()

    if not snap_row:
        st.warning("⚠️ Henüz iddaa odds snapshot'ı yok. Önce şu komutu çalıştır:")
        st.code("python 02_VERI/scrapers/iddaa_odds_scraper.py fetch")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📸 Snapshot", snap_row["snapshot_id"])
    c2.metric("⚽ Toplam maç", snap_row["n"])
    c3.metric("📊 Sinyal", "4 pure")
    c4.metric("🧪 Versiyon", "v1.2")

    # ─── Top match table ───
    with st.spinner("Sinyaller hesaplanıyor..."):
        all_signals = get_all_match_signals()

    if not all_signals:
        st.warning("Sinyal hesaplanamadı.")
        return

    all_signals.sort(key=lambda m: m["selection_score"], reverse=True)

    st.markdown("### 📊 Tüm maçların selection skoru (v1.2 — 4 pure sinyal)")
    df = pd.DataFrame([
        {
            "Maç": f"{m['home']} vs {m['away']}",
            "Score": round(m["selection_score"], 3),
            "Anomaly": round(m["s_odds_anomaly"], 2) if m["s_odds_anomaly"] is not None else None,
            "Model": round(m.get("s_model_confidence"), 2) if m.get("s_model_confidence") is not None else "N/A",
            "Sharp": round(m.get("s_sharp_money"), 2) if m.get("s_sharp_money") is not None else "N/A",
            "Cons.": round(m["s_inverse_variance"], 2) if m["s_inverse_variance"] is not None else None,
            "Yapısal yön": m["signal_direction"] or "-",
            "Model lig": m.get("model_league") or "-",
        }
        for m in all_signals[:30]
    ])
    st.dataframe(df, use_container_width=True, hide_index=True, height=420)

    # ─── TOP 3 ───
    st.markdown("---")
    st.markdown(
        "<h2 style='color:#00B14F;font-weight:800'>🥇 Seçilen 3 Maç</h2>",
        unsafe_allow_html=True
    )
    top3 = all_signals[:3]
    c1, c2, c3 = st.columns(3)
    for col, m, rank in zip([c1, c2, c3], top3, ["🥇", "🥈", "🥉"]):
        with col:
            mc = m.get("s_model_confidence")
            sm = m.get("s_sharp_money")
            mc_str = f"<b>{mc:.2f}</b>" if mc is not None else "<i style='color:#9CA3AF'>N/A</i>"
            sm_str = f"<b>{sm:.2f}</b>" if sm is not None else "<i style='color:#9CA3AF'>N/A</i>"
            model_lig = m.get("model_league") or "—"
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#E6F7EE,#FFFEF0);"
                f"border:1px solid #00B14F;border-radius:14px;padding:18px;min-height:240px'>"
                f"<div style='font-size:1.6rem'>{rank}</div>"
                f"<div style='font-weight:800;font-size:1.05rem;color:#003F19'>{m['home']}</div>"
                f"<div style='color:#6B7280;text-align:center;margin:6px 0;font-size:0.85rem'>vs</div>"
                f"<div style='font-weight:800;font-size:1.05rem;color:#003F19'>{m['away']}</div>"
                f"<hr style='border:none;border-top:1px dashed #B7E5C9;margin:10px 0'>"
                f"<div style='font-size:0.82rem;color:#4B5563;line-height:1.6'>"
                f"  Skor: <b style='color:#00B14F'>{m['selection_score']:.3f}</b><br>"
                f"  Yapısal yön: <b>{m['signal_direction'] or '-'}</b><br>"
                f"  Anomaly: <b>{(m['s_odds_anomaly'] or 0):.2f}</b><br>"
                f"  Model ({model_lig}): {mc_str}<br>"
                f"  Sharp money: {sm_str}<br>"
                f"  Consistency: <b>{(m['s_inverse_variance'] or 0):.2f}</b><br>"
                f"</div></div>",
                unsafe_allow_html=True
            )

    # ─── KOMBINASYON OPTIMIZER ───
    st.markdown("---")
    st.markdown(
        "<h2 style='color:#00B14F;font-weight:800'>🎯 Kombinasyon Optimizer</h2>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color:#4B5563'>"
        "Her maçta 7 pazar (1X2 × 3 + A/Ü × 2 + KG × 2) → "
        "<b>7³ = 343 kombinasyon</b>. Sistem 3 risk tier'ında en iyi 3-leg kuponu seçer.</p>",
        unsafe_allow_html=True
    )

    with st.spinner("343 kombinasyon hesaplanıyor..."):
        result = optimize_combinations([m["iddaa_match_id"] for m in top3])

    tiers = [
        ("GARANTI", "🛡️", "Yüksek olasılık, makul getiri", "#10B981"),
        ("DENGELI", "⚖️", "Risk-getiri dengeli", "#3B82F6"),
        ("YUKSEK_EV", "🚀", "Maksimum EV, yüksek risk", "#EF4444"),
    ]
    for tier_key, emoji, desc, color in tiers:
        c = result.get(tier_key)
        if not c:
            continue
        st.markdown(
            f"<div style='border-left:5px solid {color};background:white;"
            f"border-radius:10px;padding:16px;margin:10px 0;"
            f"box-shadow:0 2px 8px rgba(0,0,0,0.04)'>"
            f"<div style='font-size:1.2rem;font-weight:800;color:{color}'>"
            f"{emoji} {tier_key}</div>"
            f"<div style='color:#6B7280;margin-bottom:8px'>{desc}</div>"
            f"<div style='display:flex;gap:24px;margin:10px 0'>"
            f"  <div><b>Joint Prob</b><br><span style='font-size:1.2rem'>{c['joint_prob']*100:.1f}%</span></div>"
            f"  <div><b>Kombine Oran</b><br><span style='font-size:1.2rem'>{c['combined_odds']:.2f}</span></div>"
            f"  <div><b>EV (1 birim)</b><br><span style='font-size:1.2rem;color:{'#10B981' if c['ev']>0 else '#EF4444'}'>{c['ev']*100:+.1f}%</span></div>"
            f"  <div><b>Risk</b><br><span style='font-size:1.2rem'>{c['risk']:.3f}</span></div>"
            f"  <div><b>Sharpe</b><br><span style='font-size:1.2rem'>{c['sharpe']:.2f}</span></div>"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )
        legs_df = pd.DataFrame([
            {
                "Maç": leg["match"],
                "Seçim": leg["label"],
                "Oran": leg["odd"],
                "Fair Prob": f"{leg['fair_prob']*100:.0f}%",
            }
            for leg in c["legs"]
        ])
        st.dataframe(legs_df, use_container_width=True, hide_index=True)

    # ─── BİLİMSEL UYARI ───
    st.markdown(
        "<div class='notice-panel' style='margin-top:1.5rem'>"
        "<b>⚠️ Bilimsel uyarı:</b> Bu pipeline iddaa.com'un kendi pazarlarındaki "
        "tutarsızlıkları ve yorumcu konsensüsünü bir araya getirir. "
        "<b>iddaa'nın overround'u %15-20</b> (küçük liglerde) olduğu için "
        "saf negatif EV görmek normal. Edge ancak <b>tipster track-record veya "
        "model güveni</b> bookmaker'la ters düştüğünde ortaya çıkar."
        "</div>",
        unsafe_allow_html=True
    )


def page_haftanin_kombini():
    """🎯 T05 Production — Haftanın 1 kombini, FAV_CONFIRMED stratejisi."""
    st.markdown(
        "<h1 style='font-size:2rem;background:linear-gradient(90deg,#00B14F,#FFD600);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:900'>"
        "🎯 Haftanın Kombini (T05)</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color:#4B5563;font-size:1.0rem;line-height:1.55'>"
        "<b>v4 — T14+T15 sonrası 3-lig paralel:</b> Her ligten (T1+E0+D1) ayrı K=3 kombin. "
        "Flat 1000 TL/kupon. <b>4 sezon backtest: 397 kupon, NET +80,672 TL, "
        "aylık +1,779 TL.</b><br>"
        "T1 saf (+62K) yüksek ROI ama az hacim; 3-lig paralel daha yüksek toplam kazanç. "
        "Skip rule (T15 overfit) ve pause (T16 gambler's fallacy) KULLANILMAZ."
        "</p>",
        unsafe_allow_html=True
    )

    sys.path.insert(0, str(YAZILIM_DIR / "03_MODELLER" / "selective"))
    from weekly_kombin import get_weekly_kombin

    import sqlite3
    db_path = YAZILIM_DIR / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    days = pd.read_sql_query(
        "SELECT DISTINCT substr(kickoff_iso,1,10) as d FROM signal_snapshots "
        "WHERE source='football_data' AND league_code IN ('E0','T1') "
        "ORDER BY d DESC LIMIT 30", conn
    )
    conn.close()

    if days.empty:
        st.warning("signal_snapshots tablosu boş.")
        return

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        matchday = st.selectbox("Matchday seç (backtest)", days["d"].tolist())
    with c2:
        K = st.selectbox("Combo legs (K)", [1, 2, 3, 4], index=2,
                         help="v4 winner: K=3 (T06)")
    with c3:
        leagues = st.multiselect("Lig", ["T1", "E0", "D1"],
                                 default=["T1", "E0", "D1"],
                                 help="v4: 3-lig paralel flat 1000 TL = en yüksek mutlak kazanç "
                                      "(+81K). T1 only ROI %60 daha yüksek (+62K daha az hacim).")

    if not leagues:
        st.warning("En az 1 lig seç.")
        return

    result = get_weekly_kombin(matchday=matchday, K=K, leagues=leagues,
                              source="football_data")

    if result.get("error"):
        st.warning(f"❌ {result['error']} — başka bir matchday dene")
        return

    # ÖZET
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Legs", f"{result['found']}/{K}")
    c2.metric("Combo Odd", f"{result['combo_odd']:.2f}")
    c3.metric("Implied Fair", f"{result['implied_fair_prob']*100:.1f}%")
    settled = all(leg["settled"] for leg in result["legs"])
    all_won = all(leg["direction"] in (leg["result_1x2"], "H" if leg["result_1x2"]=="H" else None)
                  for leg in result["legs"]) if settled else None
    if settled:
        # Better check: each leg actually matched
        def leg_won(leg):
            d = leg["direction"]
            r = leg["result_1x2"]
            if d in ("HOME","H","1"): return r == "H"
            if d in ("AWAY","A","2"): return r == "A"
            if d in ("DRAW","D","X"): return r == "D"
            return False
        all_won = all(leg_won(leg) for leg in result["legs"])
        if all_won:
            c4.metric("Sonuç", "✅ TUTTU",
                     f"+{(result['combo_odd']-1)*100:.0f}%")
        else:
            c4.metric("Sonuç", "❌ tutmadı", "-100%")
    else:
        c4.metric("Sonuç", "henüz", "—")

    # LEG KARTLARI
    st.markdown("### 🎲 Leg Detayları")
    for i, leg in enumerate(result["legs"], 1):
        color = "#10B981" if leg["settled"] else "#3B82F6"
        if leg["settled"]:
            d = leg["direction"]; r = leg["result_1x2"]
            won = (d in ("HOME","H","1") and r=="H") or \
                  (d in ("AWAY","A","2") and r=="A") or \
                  (d in ("DRAW","D","X") and r=="D")
            color = "#10B981" if won else "#EF4444"
            badge = "✅ TUTTU" if won else "❌ tutmadı"
        else:
            badge = "⏱️ pending"

        st.markdown(
            f"<div style='border-left:5px solid {color};background:white;"
            f"border-radius:10px;padding:16px;margin:8px 0;"
            f"box-shadow:0 2px 8px rgba(0,0,0,0.04)'>"
            f"<div style='display:flex;justify-content:space-between'>"
            f"  <div><b>Leg {i}</b> · {leg['league']} {leg['season']}</div>"
            f"  <div>{badge}</div>"
            f"</div>"
            f"<div style='font-size:1.2rem;font-weight:700;color:#003F19;margin-top:6px'>"
            f"  {leg['home']} vs {leg['away']}"
            f"</div>"
            f"<div style='display:flex;gap:24px;margin-top:8px;font-size:0.9rem;color:#4B5563'>"
            f"  <div>Pick: <b>{leg['direction_label']}</b></div>"
            f"  <div>Odd: <b>{leg['odd']:.2f}</b></div>"
            f"  <div>Score: <b>{leg['score']:.2f}</b></div>"
            f"  <div>Agree: <b>{leg['agree_count']}</b></div>"
            f"</div>"
            f"<div style='margin-top:8px;color:#6B7280;font-size:0.85rem'>"
            f"  Teyit eden sinyaller: {', '.join(leg['confirmers']) if leg['confirmers'] else '—'}"
            f"</div>"
            f"</div>",
            unsafe_allow_html=True
        )

    # BACKTEST İSPATI (v4)
    st.markdown("---")
    st.markdown(
        "<div style='background:#F3F4F6;border-radius:10px;padding:14px'>"
        "<b>📊 T01-T16 v4 Birleşik (4 sezon × 4188 maç, 16 test):</b><br>"
        "<br>"
        "<b>🥇 3-lig paralel K=3 flat 1000 TL/kupon</b>: 397 kupon, <b>NET +80,672 TL</b>, "
        "aylık +1,779 TL, ROI +20.3% ✅<br>"
        "<b>🥈 T1-only K=3</b>: 103 kupon, <b>NET +62,143 TL</b>, ROI +60.3%, "
        "CI95 [+3.6, +125.1] ✅ (out-of-sample T15: +81.4%)<br>"
        "<b>🥉 ALL K=2 FAV_CONFIRMED</b>: 461 kupon, ROI +14.3%, CI95 [+0.1, +27.7]<br>"
        "<br>"
        "<b>Reddedilenler (negatif bilim):</b> Skip dark weeks (T15 overfit), "
        "Loss-streak pause (T16 gambler's fallacy), D1 standalone (-1.7%), "
        "Cross-only 3 ayrı lig (-2.2%), strict filter ≥2 confirmer (sample çöker), "
        "Full Kelly (96.5% drawdown)"
        "</div>",
        unsafe_allow_html=True
    )


def page_signal_pivot():
    """📊 Sinyal Pivot — 4188 backtest maçı, canlı filtre + strateji testi."""
    st.markdown(
        "<h1 style='font-size:2rem;background:linear-gradient(90deg,#00B14F,#FFD600);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-weight:900'>"
        "📊 Sinyal Pivot — 4188 maç</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<p style='color:#4B5563;font-size:1.0rem;line-height:1.55'>"
        "4 sezon × 3 lig × 4,188 maç backtest verisi. Sinyaller hazır, "
        "filtre + sort + strateji deneme canlı. Bulgu replikasyonu için ideal."
        "</p>",
        unsafe_allow_html=True
    )

    import sqlite3
    db_path = YAZILIM_DIR / "02_VERI" / "bahis_agent.db"
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query(
        "SELECT * FROM signal_snapshots WHERE source='football_data'", conn
    )
    conn.close()
    if df.empty:
        st.warning("signal_snapshots tablosu boş. Önce çalıştır:")
        st.code("python 02_VERI/signal_snapshots.py load")
        return

    # ─── FILTRES (sidebar tarzı 4 kolon)
    st.markdown("### 🎛️ Filtreler")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        leagues = st.multiselect("Lig", sorted(df["league_code"].unique()),
                                 default=sorted(df["league_code"].unique()))
    with c2:
        seasons = st.multiselect("Sezon", sorted(df["season"].unique()),
                                 default=sorted(df["season"].unique()))
    with c3:
        agree_min = st.slider("Min AGREE count", 0, 4, 0)
    with c4:
        score_min = st.slider("Min score_v13", 0.0, 1.0, 0.0, 0.05)

    c5, c6, c7, c8 = st.columns(4)
    with c5:
        odd_min = st.slider("Min favori odd", 1.0, 5.0, 1.0, 0.1)
    with c6:
        odd_max = st.slider("Max favori odd", 1.0, 10.0, 10.0, 0.1)
    with c7:
        require_xg = st.checkbox("Sadece xG var")
    with c8:
        require_form = st.checkbox("Sadece form var")

    # Apply filters
    flt = df[
        df["league_code"].isin(leagues) &
        df["season"].isin(seasons) &
        (df["agree_count"].fillna(0) >= agree_min) &
        (df["score_v13"].fillna(0) >= score_min) &
        (df["odd_1"].fillna(99) >= odd_min) &
        (df["odd_1"].fillna(0) <= odd_max)
    ]
    if require_xg:
        flt = flt[flt["s_xg"].fillna(0) > 0]
    if require_form:
        flt = flt[flt["s_form"].fillna(0) > 0]

    st.metric("Filtre sonrası maç sayısı", f"{len(flt):,}")

    # ─── STRATEGY TEST
    st.markdown("### 🎯 Strateji testi")
    strategy = st.selectbox(
        "Strateji",
        ["Hep favori", "v1.3 model_direction", "Consensus", "Favori + xG agree",
         "AGREE 2/3", "AGREE 3/3", "Sweet-spot (score+odd)"]
    )

    # Strateji eval
    def eval_strategy():
        if strategy == "Hep favori":
            picks = flt[flt["dir_favorite"].notna()]
            return picks, "dir_favorite"
        elif strategy == "v1.3 model_direction":
            picks = flt[(flt["dir_model"].notna()) & (flt["score_v13"] >= 0.75)]
            return picks, "dir_model"
        elif strategy == "Consensus":
            picks = flt[flt["dir_consensus"].notna()]
            return picks, "dir_consensus"
        elif strategy == "Favori + xG agree":
            picks = flt[
                flt["dir_favorite"].notna() &
                flt["dir_xg"].notna() &
                (
                    ((flt["dir_favorite"] == "H") & (flt["dir_xg"] == "HOME")) |
                    ((flt["dir_favorite"] == "A") & (flt["dir_xg"] == "AWAY"))
                )
            ]
            return picks, "dir_favorite"
        elif strategy == "AGREE 2/3":
            picks = flt[(flt["agree_count"] >= 2) & (flt["signal_count"] >= 3)]
            return picks, "dir_consensus"
        elif strategy == "AGREE 3/3":
            picks = flt[(flt["agree_count"] >= 3) & (flt["signal_count"] >= 3)]
            return picks, "dir_consensus"
        elif strategy == "Sweet-spot (score+odd)":
            picks = flt[
                (flt["score_v13"] >= 0.65) & (flt["score_v13"] <= 0.85) &
                (flt["odd_1"] >= 2.0) & (flt["odd_1"] <= 3.5)
            ]
            return picks, "dir_favorite"
        return flt, "dir_favorite"

    picks, dir_col = eval_strategy()

    if len(picks) == 0:
        st.warning("0 maç eşleşti. Filtreyi gevşet.")
        return

    # Outcome eval
    pnls = []
    for _, r in picks.iterrows():
        d = r.get(dir_col)
        if not d or pd.isna(d) or not r.get("settled"):
            continue
        # Get odd for this direction
        odd = None
        if d in ("HOME", "H", "1"): odd = r["odd_1"]
        elif d in ("AWAY", "A", "2"): odd = r["odd_2"]
        elif d in ("DRAW", "D", "X"): odd = r["odd_X"]
        elif d == "Over": odd = r["odd_over25"]
        elif d == "Under": odd = r["odd_under25"]
        if not odd or odd < 1.01:
            continue
        # Did it win?
        ftr = r.get("result_1x2")
        tg = r.get("total_goals")
        won = False
        if d in ("HOME", "H", "1"): won = ftr == "H"
        elif d in ("AWAY", "A", "2"): won = ftr == "A"
        elif d in ("DRAW", "D", "X"): won = ftr == "D"
        elif d == "Over": won = tg is not None and tg > 2.5
        elif d == "Under": won = tg is not None and tg < 2.5
        pnls.append((odd - 1) if won else -1)

    if not pnls:
        st.warning("Outcome'lu bet yok.")
        return

    n = len(pnls)
    hit = sum(1 for p in pnls if p > 0) / n
    roi = sum(pnls) / n
    # Bootstrap CI
    rng = np.random.RandomState(42)
    boot = [rng.choice(pnls, size=n, replace=True).mean() for _ in range(1000)]
    ci_low, ci_high = np.percentile(boot, [2.5, 97.5])

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("n bet", n)
    c2.metric("Hit rate", f"{hit*100:.1f}%")
    roi_color = "+" if roi > 0 else ""
    c3.metric("ROI", f"{roi*100:+.2f}%")
    c4.metric("CI95 alt", f"{ci_low*100:+.1f}%")
    c5.metric("CI95 üst", f"{ci_high*100:+.1f}%")

    if ci_low > 0:
        st.success(f"✅ EDGE pozitif (95% CI tamamen sıfır üstü)")
    elif ci_high < 0:
        st.error(f"❌ EDGE negatif (95% CI tamamen sıfır altı)")
    else:
        st.info(f"⚠️ Belirsiz (CI sıfırı içeriyor)")

    # ─── PIVOT TABLE
    st.markdown("### 📊 Pivot Tablo (lig × sezon → ROI)")
    if pnls:
        # Match pnl with picks
        picks_with_pnl = picks.copy()
        pnl_list = []
        for _, r in picks.iterrows():
            d = r.get(dir_col)
            if not d or pd.isna(d) or not r.get("settled"):
                pnl_list.append(None); continue
            odd = None
            if d in ("HOME", "H", "1"): odd = r["odd_1"]
            elif d in ("AWAY", "A", "2"): odd = r["odd_2"]
            elif d in ("DRAW", "D", "X"): odd = r["odd_X"]
            elif d == "Over": odd = r["odd_over25"]
            elif d == "Under": odd = r["odd_under25"]
            if not odd or odd < 1.01:
                pnl_list.append(None); continue
            ftr = r.get("result_1x2"); tg = r.get("total_goals")
            won = False
            if d in ("HOME", "H", "1"): won = ftr == "H"
            elif d in ("AWAY", "A", "2"): won = ftr == "A"
            elif d in ("DRAW", "D", "X"): won = ftr == "D"
            elif d == "Over": won = tg is not None and tg > 2.5
            elif d == "Under": won = tg is not None and tg < 2.5
            pnl_list.append((odd - 1) if won else -1)
        picks_with_pnl["pnl"] = pnl_list
        pwp = picks_with_pnl[picks_with_pnl["pnl"].notna()]
        if not pwp.empty:
            pivot = pwp.pivot_table(
                index="league_code", columns="season", values="pnl",
                aggfunc=["count", "mean"]
            )
            st.dataframe(pivot.round(3), use_container_width=True)

    # ─── DETAY TABLO
    with st.expander(f"Detay: {len(picks)} maç"):
        show_cols = ["league_code", "season", "kickoff_iso", "home_team", "away_team",
                     "score_v13", "agree_count", "dir_consensus", "dir_favorite",
                     "odd_1", "odd_X", "odd_2", "result_1x2",
                     "s_anomaly", "s_model", "s_xg", "s_form"]
        avail_cols = [c for c in show_cols if c in picks.columns]
        st.dataframe(picks[avail_cols].head(200), use_container_width=True, hide_index=True)


def page_kuponlar(league, anchor, db_d, da_d, bankroll, kf, league_name):
    """🏠 Ana sayfa — mevcut akış."""
    params = load_dc_params(league)
    platt = load_platt(league)
    if params is None:
        st.error(f"{league_name} için model yok.")
        return

    fixtures = get_fixtures(league, anchor.isoformat(), db_d, da_d)
    predictions = [predict(params, f["home_team"], f["away_team"], platt)
                  for f in fixtures]
    coupons = build_coupons([p for p in predictions if p], bankroll, kf)
    bet_log = load_bet_log()

    render_header(league_name, anchor, len(fixtures))
    render_hero(predictions, league_name, anchor, db_d, da_d)
    render_kpis(predictions, bet_log, bankroll)

    left, right = st.columns([2.2, 1])
    with left:
        st.markdown(
            "<div class='section-title'><div class='bar'></div>"
            "<span>📋 Bülten · Model Tahminleri</span></div>",
            unsafe_allow_html=True)
        render_fixtures_panel(fixtures, predictions, league_name)
    with right:
        render_coupon_panel(coupons)

    cands = find_candidates([p for p in predictions if p])
    render_data_panels(bet_log, params, cands)

    st.markdown(
        "<div class='notice-panel'>"
        "<b>⚠️ Bilimsel uyarı:</b> Backtest ROI +%9 görünse de "
        "<b>CLV ortalaması -%1.85</b> (n=577, p=0.0000). Kazancın "
        "<b>şans</b> olabileceğine işaret eder. Detay: 🔬 Bilimsel Kanıt sayfası."
        "</div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='disclaimer'>"
        "<b>Sorumluluk reddi:</b> BAHIS AGENT bir karar destek aracıdır, kazanç garantisi vermez. "
        "Tüm bahisler kullanıcının kendi sorumluluğundadır. 18 yaş altı kullanamaz. "
        "Yardım: <b>0850 222 39 39</b> (Yeşilay)."
        "</div>", unsafe_allow_html=True)


def page_tavsiye_edilen_kuponlar(league: str, bankroll: float, kf: float):
    """🎯 Tavsiye Edilen Kuponlar — kullanıcı bu haftanın maçlarını girer, sistem analiz eder."""
    st.markdown("<h1 style='font-size:1.8rem'>🎯 Tavsiye Edilen Kuponlar</h1>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4B5563;font-size:1rem;margin-bottom:1rem'>"
        "<b>Bu haftaki maçlar</b> için custom analiz. iddaa.com bülteninde gördüğün "
        "maçları aşağıya gir — modelimiz tahmin verir ve <b>3 risk seviyesinde kupon</b> önerir."
        "</p>", unsafe_allow_html=True)

    params = load_dc_params(league)
    platt = load_platt(league)
    league_name = LEAGUES.get(league, league)

    if params is None:
        st.error(f"{league_name} için model yok. Önce fit_and_save.py çalıştır.")
        return

    available_teams = sorted(params.teams)

    st.markdown(
        f"<div style='background:#E6F7EE;border-left:4px solid #00B14F;"
        f"padding:10px 14px;border-radius:8px;margin-bottom:1.5rem'>"
        f"<b>📋 Aktif Lig:</b> {league_name}  ·  "
        f"<b>Modeldeki takım:</b> {len(available_teams)}  ·  "
        f"<i>Sidebar'dan lig değiştirebilirsin</i>"
        f"</div>",
        unsafe_allow_html=True
    )

    tab1, tab2 = st.tabs(["✏️ Tek tek maç ekle", "📋 Toplu paste (iddaa bülteni)"])

    # ─── Session state init ───
    if "custom_matches" not in st.session_state:
        st.session_state["custom_matches"] = []

    # ─── TAB 1: TEK TEK EKLE ───
    with tab1:
        st.markdown("**Bu haftaki bir maç ekle:**")
        c1, c2, c3 = st.columns([3, 3, 1])
        with c1:
            home_team = st.selectbox(
                "Ev sahibi", available_teams,
                key="manual_home", index=0 if available_teams else None,
            )
        with c2:
            # Ev sahibini default'a hariç tut
            away_options = [t for t in available_teams if t != home_team]
            away_team = st.selectbox(
                "Deplasman", away_options,
                key="manual_away", index=0 if away_options else None,
            )
        with c3:
            st.write("&nbsp;")  # boşluk
            if st.button("➕ Ekle", use_container_width=True, key="add_match"):
                st.session_state["custom_matches"].append({
                    "home": home_team, "away": away_team,
                    "league": league,
                })
                st.rerun()

    # ─── TAB 2: TOPLU PASTE ───
    with tab2:
        st.markdown(
            "**iddaa.com bülteninden maçları yapıştır** (her satır bir maç, format: `Ev Takım - Dep Takım`)")
        paste_text = st.text_area(
            "Maçlar",
            placeholder="Galatasaray - Fenerbahce\nBesiktas - Trabzonspor\nKonyaspor - Antalyaspor",
            height=160, key="paste_area",
            label_visibility="collapsed",
        )
        cc1, cc2 = st.columns([1, 4])
        with cc1:
            if st.button("📥 Yükle", use_container_width=True, key="paste_btn"):
                added = 0
                skipped = []
                for line in paste_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    # "Ev - Dep" veya "Ev vs Dep" formatı
                    for sep in [" - ", " vs ", " VS ", " v ", "\t"]:
                        if sep in line:
                            parts = line.split(sep, 1)
                            home_raw = parts[0].strip()
                            away_raw = parts[1].strip()
                            # Fuzzy: takım adının baş kısmı eşleşsin
                            home_match = None; away_match = None
                            for t in available_teams:
                                if t.lower() == home_raw.lower() or t.lower().startswith(home_raw.lower()[:5]):
                                    home_match = t
                                    break
                            for t in available_teams:
                                if t.lower() == away_raw.lower() or t.lower().startswith(away_raw.lower()[:5]):
                                    away_match = t
                                    break
                            if home_match and away_match:
                                st.session_state["custom_matches"].append({
                                    "home": home_match, "away": away_match,
                                    "league": league,
                                })
                                added += 1
                            else:
                                skipped.append(line)
                            break
                if added > 0:
                    st.success(f"✅ {added} maç eklendi")
                if skipped:
                    st.warning(f"⚠️ {len(skipped)} maç bulunamadı (takım modelde yok): {skipped[:3]}")
                if added > 0:
                    st.rerun()

    # ─── MEVCUT MAÇLAR LİSTESİ ───
    matches = st.session_state["custom_matches"]
    if matches:
        st.markdown(f"### 📋 Analiz Edilecek Maçlar ({len(matches)})")
        if st.button("🗑️ Hepsini temizle", key="clear_all"):
            st.session_state["custom_matches"] = []
            st.rerun()

        # Predict each
        predictions = []
        for i, m in enumerate(matches):
            pred = predict(params, m["home"], m["away"], platt)
            if pred:
                pred["_idx"] = i
                pred["_league"] = m["league"]
                predictions.append(pred)

        # iddaa-bülteni tarzı liste
        bul_parts = []
        for i, pred in enumerate(predictions):
            picks = best_picks_for_match(pred)
            odds_html = (
                "<div class='bul-odds'>"
                + _odd_box("1", pred["p_1"], picks["ms"] == "1")
                + _odd_box("X", pred["p_X"], picks["ms"] == "X")
                + _odd_box("2", pred["p_2"], picks["ms"] == "2")
                + "<div style='width:8px'></div>"
                + _odd_box("Alt", pred["p_under25"], picks["au"] == "Alt")
                + _odd_box("Üst", pred["p_over25"], picks["au"] == "Üst")
                + "<div style='width:8px'></div>"
                + _odd_box("KG V", pred["p_btts"], picks["kg"] == "Var")
                + _odd_box("KG Y", pred["p_btts_no"], picks["kg"] == "Yok")
                + "</div>"
            )
            bul_parts.append(
                f"<div class='bul-card'>"
                f"<div class='bul-time'>#{i+1}</div>"
                f"<div class='bul-teams'>"
                f"<div>{pred['home']} <span style='color:#94A3B8'>vs</span> {pred['away']}</div>"
                f"<div class='bul-result'>λ ev {pred['lam_h']:.2f} · λ dep {pred['lam_a']:.2f}</div>"
                f"</div>"
                f"{odds_html}"
                f"</div>"
            )
        st.markdown("".join(bul_parts), unsafe_allow_html=True)

        # ─── ANALİZ + KUPON ÖNERİSİ ───
        st.markdown("---")
        st.markdown("### 💎 Tavsiye Edilen Kuponlar")

        coupons = build_coupons(predictions, bankroll, kf)
        cands = find_candidates(predictions)

        # 3 sütun: konservatif / dengeli / agresif
        col1, col2, col3 = st.columns(3)
        for key, col in zip(["konservatif", "dengeli", "agresif"],
                             [col1, col2, col3]):
            with col:
                legs, stats = coupons[key]
                meta = KUPON_META[key]

                if legs is None or legs.empty:
                    st.markdown(
                        f"<div class='tier-card {meta['cls']}'>"
                        f"<div class='tier-header'>{meta['tag']}</div>"
                        f"<div class='tier-title'>{meta['title']}</div>"
                        f"<div class='tier-desc'>{meta['desc']}</div>"
                        f"<div style='padding:15px 0;color:#9CA3AF;text-align:center'>"
                        f"Bu seviyede uygun bahis bulunamadı"
                        f"</div></div>",
                        unsafe_allow_html=True
                    )
                    continue

                legs_html = []
                for _, r in legs.iterrows():
                    legs_html.append(
                        f"<div class='tier-leg'>"
                        f"<div class='tier-leg-match'>{r['match']}</div>"
                        f"<div class='tier-leg-pick'>{r['pick']} @{r['market']:.2f}</div>"
                        f"<div class='tier-leg-meta'>"
                        f"Olasılık <b>%{r['p']*100:.0f}</b> · "
                        f"<span class='edge'>Edge +%{r['edge_pct']:.1f}</span>"
                        f"</div></div>"
                    )

                st.markdown(
                    f"<div class='tier-card {meta['cls']}'>"
                    f"<div class='tier-header'>{meta['tag']}</div>"
                    f"<div class='tier-title'>{meta['title']}</div>"
                    f"<div class='tier-desc'>{meta['desc']}</div>"
                    f"{''.join(legs_html)}"
                    f"<div class='tier-footer'>"
                    f"<div class='tier-stat'><span class='tier-stat-label'>Toplam oran</span>"
                    f"<span class='tier-stat-value'>{stats['odds']:.2f}</span></div>"
                    f"<div class='tier-stat'><span class='tier-stat-label'>Tutma şansı</span>"
                    f"<span class='tier-stat-value'>%{stats['prob']*100:.0f}</span></div>"
                    f"<div class='tier-stat'><span class='tier-stat-label'>Önerilen stake</span>"
                    f"<span class='tier-stat-value'>{stats['stake']:.0f} ₺</span></div>"
                    f"</div>"
                    f"<div class='tier-potansiyel'>"
                    f"🎯 Tutarsa <b>{stats['return']:.0f} ₺</b> "
                    f"<span style='font-size:0.85rem;color:#16A34A'>"
                    f"(+{stats['profit']:.0f}₺)</span>"
                    f"</div></div>",
                    unsafe_allow_html=True
                )

        # ─── EN İYİ TEK BAHİSLER ───
        if not cands.empty:
            st.markdown("---")
            st.markdown("### 🔍 En Yüksek Edge'li Tek Bahisler")
            top_cands = cands.head(15)
            top_cands_disp = top_cands[["match", "pick", "p", "market", "edge_pct"]].copy()
            top_cands_disp.columns = ["Maç", "Pazar", "Model %", "Oran", "Edge %"]
            top_cands_disp["Model %"] = (top_cands_disp["Model %"] * 100).round(1)
            top_cands_disp["Edge %"] = top_cands_disp["Edge %"].round(2)
            st.dataframe(top_cands_disp, use_container_width=True, hide_index=True,
                         height=min(60 + len(top_cands_disp) * 36, 500))
        else:
            st.info("Bu maçlarda edge'li bahis tespit edilmedi.")

        # ─── 🤖 SPRINT 2.3 — AI INSIGHTS (LLM Augmentation) ───
        st.markdown("---")
        st.markdown("### 🤖 AI Insights (Gemini LLM)")
        if LLM_MODE == "mock":
            st.markdown(
                "<div style='background:#FEF3C7;border-left:4px solid #F59E0B;"
                "padding:10px 14px;border-radius:8px;font-size:0.88rem;color:#78350F'>"
                "<b>⚙️ Mock mode aktif</b> — Gemini API key yok. "
                "Deterministik fake feature'lar üretiliyor (test amaçlı). "
                "Gerçek edge için <code>.env</code>'e <b>GEMINI_API_KEY</b> ekle, "
                "anında live moda geçer."
                "</div>", unsafe_allow_html=True)
        elif LLM_MODE == "live":
            st.markdown(
                "<div style='background:#D1FAE5;border-left:4px solid #00B14F;"
                "padding:10px 14px;border-radius:8px;font-size:0.88rem;color:#064E3B'>"
                "<b>✅ Gemini 1.5 Flash aktif</b> — gerçek LLM feature extraction."
                "</div>", unsafe_allow_html=True)

        if st.button("🔮 AI ile analiz et", key="run_llm_btn"):
            with st.spinner(f"LLM çağrılıyor ({LLM_MODE})..."):
                llm_results = []
                for pred in predictions:
                    try:
                        feats = extract_features_via_llm(
                            home=pred["home"], away=pred["away"],
                            match_date=datetime.now().strftime("%Y-%m-%d"),
                            texts=[],  # opsiyonel: news scrape entegrasyonu sonra
                            league=league_name,
                        )
                        llm_results.append({"match": f"{pred['home']} - {pred['away']}",
                                            **feats})
                    except Exception as e:
                        llm_results.append({"match": f"{pred['home']} - {pred['away']}",
                                            "_error": str(e)})
                st.session_state["llm_results"] = llm_results

        if "llm_results" in st.session_state and st.session_state["llm_results"]:
            llm_results = st.session_state["llm_results"]
            df_llm = pd.DataFrame([
                {k: v for k, v in r.items() if not k.startswith("_")}
                for r in llm_results if "_error" not in r
            ])
            if not df_llm.empty:
                # Sayısal sütunları yüzde formatına çevir (display için)
                num_cols = [c for c in df_llm.columns if c != "match"]
                df_disp = df_llm.copy()
                for c in num_cols:
                    df_disp[c] = df_disp[c].apply(lambda x: f"{x:+.2f}" if isinstance(x, (int, float)) else x)
                df_disp.columns = [
                    "Maç" if c == "match" else
                    {"motivation_score": "Motivasyon",
                     "key_player_doubt": "Kilit Oyuncu Riski",
                     "tactical_change": "Taktik Değişim",
                     "sentiment_home": "Ev Moral",
                     "sentiment_away": "Dep Moral",
                     "injury_severity": "Sakatlık Etkisi",
                     "narrative_strength": "Hikaye Gücü"}.get(c, c)
                    for c in df_disp.columns
                ]
                st.dataframe(df_disp, use_container_width=True, hide_index=True)

                st.markdown(
                    "<small style='color:#64748b'>"
                    "Bu feature'lar ileride LightGBM ensemble'a ortogonal input olarak "
                    "girecek. Şu an sadece görselleştirme — model eğitimi Sprint 2.3-final."
                    "</small>", unsafe_allow_html=True)

        # ─── BİLİMSEL UYARI ───
        st.markdown(
            "<div class='notice-panel'>"
            "<b>⚠️ Bilimsel uyarı:</b> Multi-league validation (n=577) "
            "CLV ortalaması <b>-%1.85 (p=0.0000)</b> verdi — yani sistem şu an "
            "Pinnacle'ı yenemiyor. Bu öneriler <b>karar destek</b> amaçlıdır, "
            "kazanç garantisi yoktur. Detay: 🔬 Bilimsel Kanıt sayfası."
            "</div>", unsafe_allow_html=True
        )
    else:
        st.info(
            "👆 Henüz maç eklenmedi. Yukarıdaki sekmelerden maç ekle, "
            "sistem analiz edip kupon önerecek."
        )

        # Örnek kullanım
        st.markdown("**💡 Örnek kullanım:**")
        st.markdown(
            "1. **Sidebar'dan** uygun ligi seç (örn. Türkiye Süper Lig)\n"
            "2. **Tab 1**'de tek tek maç ekle, veya\n"
            "3. **Tab 2**'de iddaa.com bülteninden satırları paste et\n"
            "4. Sistem her maç için **7 pazar** olasılığı hesaplar\n"
            "5. **3 risk seviyesinde** (Konservatif / Dengeli / Agresif) kupon önerir\n"
            "6. **En yüksek edge'li tek bahisler** liste halinde gösterilir"
        )


def page_performans(bet_log: pd.DataFrame | None):
    """📊 Sistem Performansı — detaylı backtest sonucu."""
    st.markdown("<h1 style='font-size:1.8rem'>📊 Sistem Performansı</h1>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4B5563;font-size:1rem;margin-bottom:1.5rem'>"
        "Backtest sonuçları, bankroll evrimi, win/loss dağılımı, "
        "lig bazında performans, edge dağılımı."
        "</p>", unsafe_allow_html=True)

    if bet_log is None or bet_log.empty:
        st.warning("Backtest verisi yok.")
        return

    # Üst KPI
    starting = 10000.0
    final = float(bet_log["bankroll_after"].iloc[-1])
    pnl = final - starting
    roi = pnl / float(bet_log["stake"].sum()) * 100
    win = float(bet_log["won"].mean() * 100)
    clv = float(bet_log["clv_pct"].mean())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Bankroll", f"{final:,.0f} ₺", f"{pnl:+,.0f}")
    c2.metric("ROI", f"%{roi:+.2f}")
    c3.metric("Win rate", f"%{win:.1f}",
              f"{int(bet_log['won'].sum())}/{len(bet_log)}")
    c4.metric("CLV", f"%{clv:+.2f}",
              "✅ pozitif" if clv > 0 else "❌ negatif")
    c5.metric("Toplam bet", f"{len(bet_log)}")

    # Equity curve
    st.markdown("### 📈 Bankroll Evrimi")
    eq = [starting] + bet_log["bankroll_after"].tolist()
    dates = [bet_log["match_date"].min()] + bet_log["match_date"].tolist()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=eq, mode="lines",
                              line=dict(color="#00B14F", width=2.5),
                              fill="tozeroy", fillcolor="rgba(0,177,79,0.08)"))
    fig.add_hline(y=starting, line_dash="dot", line_color="#9CA3AF")
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                       plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                       showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # PnL dağılımı
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 💰 PnL Dağılımı")
        wins = bet_log[bet_log["won"]]["pnl"]
        losses = bet_log[~bet_log["won"]]["pnl"]
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=wins, name="Kazanç",
                                    marker_color="#16A34A", opacity=0.7, nbinsx=25))
        fig.add_trace(go.Histogram(x=losses, name="Kayıp",
                                    marker_color="#DC2626", opacity=0.7, nbinsx=25))
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                          barmode="overlay",
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### 🎯 Edge Dağılımı")
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=bet_log["edge_pct"], marker_color="#00B14F",
                                    opacity=0.8, nbinsx=30))
        fig.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # Bet log
    st.markdown("### 📋 Tüm Bahisler")
    df_view = bet_log.copy()
    df_view["match_date"] = df_view["match_date"].dt.strftime("%Y-%m-%d")
    df_view = df_view[["match_date", "home", "away", "score", "selection",
                       "market_odds", "edge_pct", "stake", "won", "pnl",
                       "clv_pct", "bankroll_after"]]
    st.dataframe(df_view, use_container_width=True, hide_index=True, height=300)


def page_bilimsel(bet_log: pd.DataFrame | None):
    """🔬 Bilimsel Kanıt — multi-league validation."""
    st.markdown("<h1 style='font-size:1.8rem'>🔬 Bilimsel Kanıt</h1>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4B5563;font-size:1rem;margin-bottom:1rem'>"
        "Sistemin kazandırıp kazandırmadığının istatistiksel kanıtı. "
        "t-test, bootstrap, CLV analizi, lig bazlı performans."
        "</p>", unsafe_allow_html=True)

    # Multi-league rapor okun
    report_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "scientific_verdict.md"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        st.warning("Bilimsel rapor henüz yok. multi_league_backtest.py çalıştır.")

    # Multi-league bet log download
    bets_path = YAZILIM_DIR / "07_LOG_VE_RAPORLAR" / "multi_league_bets.csv"
    if bets_path.exists():
        with open(bets_path, "rb") as f:
            st.download_button("📥 Multi-league bet log indir",
                               f.read(), "multi_league_bets.csv", "text/csv")


def page_veri_setleri():
    """🌍 Veri Setleri."""
    st.markdown("<h1 style='font-size:1.8rem'>🌍 Veri Setleri</h1>",
                unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#4B5563;font-size:1rem;margin-bottom:1rem'>"
        "Sistemin beslendiği veri kaynakları, kapsam ve büyüklükler."
        "</p>", unsafe_allow_html=True)

    s = db_stats()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Toplam Maç", f"{s['total_fixtures']:,}")
    c2.metric("API Çağrı Bugün", f"{s['api_today']['n'] or 0}/100")

    # Lig bazlı
    st.markdown("### 📋 Lig Bazlı Veri Kapsamı")
    rows = []
    for lg, seasons in s["leagues"].items():
        for ss in seasons:
            rows.append({
                "Lig": lg, "Sezon": ss["season"],
                "Maç sayısı": ss["total"], "Oynanmış": ss["finished"],
                "Başlangıç": ss["first"], "Son": ss["last"],
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("### 🗄️ Ek Veri Kaynakları")
    st.markdown("""
| Kaynak | Tür | Boyut | Durum |
|---|---|---|---|
| **Football-Data.co.uk** | Tarihsel skor + Pinnacle/B365 odds | 5,180 maç (T1+E0+D1) | ✅ |
| **Understat** | xG (Top 5 Avrupa lig) | 5,330 maç | ✅ |
| **api-football** | Fixtures + sakatlık | 2,098 fixture + 15,475 injury | ✅ |
| **api-football Pro** | Canlı maçlar 2025-26 | — | ❌ Pro plan |
| **iddaa.com Yazar Yorumları** | Türkçe metin | — | ⏳ Sprint 2.3 |
| **Twitter / X** | Sosyal medya | — | ⏳ Sprint 2.3 |
| **Hava durumu** | Maç günü | — | ⏳ Sprint 2.3 |
    """)


def page_teknik_mimari():
    """🧠 Teknik Mimari."""
    st.markdown("<h1 style='font-size:1.8rem'>🧠 Teknik Mimari</h1>",
                unsafe_allow_html=True)

    st.markdown("""
### 📐 Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│  VERİ KATMANI                                                │
│  ├─ Football-Data.co.uk → matches.csv (5,180 maç)           │
│  ├─ api-football        → bahis_agent.db (fixtures + inj)   │
│  ├─ Understat           → xg_data tablosu (5,330 maç)       │
│  └─ Cache (JSON)        → her API çağrısı diskte           │
├─────────────────────────────────────────────────────────────┤
│  MODEL KATMANI                                                │
│  ├─ Dixon-Coles (1997)  → bivariate Poisson maç skoru      │
│  │   α (hücum), β (savunma), γ (ev avantajı), ρ (τ düz.)   │
│  ├─ Platt Scaling       → olasılık kalibrasyonu            │
│  ├─ Elo Ratings         → takım güç sıralaması             │
│  ├─ LightGBM Ensemble   → xG + sakatlık + Elo birleştirici  │
│  └─ Bayesian Blend      → 0.7·DC + 0.3·LGBM                │
├─────────────────────────────────────────────────────────────┤
│  KARAR KATMANI                                                │
│  ├─ Edge Detection      → p_model × odds - 1 > %X          │
│  ├─ Fractional Kelly    → bet sizing (0.25× Kelly)          │
│  ├─ Risk Tiers          → Konservatif / Dengeli / Agresif  │
│  └─ Coupon Builder      → 1-4 leg parlay önerisi           │
├─────────────────────────────────────────────────────────────┤
│  UI KATMANI                                                   │
│  ├─ Streamlit (Python)  → multi-page SaaS dashboard         │
│  ├─ Plotly              → interaktif chart'lar              │
│  └─ Custom CSS          → iddaa.com renk dili              │
└─────────────────────────────────────────────────────────────┘
```

### 🧮 Matematiksel Çekirdek

**Dixon-Coles Modeli:**

```
λ_home = exp(α_home + β_away + γ)    [ev gol beklentisi]
μ_away = exp(α_away + β_home)         [dep gol beklentisi]
P(home=i, away=j) = τ(i,j) × Pois(i;λ) × Pois(j;μ)
```

**Kelly Criterion:**
```
f* = (b·p - q) / b
stake = 0.25 × f* × bankroll  (max %3)
```

**Closing Line Value (CLV):**
```
CLV = (oran_aldığında / oran_kapanışta) - 1
CLV > 0 → uzun vadede karlı sinyal
```

### 📚 Akademik Referanslar

- **Dixon & Coles (1997)** — Modelling Association Football Scores
- **Kelly (1956)** — A New Interpretation of Information Rate
- **Constantinou & Fenton (2012)** — pi-ratings, dynamic team strength
- **Buchdahl (2016)** — Squares & Sharps, Suckers & Sharks
- **Wunderlich & Memmert (2018)** — Betting odds forecast accuracy
- **Spearman (2018)** — Beyond Expected Goals
    """)


def page_yol_haritasi():
    """🗺️ Yol Haritası."""
    st.markdown("<h1 style='font-size:1.8rem'>🗺️ Ürün Yol Haritası</h1>",
                unsafe_allow_html=True)

    roadmap_path = YAZILIM_DIR / "URUN_ROADMAP.md"
    if roadmap_path.exists():
        st.markdown(roadmap_path.read_text(encoding="utf-8"))
    else:
        st.warning("Roadmap dosyası yok.")


def page_hakkinda():
    """❓ Hakkında."""
    st.markdown("<h1 style='font-size:1.8rem'>❓ BAHIS AGENT Hakkında</h1>",
                unsafe_allow_html=True)

    problem_path = YAZILIM_DIR / "PROBLEM_TANIMI.md"
    if problem_path.exists():
        st.markdown(problem_path.read_text(encoding="utf-8"))
    else:
        st.warning("Problem tanımı yok.")


# ============================================================
# MAIN
# ============================================================

def main():
    page, league, anchor, db_d, da_d, bankroll, kf = render_sidebar()
    league_name = LEAGUES.get(league, league)
    bet_log = load_bet_log()

    # PAGE ROUTER
    if page == "🎯 Haftanın Kombini (T05 production)":
        page_haftanin_kombini()
    elif page == "🏆 Haftanın 3 Maçı (SELECTIVE EDGE)":
        page_selective_edge()
    elif page == "📊 Sinyal Pivot (Backtest 4188 maç)":
        page_signal_pivot()
    elif page == "🏠 Bu Haftanın Kuponları":
        page_kuponlar(league, anchor, db_d, da_d, bankroll, kf, league_name)
    elif page == "🎯 Tavsiye Edilen Kuponlar (Canlı)":
        page_tavsiye_edilen_kuponlar(league, bankroll, kf)
    elif page == "📈 Sistem Performansı":
        page_performans(bet_log)
    elif page == "🔬 Bilimsel Kanıt":
        page_bilimsel(bet_log)
    elif page == "🌍 Veri Setleri":
        page_veri_setleri()
    elif page == "🧠 Teknik Mimari":
        page_teknik_mimari()
    elif page == "🗺️ Yol Haritası":
        page_yol_haritasi()
    elif page == "❓ Hakkında":
        page_hakkinda()

    # Global footer
    st.markdown(
        "<div style='text-align:center;color:#9CA3AF;font-size:0.78rem;padding:1.5rem 0'>"
        "BAHIS AGENT v0.6 · Dixon-Coles + Platt + LightGBM · Kantitatif yaklaşım"
        "</div>", unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()
