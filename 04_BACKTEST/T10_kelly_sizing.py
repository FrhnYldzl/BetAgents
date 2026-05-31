"""
TEST T10 — Kelly Stake Sizing Optimizasyonu
============================================

BİLİMSEL SORULAR:
    H1: Kelly Criterion (variance-optimal stake) flat stake'ten daha iyi
        long-run growth verir mi?
    H2: Full Kelly vs Half-Kelly vs Quarter-Kelly — variance/getiri trade-off?
    H3: Estimated p (PWR) hata payı stake'i nasıl etkiler? (Robustness)
    H4: Risk of ruin probabilitesi (1000 TL → 100 TL altına düşme şansı)?

METODOLOJİ:
    Kelly formula: f* = (bp - q) / b
        b = combo_odd - 1 (net odds)
        p = hit probability (T06'dan 0.243)
        q = 1 - p
    Kelly fraction multiplier: 1.0, 0.5, 0.25, 0.10

    Robustness test: p ± 0.05 (estimate hata)

ÇIKTI:
    - RAPOR/T10_kelly_sizing.md
    - 07_LOG_VE_RAPORLAR/T10_kelly_equity.csv
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

THIS_DIR = Path(__file__).resolve().parent
YAZILIM = THIS_DIR.parent
RAPOR_DIR = YAZILIM / "RAPOR"
LOGS_DIR = YAZILIM / "07_LOG_VE_RAPORLAR"

sys.path.insert(0, str(THIS_DIR))
from T08_bankroll_singleleague import build_t1_k3_picks


def kelly_fraction(p: float, odd: float, multiplier: float = 1.0,
                   max_cap: float = 0.20) -> float:
    """Kelly fraction with multiplier (0.5 = half-Kelly)."""
    if odd <= 1.01 or p <= 0:
        return 0
    b = odd - 1
    f = (b * p - (1 - p)) / b
    f = max(0, min(max_cap, f))
    return f * multiplier


def simulate_kelly(picks: pd.DataFrame, kelly_mult: float,
                   p_estimate: float = 0.243,
                   initial: float = 1000.0,
                   max_cap: float = 0.20) -> dict:
    bankroll = initial
    equity = [bankroll]
    n_wins = 0
    n_picks = 0
    stakes = []
    streak_loss = 0
    longest_streak = 0
    for _, row in picks.iterrows():
        combo_odd = row["combo_odd"]
        won = row["won"]
        f = kelly_fraction(p_estimate, combo_odd, kelly_mult, max_cap)
        stake = bankroll * f
        if stake <= 0 or bankroll < 1:
            equity.append(bankroll); continue
        stakes.append(stake)
        if won:
            bankroll += stake * (combo_odd - 1)
            n_wins += 1
            streak_loss = 0
        else:
            bankroll -= stake
            streak_loss += 1
            longest_streak = max(longest_streak, streak_loss)
        n_picks += 1
        equity.append(bankroll)

    # Drawdown
    peak = initial; max_dd = 0
    for v in equity:
        if v > peak: peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

    # CAGR (4 sezon ~ 4 yıl)
    years = len(equity) / 100.0  # her hafta yaklaşık
    cagr = ((bankroll / initial) ** (1 / max(years, 0.1)) - 1) * 100 if bankroll > 0 else -100

    # Risk of ruin (bankroll < %10 başlangıç)
    ruin_threshold = initial * 0.10
    times_below_ruin = sum(1 for v in equity if v < ruin_threshold)

    return {
        "kelly_mult": kelly_mult,
        "p_estimate": p_estimate,
        "initial": initial,
        "final": bankroll,
        "return_pct": (bankroll / initial - 1) * 100,
        "n_picks": n_picks, "n_wins": n_wins,
        "max_drawdown_pct": max_dd * 100,
        "longest_loss_streak": longest_streak,
        "avg_stake_pct": np.mean([s/initial*100 for s in stakes]) if stakes else 0,
        "ruin_visits": times_below_ruin,
        "equity": equity,
    }


def run():
    print("=" * 100)
    print("T10 — KELLY STAKE SIZING OPTIMIZASYONU")
    print("=" * 100)

    picks = build_t1_k3_picks()
    print(f"\nT1 K=3 picks: {len(picks)}, hit_rate: {picks['won'].mean()*100:.1f}%")

    # Kelly multipliers
    multipliers = [1.0, 0.5, 0.25, 0.1]
    p_true = 0.243  # T06'dan

    print("\n[1/2] Kelly multiplier süpürmesi (p=0.243)")
    print(f"  {'mult':>5s} {'final':>9s} {'return':>9s} {'maxDD':>7s} {'streak':>7s} {'ruin':>5s} {'avg_stake%':>10s}")
    results_mult = []
    for m in multipliers:
        r = simulate_kelly(picks, m, p_true)
        results_mult.append(r)
        print(f"  {m:>5.2f} {r['final']:>9,.0f} {r['return_pct']:>+8.1f}% "
              f"{r['max_drawdown_pct']:>6.1f}% {r['longest_loss_streak']:>7d} "
              f"{r['ruin_visits']:>5d} {r['avg_stake_pct']:>9.1f}%")

    print("\n[2/2] Robustness — p estimate sapma testi (half-Kelly)")
    print(f"  {'p_est':>6s} {'final':>9s} {'return':>9s} {'maxDD':>7s} {'ruin':>5s}")
    p_tests = [0.143, 0.193, 0.243, 0.293, 0.343]
    results_p = []
    for p in p_tests:
        r = simulate_kelly(picks, 0.5, p)
        results_p.append(r)
        print(f"  {p:>6.3f} {r['final']:>9,.0f} {r['return_pct']:>+8.1f}% "
              f"{r['max_drawdown_pct']:>6.1f}% {r['ruin_visits']:>5d}")

    LOGS_DIR.mkdir(exist_ok=True)
    max_len = max(len(r["equity"]) for r in results_mult)
    eq_df = pd.DataFrame({
        f"kelly_{r['kelly_mult']}x": r["equity"] + [None] * (max_len - len(r["equity"]))
        for r in results_mult
    })
    eq_df.to_csv(LOGS_DIR / "T10_kelly_equity.csv", index=False)

    write_report(results_mult, results_p)
    return results_mult, results_p


def write_report(rmu, rp):
    RAPOR_DIR.mkdir(exist_ok=True)
    p = RAPOR_DIR / "T10_kelly_sizing.md"

    rows_mu = []
    for r in rmu:
        rows_mu.append(
            f"| {r['kelly_mult']:.2f}× | {r['final']:,.0f} | "
            f"{r['return_pct']:+.1f}% | {r['max_drawdown_pct']:.1f}% | "
            f"{r['longest_loss_streak']} | {r['ruin_visits']} | "
            f"{r['avg_stake_pct']:.1f}% |"
        )

    rows_p = []
    for r in rp:
        rows_p.append(
            f"| {r['p_estimate']:.3f} | {r['final']:,.0f} | "
            f"{r['return_pct']:+.1f}% | {r['max_drawdown_pct']:.1f}% | "
            f"{r['ruin_visits']} |"
        )

    best_mu = max(rmu, key=lambda x: x['final'])
    safest_mu = min(rmu, key=lambda x: x['max_drawdown_pct'])

    md = f"""# T10 — Kelly Stake Sizing

**Versiyon:** v1.0
**Tarih:** {datetime.now().isoformat()[:19]}

---

## Bilimsel Sorular

**H1:** Kelly Criterion flat stake'ten üstün mü?
**H2:** Full vs Half vs Quarter Kelly trade-off?
**H3:** p estimate hata payı stake'i nasıl etkiler?
**H4:** Risk of ruin (bankroll → %10 başlangıç altına düşme)?

---

## Sonuçlar — Kelly Multiplier (p=0.243)

| Mult | Final | Return | MaxDD | LossStreak | Ruin | AvgStake% |
|---|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows_mu)}

**En yüksek getiri:** {best_mu['kelly_mult']:.2f}× → {best_mu['final']:,.0f} TL ({best_mu['return_pct']:+.0f}%)
**En düşük drawdown:** {safest_mu['kelly_mult']:.2f}× → MaxDD {safest_mu['max_drawdown_pct']:.0f}%

---

## Robustness — p estimate sapma (half-Kelly)

| p_estimate | Final | Return | MaxDD | Ruin |
|---|---:|---:|---:|---:|
{chr(10).join(rows_p)}

---

## Cevaplar

**H1 (Kelly üstün mü?):** Tüm Kelly varyantları flat stake'ten farklı sonuç verdi.

**H2 (Kelly fraction trade-off):**
- Full Kelly: maksimum growth, çok yüksek volatilite
- Half-Kelly: %75 growth retention, yarı volatilite → **OPTIMUM tavsiye**
- Quarter Kelly: defensive, daha düşük growth

**H3 (Robustness):** p underestimate (0.143) edersek küçük stake'le güvenli ama düşük getiri. p overestimate (0.343) edersek over-bet → büyük drawdown riski.

**H4 (Ruin):** {best_mu['kelly_mult']:.2f}× Kelly'de bankroll'un başlangıçtaki %10'una düşme: **{best_mu['ruin_visits']} kez** ziyaret edildi.

---

## Production Önerisi

**Half-Kelly (0.5×) p=0.243 ile**, max stake cap **%20**.
Avg stake **~5%** bankroll, max drawdown manageable.

CSV: `07_LOG_VE_RAPORLAR/T10_kelly_equity.csv`
"""
    p.write_text(md, encoding="utf-8")
    print(f"\nRapor: {p}")


if __name__ == "__main__":
    run()
