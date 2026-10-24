"""
⚫ SİSTEM TAKIM — N/M sistem kuponlarının matematiği ve ölçümü
==============================================================
iddaa'da sistem kuponu: N seçim yaparsın, hepsinin M'li kombinasyonları
ayrı kupon olarak oynanır. "4/5" demek 5 seçimin 5 farklı dörtlüsü demektir;
en az 4 tutarsa para alırsın.

ÖNCE DÜRÜST MATEMATİK — sistem KENDİ BAŞINA KENAR YARATMAZ
-----------------------------------------------------------
Bir k/n sistemi, k'lı kombine kuponlarının DOĞRUSAL BİRLEŞİMİDİR. Dolayısıyla
lira başına beklenen değeri, o kuponların ağırlıklı ortalamasıdır:

    tek bahis   EV/TL = (1 − marj)
    2'li kombi  EV/TL = (1 − marj)²        ← marj BİLEŞİKLEŞİR
    k/n sistem  EV/TL ∈ [(1−marj)ⁿ, (1−marj)ᵏ]

Ölçülen iddaa marjı: üst liglerde %13,1 · diğerlerinde %17,2. Yani 4'lü bir
ayakta beklenen değer 0,87⁴ ≈ 0,57'ye iner. Sistem bunu DÜZELTMEZ — yalnız
ödeme dağılımını yayar.

Peki neden takım kuruyoruz? Çünkü sistemin iki gerçek işlevi var:
  1) VARYANS ŞEKİLLENDİRME — %70 isabetli bir ajanın 5 tekli bahsi ile
     4/5 sistemi aynı parayı farklı dağıtır. Kasa hayatta kalma açısından
     fark eder; beklenen değer açısından etmez.
  2) KORELASYON — kitap kombineyi bağımsız varsayarak fiyatlar. AYNI MAÇIN
     iki sonucu güçlü korelasyonludur (Kırmızı Takım ölçtü: "ALT ve YOK"
     çarpımın 1,97 katı). FARKLI maçlar ise gerçekten bağımsızdır; orada
     kitabın varsayımı DOĞRU ve kazanılacak bir şey yoktur.

Bu yüzden ön kayıtlı beklentimiz: ÇAPRAZ-MAÇ SİSTEM KUPONU, AYNI AYAKLARI
TEK TEK OYNAMAKTAN KÖTÜDÜR. Takımın işi bunu ölçmek. Kontrol grubu
kendiliğinden var: "aynı ayaklar tekli oynansaydı" (bkz. tekli_kontrol).

Eğer ölçüm bunun tersini söylerse kaçırdığımız bir şey var demektir ve
hipotez ayağa kalkar. Söylemezse, sistem kuponu kasayı yumuşatmak için
kullanılır — para kazanmak için değil.
"""
from __future__ import annotations

import itertools
import math


# ----------------------------------------------------------------------
# TEMEL MATEMATİK
# ----------------------------------------------------------------------
def kombinasyon_sayisi(n: int, k: int) -> int:
    """k/n sisteminde kaç kupon oynanır."""
    return math.comb(n, k) if 0 < k <= n else 0


def poisson_binom(p: list[float]) -> list[float]:
    """Bağımsız ama FARKLI olasılıklı n denemede 'tam j tane tuttu' dağılımı.

    Düz binom kullanmak yanlış olurdu: ayakların olasılıkları eşit değil.
    Dönen liste[j] = P(tam j ayak tuttu), j = 0..n.
    """
    d = [1.0]
    for pi in p:
        yeni = [0.0] * (len(d) + 1)
        for j, v in enumerate(d):
            yeni[j] += v * (1.0 - pi)
            yeni[j + 1] += v * pi
        d = yeni
    return d


def en_az_k(p: list[float], k: int) -> float:
    """P(en az k ayak tuttu)."""
    d = poisson_binom(p)
    return sum(d[k:]) if k <= len(p) else 0.0


# ----------------------------------------------------------------------
# SİSTEM KUPONUNUN DEĞERİ
# ----------------------------------------------------------------------
def sistem_degeri(oranlar: list[float], p: list[float], k: int,
                  birim: float = 1.0) -> dict:
    """k/n sisteminin maliyeti, beklenen getirisi ve ödeme dağılımı.

    oranlar  her ayağın ondalık oranı
    p        her ayağın GERÇEK tutma olasılığı (modelin görüşü)
    k        sistemin alt sınırı (4/5 için k=4)
    birim    her kombinasyona yatırılan tutar

    Beklenen getiri TEK TEK her kombinasyon üzerinden hesaplanır — kısayol
    yok. n küçük (≤10) olduğu için tam sayım ucuz ve yaklaşımdan güvenli.
    """
    n = len(oranlar)
    if not (0 < k <= n) or len(p) != n:
        return {"gecerli": False}
    kuponlar = list(itertools.combinations(range(n), k))
    maliyet = len(kuponlar) * birim
    bek = 0.0
    for c in kuponlar:
        # bu kombinasyon ancak İÇİNDEKİ her ayak tutarsa öder
        olas = 1.0
        carpim = 1.0
        for i in c:
            olas *= p[i]
            carpim *= oranlar[i]
        bek += olas * carpim * birim
    d = poisson_binom(p)
    return {
        "gecerli": True, "n": n, "k": k, "kupon": len(kuponlar),
        "maliyet": maliyet, "beklenen": bek,
        "ev_tl": bek / maliyet if maliyet else 0.0,
        "p_en_az_k": sum(d[k:]),
        "dagilim": d,
    }


def tekli_kontrol(oranlar: list[float], p: list[float],
                  birim: float = 1.0) -> dict:
    """KONTROL GRUBU: aynı ayaklar TEK TEK oynansaydı.

    Sistem takımının her kuponu bununla kıyaslanır. Toplam yatırım eşitlenir
    ki karşılaştırma adil olsun — sistem n kombinasyona birim koyuyorsa,
    kontrol de aynı toplamı n ayağa eşit böler.
    """
    n = len(oranlar)
    if not n or len(p) != n:
        return {"gecerli": False}
    pay = birim  # ayak başına
    bek = sum(p[i] * oranlar[i] * pay for i in range(n))
    maliyet = n * pay
    return {"gecerli": True, "n": n, "maliyet": maliyet, "beklenen": bek,
            "ev_tl": bek / maliyet if maliyet else 0.0,
            "p_en_az_bir": 1.0 - math.prod(1.0 - x for x in p)}


def karsilastir(oranlar: list[float], p: list[float], k: int) -> dict:
    """Sistem vs tekli — EV/TL ve isabet profili yan yana.

    Toplam yatırımı EŞİTLER: sistem C(n,k) kupona 1 birim koyuyorsa, kontrol
    aynı toplamı n ayağa böler. Aksi hâlde "sistem daha çok para yatırdı,
    daha çok kazandı" gibi sahte bir üstünlük çıkar.
    """
    s = sistem_degeri(oranlar, p, k, birim=1.0)
    if not s.get("gecerli"):
        return {"gecerli": False}
    t = tekli_kontrol(oranlar, p, birim=s["maliyet"] / len(oranlar))
    return {
        "gecerli": True, "n": s["n"], "k": k, "kupon": s["kupon"],
        "maliyet": s["maliyet"],
        "sistem_ev_tl": s["ev_tl"], "tekli_ev_tl": t["ev_tl"],
        "fark": s["ev_tl"] - t["ev_tl"],
        "p_en_az_k": s["p_en_az_k"],
        "ort_oran": sum(oranlar) / len(oranlar),
        "ort_p": sum(p) / len(p),
    }


# ----------------------------------------------------------------------
# SİSTEM SEÇİMİ
# ----------------------------------------------------------------------
def en_iyi_k(oranlar: list[float], p: list[float]) -> list[dict]:
    """Her k için sistem vs tekli karşılaştırması — hangisi ne veriyor.

    Not: k arttıkça EV/TL tekliye YAKLAŞIR (k=n tam kombine, k=1 ise her
    ayağa ayrı kupon ≈ tekli). Dolayısıyla "en iyi k" aslında "en az zarar
    veren k"dır. Bunu gizlemiyoruz; tablo olduğu gibi gösterilir.
    """
    out = []
    for k in range(1, len(oranlar) + 1):
        r = karsilastir(oranlar, p, k)
        if r.get("gecerli"):
            out.append(r)
    return out


# ----------------------------------------------------------------------
# KENDİ TESTİ
# ----------------------------------------------------------------------
def kendi_testi() -> list[str]:
    hata = []
    # 1) Poisson-binom toplamı 1 olmalı
    d = poisson_binom([0.7, 0.6, 0.5, 0.8])
    if abs(sum(d) - 1.0) > 1e-9:
        hata.append(f"poisson_binom toplamı {sum(d)} ≠ 1")
    # 2) Eşit olasılıkta düz binomla aynı çıkmalı
    n, pp = 5, 0.7
    d2 = poisson_binom([pp] * n)
    for j in range(n + 1):
        bek = math.comb(n, j) * pp ** j * (1 - pp) ** (n - j)
        if abs(d2[j] - bek) > 1e-9:
            hata.append(f"binom uyuşmazlığı j={j}")
            break
    # 3) k=n sistemi tam kombineye eşit olmalı
    o, p = [1.5, 1.6, 1.7], [0.7, 0.65, 0.6]
    s = sistem_degeri(o, p, 3)
    if abs(s["beklenen"] - math.prod(p) * math.prod(o)) > 1e-9:
        hata.append("k=n sistemi tam kombineye eşit değil")
    # 4) ⚠️ ASIL SINAV: adil oranlarda (marjsız) sistem tekliyi GEÇEMEMELİ.
    #    p_i = 1/o_i ise her kupon başabaştır; EV/TL her k için 1,00 olmalı.
    o2 = [2.0, 2.5, 1.8, 3.0]
    p2 = [1 / x for x in o2]
    for r in en_iyi_k(o2, p2):
        if abs(r["sistem_ev_tl"] - 1.0) > 1e-9 or abs(r["tekli_ev_tl"] - 1.0) > 1e-9:
            hata.append(f"adil oranda k={r['k']} EV/TL 1,00 değil "
                        f"(sistem {r['sistem_ev_tl']:.4f} tekli {r['tekli_ev_tl']:.4f})")
            break
    # 5) Marj varsa sistem tekliden KÖTÜ olmalı (k≥2) — modülün ana iddiası
    marj = 0.13
    p3 = [(1 / x) * (1 - marj) for x in o2]
    for r in en_iyi_k(o2, p3):
        if r["k"] >= 2 and r["fark"] > 1e-9:
            hata.append(f"marjlı oranda k={r['k']} sistem tekliyi GEÇTİ "
                        f"({r['fark']:+.4f}) — matematik beklentiye aykırı")
            break
    return hata


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    h = kendi_testi()
    print("kendi testi:", "TEMİZ" if not h else f"{len(h)} sorun")
    for x in h:
        print("  ", x)

    o = [1.45] * 5
    for ad, p in (("KENAR YOK — isabet tam fiyatın dediği kadar (%69,0)",
                   [1 / 1.45] * 5),
                  ("KENAR VAR — isabet fiyatın 1 puan üstünde (%70,0)",
                   [0.70] * 5)):
        print(f"\nÖRNEK · 5 ayak · oran 1,45 · {ad}")
        print(f"{'sistem':>8} {'kupon':>6} {'EV/TL':>7} {'tekli':>7} "
              f"{'fark':>7} {'P(≥k)':>8}")
        print("-" * 48)
        for r in en_iyi_k(o, p):
            print(f"{r['k']}/{r['n']:<6} {r['kupon']:6} {r['sistem_ev_tl']:7.3f} "
                  f"{r['tekli_ev_tl']:7.3f} {r['fark']:+7.3f} {r['p_en_az_k']:8.3f}")
    print("""
OKUMA — bu modülün tek önemli cümlesi:
  SİSTEM/KOMBİNE KENARI ÇARPAR, İKİ YÖNDE DE.
  Kenar yoksa her k aynı (fark 0) ve marj varken k büyüdükçe KÖTÜLEŞİR.
  Kenar varsa k büyüdükçe İYİLEŞİR — kenar üslenir.

  Yani "%70 isabetli ajan için sistem çok önemli" doğrudur, AMA şartı var:
  o %70'in FİYATIN İMA ETTİĞİNDEN yüksek olması gerekir. 1,45 oranın ima
  ettiği zaten %69. Ölçtük (24.10.2026): hiçbir ajan kendi fiyatını
  geçmiyor. Bugün sistem kuponu kaybı büyütür.

  Bu yüzden SİSTEM TAKIM bir KALDIRAÇTIR, kenar kaynağı değil. Gerçek kenarı
  olan bir ajan çıktığı gün hazır olsun diye kuruluyor ve o güne kadar
  kendi kontrolüyle (aynı ayaklar tekli) ölçülüyor.""")
