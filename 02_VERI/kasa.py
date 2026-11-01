"""
KASA — değerlendirme ile tahsisi AYIR
======================================
Bugüne kadar tek sayı iki işi birden yapıyordu: `current_bankroll` hem
ajanın karnesiydi hem de sermayesi. Bu iki SORU birbirinden bağımsız:

    DEĞERLENDİRME   bu ajan iyi mi?        → ölçüm, belirsizliğiyle birlikte
    TAHSİS          ne kadar yatırayım?    → ölçümden + risk sınırlarından

Karıştırınca ikisi de bozuluyor: iyi giden ajana para akıyor (karne sermaye
sanılıyor), kadro dışı devri yüzdeyi bozuyor, ve "ne kadar yatırayım"
sorusunun cevabı "geçen hafta ne kazandı"ya indirgeniyor.

TEK ANLAMLI EŞİK: isabet > 1 / oran
-----------------------------------
"%70 isabet" bir eşik DEĞİL. Ölçüldü (01.11.2026):
    TEMKİNLİ  %78,9 isabet · ort. oran 1,24 · başabaş için gerek %80,5 → -%2,1
    EUVOX     %74,7 isabet · ort. oran 1,30 · gerek %76,8              → -%2,8
    KURUCU    %67,3 isabet · ort. oran 1,25 · gerek %80,1              → -%16,1
Yüksek isabet, kısa oranla alındığında kasayı eritir. Kalabalıktan ayrılma
fikri de parimutuel (Toto) oyunlara aittir; iddaa'da havuz paylaşılmadığı
için ayrışmanın değeri yoktur — tek değerli şey İSABETTİR.

PARA KANITI TAKİP EDER
----------------------
Bahis büyüklüğü güvene değil ÖLÇÜLEN kenara bağlanır ve kenarın ALT GÜVEN
SINIRI kullanılır. Nokta tahmini kullanmak, gürültüyü kenar sanıp parayı
oraya yığmaktır — bu projede defalarca olduğu gibi.

    kenar      = isabet − 1/oran
    alt sınır  = kenar − 1,96 · standart hata        (n küçükse çok negatif)
    Kelly f    = (p·o − 1) / (o − 1)   ·  p = alt sınır ile düzeltilmiş isabet
    bahis      = bankroll × f × KESIR, tavanla sınırlı

Alt sınır sıfırın altındaysa ajan ÖLÇÜM BAHSİ oynar: en küçük birim, yalnız
veri biriksin diye. Kanıt gelince para kendiliğinden açılır.
"""
from __future__ import annotations

import math

# Kelly'nin tamamı teoride en hızlı büyüme, pratikte iflas riski: model
# hatası varsa tam Kelly fazla yatırır. Çeyrek Kelly yaygın ve dayanıklı.
KESIR = 0.25
# Tek bahis kasanın bu kadarını geçemez — ölçüm hatası ne olursa olsun.
TAVAN_PAY = 0.02
# Kanıtı olmayan ajanın ölçüm bahsi (kasa payı).
OLCUM_PAY = 0.002
# Bu kadar karar altında hiçbir kenar tahmini ciddiye alınmaz.
ASGARI_N = 30


def _se(p: float, n: int) -> float:
    """İsabet oranının standart hatası."""
    if n <= 1:
        return 0.5
    return math.sqrt(max(p * (1.0 - p), 1e-9) / n)


def degerlendir(n: int, kazanan: int, ort_oran: float) -> dict:
    """AJAN DEĞERLENDİRMESİ — para yok, yalnız ölçüm.

    Dönen 'kenar_alt' kararın dayanağıdır; 'kenar' tek başına gürültü olabilir.
    """
    if not n or ort_oran <= 1.0:
        return {"n": n, "yeterli": False}
    p = kazanan / n
    basabas = 1.0 / ort_oran
    kenar = p - basabas
    se = _se(p, n)
    return {
        "n": n, "isabet": p, "ort_oran": ort_oran,
        "basabas": basabas, "kenar": kenar, "se": se,
        "kenar_alt": kenar - 1.96 * se,
        "kenar_ust": kenar + 1.96 * se,
        "yeterli": n >= ASGARI_N,
        # birim getiri: p·(o−1) − (1−p) = p·o − 1
        "birim_getiri": p * ort_oran - 1.0,
    }


def tahsis(d: dict, bankroll: float, oran: float | None = None) -> dict:
    """TAHSİS — değerlendirmeden bahis büyüklüğü.

    `oran` verilirse O bahsin oranı kullanılır (doğrusu budur: Kelly bahsin
    kendi oranına bağlıdır). Verilmezse ajanın ortalaması.
    """
    o = float(oran or d.get("ort_oran") or 0)
    if bankroll <= 0 or o <= 1.0:
        return {"pay": 0.0, "tutar": 0.0, "gerekce": "geçersiz oran ya da kasa"}
    if not d.get("yeterli"):
        return {"pay": OLCUM_PAY, "tutar": bankroll * OLCUM_PAY,
                "gerekce": f"ölçüm bahsi — {d.get('n', 0)} karar, "
                           f"{ASGARI_N} gerekiyor"}
    # Alt güven sınırıyla düzeltilmiş isabet varsayımı
    p_alt = min(0.999, max(0.001, (1.0 / o) + d["kenar_alt"]))
    f = (p_alt * o - 1.0) / (o - 1.0)
    if f <= 0:
        return {"pay": OLCUM_PAY, "tutar": bankroll * OLCUM_PAY,
                "gerekce": f"kenar alt sınırı {d['kenar_alt']:+.3f} ≤ 0 — "
                           f"kanıt yok, ölçüm bahsi"}
    pay = min(TAVAN_PAY, f * KESIR)
    return {"pay": pay, "tutar": bankroll * pay, "kelly": f,
            "gerekce": f"kenar alt sınırı {d['kenar_alt']:+.3f} · "
                       f"çeyrek Kelly {f * KESIR:.4f}"
                       + (" · TAVAN" if f * KESIR > TAVAN_PAY else "")}


# ----------------------------------------------------------------------
# DEFTERDEN OKU
# ----------------------------------------------------------------------
def ajan_karneleri(conn=None, era_ici: bool = True) -> list[dict]:
    """Her ajanın değerlendirmesi — bahis defterinden, kasa alanlarından DEĞİL.

    Kasa alanları kadro dışı devirleriyle bozuluyor (ölçüldü: EUVOX +232 TL
    kârdayken defterde -%100 görünüyordu). Bahis defteri bozulmaz.
    """
    import db
    kapat = conn is None
    conn = conn or db.connect()
    try:
        ek = ("AND (pp.era_start IS NULL OR pb.bet_id IN "
              "  (SELECT pb2.bet_id FROM paper_bets pb2 "
              "   JOIN paper_coupons pc2 ON pc2.coupon_id = pb2.coupon_id "
              "   WHERE pc2.created_at >= pp.era_start)) " if era_ici else "")
        r = conn.execute(
            "SELECT pb.portfolio_id, COUNT(*), "
            "SUM(CASE WHEN pb.status='won' THEN 1 ELSE 0 END), AVG(pb.odds), "
            "AVG(COALESCE(pb.clv,0)) "
            "FROM paper_bets pb "
            "LEFT JOIN paper_portfolio pp ON pp.portfolio_id = pb.portfolio_id "
            "WHERE pb.status IN ('won','lost') AND pb.odds > 1.01 " + ek +
            "GROUP BY pb.portfolio_id").fetchall()
    finally:
        if kapat:
            conn.close()
    out = []
    for pid, n, kaz, o, clv in r:
        d = degerlendir(int(n or 0), int(kaz or 0), float(o or 0))
        d["ajan"] = pid
        d["clv"] = float(clv or 0)
        out.append(d)
    return sorted(out, key=lambda x: -(x.get("kenar_alt") or -9))


def kendi_testi() -> list[str]:
    hata = []
    # 1) Yüksek isabet + kısa oran = kaybeden. Eşik testi.
    d = degerlendir(1000, 790, 1.24)            # %79 isabet, 1,24 oran
    if d["birim_getiri"] >= 0:
        hata.append(f"%79 isabet 1,24 oranda kârlı görünüyor ({d['birim_getiri']:+.3f})")
    if d["kenar"] >= 0:
        hata.append("kenar artı çıktı — 1/1,24 = %80,6, isabet %79")
    # 2) Kanıt yoksa ölçüm bahsi
    t = tahsis(degerlendir(5, 4, 1.50), 1000.0)
    if abs(t["pay"] - OLCUM_PAY) > 1e-9:
        hata.append(f"n=5'te ölçüm bahsi beklenirdi, pay={t['pay']}")
    # 3) Gerçek kenar varsa para açılır ve tavanı aşmaz
    d2 = degerlendir(2000, 1200, 2.00)          # %60 isabet, 2,00 oran → kenar +%10
    t2 = tahsis(d2, 1000.0)
    if t2["pay"] <= OLCUM_PAY:
        hata.append(f"gerçek kenarda para açılmadı: {t2}")
    if t2["pay"] > TAVAN_PAY + 1e-9:
        hata.append(f"tavan aşıldı: {t2['pay']}")
    # 4) Alt sınır kullanılıyor mu — aynı kenar, küçük n daha az yatırmalı
    a = tahsis(degerlendir(50, 30, 2.00), 1000.0)["pay"]
    b = tahsis(degerlendir(2000, 1200, 2.00), 1000.0)["pay"]
    if not (a < b):
        hata.append(f"küçük örneklem daha AZ yatırmalıydı (n=50 {a} vs n=2000 {b})")
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
    print("\nÖRNEK — 1.000 TL kasa")
    print(f"{'durum':34} {'kenar':>7} {'alt sınır':>10} {'bahis':>8}  gerekçe")
    print("-" * 94)
    for ad, n, k, o in (("%79 isabet · oran 1,24 (TEMKİNLİ gibi)", 1000, 790, 1.24),
                        ("%75 isabet · oran 1,30 (EUVOX gibi)", 1000, 750, 1.30),
                        ("%60 isabet · oran 2,00 (gerçek kenar)", 2000, 1200, 2.00),
                        ("%60 isabet · oran 2,00 ama n=50", 50, 30, 2.00),
                        ("%88 isabet · oran 1,25 · n=32", 32, 28, 1.25)):
        d = degerlendir(n, k, o)
        t = tahsis(d, 1000.0)
        print(f"{ad:34} {d['kenar']:+7.3f} {d['kenar_alt']:+10.3f} "
              f"{t['tutar']:8.0f}  {t['gerekce'][:44]}")
