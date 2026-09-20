"""
CANLI · MODEL — maç içi (in-play) olasılık
===========================================
Fikir basit ve kendini savunabilir olsun:

1. Maç ÖNCESİ fiyattan gol beklentisi çöz. 1/0/2 fiyatı marjından arındırılır,
   ardından (λ_ev, λ_dep) ikilisi Poisson altında o olasılıkları verecek şekilde
   sayısal olarak bulunur. (İki bilinmeyen, iki bağımsız denklem.)
2. Maç içinde kalan süreye ölçekle: λ_kalan = λ · (kalan dakika / 90).
   Kırmızı kart gören takımın beklentisi düşer, rakibininki yükselir.
3. Mevcut skora ekleyerek nihai sonucun 1/0/2 olasılığını hesapla.

Sınırı açıkça söyleyelim: bu model maçın GİDİŞATINI (üstünlük, şut, xG) görmez.
Yalnız skor, dakika ve kırmızı kart bilir. Piyasa bunlardan fazlasını gördüğü
için modelin piyasayı yenmesi BEKLENMEZ — amaç sapmayı ÖLÇMEK, ezbere bahis
üretmek değil.
"""
from __future__ import annotations

import math

MAKS_GOL = 10            # Poisson kuyruğu için yeterli
UZATMA = 3.0             # ortalama uzatma dakikası (ikinci yarı)
KIRMIZI_KENDI = 0.74     # 10 kişi kalan takımın gol beklentisi çarpanı
KIRMIZI_RAKIP = 1.28     # rakibinin çarpanı
VARSAYILAN = (1.42, 1.12)   # lig-nötr ev/deplasman gol beklentisi (fiyat yoksa)


def marjsiz(oran) -> list[float] | None:
    """1/0/2 oranı → marjı temizlenmiş olasılık (güç yöntemi)."""
    try:
        o = [float(x) for x in oran]
    except (TypeError, ValueError):
        return None
    if len(o) != 3 or min(o) <= 1.0:
        return None
    inv = [1.0 / x for x in o]
    t = sum(inv)
    if t <= 1.0:
        return [x / t for x in inv]
    lo, hi = 1.0, 10.0
    for _ in range(60):
        k = 0.5 * (lo + hi)
        if sum(x ** k for x in inv) > 1.0:
            lo = k
        else:
            hi = k
    k = 0.5 * (lo + hi)
    p = [x ** k for x in inv]
    t = sum(p)
    return [x / t for x in p]


def _pois(lam: float, k: int) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam + k * math.log(lam) - math.lgamma(k + 1))


def sonuc_olasilik(lh: float, la: float, fark: int = 0) -> list[float]:
    """Kalan sürede λ ile, mevcut gol farkı (ev−dep) verildiğinde nihai 1/0/2."""
    pe = [_pois(lh, k) for k in range(MAKS_GOL + 1)]
    pd = [_pois(la, k) for k in range(MAKS_GOL + 1)]
    p1 = p0 = p2 = 0.0
    for x in range(MAKS_GOL + 1):
        for y in range(MAKS_GOL + 1):
            v = pe[x] * pd[y]
            d = fark + x - y
            if d > 0:
                p1 += v
            elif d == 0:
                p0 += v
            else:
                p2 += v
    t = p1 + p0 + p2
    return [p1 / t, p0 / t, p2 / t]


def lambda_coz(p: list[float], tur: int = 60) -> tuple[float, float]:
    """Maç öncesi 1/0/2 olasılığından (λ_ev, λ_dep) — ikili ikiye bölme."""
    lh, la = VARSAYILAN
    for _ in range(tur):
        q = sonuc_olasilik(lh, la, 0)
        # ev galibiyeti azsa ev λ'sını düşür; beraberlik azsa ikisini birden düşür
        oran_ev = (p[0] + 1e-9) / (q[0] + 1e-9)
        oran_dep = (p[2] + 1e-9) / (q[2] + 1e-9)
        lh *= oran_ev ** 0.22
        la *= oran_dep ** 0.22
        toplam = (p[1] + 1e-9) / (q[1] + 1e-9)
        olcek = toplam ** -0.12          # beraberlik fazlaysa toplam gol beklentisi düşer
        lh *= olcek
        la *= olcek
        lh = min(max(lh, 0.05), 6.0)
        la = min(max(la, 0.05), 6.0)
    return lh, la


def kalan_oran(dakika: int | None, safha: str | None) -> float:
    """Kalan sürenin maça oranı. Devre arası ve uzatma dikkate alınır."""
    if safha in ("HT",):
        return 45.0 / 90.0
    if safha in ("FT", "AET", "PEN", "PST", "CANC", "ABD", "AWD", "WO"):
        return 0.0
    d = float(dakika or 0)
    toplam = 90.0 + UZATMA
    return max(0.0, min(1.0, (toplam - d) / 90.0))


def inplay(p_once: list[float] | None, dakika: int | None, safha: str | None,
           ev_skor: int | None, dep_skor: int | None,
           kirmizi_ev: int = 0, kirmizi_dep: int = 0) -> dict:
    """Maç içi 1/0/2 olasılığı ve kullanılan varsayımlar."""
    if p_once:
        lh, la = lambda_coz(p_once)
        kaynak = "maç öncesi fiyat"
    else:
        lh, la = VARSAYILAN
        kaynak = "lig-nötr varsayım (zayıf)"
    r = kalan_oran(dakika, safha)
    kh = lh * r * (KIRMIZI_KENDI ** (kirmizi_ev or 0)) * (KIRMIZI_RAKIP ** (kirmizi_dep or 0))
    ka = la * r * (KIRMIZI_KENDI ** (kirmizi_dep or 0)) * (KIRMIZI_RAKIP ** (kirmizi_ev or 0))
    fark = int(ev_skor or 0) - int(dep_skor or 0)
    p = sonuc_olasilik(kh, ka, fark)
    return {"p": p, "lam_mac": [round(lh, 3), round(la, 3)], "lam_kalan": [round(kh, 3), round(ka, 3)],
            "kalan_oran": round(r, 3), "kaynak": kaynak}


def sapma(p_model: list[float], p_piyasa: list[float]) -> dict:
    """Model ile piyasa arasındaki fark — hangi sonuçta ne kadar."""
    if not p_model or not p_piyasa:
        return {}
    fark = [round(a - b, 4) for a, b in zip(p_model, p_piyasa)]
    j = max(range(3), key=lambda i: fark[i])
    return {"fark": fark, "en_cok": ("1", "0", "2")[j], "buyukluk": round(fark[j], 4),
            "oran": round((p_model[j] + 1e-9) / (p_piyasa[j] + 1e-9), 3)}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("λ çözümü (maç öncesi fiyattan):")
    for oran in ((1.50, 4.20, 6.50), (2.40, 3.30, 2.90), (5.50, 4.00, 1.60)):
        p = marjsiz(oran)
        lh, la = lambda_coz(p)
        q = sonuc_olasilik(lh, la, 0)
        print(f"  oran {oran} → p {[round(x,3) for x in p]} · λ ({lh:.2f}, {la:.2f}) "
              f"· geri kontrol {[round(x,3) for x in q]}")
    print("\nmaç içi (oran 2.40/3.30/2.90 olan maç):")
    p0 = marjsiz((2.40, 3.30, 2.90))
    for dk, e, d, kr in ((0, 0, 0, 0), (30, 1, 0, 0), (60, 1, 0, 0), (80, 1, 0, 0),
                         (80, 1, 1, 0), (60, 0, 0, 1)):
        r = inplay(p0, dk, "2H" if dk > 45 else "1H", e, d, kirmizi_ev=kr)
        print(f"  {dk:>3}' {e}-{d} kırmızı_ev={kr} → 1/0/2 = "
              f"{[f'{x:.1%}' for x in r['p']]}  (kalan λ {r['lam_kalan']})")
