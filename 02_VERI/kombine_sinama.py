"""
🧮 KOMBİNE BELGESİ SINAMASI — "Kombine Market Fiyatlama" ekinin iddiaları
kendi verimizde tutuyor mu?

Belge (kullanıcı, Tahmin Sistemi eki, 2 Eylül 2026) üç şey iddia ediyor:
  1. Skor dağılımı (λ=1,35 μ=1,10 ρ=−0,13) "30.000 maçlık gözlemle
     doğrulanıyor": 1-1 %14,48 · 0-0 %10,30 · ilk 12 skor %86,1.
  2. Dixon-Coles düşük skor düzeltmesi ρ ≈ −0,13; lig bazında kalibre
     edilmeli.
  3. Kombine marketlerde marj ana marketlerden yüksek; marjı %5'i geçen
     markette model ne kadar iyi olursa olsun edge bulmak çok zor.

Bu modül üçünü de ölçer. SALT OKUMA — hiçbir şey yazmaz.

ρ nasıl ölçülür: her maçın λ, μ değeri KAPANIŞ oranından çözülür
(marjsız P(ev) ve P(üst 2,5) → iki denklem, iki bilinmeyen). Dixon-Coles
düzeltmesi normalizasyonu bozmaz (dört hücrenin düzeltmeleri toplamda
sıfırlanır); bu yüzden ρ'nun olabilirliği yalnız 0-0 · 0-1 · 1-0 · 1-1
hücrelerinden gelir ve ızgara taramasıyla kesin bulunur. Soru şudur:
"piyasanın λ/μ'sünün ÜSTÜNE düşük skor düzeltmesi bir şey katıyor mu?"

    python kombine_sinama.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import db

N = 10
BELGE_SKOR = {"1-1": 14.48, "0-0": 10.30, "1-0": 9.98, "2-1": 8.65,
              "2-0": 7.86, "0-1": 7.83, "1-2": 7.05, "0-2": 5.22,
              "2-2": 4.76, "3-1": 3.89, "3-0": 3.54, "1-3": 2.58}


def _pmf(l: float) -> list[float]:
    out, p = [], math.exp(-l)
    for k in range(N):
        out.append(p)
        p *= l / (k + 1)
    return out


def _p_ust(T: float) -> float:
    return 1 - math.exp(-T) * (1 + T + T * T / 2)


def _p_ev(lam: float, mu: float) -> float:
    ph, pa = _pmf(lam), _pmf(mu)
    return sum(ph[x] * sum(pa[:x]) for x in range(1, N))


def _coz(q1: float, qU: float) -> tuple[float, float]:
    """Marjsız P(ev) ve P(üst 2,5) → (λ, μ), bağımsız Poisson (ρ=0)."""
    lo, hi = 0.2, 7.0
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _p_ust(m) < qU else (lo, m)
    T = (lo + hi) / 2
    lo, hi = 0.01, T - 0.01
    for _ in range(40):
        m = (lo + hi) / 2
        lo, hi = (m, hi) if _p_ev(m, T - m) < q1 else (lo, m)
    lam = (lo + hi) / 2
    return lam, T - lam


def _tau(h: int, a: int, lam: float, mu: float, rho: float) -> float:
    if h == 0 and a == 0:
        return 1 - lam * mu * rho
    if h == 0 and a == 1:
        return 1 + lam * rho
    if h == 1 and a == 0:
        return 1 + mu * rho
    if h == 1 and a == 1:
        return 1 - rho
    return 1.0


def _rho_hat(gozlem: list) -> tuple[float, float]:
    """ρ'nun en çok olabilirlik tahmini + yaklaşık standart hata."""
    def ll(r):
        s = 0.0
        for h, a, lam, mu in gozlem:
            if h <= 1 and a <= 1:
                t = _tau(h, a, lam, mu, r)
                if t <= 0:
                    return -1e18
                s += math.log(t)
        return s
    izgara = [x / 1000 for x in range(-300, 101, 2)]
    en = max(izgara, key=ll)
    d = 0.002
    ikinci = (ll(en + d) - 2 * ll(en) + ll(en - d)) / (d * d)
    se = math.sqrt(-1 / ikinci) if ikinci < 0 else float("nan")
    return en, se


def sina() -> None:
    conn = db.connect()
    try:
        skor = [dict(r) for r in conn.execute(
            "SELECT home_score hs, away_score aws FROM matches_v2 "
            "WHERE home_score IS NOT NULL AND away_score IS NOT NULL").fetchall()]
        oranli = [dict(r) for r in conn.execute(
            "SELECT league_code lg, home_score hs, away_score aws, "
            "closing_1 c1, closing_X cx, closing_2 c2, "
            "closing_over25 co, closing_under25 cu FROM matches_v2 "
            "WHERE home_score IS NOT NULL AND away_score IS NOT NULL "
            "AND closing_1 > 1.01 AND closing_X > 1.01 AND closing_2 > 1.01 "
            "AND closing_over25 > 1.01 AND closing_under25 > 1.01").fetchall()]
    finally:
        conn.close()

    # ── 1) SKOR DAĞILIMI ─────────────────────────────────────────
    say = Counter(f"{int(r['hs'])}-{int(r['aws'])}" for r in skor)
    n = sum(say.values())
    print(f"1) SKOR DAĞILIMI — {n:,} maç (gerçek) · belge: λ=1,35 μ=1,10 ρ=−0,13")
    print(f"   {'skor':5s} {'gerçek':>8s} {'belge':>8s}")
    kum = 0.0
    for i, (s, c) in enumerate(say.most_common(14), 1):
        p = c / n * 100
        kum += p
        print(f"   {s:5s} %{p:6.2f}  " +
              (f"%{BELGE_SKOR[s]:6.2f}" if s in BELGE_SKOR else "     —") +
              f"   kümülatif %{kum:5.1f}" + ("  ← ilk 12" if i == 12 else ""))
    ber = sum(c for s, c in say.items() if s.split("-")[0] == s.split("-")[1]) / n
    print(f"   beraberlik oranı: gerçek %{ber*100:.1f} · belge modeli %30,40")

    # ── 2) ρ — PİYASA λ/μ'SÜNÜN ÜSTÜNE ────────────────────────────
    gozlem, lig = [], defaultdict(list)
    for r in oranli:
        try:
            o1, ox, o2 = float(r["c1"]), float(r["cx"]), float(r["c2"])
            ou, un = float(r["co"]), float(r["cu"])
        except (TypeError, ValueError):
            continue
        s1 = 1 / o1 + 1 / ox + 1 / o2
        s2 = 1 / ou + 1 / un
        q1, qU = (1 / o1) / s1, (1 / ou) / s2
        if not (0.03 < q1 < 0.97 and 0.05 < qU < 0.95):
            continue
        lam, mu = _coz(q1, qU)
        g = (int(r["hs"]), int(r["aws"]), lam, mu)
        gozlem.append(g)
        lig[str(r["lg"] or "?")].append(g)
    m = len(gozlem)
    print(f"\n2) DÜŞÜK SKOR DÜZELTMESİ ρ — {m:,} maç, λ/μ kapanış oranından")
    if m < 500:
        print("   (örneklem yetersiz)")
    else:
        rh, se = _rho_hat(gozlem)
        print(f"   ρ tahmini (tüm veri): {rh:+.3f} ± {se:.3f}   · belge −0,130")

        def tahmin(h, a, r):
            return sum(_tau(h, a, l, u, r) * _pmf(l)[h] * _pmf(u)[a]
                       for _, _, l, u in gozlem) / m
        gz = Counter((h, a) for h, a, _, _ in gozlem)
        print(f"   {'hücre':6s} {'gerçek':>8s} {'ρ=0':>8s} {'ρ=−0,13':>9s} {'ρ tahmini':>10s}")
        for h, a in ((0, 0), (1, 1), (1, 0), (0, 1)):
            print(f"   {h}-{a:<4d} %{gz[(h, a)]/m*100:6.2f}  %{tahmin(h, a, 0)*100:6.2f}"
                  f"  %{tahmin(h, a, -0.13)*100:7.2f}  %{tahmin(h, a, rh)*100:8.2f}")
        print("   lig bazında (≥800 maç):")
        for lg, v in sorted(lig.items(), key=lambda z: -len(z[1])):
            if len(v) < 800:
                continue
            r_, s_ = _rho_hat(v)
            print(f"     {lg:5s} n={len(v):5,d}  ρ {r_:+.3f} ± {s_:.3f}")

    # ── 3) iddaa KOMBİNE MARJLARI ────────────────────────────────
    print("\n3) iddaa MARJI — pazar defteri (market_odds), tam gruplar")
    try:
        import multiplier_agent as ma
        latest, _meta = ma._load_latest()
    except Exception as e:
        print(f"   (pazar defteri okunamadı: {e})")
        return
    grup = defaultdict(list)
    for (ev, mk, _sel), odd in latest.items():
        try:
            o = float(odd)
        except (TypeError, ValueError):
            continue
        if o > 1.0:
            grup[(ev, mk)].append(1.0 / o)
    pazar = defaultdict(list)
    for (ev, mk), v in grup.items():
        pazar[mk].append(v)
    for mk, gruplar in sorted(pazar.items()):
        k = Counter(len(v) for v in gruplar).most_common(1)[0][0]
        mj = sorted(sum(v) - 1 for v in gruplar if len(v) == k)
        if len(mj) < 5:
            continue
        print(f"   {mk:12s} {k:2d} seçenek · {len(mj):3d} maç · medyan marj "
              f"%{mj[len(mj)//2]*100:5.1f}  (en düşük %{mj[0]*100:.1f})")
    print("   belgenin eşiği: marj %5'i geçerse edge bulmak 'çok zor'")


if __name__ == "__main__":
    sina()
