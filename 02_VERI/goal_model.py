"""
⚽ GOL MODELİ — piyasanın kendi fiyatından kalibre edilen Poisson
=================================================================
BANT (gol aralıkları) ve DEVRE (ilk yarı) pazarlarının adil fiyatını
üretir. Kombo ajanlarından FARKLI bir yöntem: orada tarihsel korelasyon
katsayısı vardı, burada maçın kendi fiyatından türetilen gol modeli var.

NEDEN MEŞRU: 24.612 maçta ölçüldü — toplam gol dağılımı Poisson'a uyuyor
(0-1 gol 0.95 · 2-3 gol 1.02 · 4-5 gol 1.01 · 6+ gol 0.98). Yani dağılım
varsayımı VERİYLE DOĞRULANMIŞ. Dağılımdan gelen bir açık yok; aranan şey
iddaa'nın bant FİYATLARINI bu doğru dağılımdan sapmayla koyup koymadığı.

YÖNTEM:
  1. Piyasanın 1X2 + A/Ü 2.5 fiyatları marjsızlaştırılır
  2. (λ_ev, λ_dep) ızgara aramasıyla bu olasılıklara oturtulur
  3. Model, her bantın/İY-MS hücresinin adil olasılığını verir
  4. iddaa'nın oranı adil oranı MIN_EDGE aşarsa değer vardır

⚠️ İLK YARI VARSAYIMI (DEVRE): gollerin %45'i ilk yarıda atılır kabul
edilir (futbol literatüründe standart; bizim verimizde yarı skoru HİÇ
yok, o yüzden DOĞRULANMAMIŞ bir varsayımdır). DEVRE'nin canlı sonuçları
bu varsayımı sınayacak — ajan aynı zamanda bir ölçüm aracıdır.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

MAXG = 9
HT_SHARE = 0.45           # ilk yarı gol payı (varsayım — DEVRE bunu sınar)
_FACT = [math.factorial(k) for k in range(MAXG + 1)]


def _pois(lam: float) -> list[float]:
    return [math.exp(-lam) * lam ** k / _FACT[k] for k in range(MAXG + 1)]


_GRID = [round(0.15 + 0.05 * i, 2) for i in range(78)]     # 0.15 – 4.00
_CACHE: dict = {}


def _profile(lh: float, la: float) -> tuple:
    """(P1, PX, P2, P(üst2.5)) — önbellekli."""
    key = (lh, la)
    if key in _CACHE:
        return _CACHE[key]
    ph, pa = _pois(lh), _pois(la)
    p1 = px = pov = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            q = ph[i] * pa[j]
            if i > j:
                p1 += q
            elif i == j:
                px += q
            if i + j > 2.5:
                pov += q
    out = (p1, px, 1 - p1 - px, pov)
    _CACHE[key] = out
    return out


def fit(p1: float, px: float, pover: float) -> tuple[float, float]:
    """Marjsız piyasa olasılıklarına en iyi oturan (λ_ev, λ_dep)."""
    best, bl = None, 9e9
    for lh in _GRID:
        for la in _GRID:
            m1, mx, _m2, mo = _profile(lh, la)
            loss = (m1 - p1) ** 2 + (mx - px) ** 2 + 2.0 * (mo - pover) ** 2
            if loss < bl:
                bl, best = loss, (lh, la)
    return best or (1.3, 1.1)


# ── pazar fiyatlayıcıları ─────────────────────────────────────────────

def total_goals_probs(lh: float, la: float) -> dict:
    """0-1 / 2-3 / 4-5 / 6+ bantlarının adil olasılıkları."""
    ph, pa = _pois(lh), _pois(la)
    tot = [0.0] * (2 * MAXG + 1)
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            tot[i + j] += ph[i] * pa[j]
    def rng(a, b):
        return sum(tot[k] for k in range(a, min(b, 2 * MAXG) + 1))
    return {"0-1 gol": rng(0, 1), "2-3 gol": rng(2, 3),
            "4-5 gol": rng(4, 5), "6+ gol": rng(6, 2 * MAXG)}


def ht_probs(lh: float, la: float) -> dict:
    """İY sonucu (HT_1X2) ve İY alt/üst adil olasılıkları."""
    h, a = _pois(lh * HT_SHARE), _pois(la * HT_SHARE)
    p1 = px = 0.0
    o05 = o15 = 0.0
    for i in range(MAXG + 1):
        for j in range(MAXG + 1):
            q = h[i] * a[j]
            if i > j:
                p1 += q
            elif i == j:
                px += q
            if i + j > 0.5:
                o05 += q
            if i + j > 1.5:
                o15 += q
    return {"HT_1X2": {"1": p1, "0": px, "2": 1 - p1 - px},
            "HT_OU0.5": {"Üst": o05, "Alt": 1 - o05},
            "HT_OU1.5": {"Üst": o15, "Alt": 1 - o15}}


def htft_probs(lh: float, la: float) -> dict:
    """İY/MS (9 hücre) adil olasılıkları — iki yarı bağımsız Poisson."""
    h1, a1 = _pois(lh * HT_SHARE), _pois(la * HT_SHARE)
    h2, a2 = _pois(lh * (1 - HT_SHARE)), _pois(la * (1 - HT_SHARE))
    out = {f"{x}/{y}": 0.0 for x in ("1", "0", "2") for y in ("1", "0", "2")}
    for i1 in range(6):
        for j1 in range(6):
            q1 = h1[i1] * a1[j1]
            if q1 < 1e-9:
                continue
            ht = "1" if i1 > j1 else ("2" if j1 > i1 else "0")
            for i2 in range(7):
                for j2 in range(7):
                    q = q1 * h2[i2] * a2[j2]
                    if q < 1e-12:
                        continue
                    H, A = i1 + i2, j1 + j2
                    ft = "1" if H > A else ("2" if A > H else "0")
                    out[f"{ht}/{ft}"] += q
    return out


def price_all(o1: float, ox: float, o2: float, ou: float, un: float) -> dict:
    """Bir maçın tüm model-fiyatlı pazarları. Girdi: iddaa oranları."""
    s = 1/o1 + 1/ox + 1/o2
    p1, px = (1/o1)/s, (1/ox)/s
    t = 1/ou + 1/un
    pov = (1/ou)/t
    lh, la = fit(p1, px, pov)
    out = {"lambda": (lh, la), "TOTAL_GOALS": total_goals_probs(lh, la),
           "HT_FT": htft_probs(lh, la)}
    out.update(ht_probs(lh, la))
    return out


if __name__ == "__main__":
    r = price_all(2.10, 3.40, 3.30, 1.85, 1.95)
    print("λ:", r["lambda"])
    for k in ("TOTAL_GOALS", "HT_1X2", "HT_OU0.5", "HT_FT"):
        print(f"\n{k}:")
        for sel, p in sorted(r[k].items(), key=lambda x: -x[1]):
            print(f"   {sel:10s} %{p*100:5.2f}  adil oran {1/p:6.2f}")
