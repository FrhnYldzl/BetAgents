"""
ADİL TABAN — marjsız karşılaştırma, İKİ YÖNTEMLE birden
=========================================================
Kullanıcı isteği 15.11.2026: takım araştırması ve iyileştirme.

⚠️ BU MODÜLÜN VAR OLMA SEBEBİ — 15.11.2026'da ölçüldü:
Ajan karnesini `1/oran`a göre okumak HERKESİ eksi gösteriyordu
(−8..−12p). Sebep beceri yokluğu değil, `1/oran`ın MARJ içermesi:
rastgele seçen biri bile marj kadar geride çıkar. Yani "fark" sütununun
nötr noktası sıfır değil.

Marj çıkarılınca tablo değişiyor — ama NASIL çıkarıldığına bağlı olarak
ZIT yönde değişiyor:

    takım mavi (n=899, favori ağırlıklı, ort oran 1,54)
        oransal de-vig  → +0,8p  (z=+0,46)
        üs (power)      → −1,8p  (z=−1,16)

Oransal yöntem marjı bütün seçimlere EŞİT dağıtır. Oysa bahis şirketi
uzun şanslardan daha çok marj alır; bu yüzden oransal yöntem favoriye
fazla olasılık verir ve FAVORİ OYNAYAN AJANI HAKSIZ YERE İYİ GÖSTERİR.

Bu yüzden tek yöntemle verilen "ajan kenarı var" hükmü, bulgunun değil
YÖNTEMİN sonucudur. Modül ikisini birden hesaplar ve hüküm verirken
İKİSİNİN DE aynı yöne bakmasını şart koşar.

Ölçülen marjlar (market_odds, tam kitaplar, 15.11.2026):
    1X2 %17,0 · OU2.5 %16,9 · OU1.5 %16,6 · OU3.5 %16,9
    HT_OU0.5 %16,4 · BTTS ~%17 · DC %17,8 · Handikap %23,2-23,3
Handikap pazarı diğerlerinin 6 puan üstünde — aynı beceri orada
kârlılığa çok daha uzak.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.append(str(THIS_DIR))

# pazar -> (kitaptaki seçim sayısı, kapsama çarpanı)
# ⚠️ ÇARPAN ŞART. Çifte Şans'ın üç seçimi (1X, 12, X2) her sonucu İKİ KEZ
# kapsar; gerçek olasılıkların toplamı 1 değil 2'dir. Bu bölme yapılmazsa
# DC marjı %45 çıkıyor (ölçüldü) ve Çifte Şans oynayan takım sahte olarak
# +22,7p görünüyor.
KITAP_KURALI = {
    "1X2": (3, 1.0),
    "OU2.5": (2, 1.0), "OU1.5": (2, 1.0), "OU3.5": (2, 1.0),
    "HT_OU1.5": (2, 1.0), "HT_OU0.5": (2, 1.0),
    "BTTS": (2, 1.0),
    "DC": (3, 2.0),
    "HC-1": (3, 1.0), "HC+1": (3, 1.0), "HC-2": (3, 1.0),
}

# paper_bets.market -> market_odds.market
PAZAR_ESLEME = {
    "1X2": "1X2", "UST_25": "OU2.5", "ALT_25": "OU2.5",
    "ALT_UST": "OU2.5", "KG_VAR": "BTTS", "KG_YOK": "BTTS",
    "CIFTE_SANS": "DC",
}

MAKUL_ALT, MAKUL_UST = 1.05, 1.30      # overround denetim aralığı
ASGARI_KITAP = 50                      # marj için en az bu kadar kitap


def us_katsayisi(tersler: list[float], carpan: float = 1.0) -> float:
    """sum((1/o)^k) = çarpan olacak k — ikili arama.

    k > 1 çıkar ve favoriye DAHA FAZLA olasılık verir; bu yüzden favori
    oynayan ajanın farkı bu yöntemde KÜÇÜLÜR.
    """
    if not tersler:
        return 1.0
    lo, hi = 0.3, 4.0
    for _ in range(60):
        k = (lo + hi) / 2
        s = sum(x ** k for x in tersler)
        if s > carpan:
            lo = k
        else:
            hi = k
    return (lo + hi) / 2


def marjlar(conn) -> dict:
    """Pazar başına ölçülen overround. Eksik kitaplar sayılmaz.

    Eksik kitabı saymak marjı olduğundan DÜŞÜK gösterir (eksik seçimin
    olasılığı toplamdan düşer) ve her ajanı haksız yere iyi gösterir.
    """
    kitap: dict = defaultdict(float)
    adet: dict = defaultdict(int)
    for ev, mkt, sov, odd, ts in conn.execute(
            "SELECT iddaa_event_id, market, sov, odd, ts "
            "FROM market_odds WHERE odd > 1").fetchall():
        if str(mkt) not in KITAP_KURALI:
            continue
        k = (str(ev), str(mkt), str(sov), str(ts))
        kitap[k] += 1.0 / float(odd)
        adet[k] += 1
    toplam: dict = defaultdict(list)
    for k, s in kitap.items():
        bek, carpan = KITAP_KURALI[k[1]]
        if adet[k] == bek:
            toplam[k[1]].append(s / carpan)
    out = {}
    for mkt, L in toplam.items():
        if len(L) < ASGARI_KITAP:
            continue
        o = sum(L) / len(L)
        if MAKUL_ALT <= o <= MAKUL_UST:
            out[mkt] = {"overround": o, "marj": o - 1.0, "kitap": len(L)}
    return out


def _karar(f_oransal: float, z_oransal: float,
           f_us: float, z_us: float, esik: float = 2.0) -> str:
    """İKİ YÖNTEM DE aynı yöne bakmadan hüküm verilmez."""
    if z_oransal <= -esik and z_us <= -esik:
        return "FİYATIN GERİSİNDE"
    if z_oransal >= esik and z_us >= esik:
        return "FİYATI YENİYOR"
    if (f_oransal > 0) != (f_us > 0):
        return "YÖNTEME BAĞLI — hüküm yok"
    return "ayırt edilemiyor"


def degerlendir(kayitlar: list[dict]) -> dict:
    """kayitlar: [{"p_oransal", "p_us", "kazandi"}] → iki taban, iki z.

    Not: beklenen isabeti aşmak KÂRLILIK DEĞİLDİR. Kâr için OFERE EDİLEN
    fiyatı (ham 1/oran) geçmek gerekir; adil tabanı geçmek yalnız
    "seçimlerde bilgi var" demektir. İkisi karıştırılırsa marjı
    kapatamayan bir sistem kârlı sanılır.
    """
    n = len(kayitlar)
    if not n:
        return {"n": 0, "karar": "veri yok"}
    p = sum(1 for x in kayitlar if x["kazandi"]) / n

    def hesap(alan):
        t = sum(x[alan] for x in kayitlar) / n
        var = sum(x[alan] * (1 - x[alan]) for x in kayitlar)
        se = (var ** 0.5) / n if var > 0 else 0.0
        return t, p - t, ((p - t) / se if se else 0.0)

    t1, f1, z1 = hesap("p_oransal")
    t2, f2, z2 = hesap("p_us")
    return {"n": n, "isabet": p,
            "taban_oransal": t1, "fark_oransal": f1, "z_oransal": z1,
            "taban_us": t2, "fark_us": f2, "z_us": z2,
            "karar": _karar(f1, z1, f2, z2)}


# ──────────────────────────────────────────────────────────────────
# AMPİRİK TABAN — projenin kendi reçetesi
# ──────────────────────────────────────────────────────────────────
# ⚠️ ÜÇÜNCÜ VE EN GÜVENİLİR ÖLÇÜ. Yukarıdaki iki de-vig yöntemi ZITT
# yönde yanlı: oransal favoriyi kayırır, üs cezalandırır. İkisi de
# TEORİK olasılık üretiyor ve favori-uzunşans yanlılığı marj
# çıkarıldıktan SONRA bile duruyor (ölçüldü 25.09.2026: üs yöntemi
# %78-85 bandında %81,1 derken gerçek %74,2).
#
# Yöntemsiz ölçü: aynı oran kovasında DEFTERİN KENDİ gerçekleşen oranı,
# ölçülen ajan dışarıda bırakılarak. "Aynı fiyata oynayan diğerlerinden
# iyi misin?" — bu sorunun cevabı hiçbir de-vig varsayımına dayanmaz.
#
# ⚠️ NE ÖLÇER, NE ÖLÇMEZ: GÖRELİ beceri ölçer, KÂRLILIK ölçmez. Defterin
# tamamı fiyatın gerisindeyse, tabanı geçen ajan hâlâ para kaybediyor
# olabilir. İkisini karıştırmak marjı kapatamayan sistemi kârlı sanmaktır.
KOVA_GENISLIGI = 0.05
KOVA_ASGARI = 12


def _kova(oran: float) -> float:
    return round(float(oran) / KOVA_GENISLIGI) * KOVA_GENISLIGI


def ampirik_taban(bahisler: list[dict], uyeler: set) -> dict:
    """bahisler: [{"ajan","oran","kazandi"}] · uyeler: ölçülecek ajanlar.

    Taban, AYNI kovadaki `uyeler` DIŞINDAKİ bahislerin gerçekleşen oranı.
    """
    kovalar: dict = defaultdict(list)
    for b in bahisler:
        kovalar[_kova(b["oran"])].append(
            (str(b["ajan"]), 1 if b["kazandi"] else 0))
    t_f = t_n = t_taban = 0.0
    kullanilan = 0
    for L in kovalar.values():
        ic = [w for a, w in L if a in uyeler]
        dis = [w for a, w in L if a not in uyeler]
        if len(ic) < KOVA_ASGARI or len(dis) < KOVA_ASGARI:
            continue
        p_ic = sum(ic) / len(ic)
        p_dis = sum(dis) / len(dis)
        t_f += (p_ic - p_dis) * len(ic)
        t_taban += p_dis * len(ic)
        t_n += len(ic)
        kullanilan += 1
    if not t_n:
        return {"n": 0, "kova": 0, "karar": "ortak kova yok"}
    f = t_f / t_n
    se = (0.25 / t_n + 0.25 / max(sum(
        len([1 for a, w in L if a not in uyeler])
        for L in kovalar.values()), 1)) ** 0.5
    z = f / se if se else 0.0
    return {"n": int(t_n), "kova": kullanilan, "taban": t_taban / t_n,
            "fark": f, "z": z,
            "karar": ("AYNI FİYATTA DAHA İYİ" if z >= 2.0 else
                      ("AYNI FİYATTA DAHA KÖTÜ" if z <= -2.0
                       else "ayırt edilemiyor"))}


def kendi_testi() -> list[str]:
    hata = []
    # 1) Üs katsayısı: marjlı kitapta k>1 olmalı
    ters = [1.0 / 1.45, 1.0 / 4.0, 1.0 / 5.5]
    k = us_katsayisi(ters, 1.0)
    if not (k > 1.0):
        hata.append(f"marjlı kitapta üs katsayısı 1'den büyük olmalı: {k}")
    if abs(sum(x ** k for x in ters) - 1.0) > 1e-6:
        hata.append("üs katsayısı olasılıkları 1'e toplamıyor")
    # 2) ⚠️ ASIL TUZAK: üs yöntemi FAVORİYE daha çok olasılık vermeli.
    #    Vermiyorsa favori oynayan ajan oransal yöntemde haksız yere iyi
    #    görünür ve bu modül amacını kaybeder.
    ov = sum(ters)
    p_oran_fav = ters[0] / ov
    p_us_fav = ters[0] ** k
    if not (p_us_fav > p_oran_fav):
        hata.append("üs yöntemi favoriye daha çok olasılık vermiyor — "
                    "favori yanlılığı sınanamaz")
    # uzun şansta tersi olmalı
    if not (ters[-1] ** k < ters[-1] / ov):
        hata.append("üs yöntemi uzun şansa daha az olasılık vermiyor")
    # 3) Çifte Şans çarpanı: 2'ye bölünmezse marj şişer
    bek, carpan = KITAP_KURALI["DC"]
    if carpan != 2.0:
        hata.append("DC kapsama çarpanı 2 olmalı (her seçim 2 sonucu kapsar)")
    # 4) Karar: tek yöntem yetmez
    if _karar(0.05, 3.0, -0.02, -1.0) != "YÖNTEME BAĞLI — hüküm yok":
        hata.append("zıt yönlü yöntemlerde hüküm verildi")
    if _karar(0.05, 3.0, 0.04, 2.5) != "FİYATI YENİYOR":
        hata.append("iki yöntem de artıyken hüküm verilmedi")
    if _karar(-0.05, -3.0, -0.08, -5.3) != "FİYATIN GERİSİNDE":
        hata.append("iki yöntem de eksiyken hüküm verilmedi")
    if _karar(0.05, 3.0, 0.04, 1.0) != "ayırt edilemiyor":
        hata.append("tek yöntemde anlamlı olan 'yeniyor' sayıldı")
    # 5) degerlendir: hepsi kazanmışsa fark artı olmalı
    r = degerlendir([{"p_oransal": 0.5, "p_us": 0.55, "kazandi": True}] * 40)
    if not (r["fark_oransal"] > 0 and r["fark_us"] > 0):
        hata.append("tam isabette fark artı çıkmadı")
    if degerlendir([])["n"] != 0:
        hata.append("boş girdide n sıfır değil")

    # ── AMPİRİK TABAN ────────────────────────────────────────────
    # 6) Aynı kovada daha iyi olan ajan YAKALANMALI
    bah = []
    for i in range(40):
        bah.append({"ajan": "IYI", "oran": 1.50, "kazandi": i < 32})   # %80
    for i in range(200):
        bah.append({"ajan": f"D{i%5}", "oran": 1.50, "kazandi": i < 100})  # %50
    r = ampirik_taban(bah, {"IYI"})
    if r["n"] != 40:
        hata.append(f"ampirik taban n yanlış: {r['n']}")
    if abs(r["taban"] - 0.50) > 1e-9:
        hata.append(f"taban diğerlerinin oranı olmalı: {r['taban']}")
    if abs(r["fark"] - 0.30) > 1e-9:
        hata.append(f"fark +30p olmalı: {r['fark']}")
    if r["karar"] != "AYNI FİYATTA DAHA İYİ":
        hata.append(f"artı fark yakalanmadı: {r['karar']}")
    # 7) ⚠️ KOVA KARIŞMASI: farklı fiyatlar aynı kovaya düşmemeli.
    #    Düşerse ucuz favori oynayan ajan, pahalı oynayanla kıyaslanır
    #    ve karşılaştırma anlamını kaybeder.
    if _kova(1.10) == _kova(1.50):
        hata.append("uzak oranlar aynı kovaya düştü")
    if _kova(1.52) != _kova(1.50):
        hata.append("aynı kovaya düşmesi gereken oranlar ayrıldı")
    # 8) Ortak kova yoksa hüküm VERİLMEMELİ — kontrol çizgisi ajanlarla
    #    aynı bandı oynamazsa karşılaştırma yapılamaz (ölçüldü: JOKER
    #    1X2 bahislerinin %76'sı 1,70-2,50'de, ajanların %65'i 1,25-1,40).
    ayrik = ([{"ajan": "A", "oran": 1.10, "kazandi": True}] * 30 +
             [{"ajan": "B", "oran": 2.50, "kazandi": False}] * 30)
    r2 = ampirik_taban(ayrik, {"A"})
    if r2["n"] != 0 or "yok" not in r2["karar"]:
        hata.append("ayrık fiyat bantlarında hüküm verildi")
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
