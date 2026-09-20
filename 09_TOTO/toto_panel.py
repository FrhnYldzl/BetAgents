"""
TOTO · PANEL SAYFALARI — BetAgents Desk içinde AYRI bölüm ("SÜPER TOTO")
======================================================================
app_v2.py yalnız gezinmeye bu sayfaları ekler; çizim burada. Veri yalnız
`toto_*` tablolarından ve 09_TOTO dosyalarından okunur. Bir hata olursa yalnız
Toto sayfası hata gösterir — BetAgents sayfaları etkilenmez (app_v2 sarmalar).

  bu_hafta      Bu hafta ne oynayalım, neden? (kupon · gerekçe · takvim · hatırlatıcı)
  ajan_pazari   Hangi ajanın sesi ne kadar, neden?
  gecmis_test   Bu sistemle geçmişte oynasaydık ne olurdu?
  arsiv         Geçen haftalar: ne oynadık, ne oldu, ne öğrendik?
"""
from __future__ import annotations

import html
import itertools
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

import numpy as np  # noqa: E402
import streamlit as st  # noqa: E402

import toto_db  # noqa: E402

TR = timezone(timedelta(hours=3))
SEC = ("1", "0", "2")
AYLAR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
GUNLER = ["Pzt", "Sal", "Çar", "Per", "Cum", "Cmt", "Paz"]

CSS = """<style>
.tt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--s3);}
.tt-kutu{border:1px solid var(--line);border-radius:var(--r);padding:12px 14px;background:var(--panel-2);}
.tt-kutu .et{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;color:var(--muted);font-weight:var(--w-etiket);}
.tt-kutu .dg{font-family:'JetBrains Mono',monospace;font-size:var(--t-okuma);color:var(--ink);margin-top:4px;}
.tt-kutu .al{font-size:var(--t-alt);color:var(--muted);margin-top:2px;line-height:1.45;}
table.v2 td.tt-i{text-align:center;font-family:'JetBrains Mono',monospace;font-weight:700;width:34px;}
table.v2 td.tt-on{background:var(--brand-fill);color:var(--brand);}
table.v2 td.tt-off{color:var(--line-2);}
.tt-cizgi{height:6px;border-radius:3px;background:var(--panel-3);position:relative;overflow:hidden;}
.tt-cizgi b{position:absolute;left:0;top:0;bottom:0;background:var(--brand);}
.tt-not{font-size:var(--t-alt);color:var(--ink-2);line-height:1.55;}
.tt-uyari{border-left:3px solid var(--brand);padding:8px 12px;background:var(--brand-fill);
  font-size:var(--t-alt);color:var(--ink);line-height:1.5;margin:8px 0;}
table.v2 td.tt-ger{font-size:var(--t-alt);color:var(--ink-2);line-height:1.45;}
table.v2 td.tt-ger b{color:var(--ink);font-weight:600;}
.tt-kapi{border:1px solid var(--line);border-left:4px solid var(--muted);border-radius:var(--r);
  padding:14px 16px;background:var(--panel-2);margin-bottom:var(--s3);}
.tt-kapi.degerlendir{border-left-color:var(--brand);background:var(--brand-fill);}
.tt-kapi.bekle{border-left-color:var(--line-2);}
.tt-kapi .karar{font-family:'JetBrains Mono',monospace;font-size:var(--t-etiket);letter-spacing:var(--ls-etiket);
  text-transform:uppercase;font-weight:var(--w-etiket);color:var(--muted);}
.tt-kapi .cumle{font-size:var(--t-kart);color:var(--ink);margin-top:4px;line-height:1.45;}
.tt-kapi .kosul{font-size:var(--t-alt);color:var(--ink-2);margin-top:8px;line-height:1.6;}
.tt-kapi .kosul b{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);}
.tt-kod{font-family:'JetBrains Mono',monospace;font-size:var(--t-alt);background:var(--panel-2);
  border:1px solid var(--line);padding:8px 10px;border-radius:var(--r);white-space:pre-wrap;word-break:break-word;}
.tt-cey{width:100%;height:auto;display:block;margin:4px 0 10px;}
.tt-cey text{font-family:'JetBrains Mono',monospace;}
.tt-cey .cad{font-size:11px;letter-spacing:.12em;fill:var(--muted);text-transform:uppercase;}
.tt-cey .eks{font-size:11px;fill:var(--muted);}
.tt-cey .num{font-size:12px;font-weight:700;}
table.v2.tt-izgara td.tt-i, table.v2.tt-izgara th.tt-i{width:26px;padding-left:2px;padding-right:2px;}
table.v2.tt-izgara .tt-grup{border-left:2px solid var(--line-2);}
table.v2.tt-izgara th.tt-blok{text-align:center;color:var(--brand);letter-spacing:.1em;}
table.v2.tt-izgara tr.tt-ayri td.rk{box-shadow:inset 3px 0 0 var(--brand);}
table.v2.tt-izgara td.tt-fark{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);
  color:var(--brand);text-align:center;}
table.v2.tt-izgara tfoot td{border-top:2px solid var(--line-2);padding-top:8px;}
table.v2.tt-izgara td.tt-ayak{font-family:'JetBrains Mono',monospace;font-size:var(--t-kucuk);
  color:var(--ink-2);text-align:center;line-height:1.5;}
table.v2.tt-izgara td.tt-ayak b{font-size:var(--t-alt);color:var(--ink);}
table.v2.tt-izgara td.tt-ayak .dv{color:var(--brand);}
</style>"""


# ── yardımcılar ───────────────────────────────────────────────────
def _e(x) -> str:
    return html.escape(str(x))


def _tl(v: float | None, kisa: bool = False) -> str:
    if v is None:
        return "—"
    if kisa and abs(v) >= 1e6:
        return f"{v / 1e6:,.1f} M TL".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v:,.0f} TL".replace(",", ".")


def _pct(v: float | None, n: int = 0) -> str:
    return "—" if v is None else (f"%{v * 100:.{n}f}").replace(".", ",")


def _tarih(iso: str | None) -> str:
    if not iso:
        return "—"
    t = datetime.fromisoformat(iso[:19])
    return f"{t.day} {AYLAR[t.month - 1]} {GUNLER[t.weekday()]} {t:%H:%M}"


def _kalan(iso: str | None) -> str:
    if not iso:
        return "—"
    t = datetime.fromisoformat(iso[:19]).replace(tzinfo=TR)
    s = (t - datetime.now(TR)).total_seconds()
    if s <= 0:
        return "kapandı"
    g, s = divmod(int(s), 86400)
    sa = s // 3600
    return (f"{g} gün {sa} sa" if g else f"{sa} sa {(s % 3600) // 60} dk")


def _kart(baslik: str, govde: str, ipucu: str = "") -> None:
    st.markdown("<div class='v2card'><div class='v2head'><h2>" + baslik + "</h2>" +
                (f"<div class='hint'>{ipucu}</div>" if ipucu else "") + "</div><div class='v2body'>" + govde +
                "</div></div>", unsafe_allow_html=True)


@st.cache_data(ttl=60, show_spinner=False)
def _son_analiz():
    """Panel yalnız OKUR — tabloları Toto zamanlayıcısı kurar (DDL web sürecinde koşmaz)."""
    try:
        return toto_db.son_analiz()
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def _haftalar():
    try:
        return toto_db.haftalar_tablo(40)
    except Exception:
        return []


def _ilk_gorulme(hid) -> str:
    try:
        for h in _haftalar():
            if h["hafta_id"] == hid and h.get("ilk_gorulme"):
                t = datetime.fromisoformat(h["ilk_gorulme"][:19]).replace(tzinfo=timezone.utc).astimezone(TR)
                return f" · sistem ilk gördü: {_tarih(t.strftime('%Y-%m-%dT%H:%M:%S'))}"
    except Exception:
        pass
    return ""


def _kadro_kutu(A: dict) -> str:
    """Eksik oyuncu verisinin durumu — anahtar var mı, kaç maçta veri var."""
    k = A.get("kadro") or {}
    if not k:
        return ""
    durum = k.get("durum") or "—"
    kapsam, pencere = k.get("kapsam", 0), k.get("pencere", 0)
    alt = (f"{kapsam}/15 maçta eksik listesi var" if kapsam else
           ("veri penceresi henüz açılmadı (ücretsiz plan: dün–bugün–yarın)" if not pencere
            else "penceredeki maçlarda liste bulunamadı"))
    return (f"<div class='tt-kutu'><div class='et'>Kadro verisi</div><div class='dg'>{_e(durum)}</div>"
            f"<div class='al'>{_e(alt)}</div></div>")


# ── güç × kaldıraç çeyreği ────────────────────────────────────────
CEYREK = {
    "BANKO": "Hem biliyoruz hem kalabalık favorimizi az oynuyor. Tek işaret — kuponun omurgası.",
    "KALABALIK FAVORİ": "Biliyoruz ama herkes aynı yere yığılmış. Tek işaret, kupona değer katmaz.",
    "FIRSAT": "Belirsiz maç, ama kalabalık yanlış yerde. Riski buradan satın al — ikili işaret.",
    "KARANLIK": "Ne güçlü bilgimiz var ne kalabalık yanılıyor. Sigorta (ikili/üçlü) ya da geç.",
}
X0, X1, Y0, Y1 = 0.34, 0.92, 0.55, 1.85          # eksen sınırları (güç · kaldıraç)
GX, GY = 0.55, 1.00                               # çeyrek ayırıcıları
CL, CR, CT, CB = 76, 726, 32, 340                 # çizim alanı


def _cx(g: float) -> float:
    g = min(max(g, X0), X1)
    return CL + (CR - CL) * (g - X0) / (X1 - X0)


def _cy(v: float) -> float:
    v = min(max(v, Y0), Y1)
    return CB - (CB - CT) * (math.log(v) - math.log(Y0)) / (math.log(Y1) - math.log(Y0))


def _ceyrek_veri(A: dict, S: list) -> list[dict]:
    """Her maç: güç (favorimizin olasılığı) · kaldıraç (favorimizin olasılığı ÷ kalabalığın ona verdiği pay).
    Kaldıraç 1'in ALTI, kalabalığın aynı sonuca bizden çok yığıldığı demektir — bilmek para kazandırmaz."""
    out = []
    for i, m in enumerate(A["maclar"]):
        P, Q = A["P"][i], A["Q"][i]
        f = max(range(3), key=lambda x: P[x])
        guc, kal = float(P[f]), float(P[f] / max(Q[f], 1e-9))
        j = max(range(3), key=lambda x: P[x] / max(Q[x], 1e-9))
        ad = ("BANKO" if kal >= GY else "KALABALIK FAVORİ") if guc >= GX else ("FIRSAT" if kal >= GY else "KARANLIK")
        out.append({"i": i, "mac": f"{m['ev']} - {m['dep']}", "guc": guc, "kal": kal,
                    "fav": SEC[f], "sec": SEC[j], "sec_kal": float(P[j] / max(Q[j], 1e-9)),
                    "n": len(S[i]), "ceyrek": ad, "bilgi": m.get("bilgi", "yok"),
                    "x": _cx(guc), "y": _cy(kal)})
    for _ in range(60):                            # üst üste binen noktaları hafifçe ayır
        for a in out:
            for b in out:
                if a is b:
                    continue
                dx, dy = a["x"] - b["x"], a["y"] - b["y"]
                d = math.hypot(dx, dy)
                if 1e-6 < d < 30:
                    it = (30 - d) / d * 0.25
                    a["x"] += dx * it; a["y"] += dy * it
                elif d <= 1e-6:
                    a["x"] += 0.7; a["y"] -= 0.7
        for a in out:
            a["x"] = min(max(a["x"], CL + 14), CR - 14)
            a["y"] = min(max(a["y"], CT + 14), CB - 14)
    return out


def _ceyrek_svg(V: list) -> str:
    gx, gy = _cx(GX), _cy(GY)
    s = [f"<svg class='tt-cey' viewBox='0 0 760 418' preserveAspectRatio='xMidYMid meet' role='img'>"]
    s.append(f"<rect x='{gx}' y='{CT}' width='{CR - gx}' height='{gy - CT}' fill='var(--brand-fill)' opacity='.55'/>")
    s.append(f"<rect x='{CL}' y='{CT}' width='{gx - CL}' height='{gy - CT}' fill='var(--panel-2)'/>")
    s.append(f"<rect x='{CL}' y='{CT}' width='{CR - CL}' height='{CB - CT}' fill='none' stroke='var(--line)'/>")
    s.append(f"<line x1='{gx}' y1='{CT}' x2='{gx}' y2='{CB}' stroke='var(--line-2)' stroke-dasharray='3 3'/>")
    s.append(f"<line x1='{CL}' y1='{gy}' x2='{CR}' y2='{gy}' stroke='var(--line-2)' stroke-dasharray='3 3'/>")
    for ad, ax, ay, an in (("FIRSAT", CL + 10, CT + 20, "start"), ("BANKO", CR - 10, CT + 20, "end"),
                           ("KARANLIK", CL + 10, CB - 10, "start"), ("KALABALIK FAVORİ", CR - 10, CB - 10, "end")):
        s.append(f"<text class='cad' x='{ax}' y='{ay}' text-anchor='{an}'>{ad}</text>")
    for g in (0.40, 0.55, 0.70, 0.85):             # x ekseni
        s.append(f"<text class='eks' x='{_cx(g)}' y='{CB + 16}' text-anchor='middle'>%{g * 100:.0f}</text>")
    for v in (0.6, 0.8, 1.0, 1.3, 1.7):            # y ekseni
        s.append(f"<text class='eks' x='{CL - 8}' y='{_cy(v) + 4}' text-anchor='end'>{v:.1f}×</text>")
    s.append(f"<text class='cad' x='{(CL + CR) / 2}' y='{CB + 36}' text-anchor='middle'>"
             "GÜÇ · favorimizin olasılığı →</text>")
    s.append(f"<text class='cad' x='-{(CT + CB) / 2}' y='16' text-anchor='middle' transform='rotate(-90)'>"
             "KALDIRAÇ · kalabalık favorimizi ne kadar AZ oynuyor →</text>")
    dolgu = {1: ("var(--brand)", "var(--brand)", "#ffffff"), 2: ("var(--brand-fill)", "var(--brand)", "var(--brand)"),
             3: ("var(--panel-3)", "var(--line-2)", "var(--muted)")}
    for p in V:
        f, c, t = dolgu.get(p["n"], dolgu[3])
        kes = " stroke-dasharray='2 2'" if p["bilgi"] == "yok" else ""
        s.append(f"<circle cx='{p['x']:.1f}' cy='{p['y']:.1f}' r='13' fill='{f}' stroke='{c}'{kes}/>"
                 f"<text class='num' x='{p['x']:.1f}' y='{p['y'] + 4:.1f}' text-anchor='middle' fill='{t}'>"
                 f"{p['i'] + 1}</text>")
    ly = CB + 66
    for dx, (n, ad) in zip((CL, CL + 150, CL + 290), ((1, "tek işaret"), (2, "ikili"), (3, "üçlü"))):
        f, c, _t = dolgu[n]
        s.append(f"<circle cx='{dx + 8}' cy='{ly - 4}' r='7' fill='{f}' stroke='{c}'/>"
                 f"<text class='eks' x='{dx + 22}' y='{ly}'>{ad}</text>")
    s.append(f"<text class='eks' x='{CL + 420}' y='{ly}'>kesik çizgi: fiyatı/bilgisi olmayan maç</text>")
    s.append("</svg>")
    return "".join(s)


# ── portföy: kuponun A·B·C·D blokları ─────────────────────────────
BLOK_AD = ("A", "B", "C", "D")
BLOK_VARSAYILAN = ("DENGELİ", "15_AVCISI", "YOK", "YOK")
PORTFOY_M = 40_000            # birleşik olasılık için örnekleme (12+/13+/14+); 15 TAM hesaplanır


def _pb_dagilim(x) -> np.ndarray:
    """Poisson-binom: bir KUTUNUN en iyi kolonunun doğru sayısı dağılımı (kesin)."""
    f = np.zeros(len(x) + 1)
    f[0] = 1.0
    for v in x:
        f[1:] = f[1:] * (1 - v) + f[:-1] * v
        f[0] *= (1 - v)
    return f


def _blok_olcum(P, Q, S) -> dict:
    """Bir bloğun (kutunun) kapsama olasılığı ve kalabalık benzerliği."""
    px = np.array([sum(P[i][j] for j in S[i]) for i in range(15)])
    qx = np.array([sum(Q[i][j] for j in S[i]) for i in range(15)])
    f = _pb_dagilim(px)
    return {"p15": float(f[15]), "p13p": float(f[13:].sum()), "p12p": float(f[12:].sum()),
            "q_benzer": float(np.prod(qx / np.maximum(px, 1e-12))), "px": px}


def _birlesik(P, bloklar: list) -> dict:
    """Birden çok bloğun birleşimi: 15 TAM (içerme-dışarma), 12+/13+/14+ örneklemeyle."""
    tam15 = 0.0
    for r in range(1, len(bloklar) + 1):
        for comb in itertools.combinations(range(len(bloklar)), r):
            p = 1.0
            for i in range(15):
                ort = set(bloklar[comb[0]][i])
                for b in comb[1:]:
                    ort &= set(bloklar[b][i])
                p *= sum(P[i][j] for j in ort)
                if p == 0.0:
                    break
            tam15 += ((-1) ** (r + 1)) * p
    rng = np.random.default_rng(7)
    O = np.stack([rng.choice(3, size=PORTFOY_M, p=P[i]) for i in range(15)], axis=1)
    en_iyi = np.zeros(PORTFOY_M, dtype=np.int16)
    for S in bloklar:
        cov = np.zeros((15, 3), dtype=bool)
        for i in range(15):
            for j in S[i]:
                cov[i, j] = True
        d = cov[np.arange(15)[None, :], O].sum(1).astype(np.int16)
        en_iyi = np.maximum(en_iyi, d)
    return {"p15": float(tam15), "p13p": float((en_iyi >= 13).mean()), "p12p": float((en_iyi >= 12).mean())}


def _portfoy_kart(A: dict, butce: int) -> None:
    kupon = {k["profil"]: k for k in A["kuponlar"] if k["butce"] == butce}
    if not kupon:
        return
    secenek = ["YOK"] + [p for p in ("FAVORİ", "DENGELİ", "15_AVCISI") if p in kupon]
    ad = {"YOK": "— boş —", "FAVORİ": "Favori", "DENGELİ": "Dengeli", "15_AVCISI": "15 Avcısı"}
    st.markdown("<div class='tt-not' style='margin-top:6px'><b>Portföy.</b> Kupon A, B, C ve D olmak üzere dört "
                "ayrı kolondan oluşur ve her biri bağımsız işaretlenir. Aynı işaretleri dört kez yazmak dört şans "
                "değil, pahalı tek şanstır — ölçtük: 32 kolonu bloklara dağıtmanın kapsama kazancı en fazla ×1,07. "
                "Dört bloğun asıl değeri <b>zıt profilleri aynı bilete koyabilmek</b>.<br>"
                "<b>Dikkat:</b> en sık tutan blok en iyi blok değildir. Favori sık tutar ama kalabalık tam o "
                "kutuda oturur, bu yüzden TL başına dönüşü en düşük olandır. Aşağıdaki son iki sütunu birlikte "
                "oku: isabet sıklığı ile TL başına dönüş çoğu hafta ters yönde çalışır.</div>",
                unsafe_allow_html=True)
    sutun = st.columns(4)
    secim = []
    for i, (s, blok) in enumerate(zip(sutun, BLOK_AD)):
        with s:
            v = BLOK_VARSAYILAN[i] if BLOK_VARSAYILAN[i] in secenek else "YOK"
            secim.append(st.selectbox(f"{blok} kolonu", secenek, index=secenek.index(v),
                                      format_func=lambda x: ad[x], key=f"tt_blok_{blok}"))
    P, Q = A["P"], A["Q"]
    satir, bloklar, maliyet, kolon, ev_top = "", [], 0.0, 0, 0.0
    dolu: list[tuple[str, str, list]] = []
    for blok, prof in zip(BLOK_AD, secim):
        if prof == "YOK":
            satir += (f"<tr><td class='rk'>{blok}</td><td class='sb'>boş</td><td class='n'>—</td>"
                      "<td class='n'>—</td><td class='n'>—</td><td class='n'>—</td><td class='n'>—</td></tr>")
            continue
        k = kupon[prof]
        S = [list(x) for x in k["S"]]
        o = _blok_olcum(P, Q, S)
        bloklar.append(S)
        dolu.append((blok, ad[prof], S, k))
        maliyet += k["maliyet"]
        kolon += k["kolon"]
        ev_top += (k.get("ev_tl") or 0.0) * k["maliyet"]        # beklenen değer kolonda DOĞRUSAL
        satir += (f"<tr><td class='rk'>{blok}</td><td><span class='ag'>{_e(ad[prof])}</span>"
                  f"<span class='sb'>{k['kolon']} kolon · {_tl(k['maliyet'])}</span></td>"
                  f"<td class='n'>{_pct(o['p15'], 3)}</td><td class='n'>{_pct(o['p13p'], 2)}</td>"
                  f"<td class='n'>{_pct(o['p12p'], 1)}</td><td class='n'>{o['q_benzer']:.2f}</td>"
                  f"<td class='n'>{k['ev_tl']:.2f}</td></tr>")
    if not bloklar:
        return
    B = _birlesik(P, bloklar)
    ayrisma = ""
    if len(bloklar) >= 2:
        far = [sum(1 for i in range(15) if set(bloklar[a][i]) != set(bloklar[b][i]))
               for a in range(len(bloklar)) for b in range(a + 1, len(bloklar))]
        ayrisma = (f"<div class='tt-not' style='margin-top:10px'>Bloklar birbirinden ortalama "
                   f"<b>{np.mean(far):.1f}/15 maçta</b> ayrışıyor (en az {min(far)}, en çok {max(far)}). "
                   "Ayrışma ne kadar yüksekse şanslar o kadar bağımsızdır.</div>")
    ozet = ("<div class='tt-grid' style='margin-bottom:12px'>"
            f"<div class='tt-kutu'><div class='et'>Toplam</div><div class='dg'>{kolon} kolon</div>"
            f"<div class='al'>{_tl(maliyet)} · {len(bloklar)} blok dolu</div></div>"
            f"<div class='tt-kutu'><div class='et'>Birleşik 12+</div><div class='dg'>{_pct(B['p12p'], 1)}</div>"
            "<div class='al'>en az bir blok 12 ya da üstünü bilir</div></div>"
            f"<div class='tt-kutu'><div class='et'>Birleşik 15</div><div class='dg'>{_pct(B['p15'], 4)}</div>"
            "<div class='al'>tam hesap · 13+ için " + _pct(B["p13p"], 2) + "</div></div>"
            f"<div class='tt-kutu'><div class='et'>Portföy dönüşü</div>"
            f"<div class='dg'>{(ev_top / maliyet if maliyet else 0):.2f} / TL</div>"
            "<div class='al'>blokların maliyet ağırlıklı ortalaması</div></div></div>")
    # maç × blok ızgarası — fişe geçirilecek biçim
    ust = "".join(f"<th colspan='3' class='tt-blok tt-grup'>{b} · {_e(p)}</th>" for b, p, _, _k in dolu)
    alt = "".join("".join(f"<th class='tt-i{' tt-grup' if j == 0 else ''}'>{SEC[j]}</th>" for j in range(3))
                  for _ in dolu)
    izgara = ""
    for i, m in enumerate(A["maclar"]):
        hucre, setler = "", []
        for _b, _p, S, _k in dolu:
            setler.append(tuple(sorted(S[i])))
            for j in range(3):
                sinif = "tt-i " + ("tt-on" if j in S[i] else "tt-off") + (" tt-grup" if j == 0 else "")
                hucre += f"<td class='{sinif}'>{SEC[j]}</td>"
        ayri = len(set(setler)) > 1
        tr = "<tr class='tt-ayri'>" if ayri else "<tr>"
        izgara += (tr
                   + f"<td class='rk'>{i + 1}</td>"
                   f"<td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>"
                   f"<span class='sb'>{_tarih(m['tarih'])} · {_e(m['turnuva'])}</span></td>"
                   f"{hucre}<td class='tt-fark'>{'ayrı' if ayri else ''}</td></tr>")
    # blok ekonomisi: ızgaranın altında, her bloğun kendi sütununda
    ayak = "".join(
        f"<td colspan='3' class='tt-grup tt-ayak'>{_tl(k['maliyet'])}<br>"
        f"<b>{(k.get('ev_tl') or 0):.2f}</b> / TL"
        + (f"<br><span class='dv'>devirle {(k['ev_tl_devirli']):.2f}</span>" if k.get("ev_tl_devirli") else "")
        + "</td>" for _b, _p, _S, k in dolu)
    kopya = "".join(
        f"<div class='et' style='margin-top:10px'>{b} kolonu · {_e(p)}</div><div class='tt-kod'>"
        + _e(" · ".join(f"{i + 1}:" + "/".join(SEC[j] for j in S[i]) for i in range(15))) + "</div>"
        for b, p, S, _k in dolu)
    n_ayri = sum(1 for i in range(15)
                 if len({tuple(sorted(S[i])) for _b, _p, S, _k in dolu}) > 1)
    kapsam = A.get("iddaa_kapsam")
    _kart("Portföy · A · B · C · D", ozet
          + "<table class='v2'><thead><tr><th></th><th>Blok</th><th>15</th><th>13+</th><th>12+</th>"
            "<th>Kalabalık benzerliği</th><th>Beklenen dönüş/TL</th></tr></thead>"
            f"<tbody>{satir}</tbody></table>" + ayrisma
          + "<div class='et' style='margin-top:16px'>Maç maç işaretler</div>"
            "<div class='tt-not'>Fişteki düzenin aynısı: her blok kendi 1 · 0 · 2 sütunlarıyla. Soldaki "
            f"kalın çizgi ve sağdaki <b>ayrı</b> etiketi, blokların farklı işaret koyduğu maçları gösterir — "
            f"portföyün çeşitlenmesi <b>{n_ayri} maçta</b> gerçekleşiyor, diğerlerinde bütün bloklar aynı "
            "kaderi paylaşır.</div>"
            "<table class='v2 tt-izgara' style='margin-top:8px'><thead>"
            f"<tr><th></th><th>Maç</th>{ust}<th></th></tr>"
            f"<tr><th></th><th></th>{alt}<th></th></tr></thead><tbody>{izgara}</tbody>"
            f"<tfoot><tr><td></td><td class='sb'>Bloğun maliyeti ve TL başına beklenen dönüşü</td>"
            f"{ayak}<td></td></tr></tfoot></table>"
            f"<div class='tt-not' style='margin-top:8px'>Bu hafta <b>{kapsam}/15</b> maçta iddaa fiyatı var; "
            "fiyatı olmayan maçlarda olasılık ajanlardan geliyor. Kalan fiyatlar açıldıkça bu getiriler "
            "güncellenir. <b>Devirle</b> satırı, önceki haftadan devir gelirse oluşacak değeri gösterir — "
            "bu haftanın devri henüz kesin değil.</div>"
          + kopya
          + "<div class='tt-not' style='margin-top:10px'><b>Kalabalık benzerliği</b> 1'in üstündeyse kalabalık o "
            "kutuyu olasılığından fazla oynuyor demektir — tutarsan ikramiyeyi daha çok kişiyle bölüşürsün. "
            "1'in altı tersi: seyrek tutar ama tuttuğunda paylaşan azdır.</div>"
            "<div class='tt-uyari'><b>Misli bu tabloyu değiştirmez.</b> Misli olasılığı hiç artırmaz, yalnız "
            "bahsi katlar. Üstelik parimutuelde 15'i bilen tek kolon sizseniz misli 2 havuzun 2/2'sini verir — "
            "yani aynı para, iki katı bedel. Şansı artırmanın yolu kolon, misli değil.</div>",
          f"{kolon} kolon · {_tl(maliyet)}")


def _ceyrek_kart(A: dict, k: dict) -> None:
    V = _ceyrek_veri(A, k["S"])
    kutular = ""
    for ad, aciklama in CEYREK.items():
        uy = [p for p in V if p["ceyrek"] == ad]
        no = " · ".join(f"{p['i'] + 1}" for p in uy) or "—"
        kutular += (f"<div class='tt-kutu'><div class='et'>{_e(ad)} · {len(uy)} maç</div>"
                    f"<div class='dg'>{_e(no)}</div><div class='al'>{_e(aciklama)}</div></div>")
    _kart("Güç × Kaldıraç · kupon neden böyle kuruldu",
          "<div class='tt-not'><b>Yatay eksen — güç:</b> modelin favorisine verdiği olasılık. "
          "<b>Dikey eksen — kaldıraç:</b> o favorinin olasılığı ÷ kalabalığın ona verdiği işaret payı. "
          "1,0'ın <b>üstü</b> kalabalığın onu az oynadığı, <b>altı</b> herkesin aynı yere yığıldığı demektir. "
          "Toto parimutuel olduğu için ikramiyeyi bölüşürüz: bir maçı bilmek değil, <b>kalabalıktan farklı "
          "bilmek</b> kazandırır. Kuponun parası sağ üstten, riski sol taraftan gelir; sağ alt bölge doğru "
          "olsa bile ödemeyi kalabalıkla paylaştırır.</div>" + _ceyrek_svg(V)
          + f"<div class='tt-grid'>{kutular}</div>", "P / q · işaret sayısı")


def ics(A: dict) -> str:
    """Takvim dosyası: kapanıştan 24 ve 3 saat önce hatırlatır."""
    h = A["hafta"]
    kap = datetime.fromisoformat(h["kapanis"][:19]).replace(tzinfo=TR).astimezone(timezone.utc)
    ilk = A["maclar"][0] if A.get("maclar") else {}
    f = lambda t: t.strftime("%Y%m%dT%H%M%SZ")
    aciklama = (f"Spor Toto {h['sezon']} {h['ad']} · son oynama {_tarih(h['kapanis'])} (TR)\\n"
                f"İlk maç: {ilk.get('ev', '')} - {ilk.get('dep', '')}\\n"
                "Kuponu BetAgents Desk > SÜPER TOTO > Bu Hafta sayfasından al.")
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//BetAgents//Toto//TR", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT", f"UID:toto-{h['id']}@betagents", f"DTSTAMP:{f(datetime.now(timezone.utc))}",
        f"DTSTART:{f(kap - timedelta(minutes=30))}", f"DTEND:{f(kap)}",
        f"SUMMARY:Spor Toto {h['ad']} — son oynama {kap.astimezone(TR):%H:%M}",
        f"DESCRIPTION:{aciklama}",
        "BEGIN:VALARM", "TRIGGER:-PT24H", "ACTION:DISPLAY", "DESCRIPTION:Toto: son 24 saat", "END:VALARM",
        "BEGIN:VALARM", "TRIGGER:-PT3H", "ACTION:DISPLAY", "DESCRIPTION:Toto: son 3 saat — kuponu kontrol et",
        "END:VALARM", "END:VEVENT", "END:VCALENDAR", ""])


# ── 1 · BU HAFTA ──────────────────────────────────────────────────
def bu_hafta(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    A = _son_analiz()
    if not A:
        baslik("Süper Toto", "Analiz henüz yok — Toto zamanlayıcısı ilk koşusunu yapınca burada görünür.", [])
        return
    h = A["hafta"]
    havuz15 = A["havuz"].get("15") if isinstance(A["havuz"], dict) else None
    havuz15 = havuz15 if havuz15 is not None else A["havuz"].get(15)
    kpi = [{"ad": "Kapanış", "deger": _kalan(h["kapanis"])},
           {"ad": "15 havuzu", "deger": _tl(havuz15, True) if A["devir_kesin"] else
            _tl(havuz15, True) + " / " + _tl(havuz15 + (A["devir_senaryo"] or {}).get("15", 0), True)},
           {"ad": "iddaa fiyatı", "deger": f"{A['iddaa_kapsam']}/15"},
           {"ad": "Kolon", "deger": _tl(A["fiyat"])}]
    baslik(f"{h['sezon']} · {h['ad']}", "Olasılığı ajan pazarı, kalabalığın ne oynadığını kalabalık modeli "
           "söyler; kupon ikisinin farkından kurulur. Her işaretin gerekçesi aşağıda.", kpi)

    # oynama kapısı — sistemin bu hafta için kararı
    kp = A.get("kapi")
    if kp:
        ks = ""
        for ad, v in kp["kosul"].items():
            im = "✓" if v["saglandi"] else "—"
            ks += f"<div class='kosul'><b>{im}</b> {_e(v['aciklama'])}</div>"
        on = kp.get("onerilen") or {}
        oner = ""
        if kp["karar"] == "DEĞERLENDİR" and on:
            oner = (f"<div class='kosul' style='margin-top:10px'><b>ÖNERİ</b> {_e(on['profil_ad'])} "
                    f"{on['kolon']} kolon · {_tl(on['maliyet'])} · TL başına {on['ev_tl']:.2f}</div>")
        st.markdown(f"<div class='tt-kapi {kp['renk']}'><div class='karar'>bu hafta · {_e(kp['karar'])}</div>"
                    f"<div class='cumle'>{_e(kp['ozet'])}</div>{ks}{oner}"
                    "<div class='kosul' style='margin-top:10px;color:var(--muted)'>Kural: fiyat kapsamı ≥ 12/15, "
                    "devir ≥ dağıtılan tutarın %15'i, üst sınırdaki en iyi kuponun TL başına beklentisi ≥ 1,20. "
                    "Geçmiş test hiçbir profilin kârlılığını kanıtlamadı; varsayılan duruş kâğıt üzerinde izlemek.</div>"
                    "</div>", unsafe_allow_html=True)

    # takvim + nasıl oynanır
    ilk = A["maclar"][0]
    devir_metni = (f"Devir kesin: 15'liğe <b>{_tl((A['devir'] or {}).get('15', 0), True)}</b>." if A["devir_kesin"]
                   else f"<b>{_e(A['onceki_hafta']['ad'])} henüz sonuçlanmadı.</b> O hafta 15 bilen çıkmazsa bu haftanın "
                        f"15 havuzuna yaklaşık <b>{_tl((A['devir_senaryo'] or {}).get('15', 0), True)}</b> devir eklenir; "
                        "sonuç gelince analiz kendiliğinden yenilenir.")
    govde = ("<div class='tt-grid'>"
             f"<div class='tt-kutu'><div class='et'>Son oynama</div><div class='dg'>{_tarih(h['kapanis'])}</div>"
             f"<div class='al'>İlk maç {_e(ilk['ev'])} - {_e(ilk['dep'])} · kalan {_kalan(h['kapanis'])}</div></div>"
             f"<div class='tt-kutu'><div class='et'>Maçlar</div><div class='dg'>{_tarih(A['maclar'][0]['tarih'])[:6]} → "
             f"{_tarih(max(m['tarih'] for m in A['maclar']))[:6]}</div><div class='al'>15 maç · sonuç maç sonunda (90 dk)</div></div>"
             f"<div class='tt-kutu'><div class='et'>Nerede</div><div class='dg'>iddaa · bayi</div>"
             "<div class='al'>iddaa.com Spor Toto, yetkili uygulamalar (Nesine, Bilyoner, Misli…) ya da Spor Toto bayisi</div></div>"
             f"<div class='tt-kutu'><div class='et'>Satışa açılış</div><div class='dg'>{_tarih(A.get('satis_acilis'))}</div>"
             f"<div class='al'>Önceki program kapanınca açılır (oyun planı m.9/1){_ilk_gorulme(h['id'])}</div></div>"
             f"<div class='tt-kutu'><div class='et'>Analiz</div><div class='dg'>{_e(A['olusturma'][11:16])}</div>"
             f"<div class='al'>{_e(A['olusturma'][:10])} · günde 3 kez + kapanışa 3 saat kala son kez</div></div>"
             + _kadro_kutu(A)
             + "</div>"
             f"<div class='tt-uyari'>{devir_metni}</div>"
             "<div class='tt-not'><b>Nasıl oynanır.</b> 15 maçın her birine 1 (ev), 0 (beraberlik) ya da 2 (deplasman) "
             "işaretlenir. Bir maça birden çok işaret koymak <b>sistem</b> oynamaktır: kolon sayısı çarpılır "
             "(ör. 3 maçta ikili = 2×2×2 = 8 kolon). Kolon " + _tl(A["fiyat"]) + ", bir bilette en çok 2.500 kolon. "
             "12, 13, 14 ve 15 doğru ödül alır; her kolon yalnız bildiği EN ÜST dereceden ödenir. Oyun ilk maçın "
             "başlamasıyla kapanır.</div>")
    _kart("Oynama takvimi", govde, "Spor Toto oyun planı m.8–11")
    st.download_button("Takvime ekle (.ics · 24 ve 3 saat önce hatırlatır)", data=ics(A).encode("utf-8"),
                       file_name=f"toto-{h['id']}.ics", mime="text/calendar", key="tt_ics")

    # kupon seçici
    prof_ad = {"15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli", "FAVORİ": "Favori"}
    c1, c2 = st.columns([3, 2])
    with c1:
        prof = st.radio("Profil", list(prof_ad), format_func=lambda x: prof_ad[x], horizontal=True, key="tt_prof")
    butceler = sorted({k["butce"] for k in A["kuponlar"]})
    with c2:
        B = st.selectbox("Bütçe (en çok kolon)", butceler, index=0, key="tt_butce",
                         format_func=lambda b: f"{b} kolon · en çok {_tl(b * A['fiyat'])}")
    k = next(x for x in A["kuponlar"] if x["profil"] == prof and x["butce"] == B)
    satirlar = ""
    for i, m in enumerate(A["maclar"]):
        isr = set(k["S"][i])
        hucre = "".join(f"<td class='tt-i {'tt-on' if j in isr else 'tt-off'}'>{SEC[j]}</td>" for j in range(3))
        ger = k["gerekce"][i].split(" — ", 1)[-1] if k.get("gerekce") else ""
        satirlar += (f"<tr><td class='rk'>{i + 1}</td><td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>"
                     f"<span class='sb'>{_tarih(m['tarih'])} · {_e(m['turnuva'])}</span></td>{hucre}"
                     f"<td class='tt-ger'>{_e(ger)}</td></tr>")
    ozet = ("<div class='tt-grid' style='margin-bottom:12px'>"
            f"<div class='tt-kutu'><div class='et'>Kupon</div><div class='dg'>{k['kolon']} kolon</div>"
            f"<div class='al'>{_tl(k['maliyet'])}</div></div>"
            f"<div class='tt-kutu'><div class='et'>15 şansı</div><div class='dg'>{_pct(k['p15'], 3)}</div>"
            f"<div class='al'>{_e(k['sans15'])} · 15 gelirse ≈ {_tl(k['odul15'], True)}</div></div>"
            f"<div class='tt-kutu'><div class='et'>12+ şansı</div><div class='dg'>{_pct(k['p12p'], 1)}</div>"
            f"<div class='al'>{_e(k['sans12'])}</div></div>"
            f"<div class='tt-kutu'><div class='et'>Beklenen dönüş</div><div class='dg'>{k['ev_tl']:.2f} / TL</div>"
            f"<div class='al'>{'devir gelirse ' + format(k['ev_tl_devirli'], '.2f') + ' / TL · ' if k.get('ev_tl_devirli') else ''}"
            "ortalama oyuncu ≈ 0,64</div></div></div>")
    kopya = " · ".join(f"{i + 1}:{'/'.join(SEC[j] for j in k['S'][i])}" for i in range(15))
    _kart(f"Kupon · {prof_ad[prof]}", ozet + f"<div class='tt-not'>{_e(k['profil_aciklama'])}</div>"
          "<table class='v2' style='margin-top:10px'><thead><tr><th></th><th>Maç</th><th>1</th><th>0</th><th>2</th>"
          f"<th>Neden</th></tr></thead><tbody>{satirlar}</tbody></table>"
          f"<div class='et' style='margin-top:12px'>Kupona geçir</div><div class='tt-kod'>{_e(kopya)}</div>",
          f"{k['kolon']} kolon · {_tl(k['maliyet'])}")
    st.markdown("<div class='tt-uyari'><b>Beklenti ayarı.</b> Beklenen dönüşün büyük kısmı 14 ve 15 isabetinden gelir. "
                "Bunlar tek haftada çok seyrektir; kâr ancak uzun sürede ve seyrek büyük vuruşlarla gerçekleşir. "
                "Geçmiş Test sayfası bunun geçmişte nasıl sonuçlandığını gösterir. Bu bir yatırım tavsiyesi değildir; "
                "karar ve bütçe sınırı sizindir.</div>", unsafe_allow_html=True)

    _ceyrek_kart(A, k)
    _portfoy_kart(A, B)

    # maç analizi
    rows = ""
    for i, m in enumerate(A["maclar"]):
        P, Q = A["P"][i], A["Q"][i]
        g = m["gerekce"]
        idd = m.get("iddaa") or {}
        oran = " / ".join(f"{x:.2f}" for x in idd["oran"]) if idd.get("oran") else "fiyat yok"
        pq = " · ".join(f"{SEC[j]} {_pct(P[j])}/{_pct(Q[j])}" for j in range(3))
        rows += (f"<tr><td class='rk'>{i + 1}</td><td><span class='ag'>{_e(m['ev'])} - {_e(m['dep'])}</span>"
                 f"<span class='sb'>{_e(m['turnuva'])} · bilgi: {_e(m['bilgi'])}</span></td>"
                 f"<td class='n'>{_e(oran)}</td><td class='tt-ger'>{pq}</td>"
                 f"<td class='n'>{_e(g['deger'])} · {max(g['deger_orani']):.2f}</td></tr>")
    _kart("Maç analizi", "<div class='tt-not'>Her maçta: gerçek olasılık (ajan pazarı) / kalabalığın işaretleme "
          "payı. Değer oranı = olasılık ÷ kalabalık; 1'in üstü, o sonucun kalabalıkça az oynandığı demektir.</div>"
          "<table class='v2' style='margin-top:8px'><thead><tr><th></th><th>Maç</th><th>iddaa 1/0/2</th>"
          f"<th>Olasılık / kalabalık</th><th>Değerli</th></tr></thead><tbody>{rows}</tbody></table>",
          "P / q")
    secenek = [f"{i + 1}. {m['ev']} - {m['dep']}" for i, m in enumerate(A["maclar"])]
    sec = st.selectbox("Maç ayrıntısı · ajan görüşleri", secenek, index=0, key="tt_mac_sec")
    i = secenek.index(sec)
    m = A["maclar"][i]
    sat = "".join(f"<div class='tt-not'>• {_e(x)}</div>" for x in m["gerekce"]["satirlar"])
    aj = ""
    for t in m.get("islemler") or []:
        aj += (f"<tr><td class='ag'>{_e(t['ajan'])}</td><td class='n'>{_pct(t['pay'])}</td>"
               f"<td class='n'>{' · '.join(_pct(x) for x in t['gorus'])}</td>"
               f"<td class='n'>{_e(t['aldigi'])} (+{t['fark'] * 100:.0f} puan)</td></tr>")
    notlar = m.get("not") or {}
    ek = []
    if notlar.get("elo"):
        ek.append(f"Elo {notlar['elo'][0]} - {notlar['elo'][1]}")
    if "h2h_n" in notlar:
        ek.append(f"son 8 yılda aralarındaki maç: {notlar['h2h_n']}")
    idd = m.get("iddaa") or {}
    if idd.get("oran"):
        ek.append("iddaa " + " / ".join(f"{x:.2f}" for x in idd["oran"]))
    kd = notlar.get("kadro")
    kadro_html = ""
    if kd:
        kadro_html = ("<table class='v2' style='margin-top:10px'><thead><tr><th>Eksik oyuncular</th>"
                      f"<th>{_e(m['ev'])}</th><th>{_e(m['dep'])}</th></tr></thead><tbody>"
                      f"<tr><td>Kaç oyuncu</td><td class='n'>{kd['ev_eksik']}</td><td class='n'>{kd['dep_eksik']}</td></tr>"
                      f"<tr><td>Ağırlık (kesin yok = 1)</td><td class='n'>{_e(kd['ev_agirlik'])}</td>"
                      f"<td class='n'>{_e(kd['dep_agirlik'])}</td></tr>"
                      f"<tr><td>İsimler</td><td class='tt-ger'>{_e(', '.join(kd['ev_liste']) or '—')}</td>"
                      f"<td class='tt-ger'>{_e(', '.join(kd['dep_liste']) or '—')}</td></tr></tbody></table>")
    elif notlar.get("kadro_hata"):
        kadro_html = "<div class='sb' style='margin-top:8px'>Kadro verisi alınamadı.</div>"
    kr = m.get("karne") or {}
    kev, kdp = kr.get("ev", {}), kr.get("dep", {})
    def _k(d, a, b=None):
        v = d.get(a)
        if v is None:
            return "—"
        v = f"{v:.2f}".replace(".", ",") if isinstance(v, float) else f"{v}"
        return _e(v + (f" · {d.get(b)}" if b and d.get(b) else ""))
    karne = ("<table class='v2' style='margin-top:10px'><thead><tr><th>Takım karnesi</th>"
             f"<th>{_e(m['ev'])}</th><th>{_e(m['dep'])}</th></tr></thead><tbody>"
             f"<tr><td>Elo · sıra</td><td class='n'>{_k(kev, 'elo', 'elo_sira')}</td><td class='n'>{_k(kdp, 'elo', 'elo_sira')}</td></tr>"
             f"<tr><td>Hücum · sıra</td><td class='n'>{_k(kev, 'hucum', 'hucum_sira')}</td><td class='n'>{_k(kdp, 'hucum', 'hucum_sira')}</td></tr>"
             f"<tr><td>Savunma · sıra (düşük iyi)</td><td class='n'>{_k(kev, 'savunma', 'savunma_sira')}</td><td class='n'>{_k(kdp, 'savunma', 'savunma_sira')}</td></tr>"
             f"<tr><td>Toto'da görünme</td><td class='n'>{_k(kev, 'toto_n')}</td><td class='n'>{_k(kdp, 'toto_n')}</td></tr>"
             f"<tr><td>Toto'daki son 5 (G/B/M)</td><td class='n'>{_k(kev, 'toto_son')}</td><td class='n'>{_k(kdp, 'toto_son')}</td></tr>"
             "</tbody></table>")
    _kart(f"{i + 1}. {_e(m['ev'])} - {_e(m['dep'])}", sat + "<table class='v2' style='margin-top:8px'><thead><tr>"
          "<th>Ajan</th><th>Pazar payı</th><th>Görüş 1/0/2</th><th>Fiyata göre aldığı</th></tr></thead>"
          f"<tbody>{aj}</tbody></table>{karne}{kadro_html}<div class='sb' style='margin-top:6px'>{_e(' · '.join(ek))}</div>",
          _tarih(m["tarih"]))


# ── 2 · AJAN PAZARI ───────────────────────────────────────────────
def ajan_pazari(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    A = _son_analiz()
    CZ = (A or {}).get("cuzdan") or {}
    if CZ and "KULUP" not in CZ:
        CZ = {"KULUP": CZ}
    W = CZ.get("KULUP") or {}
    baslik("Ajan Pazarı", "Ajanlar her maçta inandıkları kadar pozisyon alır; haklı çıkanın cüzdanı büyür, pazar "
           "fiyatı servet ağırlıklıdır (Kelly bahisçileri pazarı). Kulüp ve milli maçlar ayrı pazarlarda yarışır.",
           [{"ad": a, "deger": _pct(w)} for a, w in sorted(W.items(), key=lambda x: -x[1])])
    acik = ("<div class='tt-not'><b>Nasıl çalışır.</b> Her maç 3 sonuçlu bir pazardır. Her ajan servetinin %10'unu "
            "kendi olasılıklarına göre sonuçlara dağıtır. Pazar fiyatı = servetle ağırlıklı görüş ortalaması. "
            "Maç bitince cüzdan, ajanın doğru sonuca verdiği olasılık ÷ pazar fiyatı oranında büyür ya da küçülür. "
            "Böylece geçmişte gerçekten bilgi katan ajanın sesi kendiliğinden artar, boş konuşan fakirleşir. "
            "Noterle belirlenen maçlar cüzdanları değiştirmez.</div>"
            "<div class='tt-not' style='margin-top:8px'><b>Ajanlar.</b> PİYASA: iddaa'nın marjı temizlenmiş fiyatı. "
            "ELO: takım gücü (kulüpte lig içi, millide Dünya Futbol Elo kuralları). FORM: son bir yılın gol verisinden "
            "hücum/savunma modeli. H2H: aralarındaki maçlar (Elo'ya doğru büzülmüş).</div>")
    def _bar(Wx):
        b = ""
        for a, w in sorted(Wx.items(), key=lambda x: -x[1]):
            b += (f"<tr><td class='ag'>{_e(a)}</td><td style='width:60%'><div class='tt-cizgi'><b style='width:{w * 100:.1f}%'>"
                  f"</b></div></td><td class='n'>{_pct(w, 1)}</td></tr>")
        return b
    ek = ("<div class='tt-not' style='margin-top:8px'><b>Neden iki pazar.</b> Geçmiş testte milli maçlarda en isabetli "
          "ajan H2H çıktı (log-kayıp 0,813), kulüp maçlarında piyasa fiyatı. Ortak cüzdan H2H'nin sesini kulüp "
          "maçlarındaki başarısına göre kısıyordu; ayrı milli pazar bu kaybı giderdi.</div>")
    _kart("Cüzdanlar · kulüp maçları", acik + ek + f"<table class='v2' style='margin-top:10px'><tbody>{_bar(W)}</tbody></table>",
          "2022–2026 geçmişinde öğrenildi · her hafta güncellenir")
    if CZ.get("MILLI"):
        _kart("Cüzdanlar · milli maçlar", f"<table class='v2'><tbody>{_bar(CZ['MILLI'])}</tbody></table>",
              "kesir 0,3 · 329 milli maçla öğrenildi")
    try:
        gec = toto_db.cuzdan_gecmisi()
    except Exception:
        gec = []
    if gec:
        import pandas as pd
        df = pd.DataFrame(gec, columns=["hafta", "ajan", "servet"])
        df = df[~df["ajan"].str.startswith("M:")].pivot(index="hafta", columns="ajan", values="servet")
        st.line_chart(df)
    if A:
        rows = ""
        for m in A["maclar"]:
            for t in (m.get("islemler") or [])[:4]:
                rows += (f"<tr><td class='rk'>{m['sira']}</td><td>{_e(m['ev'])} - {_e(m['dep'])}</td><td>{_e(t['ajan'])}</td>"
                         f"<td class='n'>{_pct(t['pay'])}</td><td class='n'>{_e(t['aldigi'])} +{t['fark'] * 100:.0f}</td></tr>")
        _kart("Bu haftanın işlemleri", "<table class='v2'><thead><tr><th></th><th>Maç</th><th>Ajan</th><th>Pay</th>"
              f"<th>Fiyata göre aldığı</th></tr></thead><tbody>{rows}</tbody></table>", "görüş − pazar fiyatı")


# ── 3 · GEÇMİŞ TEST ───────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def _gt():
    p = KOK / "geri_test_ozet.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def gecmis_test(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    G = _gt()
    if not G:
        baslik("Geçmiş Test", "Geçmiş test özeti henüz yok.", [])
        return
    baslik("Geçmiş Test", G.get("alt", ""), [{"ad": x["ad"], "deger": x["deger"]} for x in G.get("kpi", [])])
    for blok in G.get("bloklar", []):
        _kart(blok["baslik"], blok["html"], blok.get("ipucu", ""))


# ── 4 · ARŞİV ─────────────────────────────────────────────────────
def arsiv(baslik) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    baslik("Toto Arşivi", "Geçen haftalar: ne önerdik, ne oldu, ne öğrendik.", [])
    try:
        dersler = toto_db.dersler(20)
        kup = toto_db.kuponlar()
    except Exception:
        dersler, kup = [], []
    if not dersler:
        st.markdown("<div class='v2bos'>Henüz sonuçlanmış Toto haftası yok — ilk hafta kapanınca burada ders yazılır.</div>",
                    unsafe_allow_html=True)
    for d in dersler:
        maclar = "".join(
            f"<tr><td class='rk'>{m['sira']}</td><td>{_e(m['mac'])}</td><td class='n'>{_e(m['sonuc'])}</td>"
            f"<td class='n'>{_pct(m['p'])}</td><td class='n'>{_pct(m['q'])}</td>"
            f"<td class='sb'>{'SÜRPRİZ · ' if m['surpriz'] else ''}{'noter · ' if m['noter'] else ''}"
            f"{_e(', '.join(m['bilen_ajan']) or '—')}</td></tr>" for m in d.get("mac", []))
        _pa = {"15_AVCISI": "15 Avcısı", "DENGELİ": "Dengeli", "FAVORİ": "Favori"}
        kp = "".join(f"<tr><td>{_e(_pa.get(k['profil'], k['profil']))}</td><td class='n'>{k['kolon']}</td><td class='n'>{k['dogru']}</td>"
                     f"<td class='n'>{_tl(k['odeme'])}</td><td class='n'>{_tl(k['maliyet'])}</td></tr>"
                     for k in d.get("kupon", []))
        kal = d.get("kalabalik") or {}
        ek = (f"Kalabalık modeli (sonuç bilinince): 15/14/13/12 kazanan tahmini {kal.get('tahmin')} · gerçek "
              f"{kal.get('gercek')}" if kal else "")
        ozet_satir = "".join(f"<div class='tt-not'>• {_e(x.replace('15_AVCISI', '15 Avcısı').replace('DENGELİ', 'Dengeli').replace('FAVORİ', 'Favori'))}</div>"
                             for x in d.get("ozet", []))
        ust = ozet_satir or f"<div class='tt-not'>Sürpriz sonuç: {d.get('surpriz_sayisi', '—')}. {ek}</div>"
        _kart(f"{_e(d['hafta'])}", ust +
              "<table class='v2' style='margin-top:8px'><thead><tr><th>Profil</th><th>Kolon</th><th>En çok doğru</th>"
              f"<th>Ödeme</th><th>Maliyet</th></tr></thead><tbody>{kp}</tbody></table>"
              "<table class='v2' style='margin-top:8px'><thead><tr><th></th><th>Maç</th><th>Sonuç</th><th>Olasılık</th>"
              f"<th>Kalabalık</th><th>Not · bilen ajan</th></tr></thead><tbody>{maclar}</tbody></table>", "kâğıt kupon")
    try:
        kay = toto_db.son_kayitlar(15)
    except Exception:
        kay = []
    if kay:
        _kart("Olay günlüğü", "".join(f"<div class='sb'>{_e(t[:16])} · {_e(tr)} · {_e(m)}</div>" for t, tr, m in kay))
