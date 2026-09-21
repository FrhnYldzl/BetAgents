"""
HAFTALIK BAKIM · KONTROLLER — BetAgents bahislerinin bütünlük denetimi
=====================================================================
BetAgents tablolarını (paper_bets, paper_coupons) YALNIZ OKUR. Hiçbir şey yazmaz,
hiçbir şeyi düzeltmez — neyin bozuk olduğunu söyler. Düzeltme ayrı bir karardır.

Üç kademe:
  ALARM  sıfır olmalı; değilse hemen bakılır (sonuçlandırma · çift kayıt · oran)
  İZLE   eğilimi takip edilir (bayat · sahipsiz · lig kodu · CLV kapsamı)
  BİLGİ  ajan karnesi (filtre uyumu · istatistik şişmesi)

Sağlık › Defter sekmesini TAMAMLAR: o kupon düzeyinde erken ödemeyi yakalar;
bu dosya bahis düzeyinde her sonucu skordan yeniden hesaplar.
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

_V = Path(__file__).resolve().parent.parent / "02_VERI"
if str(_V) not in sys.path:
    sys.path.insert(0, str(_V))

KIRLI_LIG = {"", "ALL", "UNK", "?", "NONE"}
BAYAT_SAAT = 48
LIG_ESIK = 0.50            # 'ALL' payı bunun üstündeyse SARI
CLV_ESIK = 0.50            # CLV'si ölçülebilen pay bunun altındaysa SARI


# ── yardımcılar ───────────────────────────────────────────────────
def _veri() -> tuple[list[dict], list[dict]]:
    import db
    c = db.connect()
    try:
        b = c.execute(
            "SELECT bet_id, coupon_id, signal_name, league, home_team, away_team, kickoff_utc, market, pick, "
            "odds, implied_prob, model_prob, edge, status, home_score, away_score, clv, closing_odds "
            "FROM paper_bets").fetchall()
        try:
            k = c.execute("SELECT coupon_id, coupon_type, num_legs, combined_odds, status FROM paper_coupons").fetchall()
        except Exception:
            k = []
    finally:
        c.close()
    ab = ["bet_id", "coupon_id", "ajan", "lig", "ev", "dep", "kickoff", "market", "pick", "oran", "ip", "mp",
          "kenar", "durum", "ev_skor", "dep_skor", "clv", "kapanis"]
    ak = ["coupon_id", "tip", "ayak", "oran", "durum"]
    return [dict(zip(ab, x)) for x in b], [dict(zip(ak, x)) for x in k]


def _s1x2(h: int, a: int) -> str:
    return "1" if h > a else ("0" if h == a else "2")


def _ou(h: int, a: int) -> str:
    return "ÜST" if h + a > 2.5 else "ALT"


def _kg(h: int, a: int) -> str:
    return "VAR" if (h > 0 and a > 0) else "YOK"


def tutar_mi(market, pick, h: int, a: int):
    """Seçim bu skorla kazanır mı? Tanınmayan pazar → None (denetim dışı sayılır)."""
    m = str(market or "").upper()
    p = str(pick or "").strip()
    pu = p.upper().replace("X", "0").replace("UST", "ÜST")
    if m == "1X2":
        return _s1x2(h, a) == pu
    if m in ("UST_25", "ALT_25"):
        return _ou(h, a) == pu
    if m in ("KG_VAR", "KG_YOK"):
        return _kg(h, a) == pu
    if m in ("1X2_OU", "1X2_BTTS", "OU_BTTS"):
        parca = [x.strip() for x in re.split(r"\s+VE\s+", p.upper())]
        if len(parca) != 2:
            return None
        sonuc = []
        for x in parca:
            x = x.replace("X", "0").replace("UST", "ÜST")
            if x in ("1", "0", "2"):
                sonuc.append(_s1x2(h, a) == x)
            elif x in ("ALT", "ÜST"):
                sonuc.append(_ou(h, a) == x)
            elif x in ("VAR", "YOK"):
                sonuc.append(_kg(h, a) == x)
            else:
                return None
        return all(sonuc)
    if m == "TOTAL_GOALS":
        t = h + a
        mm = re.match(r"(\d+)\s*-\s*(\d+)", p)
        if mm:
            return int(mm.group(1)) <= t <= int(mm.group(2))
        mm = re.match(r"(\d+)\s*\+", p)
        if mm:
            return t >= int(mm.group(1))
    return None


def _zaman(s) -> datetime | None:
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _mac(b: dict) -> str:
    return f"{(b.get('ev') or '')[:22]} - {(b.get('dep') or '')[:22]}"


def _sonuc(kid, ad, kademe, deger, esik, kotu, aciklama, ornek=None, birim="") -> dict:
    if kademe == "bilgi":
        durum = "bilgi"
    elif kademe == "alarm":
        durum = "kirmizi" if kotu else "yesil"
    else:
        durum = "sari" if kotu else "yesil"
    return {"id": kid, "ad": ad, "kademe": kademe, "deger": deger, "esik": esik, "birim": birim,
            "durum": durum, "aciklama": aciklama, "ornek": (ornek or [])[:8]}


# ── kontroller ────────────────────────────────────────────────────
def k_sonuclandirma(B: list[dict]) -> dict:
    yanlis, denetlenen, taninmayan = [], 0, Counter()
    for b in B:
        if b["durum"] not in ("won", "lost") or b["ev_skor"] is None or b["dep_skor"] is None:
            continue
        t = tutar_mi(b["market"], b["pick"], int(b["ev_skor"]), int(b["dep_skor"]))
        if t is None:
            taninmayan[str(b["market"])] += 1
            continue
        denetlenen += 1
        if t != (b["durum"] == "won"):
            yanlis.append(f"{b['ajan']} · {_mac(b)} · {b['market']} {b['pick']} · skor "
                          f"{b['ev_skor']}-{b['dep_skor']} → kayıt '{b['durum']}'")
    ek = f" Tanınmayan pazar: {dict(taninmayan)}." if taninmayan else ""
    return _sonuc("sonuclandirma", "Sonuçlandırma doğruluğu", "alarm", len(yanlis), 0, bool(yanlis),
                  f"{denetlenen} sonuçlanmış bahis skordan yeniden hesaplandı.{ek} Yanlış sonuç, bütün "
                  "performans ölçülerini (isabet, getiri, ajan sıralaması) sessizce bozar.", yanlis, "bahis")


def k_cift(B: list[dict]) -> dict:
    say = Counter((b["coupon_id"], b["ajan"], b["ev"], b["dep"], str(b["kickoff"])[:10], b["market"], b["pick"])
                  for b in B)
    cift = [(k, v) for k, v in say.items() if v > 1]
    fazla = sum(v - 1 for _, v in cift)
    ornek = [f"×{v} · {k[1]} · {k[2][:20]} - {k[3][:20]} · {k[5]} {k[6]}" for k, v in cift]
    return _sonuc("cift", "Aynı kuponda tekrar eden ayak", "alarm", fazla, 0, fazla > 0,
                  "Aynı ayağın AYNI kuponda birden çok kez yazılması gerçek çift kayıttır. (Aynı ayağın "
                  "farklı kuponlarda olması kombi tasarımıdır — o ayrıca 'istatistik şişmesi'nde izlenir.)",
                  ornek, "kayıt")


def k_oran(B: list[dict]) -> dict:
    kotu = [b for b in B if b["oran"] is None or float(b["oran"] or 0) <= 1.0 or float(b["oran"] or 0) > 1000]
    ornek = [f"{b['ajan']} · {_mac(b)} · {b['market']} {b['pick']} · oran {b['oran']}" for b in kotu]
    return _sonuc("oran", "Geçersiz oran", "alarm", len(kotu), 0, bool(kotu),
                  "Oranı boş, 1,00 ya da altı veya 1000'in üstü olan bahis. Getiri hesabını bozar.", ornek, "bahis")


def k_bayat(B: list[dict], simdi: datetime) -> dict:
    bayat = []
    for b in B:
        if b["durum"] != "open":
            continue
        t = _zaman(b["kickoff"])
        if t and (simdi - t) > timedelta(hours=BAYAT_SAAT):
            bayat.append((simdi - t, b))
    bayat.sort(key=lambda x: -x[0].total_seconds())
    ornek = [f"{d.days} gün · {b['ajan']} · {_mac(b)} · {str(b['kickoff'])[:10]}" for d, b in bayat]
    return _sonuc("bayat", f"Başlamasından {BAYAT_SAAT} saat geçip hâlâ açık", "izle", len(bayat), 0,
                  bool(bayat), "Sonuçlandırma boru hattının kaçırdığı maçlar — çoğu zaman ertelenen ya da "
                  "yarıda kalan maç. Kasada askıda para demektir.", ornek, "bahis")


def k_sahipsiz(B: list[dict]) -> dict:
    s = [b for b in B if not str(b["ajan"] or "").strip()]
    ornek = [f"{_mac(b)} · {b['market']} {b['pick']} · {b['durum']}" for b in s]
    return _sonuc("sahipsiz", "Ajanı boş bahis", "izle", len(s), 0, bool(s),
                  "Kasaya giren ama hiçbir ajanın karnesine girmeyen bahis. Ajan sıralaması bunları görmez.",
                  ornek, "bahis")


def k_lig(B: list[dict]) -> dict:
    n = len(B) or 1
    kirli = [b for b in B if str(b["lig"] or "").strip().upper() in KIRLI_LIG]
    pay = len(kirli) / n
    ornek = [f"{b['ajan']} · {_mac(b)}" for b in kirli[:8]]
    return _sonuc("lig", "Lig kodu 'ALL' ya da boş", "izle", round(pay, 4), LIG_ESIK, pay > LIG_ESIK,
                  "Lig kodu olmayan bahiste lig bazlı hiçbir filtre ve analiz çalışmaz. 'Yalnız büyük ligler' "
                  "diyen bir kural bu bahisleri ayırt EDEMEZ.", ornek, "oran")


def k_clv(B: list[dict]) -> dict:
    kap = [b for b in B if b["durum"] in ("won", "lost")]
    olculen = [b for b in kap if b["clv"] not in (None, 0, 0.0)]
    pay = len(olculen) / (len(kap) or 1)
    return _sonuc("clv", "CLV'si ölçülebilen sonuçlanmış bahis", "izle", round(pay, 4), CLV_ESIK,
                  pay < CLV_ESIK, "CLV (kapanışa göre fiyat üstünlüğü) bir ajanın gerçekten iyi fiyat "
                  "yakalayıp yakalamadığının tek dürüst ölçüsü. Boş ya da sıfır kalan CLV ölçülemeyen demektir. "
                  "CANLI toplayıcı kapanış fiyatını yakaladıkça bu pay artmalı.", [], "oran")


def k_filtre(B: list[dict]) -> dict:
    g = defaultdict(list)
    for b in B:
        if b["oran"] and float(b["oran"]) > 1:
            g[str(b["ajan"] or "(boş)")].append(b)
    satir = []
    for a, v in sorted(g.items(), key=lambda z: -len(z[1])):
        o = sorted(float(x["oran"]) for x in v)
        satir.append({"ajan": a, "bahis": len(v), "en_dusuk": round(o[0], 2),
                      "medyan": round(o[len(o) // 2], 2), "en_yuksek": round(o[-1], 2),
                      "pazar": sorted({str(x["market"]) for x in v})})
    r = _sonuc("filtre", "Ajan filtre uyumu (oran bandı · pazar)", "bilgi", len(satir), None, False,
               "Her ajanın gerçekte hangi oran aralığında ve hangi pazarlarda oynadığı. Adıyla çelişen bir "
               "bant (ör. 'güçlü favori' ama 3,00 üstü oran) filtre sızıntısıdır.")
    r["tablo"] = satir
    return r


def k_sisme(B: list[dict]) -> dict:
    satir, g = [], defaultdict(lambda: [0, set()])
    for b in B:
        if b["durum"] in ("won", "lost"):
            k = (b["ev"], b["dep"], str(b["kickoff"])[:10], b["market"], b["pick"])
            g[str(b["ajan"] or "(boş)")][0] += 1
            g[str(b["ajan"] or "(boş)")][1].add(k)
    for a, (n, s) in sorted(g.items(), key=lambda z: -z[1][0]):
        satir.append({"ajan": a, "satir": n, "tekil": len(s), "sisme": round(n / len(s), 3) if s else 1.0})
    en = max((x["sisme"] for x in satir), default=1.0)
    r = _sonuc("sisme", "Ajan istatistiği şişmesi", "bilgi", en, None, False,
               "Aynı ayak hem tekli hem kombi kupona girince her kuponda ayrı sayılır. Kombi tasarımının "
               "doğal sonucu — ama ajanın isabet ve getirisi tekrarlı gözlemle hesaplanır, örneklem olduğundan "
               "büyük görünür. ×1,20 = gözlemlerin beşte biri tekrar.")
    r["tablo"] = satir
    return r


def kos(simdi: datetime | None = None) -> dict:
    """Bütün kontrolleri çalıştır. Hiçbir şey yazmaz; sonucu döndürür."""
    simdi = simdi or datetime.now(timezone.utc)
    B, _K = _veri()
    sonuclar = [k_sonuclandirma(B), k_cift(B), k_oran(B), k_bayat(B, simdi), k_sahipsiz(B), k_lig(B), k_clv(B),
                k_filtre(B), k_sisme(B)]
    return {"ts": simdi.isoformat(timespec="seconds"), "bahis": len(B),
            "kirmizi": sum(1 for x in sonuclar if x["durum"] == "kirmizi"),
            "sari": sum(1 for x in sonuclar if x["durum"] == "sari"),
            "yesil": sum(1 for x in sonuclar if x["durum"] == "yesil"),
            "kontroller": sonuclar}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    R = kos()
    print(f"bahis {R['bahis']} · kırmızı {R['kirmizi']} · sarı {R['sari']} · yeşil {R['yesil']}\n")
    for x in R["kontroller"]:
        isaret = {"kirmizi": "🔴", "sari": "🟡", "yesil": "🟢", "bilgi": "🔵"}[x["durum"]]
        print(f"{isaret} {x['ad']:48s} {x['deger']}")
        for o in x["ornek"][:3]:
            print(f"      {o}")
