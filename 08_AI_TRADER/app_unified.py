"""
AI TRADER — TEK BİRLEŞİK UYGULAMA (Single Unified App)
=======================================================
8503 + 8504 → TEK app, TEK navigasyon. Mod toggle YOK.
Tüm sayfalar tek sol menüde gruplu:

  💸 CANLI TRADER : Genel Bakış · Maçlar · Pozisyonlar · Emirler ·
                    Journal · Grafikler · Risk · Ayarlar
  📊 ANALİZ       : Canlı Takvim · Trading Desk · Kupon Mühendisi ·
                    Model Kataloğu · Analitik · Veri Kalitesi · Playbook

Çalıştır:
  python -m streamlit run app_unified.py --server.port 8500
"""
from __future__ import annotations
import sys
from pathlib import Path

import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

# ── TEK set_page_config (ilk Streamlit komutu) ─────────────────
st.set_page_config(
    page_title="AI TRADER · Digital Twin",
    page_icon="◉",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── İki modülü de import et (page fonksiyonları + CSS sabitleri) ──
import app_trader as T
import app_pro as P

# ── CSS'i HER RERUN'da yeniden enjekte et ──────────────────────
# (modül-seviyesi st.markdown sadece ilk import'ta çalışır; rerun'da kaybolur)
# Önce PRO, sonra TRADER → trader base stilleri baskın; iki sınıf seti de mevcut.
st.markdown(P.PRO_CSS, unsafe_allow_html=True)
st.markdown(T.TRADER_CSS, unsafe_allow_html=True)

# app_pro bazı sayfaları sb_bankroll session_state'i bekler → varsayılan ver
st.session_state.setdefault("sb_bankroll", 5000)

# ── SAYFA KAYIT DEFTERİ ────────────────────────────────────────
# (etiket → fonksiyon).  Trader sayfaları portfolio arg alır; analiz almaz.
TRADER_PAGES = {
    "Genel Bakış":        T.page_overview,
    "CLV · Edge Karne":   T.page_clv,
    "Hazır Kuponlar":     T.page_ready_coupons,
    "Maçlar & Sinyaller": T.page_matches,
    "Pozisyonlar":        T.page_positions,
    "Emirler":            T.page_orders,
    "Journal":            T.page_journal,
    "Grafikler":          T.page_charts,
    "Risk":               T.page_risk,
    "Ayarlar":            T.page_settings,
}
RESEARCH_PAGES = {
    "Canlı Takvim":       P.page_live_calendar,
    "Trading Desk":       P.page_trading_desk,
    "Kupon Mühendisi":    P.page_coupon_engineer,
    "Model Kataloğu":     P.page_model_catalog,
    "Analitik":           P.page_analytics,
    "Veri Kalitesi":      P.page_data_excellency,
    "Playbook":           P.page_playbook,
}

NAV_KEY = "nav_page"
if NAV_KEY not in st.session_state:
    st.session_state[NAV_KEY] = "Genel Bakış"

# ── TEK SOL MENÜ ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding:16px 14px 8px 14px;">
      <div style="color:#10d48e;font-size:21px;font-weight:900;
                  letter-spacing:0.06em;font-family:Consolas,monospace;">
        ◉ AI TRADER
      </div>
      <div style="color:#475569;font-size:10px;margin-top:2px;
                  font-family:Consolas,monospace;letter-spacing:0.04em;">
        Digital Twin · Tek Uygulama v3
      </div>
    </div>
    <div style="border-bottom:1px solid #1e293b;margin:0 0 8px 0;"></div>
    """, unsafe_allow_html=True)

    def _nav_group(title, pages):
        st.markdown(
            f'<div style="color:#64748b;font-size:9px;text-transform:uppercase;'
            f'letter-spacing:0.12em;padding:8px 14px 4px 14px;font-weight:700;">{title}</div>',
            unsafe_allow_html=True,
        )
        for label in pages:
            active = (st.session_state[NAV_KEY] == label)
            if st.button(
                ("▸ " if active else "  ") + label,
                key=f"nav_{label}",
                use_container_width=True,
                type=("primary" if active else "secondary"),
            ):
                st.session_state[NAV_KEY] = label
                st.rerun()

    _nav_group("💸 CANLI TRADER", TRADER_PAGES)
    _nav_group("📊 ANALİZ", RESEARCH_PAGES)

    import sys as _sys
    import os as _os
    _veri_path = str(Path(__file__).resolve().parent.parent / "02_VERI")
    if _veri_path not in _sys.path:
        _sys.path.insert(0, _veri_path)
    try:
        import db as _db_mod
        _db_label = "PostgreSQL" if _db_mod.is_postgres() else "bahis_agent (SQLite)"
    except Exception:
        _db_label = "bahis_agent"
    st.markdown(
        f'<div style="border-top:1px solid #1e293b;margin-top:10px;padding:8px 14px;'
        f'color:#2d3f5e;font-size:9px;font-family:Consolas,monospace;">DB: {_db_label}</div>',
        unsafe_allow_html=True,
    )

# ── SEÇİLEN SAYFAYI ÇALIŞTIR ───────────────────────────────────
selected = st.session_state[NAV_KEY]

if selected in TRADER_PAGES:
    portfolio = T.load_portfolio()
    # Trader sayfalarında üst durum çubuğu (varsa)
    try:
        T.render_status_bar(portfolio)
    except Exception:
        pass
    TRADER_PAGES[selected](portfolio)
elif selected in RESEARCH_PAGES:
    RESEARCH_PAGES[selected]()
else:
    st.error(f"Bilinmeyen sayfa: {selected}")
