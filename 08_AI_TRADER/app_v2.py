"""
◉ BETAGENTS DESK — V2
=======================================================================
Mevcut uygulamaya (app_unified, 8500) DOKUNMAZ. Ayrı dosya, ayrı port.
Son hâli oturunca geçiş yapılır.

  python -m streamlit run app_v2.py --server.port 8600

TASARIM: açık ekran finansal panel. Bloomberg terminalinin beyaz hâli —
koyu tek eleman üstteki durum şeridi, gerisi kâğıt. Rakamlar tabular
figürlü monospace (sütunlar hizalansın), metin Archivo.

ÜRÜN TEZİ — bu sayfanın var olma sebebi:
    İSABET ORANI YANILTIR. %75 isabet, oran 1,24'te KÖTÜDÜR (fiyat
    zaten %80,6 bekliyordu). %59 isabet, oran 1,84'te İYİDİR. Doğru
    ölçü isabet değil, FİYATIN BEKLEDİĞİNDEN NE KADAR FAZLASI.
    Moneyball'ın vuruş ortalaması → on-base yüzdesi geçişinin karşılığı.

    Ve kombine kupon, marjı ÇARPAR. Tek ayakta -%13, iki ayakta -%28,
    üç ayakta -%38 — hiçbir şeyde yanılmadan önce. Kupon tezgahı bunu
    ekleme yaptıkça canlı gösterir; sezginin fiyatı görünür olur.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import streamlit as st

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
sys.path.insert(0, str(THIS_DIR.parent / "02_VERI"))

try:
    st.set_page_config(page_title="BetAgents Desk", page_icon="◉",
                       layout="wide", initial_sidebar_state="collapsed")
except Exception:
    pass


# ══════════════════════════════════════════════════════════════
# VERİ
# ══════════════════════════════════════════════════════════════

def _load_env() -> None:
    """Proje kökündeki .env'i ortama al (API anahtarları). DATABASE_URL
    orada YOKSA db.py yerel SQLite'a düşer — bu meşru bir yerel geliştirme
    yolu, ama hangi veritabanına baktığın EKRANDA yazmalı."""
    import os
    for p in (THIS_DIR.parent / ".env", THIS_DIR.parent.parent / ".env"):
        if not p.exists():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except Exception:
            pass


_load_env()


def _kaynak() -> str:
    """Hangi veritabanı? Yanlış kaynağı üretim sanmak, yanlış rakama
    güvenmektir — bu yüzden durum şeridinde açıkça yazar."""
    import os
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url.startswith("postgres"):
        return "PostgreSQL · Railway"
    if os.environ.get("PGHOST"):
        return "PostgreSQL · PG*"
    return "SQLite · YEREL"


def _rows(sql: str, params: tuple = (), sessiz: bool = False) -> list[dict]:
    """Sorgu başına taze bağlantı + 1 yeniden deneme.
    (Railway PG proxy'si bağlantıyı sorgu ortasında düşürebiliyor.)

    sessiz=True: tablo henüz yoksa boş liste dön. Ölçüm defteri tablosu
    (measurement_runs) ilk koşudan önce yoktur; bunun yüzünden tüm sayfa
    çökmemeli — eksik bir panel, çöken bir sayfadan iyidir."""
    import db as _db
    last: Exception | None = None
    for _ in (1, 2):
        conn = None
        try:
            conn = _db.connect()
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        except Exception as e:
            last = e
            msg = str(e).lower()
            if sessiz and ("no such table" in msg or "does not exist" in msg
                           or "undefinedtable" in msg):
                return []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
    if sessiz:
        return []
    raise last


# ölçülen marj katsayıları (31.08.2026, iddaa kapanış fiyatları)
MARGIN = {
    "1X2": 1.176, "UST_25": 1.174, "ALT_25": 1.174, "OU2.5": 1.174,
    "KG_VAR": 1.164, "KG_YOK": 1.164, "BTTS": 1.164,
    "1X2_OU": 1.195, "1X2_BTTS": 1.204, "OU_BTTS": 1.186,
    "TOTAL_GOALS": 1.196, "HT_FT": 1.258,
}
CODE = {"E0": "ENG", "I1": "ITA", "SP1": "ESP", "D1": "GER", "T1": "TUR",
        "F1": "FRA", "BRA1": "BRA", "USA1": "USA", "N1": "NED", "P1": "POR"}
LEAGUE = {"E0": "Premier Lig", "I1": "Serie A", "SP1": "La Liga",
          "D1": "Bundesliga", "T1": "Süper Lig", "F1": "Ligue 1",
          "BRA1": "Brasileirão", "USA1": "MLS"}
EMOJI = {
    "TEMKINLI_V1": "🛡", "AVCI_V1": "🎯", "MEMUR_V1": "📋", "HOCA_V1": "🧮",
    "SIMYACI_V1": "🧪", "POPULER_V1": "🔥", "ERKENKUS_V1": "⏰",
    "CESUR_V1": "🦁", "JOKER_V1": "🃏", "KALECI_V1": "🧤", "KONSEY_V1": "🏛",
    "TERS_V1": "🪞", "CARPAN_V1": "🎰", "SIMETRI_V1": "🔺", "KAVSAK_V1": "✖️",
    "BANT_V1": "🥅", "DEVRE_V1": "⏱", "TRIVOX_V1": "🇹🇷", "EUVOX_V1": "🇪🇺",
    "OPUS5_V1": "🧑‍💻", "KURUCU_V2": "👑", "PAPER_V1": "📚",
}
NAME = {k: k.rsplit("_", 1)[0].replace("KURUCU", "KURUCU") for k in EMOJI}


@st.cache_data(ttl=180, show_spinner=False)
def load_agents() -> list[dict]:
    """Ajan güveni — İSABET DEĞİL, fiyata göre üstünlük.

    beklenen isabet = ortalama(1/oran)   → fiyatın ima ettiği
    üstünlük        = gerçek isabet − beklenen
    hüküm           = flat_skill'in t değeri (stake-bağımsız)

    ⚠️ Kusursuz seri (hepsi kazandı/kaybetti) standart hatayı sıfıra
    çökertir ve t sonsuza gider. Bu anlamlılık DEĞİLDİR — ÖLÇÜLEMEZ."""
    rows = _rows("SELECT portfolio_id p, odds o, status s FROM paper_bets "
                 "WHERE status IN ('won','lost') AND odds > 1.01", sessiz=True)
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(r["p"], []).append(r)
    out = []
    for pid, v in by.items():
        n = len(v)
        if n < 5:
            continue
        won = sum(1 for x in v if x["s"] == "won")
        hit = won / n
        exp = sum(1.0 / float(x["o"]) for x in v) / n
        ret = [((float(x["o"]) - 1.0) if x["s"] == "won" else -1.0) for x in v]
        skill = sum(ret) / n
        var = sum((x - skill) ** 2 for x in ret) / max(n - 1, 1)
        se = math.sqrt(var / n) if var > 0 else 0.0
        perfect = (won == 0 or won == n)
        t = (skill / se) if (se > 1e-9 and not perfect) else None
        out.append({
            "pid": pid, "ad": pid.rsplit("_", 1)[0], "em": EMOJI.get(pid, "•"),
            "n": n, "hit": hit, "exp": exp, "edge": hit - exp,
            "odds": sum(float(x["o"]) for x in v) / n,
            "skill": skill, "t": t, "perfect": perfect,
        })
    out.sort(key=lambda z: -z["edge"])
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_board() -> list[dict]:
    """Açık pozisyonlar — bugünün tahtası."""
    rows = _rows(
        "SELECT bet_id, portfolio_id p, home_team h, away_team a, league lg, "
        "market mk, pick pk, odds o, kickoff_utc ko FROM paper_bets "
        "WHERE status='open' AND odds > 1.01 ORDER BY kickoff_utc LIMIT 60",
        sessiz=True)
    seen, out = set(), []
    for r in rows:
        key = (r["h"], r["a"], r["mk"], r["pk"])
        if key in seen:            # aynı seçimi birden çok ajan oynamış olabilir
            continue
        seen.add(key)
        lg = (r["lg"] or "ALL")
        out.append({
            "id": str(r["bet_id"]), "pid": r["p"],
            "em": EMOJI.get(r["p"], "•"), "ad": str(r["p"]).rsplit("_", 1)[0],
            "h": r["h"], "a": r["a"], "lg": lg,
            "code": CODE.get(lg, "—"), "lig": LEAGUE.get(lg, "lig kodlanmamış"),
            "mk": r["mk"], "pk": r["pk"], "o": float(r["o"]),
            "m": MARGIN.get(str(r["mk"]).upper(), 1.18),
            "ko": str(r["ko"])[11:16],
        })
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_rail() -> dict:
    p = _rows("SELECT COALESCE(SUM(current_bankroll),0) cb, COUNT(*) n "
              "FROM paper_portfolio", sessiz=True)
    o = _rows("SELECT COUNT(*) n FROM paper_bets WHERE status='open'", sessiz=True)
    c = _rows("SELECT COUNT(*) n FROM paper_bets WHERE status IN ('won','lost')",
              sessiz=True)
    # ölçüm defteri tablosu ilk koşudan önce YOKTUR — sessiz geç
    m = _rows("SELECT finding_id f, value v, passed g FROM measurement_runs "
              "WHERE finding_id='K_BECERI' ORDER BY ts DESC LIMIT 1", sessiz=True)
    k = m[0] if m else None
    return {"kasa": float(p[0]["cb"] or 0) if p else 0.0,
            "portfoy": int(p[0]["n"] or 0) if p else 0,
            "acik": int(o[0]["n"] or 0) if o else 0,
            "kapali": int(c[0]["n"] or 0) if c else 0,
            "kaynak": _kaynak(),
            "k": (float(k["v"]) if k else None),
            "k_gecti": (bool(k["g"]) if k else None)}


# ══════════════════════════════════════════════════════════════
# TASARIM
# ══════════════════════════════════════════════════════════════

V2_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root{
  --ground:#fcfdfe; --panel:#ffffff; --panel-2:#f6f9fb;
  --rail:#0b1420; --rail-ink:#e8edf2; --rail-dim:#7f8fa1;
  --ink:#0a1220; --ink-2:#3c4a5a; --muted:#66768a;
  --line:#e6ebf0; --line-2:#cfd8e1;
  --brand:#9a6410; --brand-fill:#f5ead6;
  --pos:#0e6b4b; --pos-fill:#e0f0e9;
  --neg:#a82f22; --neg-fill:#fae7e4;
  --warn:#8a6314; --warn-fill:#f8efdb;
}
.stApp, [data-testid="stAppViewContainer"]{background:var(--ground);}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding:0.6rem 1.4rem 3rem!important;max-width:1620px;}
html, body, [class*="css"]{font-family:Archivo,"Segoe UI",system-ui,sans-serif;}

.v2rail{
  background:var(--rail);color:var(--rail-ink);
  padding:11px 20px;display:flex;align-items:center;gap:28px;
  flex-wrap:wrap;margin:0 0 14px;
}
.v2rail .bm{display:flex;align-items:baseline;gap:9px;}
.v2rail .bm b{font-size:16px;font-weight:700;letter-spacing:-0.01em;}
.v2rail .bm span{font-family:"JetBrains Mono",monospace;font-size:9.5px;
  color:var(--brand);letter-spacing:0.18em;text-transform:uppercase;}
.v2rail .st label{display:block;font-family:"JetBrains Mono",monospace;
  font-size:9px;letter-spacing:0.14em;text-transform:uppercase;color:var(--rail-dim);}
.v2rail .st b{font-family:"JetBrains Mono",monospace;font-size:14px;
  font-weight:500;font-variant-numeric:tabular-nums;}
.v2rail .st b.dn{color:#f08a78;} .v2rail .st b.up{color:#4ecf9a;}

.v2card{background:var(--panel);border:1px solid var(--line);margin-bottom:12px;}
.v2head{display:flex;justify-content:space-between;align-items:center;gap:10px;
  padding:10px 14px;border-bottom:1px solid var(--line);background:var(--panel-2);}
.v2head h2{margin:0;font-size:11px;font-weight:700;letter-spacing:0.14em;
  text-transform:uppercase;font-family:"JetBrains Mono",monospace;color:var(--ink);}
.v2head .hint{font-family:"JetBrains Mono",monospace;font-size:9.5px;
  color:var(--muted);letter-spacing:0.06em;}
.v2body{padding:12px 14px;}
/* ⚠️ Dar ekranda tablo kolonu tasip komsu panelin uzerine biniyordu.
   Genis icerik KENDI kutusunda kaysin, sayfa govdesi asla yatay
   kaymasin. */
.v2card{overflow:hidden;}
.v2body:has(table){overflow-x:auto;}
table.v2{min-width:330px;}
div[data-testid='column']{min-width:0;overflow:hidden;}

.v2mb{border:1px solid var(--line);border-left:3px solid var(--brand);
  background:var(--panel-2);padding:11px 13px;margin:0 0 12px;
  font-size:12.5px;color:var(--ink-2);line-height:1.55;}
.v2mb b{color:var(--ink);}

table.v2{width:100%;border-collapse:collapse;
  font-variant-numeric:tabular-nums;}
table.v2 th{font-family:"JetBrains Mono",monospace;font-size:9px;
  letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);
  font-weight:500;text-align:left;padding:0 8px 7px 0;
  border-bottom:1px solid var(--line-2);white-space:nowrap;}
table.v2 th.r,table.v2 td.r{text-align:right;padding-right:0;}
table.v2 td{padding:7px 8px 7px 0;border-bottom:1px solid var(--line);
  font-size:13px;color:var(--ink);}
table.v2 td.n{font-family:"JetBrains Mono",monospace;font-size:12.5px;}
table.v2 .rk{font-family:"JetBrains Mono",monospace;font-size:10px;
  color:var(--muted);width:18px;}
table.v2 .ag{font-weight:600;font-size:12.5px;}
table.v2 .sb{display:block;font-family:"JetBrains Mono",monospace;
  font-size:9.5px;color:var(--muted);}
/* AVANTAJ GORUNUR OLMALI. Negatifler cok, pozitifler az — o yuzden
   pozitif VURGULANIR (yesil cip), negatif sadece renklenir. Boylece
   goz tabloyu tararken "bakilacaklari" aninda bulur.
   Semantik renk (iyi/kotu) marka renginden (amber) AYRIDIR. */
.dp{color:var(--pos);font-family:"JetBrains Mono",monospace;font-weight:700;
  background:var(--pos-fill);padding:2px 7px;border-radius:2px;
  display:inline-block;white-space:nowrap;}
.dm{color:var(--neg);font-family:"JetBrains Mono",monospace;font-weight:500;}
.dp::before{content:"▲ ";font-size:8px;vertical-align:1px;}
.dm::before{content:"▼ ";font-size:8px;vertical-align:1px;opacity:.55;}
/* avantajli satir: ajan hucresinde ince yesil serit — tarama isareti */
table.v2 tr.adv td:first-child{box-shadow:inset 2px 0 0 var(--pos);}
table.v2 tr.adv .ag{color:var(--pos);}
/* buyuk okumalar */
.ro b.ps{color:var(--pos);} .ro b.ng{color:var(--neg);}
.ro.big b.ps{background:var(--pos-fill);padding:2px 10px;border-radius:3px;}
.gr{display:inline-block;font-family:"JetBrains Mono",monospace;font-size:9px;
  font-weight:700;letter-spacing:0.08em;padding:2px 6px;border-radius:2px;}
.g1{background:var(--pos-fill);color:var(--pos);}
.g2{background:var(--warn-fill);color:var(--warn);}
.g3{background:var(--neg-fill);color:var(--neg);}

.cc{display:inline-block;font-family:"JetBrains Mono",monospace;font-size:9px;
  font-weight:700;letter-spacing:0.06em;min-width:26px;text-align:center;
  padding:2px 4px;margin-right:7px;border:1px solid var(--line-2);
  border-radius:2px;color:var(--ink-2);background:var(--panel-2);}
.cc.no{color:var(--muted);border-style:dashed;opacity:.75;}

.dq{font-family:"JetBrains Mono",monospace;font-size:10.5px;line-height:1.6;
  color:var(--muted);background:var(--warn-fill);border:1px solid var(--line);
  border-left:3px solid var(--warn);padding:8px 11px;margin:0 0 10px;}
.dq b{color:var(--warn);}

.ro{display:flex;justify-content:space-between;align-items:baseline;
  padding:8px 0;border-bottom:1px solid var(--line);}
.ro span{font-family:"JetBrains Mono",monospace;font-size:9.5px;
  letter-spacing:0.1em;text-transform:uppercase;color:var(--muted);}
.ro b{font-family:"JetBrains Mono",monospace;font-size:18px;font-weight:500;
  font-variant-numeric:tabular-nums;color:var(--ink);}
.ro.big b{font-size:26px;letter-spacing:-0.02em;}
.ro b.ng{color:var(--neg);} .ro b.ps{color:var(--pos);}
.meter{height:5px;background:var(--line);margin:4px 0 12px;}
.meter i{display:block;height:100%;background:var(--neg);}
.vd{font-size:12.5px;line-height:1.55;padding:10px 12px;border:1px solid var(--line);
  background:var(--panel-2);color:var(--ink-2);}
.vd b{color:var(--ink);}

/* Streamlit onay kutusu — tahtada satır gibi görünsün.
   ⚠️ Streamlit'in kendi teması koyu olursa yazı rengi beyaz gelir ve
   beyaz zeminde GÖRÜNMEZ olur (emoji görünür, metin kaybolur — ilk
   koşuda tam bu oldu). Renk burada ZORLANIR, temaya bırakılmaz. */
[data-testid="stCheckbox"]{margin:0!important;}
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] label *,
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] div[data-testid="stMarkdownContainer"] p{
  font-size:12.5px!important;color:var(--ink)!important;
  margin:0!important;line-height:1.45!important;}
[data-testid="stCheckbox"] label:hover p{color:var(--brand)!important;}
div[data-testid="column"]{padding:0 4px;}
/* Streamlit'in kendi metinleri (widget etiketleri, markdown) koyu kalsın.
   ⚠️ GENIS SECICI KULLANMA: '.stApp div{color:...}' yazmak durum
   seridini de vurur ve koyu zemin uzerine koyu yazi uretir — ilk
   denemede tam bu oldu. Yalniz Streamlit'in KENDI ciktilarini hedefle,
   kendi bilesenlerimize (v2rail, v2card) dokunma. */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p,
.stApp > header ~ div [data-testid="stText"]{color:var(--ink);}
.v2rail, .v2rail *{color:var(--rail-ink);}
.v2rail .st label{color:var(--rail-dim);}
.v2rail .bm span{color:var(--brand);}
.v2rail .st b.dn{color:#f08a78;} .v2rail .st b.up{color:#4ecf9a;}
</style>
"""


def _pct(v: float) -> str:
    return f"{v*100:.1f}".replace(".", ",") + "%"


def _sgn(v: float) -> str:
    return ("+" if v >= 0 else "−") + f"{abs(v)*100:.1f}".replace(".", ",") + "p"


def _num(v: float, d: int = 2) -> str:
    return f"{v:.{d}f}".replace(".", ",")


@st.cache_data(ttl=120, show_spinner=False)
def load_opus() -> dict:
    """OPUS 5 defteri — GERÇEKTE oynananlar.

    Yol haritasının kapatılması gereken tek sorusu burada ölçülür:
    kâğıt ajanlar ucuz bölgede -%12,5 gösteriyor, ama sahada kazanç
    bildiriliyor. İkisi birden doğru olabilir — gerçekte oynananlar,
    kâğıt ajanların oynadıklarından farklı olabilir. FARK ÖLÇÜLMELİ.

    Ve asıl soru: KOMBİNE YAPMAK, ayakları TEK TEK oynamaktan iyi mi?
    Her çok-ayaklı kupon için karşı-olgusal hesaplanır: aynı ayaklar
    tek tek oynansaydı ne getirirdi? Marj analizine göre kombine
    pahalı olmalı; bu, tezin kendi verinle sınanması."""
    cs = _rows(
        "SELECT coupon_id cid, status st, combined_odds co, stake sk, "
        "COALESCE(pnl,0) pnl, reasoning rs FROM paper_coupons "
        "WHERE portfolio_id='OPUS5_V1'", sessiz=True)
    if not cs:
        return {"var": False}
    ids = [c["cid"] for c in cs]
    qs = ",".join("?" for _ in ids)
    legs = _rows(
        f"SELECT coupon_id cid, odds o, status st, market mk, pick pk, "
        f"home_team h, away_team a FROM paper_bets WHERE coupon_id IN ({qs})",
        tuple(ids), sessiz=True)
    by: dict = {}
    for l in legs:
        by.setdefault(l["cid"], []).append(l)

    dec = [c for c in cs if c["st"] in ("won", "lost")]
    kombo_r, tek_r, n_multi = [], [], 0
    for c in dec:
        L = by.get(c["cid"], [])
        if not L:
            continue
        co = float(c["co"] or 1)
        kombo_r.append((co - 1.0) if c["st"] == "won" else -1.0)
        # karşı-olgusal: aynı ayaklar tek tek, eşit paylı
        sing = [((float(l["o"]) - 1.0) if l["st"] == "won" else -1.0)
                for l in L if l["st"] in ("won", "lost")]
        tek_r.append(sum(sing) / len(sing) if sing else 0.0)
        if len(L) >= 2:
            n_multi += 1

    # ayak düzeyi: fiyata göre üstünlük (ajan tablosuyla aynı ölçü)
    fl = [l for l in legs if l["st"] in ("won", "lost") and float(l["o"] or 0) > 1.01]
    hit = (sum(1 for l in fl if l["st"] == "won") / len(fl)) if fl else 0.0
    exp = (sum(1.0 / float(l["o"]) for l in fl) / len(fl)) if fl else 0.0

    def _m(v):
        return (sum(v) / len(v)) if v else 0.0

    return {
        "var": True, "kupon": len(cs),
        "acik": sum(1 for c in cs if c["st"] == "open"),
        "karar": len(dec), "cok_ayakli": n_multi,
        "ayak": len(fl), "hit": hit, "exp": exp, "edge": hit - exp,
        "kombo": _m(kombo_r), "tek": _m(tek_r),
        "fark": _m(kombo_r) - _m(tek_r), "n_kars": len(kombo_r),
        "pnl": sum(float(c["pnl"] or 0) for c in dec),
    }


@st.cache_data(ttl=180, show_spinner=False)
def load_havuz() -> dict:
    """Tüm kâğıt ajanların ayak düzeyi ortalaması — OPUS 5 kıyas tabanı."""
    rows = _rows("SELECT odds o, status s FROM paper_bets "
                 "WHERE status IN ('won','lost') AND odds > 1.01 "
                 "AND portfolio_id <> 'OPUS5_V1'", sessiz=True)
    if not rows:
        return {"n": 0}
    n = len(rows)
    hit = sum(1 for r in rows if r["s"] == "won") / n
    exp = sum(1.0 / float(r["o"]) for r in rows) / n
    flat = sum(((float(r["o"]) - 1.0) if r["s"] == "won" else -1.0)
               for r in rows) / n
    return {"n": n, "hit": hit, "exp": exp, "edge": hit - exp, "flat": flat}


# ══════════════════════════════════════════════════════════════
# SAYFA
# ══════════════════════════════════════════════════════════════

def _rail() -> None:
    """Durum şeridi — iki sayfa da kullanır. Veri kaynağı burada
    YAZAR: yanlış kaynağı üretim sanmak, yanlış rakama güvenmektir."""

    r = load_rail()
    kcell = ("henüz yok" if r["k"] is None
             else f"{r['k']:+.3f}".replace(".", ","))
    kasa = f"{r['kasa']:,.0f}".replace(",", ".")
    kapali = f"{r['kapali']:,}".replace(",", ".")
    yerel = r["kaynak"].startswith("SQLite")
    st.markdown(f"""
    <div class="v2rail">
      <div class="bm"><b>BETAGENTS</b><span>Desk · v2</span></div>
      <div class="st"><label>Veri kaynağı</label>
        <b class="{'dn' if yerel else ''}">{r['kaynak']}</b></div>
      <div class="st"><label>Toplam kasa</label><b>{kasa} ₺</b></div>
      <div class="st"><label>Portföy</label><b>{r['portfoy']}</b></div>
      <div class="st"><label>Açık pozisyon</label><b>{r['acik']}</b></div>
      <div class="st"><label>Kapanmış bahis</label><b>{kapali}</b></div>
      <div class="st"><label>Beceri katsayısı k</label>
        <b class="{'up' if r['k_gecti'] else 'dn'}">{kcell}</b></div>
    </div>""", unsafe_allow_html=True)
    if yerel:
        st.markdown(
            "<div class='dq' style='margin:0 0 12px;'><b>YEREL SQLITE</b> — "
            "üretim verisi değil. Canlı rakamlar için <code>DATABASE_URL</code> "
            "ortam değişkeni gerekiyor. Aşağıdaki her sayı bu kaynaktan.</div>",
            unsafe_allow_html=True)


def page_desk() -> None:
    left, mid, right = st.columns([1.08, 1.55, 1.0], gap="small")

    # ── SOL: ajan güveni ──────────────────────────────────────
    with left:
        ags = load_agents()
        by_hit = sorted(ags, key=lambda z: -z["hit"])
        swap = ""
        for a in ags:
            i_hit = by_hit.index(a) + 1
            i_edge = ags.index(a) + 1
            if abs(i_hit - i_edge) >= 5:
                swap = (f"<b>{a['ad']}</b> isabette {i_hit}. sırada, "
                        f"üstünlükte {i_edge}. sırada.")
                break
        body = []
        for i, a in enumerate(ags, 1):
            if a["perfect"]:
                g, txt = "g2", "ÖLÇÜLEMEZ"
            elif a["t"] is None:
                g, txt = "g2", "GÜRÜLTÜ"
            elif a["t"] <= -1.96:
                g, txt = "g3", "KÖTÜ"
            elif a["t"] >= 1.96:
                g, txt = "g1", "İYİ"
            else:
                g, txt = "g2", "GÜRÜLTÜ"
            # 0,5 puandan kucuk fark isaretlenmez — +0,0p yesil
            # gostermek, olcum gurultusunu avantaj gibi sunmaktir.
            adv = " class='adv'" if a["edge"] >= 0.005 else ""
            body.append(
                f"<tr{adv}><td class='rk'>{i}</td>"
                f"<td><span class='ag'>{a['em']} {a['ad']}</span>"
                f"<span class='sb'>n={a['n']} · oran {_num(a['odds'])}</span></td>"
                f"<td class='r n'>{_pct(a['hit'])}</td>"
                f"<td class='r n'>{_pct(a['exp'])}</td>"
                f"<td class='r'><span class='{'dp' if a['edge']>=0.005 else 'dm'}'>"
                f"{_sgn(a['edge'])}</span></td>"
                f"<td class='r'><span class='gr {g}'>{txt}</span></td></tr>")
        st.markdown(f"""
        <div class="v2card">
          <div class="v2head"><h2>Ajan Güveni</h2>
            <div class="hint">fiyata göre üstünlük</div></div>
          <div class="v2body">
            <div class="v2mb"><b>İsabet oranı yanıltır.</b> %75 isabet, oran
              1,24'te <b>kötüdür</b> — fiyat zaten %80,6 bekliyordu. %59 isabet,
              oran 1,84'te <b>iyidir</b>. Doğru ölçü isabet değil,
              <b>fiyatın beklediğinden ne kadar fazlası</b>.
              {(" " + swap) if swap else ""}</div>
            <table class="v2"><thead><tr><th></th><th>Ajan</th>
              <th class="r">İsabet</th><th class="r">Fiyat bekler</th>
              <th class="r">Fark</th><th class="r">Hüküm</th></tr></thead>
              <tbody>{''.join(body)}</tbody></table>
          </div></div>""", unsafe_allow_html=True)

    # ── ORTA: tahta ───────────────────────────────────────────
    board = load_board()
    if "v2_sel" not in st.session_state:
        st.session_state["v2_sel"] = []
    with mid:
        unknown = sum(1 for b in board if b["lg"] == "ALL")
        st.markdown(f"""
        <div class="v2card"><div class="v2head"><h2>Bugünün Tahtası</h2>
          <div class="hint">işaretle → kupona ekle</div></div>
          <div class="v2body" style="padding-bottom:2px;">
          <div class="dq"><b>{unknown}/{len(board)}</b> maçta lig kodlanmamış —
            veritabanında son 7 günün %79'u böyle. Ülke rozeti yerine
            <b>—</b> gösteriliyor; uydurulmuyor.</div>
          </div></div>""", unsafe_allow_html=True)
        sel = []
        for b in board[:22]:
            c1, c2 = st.columns([5.2, 1], gap="small")
            with c1:
                lbl = (f"{b['h']} — {b['a']}  ·  {b['em']} {b['ad']}"
                       f"  ·  {b['mk']} {b['pk']}  ·  {b['ko']}")
                on = st.checkbox(lbl, key=f"v2_{b['id']}")
            with c2:
                st.markdown(
                    f"<div style='text-align:right;font-family:\"JetBrains Mono\",monospace;"
                    f"font-size:16px;color:var(--ink);padding-top:2px;'>"
                    f"<span class='cc{' no' if b['lg']=='ALL' else ''}'>{b['code']}</span>"
                    f"{_num(b['o'])}</div>", unsafe_allow_html=True)
            if on:
                sel.append(b)

    # ── SAĞ: kupon tezgahı ────────────────────────────────────
    with right:
        n = len(sel)
        if n:
            O = 1.0
            p = 1.0
            for b in sel:
                O *= b["o"]
                p *= (1.0 / b["o"]) / b["m"]
            ev = p * O - 1.0
            same = len({(b["h"], b["a"]) for b in sel}) < n
            legs = "".join(
                f"<div style='display:flex;justify-content:space-between;"
                f"font-size:12px;padding:6px 8px;background:var(--panel-2);"
                f"border:1px solid var(--line);margin-bottom:6px;'>"
                f"<span>{b['h'][:16]} · <b>{b['pk']}</b></span>"
                f"<span style='font-family:\"JetBrains Mono\",monospace;'>"
                f"{_num(b['o'])}</span></div>" for b in sel)
            vd = (f"<b>{n} ayak · {_pct(p)} tutma şansı.</b> Hiçbir şeyde "
                  f"yanılmadan önce <b>{_num(abs(ev)*100,1)}%</b> geride "
                  f"başlıyorsun — bu, ayakların marjlarının çarpımı.")
            if same:
                vd += (" <b>Uyarı:</b> aynı maçtan birden fazla ayak var; "
                       "bunlar bağımsız değil, gerçek olasılık gösterilenden farklı.")
            if n >= 3:
                vd += " Üç ayakta maliyet, ölçülen en pahalı bölgeyi (−%22) geçiyor."
            elif n == 1 and ev > -0.13:
                vd += " Tek ayak, ölçülen en ucuz bölgede (−%9,8 marj tabanı)."
            ro = (f"<div class='ro'><span>Ayak</span><b>{n}</b></div>"
                  f"<div class='ro'><span>Toplam oran</span><b>{_num(O)}</b></div>"
                  f"<div class='ro'><span>Gerçek olasılık</span><b>{_pct(p)}</b></div>"
                  f"<div class='ro big'><span>Beklenen getiri</span>"
                  f"<b class='{'ps' if ev>=0 else 'ng'}'>"
                  f"{'+' if ev>=0 else '−'}{_num(abs(ev)*100,1)}%</b></div>")
            meter = f"<div class='meter'><i style='width:{min(100,abs(ev)*220):.0f}%'></i></div>"
        else:
            legs = ("<div style='font-family:\"JetBrains Mono\",monospace;"
                    "font-size:11px;color:var(--muted);text-align:center;"
                    "padding:10px 0;border:1px dashed var(--line-2);'>"
                    "kupon boş</div>")
            ro = ("<div class='ro'><span>Ayak</span><b>0</b></div>"
                  "<div class='ro'><span>Toplam oran</span><b>—</b></div>"
                  "<div class='ro'><span>Gerçek olasılık</span><b>—</b></div>"
                  "<div class='ro big'><span>Beklenen getiri</span><b>—</b></div>")
            meter = "<div class='meter'><i style='width:0%'></i></div>"
            vd = ("Bir seçim işaretle. Her ayak kendi marjını taşır ve "
                  "<b>marjlar çarpılır</b> — kupon uzadıkça maliyet katlanır.")
        st.markdown(f"""
        <div class="v2card"><div class="v2head"><h2>Kupon Tezgahı</h2>
          <div class="hint">marj canlı hesaplanır</div></div>
          <div class="v2body">{legs}{ro}{meter}
          <div class="vd">{vd}</div></div></div>""", unsafe_allow_html=True)

    st.markdown(
        "<div style='font-family:\"JetBrains Mono\",monospace;font-size:10px;"
        "color:var(--muted);padding:14px 2px;letter-spacing:0.04em;'>"
        "Marj katsayıları ölçüldü (31.08.2026): 1X2 %17,6 · A/Ü %17,4 · "
        "KG %16,4 · kombo %19,5–20,4 · Kâğıt ticaret, kişisel araştırma"
        "</div>", unsafe_allow_html=True)


def page_opus() -> None:
    """🧑‍💻 OPUS 5 — gerçekte oynananların defteri."""
    o = load_opus()
    h = load_havuz()
    left, right = st.columns([1.15, 1.0], gap="small")

    with left:
        if not o.get("var"):
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>OPUS 5 Defteri</h2>"
                "<div class='hint'>gerçekte oynananlar</div></div>"
                "<div class='v2body'><div class='dq'>Defter boş. Sağdan gerçekte "
                "oynadığın kuponu kaydet — kâğıt ile saha arasındaki fark ancak "
                "böyle ölçülebilir.</div></div></div>", unsafe_allow_html=True)
        else:
            fark = o["edge"] - h["edge"] if h.get("n") else 0.0
            if fark > 0.02:
                yorum = ("<b>Saha kâğıdı geçiyor.</b> Aradaki farkı yaratan şey "
                         "modelin göremediği bir bilgidir — onu bulmak yol "
                         "haritasının dört fazından da değerli.")
            elif abs(fark) <= 0.02:
                yorum = ("<b>Saha ile kâğıt aynı yerde.</b> Gerçek oyun, "
                         "ajanların ölçülen performansından ayrışmıyor.")
            else:
                yorum = ("<b>Kâğıt sahayı geçiyor.</b> Manuel seçim, ajanların "
                         "ham çıktısından daha kötü sonuç veriyor.")
            hn = "{:,}".format(h.get("n", 0)).replace(",", ".")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>OPUS 5 Defteri</h2>"
                "<div class='hint'>gerçekte oynananlar</div></div>"
                "<div class='v2body'>"
                "<table class='v2'><thead><tr><th></th>"
                "<th class='r'>Ayak</th><th class='r'>İsabet</th>"
                "<th class='r'>Fiyat bekler</th><th class='r'>Fark</th>"
                "</tr></thead><tbody>"
                "<tr" + (" class='adv'" if o["edge"] > h.get("edge", 0) else "") +
                "><td><span class='ag'>🧑‍💻 OPUS 5 · sen</span>"
                "<span class='sb'>" + str(o["kupon"]) + " kupon · " +
                str(o["acik"]) + " açık</span></td>"
                "<td class='r n'>" + str(o["ayak"]) + "</td>"
                "<td class='r n'>" + _pct(o["hit"]) + "</td>"
                "<td class='r n'>" + _pct(o["exp"]) + "</td>"
                "<td class='r'><span class='" +
                ("dp" if o["edge"] >= 0 else "dm") + "'>" + _sgn(o["edge"]) +
                "</span></td></tr>"
                "<tr><td><span class='ag'>📊 Kâğıt ajanlar · havuz</span>"
                "<span class='sb'>kıyas tabanı</span></td>"
                "<td class='r n'>" + hn + "</td>"
                "<td class='r n'>" + _pct(h.get("hit", 0)) + "</td>"
                "<td class='r n'>" + _pct(h.get("exp", 0)) + "</td>"
                "<td class='r'><span class='" +
                ("dp" if h.get("edge", 0) >= 0 else "dm") + "'>" +
                _sgn(h.get("edge", 0)) + "</span></td></tr>"
                "</tbody></table>"
                "<div class='v2mb' style='margin-top:12px;'>" + yorum +
                " Sahanın üstünlüğü havuzdan <b>" + _sgn(fark) +
                "</b> farklı.</div></div></div>", unsafe_allow_html=True)

            if o["n_kars"] >= 3:
                k, t, d = o["kombo"], o["tek"], o["fark"]
                if d > 0:
                    hkm = "Kombine <b>daha iyi</b> — ama örneklem küçük."
                else:
                    hkm = ("Kombine <b>daha kötü</b>. Marj analizi bunu "
                           "öngörüyordu: her ayak kendi marjını taşır ve "
                           "marjlar çarpılır.")
                st.markdown(
                    "<div class='v2card'><div class='v2head'>"
                    "<h2>Kombine mi, Tek Tek mi</h2>"
                    "<div class='hint'>karşı-olgusal · " + str(o["n_kars"]) +
                    " kupon</div></div><div class='v2body'>"
                    "<div class='ro'><span>Kombine oynandı</span><b class='" +
                    ("ps" if k >= 0 else "ng") + "'>" +
                    ("+" if k >= 0 else "−") + _num(abs(k) * 100, 1) + "%</b></div>"
                    "<div class='ro'><span>Aynı ayaklar tek tek</span><b class='" +
                    ("ps" if t >= 0 else "ng") + "'>" +
                    ("+" if t >= 0 else "−") + _num(abs(t) * 100, 1) + "%</b></div>"
                    "<div class='ro big'><span>Kombinenin katkısı</span><b class='" +
                    ("ps" if d >= 0 else "ng") + "'>" +
                    ("+" if d >= 0 else "−") + _num(abs(d) * 100, 1) + "p</b></div>"
                    "<div class='vd' style='margin-top:10px;'>" + hkm +
                    " Bu, kombine alışkanlığının <b>kendi verinle</b> ölçülmüş "
                    "fiyatıdır — varsayımla değil.</div></div></div>",
                    unsafe_allow_html=True)
            else:
                st.markdown(
                    "<div class='v2card'><div class='v2head'>"
                    "<h2>Kombine mi, Tek Tek mi</h2>"
                    "<div class='hint'>bekliyor</div></div><div class='v2body'>"
                    "<div class='dq'>Karşı-olgusal için en az 3 sonuçlanmış "
                    "kupon gerekiyor — şu an " + str(o["n_kars"]) +
                    ". Kaydettikçe ölçülecek.</div></div></div>",
                    unsafe_allow_html=True)

    with right:
        board = load_board()
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Gerçekte Ne Oynadın</h2>"
            "<div class='hint'>işaretle → kaydet</div></div>"
            "<div class='v2body' style='padding-bottom:4px;'>"
            "<div class='v2mb'>iddaa arşivi siliyor. Buraya girdiğin her kupon "
            "kalıcı olur ve <b>kâğıt ile saha arasındaki farkı</b> ölçmeyi "
            "mümkün kılar.</div></div></div>", unsafe_allow_html=True)
        secili = []
        for b in board[:18]:
            lbl = b["h"] + " — " + b["a"] + "  ·  " + str(b["pk"]) + \
                  "  ·  " + _num(b["o"])
            if st.checkbox(lbl, key="op_" + b["id"]):
                secili.append(b)
        stake = st.number_input("Bahis (₺)", min_value=5.0, max_value=5000.0,
                                value=50.0, step=5.0, key="op_stake")
        if secili:
            O = 1.0
            for b in secili:
                O *= b["o"]
            doner = "{:,.0f}".format(stake * O).replace(",", ".")
            st.markdown(
                "<div class='vd' style='margin:8px 0;'><b>" + str(len(secili)) +
                " ayak · toplam oran " + _num(O) + "</b> · " +
                "{:.0f}".format(stake) + " ₺ yatırırsan tutarsa " + doner +
                " ₺ döner.</div>", unsafe_allow_html=True)
        if st.button("✓ Gerçekte oynadım — kaydet", type="primary",
                     use_container_width=True, disabled=not secili):
            try:
                import manual_book as mb
                res = mb.play_custom([b["id"] for b in secili],
                                     stake=float(stake))
            except Exception as e:
                res = {"ok": False, "msg": "Hata: %s: %s" % (type(e).__name__, e)}
            if res.get("ok"):
                st.success(res["msg"])
                for b in secili:
                    st.session_state["op_" + b["id"]] = False
                load_opus.clear()
                st.rerun()
            else:
                st.error(res.get("msg", "kaydedilemedi"))


PAGES = {"◧ Desk": page_desk, "🧑‍💻 OPUS 5": page_opus}


def main() -> None:
    st.markdown(V2_CSS, unsafe_allow_html=True)
    if "v2_page" not in st.session_state:
        st.session_state["v2_page"] = "◧ Desk"
    # ⚠️ AÇIK KEY ŞART: Streamlit widget kimliğini etiket + parametrelerden
    # türetir. `type` her yeniden çizimde primary<->secondary arasında
    # değiştiği için kimlik de değişiyor ve tıklama kayboluyordu — sayfa
    # hiç geçmiyordu. Sabit key kimliği çakılar.
    cols = st.columns([1, 1, 6])
    for i, (name, _fn) in enumerate(PAGES.items()):
        with cols[i]:
            if st.button(name, key=f"v2nav_{i}", use_container_width=True,
                         type=("primary" if st.session_state["v2_page"] == name
                               else "secondary")):
                st.session_state["v2_page"] = name
                st.rerun()
    _rail()
    PAGES[st.session_state["v2_page"]]()


if __name__ == "__main__":
    main()
