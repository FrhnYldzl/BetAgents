"""
KUPON MASTER — hedef orana kilitlenmiş kupon kurucu
=====================================================
Kullanıcı kararı (15.11.2026): *"Az oranlı çok maçlı kuponlarda eğer
amacım 1.6 ise bu ajanların maçlarını tek kupon yapıp istediğim oranla
isabeti oluşturabiliyorum. Karma ajanlardan veya ajanın kendi
tutarlılığıyla kupon isabet ve kazancının hedefine kitlenmeli."*

Bu modül bir AJAN DEĞİL, ajanların ÜSTÜNDE bir katman. Yeni seçim
üretmez; sahadaki ajanların açık pozisyonlarından, verilen hedef orana
oturan EN YÜKSEK İSABETLİ kombinasyonu kurar.

ÜÇ OLASILIK, HEP BİRLİKTE
--------------------------
Her kupon için üç sayı hesaplanır ve üçü de saklanır:

    sans_piyasa  piyasanın MARJSIZ olasılığı — beceri varsayımı YOK
    sans_ajan    + ajanın ölçülmüş kalibrasyon sapması (kenar)
    sans_alt     + o sapmanın %95 ALT sınırı (muhafazakâr)

Aradaki fark, ajanın İDDİASIDIR. Üçünü birlikte saklamak şunu sağlar:
50 gün sonra hangisinin doğru çıktığını ölçebiliriz. Tek sayı yazsaydık
bunu bir daha asla bilemezdik.

⚠️ KONTROL ÇİZGİLERİ KUPONA GİRMEZ
JOKER'ler ajan değil, ölçü aletidir. Kupona konursa iki şey birden
bozulur: rastgele seçime para yatırılır ve JOKER ölçü aleti olmaktan
çıkar. Ölçüldü (15.11.2026): kontrol çizgileri serbest bırakılınca
optimizasyon neredeyse HER kombinasyonda SARI JOKER'i seçti — çünkü
kısa oranlı yüksek isabetli her ayak p×o hesabında iyi görünür.
Seçilen şey beceri değil, ORAN ŞEKLİYDİ.

⚠️ PAS GEÇMEZ
Kullanıcı şartı: *"Riski ölçebiliyorsak her gün çıkarabilmeli."*
KPI'yi karşılayan kombinasyon yoksa en iyisi yine gösterilir, yalnız
`kpi=False` ve risk etiketiyle. Disiplin saklamakta değil, doğru
etiketlemekte.
"""
from __future__ import annotations

import itertools
import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

import kupon_orkestra as KO  # noqa: E402

# ── HEDEF ve KPI (kullanıcı kararı 15.11.2026) ───────────────────────
# "Hedef plandan biraz daha üstte bir başarı KPI olsun, emniyet payı
# koyalım, standart yükselsin — indirmek ok olur."
# Proje planının bandı 1,60–2,00. Taban yerine 1,80 hedefleniyor.
HEDEF_ORAN = 1.80
# 1,80'de başabaş %55,6. KPI onun 5,5 puan üstü → 1 TL karşılığı ≥ 1,10.
KPI_EV = 1.10
# Hedefin bu kadar üstüne kadar kabul (1,80–2,16)
ORAN_TAVAN_KAT = 1.20
# Bir ajan en çok bu kadar kuponda görünebilir — tek ajana yığılmayı
# engeller. Ölçüldü: kontrolsüz bırakılınca ERKENKUŞ HER kombinasyonda
# çıkıyordu; liste çeşitli görünüp aslında tek bahse dönüşür.
AJAN_TAVAN = 2
# ⚠️ TEK KUPON İÇİNDE aynı ajandan en çok bu kadar ayak. AJAN_TAVAN
# kuponlar ARASI sayıyor, bu kupon İÇİNİ sayar — ikisi ayrı sorun.
# Ölçüldü (15.11.2026): sınırsızken en iyi kupon 4 ayağın DÖRDÜNÜ de
# EŞİK'ten aldı ve şansı %28,1'den %56,1'e çıktı. O 28 puan tek ajanın
# n=38'lik iddiasının dört kez çarpılmasıydı; ajan yanılıyorsa kupon
# dört kat yanılır.
KUPON_ICI_AJAN_TAVAN = 2
MAKS_AYAK = 4


def _kontrol_mu(pid: str) -> bool:
    """JOKER = kontrol çizgisi. Ajan değil, ölçü aleti."""
    return "JOKER" in str(pid or "").upper()


def ayak_olasiliklari(aday: dict, karne: dict) -> dict:
    """Bir ayağın üç olasılığı: piyasa · ajan · alt sınır.

    ⚠️ İKİ FARKLI TABAN — karıştırılırsa marj İKİ KEZ düşülür.
    İlk yazımda bu hata yapıldı ve EŞİK'in şansı %84,2 yerine %72,5
    çıktı (11,7 puan eksik), bütün kuponların EV'si 0,4-0,6'ya indi.

    piyasa : (1/oran) / ima_toplamı
        Beceri varsayımı yok. Marjı burada DÜŞMEK zorundayız, çünkü
        ham 1/oran olasılık değil, marj içerir.

    ajan   : 1/oran + kenar
        kasa'nın kenarı `isabet − 1/ort_oran` ile, yani HAM fiyata göre
        ölçülüyor — marjı zaten İÇİNDE taşıyor. Üstüne bir de marj
        düzeltmesi yapmak çift sayımdır. (kupon_orkestra'da aynı kural
        doğru yazılıydı; burada bozulmuştu.)
    """
    o = float(aday["oran"])
    ham = 1.0 / o
    ima = float(aday.get("ima") or KO.VARSAYILAN_IMA)
    piyasa = ham / max(ima, 1.0)
    n = int(karne.get("n") or 0)
    yeterli = bool(karne.get("yeterli"))
    kenar = float(karne.get("kenar") or 0.0) if yeterli else 0.0
    kenar_alt = float(karne.get("kenar_alt") or 0.0) if yeterli else 0.0

    def kirp(x):
        return min(0.99, max(0.01, x))
    return {"piyasa": kirp(piyasa),
            # Kanıt yoksa ajan tabanı da piyasa tabanıdır: uydurma yok.
            "ajan": kirp(ham + kenar) if yeterli else kirp(piyasa),
            "alt": kirp(ham + kenar_alt) if yeterli else kirp(piyasa),
            "n": n, "yeterli": yeterli}


def _etiket(ayaklar: list[dict]) -> str:
    """Kuponun kanıt gücü — en zayıf halkaya göre."""
    if not ayaklar:
        return "boş"
    if all(a["_p"]["yeterli"] for a in ayaklar):
        return "kanıtlı"
    if any(a["_p"]["yeterli"] for a in ayaklar):
        return "zayıf kanıt"
    return "deneysel"


def kupon_degerlendir(ayaklar: list[dict]) -> dict:
    oran = 1.0
    sp = sa = sl = 1.0
    for a in ayaklar:
        oran *= float(a["oran"])
        sp *= a["_p"]["piyasa"]
        sa *= a["_p"]["ajan"]
        sl *= a["_p"]["alt"]
    return {
        "ayak": len(ayaklar), "oran": oran,
        "sans_piyasa": sp, "sans_ajan": sa, "sans_alt": sl,
        "ev_piyasa": sp * oran, "ev_ajan": sa * oran, "ev_alt": sl * oran,
        "kpi": (sa * oran) >= KPI_EV,
        "etiket": _etiket(ayaklar),
        "ayaklar": ayaklar,
    }


def uret(adaylar: list[dict], karneler: dict, hedef: float = None,
         en_cok: int = 6) -> list[dict]:
    """Hedef orana oturan kombinasyonlar — en yüksek ajan şansından sırayla.

    PAS GEÇMEZ: KPI'yi karşılayan yoksa en iyi adaylar yine döner,
    `kpi=False` ile.
    """
    hedef = float(hedef or HEDEF_ORAN)
    tavan = hedef * ORAN_TAVAN_KAT
    zengin = []
    for a in adaylar:
        pid = a.get("ajan")
        if _kontrol_mu(pid):
            continue                      # kontrol çizgisi kupona girmez
        o = float(a.get("oran") or 0)
        if o <= 1.01:
            continue
        k = karneler.get(pid) or {}
        zengin.append({**a, "oran": o, "_p": ayak_olasiliklari(a, k)})
    if not zengin:
        return []
    # En olası ayaklar önce — kombinasyon patlamasını sınırla
    zengin.sort(key=lambda x: -x["_p"]["ajan"])
    havuz = zengin[:14]

    bulunan = []
    for k in range(1, MAKS_AYAK + 1):
        for c in itertools.combinations(havuz, k):
            if len({x.get("mac_id") for x in c}) != k:
                continue              # aynı maçtan iki ayak olmaz
            from collections import Counter as _C
            if max(_C(x.get("ajan") for x in c).values()) >                     KUPON_ICI_AJAN_TAVAN:
                continue              # tek ajanın iddiası katlanmasın
            o = 1.0
            for x in c:
                o *= float(x["oran"])
            if not (hedef <= o <= tavan):
                continue
            bulunan.append(kupon_degerlendir(list(c)))
    if not bulunan:
        return []
    bulunan.sort(key=lambda x: -x["sans_ajan"])
    # Tek ajana yığılmayı engelle
    from collections import defaultdict
    sayac: dict = defaultdict(int)
    out = []
    for x in bulunan:
        pidler = [a.get("ajan") for a in x["ayaklar"]]
        if any(sayac[p] >= AJAN_TAVAN for p in pidler):
            continue
        for p in pidler:
            sayac[p] += 1
        out.append(x)
        if len(out) >= en_cok:
            break
    return out


def gunun_kuponlari(conn=None, hedef: float = None, en_cok: int = 6) -> dict:
    """Günün kuponları + neden o kadar çıktığının açıklaması."""
    import db
    kapat = conn is None
    conn = conn or db.connect()
    try:
        karne = KO.karne_haritasi(conn)
        aday = KO.gunun_adaylari(conn)
    finally:
        if kapat:
            conn.close()
    oynanabilir = [a for a in aday if not _kontrol_mu(a.get("ajan"))]
    kup = uret(oynanabilir, karne, hedef, en_cok)
    return {
        "kuponlar": kup,
        "hedef": float(hedef or HEDEF_ORAN),
        "kpi_ev": KPI_EV,
        "aday": len(aday),
        "oynanabilir_aday": len(oynanabilir),
        "kontrol_elendi": len(aday) - len(oynanabilir),
        "kpi_gecen": sum(1 for x in kup if x["kpi"]),
    }


def kendi_testi() -> list[str]:
    hata = []

    def ay(pid, oran, mac, kenar=0.0, kenar_alt=None, yeterli=True, ima=1.17):
        return ({"ajan": pid, "oran": oran, "mac_id": mac, "ima": ima,
                 "market": "1X2", "pick": "1", "bet_id": str(mac)},
                {"n": 100, "yeterli": yeterli, "kenar": kenar,
                 "kenar_alt": kenar if kenar_alt is None else kenar_alt})

    # 1) Kontrol çizgisi kupona GİRMEMELİ
    a1, k1 = ay("ERKENKUS_V1", 1.35, 1)
    a2, k2 = ay("SARI_JOKER_V1", 1.35, 2)
    r = uret([a1, a2], {"ERKENKUS_V1": k1, "SARI_JOKER_V1": k2}, hedef=1.80)
    for x in r:
        if any(_kontrol_mu(a["ajan"]) for a in x["ayaklar"]):
            hata.append("kontrol çizgisi kupona girdi")
            break
    # 2) Hedef bandı: üretilen her kupon bantta olmalı
    ad, kr = [], {}
    for i in range(6):
        a, k = ay(f"A{i}_V1", 1.35, i, kenar=0.02)
        ad.append(a)
        kr[f"A{i}_V1"] = k
    r = uret(ad, kr, hedef=1.80, en_cok=20)
    if not r:
        hata.append("bantta kupon üretilmedi (1,35×1,35=1,82)")
    for x in r:
        if not (1.80 <= x["oran"] <= 1.80 * ORAN_TAVAN_KAT + 1e-9):
            hata.append(f"bant dışı kupon: oran {x['oran']:.3f}")
            break
    # 3) Üç olasılık sıralı olmalı: alt ≤ ajan, ve kenar artıysa ajan > piyasa
    if r:
        x = r[0]
        if not (x["sans_alt"] <= x["sans_ajan"] + 1e-9):
            hata.append("alt sınır ajan şansından büyük")
        if not (x["sans_ajan"] > x["sans_piyasa"]):
            hata.append("artı kenarda ajan şansı piyasayı geçmeli")
    # 3b) ÇİFT MARJ SAYIMI — kanıtlı ajanın tabanı HAM 1/oran olmalı,
    #     marjsızlaştırılmış değil. kasa'nın kenarı ham fiyata göre
    #     ölçülüyor; marjsız tabana eklemek marjı iki kez düşer.
    #     Gerçek vaka: EŞİK isabet %84,2 · ort oran 1,21 → kenar
    #     = 0,842 − 1/1,21 = +0,016. Doğru hesap 1/1,21 + 0,016 = 0,842.
    #     Yanlış hesap (1/1,21)/1,166 + 0,016 = 0,725 — 11,7 puan eksik.
    a, k = ay("E_V1", 1.21, 11, kenar=0.016, yeterli=True, ima=1.166)
    p = ayak_olasiliklari(a, k)
    bek = 1.0 / 1.21 + 0.016
    if abs(p["ajan"] - bek) > 1e-9:
        hata.append(f"kanıtlı ajanda çift marj sayımı: {p['ajan']:.4f} "
                    f"≠ {bek:.4f}")
    if not (p["piyasa"] < p["ajan"]):
        hata.append("marjsız piyasa tabanı ajan tabanından büyük olmamalı")
    # 4) Kanıtsız ajanda kenar UYGULANMAMALI
    a, k = ay("X_V1", 1.50, 9, kenar=0.20, yeterli=False)
    p = ayak_olasiliklari(a, k)
    if abs(p["ajan"] - p["piyasa"]) > 1e-9:
        hata.append("kanıtsız ajanın kenarı uygulandı")
    # 5) Aynı maçtan iki ayak olmamalı
    b1, kb1 = ay("B1_V1", 1.35, 7)
    b2, kb2 = ay("B2_V1", 1.35, 7)
    r = uret([b1, b2], {"B1_V1": kb1, "B2_V1": kb2}, hedef=1.80)
    for x in r:
        if len({a["mac_id"] for a in x["ayaklar"]}) != x["ayak"]:
            hata.append("aynı maçtan iki ayak aynı kupona girdi")
            break
    # 5b) KUPON İÇİ ajan tavanı — tek ajandan 4 ayak olmamalı
    ad3, kr3 = [], {}
    for i in range(6):
        a, k = ay("TEK_V1", 1.17, 200 + i, kenar=0.05)
        ad3.append(a)
        kr3["TEK_V1"] = k
    r = uret(ad3, kr3, hedef=1.80, en_cok=10)
    for x in r:
        from collections import Counter as _C2
        if max(_C2(a["ajan"] for a in x["ayaklar"]).values()) >                 KUPON_ICI_AJAN_TAVAN:
            hata.append("tek ajandan tavandan fazla ayak aynı kuponda")
            break
    # 6) Tek ajan tavanı
    ad2, kr2 = [], {}
    for i in range(8):
        a, k = ay(f"C{i}_V1", 1.35, 100 + i, kenar=0.0 if i else 0.10)
        ad2.append(a)
        kr2[f"C{i}_V1"] = k
    r = uret(ad2, kr2, hedef=1.80, en_cok=10)
    from collections import Counter
    say = Counter(a["ajan"] for x in r for a in x["ayaklar"])
    if say and max(say.values()) > AJAN_TAVAN:
        hata.append(f"tek ajan {max(say.values())} kuponda "
                    f"(tavan {AJAN_TAVAN})")
    # 7) KPI bayrağı doğru mu
    if r:
        for x in r:
            if x["kpi"] != (x["ev_ajan"] >= KPI_EV):
                hata.append("kpi bayrağı ev_ajan ile tutarsız")
                break
    return hata


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)
