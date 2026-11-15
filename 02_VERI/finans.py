"""
FİNANS AJANI — planı işletir, durumu söyler, disiplini takip eder
===================================================================
Kullanıcı (15.11.2026): *"Bu projeyi yönlendiren, durumu belirten,
geri bildirimler veren bir agent olmalı finansal açıdan."*

Kupon üretmez. Üç soruyu cevaplar:
  1. NEREDEYİZ   rolling p, yield, aylık hedefe göre durum
  2. DUR MU      kill-switch eşikleri
  3. NE YAPMALI  stake, çekim, masada kalacak bankroll

PLANIN PARAMETRELERİ — Excel'den (Iddaa_Bet_Agent_2027_Proje_Plani)
--------------------------------------------------------------------
Plan p=0,90 · o=1,80 · yield=%62 varsayıyordu. ÖLÇÜLDÜ (15.11.2026,
2.533 sonuçlanmış kupon):

    plan bandında (1,60-2,00)  n=758  p=0,4934  ROI −%12,6  (z=−3,98)
    defterin tamamı            n=2533 p=0,4335  ROI −%19,3

Fark 41 puan. Bu yüzden `p` ve `yield` burada ELLE GİRİLMEZ, DEFTERDEN
ÖLÇÜLÜR. Plan bir temenni değil, ölçüm aleti olsun diye.

⚠️ PLANIN KENDİ KURALI ZATEN DURDURUYOR
K-S2: "son 40 kuponda p < %70 → DUR". Ölçülen p %49. Yani planın kendi
güvenlik kuralı, bugünkü veriyle oyunu durdurur. Bu modül o kuralı
sadakatle uygular — yumuşatmaz.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

# ── Plandan gelen sabitler (Excel · Parametreler sayfası) ────────────
GUVENLIK_PAYI = 1.15        # stake çarpanı
BANKROLL_KATSAYI = 10       # masada tutulacak = stake × bu
KS1_PENCERE, KS1_ESIK = 20, 0.75   # p < %75 → stake yarıya
KS2_PENCERE, KS2_ESIK = 40, 0.70   # p < %70 → DUR
VERGI_ORANI = 0.20

DUR, YAVASLA, DEVAM = "DUR", "YAVAŞLA", "DEVAM"


def _son_n(kapanan: list[dict], n: int) -> list[dict]:
    return kapanan[-n:] if len(kapanan) >= n else []


def kill_switch(kapanan: list[dict]) -> dict:
    """Planın iki kademeli güvenlik kuralı — yumuşatılmadan.

    kapanan: eskiden yeniye sıralı [{"kazandi": bool}, ...]
    """
    s1 = _son_n(kapanan, KS1_PENCERE)
    s2 = _son_n(kapanan, KS2_PENCERE)
    p1 = (sum(1 for x in s1 if x["kazandi"]) / len(s1)) if s1 else None
    p2 = (sum(1 for x in s2 if x["kazandi"]) / len(s2)) if s2 else None
    durum, sebep = DEVAM, "eşiklerin üstünde"
    if p2 is not None and p2 < KS2_ESIK:
        durum = DUR
        sebep = (f"K-S2: son {KS2_PENCERE} kuponda p=%{p2*100:.1f} "
                 f"< %{KS2_ESIK*100:.0f} → DUR, model yeniden kalibre")
    elif p1 is not None and p1 < KS1_ESIK:
        durum = YAVASLA
        sebep = (f"K-S1: son {KS1_PENCERE} kuponda p=%{p1*100:.1f} "
                 f"< %{KS1_ESIK*100:.0f} → stake YARIYA")
    elif p2 is None and p1 is None:
        sebep = f"henüz {KS1_PENCERE} kapanmış kupon yok — ölçüm bekliyor"
    return {"durum": durum, "sebep": sebep, "p20": p1, "p40": p2,
            "n": len(kapanan)}


def stake_hesapla(hedef_kar: float, kupon_sayisi: int, yield_: float) -> dict:
    """Plan formülü: stake = hedef ÷ (kupon × yield) × güvenlik payı.

    ⚠️ yield ARTI DEĞİLSE stake hesaplanamaz. Eksi yield'de formül
    negatif ya da anlamsız stake üretir; "ne kadar oynayayım" sorusunun
    cevabı o durumda bir sayı değil, "oynama"dır. Sessizce bir sayı
    döndürmek, kaybeden bir sisteme para ölçmek olurdu.
    """
    if yield_ <= 0:
        return {"stake": 0.0, "bankroll": 0.0, "gecerli": False,
                "sebep": f"ölçülen yield {yield_*100:+.1f}% — artı değil. "
                         f"Stake formülü geçersiz; hedef kâr bu sistemle "
                         f"matematiksel olarak tutturulamaz."}
    if kupon_sayisi <= 0:
        return {"stake": 0.0, "bankroll": 0.0, "gecerli": False,
                "sebep": "kupon sayısı sıfır"}
    stake = hedef_kar / (kupon_sayisi * yield_) * GUVENLIK_PAYI
    return {"stake": stake, "bankroll": stake * BANKROLL_KATSAYI,
            "gecerli": True,
            "sebep": f"hedef {hedef_kar:,.0f} ÷ ({kupon_sayisi} × "
                     f"{yield_:.3f}) × {GUVENLIK_PAYI}"}


def durum(conn=None, hedef_kar: float = 0.0, kupon_sayisi: int = 0) -> dict:
    """Tam finansal durum — defterden ölçülmüş."""
    import ferhan_kupon as FK
    kapat = conn is None
    import db
    conn = conn or db.connect()
    try:
        FK.kur(conn)
        r = conn.execute(
            "SELECT durum, COALESCE(gercek_bahis, bahis, ?), oran, "
            "       COALESCE(sonuc_ts, uretim_ts) "
            "FROM ferhan_kupon WHERE oynandi = 1 "
            "AND durum IN ('kazandi','kaybetti') "
            "ORDER BY COALESCE(sonuc_ts, uretim_ts)", (FK.BAHIS,)).fetchall()
        para = FK.para_karnesi(conn)
    finally:
        if kapat:
            conn.close()
    kapanan = [{"kazandi": d == "kazandi", "bahis": float(b or 0),
                "oran": float(o or 0)} for d, b, o, _ in r]
    ks = kill_switch(kapanan)
    # Ölçülen yield: gerçekleşen kâr / ciro
    yatan = sum(x["bahis"] for x in kapanan)
    kar = sum((x["bahis"] * x["oran"] - x["bahis"]) if x["kazandi"]
              else -x["bahis"] for x in kapanan)
    ol_yield = (kar / yatan) if yatan else 0.0
    p = (sum(1 for x in kapanan if x["kazandi"]) / len(kapanan)
         ) if kapanan else 0.0
    st = stake_hesapla(hedef_kar, kupon_sayisi, ol_yield) if hedef_kar else {
        "stake": 0.0, "bankroll": 0.0, "gecerli": False,
        "sebep": "hedef girilmedi"}
    return {"kill_switch": ks, "p": p, "yield": ol_yield,
            "yatan": yatan, "kar": kar, "n": len(kapanan),
            "stake": st, "defter": para,
            "vergi_tahmini": max(0.0, kar) * VERGI_ORANI}


def tavsiye(d: dict) -> list[str]:
    """İnsan diliyle ne yapılmalı — abartısız, ölçüme dayalı."""
    out = []
    ks = d["kill_switch"]
    if ks["durum"] == DUR:
        out.append(f"🛑 DUR — {ks['sebep']}")
    elif ks["durum"] == YAVASLA:
        out.append(f"⚠️ STAKE YARIYA — {ks['sebep']}")
    else:
        out.append(f"✅ {ks['sebep']}")
    if d["n"] == 0:
        out.append("Henüz oynanmış ve kapanmış kupon yok. Defterde öneri "
                   f"{d['defter']['oneri']}, işaretsiz "
                   f"{d['defter']['isaretsiz']} — işaretlemeden muhasebe "
                   f"başlamaz.")
        return out
    out.append(f"Ölçülen: {d['n']} kupon · p=%{d['p']*100:.1f} · "
               f"yield {d['yield']*100:+.1f}% · "
               f"kâr {d['kar']:+,.0f} ₺ / ciro {d['yatan']:,.0f} ₺")
    if not d["stake"]["gecerli"]:
        out.append(f"Stake hesaplanamıyor: {d['stake']['sebep']}")
    else:
        out.append(f"Plan stake'i: {d['stake']['stake']:,.0f} ₺ · "
                   f"masada kalması gereken "
                   f"{d['stake']['bankroll']:,.0f} ₺")
    if d["kar"] > 0:
        out.append(f"Kâr realizasyonu: {d['kar']:,.0f} ₺ kâr var, vergi "
                   f"tahmini {d['vergi_tahmini']:,.0f} ₺. Ay sonunda "
                   f"hedef kârı ÇEK, yalnız bankroll masada kalsın.")
    return out


def kendi_testi() -> list[str]:
    hata = []
    # 1) Kill-switch eşikleri
    kayip40 = [{"kazandi": False}] * 40
    if kill_switch(kayip40)["durum"] != DUR:
        hata.append("40 kayıpta DUR demedi")
    # SINIR: 28/40 = tam %70. Eşik "< %70" olduğu için K-S2
    # TETİKLENMEMELİ. (İlk yazımda bu vaka DUR bekliyordu ve test kaldı —
    # beklenti yanlıştı, eşik sınırı dışlayıcı.)
    tam70 = [{"kazandi": True}] * 28 + [{"kazandi": False}] * 12
    r70 = kill_switch(tam70)
    if r70["durum"] == DUR:
        hata.append("p tam %70 iken DUR dedi — eşik dışlayıcı olmalı")
    if r70["durum"] != YAVASLA:
        hata.append(f"son 20'de %40 iken K-S1 beklenirdi, {r70['durum']}")
    # Eşiğin ALTI: 27/40 = %67,5 → DUR
    alt70 = [{"kazandi": True}] * 27 + [{"kazandi": False}] * 13
    if kill_switch(alt70)["durum"] != DUR:
        hata.append("p %67,5 iken DUR demedi")
    iyi = [{"kazandi": True}] * 40
    if kill_switch(iyi)["durum"] != DEVAM:
        hata.append("hepsi kazançken DEVAM demedi")
    az = [{"kazandi": True}] * 5
    if kill_switch(az)["durum"] != DEVAM:
        hata.append("örneklem azken DUR dedi — eşik yok, ölçüm bekler")
    # 2) K-S1 yalnız: son 20 düşük, son 40 eşiğin üstünde
    #    20 kayıp + 20 kazanç sırayla → son20 p=1,0 olur; ters kur
    k = [{"kazandi": True}] * 24 + [{"kazandi": False}] * 6 + \
        [{"kazandi": True}] * 10
    r = kill_switch(k)
    if r["durum"] == DUR:
        hata.append("K-S2 eşiği aşılmadığı hâlde DUR dedi")
    # 3) Eksi yield'de stake hesaplanmamalı
    s = stake_hesapla(10000, 60, -0.126)
    if s["gecerli"] or s["stake"] != 0:
        hata.append("eksi yield'de stake üretildi — kaybeden sisteme "
                    "para ölçülmemeli")
    # 4) Artı yield'de plan formülü
    s2 = stake_hesapla(10000, 60, 0.62)
    bek = 10000 / (60 * 0.62) * GUVENLIK_PAYI
    if not s2["gecerli"] or abs(s2["stake"] - bek) > 1e-6:
        hata.append(f"stake formülü yanlış: {s2['stake']:.2f} ≠ {bek:.2f}")
    if abs(s2["bankroll"] - bek * BANKROLL_KATSAYI) > 1e-6:
        hata.append("bankroll katsayısı uygulanmadı")
    # 5) Sıfır kupon
    if stake_hesapla(1000, 0, 0.5)["gecerli"]:
        hata.append("kupon sayısı sıfırken stake üretildi")
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
