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

# ⚠️ "expanded": kenar cubugu masaustunde ACIK baslar. "auto" yanlis
# karar veriyordu — 1600px'te bile kapali aciliyor ve kullanici
# hamburger aramak zorunda kaliyordu. Mobil davranis (uzerine acilan
# cekmece) zaten standarttir ve CSS ile ele aliniyor.
try:
    st.set_page_config(page_title="BetAgents Desk", page_icon="◉",
                       layout="wide", initial_sidebar_state="expanded")
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


@st.cache_resource(show_spinner=False)
def _conn():
    """TEK paylasilan baglanti — rerun'lar arasinda yasar.

    NEDEN: Railway PG proxy'sinde baglanti KURMAK pahali (~1,5 sn),
    sorgunun kendisi ucuz. Eskiden her sorgu yeni baglanti aciyordu:
    Sistem sayfasi 10 baglanti ~ 15 sn soguk acilis demekti. Sayfa
    gecislerindeki SOLMA bundandi — Streamlit ekrani soldurup baglanti
    kurulmasini bekliyordu.

    Bayat baglanti riski var (proxy dusurebilir), o yuzden _rows hata
    alinca onbellegi temizleyip TAZE baglantiyla bir kez daha dener."""
    import db as _db
    return _db.connect()


def _rows(sql: str, params: tuple = (), sessiz: bool = False) -> list[dict]:
    """Paylasilan baglanti uzerinden sorgu + bayatlarsa 1 tazeleme.

    sessiz=True: tablo henuz yoksa bos liste don. Olcum defteri tablosu
    (measurement_runs) ilk kosudan once yoktur; bunun yuzunden tum sayfa
    cokmemeli — eksik bir panel, coken bir sayfadan iyidir."""
    last = None
    for deneme in (1, 2):
        try:
            return [dict(r) for r in _conn().execute(sql, params).fetchall()]
        except Exception as e:
            last = e
            msg = str(e).lower()
            yok = ("no such table" in msg or "does not exist" in msg
                   or "undefinedtable" in msg)
            # PG'de basarisiz ifade islemi ABORT eder — sonraki her sorgu
            # da patlar. Geri almadan devam etmek tum sayfayi cokertir.
            try:
                _conn().rollback()
            except Exception:
                _conn.clear()
            if sessiz and yok:
                return []
            if deneme == 1 and not yok:
                _conn.clear()          # bayat/kirik baglanti: taze ac
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
# Ajan monogramlari — emoji yerine borsa sembolu mantigi.
# Emoji finansal panelde laubali durur ve Windows'ta bir kismi
# render olmaz (bayraklar harf ciftine duser). Iki harf her yerde
# ayni gorunur, hizalanir ve takima gore renklenir.
MONO = {
    "TEMKINLI_V1": "TK", "AVCI_V1": "AV", "MEMUR_V1": "MM", "HOCA_V1": "HC",
    "SIMYACI_V1": "SM", "POPULER_V1": "PP", "ERKENKUS_V1": "EK",
    "CESUR_V1": "CS", "JOKER_V1": "JK", "KALECI_V1": "KL", "KONSEY_V1": "KN",
    "TERS_V1": "TR", "CARPAN_V1": "KM", "SIMETRI_V1": "SI", "KAVSAK_V1": "KV",
    "BANT_V1": "BN", "DEVRE_V1": "DV", "TRIVOX_V1": "TV", "EUVOX_V1": "EU",
    "OPUS5_V1": "O5", "KURUCU_V2": "KU", "PAPER_V1": "PA",
}
_KIRMIZI_PID = {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"}


def _rozet(pid: str) -> str:
    """Ajan monogramı — kırmızı takım sıcak, mavi takım nötr."""
    m = MONO.get(pid)
    if not m:
        m = str(pid or "?")[:2].upper()
    k = " kr" if pid in _KIRMIZI_PID else ""
    # Sondaki bosluk KASITLI: gorsel araligi margin verir ama metin
    # olarak bitisik okunuyordu ("EUEUVOX"). Ekran okuyucu icin ayrilmali.
    return "<i class='mono" + k + "'>" + m + "</i> "


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
            "pid": pid, "ad": pid.rsplit("_", 1)[0], "em": pid,
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
            "em": r["p"], "ad": str(r["p"]).rsplit("_", 1)[0],
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
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ══════════════════════════════════════════════════════════════
   ÖLÇEK — tek kaynak. Her boyut buradan türer.
   Önceki sürüm fazla sıkışıktı: gövde 13,5px, etiket 9,5px.
   Profesyonel panel gövdede 14-15px, etikette 11px kullanır;
   altına inince ekran "yoğun" değil "okunmaz" olur.
   ══════════════════════════════════════════════════════════════ */
:root{
  --s1:4px;  --s2:8px;  --s3:12px; --s4:16px; --s5:22px; --s6:32px;
  --t-etiket:11px;   /* sütun başlığı, rozet, üst etiket */
  --t-alt:12.5px;    /* satır altı bilgi */
  --t-govde:14px;    /* tablo hücresi */
  --t-metin:15px;    /* açıklama, düz yazı */
  --t-kart:13px;     /* kart başlığı */
  --t-sayfa:21px;    /* sayfa başlığı */
  --t-okuma:20px;    /* okuma rakamı */
  --t-dev:30px;      /* tek büyük rakam */
  --yan:252px;
  --kart-ic:18px 20px;
  --satir-y:14px;
  --r:3px;           /* köşe yarıçapı — panel işi, yuvarlak değil */

  --ground:#fbfcfd; --panel:#ffffff; --panel-2:#f4f7f9; --panel-3:#eef3f6;
  --rail:#0b1420; --rail-ink:#e8edf2; --rail-dim:#8496a8;
  --ink:#0a1220; --ink-2:#38485a; --muted:#6b7c8e;
  --line:#e8edf1; --line-2:#d2dbe3;
  --brand:#8f5d0d; --brand-fill:#f7edda;
  --pos:#0b6b49; --pos-fill:#e3f2ec;
  --neg:#a02c1f; --neg-fill:#fbe8e5;
  --warn:#7f5a10; --warn-fill:#f9f1dd;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --ground:#0a1017; --panel:#111a24; --panel-2:#16212d; --panel-3:#1b2734;
    --rail:#060c13; --rail-ink:#dbe4ed; --rail-dim:#71828f;
    --ink:#e8eff6; --ink-2:#b2c1d0; --muted:#7d8d9e;
    --line:#1f2c39; --line-2:#2c3c4c;
    --brand:#dda94b; --brand-fill:#251e11;
    --pos:#45c795; --pos-fill:#0e2820;
    --neg:#ea8071; --neg-fill:#2b1614;
    --warn:#dda94b; --warn-fill:#251e11;
  }
}
:root[data-theme="dark"]{
  --ground:#0a1017; --panel:#111a24; --panel-2:#16212d; --panel-3:#1b2734;
  --rail:#060c13; --rail-ink:#dbe4ed; --rail-dim:#71828f;
  --ink:#e8eff6; --ink-2:#b2c1d0; --muted:#7d8d9e;
  --line:#1f2c39; --line-2:#2c3c4c;
  --brand:#dda94b; --brand-fill:#251e11;
  --pos:#45c795; --pos-fill:#0e2820;
  --neg:#ea8071; --neg-fill:#2b1614;
  --warn:#dda94b; --warn-fill:#251e11;
}

.stApp,[data-testid="stAppViewContainer"]{background:var(--ground);}
[data-testid="stHeader"]{background:transparent;height:0;}
.block-container{padding:var(--s5) var(--s6) var(--s6)!important;max-width:1680px;}
html,body,[class*="css"]{font-family:Archivo,"Segoe UI",system-ui,sans-serif;}

/* ── SAYFA BAŞLIĞI ─────────────────────────────────────────
   Önceki sürümde koyu şerit sol panelin bilgisini TEKRAR
   ediyordu ve sayfa başlığı yoktu — nerede olduğunu sadece
   menüden anlıyordun. Şerit artık sayfaya ait: başlık solda,
   O SAYFANIN ölçüleri sağda.                                */
.v2ph{
  display:flex;align-items:flex-end;justify-content:space-between;
  gap:var(--s5);flex-wrap:wrap;
  padding:0 0 var(--s3);margin:0 0 var(--s5);
  border-bottom:1px solid var(--line-2);
}
.v2ph .sol h1{
  margin:0;font-size:var(--t-sayfa);font-weight:600;letter-spacing:-0.015em;
  color:var(--ink);line-height:1.2;}
.v2ph .sol p{
  margin:3px 0 0;font-size:var(--t-alt);color:var(--muted);max-width:62ch;}
.v2ph .sag{display:flex;gap:var(--s5);flex-wrap:wrap;}
.v2kpi{display:flex;flex-direction:column;gap:2px;}
.v2kpi span{font-family:"JetBrains Mono",monospace;font-size:10px;
  letter-spacing:0.14em;text-transform:uppercase;color:var(--muted);}
.v2kpi b{font-family:"JetBrains Mono",monospace;font-size:var(--t-okuma);
  font-weight:500;font-variant-numeric:tabular-nums;color:var(--ink);
  line-height:1.15;}
.v2kpi b.ps{color:var(--pos);} .v2kpi b.ng{color:var(--neg);}

/* ── KENAR ÇUBUĞU ──────────────────────────────────────── */
[data-testid="stSidebar"]{background:var(--rail);border-right:0;
  width:var(--yan)!important;min-width:var(--yan)!important;}
[data-testid="stSidebar"] [data-testid="stSidebarContent"]{
  padding:var(--s5) var(--s3) var(--s4);}
.v2brand{padding:0 var(--s2) var(--s5);}
.v2brand b{display:block;font-size:18px;font-weight:700;letter-spacing:-0.015em;
  line-height:1.1;}
.v2brand span{display:block;font-family:"JetBrains Mono",monospace;
  font-size:10px;letter-spacing:0.2em;text-transform:uppercase;margin-top:4px;}
.v2navlbl{font-family:"JetBrains Mono",monospace;font-size:10px;
  letter-spacing:0.16em;text-transform:uppercase;
  padding:var(--s4) var(--s2) var(--s2);}
[data-testid="stSidebar"] .stButton>button{
  width:100%;text-align:left;justify-content:flex-start;
  background:transparent;border:0;border-left:2px solid transparent;
  border-radius:0;padding:10px var(--s3);margin:0;min-height:42px;
  font-weight:500;transition:background .12s,border-color .12s;}
[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(255,255,255,.055);border-left-color:var(--rail-dim);}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:rgba(255,255,255,.09);border-left-color:var(--brand);}
.v2yan-alt{margin-top:var(--s5);padding:var(--s4) var(--s2) 0;
  border-top:1px solid rgba(255,255,255,.08);
  font-family:"JetBrains Mono",monospace;line-height:1.9;letter-spacing:0.04em;}

/* ⚠️ DÖRDÜNCÜ KEZ: [stMarkdownContainer] p{color} kuralı özgüllükte
   kenar çubuğunun önüne geçiyor. Renkler burada AÇIKÇA verilir. */
[data-testid="stSidebar"] *{color:var(--rail-ink);}
[data-testid="stSidebar"] .stButton>button p,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p{
  font-size:var(--t-metin)!important;margin:0!important;
  color:var(--rail-ink)!important;}
[data-testid="stSidebar"] .stButton>button[kind="primary"] p{
  color:#fff!important;font-weight:600!important;}
[data-testid="stSidebar"] .v2brand span{color:var(--brand)!important;
  font-size:10px!important;}
[data-testid="stSidebar"] .v2navlbl{color:var(--rail-dim)!important;
  font-size:10px!important;}
[data-testid="stSidebar"] .v2yan-alt,
[data-testid="stSidebar"] .v2yan-alt *{color:var(--rail-dim)!important;
  font-size:10.5px!important;}
[data-testid="stSidebar"] .v2yan-alt b{color:var(--rail-ink)!important;}
[data-testid="stSidebar"] .v2yan-alt b.uyari{color:#f08a78!important;}

/* ── KART ──────────────────────────────────────────────── */
.v2card{background:var(--panel);border:1px solid var(--line);
  border-radius:var(--r);margin-bottom:var(--s4);overflow:hidden;}
.v2head{display:flex;justify-content:space-between;align-items:baseline;
  gap:var(--s3);padding:var(--s3) 20px;border-bottom:1px solid var(--line);
  background:var(--panel-2);}
.v2head h2{margin:0;font-size:var(--t-kart);font-weight:600;
  letter-spacing:0.01em;color:var(--ink);text-transform:none;
  font-family:Archivo,sans-serif;}
.v2head .hint{font-family:"JetBrains Mono",monospace;font-size:10px;
  color:var(--muted);letter-spacing:0.08em;text-transform:uppercase;
  white-space:nowrap;}
.v2body{padding:var(--kart-ic);}
.v2body:has(table){overflow-x:auto;}

/* ── TABLO ZANAATI ─────────────────────────────────────── */
table.v2{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;
  min-width:340px;}
table.v2 th{
  font-family:"JetBrains Mono",monospace;font-size:var(--t-etiket);
  letter-spacing:0.09em;text-transform:uppercase;color:var(--muted);
  font-weight:500;text-align:left;white-space:nowrap;
  padding:0 var(--s4) 10px 0;border-bottom:1px solid var(--line-2);}
table.v2 th:last-child,table.v2 td:last-child{padding-right:0;}
table.v2 th.r,table.v2 td.r{text-align:right;}
table.v2 td{padding:var(--satir-y) var(--s4) var(--satir-y) 0;
  border-bottom:1px solid var(--line);font-size:var(--t-govde);
  color:var(--ink);vertical-align:middle;}
table.v2 tbody tr{transition:background .1s;}
table.v2 tbody tr:hover{background:var(--panel-2);}
table.v2 tbody tr:last-child td{border-bottom:0;}
table.v2 td.n{font-family:"JetBrains Mono",monospace;font-size:13.5px;}
table.v2 .rk{font-family:"JetBrains Mono",monospace;font-size:11px;
  color:var(--muted);width:22px;padding-right:var(--s2);}
table.v2 .ag{font-weight:600;font-size:var(--t-govde);letter-spacing:-0.005em;
  display:block;}
table.v2 .sb{display:block;font-family:"JetBrains Mono",monospace;
  font-size:var(--t-alt);color:var(--muted);margin-top:3px;
  letter-spacing:0.02em;white-space:nowrap;}
/* ilk sutun icerigi kirilmasin, sayisal sutunlar daralsin */
table.v2 td:first-child,table.v2 th:first-child{padding-right:var(--s5);}
table.v2 td.n,table.v2 th.r{white-space:nowrap;}

/* ── SEMANTİK ──────────────────────────────────────────── */
.dp{color:var(--pos);font-family:"JetBrains Mono",monospace;font-weight:600;
  background:var(--pos-fill);padding:3px 9px;border-radius:var(--r);
  display:inline-block;white-space:nowrap;font-size:13px;}
.dm{color:var(--neg);font-family:"JetBrains Mono",monospace;font-weight:500;
  white-space:nowrap;font-size:13px;}
.dp::before{content:"▲ ";font-size:8px;vertical-align:1.5px;}
.dm::before{content:"▼ ";font-size:8px;vertical-align:1.5px;opacity:.5;}
table.v2 tr.adv td:first-child{box-shadow:inset 2px 0 0 var(--pos);}
table.v2 tr.adv .ag{color:var(--pos);}
.gr{display:inline-block;font-family:"JetBrains Mono",monospace;
  font-size:10px;font-weight:600;letter-spacing:0.07em;
  padding:4px 8px;border-radius:var(--r);white-space:nowrap;}
.g1{background:var(--pos-fill);color:var(--pos);}
.g2{background:var(--warn-fill);color:var(--warn);}
.g3{background:var(--neg-fill);color:var(--neg);}
.cc{display:inline-block;font-family:"JetBrains Mono",monospace;font-size:10px;
  font-weight:600;letter-spacing:0.05em;min-width:30px;text-align:center;
  padding:3px 5px;margin-right:9px;border:1px solid var(--line-2);
  border-radius:var(--r);color:var(--ink-2);background:var(--panel-2);}
.cc.no{color:var(--muted);border-style:dashed;opacity:.7;}

/* ── AÇIKLAMA KUTULARI ─────────────────────────────────── */
.v2mb{border:1px solid var(--line);border-left:3px solid var(--brand);
  background:var(--panel-2);padding:var(--s3) var(--s4);margin:0 0 var(--s4);
  font-size:var(--t-metin);color:var(--ink-2);line-height:1.6;
  border-radius:0 var(--r) var(--r) 0;}
.v2mb b{color:var(--ink);font-weight:600;}
.dq{font-family:"JetBrains Mono",monospace;font-size:11.5px;line-height:1.75;
  color:var(--muted);background:var(--warn-fill);border:1px solid var(--line);
  border-left:3px solid var(--warn);padding:10px var(--s3);margin:0 0 var(--s3);
  border-radius:0 var(--r) var(--r) 0;}
.dq b{color:var(--warn);}
.vd{font-size:var(--t-metin);line-height:1.6;padding:var(--s3) var(--s4);
  border:1px solid var(--line);background:var(--panel-2);color:var(--ink-2);
  border-radius:var(--r);}
.vd b{color:var(--ink);font-weight:600;}

/* ── OKUMA SATIRLARI ───────────────────────────────────── */
.ro{display:flex;justify-content:space-between;align-items:baseline;
  padding:11px 0;border-bottom:1px solid var(--line);}
.ro:last-of-type{border-bottom:0;}
.ro span{font-family:"JetBrains Mono",monospace;font-size:10.5px;
  letter-spacing:0.11em;text-transform:uppercase;color:var(--muted);}
.ro b{font-family:"JetBrains Mono",monospace;font-size:var(--t-okuma);
  font-weight:500;font-variant-numeric:tabular-nums;color:var(--ink);}
.ro.big b{font-size:var(--t-dev);letter-spacing:-0.02em;}
.ro b.ps{color:var(--pos);} .ro b.ng{color:var(--neg);}
.ro.big b.ps{background:var(--pos-fill);padding:3px 11px;border-radius:var(--r);}
.meter{height:5px;background:var(--line);margin:var(--s1) 0 var(--s3);
  border-radius:99px;overflow:hidden;}
.meter i{display:block;height:100%;background:var(--neg);}

/* ── TAHTA (seçim satırları) ───────────────────────────── */
.pick{display:grid;grid-template-columns:1fr auto;gap:4px var(--s3);
  padding:11px var(--s3);border:1px solid var(--line);border-radius:var(--r);
  background:var(--panel);margin-bottom:var(--s2);cursor:pointer;
  transition:border-color .12s,background .12s;align-items:center;}
.pick:hover{border-color:var(--brand);background:var(--panel-2);}
.pick.on{border-color:var(--brand);background:var(--brand-fill);}
.pick .match{font-weight:600;font-size:var(--t-govde);}
.pick .meta{font-family:"JetBrains Mono",monospace;font-size:var(--t-alt);
  color:var(--muted);margin-top:2px;}
.pick .odds{font-family:"JetBrains Mono",monospace;font-size:18px;
  font-weight:500;text-align:right;line-height:1.1;}
.pick .odds em{display:block;font-style:normal;font-size:9px;
  color:var(--muted);letter-spacing:0.1em;margin-top:2px;}
.fl{display:none;}
/* ── AJAN MONOGRAMI ────────────────────────────────────
   Emoji yerine iki harf: hizalanir, her yerde ayni gorunur,
   takim rengini tasir. Borsa sembolu gibi okunur.          */
.mono{
  font-style:normal;font-family:"JetBrains Mono",monospace;
  font-size:10px;font-weight:700;letter-spacing:0.04em;
  display:inline-flex;align-items:center;justify-content:center;
  width:24px;height:20px;margin-right:3px;vertical-align:-4px;
  border:1px solid var(--line-2);border-radius:var(--r);
  color:var(--ink-2);background:var(--panel-2);flex:0 0 auto;}
.mono.kr{color:var(--neg);border-color:var(--neg);
  background:var(--neg-fill);}
table.v2 tr.adv .mono{border-color:var(--pos);color:var(--pos);
  background:var(--pos-fill);}
.em{display:none;}

/* ── Streamlit bileşenleri ─────────────────────────────── */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p{color:var(--ink);}
[data-testid="stCheckbox"]{margin:0!important;}
[data-testid="stCheckbox"] label,
[data-testid="stCheckbox"] label p,
[data-testid="stCheckbox"] div[data-testid="stMarkdownContainer"] p{
  font-size:var(--t-govde)!important;color:var(--ink)!important;
  margin:0!important;line-height:1.5!important;}
[data-testid="stCheckbox"] label:hover p{color:var(--brand)!important;}
div[data-testid="column"]{padding:0 var(--s2);min-width:0;}
div[data-testid="column"]:first-child{padding-left:0;}
div[data-testid="column"]:last-child{padding-right:0;}

/* ══════════════════════════════════════════════════════════
   ÜRÜN DENETİMİ — buton sistemi, gezinme, form kontrolleri
   Streamlit'in varsayılan bileşenleri "bitmemiş" hissi verir:
   yuvarlak köşeler, mavi vurgu, gri kenarlık. Hepsi tasarım
   sistemine çekildi.
   ══════════════════════════════════════════════════════════ */

/* ── KENAR ÇUBUĞU: gerçek gezinme ─────────────────────── */
[data-testid="stSidebar"]{box-shadow:1px 0 0 rgba(255,255,255,.05);}
.v2brand{display:flex;align-items:center;gap:10px;
  padding:0 var(--s2) var(--s5);}
.v2brand .mark{
  width:30px;height:30px;flex:0 0 auto;border-radius:var(--r);
  background:var(--brand);color:#0b1420;
  display:flex;align-items:center;justify-content:center;
  font-family:"JetBrains Mono",monospace;font-size:13px;font-weight:700;
  letter-spacing:-0.03em;}
.v2brand .yazi b{display:block;font-size:16px;font-weight:700;
  letter-spacing:-0.015em;line-height:1.15;}
.v2brand .yazi span{display:block;font-family:"JetBrains Mono",monospace;
  font-size:9.5px;letter-spacing:0.2em;text-transform:uppercase;margin-top:2px;}

[data-testid="stSidebar"] .stButton{margin:0!important;}
[data-testid="stSidebar"] .stButton>button{
  position:relative;width:100%;text-align:left;justify-content:flex-start;
  background:transparent;border:0;border-radius:var(--r);
  padding:0 var(--s3) 0 34px;margin:1px 0;min-height:40px;height:40px;
  font-weight:500;letter-spacing:-0.005em;
  transition:background .13s ease,color .13s ease;}
/* nokta göstergesi — aktif olanda amber, diğerlerinde soluk */
[data-testid="stSidebar"] .stButton>button::before{
  content:"";position:absolute;left:14px;top:50%;transform:translateY(-50%);
  width:5px;height:5px;border-radius:50%;background:var(--rail-dim);
  opacity:.45;transition:background .13s,opacity .13s,box-shadow .13s;}
[data-testid="stSidebar"] .stButton>button:hover{
  background:rgba(255,255,255,.06);}
[data-testid="stSidebar"] .stButton>button:hover::before{opacity:.9;}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{
  background:rgba(255,255,255,.10);}
[data-testid="stSidebar"] .stButton>button[kind="primary"]::before{
  background:var(--brand);opacity:1;
  box-shadow:0 0 0 3px color-mix(in srgb,var(--brand) 22%,transparent);}
[data-testid="stSidebar"] .stButton>button:focus-visible{
  outline:2px solid var(--brand);outline-offset:-2px;}

/* ── ANA ALAN BUTONLARI: hayalet + birincil ───────────── */
/* ⚠️ [data-testid="stAppViewContainer"] kenar cubugunu DA kapsiyor —
   ilk denemede aktif menu ogesi tamamen amber oldu. Kenar cubugu
   acikca haric tutulur. */
[data-testid="stAppViewContainer"] .stButton>button:not([data-testid="stSidebar"] *),
section[data-testid="stMain"] .stButton>button{
  border-radius:var(--r);border:1px solid var(--line-2);
  background:var(--panel);color:var(--ink);
  font-size:var(--t-govde);font-weight:500;min-height:38px;
  padding:0 var(--s4);letter-spacing:-0.005em;
  transition:border-color .13s,background .13s,color .13s;}
section[data-testid="stMain"] .stButton>button:hover{
  border-color:var(--brand);color:var(--brand);background:var(--panel-2);}
section[data-testid="stMain"] .stButton>button:focus-visible{
  outline:2px solid var(--brand);outline-offset:2px;}
section[data-testid="stMain"] .stButton>button[kind="primary"]{
  background:var(--brand);border-color:var(--brand);color:#fff;font-weight:600;}
section[data-testid="stMain"] .stButton>button[kind="primary"]:hover{
  filter:brightness(1.08);color:#fff;}

/* ── ALT GEZİNME ──────────────────────────────────────── */
.v2gez{display:flex;align-items:center;justify-content:space-between;
  gap:var(--s4);padding-top:var(--s4);margin-top:var(--s5);
  border-top:1px solid var(--line);}
.v2gez-orta{font-family:"JetBrains Mono",monospace;font-size:10.5px;
  letter-spacing:0.12em;text-transform:uppercase;color:var(--muted);
  text-align:center;}

/* ── FORM KONTROLLERİ ─────────────────────────────────── */
[data-testid="stSelectbox"] div[data-baseweb="select"]>div,
[data-testid="stMultiSelect"] div[data-baseweb="select"]>div{
  background:var(--panel)!important;border-color:var(--line-2)!important;
  border-radius:var(--r)!important;min-height:38px;font-size:var(--t-govde);}
[data-testid="stSelectbox"] div[data-baseweb="select"]>div:hover,
[data-testid="stMultiSelect"] div[data-baseweb="select"]>div:hover{
  border-color:var(--brand)!important;}
/* ⚠️ SADECE form etiketleri — onay kutusu etiketleri de stWidgetLabel'dir
   ve ilk denemede TAHTADAKI MAC ADLARI buyuk harfe dondu. Onay kutusu
   haric tutulur. */
[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] p,
[data-testid="stMultiSelect"] [data-testid="stWidgetLabel"] p,
[data-testid="stNumberInput"] [data-testid="stWidgetLabel"] p{
  font-size:var(--t-alt)!important;color:var(--muted)!important;
  font-family:"JetBrains Mono",monospace;letter-spacing:0.09em;
  text-transform:uppercase;margin-bottom:5px!important;}
[data-testid="stCheckbox"] [data-testid="stWidgetLabel"] p{
  text-transform:none!important;letter-spacing:normal!important;
  font-family:Archivo,sans-serif!important;}
[data-testid="stNumberInput"] input{background:var(--panel)!important;
  border-radius:var(--r)!important;font-family:"JetBrains Mono",monospace;}
div[data-baseweb="tag"]{background:var(--brand-fill)!important;
  color:var(--brand)!important;border-radius:var(--r)!important;
  font-family:"JetBrains Mono",monospace!important;font-size:11px!important;}

/* ── MOBİL: çekmece davranışı ─────────────────────────── */
@media (max-width:768px){
  [data-testid="stSidebar"]{box-shadow:0 0 0 100vmax rgba(0,0,0,.45);}
}

/* ── ALT SEKMELER ──────────────────────────────────────
   Bir sayfada dört ayri soru varsa dordunu ust uste yigmak
   "kompakt" degil OKUNMAZ yapar. Sekme, sayfayi bolmeden
   odagi bolerek cozer.                                    */
.v2sek{display:flex;gap:2px;border-bottom:1px solid var(--line-2);
  margin:0 0 var(--s4);overflow-x:auto;}
[data-testid="stSidebar"] .v2grup{
  font-family:"JetBrains Mono",monospace;font-size:9.5px;
  letter-spacing:0.18em;text-transform:uppercase;
  padding:var(--s4) var(--s3) 6px;opacity:.65;}
[data-testid="stSidebar"] .v2grup:first-of-type{padding-top:var(--s2);}
/* alt oge — ana ogenin altinda, girintili */
[data-testid="stSidebar"] .stButton>button.v2alt{padding-left:46px;}

/* ── SEKME BUTONLARI (ana alan) ───────────────────────── */
section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(.v2sekme-isaret)
  .stButton>button{
  border:0;border-bottom:2px solid transparent;border-radius:0;
  background:transparent;color:var(--muted);font-weight:500;
  min-height:36px;padding:0 var(--s3);}
section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(.v2sekme-isaret)
  .stButton>button:hover{color:var(--ink);background:transparent;
  border-bottom-color:var(--line-2);}
section[data-testid="stMain"] div[data-testid="stHorizontalBlock"]:has(.v2sekme-isaret)
  .stButton>button[kind="primary"]{
  background:transparent;color:var(--ink);font-weight:600;
  border-bottom-color:var(--brand);}

/* ── SUZGEC ALANI: arama kutusu sanilmasin ────────────── */
.v2suz{display:flex;align-items:center;gap:var(--s2);
  font-family:"JetBrains Mono",monospace;font-size:10px;
  letter-spacing:0.14em;text-transform:uppercase;color:var(--muted);
  margin:0 0 var(--s2);}
.v2suz::before{content:"";width:11px;height:11px;flex:0 0 auto;
  border:1.5px solid var(--muted);
  clip-path:polygon(0 0,100% 0,62% 45%,62% 100%,38% 82%,38% 45%);}

/* ── SEPET ────────────────────────────────────────────── */
.v2sepet-satir{display:flex;align-items:center;justify-content:space-between;
  gap:var(--s3);padding:10px var(--s3);border:1px solid var(--line);
  border-radius:var(--r);background:var(--panel-2);margin-bottom:6px;}
.v2sepet-satir .ad{font-size:var(--t-govde);font-weight:500;}
.v2sepet-satir .alt{font-family:"JetBrains Mono",monospace;
  font-size:var(--t-alt);color:var(--muted);margin-top:2px;}
.v2bos{border:1px dashed var(--line-2);border-radius:var(--r);
  padding:var(--s5) var(--s3);text-align:center;color:var(--muted);
  font-family:"JetBrains Mono",monospace;font-size:11.5px;line-height:1.8;}

/* ── MOBİL: küçültme değil önceliklendirme ─────────────── */
@media (max-width:900px){
  :root{--yan:236px;--s6:20px;}
  .block-container{padding:var(--s4) var(--s4) var(--s6)!important;}
  .v2ph{flex-direction:column;align-items:flex-start;gap:var(--s3);}
  .v2ph .sag{gap:var(--s4);}
}
@media (max-width:640px){
  :root{--kart-ic:14px 15px;--satir-y:15px;--t-sayfa:19px;}
  table.v2 th.opt,table.v2 td.opt{display:none;}
  .v2kpi b{font-size:17px;}
  .ro.big b{font-size:25px;}
  .pick,[data-testid="stCheckbox"] label{min-height:44px;}
  .v2card{margin-bottom:var(--s3);}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;}}
</style>
"""



def _sekmeler(anahtar: str, adlar: list) -> str:
    """Sayfa içi sekme çubuğu — bir sayfada dört ayrı soru varsa
    dördünü üst üste yığmak 'kompakt' değil OKUNMAZ yapar."""
    st.markdown("<span class='v2sekme-isaret'></span>",
                unsafe_allow_html=True)
    k = "v2sek_" + anahtar
    if k not in st.session_state:
        st.session_state[k] = adlar[0]
    kol = st.columns(len(adlar) + 2, gap="small")
    for i, ad in enumerate(adlar):
        with kol[i]:
            if st.button(ad, key=k + "_" + str(i), use_container_width=True,
                         type=("primary" if st.session_state[k] == ad
                               else "secondary")):
                st.session_state[k] = ad
                st.rerun()
    st.markdown("<div style='height:1px;background:var(--line-2);"
                "margin:-6px 0 var(--s4);'></div>", unsafe_allow_html=True)
    return st.session_state[k]


def _suzgec_basligi(metin: str) -> None:
    st.markdown("<div class='v2suz'>" + metin + "</div>",
                unsafe_allow_html=True)


def _sayfa_basligi(baslik: str, alt: str, kpi: list | None = None) -> None:
    """Sayfa başlığı + O SAYFAYA ait ölçüler.

    Genel durum şeridi kaldırıldı: sol panelin bilgisini tekrar ediyordu
    ve sayfa başlığı yoktu — kullanıcı nerede olduğunu sadece menüden
    anlıyordu. Şerit artık sayfaya ait."""
    k = ""
    for x in (kpi or []):
        cls = x.get("cls", "")
        k += ("<div class='v2kpi'><span>" + x["ad"] + "</span><b class='" +
              cls + "'>" + x["deger"] + "</b></div>")
    st.markdown(
        "<div class='v2ph'><div class='sol'><h1>" + baslik + "</h1>"
        "<p>" + alt + "</p></div>"
        "<div class='sag'>" + k + "</div></div>", unsafe_allow_html=True)



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


KIRMIZI = {"CARPAN_V1", "SIMETRI_V1", "KAVSAK_V1", "BANT_V1", "DEVRE_V1"}


@st.cache_data(ttl=180, show_spinner=False)
def load_lig() -> dict:
    """Dönem-kapsamlı ajan ligi — mavi ve kırmızı AYRI.

    ⚠️ Dönem (era) filtresi şart: Era-1 arşivlendi, Era-2 2026-08-23'te
    1.000 TL ile başladı. Era-1 sonuçlarını Era-2 karnesine karıştırmak,
    kapanmış bir hesabı açık gibi göstermektir.

    Sıralama İSABETE göre değil, FİYATA GÖRE ÜSTÜNLÜĞE göre — Desk ile
    aynı ölçü. İkisi farklı sıralama verdiği için tutarlılık şart."""
    rows = _rows(
        "SELECT pb.portfolio_id p, pb.odds o, pb.status s "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    pf = _rows("SELECT portfolio_id p, current_bankroll cb, initial_bankroll ib, "
               "era_no, benched, ihtar_count ih FROM paper_portfolio", sessiz=True)
    kasa = {x["p"]: x for x in pf}
    by: dict = {}
    for r in rows:
        by.setdefault(r["p"], []).append(r)

    def kur(pid, v):
        n = len(v)
        won = sum(1 for x in v if x["s"] == "won")
        hit = won / n if n else 0.0
        exp = (sum(1.0 / float(x["o"]) for x in v) / n) if n else 0.0
        ret = [((float(x["o"]) - 1.0) if x["s"] == "won" else -1.0) for x in v]
        skill = (sum(ret) / n) if n else 0.0
        var = (sum((x - skill) ** 2 for x in ret) / max(n - 1, 1)) if n > 1 else 0.0
        se = math.sqrt(var / n) if (var > 0 and n) else 0.0
        perfect = n > 0 and (won == 0 or won == n)
        k = kasa.get(pid, {})
        ib = float(k.get("ib") or 1000)
        cb = float(k.get("cb") or 0)
        return {"pid": pid, "ad": pid.rsplit("_", 1)[0],
                "em": pid, "n": n, "hit": hit, "exp": exp,
                "edge": hit - exp, "skill": skill,
                "t": (skill / se) if (se > 1e-9 and not perfect) else None,
                "perfect": perfect, "kasa": cb, "ilk": ib,
                "yuzde": (cb / ib * 100) if ib else 0.0,
                "era": k.get("era_no"), "benched": bool(k.get("benched")),
                "ihtar": int(k.get("ih") or 0),
                "odds": (sum(float(x["o"]) for x in v) / n) if n else 0.0}

    tum = [kur(p, v) for p, v in by.items()]
    # hic bahsi olmayan (ornegin susan kirmizi ajanlar) da listede dursun
    for p in kasa:
        if p not in by and p in KIRMIZI:
            tum.append(kur(p, []))
    mavi = [x for x in tum if x["pid"] not in KIRMIZI
            and x["pid"] not in ("PAPER_V1", "OPUS5_V1")]
    kirmizi = [x for x in tum if x["pid"] in KIRMIZI]
    mavi.sort(key=lambda z: -z["edge"])
    kirmizi.sort(key=lambda z: -z["edge"])
    return {"mavi": mavi, "kirmizi": kirmizi}


@st.cache_data(ttl=300, show_spinner=False)
def load_defter() -> list[dict]:
    """Ölçüm defteri — her bulgunun son hükmü + değişim geçmişi."""
    rows = _rows("SELECT ts, finding_id f, n, value v, passed g, detail d "
                 "FROM measurement_runs ORDER BY ts", sessiz=True)
    if not rows:
        return []
    by: dict = {}
    for r in rows:
        by.setdefault(r["f"], []).append(r)
    out = []
    for fid, v in by.items():
        son = v[-1]
        degisim = sum(1 for i in range(1, len(v))
                      if bool(v[i]["g"]) != bool(v[i - 1]["g"]))
        onceki = v[-2] if len(v) > 1 else None
        out.append({
            "id": fid, "ts": str(son["ts"])[:16], "n": son["n"],
            "v": float(son["v"] or 0), "gecti": bool(son["g"]),
            "detay": son["d"], "kosu": len(v), "degisim": degisim,
            "trend": (float(son["v"] or 0) - float(onceki["v"] or 0))
                     if onceki else None,
        })
    out.sort(key=lambda z: (not z["gecti"], z["id"]))
    return out


@st.cache_data(ttl=180, show_spinner=False)
def load_sistem() -> dict:
    """Sistem sağlığı — sessizlik meşru mu, arıza mı?

    Bu sayfanın tezi: bir ajanın oynamaması iki farklı şey olabilir ve
    ikisini karıştırmak haftalarca sürebilir. 'Meşru PAS' (aday yok) ile
    'TIKANIKLIK' (kod/veri kırık) ayrı ayrı işaretlenir. Bir kez fetch
    çöktüğünde tüm ajanlar masum sessizlik gibi görünmüştü — SİSTEM
    satırı tam bunun için var."""
    diag = _rows(
        "SELECT DISTINCT ON (pid) pid, ts, status, detail FROM agent_diag "
        "ORDER BY pid, ts DESC", sessiz=True)
    if not diag:                        # SQLite: DISTINCT ON yok
        diag = _rows(
            "SELECT d.pid, d.ts, d.status, d.detail FROM agent_diag d "
            "JOIN (SELECT pid p, MAX(ts) m FROM agent_diag GROUP BY pid) x "
            "ON x.p = d.pid AND x.m = d.ts", sessiz=True)
    sistem = next((d for d in diag if d["pid"] == "SISTEM"), None)
    ajan = [d for d in diag if d["pid"] != "SISTEM"]

    def sinif(st_):
        t = str(st_ or "")
        if "TIKANIKLIK" in t:
            return 0
        if "🟠" in t or "MONTAJ" in t or "KUYRUK" in t:
            return 1
        if "MEŞRU PAS" in t or "SESSİZ" in t:
            return 2
        return 3

    ajan.sort(key=lambda d: (sinif(d["status"]), d["pid"]))

    # veri doluluk — yol haritasının Faz 1 listesi
    tot = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1",
                sessiz=True)
    T = int(tot[0]["n"]) if tot else 0
    alanlar = []
    for kol, ad, neden in (
        ("external_id_af", "api-football kimliği",
         "keskin fiyat hattının önkoşulu"),
        ("home_score_ht", "ilk yarı skoru",
         "çıpaların ulaşamadığı tek boyut · HT_FT marjı %25,8"),
        ("closing_btts_yes", "KG kapanış fiyatı", "KG pazarı fiyatlaması"),
        ("home_xg", "xG", "hareket öngörüsü için girdi"),
        ("h2h_n", "karşılaşma geçmişi", "zenginleştirme"),
    ):
        r = _rows(f"SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1 "
                  f"AND {kol} IS NOT NULL", sessiz=True)
        n = int(r[0]["n"]) if r else 0
        alanlar.append({"kol": kol, "ad": ad, "neden": neden, "n": n,
                        "pay": (n / T) if T else 0.0})

    lig = _rows("SELECT COUNT(*) n FROM matches_v2 "
                "WHERE kickoff_utc > '2026-08-24' AND league_code = 'ALL'",
                sessiz=True)
    lig_tum = _rows("SELECT COUNT(*) n FROM matches_v2 "
                    "WHERE kickoff_utc > '2026-08-24'", sessiz=True)
    la = int(lig[0]["n"]) if lig else 0
    lt = int(lig_tum[0]["n"]) if lig_tum else 0
    alanlar.append({"kol": "league_code", "ad": "lig sınıflandırması",
                    "neden": "ülke rozeti · lig bazlı analiz",
                    "n": lt - la, "pay": ((lt - la) / lt) if lt else 0.0})
    return {"sistem": sistem, "ajan": ajan, "alan": alanlar, "mac": T}


@st.cache_data(ttl=240, show_spinner=False)
def load_inceleme() -> dict:
    """Kazanan/kaybeden ayrıştırması — DATA · MODEL · TRADE.

    V1'in kupon analizi sayfasının yerine geçer, üç farkla:
      1) Edge MARJSIZ ölçülür (mp/q − 1). V1 marjlı edge kullanıyordu;
         o tanımda varyansın çoğu marj farkıdır, tahmin hatası değil.
      2) Dönem kapsamlı — arşivlenen dönem karneye karışmaz.
      3) KAYIP ANATOMİSİ eklendi: kombine kaybettiğinde hangi ayak
         düşürdü? Ölçüldü ki altı hücrenin altısında zayıf halka
         SONUÇ (1X2) ayağı — kaybın ~yarısı gol ayağı tuttuğu hâlde.
    """
    rows = _rows(
        "SELECT pb.market mk, pb.pick pk, pb.odds o, pb.model_prob mp, "
        "pb.status s, pb.league lg, pb.home_score hs, pb.away_score aws, "
        "pb.reason rsn, pb.postmortem pm, pb.settled_at sat, "
        "pb.home_team h, pb.away_team a, pb.portfolio_id p, "
        "pc.coupon_type ct, "
        "m.closing_1 c1, m.closing_X cx, m.closing_2 c2, "
        "m.closing_over25 cu, m.closing_under25 ca, "
        "m.closing_btts_yes bv, m.closing_btts_no bn "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "LEFT JOIN matches_v2 m ON m.match_id = pb.match_id "
        "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start)",
        sessiz=True)
    if not rows:
        return {"n": 0}

    D = []
    for r in rows:
        try:
            o = float(r["o"])
        except Exception:
            continue
        mk = str(r["mk"] or "").upper()
        pk = str(r["pk"] or "").strip()
        # marjsız fiyat — pazarın tam vektöründen
        q = None
        try:
            if mk == "1X2":
                v = [r["c1"], r["cx"], r["c2"]]
                i = {"1": 0, "0": 1, "X": 1, "2": 2}.get(pk.upper())
            elif mk in ("UST_25", "ALT_25", "OU2.5"):
                v = [r["cu"], r["ca"]]
                i = 0 if (mk == "UST_25" or pk.upper() in ("UST", "ÜST")) else 1
            elif mk in ("KG_VAR", "KG_YOK"):
                v = [r["bv"], r["bn"]]
                i = 0 if mk == "KG_VAR" else 1
            else:
                v, i = None, None
            if v and i is not None and not any(
                    x is None or float(x) <= 1.01 for x in v):
                inv = [1.0 / float(x) for x in v]
                q = inv[i] / sum(inv)
        except Exception:
            q = None
        mp = None
        try:
            mp = float(r["mp"]) if r["mp"] is not None else None
            if mp is not None and not (0 < mp < 1):
                mp = None
        except Exception:
            mp = None
        won = r["s"] == "won"
        D.append({
            "mk": mk, "pk": pk, "o": o, "q": q, "mp": mp, "won": won,
            "ret": (o - 1.0) if won else -1.0,
            "e": (mp / q - 1.0) if (mp and q) else None,
            "lg": (r["lg"] or "—"), "ct": str(r["ct"] or "?"),
            "rsn": r["rsn"], "pm": r["pm"], "sat": str(r["sat"] or "")[:16],
            "h": r["h"], "a": r["a"], "p": r["p"],
            "hs": r["hs"], "aws": r["aws"],
        })

    def blok(sel):
        n = len(sel)
        if not n:
            return None
        return {"n": n,
                "hit": sum(1 for x in sel if x["won"]) / n,
                "bek": sum(1.0 / x["o"] for x in sel) / n,
                "roi": sum(x["ret"] for x in sel) / n}

    # ── MODEL: kalibrasyon (model olasılığı bandına göre) ──
    kal = []
    for lo, hi, ad in ((0, .40, "%0-40"), (.40, .55, "%40-55"),
                       (.55, .70, "%55-70"), (.70, .85, "%70-85"),
                       (.85, 1.01, "%85+")):
        g = [x for x in D if x["mp"] and lo <= x["mp"] < hi]
        if len(g) < 5:
            kal.append({"ad": ad, "n": len(g)})
            continue
        pr = sum(x["mp"] for x in g) / len(g)
        ac = sum(1 for x in g if x["won"]) / len(g)
        kal.append({"ad": ad, "n": len(g), "tah": pr, "ger": ac,
                    "fark": ac - pr})

    # ── MODEL: marjsız edge → gerçekleşen getiri ──
    eb = []
    ed = [x for x in D if x["e"] is not None]
    if len(ed) >= 25:
        ed.sort(key=lambda z: z["e"])
        m = len(ed)
        for i in range(5):
            g = ed[i * m // 5:(i + 1) * m // 5] if i < 4 else ed[4 * m // 5:]
            eb.append({"ad": f"Q{i+1}", "n": len(g),
                       "e": sum(x["e"] for x in g) / len(g),
                       "roi": sum(x["ret"] for x in g) / len(g)})

    # ── TRADE: pazar · kupon türü · lig ──
    def grupla(key, en_az=8):
        d = {}
        for x in D:
            d.setdefault(x[key], []).append(x)
        out = [{"ad": k, **blok(v)} for k, v in d.items()
               if blok(v) and len(v) >= en_az]
        out.sort(key=lambda z: -z["n"])
        return out[:9]

    # ── KAYIP ANATOMİSİ: kombine kaybettiğinde hangi ayak düşürdü? ──
    anat = {"sonuc": 0, "gol": 0, "iki": 0, "n": 0}
    for x in D:
        if x["won"] or " ve " not in str(x["pk"]):
            continue
        if x["hs"] is None or x["aws"] is None:
            continue
        try:
            hs, aws = int(x["hs"]), int(x["aws"])
        except Exception:
            continue
        parts = [p.strip() for p in str(x["pk"]).split(" ve ", 1)]
        if len(parts) != 2:
            continue
        a1, b1 = parts
        res = "1" if hs > aws else ("0" if hs == aws else "2")
        ok_a = (a1 == res) if a1 in ("1", "0", "2") else (
            (hs + aws > 2.5) == (a1.upper() in ("ÜST", "UST")))
        bu = b1.upper()
        if bu in ("ÜST", "UST"):
            ok_b = hs + aws > 2.5
        elif bu == "ALT":
            ok_b = hs + aws < 2.5
        elif bu == "VAR":
            ok_b = hs > 0 and aws > 0
        elif bu == "YOK":
            ok_b = not (hs > 0 and aws > 0)
        else:
            continue
        anat["n"] += 1
        if ok_a and not ok_b:
            anat["gol"] += 1
        elif ok_b and not ok_a:
            anat["sonuc"] += 1
        else:
            anat["iki"] += 1

    # ── gerekçe defteri: son kayıtlar ──
    gd = [x for x in D if (x["rsn"] or x["pm"])]
    gd.sort(key=lambda z: z["sat"], reverse=True)

    return {"n": len(D), "genel": blok(D), "kal": kal, "eb": eb,
            "pazar": grupla("mk"), "tur": grupla("ct", 5),
            "lig": grupla("lg"), "anat": anat, "defter": gd[:22]}


@st.cache_data(ttl=300, show_spinner=False)
def load_clv() -> dict:
    """CLV kırılımı — pazar ve lig bazında kapanış çizgisi performansı.

    CLV neden önemli: girdiğin fiyat kapanıştan iyiyse, piyasadan ÖNCE
    doğru tarafı görmüşsün demektir. Sonuçtan bağımsızdır — kaybettiğin
    bahiste bile pozitif CLV seçimin doğruluğunu söyler.

    ⚠️ Tek başına marjı YENMEZ. iddaa'nın %17,6'sını aşmak için +%17,6
    CLV gerekir; öyle bir şey yok. CLV bir kâr vaadi değil, ÖNCÜ
    GÖSTERGEDİR."""
    rows = _rows(
        "SELECT market mk, league lg, clv FROM paper_bets "
        "WHERE clv IS NOT NULL", sessiz=True)
    if len(rows) < 50:
        return {"n": len(rows)}
    v = []
    for r in rows:
        try:
            v.append({"mk": str(r["mk"] or "—"), "lg": str(r["lg"] or "—"),
                      "c": float(r["clv"])})
        except Exception:
            continue
    n = len(v)
    m = sum(x["c"] for x in v) / n
    sd = math.sqrt(sum((x["c"] - m) ** 2 for x in v) / max(n - 1, 1)) / math.sqrt(n)

    def kir(key, en_az=30):
        d = {}
        for x in v:
            d.setdefault(x[key], []).append(x["c"])
        out = []
        for k, g in d.items():
            if len(g) < en_az:
                continue
            mm = sum(g) / len(g)
            out.append({"ad": k, "n": len(g), "ort": mm,
                        "beat": sum(1 for z in g if z > 0) / len(g)})
        out.sort(key=lambda z: -z["ort"])
        return out[:8]

    return {"n": n, "ort": m, "t": (m / sd) if sd > 1e-12 else 0.0,
            "beat": sum(1 for x in v if x["c"] > 0) / n,
            "sifir": sum(1 for x in v if abs(x["c"]) < 1e-9) / n,
            "pazar": kir("mk"), "lig": kir("lg")}


@st.cache_data(ttl=600, show_spinner=False)
def load_mihenk() -> dict:
    """Mihenk — 2 günde bir arşivlenen yönetici özeti (V1'den taşındı).

    V2 raporu yeniden ÜRETMEZ, arşivi okur. Rapor üretimi
    02_VERI/exec_report.py'de kalır; burası okuma yüzeyidir. Bir işin
    iki yerde yapılması, V1'in en büyük hatasıydı."""
    rows = _rows("SELECT report_no no, ts, payload FROM exec_reports "
                 "ORDER BY report_no DESC LIMIT 6", sessiz=True)
    if not rows:
        return {"var": False}
    import json
    son = rows[0]
    try:
        p = json.loads(son["payload"])
    except Exception:
        p = {}
    return {"var": True, "no": son["no"], "ts": str(son["ts"])[:16],
            "payload": p, "gecmis": [{"no": r["no"], "ts": str(r["ts"])[:16]}
                                     for r in rows]}


@st.cache_data(ttl=240, show_spinner=False)
def load_egri() -> dict:
    """Kasa eğrisi ve düşüş — dönem kapsamlı, tüm ajanlar birleşik.

    ⚠️ Sıralama kuponun SONUÇLANDIĞI ana göre yapılır, kurulduğu ana
    göre değil. Kasa gerçekte para değiştiğinde hareket eder; kurulma
    sırasına göre çizilen eğri, olmamış bir geçmişi gösterir."""
    rows = _rows(
        "SELECT pc.settled_at sa, pc.pnl, pc.stake, pc.status st "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "ORDER BY pc.settled_at", sessiz=True)
    if len(rows) < 10:
        return {"n": len(rows)}
    kum, tepe, dusus = 0.0, 0.0, 0.0
    nokta, ciro = [], 0.0
    for r in rows:
        try:
            kum += float(r["pnl"] or 0)
            ciro += float(r["stake"] or 0)
        except Exception:
            continue
        tepe = max(tepe, kum)
        dusus = min(dusus, kum - tepe)
        nokta.append({"t": str(r["sa"])[:10], "k": kum, "tepe": tepe})
    son = nokta[-1]["k"] if nokta else 0.0
    return {"n": len(nokta), "nokta": nokta, "son": son, "tepe": tepe,
            "dusus": dusus, "ciro": ciro,
            "roi": (son / ciro) if ciro else 0.0,
            "dusus_pay": (dusus / tepe) if tepe > 0 else 0.0}


def _svg_egri(d: dict, w: int = 560, h: int = 150) -> str:
    """Kasa eğrisi — satır içi SVG, temaya duyarlı.

    Kütüphane yok: plotly bir grafik için 3 MB bağımlılık demek. Alan
    dolgusu, sıfır çizgisi, vurgulanmış son nokta ve düşüş gölgesi
    elle çizilir — okunurluk kütüphaneden değil, seçimlerden gelir."""
    p = d["nokta"]
    if len(p) < 2:
        return ""
    ys = [x["k"] for x in p] + [0.0]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = (hi - lo) * 0.12
    lo, hi = lo - pad, hi + pad
    n = len(p)

    def X(i):
        return 4 + i * (w - 8) / max(n - 1, 1)

    def Y(v):
        return h - 6 - (v - lo) / (hi - lo) * (h - 12)

    cizgi = " ".join(f"{X(i):.1f},{Y(x['k']):.1f}" for i, x in enumerate(p))
    alan = (f"{X(0):.1f},{Y(0):.1f} " + cizgi +
            f" {X(n-1):.1f},{Y(0):.1f}")
    y0 = Y(0)
    poz = d["son"] >= 0
    renk = "var(--pos)" if poz else "var(--neg)"
    return (
        f"<svg viewBox='0 0 {w} {h}' width='100%' height='{h}' "
        f"preserveAspectRatio='none' role='img' "
        f"aria-label='Kasa eğrisi, son değer {d['son']:.0f} lira'>"
        f"<line x1='0' y1='{y0:.1f}' x2='{w}' y2='{y0:.1f}' "
        f"stroke='var(--line-2)' stroke-width='1' stroke-dasharray='3 3'/>"
        f"<polygon points='{alan}' fill='{renk}' opacity='0.10'/>"
        f"<polyline points='{cizgi}' fill='none' stroke='{renk}' "
        f"stroke-width='1.8' stroke-linejoin='round'/>"
        f"<circle cx='{X(n-1):.1f}' cy='{Y(p[-1]['k']):.1f}' r='3.5' "
        f"fill='{renk}'/></svg>")


@st.cache_data(ttl=120, show_spinner=False)
def load_pozisyon() -> list[dict]:
    """Açık kuponlar — kupon düzeyinde, ayaklarıyla (V1 pozisyon+emir).

    Tahta tek tek seçimleri gösterir; burası KUPONU gösterir: kaç ayak,
    toplam oran, ne kadar yatırıldı, tutarsa ne döner. İkisi farklı
    sorulara cevap verir."""
    kup = _rows(
        "SELECT pc.coupon_id cid, pc.portfolio_id p, pc.num_legs nl, "
        "pc.combined_odds co, pc.stake sk, pc.potential_return pr, "
        "pc.created_at ca FROM paper_coupons pc "
        "WHERE pc.status='open' ORDER BY pc.created_at DESC LIMIT 40",
        sessiz=True)
    if not kup:
        return []
    ids = [k["cid"] for k in kup]
    qs = ",".join("?" for _ in ids)
    ayak = _rows(
        f"SELECT coupon_id cid, home_team h, away_team a, market mk, "
        f"pick pk, odds o, kickoff_utc ko FROM paper_bets "
        f"WHERE coupon_id IN ({qs}) ORDER BY kickoff_utc", tuple(ids),
        sessiz=True)
    by: dict = {}
    for x in ayak:
        by.setdefault(x["cid"], []).append(x)
    out = []
    for k in kup:
        L = by.get(k["cid"], [])
        if not L:
            continue
        out.append({
            "p": k["p"], "em": k["p"],
            "ad": str(k["p"]).rsplit("_", 1)[0],
            "n": len(L), "co": float(k["co"] or 0), "sk": float(k["sk"] or 0),
            "pr": float(k["pr"] or 0), "ko": str(L[0]["ko"])[5:16].replace("T", " "),
            "ayak": [{"h": x["h"], "a": x["a"], "mk": x["mk"],
                      "pk": x["pk"], "o": float(x["o"] or 0)} for x in L],
        })
    out.sort(key=lambda z: z["ko"])
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_risk() -> list[dict]:
    """Ajan risk durumu — kasa tabanı, dönem, ihtar, lisans (V1 risk+ayarlar).

    Prop-firm mantığı: her ajanın kendi kasası, kendi tabanı ve kendi
    sözleşmesi var. Taban altına düşen ajan koruma moduna girer; iki
    ihtar kadro dışı demektir. Bu sayfa o sözleşmenin durumunu gösterir."""
    rows = _rows(
        "SELECT portfolio_id p, current_bankroll cb, initial_bankroll ib, "
        "peak_bankroll pk, period_status ps, period_start_bankroll pb, "
        "ihtar_count ih, benched bn, era_no en, status st "
        "FROM paper_portfolio ORDER BY current_bankroll DESC", sessiz=True)
    out = []
    for r in rows:
        ib = float(r["ib"] or 1000)
        cb = float(r["cb"] or 0)
        pk = float(r["pk"] or ib)
        oran = (cb / ib) if ib else 0
        if bool(r["bn"]):
            dur, sev = "KADRO DIŞI", "g3"
        elif oran < 0.50:
            dur, sev = "TABAN FRENİ", "g3"
        elif int(r["ih"] or 0) >= 2:
            dur, sev = "2 İHTAR", "g3"
        elif int(r["ih"] or 0) == 1:
            dur, sev = "1 İHTAR", "g2"
        elif oran >= 1.0:
            dur, sev = "SAĞLIKLI", "g1"
        else:
            dur, sev = "İZLEMEDE", "g2"
        out.append({
            "p": r["p"], "em": r["p"],
            "ad": str(r["p"]).rsplit("_", 1)[0], "cb": cb, "ib": ib,
            "oran": oran, "tepe": pk,
            "dusus": ((cb - pk) / pk) if pk > 0 else 0.0,
            "ihtar": int(r["ih"] or 0), "era": r["en"],
            "dur": dur, "sev": sev,
        })
    return out


@st.cache_data(ttl=240, show_spinner=False)
def load_ajan_egri() -> dict:
    """Her ajanın kendi kasa eğrisi — dönem kapsamlı.

    Finansal terminalin küçük-çoklu (small multiples) mantığı: yan yana
    duran küçük eğriler, tek büyük grafikten daha çok şey söyler. Göz
    şekli karşılaştırır — hangisi yükseliyor, hangisi düz, hangisi
    uçurumdan düşmüş."""
    rows = _rows(
        "SELECT pc.portfolio_id p, pc.settled_at sa, pc.pnl "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "ORDER BY pc.settled_at", sessiz=True)
    by: dict = {}
    for r in rows:
        try:
            by.setdefault(r["p"], []).append(float(r["pnl"] or 0))
        except Exception:
            continue
    out = {}
    for pid, v in by.items():
        kum, seri, tepe, dus = 0.0, [], 0.0, 0.0
        for x in v:
            kum += x
            tepe = max(tepe, kum)
            dus = min(dus, kum - tepe)
            seri.append(kum)
        out[pid] = {"seri": seri, "son": kum, "dusus": dus, "n": len(seri)}
    return out


def _kivilcim(seri: list, w: int = 96, h: int = 26) -> str:
    """Kıvılcım çizgisi — tablo hücresine sığan mini eğri.

    Eksen yok, etiket yok: bu bir grafik değil, bir ŞEKİL. Rakam zaten
    yanındaki sütunda; buradan okunması gereken tek şey yön ve pürüz."""
    if not seri or len(seri) < 2:
        return "<span style='color:var(--muted);font-size:11px;'>—</span>"
    lo, hi = min(seri + [0.0]), max(seri + [0.0])
    if hi - lo < 1e-9:
        hi = lo + 1
    n = len(seri)
    pts = " ".join(
        f"{2 + i * (w - 4) / max(n - 1, 1):.1f},"
        f"{h - 2 - (v - lo) / (hi - lo) * (h - 4):.1f}"
        for i, v in enumerate(seri))
    y0 = h - 2 - (0 - lo) / (hi - lo) * (h - 4)
    renk = "var(--pos)" if seri[-1] >= 0 else "var(--neg)"
    sx = 2 + (n - 1) * (w - 4) / max(n - 1, 1)
    sy = h - 2 - (seri[-1] - lo) / (hi - lo) * (h - 4)
    return (
        f"<svg viewBox='0 0 {w} {h}' width='{w}' height='{h}' "
        f"style='display:block;' aria-hidden='true'>"
        f"<line x1='0' y1='{y0:.1f}' x2='{w}' y2='{y0:.1f}' "
        f"stroke='var(--line-2)' stroke-width='1'/>"
        f"<polyline points='{pts}' fill='none' stroke='{renk}' "
        f"stroke-width='1.4' stroke-linejoin='round'/>"
        f"<circle cx='{sx:.1f}' cy='{sy:.1f}' r='2' fill='{renk}'/></svg>")


@st.cache_data(ttl=180, show_spinner=False)
def load_ajan_detay(pid: str) -> dict:
    """Tek ajanın dosyası — V1'de ayrı sayfaydı, artık aynı yerde açılır.

    Ayrı sayfa yerine açılır panel: bağlamı kaybetmeden inceleme.
    Ligden çıkıp geri dönmek, karşılaştırmayı bozar."""
    bet = _rows(
        "SELECT pb.home_team h, pb.away_team a, pb.market mk, pb.pick pk, "
        "pb.odds o, pb.status s, pb.reason rsn, pb.postmortem pm, "
        "pb.settled_at sat, pb.league lg "
        "FROM paper_bets pb "
        "JOIN paper_coupons pc ON pc.coupon_id = pb.coupon_id "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
        "WHERE pb.portfolio_id = ? AND pb.status IN ('won','lost') "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "ORDER BY pb.settled_at DESC LIMIT 14", (pid,), sessiz=True)
    acik = _rows(
        "SELECT home_team h, away_team a, market mk, pick pk, odds o, "
        "kickoff_utc ko FROM paper_bets WHERE portfolio_id = ? "
        "AND status = 'open' ORDER BY kickoff_utc LIMIT 8", (pid,), sessiz=True)
    tes = _rows(
        "SELECT status, detail, ts FROM agent_diag WHERE pid = ? "
        "ORDER BY ts DESC LIMIT 1", (pid,), sessiz=True)
    return {"bet": bet, "acik": acik, "teshis": (tes[0] if tes else None)}


@st.cache_data(ttl=300, show_spinner=False)
def load_veri_ozet() -> dict:
    """Verinin ÖZETİ, KALİTESİ ve TAZELİĞİ.

    Doluluk oranı tek başına yetmez: 26.000 satırın %90'ı dolu olabilir
    ama hepsi iki yıl önceden ise sistem kördür. Üç soru ayrı ayrı
    sorulmalı — ne kadar var, ne kadarı dolu, ne kadarı taze."""
    t = _rows("SELECT COUNT(*) n FROM matches_v2", sessiz=True)
    st_ = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=1",
                sessiz=True)
    ac = _rows("SELECT COUNT(*) n FROM matches_v2 WHERE is_settled=0 "
               "AND kickoff_utc > ?", (_simdi(),), sessiz=True)
    tz = _rows("SELECT MAX(refreshed_at) v FROM matches_v2", sessiz=True)
    # kaynak dagilimi ve tarih araligi
    kay = _rows("SELECT closing_source k, COUNT(*) n, "
                "MIN(substr(CAST(kickoff_utc AS TEXT),1,7)) ilk, "
                "MAX(substr(CAST(kickoff_utc AS TEXT),1,7)) son "
                "FROM matches_v2 WHERE is_settled=1 AND closing_1 IS NOT NULL "
                "GROUP BY closing_source ORDER BY n DESC", sessiz=True)
    # tablo boyutlari — sistemin hafizasi
    tablolar = []
    for tb, ad in (("matches_v2", "maç"), ("market_odds", "pazar fiyatı"),
                   ("paper_bets", "bahis"), ("paper_coupons", "kupon"),
                   ("odds_history", "fiyat geçmişi"),
                   ("measurement_runs", "ölçüm koşusu"),
                   ("injuries", "sakatlık"), ("xg_data", "xG")):
        r = _rows(f"SELECT COUNT(*) n FROM {tb}", sessiz=True)
        if r:
            tablolar.append({"ad": ad, "tb": tb, "n": int(r[0]["n"] or 0)})
    return {
        "toplam": int(t[0]["n"]) if t else 0,
        "sonuclanmis": int(st_[0]["n"]) if st_ else 0,
        "yaklasan": int(ac[0]["n"]) if ac else 0,
        "tazelik": str(tz[0]["v"])[:16] if (tz and tz[0]["v"]) else None,
        "kaynak": kay, "tablolar": tablolar,
    }


def _simdi() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


@st.cache_data(ttl=240, show_spinner=False)
def load_egri_ham() -> list[dict]:
    """Ham kupon akışı — süzgeç uygulanabilsin diye toplanmadan.

    Eğri sunucuda değil, süzgeçten SONRA hesaplanır. Önceden toplanmış
    seri süzülemez: ajan çıkarınca eğrinin baştan kurulması gerekir."""
    return _rows(
        "SELECT pc.portfolio_id p, pc.settled_at sa, pc.pnl, pc.stake, "
        "pc.coupon_type ct, pc.num_legs nl, "
        "(SELECT string_agg(DISTINCT pb.market, ',') FROM paper_bets pb "
        " WHERE pb.coupon_id = pc.coupon_id) mk "
        "FROM paper_coupons pc "
        "JOIN paper_portfolio pp ON pp.portfolio_id = pc.portfolio_id "
        "WHERE pc.status IN ('won','lost') AND pc.settled_at IS NOT NULL "
        "AND (pp.era_start IS NULL OR pc.created_at >= pp.era_start) "
        "ORDER BY pc.settled_at", sessiz=True)


def _svg_zaman(nokta: list, w: int = 900, h: int = 260) -> str:
    """Zaman eksenli kasa eğrisi — Bloomberg/Alpaca usulü.

    Eksen olmadan grafik bir şekilden ibarettir: 'yükseliyor' dersin ama
    'ne zaman' diyemezsin. Burada X tarih, Y para; ikisi de etiketli,
    seyrek ızgaralı. Izgara soluk çünkü işi hizalamak, dikkat çekmek
    değil."""
    if len(nokta) < 2:
        return ("<div class='dq'>Eğri için en az iki sonuçlanmış kupon "
                "gerekiyor.</div>")
    SOL, ALT, UST, SAG = 58, 26, 10, 12
    gw, gh = w - SOL - SAG, h - ALT - UST
    ys = [p["k"] for p in nokta] + [0.0]
    lo, hi = min(ys), max(ys)
    if hi - lo < 1e-9:
        hi = lo + 1
    pad = (hi - lo) * 0.10
    lo, hi = lo - pad, hi + pad
    n = len(nokta)

    def X(i):
        return SOL + i * gw / max(n - 1, 1)

    def Y(v):
        return UST + gh - (v - lo) / (hi - lo) * gh

    parts = []
    # yatay izgara + para etiketleri
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        v = lo + (hi - lo) * f
        y = Y(v)
        parts.append(
            f"<line x1='{SOL}' y1='{y:.1f}' x2='{w-SAG}' y2='{y:.1f}' "
            f"stroke='var(--line)' stroke-width='1'/>"
            f"<text x='{SOL-8}' y='{y+3.5:.1f}' text-anchor='end' "
            f"font-size='10' fill='var(--muted)' "
            f"font-family='JetBrains Mono,monospace'>"
            f"{('+' if v>=0 else '−')}{abs(v):,.0f}</text>".replace(",", "."))
    # sifir cizgisi belirgin
    parts.append(
        f"<line x1='{SOL}' y1='{Y(0):.1f}' x2='{w-SAG}' y2='{Y(0):.1f}' "
        f"stroke='var(--line-2)' stroke-width='1.2' stroke-dasharray='4 3'/>")
    # dikey izgara + tarih etiketleri (en fazla 6)
    adim = max(1, n // 6)
    for i in range(0, n, adim):
        x = X(i)
        t = str(nokta[i]["t"])[5:10].replace("-", ".")
        parts.append(
            f"<line x1='{x:.1f}' y1='{UST}' x2='{x:.1f}' y2='{UST+gh}' "
            f"stroke='var(--line)' stroke-width='1'/>"
            f"<text x='{x:.1f}' y='{h-8}' text-anchor='middle' font-size='10' "
            f"fill='var(--muted)' font-family='JetBrains Mono,monospace'>"
            f"{t}</text>")
    cizgi = " ".join(f"{X(i):.1f},{Y(p['k']):.1f}" for i, p in enumerate(nokta))
    alan = f"{X(0):.1f},{Y(0):.1f} {cizgi} {X(n-1):.1f},{Y(0):.1f}"
    poz = nokta[-1]["k"] >= 0
    renk = "var(--pos)" if poz else "var(--neg)"
    parts.append(f"<polygon points='{alan}' fill='{renk}' opacity='0.09'/>")
    parts.append(f"<polyline points='{cizgi}' fill='none' stroke='{renk}' "
                 f"stroke-width='1.9' stroke-linejoin='round'/>")
    parts.append(f"<circle cx='{X(n-1):.1f}' cy='{Y(nokta[-1]['k']):.1f}' "
                 f"r='4' fill='{renk}'/>")
    return (f"<svg viewBox='0 0 {w} {h}' width='100%' height='{h}' "
            f"role='img' aria-label='Kasa eğrisi, zaman eksenli'>"
            + "".join(parts) + "</svg>")


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
    r = load_rail()
    _sayfa_basligi(
        "Karar Masası",
        "Kime güvenilir, bugün ne var, ne kuruyorsun — üçü bir arada.",
        [{"ad": "Açık pozisyon", "deger": str(r["acik"])},
         {"ad": "Kapanmış bahis",
          "deger": "{:,}".format(r["kapali"]).replace(",", ".")},
         {"ad": "Beceri k",
          "deger": ("henüz yok" if r["k"] is None
                    else ("%+.3f" % r["k"]).replace(".", ",")),
          "cls": ("ps" if r["k_gecti"] else "ng")}])
    left, mid, right = st.columns([1.32, 1.42, 0.98], gap="medium")

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
                f"<td><span class='ag'>{_rozet(a['pid'])}{a['ad']}</span>"
                f"<span class='sb'>n={a['n']} · oran {_num(a['odds'])}</span></td>"
                f"<td class='r n opt'>{_pct(a['hit'])}</td>"
                f"<td class='r n opt'>{_pct(a['exp'])}</td>"
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
              <th class="r opt">İsabet</th><th class="r opt">Fiyat bekler</th>
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
            c1, c2 = st.columns([4.3, 1.35], gap="small")
            with c1:
                lbl = (f"{b['h']} — {b['a']}  ·  {b['ad']}"
                       f"  ·  {b['mk']} {b['pk']}  ·  {b['ko']}")
                _sepette = any(x["id"] == b["id"] for x in _sepet())
                on = st.checkbox(lbl + ("   ✓ sepette" if _sepette else ""),
                                 key=f"v2_{b['id']}")
            with c2:
                st.markdown(
                    f"<div style='text-align:right;font-family:\"JetBrains Mono\",monospace;"
                    f"font-size:17px;color:var(--ink);padding-top:3px;"
                    f"white-space:nowrap;'>"
                    f"<span class='cc{' no' if b['lg']=='ALL' else ''}'>{b['code']}</span>"
                    f"{_num(b['o'])}</div>", unsafe_allow_html=True)
            if on:
                sel.append(b)

    # ── SAĞ: sepete gönder ─────────────────────────────────────
    with right:
        sp = _sepet()
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Seçtiklerin</h2>"
            "<div class='hint'>sepete gönder</div></div><div class='v2body'>",
            unsafe_allow_html=True)
        if sel:
            O = 1.0
            for b in sel:
                O *= b["o"]
            st.markdown(
                "<div class='ro'><span>İşaretli</span><b>" + str(len(sel)) +
                "</b></div><div class='ro'><span>Toplam oran</span><b>" +
                _num(O) + "</b></div>", unsafe_allow_html=True)
            if st.button("Sepete ekle  (" + str(len(sel)) + ")",
                         type="primary", use_container_width=True,
                         key="v2_sepete"):
                # ⚠️ Onay kutusu durumuna DOKUNMA: Streamlit, bir widget'ın
                # session_state'ini AYNI çalıştırmada değiştirmeyi yasaklar ve
                # istisna firlatir — ilk denemede iki secimden biri eklendi ve
                # sayfa hic gecmedi. Sepet zaten kimlige gore tekillestiriyor,
                # kutular isaretli kalsa da zarar yok.
                for b in sel:
                    sepete_ekle(b)
                st.session_state["v2_page"] = "Sepet"
                st.rerun()
        else:
            st.markdown(
                "<div class='v2bos'>Tahtadan seçim işaretle.<br>"
                "Seçtiklerin sepete gider, orada tartılır.</div>",
                unsafe_allow_html=True)
        if sp:
            st.markdown(
                "<div class='dq' style='margin-top:var(--s3);'>Sepette "
                "<b>" + str(len(sp)) + " ayak</b> bekliyor. Tartmak ve "
                "oynamak için <b>Sepet</b> sayfasına geç.</div>",
                unsafe_allow_html=True)
        st.markdown("</div></div>", unsafe_allow_html=True)

    poz = load_pozisyon()
    if poz:
        sat = []
        for k in poz[:14]:
            ayaklar = " + ".join(
                str(x["h"])[:12] + " " + str(x["pk"])[:10] for x in k["ayak"])
            sat.append(
                "<tr><td><span class='ag'>" + _rozet(k["p"]) + k["ad"] +
                "</span><span class='sb'>" + ayaklar[:92] + "</span></td>"
                "<td class='r n opt'>" + str(k["n"]) + "</td>"
                "<td class='r n'>" + _num(k["co"]) + "</td>"
                "<td class='r n opt'>" + "{:.0f}".format(k["sk"]) + " ₺</td>"
                "<td class='r n'>" + "{:,.0f}".format(k["pr"]).replace(",", ".") +
                " ₺</td><td class='r n opt'>" + k["ko"] + "</td></tr>")
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Açık Kuponlar</h2>"
            "<div class='hint'>" + str(len(poz)) + " kupon · kupon düzeyi"
            "</div></div><div class='v2body'>"
            "<div class='v2mb'>Tahta tek tek <b>seçimleri</b> gösterir; "
            "burası <b>kuponu</b>: kaç ayak, toplam oran, tutarsa ne döner. "
            "İkisi farklı sorulara cevap verir.</div>"
            "<table class='v2'><thead><tr><th>Ajan ve ayaklar</th>"
            "<th class='r opt'>Ayak</th><th class='r'>Oran</th>"
            "<th class='r opt'>Yatan</th><th class='r'>Döner</th>"
            "<th class='r opt'>Başlangıç</th></tr></thead><tbody>" +
            "".join(sat) + "</tbody></table></div></div>",
            unsafe_allow_html=True)

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
    _k = []
    if o.get("var"):
        _f = o["edge"] - h["edge"] if h.get("n") else 0.0
        _k = [{"ad": "Kupon", "deger": str(o["kupon"])},
              {"ad": "Havuzdan fark", "deger": _sgn(_f),
               "cls": ("ps" if _f >= 0 else "ng")}]
    _sayfa_basligi(
        "OPUS 5 Defteri",
        "Gerçekte oynananlar. Kâğıt ile saha arasındaki fark ancak "
        "burada ölçülebilir.", _k)
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
                "<th class='r opt'>Ayak</th><th class='r opt'>İsabet</th>"
                "<th class='r opt'>Fiyat bekler</th><th class='r'>Fark</th>"
                "</tr></thead><tbody>"
                "<tr" + (" class='adv'" if o["edge"] > h.get("edge", 0) else "") +
                "><td><span class='ag'>OPUS 5 · sen</span>"
                "<span class='sb'>" + str(o["kupon"]) + " kupon · " +
                str(o["acik"]) + " açık</span></td>"
                "<td class='r n'>" + str(o["ayak"]) + "</td>"
                "<td class='r n'>" + _pct(o["hit"]) + "</td>"
                "<td class='r n'>" + _pct(o["exp"]) + "</td>"
                "<td class='r'><span class='" +
                ("dp" if o["edge"] >= 0 else "dm") + "'>" + _sgn(o["edge"]) +
                "</span></td></tr>"
                "<tr><td><span class='ag'>Kâğıt ajanlar · havuz</span>"
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


def _ajan_paneli(pid: str, lig: dict) -> None:
    """Ajan dosyası — ayrı sayfa değil, ligin İÇİNDE açılır panel.

    V1'de her ajanın kendi sayfası vardı (20 menü girdisi). Ayrı sayfa
    bağlamı koparır: ligden çıkıp geri dönmek karşılaştırmayı bozar.
    Panel, sıralamanın hemen altında açılır ve kapanır."""
    tum = lig["mavi"] + lig["kirmizi"]
    a = next((x for x in tum if x["pid"] == pid), None)
    if not a:
        return
    d = load_ajan_detay(pid)
    eg = load_ajan_egri().get(pid, {})
    ust, kapat = st.columns([6, 1], gap="small")
    with ust:
        st.markdown(
            "<div style='display:flex;align-items:baseline;gap:var(--s3);"
            "margin:var(--s4) 0 var(--s3);'>"
            "<span style='font-size:var(--t-sayfa);font-weight:600;'>" +
            _rozet(pid) + a["ad"] + "</span>"
            "<span style='font-family:\"JetBrains Mono\",monospace;"
            "font-size:var(--t-alt);color:var(--muted);'>dönem " +
            str(a["era"] or "—") + " · n=" + str(a["n"]) + " · kasa " +
            "{:,.0f}".format(a["kasa"]).replace(",", ".") + " ₺</span></div>",
            unsafe_allow_html=True)
    with kapat:
        if st.button("Kapat", key="v2_ajan_kapat", use_container_width=True):
            st.session_state["v2_ajan"] = None
            st.rerun()

    sol, sag = st.columns([1.0, 1.0], gap="small")
    with sol:
        ic = ""
        if d["teshis"]:
            t = str(d["teshis"]["status"] or "")
            g = ("g3" if "TIKANIKLIK" in t else
                 "g1" if "🟢" in t else "g2")
            temiz = t
            for e in ("🔴 ", "🟠 ", "🟢 ", "⚪ ", "😴 ", "🧊 ", "⏸ ", "🔒 ",
                      "🏁 ", "🛑 ", "🚫 "):
                temiz = temiz.replace(e, "")
            ic += ("<div class='dq' style='margin-bottom:var(--s3);'>"
                   "<span class='gr " + g + "'>" + temiz + "</span> " +
                   str(d["teshis"]["detail"] or "")[:120] + "</div>")
        if eg.get("seri"):
            ic += _svg_egri({"nokta": [{"k": v} for v in eg["seri"]],
                             "son": eg["son"]}, 460, 120)
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Seyir ve Durum</h2>"
            "<div class='hint'>dönem içi</div></div><div class='v2body'>" +
            (ic or "<div class='dq'>Dönem içi veri yok.</div>") +
            "</div></div>", unsafe_allow_html=True)

        if d["acik"]:
            sat = "".join(
                "<tr><td><span class='ag'>" + str(x["h"])[:16] + " — " +
                str(x["a"])[:16] + "</span><span class='sb'>" +
                str(x["mk"]) + " · " + str(x["pk"]) + "</span></td>"
                "<td class='r n'>" + _num(float(x["o"] or 0)) + "</td>"
                "<td class='r n opt'>" + str(x["ko"])[5:16].replace("T", " ") +
                "</td></tr>" for x in d["acik"])
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Açık Pozisyon</h2>"
                "<div class='hint'>" + str(len(d["acik"])) + " bahis</div></div>"
                "<div class='v2body'><table class='v2'><thead><tr><th>Maç</th>"
                "<th class='r'>Oran</th><th class='r opt'>Başlangıç</th>"
                "</tr></thead><tbody>" + sat + "</tbody></table></div></div>",
                unsafe_allow_html=True)

    with sag:
        if d["bet"]:
            sat = "".join(
                "<tr><td><span class='ag'>" + str(x["h"])[:15] + " — " +
                str(x["a"])[:15] + "</span><span class='sb'>" +
                str(x["rsn"] or "—")[:88] + "</span></td>"
                "<td class='r'><span class='" +
                ("dp" if x["s"] == "won" else "dm") + "'>" +
                str(x["pk"])[:14] + "</span>"
                "<span class='sb' style='text-align:right;'>" +
                str(x["pm"] or "")[:52] + "</span></td></tr>"
                for x in d["bet"])
            st.markdown(
                "<div class='v2card'><div class='v2head'>"
                "<h2>Gerekçe ve Sonuç</h2><div class='hint'>son " +
                str(len(d["bet"])) + " bahis</div></div><div class='v2body'>"
                "<table class='v2'><thead><tr><th>Maç ve gerekçe</th>"
                "<th class='r'>Seçim · ne oldu</th></tr></thead><tbody>" +
                sat + "</tbody></table></div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2card'><div class='v2head'>"
                "<h2>Gerekçe ve Sonuç</h2><div class='hint'>boş</div></div>"
                "<div class='v2body'><div class='dq'>Dönem içi kapanmış "
                "bahis yok.</div></div></div>", unsafe_allow_html=True)


def _gezinme_alt() -> None:
    """Önceki / sonraki sayfa — okuma sırasını takip eden gezinme.

    Sol panel 'nereye gidebilirim'i söyler; alttaki bu çift 'sırada ne
    var'ı. İkisi farklı sorulardır ve panelde ikisi de gerekir."""
    ad = list(PAGES)
    i = ad.index(st.session_state["v2_page"])
    onc = ad[i - 1] if i > 0 else None
    son = ad[i + 1] if i < len(ad) - 1 else None
    st.markdown("<div class='v2gez'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.4, 2.2, 1.4], gap="small")
    with c1:
        if onc and st.button("Önceki:  " + onc, key="v2_onc",
                             use_container_width=True):
            st.session_state["v2_page"] = onc
            st.session_state["v2_ajan"] = None
            st.rerun()
    with c2:
        st.markdown(
            "<div class='v2gez-orta'>" + str(i + 1) + " / " + str(len(ad)) +
            " · " + st.session_state["v2_page"] + "</div>",
            unsafe_allow_html=True)
    with c3:
        if son and st.button("Sonraki:  " + son, key="v2_son",
                             use_container_width=True):
            st.session_state["v2_page"] = son
            st.session_state["v2_ajan"] = None
            st.rerun()


def _takim_tablo(rows, baslik, alt, renk, EG=None):
    EG = EG or {}
    if not rows:
        return ("<div class='v2card'><div class='v2head'><h2>" + baslik +
                "</h2><div class='hint'>" + alt + "</div></div>"
                "<div class='v2body'><div class='dq'>Bu takımda dönem içi "
                "kapanmış bahis yok.</div></div></div>")
    body = []
    for i, a in enumerate(rows, 1):
        if a["n"] == 0:
            g, txt = "g2", "SESSİZ"
        elif a["perfect"]:
            g, txt = "g2", "ÖLÇÜLEMEZ"
        elif a["t"] is None:
            g, txt = "g2", "GÜRÜLTÜ"
        elif a["t"] <= -1.96:
            g, txt = "g3", "KÖTÜ"
        elif a["t"] >= 1.96:
            g, txt = "g1", "İYİ"
        else:
            g, txt = "g2", "GÜRÜLTÜ"
        # ⚠️ n=1'lik bir farki yesil cip ile one cikarmak, gurultuyu
        # avantaj gibi sunmaktir. KAVSAK n=1 ile +36,8p gosteriyordu.
        # Vurgu icin hem anlamli fark hem asgari orneklem sart.
        yeter = a["n"] >= 10
        adv = " class='adv'" if (a["edge"] >= 0.005 and yeter) else ""
        uyari = ""
        if a["benched"]:
            uyari = " <span class='gr g3'>KADRO DIŞI</span>"
        elif a["ihtar"]:
            uyari = " <span class='gr g2'>" + str(a["ihtar"]) + " İHTAR</span>"
        kasa_cls = "dp" if a["yuzde"] >= 100 else "dm"
        body.append(
            "<tr" + adv + "><td class='rk'>" + str(i) + "</td>"
            "<td><span class='ag'>" + _rozet(a["pid"]) + a["ad"] + "</span>" + uyari +
            "<span class='sb'>n=" + str(a["n"]) +
            (" · oran " + _num(a["odds"]) if a["n"] else " · oynamadı") +
            "</span></td>"
            "<td class='opt' style='width:100px;'>" +
            _kivilcim(EG.get(a["pid"], {}).get("seri", [])) + "</td>"
            "<td class='r n'>" + ("{:,.0f}".format(a["kasa"]).replace(",", ".")) + "</td>"
            "<td class='r opt'><span class='" + kasa_cls + "'>" +
            "{:.0f}".format(a["yuzde"]) + "%</span></td>"
            "<td class='r n opt'>" + (_pct(a["hit"]) if a["n"] else "—") + "</td>"
            "<td class='r n opt'>" + (_pct(a["exp"]) if a["n"] else "—") + "</td>"
            "<td class='r'>" + (
                "<span class='" + ("dp" if (a["edge"] >= 0.005 and yeter)
                                   else "dm") + "'>" +
                _sgn(a["edge"]) + "</span>" if a["n"] else "—") + "</td>"
            "<td class='r'><span class='gr " + g + "'>" + txt + "</span></td></tr>")
    return ("<div class='v2card' style='border-top:3px solid " + renk + ";'>"
            "<div class='v2head'><h2>" + baslik + "</h2>"
            "<div class='hint'>" + alt + "</div></div><div class='v2body'>"
            "<table class='v2'><thead><tr><th></th><th>Ajan</th>"
            "<th class='opt'>Seyir</th>"
            "<th class='r'>Kasa</th><th class='r opt'>%</th>"
            "<th class='r opt'>İsabet</th>"
            "<th class='r opt'>Fiyat bekler</th><th class='r'>Fark</th>"
            "<th class='r'>Hüküm</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>")


def _sepet() -> list:
    if "v2_sepet" not in st.session_state:
        st.session_state["v2_sepet"] = []
    return st.session_state["v2_sepet"]


def sepete_ekle(b: dict) -> None:
    sp = _sepet()
    if not any(x["id"] == b["id"] for x in sp):
        sp.append(b)


def page_sepet() -> None:
    """Sepet — seçtiklerini topla, tart, sonra oyna.

    Ayrı sayfa olmasının sebebi: seçmek ile OYNAMAK farklı kararlardır.
    Tahtada gezerken 'bunu beğendim' demek ucuzdur; kuponu kurup parayı
    yatırmak değildir. Sepet ikisinin arasına bir eşik koyar."""
    sp = _sepet()
    O, p = 1.0, 1.0
    for b in sp:
        O *= b["o"]
        p *= (1.0 / b["o"]) / b["m"]
    ev = (p * O - 1.0) if sp else 0.0
    _sayfa_basligi(
        "Sepet",
        "Seçmek ile oynamak farklı kararlardır. Sepet ikisinin arasına "
        "bir eşik koyar: burada tartılır, sonra kaydedilir.",
        [{"ad": "Ayak", "deger": str(len(sp))},
         {"ad": "Toplam oran", "deger": (_num(O) if sp else "—")},
         {"ad": "Beklenen getiri",
          "deger": (("+" if ev >= 0 else "−") + _num(abs(ev) * 100, 1) + "%"
                    if sp else "—"),
          "cls": ("ps" if ev >= 0 else "ng")}])

    sol, sag = st.columns([1.35, 1.0], gap="medium")
    with sol:
        st.markdown("<div class='v2card'><div class='v2head'>"
                    "<h2>Sepetteki Seçimler</h2><div class='hint'>"
                    "çıkarmak için sil</div></div><div class='v2body'>",
                    unsafe_allow_html=True)
        if not sp:
            st.markdown(
                "<div class='v2bos'>Sepet boş.<br>Karar Masası'ndaki "
                "tahtadan seçim ekle.</div>", unsafe_allow_html=True)
        else:
            for b in list(sp):
                c1, c2 = st.columns([5, 1], gap="small")
                with c1:
                    st.markdown(
                        "<div class='v2sepet-satir'><div>"
                        "<div class='ad'>" + str(b["h"]) + " — " +
                        str(b["a"]) + "</div><div class='alt'>" +
                        str(b["ad"]) + " · " + str(b["mk"]) + " · " +
                        str(b["pk"]) + "</div></div>"
                        "<div style='font-family:\"JetBrains Mono\",monospace;"
                        "font-size:17px;font-weight:500;'>" + _num(b["o"]) +
                        "</div></div>", unsafe_allow_html=True)
                with c2:
                    if st.button("Sil", key="v2_sil_" + b["id"],
                                 use_container_width=True):
                        st.session_state["v2_sepet"] = [
                            x for x in sp if x["id"] != b["id"]]
                        st.rerun()
        st.markdown("</div></div>", unsafe_allow_html=True)

    with sag:
        if sp:
            ayni = len({(b["h"], b["a"]) for b in sp}) < len(sp)
            not_ = ("<b>" + str(len(sp)) + " ayak · " + _pct(p) +
                    " tutma şansı.</b> Hiçbir şeyde yanılmadan önce <b>" +
                    _num(abs(ev) * 100, 1) + "%</b> geride başlıyorsun — "
                    "ayakların marjlarının çarpımı.")
            if ayni:
                not_ += (" <b>Uyarı:</b> aynı maçtan birden fazla ayak var; "
                         "bağımsız değiller, gerçek olasılık farklı.")
            if len(sp) >= 3:
                not_ += (" Üç ayakta maliyet, ölçülen en pahalı bölgeyi "
                         "(−%22) geçiyor.")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Tartı</h2>"
                "<div class='hint'>marj canlı</div></div><div class='v2body'>"
                "<div class='ro'><span>Toplam oran</span><b>" + _num(O) +
                "</b></div>"
                "<div class='ro'><span>Gerçek olasılık</span><b>" + _pct(p) +
                "</b></div>"
                "<div class='ro big'><span>Beklenen getiri</span><b class='" +
                ("ps" if ev >= 0 else "ng") + "'>" +
                ("+" if ev >= 0 else "−") + _num(abs(ev) * 100, 1) +
                "%</b></div>"
                "<div class='vd' style='margin-top:var(--s3);'>" + not_ +
                "</div></div></div>", unsafe_allow_html=True)
            st.markdown("<div class='v2card'><div class='v2head'>"
                        "<h2>Gerçekte Oyna</h2><div class='hint'>"
                        "OPUS 5 defterine yazılır</div></div>"
                        "<div class='v2body'>", unsafe_allow_html=True)
            stake = st.number_input("Bahis (₺)", min_value=5.0,
                                    max_value=5000.0, value=50.0, step=5.0,
                                    key="v2_sepet_stake")
            st.markdown(
                "<div class='dq' style='margin:var(--s2) 0;'>Tutarsa <b>" +
                "{:,.0f}".format(stake * O).replace(",", ".") +
                " ₺</b> döner. Bu kayıt kâğıt ile saha arasındaki farkı "
                "ölçmeyi mümkün kılar — iddaa arşivi siliyor.</div>",
                unsafe_allow_html=True)
            if st.button("Oyna ve deftere yaz", type="primary",
                         use_container_width=True, key="v2_oyna"):
                try:
                    import manual_book as mb
                    r = mb.play_custom([b["id"] for b in sp],
                                       stake=float(stake))
                except Exception as e:
                    r = {"ok": False,
                         "msg": "Hata: %s: %s" % (type(e).__name__, e)}
                if r.get("ok"):
                    st.success(r["msg"])
                    st.session_state["v2_sepet"] = []
                    load_opus.clear()
                    st.rerun()
                else:
                    st.error(r.get("msg", "kaydedilemedi"))
            st.markdown("</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Tartı</h2>"
                "<div class='hint'>bekliyor</div></div><div class='v2body'>"
                "<div class='v2bos'>Sepete seçim ekleyince<br>"
                "marj ve beklenen getiri burada hesaplanır.</div>"
                "</div></div>", unsafe_allow_html=True)


def page_lig() -> None:
    """🏆 Lig — mavi ve kırmızı takım, dönem kapsamlı."""
    d = load_lig()
    ham = load_egri_ham()
    kpi = [{"ad": "Mavi takım", "deger": str(len(d["mavi"])) + " ajan"},
           {"ad": "Kırmızı takım", "deger": str(len(d["kirmizi"])) + " ajan"}]
    if ham:
        _t = sum(float(x["pnl"] or 0) for x in ham)
        _c = sum(float(x["stake"] or 0) for x in ham)
        kpi += [
            {"ad": "Net", "deger": ("+" if _t >= 0 else "−") +
             "{:,.0f}".format(abs(_t)).replace(",", ".") + " ₺",
             "cls": ("ps" if _t >= 0 else "ng")},
            {"ad": "ROI", "deger": ("+" if _t >= 0 else "−") +
             _num(abs(_t / _c) * 100, 1) + "%" if _c else "—",
             "cls": ("ps" if _t >= 0 else "ng")}]
    _sayfa_basligi(
        "Ajan Ligi",
        "Yürürlükteki dönem. Sıralama isabete göre değil, fiyata göre "
        "üstünlüğe göre — iki ölçü farklı sıralama verir.", kpi)

    # ── KASA EĞRİSİ · süzgeçli, zaman eksenli
    if ham:
        tum_ajan = sorted({str(x["p"]) for x in ham})
        tum_tur = sorted({str(x["ct"] or "?") for x in ham})
        f1, f2 = st.columns([1.0, 1.0], gap="small")
        with f1:
            sec_ajan = st.multiselect(
                "Ajan", tum_ajan, default=[], key="v2_eg_ajan",
                placeholder="tümü",
                help="Boş bırakırsan hepsi. Eğri süzgeçten SONRA yeniden "
                     "hesaplanır — önceden toplanmış seri süzülemez.")
        with f2:
            sec_tur = st.multiselect(
                "Oyun türü", tum_tur, default=[], key="v2_eg_tur",
                placeholder="tümü",
                help="Kupon türü: tek, kombine, sistem…")
        sz = [x for x in ham
              if (not sec_ajan or str(x["p"]) in sec_ajan)
              and (not sec_tur or str(x["ct"] or "?") in sec_tur)]
        kum, tepe, dus, nokta, ciro = 0.0, 0.0, 0.0, [], 0.0
        for x in sz:
            try:
                kum += float(x["pnl"] or 0)
                ciro += float(x["stake"] or 0)
            except Exception:
                continue
            tepe = max(tepe, kum)
            dus = min(dus, kum - tepe)
            nokta.append({"t": str(x["sa"])[:10], "k": kum})
        etiket = ("tümü" if not (sec_ajan or sec_tur)
                  else " · ".join(sec_ajan + sec_tur)[:60])
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Kasa Eğrisi</h2>"
            "<div class='hint'>" + etiket + " · " + str(len(sz)) +
            " kupon</div></div><div class='v2body'>" +
            _svg_zaman(nokta) +
            ("<div style='display:flex;gap:var(--s5);flex-wrap:wrap;"
             "margin-top:var(--s3);border-top:1px solid var(--line);"
             "padding-top:var(--s3);'>"
             "<div class='v2kpi'><span>Net</span><b class='" +
             ("ps" if kum >= 0 else "ng") + "'>" +
             ("+" if kum >= 0 else "−") +
             "{:,.0f}".format(abs(kum)).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>Ciro</span><b>" +
             "{:,.0f}".format(ciro).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>ROI</span><b class='" +
             ("ps" if kum >= 0 else "ng") + "'>" +
             (("+" if kum >= 0 else "−") + _num(abs(kum / ciro) * 100, 1) + "%"
              if ciro else "—") + "</b></div>"
             "<div class='v2kpi'><span>En büyük düşüş</span><b class='ng'>−" +
             "{:,.0f}".format(abs(dus)).replace(",", ".") + " ₺</b></div>"
             "<div class='v2kpi'><span>Tepe</span><b>" +
             "{:,.0f}".format(tepe).replace(",", ".") + " ₺</b></div></div>"
             if nokta else "") +
            "</div></div>", unsafe_allow_html=True)

    st.markdown(
        "<div class='v2mb'><b>Sıralama isabete göre değil, fiyata göre "
        "üstünlüğe göre.</b> İki ölçü farklı sıralama veriyor ve doğrusu "
        "bu — %75 isabet oran 1,24'te kötüdür. Rakamlar <b>yürürlükteki "
        "dönemi</b> kapsar; arşivlenen dönem karneye karışmaz.</div>",
        unsafe_allow_html=True)
    ae = load_ajan_egri()
    st.markdown(_takim_tablo(d["mavi"], "Mavi Takım",
                             "sinyal motoru · " + str(len(d["mavi"])) + " ajan",
                             "#2563a8", ae), unsafe_allow_html=True)
    st.markdown(_takim_tablo(d["kirmizi"], "Kırmızı Takım",
                             "kombo pazarları · " + str(len(d["kirmizi"])) + " ajan",
                             "#a82f22", ae), unsafe_allow_html=True)
    # ── ajan dosyasına iniş: liste + panel (ayrı sayfa değil)
    tum = d["mavi"] + d["kirmizi"]
    if "v2_ajan" not in st.session_state:
        st.session_state["v2_ajan"] = None
    secenek = ["— ajan seç —"] + [x["ad"] for x in tum]
    simdi = st.session_state["v2_ajan"]
    idx = 0
    if simdi:
        ad_simdi = next((x["ad"] for x in tum if x["pid"] == simdi), None)
        if ad_simdi in secenek:
            idx = secenek.index(ad_simdi)
    sec = st.selectbox("Ajan dosyası aç", secenek, index=idx,
                       key="v2_ajan_sec",
                       help="Ajanın seyri, açık pozisyonları, gerekçeleri "
                            "ve teşhisi — ligden çıkmadan.")
    yeni = next((x["pid"] for x in tum if x["ad"] == sec), None)
    if yeni != st.session_state["v2_ajan"]:
        st.session_state["v2_ajan"] = yeni
        st.rerun()
    if st.session_state["v2_ajan"]:
        _ajan_paneli(st.session_state["v2_ajan"], d)

    st.markdown(
        "<div class='dq'>Kırmızı takımın sessizliği <b>arıza değil</b>: "
        "ölçüldü, iddaa kombo pazarlarında korelasyonu doğru fiyatlıyor "
        "(1X2_OU +%0,1 · 1X2_BTTS −%0,3 · OU_BTTS −%1,2) ve marj %19-20. "
        "Sürekli skor modeli sahte edge üretmiyor — 450 adaydan 0'ı eşiği "
        "geçiyor. <i>Faz 2 · model</i></div>", unsafe_allow_html=True)


def page_defter() -> None:
    """📓 Ölçüm Defteri — her bulgunun ön kayıtlı kurala karşı hükmü."""
    rows = load_defter()
    if rows:
        _g = sum(1 for r in rows if r["gecti"])
        _c = load_clv()
        _k = [{"ad": "Kural sağlayan", "deger": str(_g) + "/" + str(len(rows)),
               "cls": ("ps" if _g * 2 >= len(rows) else "ng")}]
        if _c.get("n", 0) >= 50:
            _k.append({"ad": "CLV",
                       "deger": ("+" if _c["ort"] >= 0 else "−") +
                       _num(abs(_c["ort"]) * 100, 2) + "%",
                       "cls": ("ps" if _c["t"] > 1.96 else "ng")})
        _sayfa_basligi(
            "Ölçüm Defteri",
            "Her bulgunun ön kayıtlı kurala karşı hükmü. Kural sonuç "
            "görülmeden yazıldı ki sonradan esnetilemesin.", _k)
    if not rows:
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Ölçüm Defteri</h2>"
            "<div class='hint'>henüz koşmadı</div></div><div class='v2body'>"
            "<div class='dq'>Defter henüz koşmadı. Worker her gün 04:20'de "
            "hafif ölçümleri, pazartesi 03:10'da tam takımı koşar. Elle: "
            "<code>python 02_VERI/olcum_defteri.py</code></div></div></div>",
            unsafe_allow_html=True)
        return
    gecen = sum(1 for r in rows if r["gecti"])
    body = []
    for r in rows:
        g = "g1" if r["gecti"] else "g3"
        txt = "KURAL SAĞLANDI" if r["gecti"] else "sağlanmadı"
        tr = ""
        if r["trend"] is not None and abs(r["trend"]) > 1e-9:
            cls = "dp" if r["trend"] > 0 else "dm"
            tr = ("<span class='" + cls + "' style='font-size:10px;'>" +
                  ("+" if r["trend"] > 0 else "−") +
                  _num(abs(r["trend"]), 3) + "</span>")
        dg = ("<span class='gr g2'>🔔 " + str(r["degisim"]) + " KEZ DÖNDÜ</span>"
              if r["degisim"] else "")
        body.append(
            "<tr><td><span class='ag'>" + r["id"] + "</span>" + dg +
            "<span class='sb'>" + str(r["detay"] or "")[:96] + "</span></td>"
            "<td class='r n opt'>" + "{:,}".format(r["n"]).replace(",", ".") + "</td>"
            "<td class='r n'>" + _num(r["v"], 3) + " " + tr + "</td>"
            "<td class='r n opt'>" + str(r["kosu"]) + "</td>"
            "<td class='r'><span class='gr " + g + "'>" + txt + "</span></td></tr>")
    st.markdown(
        "<div class='v2card'><div class='v2head'><h2>Ölçüm Defteri</h2>"
        "<div class='hint'>" + str(gecen) + "/" + str(len(rows)) +
        " kural sağlıyor</div></div><div class='v2body'>"
        "<div class='v2mb'><b>Kurallar sonuç görülmeden yazıldı</b> ki "
        "sonradan esnetilemesin. 'Sağlanmadı' bir arıza değil, bir "
        "<b>hükümdür</b> — konsept o kadar. Bir bulgunun çürümesi de "
        "güçlenmesi de karar gerektirir.</div>"
        "<table class='v2'><thead><tr><th>Ölçüm</th><th class='r opt'>n</th>"
        "<th class='r'>Değer</th><th class='r opt'>Koşu</th>"
        "<th class='r'>Hüküm</th></tr></thead><tbody>" +
        "".join(body) + "</tbody></table></div></div>", unsafe_allow_html=True)

    sol, sag = st.columns([1.0, 1.0], gap="small")

    # ── CLV: V1'in ayri sayfasi, artik olcum katmaninin icinde
    with sol:
        c = load_clv()
        if c.get("n", 0) < 50:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>CLV</h2>"
                "<div class='hint'>kapanış çizgisi</div></div>"
                "<div class='v2body'><div class='dq'>Yeterli CLV kaydı yok."
                "</div></div></div>", unsafe_allow_html=True)
        else:
            iyi = c["t"] > 1.96
            sat = []
            for x in c["pazar"]:
                cls = "dp" if x["ort"] > 0.002 else "dm"
                sat.append("<tr><td><span class='ag'>" + x["ad"][:14] +
                           "</span></td><td class='r n opt'>" + str(x["n"]) +
                           "</td><td class='r'><span class='" + cls + "'>" +
                           ("+" if x["ort"] >= 0 else "−") +
                           _num(abs(x["ort"]) * 100, 2) + "%</span></td>"
                           "<td class='r n'>" + _pct(x["beat"]) + "</td></tr>")
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>CLV · Kapanış Çizgisi</h2>"
                "<div class='hint'>öncü gösterge</div></div><div class='v2body'>"
                "<div class='v2mb'>Girdiğin fiyat kapanıştan iyiyse piyasadan "
                "<b>önce</b> doğru tarafı görmüşsün demektir — sonuçtan "
                "bağımsız. Ama tek başına marjı yenmez: %17,6'yı aşmak için "
                "+%17,6 CLV gerekir.</div>"
                "<div class='ro'><span>Ortalama CLV</span><b class='" +
                ("ps" if iyi else "ng") + "'>" +
                ("+" if c["ort"] >= 0 else "−") + _num(abs(c["ort"]) * 100, 2) +
                "%</b></div>"
                "<div class='ro'><span>t değeri</span><b class='" +
                ("ps" if iyi else "ng") + "'>" + _num(c["t"], 2) + "</b></div>"
                "<div class='ro'><span>Kapanışı geçen</span><b>" +
                _pct(c["beat"]) + "</b></div>"
                "<div class='ro'><span>Hiç oynamayan</span><b>" +
                _pct(c["sifir"]) + "</b></div>"
                "<table class='v2' style='margin-top:12px;'><thead><tr>"
                "<th>Pazar</th><th class='r opt'>n</th><th class='r'>CLV</th>"
                "<th class='r'>Geçen</th></tr></thead><tbody>" +
                "".join(sat) + "</tbody></table></div></div>",
                unsafe_allow_html=True)

    # ── MIHENK: arsivi OKU, yeniden uretme
    with sag:
        mh = load_mihenk()
        if not mh.get("var"):
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Mihenk</h2>"
                "<div class='hint'>yönetici özeti</div></div>"
                "<div class='v2body'><div class='dq'>Henüz arşivlenmiş rapor "
                "yok. Üretim: <code>python 02_VERI/exec_report.py</code>"
                "</div></div></div>", unsafe_allow_html=True)
        else:
            p = mh["payload"]
            bul = p.get("findings") or p.get("bulgular") or []
            kap = p.get("gates") or []
            ic = ""
            if bul:
                ic += ("<div class='v2mb'><b>Bulgular</b><br>" +
                       "<br>".join("· " + str(b)[:150] for b in bul[:6]) +
                       "</div>")
            if kap:
                sat = []
                for gt in kap[:6]:
                    ad = str(gt.get("name") or gt.get("ad") or "?")[:30]
                    ok = bool(gt.get("ok") or gt.get("passed"))
                    sat.append("<tr><td><span class='ag'>" + ad + "</span></td>"
                               "<td class='r'><span class='gr " +
                               ("g1" if ok else "g3") + "'>" +
                               ("GEÇTİ" if ok else "geçmedi") +
                               "</span></td></tr>")
                ic += ("<table class='v2'><thead><tr><th>Gerçek para kapısı</th>"
                       "<th class='r'>Durum</th></tr></thead><tbody>" +
                       "".join(sat) + "</tbody></table>")
            if not ic:
                ic = ("<div class='dq'>Rapor #" + str(mh["no"]) +
                      " arşivde ama okunabilir bulgu alanı yok.</div>")
            gec = " · ".join("#" + str(g["no"]) for g in mh["gecmis"])
            st.markdown(
                "<div class='v2card'><div class='v2head'>"
                "<h2>Mihenk · Rapor #" + str(mh["no"]) + "</h2>"
                "<div class='hint'>" + mh["ts"] + "</div></div>"
                "<div class='v2body'>" + ic +
                "<div class='dq' style='margin:10px 0 0;'>Arşiv: " + gec +
                " · rapor <b>üretimi</b> exec_report.py'de kalır, burası "
                "okuma yüzeyidir. Bir işin iki yerde yapılması V1'in en "
                "büyük hatasıydı.</div></div></div>", unsafe_allow_html=True)


def page_sistem() -> None:
    """🩺 Sistem — sessizlik meşru mu, arıza mı?"""
    d = load_sistem()
    sy = d["sistem"]
    _durum = str(sy["status"]) if sy else "—"
    _bos = sum(1 for f in d["alan"] if f["pay"] < 0.5)
    _sayfa_basligi(
        "Sistem Sağlığı",
        "Bir ajanın oynamaması meşru PAS da olabilir tıkanıklık da — "
        "ikisini karıştırmak haftalar sürer.",
        [{"ad": "Veri hattı", "deger": _durum.split(" ")[-1][:14],
          "cls": ("ng" if "TIKANIKLIK" in _durum else "ps")},
         {"ad": "Zayıf alan", "deger": str(_bos) + " / " + str(len(d["alan"])),
          "cls": ("ng" if _bos else "ps")}])
    if sy:
        kirik = "TIKANIKLIK" in str(sy["status"])
        st.markdown(
            "<div class='" + ("dq" if kirik else "v2mb") + "'>"
            "<b>" + str(sy["status"]) + "</b> — " + str(sy["detail"] or "") +
            "<br><span style='font-size:10.5px;opacity:.75;'>son teşhis " +
            str(sy["ts"])[:16] + "</span></div>", unsafe_allow_html=True)

    sek = _sekmeler("sistem", ["Teşhis", "Veri", "Risk"])

    if sek == "Teşhis":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> bir ajan neden oynamıyor — "
            "<b>meşru PAS</b> mı (eşiği geçen aday yok) yoksa <b>tıkanıklık</b> "
            "mı (kod/veri kırık)? İkisini karıştırmak haftalar sürer. En üstteki "
            "SİSTEM satırı veri hattını bekler: fetch çökerse tüm ajanlar masum "
            "sessizlik gibi görünür.</div>", unsafe_allow_html=True)
    elif sek == "Veri":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> hangi analiz <b>yapılamıyor</b>? "
            "Boş sütun, yapılamayan analiz demektir. Doluluk tek başına yetmez: "
            "26.000 satırın %90'ı dolu ama hepsi iki yıl önceden ise sistem "
            "kördür. Üç soru ayrı sorulur — ne kadar var, ne kadarı dolu, ne "
            "kadarı taze.</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> hangi ajan sözleşmesini "
            "zorluyor? Prop-firm mantığı: her ajanın kendi kasası, tabanı ve "
            "sözleşmesi var. Taban altına düşen koruma moduna girer, iki ihtar "
            "kadro dışı demektir. <b>Sistemin ajanı susturması arıza değil, "
            "sözleşmenin işlemesidir.</b></div>", unsafe_allow_html=True)

    if sek != "Teşhis":
        left, right = st.container(), st.container()
    else:
        left, right = st.columns([1.25, 1.0], gap="small")

    with left:
        body = []
        for a in d["ajan"]:
            t = str(a["status"] or "")
            if "TIKANIKLIK" in t:
                g = "g3"
            elif "🟠" in t or "MONTAJ" in t:
                g = "g2"
            elif "🟢" in t:
                g = "g1"
            else:
                g = "g2"
            pid = str(a["pid"])
            body.append(
                "<tr><td><span class='ag'>" + _rozet(pid) +
                pid.rsplit("_", 1)[0] + "</span>"
                "<span class='sb'>" + str(a["detail"] or "")[:88] + "</span></td>"
                "<td class='r'><span class='gr " + g + "'>" +
                t.replace("🔴 ", "").replace("🟠 ", "").replace("🟢 ", "")
                 .replace("⚪ ", "").replace("😴 ", "").replace("🧊 ", "")
                 .replace("⏸ ", "").replace("🔒 ", "").replace("🏁 ", "")
                 .replace("🛑 ", "").replace("🚫 ", "") + "</span></td></tr>")
        if sek != "Teşhis":
            body = []
        st.markdown(
            ("" if sek != "Teşhis" else
             "<div class='v2card'><div class='v2head'><h2>Ajan Teşhisi</h2>"
            "<div class='hint'>günlük · sorunlu üstte</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Bir ajanın oynamaması iki ayrı şey olabilir: "
            "<b>meşru PAS</b> (eşiği geçen aday yok) ya da <b>tıkanıklık</b> "
            "(kod/veri kırık). İkisini karıştırmak haftalar sürebilir — "
            "bu yüzden sebep her gün kayda geçer.</div>"
            "<table class='v2'><thead><tr><th>Ajan</th>"
            "<th class='r'>Durum</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>"),
            unsafe_allow_html=True)

    with right:
        if sek != "Veri":
            st.markdown("", unsafe_allow_html=True)
        body = []
        for f in d["alan"]:
            p = f["pay"]
            if p >= 0.90:
                g, txt = "g1", "TAM"
            elif p >= 0.50:
                g, txt = "g2", "KISMÎ"
            elif p > 0:
                g, txt = "g3", "ZAYIF"
            else:
                g, txt = "g3", "BOŞ"
            bar = int(round(p * 100))
            body.append(
                "<tr><td><span class='ag'>" + f["ad"] + "</span>"
                "<span class='sb'>" + f["neden"] + "</span>"
                "<div style='height:3px;background:var(--line);margin-top:5px;'>"
                "<i style='display:block;height:3px;width:" + str(bar) + "%;"
                "background:" + ("var(--pos)" if p >= 0.5 else "var(--neg)") +
                ";'></i></div></td>"
                "<td class='r n'>" + "{:,}".format(f["n"]).replace(",", ".") +
                "</td>"
                "<td class='r'><span class='gr " + g + "'>" +
                "{:.0f}".format(p * 100) + "% " + txt + "</span></td></tr>")
        st.markdown(
            ("" if sek != "Veri" else
             "<div class='v2card'><div class='v2head'><h2>Veri Doluluğu</h2>"
            "<div class='hint'>yol haritası · faz 1</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Boş sütun, yapılamayan analiz demektir. "
            "<b>İlk yarı skoru</b> hiç yok — oysa iddaa'nın çıpa pazarları "
            "golün <b>ne zaman</b> atıldığını belirlemiyor; kitabın en az "
            "güvendiği yer orası (HT_FT marjı %25,8).</div>"
            "<table class='v2'><thead><tr><th>Alan</th><th class='r'>Dolu</th>"
            "<th class='r'>Oran</th></tr></thead><tbody>" +
            "".join(body) + "</tbody></table></div></div>"),
            unsafe_allow_html=True)

    vo = load_veri_ozet() if sek == "Veri" else {}
    if vo.get("toplam"):
        tsat = "".join(
            "<tr><td><span class='ag'>" + x["ad"] + "</span>"
            "<span class='sb'>" + x["tb"] + "</span></td>"
            "<td class='r n'>" + "{:,}".format(x["n"]).replace(",", ".") +
            "</td></tr>" for x in vo["tablolar"])
        ksat = "".join(
            "<tr><td><span class='ag'>" + str(k["k"] or "?") + "</span>"
            "<span class='sb'>" + str(k["ilk"]) + " → " + str(k["son"]) +
            "</span></td><td class='r n'>" +
            "{:,}".format(int(k["n"])).replace(",", ".") + "</td></tr>"
            for k in vo["kaynak"])
        s1, s2 = st.columns([1.0, 1.0], gap="small")
        with s1:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Veri Özeti</h2>"
                "<div class='hint'>sistemin hafızası</div></div>"
                "<div class='v2body'>"
                "<div class='ro'><span>Toplam maç</span><b>" +
                "{:,}".format(vo["toplam"]).replace(",", ".") + "</b></div>"
                "<div class='ro'><span>Sonuçlanmış</span><b>" +
                "{:,}".format(vo["sonuclanmis"]).replace(",", ".") + "</b></div>"
                "<div class='ro'><span>Yaklaşan</span><b>" +
                str(vo["yaklasan"]) + "</b></div>"
                "<div class='ro'><span>Son tazeleme</span><b style='font-size:14px;'>" +
                str(vo["tazelik"] or "—") + "</b></div>"
                "<table class='v2' style='margin-top:var(--s3);'><thead><tr>"
                "<th>Tablo</th><th class='r'>Satır</th></tr></thead><tbody>" +
                tsat + "</tbody></table></div></div>", unsafe_allow_html=True)
        with s2:
            st.markdown(
                "<div class='v2card'><div class='v2head'><h2>Fiyat Kaynağı</h2>"
                "<div class='hint'>kapsam ve dönem</div></div>"
                "<div class='v2body'>"
                "<div class='v2mb'>Hangi fiyattan ölçtüğün, ne ölçtüğünü "
                "belirler. Pinnacle marjı ~%3, iddaa ~%17,6 — aynı modeli "
                "iki kaynakta sınamak <b>iki farklı sonuç</b> verir. "
                "Kaynakların <b>çakışmadığına</b> dikkat et.</div>"
                "<table class='v2'><thead><tr><th>Kaynak · dönem</th>"
                "<th class='r'>Maç</th></tr></thead><tbody>" + ksat +
                "</tbody></table></div></div>", unsafe_allow_html=True)

    rk = load_risk() if sek == "Risk" else []
    if rk:
        sat = []
        for x in rk:
            if x["p"] in ("PAPER_V1",):
                continue
            kc = "dp" if x["oran"] >= 1.0 else "dm"
            sat.append(
                "<tr><td><span class='ag'>" + _rozet(x["p"]) + x["ad"] +
                "</span><span class='sb'>dönem " + str(x["era"] or "—") +
                " · başlangıç " + "{:,.0f}".format(x["ib"]).replace(",", ".") +
                " ₺</span></td>"
                "<td class='r n'>" + "{:,.0f}".format(x["cb"]).replace(",", ".") +
                " ₺</td>"
                "<td class='r'><span class='" + kc + "'>" +
                "{:.0f}".format(x["oran"] * 100) + "%</span></td>"
                "<td class='r n opt'>" +
                ("−" + _num(abs(x["dusus"]) * 100, 0) + "%"
                 if x["dusus"] < 0 else "—") + "</td>"
                "<td class='r'><span class='gr " + x["sev"] + "'>" +
                x["dur"] + "</span></td></tr>")
        st.markdown(
            "<div class='v2card'><div class='v2head'><h2>Risk ve Sözleşme</h2>"
            "<div class='hint'>prop-firm mantığı</div></div>"
            "<div class='v2body'>"
            "<div class='v2mb'>Her ajanın <b>kendi kasası ve kendi "
            "sözleşmesi</b> var. Taban altına düşen koruma moduna girer, "
            "iki ihtar kadro dışı demektir. Sistemin ajanı susturması "
            "bir arıza değil, sözleşmenin işlemesidir.</div>"
            "<table class='v2'><thead><tr><th>Ajan</th><th class='r'>Kasa</th>"
            "<th class='r'>%</th><th class='r opt'>Tepeden</th>"
            "<th class='r'>Durum</th></tr></thead><tbody>" +
            "".join(sat) + "</tbody></table></div></div>",
            unsafe_allow_html=True)


def _mini(baslik, ipucu, basliklar, satirlar):
    if not satirlar:
        return ("<div class='v2card'><div class='v2head'><h2>" + baslik +
                "</h2><div class='hint'>" + ipucu + "</div></div>"
                "<div class='v2body'><div class='dq'>Yeterli örneklem yok."
                "</div></div></div>")
    th = "".join("<th class='r'>" + h + "</th>" if i else "<th>" + h + "</th>"
                 for i, h in enumerate(basliklar))
    tb = "".join("<tr>" + "".join(
        ("<td>" + c + "</td>") if i == 0 else ("<td class='r'>" + c + "</td>")
        for i, c in enumerate(r)) + "</tr>" for r in satirlar)
    return ("<div class='v2card'><div class='v2head'><h2>" + baslik + "</h2>"
            "<div class='hint'>" + ipucu + "</div></div><div class='v2body'>"
            "<table class='v2'><thead><tr>" + th + "</tr></thead><tbody>" +
            tb + "</tbody></table></div></div>")


def page_inceleme() -> None:
    """İnceleme — kazanan/kaybeden ayrıştırması, dört ayrı soruda.

    Tek sayfada dört tabloyu üst üste yığmak 'kompakt' değil OKUNMAZ
    yapar. Her sekme TEK bir karara hizmet eder ve hangisi olduğunu
    kendi yazar."""
    d = load_inceleme()
    if not d.get("n"):
        _sayfa_basligi("İnceleme", "Dönem içinde kapanmış bahis yok.", [])
        st.markdown("<div class='v2bos'>Veri birikince burası dolacak.</div>",
                    unsafe_allow_html=True)
        return
    g = d["genel"]
    _sayfa_basligi(
        "İnceleme",
        "Kayıp modelden mi, pazardan mı, veriden mi geliyor — üçü ayrılır.",
        [{"ad": "Kapanmış bahis", "deger": str(g["n"])},
         {"ad": "İsabet", "deger": _pct(g["hit"])},
         {"ad": "Getiri", "deger": ("+" if g["roi"] >= 0 else "−") +
          _num(abs(g["roi"]) * 100, 1) + "%",
          "cls": ("ps" if g["roi"] >= 0 else "ng")}])

    sek = _sekmeler("inceleme",
                    ["Model", "Trade", "Kayıp Anatomisi", "Gerekçe Defteri"])

    if sek == "Model":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> modelin ürettiği olasılığa "
            "güvenilir mi? Kalibrasyon <i>“model %X dediğinde gerçekten %X mi "
            "oluyor”</i>u, edge geçerliliği <i>“yüksek edge gerçekten daha iyi "
            "mi”</i>yi sorar. İkisi de hayır derse sorun modeldedir; evet derse "
            "kaybı başka yerde aramak gerekir.</div>", unsafe_allow_html=True)
        kr = []
        for k in d["kal"]:
            if k.get("n", 0) < 5:
                kr.append([k["ad"], str(k.get("n", 0)), "—", "—", "—"])
                continue
            f = k["fark"]
            kr.append([k["ad"], str(k["n"]), _pct(k["tah"]), _pct(k["ger"]),
                       "<span class='" + ("dp" if abs(f) <= 0.05 else "dm") +
                       "'>" + _sgn(f) + "</span>"])
        er = []
        for e in d["eb"]:
            er.append([e["ad"], str(e["n"]), _sgn(e["e"]),
                       "<span class='" + ("dp" if e["roi"] >= 0 else "dm") +
                       "'>" + ("+" if e["roi"] >= 0 else "−") +
                       _num(abs(e["roi"]) * 100, 1) + "%</span>"])
        c1, c2 = st.columns([1, 1], gap="medium")
        with c1:
            st.markdown(_mini("Kalibrasyon",
                              "model %X dediğinde gerçekten %X mi oluyor",
                              ["Model bandı", "n", "Tahmin", "Gerçek", "Fark"],
                              kr), unsafe_allow_html=True)
        with c2:
            st.markdown(_mini("Edge geçerliliği",
                              "yüksek edge gerçekten daha iyi mi",
                              ["Dilim", "n", "Ort. edge", "Getiri"], er),
                        unsafe_allow_html=True)

    elif sek == "Trade":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> doğru olasılıkla yanlış yerde mi "
            "oynuyoruz? Aynı model farklı pazarda ve farklı kupon türünde "
            "farklı sonuç verir — çünkü <b>marj her yerde aynı değil</b>. Bu "
            "tablolar nereden çıkılacağını söyler.</div>",
            unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1, 1], gap="medium")
        for kol, (bas, anh, ip) in zip(
                (c1, c2, c3),
                (("Pazar", "pazar", "hangi pazarda iyiyiz"),
                 ("Kupon türü", "tur", "tek mi kombine mi"),
                 ("Lig", "lig", "nerede oynuyoruz"))):
            sat = []
            for x in d[anh]:
                sat.append([str(x["ad"])[:16], str(x["n"]), _pct(x["hit"]),
                            "<span class='" +
                            ("dp" if x["roi"] >= 0 else "dm") + "'>" +
                            ("+" if x["roi"] >= 0 else "−") +
                            _num(abs(x["roi"]) * 100, 1) + "%</span>"])
            with kol:
                st.markdown(_mini(bas, ip, ["", "n", "İsabet", "Getiri"], sat),
                            unsafe_allow_html=True)

    elif sek == "Kayıp Anatomisi":
        st.markdown(
            "<div class='v2mb'><b>Karar:</b> kombine kaybettiğinde hangi ayak "
            "düşürdü? Zayıf halka belliyse o ayağı kupondan çıkarmak "
            "<b>ölçülebilir</b> bir iyileştirmedir. Tarihsel evrende altı "
            "hücrenin altısında zayıf halka <b>sonuç (1X2) ayağıydı</b> — "
            "kaybın yarısı gol ayağı tuttuğu hâlde geliyordu.</div>",
            unsafe_allow_html=True)
        a = d["anat"]
        if a["n"] >= 5:
            top = a["n"]
            sat = [[ad, str(a[k]), _pct(a[k] / top)]
                   for k, ad in (("sonuc", "Sonuç ayağı düşürdü"),
                                 ("gol", "Gol/KG ayağı düşürdü"),
                                 ("iki", "İkisi birden"))]
            zayif = "SONUÇ (1X2)" if a["sonuc"] >= a["gol"] else "GOL/KG"
            c1, c2 = st.columns([1, 1], gap="medium")
            with c1:
                st.markdown(
                    _mini("Hangi ayak düşürdü", str(top) + " kombine kaybı",
                          ["Ayak", "n", "Pay"], sat), unsafe_allow_html=True)
            with c2:
                st.markdown(
                    "<div class='v2card'><div class='v2head'><h2>Hüküm</h2>"
                    "<div class='hint'>zayıf halka</div></div>"
                    "<div class='v2body'><div class='ro big'>"
                    "<span>Zayıf halka</span><b class='ng'>" + zayif +
                    "</b></div><div class='vd' style='margin-top:var(--s3);'>"
                    "Bu ayak kupondan çıkarılırsa kayıpların <b>" +
                    _pct(max(a["sonuc"], a["gol"]) / top) + "</b>'i "
                    "önlenebilirdi — diğer ayak zaten tutmuştu.</div>"
                    "</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='v2bos'>Karşı-olgusal için en az 5 kombine kaybı "
                "gerekiyor — şu an " + str(a["n"]) + ".</div>",
                unsafe_allow_html=True)

    else:
        st.markdown(
            "<div class='v2mb'><b>Karar yok — burası hafıza.</b> Her bahsin "
            "<b>neden</b> seçildiği ve sonra <b>ne kadar yaklaştığı</b>. Kupon "
            "sonucu ikilidir (tuttu/tutmadı) ama bilgi süreklidir: “bir gol "
            "eksik” ile “3-0 ıska” aynı şey değildir.</div>",
            unsafe_allow_html=True)
        if d["defter"]:
            sat = []
            for x in d["defter"]:
                sat.append(
                    ["<span class='ag'>" + _rozet(x["p"]) +
                     str(x["h"])[:15] + " — " + str(x["a"])[:15] + "</span>"
                     "<span class='sb'>" + str(x["rsn"] or "—")[:120] +
                     "</span>",
                     "<span class='" + ("dp" if x["won"] else "dm") + "'>" +
                     str(x["pk"])[:16] + "</span>",
                     "<span class='sb'>" + str(x["pm"] or "—")[:70] +
                     "</span>"])
            st.markdown(
                _mini("Gerekçe Defteri", "neden seçildi · ne kadar yaklaştı",
                      ["Maç ve gerekçe", "Seçim", "Sonra ne oldu"], sat),
                unsafe_allow_html=True)
        else:
            st.markdown("<div class='v2bos'>Gerekçe kaydı yok.</div>",
                        unsafe_allow_html=True)

# Menü etiketleri sade: aktif durumdaki amber şerit zaten yönlendiriyor,
# emoji sadece gürültü ekliyordu.
# ── BİLGİ MİMARİSİ ──────────────────────────────────────────
# Menü üç işe göre bölündü. Düz liste, yedi maddeden sonra
# "hangisi neydi" sorusunu doğurur; grup o soruyu kaldırır.
# OPUS 5 artık Lig'in ALTINDA: ikisi de "kim ne yaptı" sorusuna
# bakar, biri kâğıt ajanlara biri sahaya.
GRUPLAR = [
    ("Karar", [("Karar Masası", page_desk), ("Sepet", page_sepet)]),
    ("Takip", [("Ajan Ligi", page_lig), ("OPUS 5", page_opus, True),
               ("İnceleme", page_inceleme)]),
    ("Sistem", [("Ölçüm Defteri", page_defter), ("Sağlık", page_sistem)]),
]
PAGES = {}
for _g, _ler in GRUPLAR:
    for _x in _ler:
        PAGES[_x[0]] = _x[1]


def main() -> None:
    st.markdown(V2_CSS, unsafe_allow_html=True)
    if "v2_page" not in st.session_state:
        st.session_state["v2_page"] = "Karar Masası"

    with st.sidebar:
        st.markdown(
            "<div class='v2brand'><div class='mark'>BA</div>"
            "<div class='yazi'><b>BetAgents</b>"
            "<span>Desk · v2</span></div></div>", unsafe_allow_html=True)
        # ⚠️ ACIK KEY: Streamlit widget kimligini etiket + parametrelerden
        # turetir; `type` her cizimde degistigi icin kimlik kayardi.
        _i = 0
        for grup, ogeler in GRUPLAR:
            st.markdown("<div class='v2grup'>" + grup + "</div>",
                        unsafe_allow_html=True)
            for oge in ogeler:
                ad = oge[0]
                sp = _sepet()
                etiket = ad
                if ad == "Sepet" and sp:
                    etiket = ad + "  (" + str(len(sp)) + ")"
                if st.button(etiket, key=f"v2nav_{_i}",
                             use_container_width=True,
                             type=("primary"
                                   if st.session_state["v2_page"] == ad
                                   else "secondary")):
                    st.session_state["v2_page"] = ad
                    st.session_state["v2_ajan"] = None
                    st.rerun()
                _i += 1
        r = load_rail()
        yerel = r["kaynak"].startswith("SQLite")
        st.markdown(
            "<div class='v2yan-alt'>"
            "KAYNAK<br><b class='" + ("uyari" if yerel else "") + "'>" +
            r["kaynak"] + "</b><br><br>"
            "AÇIK POZİSYON<br><b>" + str(r["acik"]) + "</b><br><br>"
            "KAPANMIŞ BAHİS<br><b>" +
            "{:,}".format(r["kapali"]).replace(",", ".") + "</b>"
            "</div>", unsafe_allow_html=True)

    PAGES[st.session_state["v2_page"]]()
    _gezinme_alt()


if __name__ == "__main__":
    main()
